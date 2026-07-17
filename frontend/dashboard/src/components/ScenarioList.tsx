import { useState, useEffect, useCallback } from 'react';
import api from '../lib/api';
import ScenarioDetail from './ScenarioDetail';

export interface PriceChange {
  productId: string;
  currentPrice: number;
  newPrice: number;
  changePercent: number;
}

export interface GuardrailResult {
  rule: string;
  passed: boolean;
  reason?: string;
}

export interface PricingScenario {
  scenarioId: string;
  cycleId: string;
  rank: number;
  strategyName?: string;
  confidenceScore: number;
  statusLabel: 'Recommended' | 'Review Required' | 'Human Exception Handling';
  riskLevel: 'LOW' | 'MEDIUM' | 'HIGH';
  priceChanges: PriceChange[];
  projectedRevenue: number;
  projectedMargin: number;
  projectedMarketShare?: number;
  compositeScore: number;
  competitiveFactors: Record<string, unknown>;
  demandFactors: Record<string, unknown>;
  marketFactors: Record<string, unknown>;
  guardrailResults: GuardrailResult[];
  approvalStatus?: string;
  approvalComment?: string;
  approvedBy?: string;
  approvedAt?: string;
  createdAt?: string;
}

interface ScenarioListProps {
  cycleId: string;
}

const PAGE_SIZE = 20;

const statusBadgeClasses: Record<string, string> = {
  Recommended: 'bg-green-100 text-green-800 border-green-200',
  'Review Required': 'bg-yellow-100 text-yellow-800 border-yellow-200',
  'Human Exception Handling': 'bg-red-100 text-red-800 border-red-200',
};

export default function ScenarioList({ cycleId }: ScenarioListProps) {
  const [scenarios, setScenarios] = useState<PricingScenario[]>([]);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [expandedScenarioId, setExpandedScenarioId] = useState<string | null>(null);

  const fetchScenarios = useCallback(async (pageNum: number) => {
    setLoading(true);
    setError(null);
    try {
      const response = await api.get(
        `/pricing-cycles/${cycleId}/scenarios`,
        { params: { page: pageNum, pageSize: PAGE_SIZE } }
      );
      const data = response.data;
      setScenarios(data.scenarios ?? data.items ?? []);
      setTotalPages(data.totalPages ?? (Math.ceil((data.total ?? 0) / PAGE_SIZE) || 1));
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to load scenarios';
      setError(message);
    } finally {
      setLoading(false);
    }
  }, [cycleId]);

  useEffect(() => {
    fetchScenarios(page);
  }, [page, fetchScenarios]);

  const handlePageChange = (newPage: number) => {
    if (newPage >= 1 && newPage <= totalPages) {
      setPage(newPage);
      setExpandedScenarioId(null);
    }
  };

  const toggleExpand = (scenarioId: string) => {
    setExpandedScenarioId((prev) => (prev === scenarioId ? null : scenarioId));
  };

  const formatCurrency = (value: number) =>
    new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(value);

  const formatPercent = (value: number) =>
    `${value >= 0 ? '+' : ''}${value.toFixed(2)}%`;

  // Determine which scenarios are in the top 3 (by rank)
  const top3Ranks = new Set(
    [...scenarios].sort((a, b) => a.rank - b.rank).slice(0, 5).map((s) => s.scenarioId)
  );

  if (loading && scenarios.length === 0) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600" />
        <span className="ml-3 text-gray-600">Loading scenarios...</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-red-50 border border-red-200 rounded-lg p-4">
        <p className="text-red-700 text-sm">{error}</p>
        <button
          onClick={() => fetchScenarios(page)}
          className="mt-2 text-sm text-red-600 underline hover:text-red-800"
        >
          Retry
        </button>
      </div>
    );
  }

  if (scenarios.length === 0) {
    return (
      <div className="text-center py-12 text-gray-500">
        No scenarios generated yet for this pricing cycle.
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-gray-900">
          Pricing Scenarios
        </h2>
        <span className="text-sm text-gray-500">
          Page {page} of {totalPages}
        </span>
      </div>

      {/* Scenario Table */}
      <div className="border border-gray-200 rounded-lg shadow-sm overflow-x-auto">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Rank / Strategy
              </th>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Confidence
              </th>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Status
              </th>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Projected Revenue
              </th>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Projected Margin
              </th>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Approval
              </th>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Actions
              </th>
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-gray-200">
            {scenarios.map((scenario) => (
              <ScenarioRow
                key={scenario.scenarioId}
                scenario={scenario}
                isTop3={top3Ranks.has(scenario.scenarioId)}
                isExpanded={expandedScenarioId === scenario.scenarioId}
                onToggle={() => toggleExpand(scenario.scenarioId)}
                formatCurrency={formatCurrency}
                formatPercent={formatPercent}
              />
            ))}
          </tbody>
        </table>
      </div>

      {/* Pagination Controls */}
      <PaginationControls
        page={page}
        totalPages={totalPages}
        onPageChange={handlePageChange}
      />
    </div>
  );
}

interface ScenarioRowProps {
  scenario: PricingScenario;
  isTop3: boolean;
  isExpanded: boolean;
  onToggle: () => void;
  formatCurrency: (value: number) => string;
  formatPercent: (value: number) => string;
}

