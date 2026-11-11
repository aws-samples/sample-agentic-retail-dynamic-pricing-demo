"""POST /approvals authorization (CWE-862 report).

Reproduces the reported proof of concept: an account whose only Cognito group
is Operations approved a HIGH risk scenario (with a 50+ character comment) and
overwrote live product prices. Approving or rejecting now requires the
PricingAnalysts group, reverting requires Operations, both by exact group
name, and both are checked before any read or write.

DynamoDB is moto; no AWS calls are made.
"""

import json
from decimal import Decimal

import boto3
import pytest
from moto import mock_aws

from backend.api_handlers import approvals

REGION = "us-east-1"
CYCLE_ID = "cyc-001"
SCENARIO_ID = "scn-100"
PRODUCT_ID = "ELEC-001"
INITIATOR = "user-initiator-sub"
ANALYST = "user-analyst-sub"
OPS = "user-ops-sub"
JUSTIFICATION = "Approving to match the competitor's price drop on this category this week."


def _table(name, hash_key, range_key=None):
    keys = [{"AttributeName": hash_key, "KeyType": "HASH"}]
    attrs = [{"AttributeName": hash_key, "AttributeType": "S"}]
    if range_key:
        keys.append({"AttributeName": range_key, "KeyType": "RANGE"})
        attrs.append({"AttributeName": range_key, "AttributeType": "S"})
    boto3.client("dynamodb", region_name=REGION).create_table(
        TableName=name, KeySchema=keys, AttributeDefinitions=attrs, BillingMode="PAY_PER_REQUEST",
    )


@pytest.fixture
def aws(monkeypatch):
    for var, value in {
        "AWS_ACCESS_KEY_ID": "testing",
        "AWS_SECRET_ACCESS_KEY": "testing",
        "AWS_DEFAULT_REGION": REGION,
        "PRICING_CYCLES_TABLE": "PricingCycles",
        "AUDIT_TRAIL_TABLE": "AuditTrail",
    }.items():
        monkeypatch.setenv(var, value)
    monkeypatch.delenv("IMPLEMENTATION_MONITORING_AGENT_ARN", raising=False)
    with mock_aws():
        _table(approvals.APPROVALS_TABLE, "scenarioId", "timestamp")
        _table(approvals.PRICING_SCENARIOS_TABLE, "cycleId", "scenarioId")
        _table(approvals.PRODUCTS_TABLE, "productId")
        _table("PricingCycles", "cycleId", "status")
        _table("AuditTrail", "scenarioId", "timestamp#ruleId")
        ddb = boto3.resource("dynamodb", region_name=REGION)
        ddb.Table("PricingCycles").put_item(Item={
            "cycleId": CYCLE_ID, "status": "COMPLETE", "requestedBy": INITIATOR,
        })
        ddb.Table(approvals.PRODUCTS_TABLE).put_item(Item={
            "productId": PRODUCT_ID, "currentPrice": Decimal("100.00"),
        })
        yield ddb


def _scenario(ddb, status=None):
    item = {
        "cycleId": CYCLE_ID,
        "scenarioId": SCENARIO_ID,
        "riskLevel": "HIGH",
        "priceChanges": [{"productId": PRODUCT_ID, "currentPrice": 100.0, "newPrice": 79.99}],
    }
    if status:
        item["approvalStatus"] = status
    ddb.Table(approvals.PRICING_SCENARIOS_TABLE).put_item(Item=approvals._convert_floats_to_decimal(item))


def _post(body, sub, groups):
    claims = {"sub": sub}
    if groups is not None:
        claims["cognito:groups"] = groups
    return approvals.handler({
        "httpMethod": "POST",
        "path": "/approvals",
        "body": json.dumps(body),
        "requestContext": {"authorizer": {"claims": claims}},
    }, None)


def _approve(sub, groups, action="APPROVED"):
    return _post({
        "scenarioId": SCENARIO_ID, "action": action, "comment": JUSTIFICATION, "cycleId": CYCLE_ID,
    }, sub, groups)


def _revert(sub, groups):
    return _post({
        "scenarioId": SCENARIO_ID, "action": "REJECTED", "cycleId": CYCLE_ID,
        "comment": "Price revert", "revertPrices": True,
    }, sub, groups)


def _price(ddb):
    return ddb.Table(approvals.PRODUCTS_TABLE).get_item(Key={"productId": PRODUCT_ID})["Item"]["currentPrice"]


