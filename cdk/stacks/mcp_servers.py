"""CDK construct for MCP Server Lambda functions.

Defines the 4 MCP Server Lambda functions that provide tool interfaces
for agents to access external data sources (simulated for MVP demo):
- Competitor API Server: competitor pricing data
- ERP/POS Server: sales history and POS data
- Market Signals Server: market trends and sentiment
- Cost & Finance Server: cost structures and margin targets
"""

from pathlib import Path

from constructs import Construct
import aws_cdk as cdk
from aws_cdk import aws_lambda as lambda_


# Path to the backend/mcp_servers directory relative to the CDK project root
MCP_SERVERS_DIR = Path(__file__).parent.parent.parent / "backend" / "mcp_servers"


class McpServersConstruct(Construct):
    """Construct containing all MCP Server Lambda functions.

    Each Lambda function represents an MCP Server that provides tool
    interfaces for agents to access external data sources. All functions
    use Python 3.12 runtime, 256 MB memory, and 30s timeout.
    """

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id)

        # Create Lambda functions for each MCP Server
        self.competitor_api_fn = self._create_mcp_lambda(
            "CompetitorApi",
            "Competitor API MCP Server - provides competitor pricing data",
            "competitor_api",
        )

        self.erp_pos_fn = self._create_mcp_lambda(
            "ErpPos",
            "ERP/POS MCP Server - provides sales history and POS data",
            "erp_pos",
        )

        self.market_signals_fn = self._create_mcp_lambda(
            "MarketSignals",
            "Market Signals MCP Server - provides market trends and sentiment",
            "market_signals",
        )

        self.cost_finance_fn = self._create_mcp_lambda(
            "CostFinance",
            "Cost & Finance MCP Server - provides cost structures and margin targets",
            "cost_finance",
        )

    def _create_mcp_lambda(
        self,
        name: str,
        description: str,
        handler_dir: str,
    ) -> lambda_.Function:
        """Create a Lambda function for an MCP Server.

        Args:
            name: Logical name for the Lambda function construct.
            description: Description of the MCP Server's purpose.
            handler_dir: Subdirectory name under backend/mcp_servers/ containing the handler.

        Returns:
            The created Lambda function.
        """
        fn = lambda_.Function(
            self,
            f"{name}McpServer",
            function_name=f"rdp-mcp-{handler_dir.replace('_', '-')}",
            description=description,
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="handler.handler",
            code=lambda_.Code.from_asset(
                str(MCP_SERVERS_DIR / handler_dir),
            ),
            memory_size=256,
            timeout=cdk.Duration.seconds(30),
        )

        # Tag the function for identification
        cdk.Tags.of(fn).add("Component", "McpServer")
        cdk.Tags.of(fn).add("McpServer", name)

        return fn