function ScenarioRow({
  scenario,
  isTop3,
  isExpanded,
  onToggle,
  formatCurrency,
  formatPercent,
}: ScenarioRowProps) {
  return (
    <>
      <tr
        className={`hover:bg-gray-50 cursor-pointer transition-colors ${
          isTop3 ? 'bg-blue-50/30' : ''
        }`}
        onClick={onToggle}
      >
        <td className="px-4 py-3 whitespace-nowrap">
          <div className="flex items-center gap-2">
            <span className="inline-flex items-center justify-center w-8 h-8 rounded-full bg-gray-100 text-sm font-semibold text-gray-700">
              {scenario.rank}
            </span>
            <div>
              <span className="text-sm font-medium text-gray-900">{scenario.strategyName ?? `Strategy ${scenario.rank}`}</span>
              {isTop3 && (
                <span className="ml-2 text-[10px] text-blue-600 font-medium">Top 5</span>
              )}
            </div>
          </div>
        </td>
        <td className="px-4 py-3 whitespace-nowrap">
          <ConfidenceBadge score={scenario.confidenceScore} />
        </td>
        <td className="px-4 py-3 whitespace-nowrap">
          <span
            className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium border ${
              statusBadgeClasses[scenario.statusLabel] ?? 'bg-gray-100 text-gray-800 border-gray-200'
            }`}
          >
            {scenario.statusLabel}
          </span>
        </td>
        <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-900">
          {formatCurrency(scenario.projectedRevenue)}
        </td>
        <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-900">
          {formatPercent(scenario.projectedMargin)}
        </td>
        <td className="px-4 py-3 whitespace-nowrap">
          {scenario.approvalStatus ? (
            <div>
              <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${
                scenario.approvalStatus === 'APPROVED'
                  ? 'bg-green-100 text-green-800'
                  : 'bg-red-100 text-red-800'
              }`}>
                {scenario.approvalStatus === 'APPROVED' ? '✓ Approved' : '✗ Rejected'}
              </span>
              <p className="text-[10px] text-gray-500 mt-0.5">
                {scenario.approvedBy === 'system-auto-approval' ? '⚡ Auto (STP)' : scenario.approvedBy ?? ''}
              </p>
            </div>
          ) : (
            <span className="text-xs text-gray-400 italic">Pending</span>
          )}
        </td>
        <td className="px-4 py-3 whitespace-nowrap">
          <button
            className="text-blue-600 hover:text-blue-800 text-sm font-medium"
            onClick={(e) => {
              e.stopPropagation();
              onToggle();
            }}
          >
            {isExpanded ? 'Collapse' : 'Details'}
          </button>
        </td>
      </tr>
      {isExpanded && (
        <tr>
          <td colSpan={7} className="px-0 py-0">
            <ScenarioDetail scenario={scenario} showContributingFactors={isTop3} />
          </td>
        </tr>
      )}
    </>
  );
}

function ConfidenceBadge({ score }: { score: number }) {
  let colorClass = 'bg-red-100 text-red-700';
  if (score >= 80) {
    colorClass = 'bg-green-100 text-green-700';
  } else if (score >= 60) {
    colorClass = 'bg-yellow-100 text-yellow-700';
  } else if (score >= 40) {
    colorClass = 'bg-orange-100 text-orange-700';
  }

  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold ${colorClass}`}>
      {score}/100
    </span>
  );
}

interface PaginationControlsProps {
  page: number;
  totalPages: number;
  onPageChange: (page: number) => void;
}

function PaginationControls({ page, totalPages, onPageChange }: PaginationControlsProps) {
  const getPageNumbers = (): (number | '...')[] => {
    const pages: (number | '...')[] = [];
    if (totalPages <= 7) {
      for (let i = 1; i <= totalPages; i++) pages.push(i);
    } else {
      pages.push(1);
      if (page > 3) pages.push('...');
      const start = Math.max(2, page - 1);
      const end = Math.min(totalPages - 1, page + 1);
      for (let i = start; i <= end; i++) pages.push(i);
      if (page < totalPages - 2) pages.push('...');
      pages.push(totalPages);
    }
    return pages;
  };

  return (
    <nav className="flex items-center justify-between border-t border-gray-200 pt-4">
      <button
        onClick={() => onPageChange(page - 1)}
        disabled={page <= 1}
        className="inline-flex items-center px-3 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
      >
        ← Previous
      </button>

      <div className="flex items-center gap-1">
        {getPageNumbers().map((p, idx) =>
          p === '...' ? (
            <span key={`ellipsis-${idx}`} className="px-2 py-1 text-gray-400">
              …
            </span>
          ) : (
            <button
              key={p}
              onClick={() => onPageChange(p)}
              className={`px-3 py-1 text-sm rounded-md ${
                p === page
                  ? 'bg-blue-600 text-white font-semibold'
                  : 'text-gray-700 hover:bg-gray-100'
              }`}
            >
              {p}
            </button>
          )
        )}
      </div>

      <button
        onClick={() => onPageChange(page + 1)}
        disabled={page >= totalPages}
        className="inline-flex items-center px-3 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
      >
        Next →
      </button>
    </nav>
  );
}
