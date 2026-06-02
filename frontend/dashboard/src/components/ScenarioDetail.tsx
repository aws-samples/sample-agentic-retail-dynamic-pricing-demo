import type { PricingScenario, GuardrailResult } from './ScenarioList';
import { useState, useRef } from 'react';
import ApprovalActions from './ApprovalActions';
import api from '../lib/api';
import Tooltip from './Tooltip';
import { getFactorTooltip } from '../lib/methodologyData';
import MethodologyPanel from './MethodologyPanel';

interface ScenarioDetailProps {
  scenario: PricingScenario;
  showContributingFactors?: boolean;
}

export default function ScenarioDetail({ scenario, showContributingFactors = true }: ScenarioDetailProps) {
  const [reverting, setReverting] = useState(false);
  const [reverted, setReverted] = useState(false);
  const [revertError, setRevertError] = useState<string | null>(null);

  const handleRevert = async () => {
    setReverting(true);
    setRevertError(null);
    try {
      await api.post('/approvals', {
        scenarioId: scenario.scenarioId,
        cycleId: scenario.cycleId,
        action: 'REJECTED',
        comment: `Price revert: Rolling back ${scenario.priceChanges.length} price changes to previous values.`,
        riskLevel: scenario.riskLevel,
        revertPrices: true,
      });
      setReverted(true);
    } catch (err: unknown) {
      setRevertError(err instanceof Error ? err.message : 'Failed to revert prices');
    } finally {
      setReverting(false);
    }
  };

  return (
    <div className="bg-gray-50 border-t border-gray-200 p-6 space-y-6">
      {/* Price Changes Section */}
      <section>
        <h3 className="text-sm font-semibold text-gray-900 mb-3">Price Changes</h3>
        {scenario.priceChanges.length > 0 ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {scenario.priceChanges.map((change) => (
              <div
                key={change.productId}
                className="bg-white rounded-md border border-gray-200 p-3"
              >
                <p className="text-sm font-medium text-gray-900 truncate">
                  {(change as any).productName || change.productId}
                </p>
                <p className="text-[10px] text-gray-400 font-mono">{change.productId}</p>
                <div className="flex items-center gap-2 mt-1">
                  <span className="text-sm text-gray-600 line-through">
                    ${change.currentPrice.toFixed(2)}
                  </span>
                  <span className="text-sm font-semibold text-gray-900">
                    ${change.newPrice.toFixed(2)}
                  </span>
                  <span
                    className={`text-xs font-medium ${
                      change.changePercent >= 0 ? 'text-green-600' : 'text-red-600'
                    }`}
                  >
                    {change.changePercent >= 0 ? '+' : ''}
                    {change.changePercent.toFixed(2)}%
                  </span>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-sm text-gray-500">No price changes in this scenario.</p>
        )}
      </section>

      {/* Contributing Factors (shown for top 3 scenarios) */}
      {showContributingFactors && (
        <ContributingFactorsSection scenario={scenario} />
      )}

      {/* Data Sources and Confidence Rationale */}
      <section className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="bg-white rounded-md border border-gray-200 p-4">
          <h4 className="text-sm font-semibold text-gray-900 mb-2">Data Sources Consulted</h4>
          <DataSourcesList scenario={scenario} />
        </div>

        <div className="bg-white rounded-md border border-gray-200 p-4">
          <h4 className="text-sm font-semibold text-gray-900 mb-2">Confidence Score Rationale</h4>
          <ConfidenceRationale scenario={scenario} />
        </div>
      </section>

      {/* Guardrail Results */}
      <section>
        <h3 className="text-sm font-semibold text-gray-900 mb-3">Guardrail Results</h3>
        {scenario.guardrailResults.length > 0 ? (
          <div className="space-y-2">
            {scenario.guardrailResults.map((result, idx) => (
              <GuardrailResultRow key={`${result.rule}-${idx}`} result={result} />
            ))}
          </div>
        ) : (
          <p className="text-sm text-gray-500">No guardrail evaluations recorded.</p>
        )}
      </section>

      {/* Summary Metrics */}
      <section className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <MetricCard
          label="Composite Score"
          value={scenario.compositeScore.toFixed(2)}
        />
        <MetricCard
          label="Confidence"
          value={`${scenario.confidenceScore}/100`}
        />
        <MetricCard
          label="Risk Level"
          value={scenario.riskLevel}
          valueClass={riskLevelColor(scenario.riskLevel)}
        />
        <MetricCard
          label="Market Share Impact"
          value={
            scenario.projectedMarketShare !== undefined
              ? `${scenario.projectedMarketShare >= 0 ? '+' : ''}${scenario.projectedMarketShare.toFixed(2)}%`
              : 'N/A'
          }
        />
      </section>

      {/* AI Rationale */}
      {(scenario as any).aiRationale && (
        <section className="bg-blue-50 border border-blue-200 rounded-md p-4">
          <h3 className="text-sm font-semibold text-blue-900 mb-2">AI Decision Rationale</h3>
          <p className="text-sm text-blue-800">{(scenario as any).aiRationale}</p>
        </section>
      )}

      {/* Approval Actions (HITL) */}
      {!scenario.approvalStatus && (
        <ApprovalActions
          scenarioId={scenario.scenarioId}
          cycleId={scenario.cycleId}
          riskLevel={scenario.riskLevel}
          statusLabel={scenario.statusLabel}
        />
      )}

      {scenario.approvalStatus && (
        <div className={`rounded-md border p-4 ${
          scenario.approvalStatus === 'APPROVED'
            ? 'bg-green-50 border-green-200'
            : 'bg-red-50 border-red-200'
        }`}>
          <div className="flex items-center justify-between">
            <div>
              <p className={`text-sm font-medium ${
                scenario.approvalStatus === 'APPROVED' ? 'text-green-800' : 'text-red-800'
              }`}>
                {scenario.approvalStatus === 'APPROVED' ? '✓ Approved' : '✗ Rejected'}
                {scenario.approvedBy && ` by ${scenario.approvedBy}`}
                {scenario.approvedAt && ` on ${new Date(scenario.approvedAt).toLocaleString()}`}
              </p>
              {scenario.approvalComment && (
                <p className="text-sm text-gray-600 mt-1">{scenario.approvalComment}</p>
              )}
            </div>
            {scenario.approvalStatus === 'APPROVED' && !reverted && (
              <button
                onClick={handleRevert}
                disabled={reverting}
                className="px-3 py-1.5 text-xs font-medium text-amber-700 bg-amber-50 border border-amber-300 rounded-md hover:bg-amber-100 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                {reverting ? 'Reverting...' : '↩ Revert Prices'}
              </button>
            )}
          </div>
          {reverted && (
            <p className="text-xs text-amber-700 mt-2 font-medium">
              ↩ Prices reverted to previous values. Refresh the storefront to see changes.
            </p>
          )}
          {revertError && (
            <p className="text-xs text-red-600 mt-2">{revertError}</p>
          )}
        </div>
      )}
    </div>
  );
}

interface FactorsCardProps {
  title: string;
  icon: string;
  factors: Record<string, unknown>;
  colorClass: string;
}

function ContributingFactorsSection({ scenario }: { scenario: PricingScenario }) {
  const [methodologyOpen, setMethodologyOpen] = useState(false);
  const methodologyBtnRef = useRef<HTMLButtonElement>(null);

  return (
    <section className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-gray-900">Contributing Factors</h3>
        <button
          ref={methodologyBtnRef}
          onClick={() => setMethodologyOpen(true)}
          className="text-xs text-indigo-600 hover:text-indigo-800 font-medium transition-colors"
        >
          📖 View Methodology
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* Competitive Factors */}
        <FactorsCard
          title="Competitive Factors"
          icon="🏪"
          factors={scenario.competitiveFactors}
          colorClass="border-blue-200 bg-blue-50/50"
        />

        {/* Demand Factors */}
        <FactorsCard
          title="Demand Factors"
          icon="📈"
          factors={scenario.demandFactors}
          colorClass="border-purple-200 bg-purple-50/50"
        />

        {/* Market Factors */}
        <FactorsCard
          title="Market Factors"
          icon="🌐"
          factors={scenario.marketFactors}
          colorClass="border-teal-200 bg-teal-50/50"
        />
      </div>

      <MethodologyPanel
        isOpen={methodologyOpen}
        onClose={() => setMethodologyOpen(false)}
        triggerRef={methodologyBtnRef}
      />
    </section>
  );
}

function FactorsCard({ title, icon, factors, colorClass }: FactorsCardProps) {
  const entries = Object.entries(factors);

  return (
    <div className={`rounded-md border p-4 ${colorClass}`}>
      <h4 className="text-sm font-semibold text-gray-800 flex items-center gap-1.5 mb-2">
        <span>{icon}</span>
        {title}
      </h4>
      {entries.length > 0 ? (
        <dl className="space-y-1.5">
          {entries.slice(0, 6).map(([key, value]) => {
            const tooltip = getFactorTooltip(key);
            return (
              <div key={key} className="flex justify-between text-xs">
                <dt className="text-gray-600 capitalize">
                  {tooltip ? (
                    <Tooltip content={tooltip}>
                      <span className="underline decoration-dotted cursor-help">{formatKey(key)}</span>
                    </Tooltip>
                  ) : (
                    formatKey(key)
                  )}
                </dt>
                <dd className="text-gray-900 font-medium truncate max-w-[50%] text-right">
                  {formatValue(value)}
                </dd>
              </div>
            );
          })}
          {entries.length > 6 && (
            <p className="text-xs text-gray-500 italic">
              +{entries.length - 6} more factors
            </p>
          )}
        </dl>
      ) : (
        <p className="text-xs text-gray-500">No data available</p>
      )}
    </div>
  );
}

function DataSourcesList({ scenario }: { scenario: PricingScenario }) {
  const sources: string[] = [];

  if (Object.keys(scenario.competitiveFactors).length > 0) {
    sources.push('Competitor API Server');
  }
  if (Object.keys(scenario.demandFactors).length > 0) {
    sources.push('ERP/POS Server');
  }
  if (Object.keys(scenario.marketFactors).length > 0) {
    sources.push('Market Signals Server');
  }

  // Always include Cost & Finance since scenarios require guardrail evaluation
  sources.push('Cost & Finance Server');

  return (
    <ul className="space-y-1.5">
      {sources.map((source) => (
        <li key={source} className="flex items-center gap-2 text-sm text-gray-700">
          <span className="w-2 h-2 rounded-full bg-green-400 flex-shrink-0" />
          {source}
        </li>
      ))}
    </ul>
  );
}

function ConfidenceRationale({ scenario }: { scenario: PricingScenario }) {
  const factors: string[] = [];

  const competitiveCount = Object.keys(scenario.competitiveFactors).length;
  const demandCount = Object.keys(scenario.demandFactors).length;
  const marketCount = Object.keys(scenario.marketFactors).length;
  const guardrailsPassed = scenario.guardrailResults.filter((r) => r.passed).length;
  const guardrailsTotal = scenario.guardrailResults.length;

  if (competitiveCount > 0) {
    factors.push(`${competitiveCount} competitive data points analyzed`);
  }
  if (demandCount > 0) {
    factors.push(`${demandCount} demand signals incorporated`);
  }
  if (marketCount > 0) {
    factors.push(`${marketCount} market indicators evaluated`);
  }
  if (guardrailsTotal > 0) {
    factors.push(`${guardrailsPassed}/${guardrailsTotal} guardrails passed`);
  }

  if (scenario.confidenceScore >= 80) {
    factors.push('Strong alignment across all data sources');
  } else if (scenario.confidenceScore >= 60) {
    factors.push('Moderate alignment with some uncertainty');
  } else {
    factors.push('Limited data alignment — higher uncertainty');
  }

  return (
    <ul className="space-y-1.5">
      {factors.map((factor, idx) => (
        <li key={idx} className="flex items-start gap-2 text-sm text-gray-700">
          <span className="text-gray-400 mt-0.5">•</span>
          {factor}
        </li>
      ))}
    </ul>
  );
}

function GuardrailResultRow({ result }: { result: GuardrailResult }) {
  return (
    <div
      className={`flex items-center justify-between px-3 py-2 rounded-md border text-sm ${
        result.passed
          ? 'bg-green-50 border-green-200'
          : 'bg-red-50 border-red-200'
      }`}
    >
      <div className="flex items-center gap-2">
        <span className={result.passed ? 'text-green-600' : 'text-red-600'}>
          {result.passed ? '✓' : '✗'}
        </span>
        <span className="font-medium text-gray-800">{result.rule}</span>
      </div>
      {result.reason && (
        <span className="text-xs text-gray-600 max-w-[50%] truncate">
          {result.reason}
        </span>
      )}
    </div>
  );
}

interface MetricCardProps {
  label: string;
  value: string;
  valueClass?: string;
}

function MetricCard({ label, value, valueClass = 'text-gray-900' }: MetricCardProps) {
  return (
    <div className="bg-white rounded-md border border-gray-200 p-3 text-center">
      <p className="text-xs text-gray-500 mb-1">{label}</p>
      <p className={`text-sm font-semibold ${valueClass}`}>{value}</p>
    </div>
  );
}

// Utility functions

function formatKey(key: string): string {
  return key
    .replace(/([A-Z])/g, ' $1')
    .replace(/_/g, ' ')
    .trim();
}

function formatValue(value: unknown): string {
  if (value === null || value === undefined) return 'N/A';
  if (typeof value === 'number') {
    if (Number.isInteger(value)) return value.toString();
    return value.toFixed(2);
  }
  if (typeof value === 'boolean') return value ? 'Yes' : 'No';
  if (typeof value === 'string') return value;
  if (Array.isArray(value)) return `[${value.length} items]`;
  if (typeof value === 'object') return `{${Object.keys(value).length} fields}`;
  return String(value);
}

function riskLevelColor(level: string): string {
  switch (level) {
    case 'LOW':
      return 'text-green-700';
    case 'MEDIUM':
      return 'text-yellow-700';
    case 'HIGH':
      return 'text-red-700';
    default:
      return 'text-gray-900';
  }
}