def _stored(ddb):
    return ddb.Table(approvals.PRICING_SCENARIOS_TABLE).get_item(
        Key={"cycleId": CYCLE_ID, "scenarioId": SCENARIO_ID},
    )["Item"]


def _nothing_written(ddb, expected_status=None):
    assert _price(ddb) == Decimal("100.00")
    assert _stored(ddb).get("approvalStatus") == expected_status
    assert ddb.Table(approvals.APPROVALS_TABLE).scan()["Items"] == []
    assert ddb.Table("AuditTrail").scan()["Items"] == []


class TestReportedProofOfConcept:
    def test_operations_only_account_cannot_approve_or_change_prices(self, aws):
        """The exact report: Operations-only, HIGH risk, 50+ char comment, not the initiator."""
        _scenario(aws)
        response = _approve(OPS, "Operations")
        assert response["statusCode"] == 403
        assert "PricingAnalysts" in json.loads(response["body"])["error"]
        _nothing_written(aws)

    def test_operations_only_account_cannot_reject(self, aws):
        _scenario(aws)
        assert _approve(OPS, "Operations", action="REJECTED")["statusCode"] == 403
        _nothing_written(aws)


class TestApproverRole:
    @pytest.mark.parametrize("groups", [
        "PricingAnalysts", "Operations,PricingAnalysts", "[Operations, PricingAnalysts]", ["PricingAnalysts"],
    ])
    def test_pricing_analyst_can_approve_and_prices_update(self, aws, groups):
        _scenario(aws)
        response = _approve(ANALYST, groups)
        assert response["statusCode"] == 200, response["body"]
        assert _price(aws) == Decimal("79.99")
        stored = _stored(aws)
        assert stored["approvalStatus"] == "APPROVED"
        assert stored["approvedBy"] == ANALYST

    def test_pricing_analyst_can_reject(self, aws):
        _scenario(aws)
        assert _approve(ANALYST, "PricingAnalysts", action="REJECTED")["statusCode"] == 200
        assert _stored(aws)["approvalStatus"] == "REJECTED"
        assert _price(aws) == Decimal("100.00")

    @pytest.mark.parametrize("groups", [None, "", "NotPricingAnalysts", "PricingAnalystsReadOnly", "pricinganalysts"])
    def test_no_group_or_lookalike_group_is_denied(self, aws, groups):
        """Exact names only: substring and case-insensitive matches are rejected."""
        _scenario(aws)
        assert _approve(ANALYST, groups)["statusCode"] == 403
        _nothing_written(aws)

    def test_separation_of_duties_still_applies_to_analysts(self, aws):
        _scenario(aws)
        response = _approve(INITIATOR, "PricingAnalysts")
        assert response["statusCode"] == 403
        assert "Separation of duties" in json.loads(response["body"])["error"]
        _nothing_written(aws)

    def test_role_is_checked_before_any_database_access(self, aws, monkeypatch):
        """Deny by default: an unauthorized call must not reach DynamoDB at all."""
        calls = []
        monkeypatch.setattr(approvals, "_get_dynamodb_resource", lambda: calls.append(1))
        assert _approve(OPS, "Operations")["statusCode"] == 403
        assert calls == []


class TestRevertRole:
    def test_operations_can_revert(self, aws):
        _scenario(aws, status="APPROVED")
        aws.Table(approvals.PRODUCTS_TABLE).put_item(Item={
            "productId": PRODUCT_ID, "currentPrice": Decimal("79.99"), "previousPrice": Decimal("100.00"),
        })
        response = _revert(OPS, "Operations")
        assert response["statusCode"] == 200, response["body"]

    @pytest.mark.parametrize("groups", ["PricingAnalysts", "NotOperations", "OperationsReadOnly", ""])
    def test_non_operations_revert_is_denied_before_any_write(self, aws, groups):
        """The old check ran after the approval record and REJECTED status were written."""
        _scenario(aws, status="APPROVED")
        assert _revert(ANALYST, groups)["statusCode"] == 403
        _nothing_written(aws, expected_status="APPROVED")


class TestErrorResponses:
    def test_internal_errors_do_not_leak_exception_text(self, aws, monkeypatch):
        def boom():
            raise RuntimeError("secret-internal-detail")

        monkeypatch.setattr(approvals, "_get_dynamodb_resource", boom)
        response = _approve(ANALYST, "PricingAnalysts")
        assert response["statusCode"] == 500
        assert "secret-internal-detail" not in response["body"]
