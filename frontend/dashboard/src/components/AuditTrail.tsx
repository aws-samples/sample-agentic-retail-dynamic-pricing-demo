import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import api from '../lib/api';
import { formatPricingGroup } from '../lib/productNames';

interface AuditCycle {
  cycleId: string;
  status: string;
  pricingGroup: string;
  objectives: string[];
  constraints: Record<string, unknown>;
  scenarioCount: number;
  requestedBy: string;
  createdAt: string;
  completedAt?: string;
  scenarios?: AuditScenario[];
}

interface AuditScenario {
  scenarioId: string;
  rank: number;
  riskLevel: string;
  statusLabel: string;
  confidenceScore: number;
  projectedRevenue: number;
  projectedMargin: number;
  aiRationale?: string;
  approvalStatus?: string;
  approvedBy?: string;
  approvedAt?: string;
  approvalComment?: string;
  guardrailResults?: { rule: string; passed: boolean; reason?: string }[];
  priceChanges?: { productId: string; productName?: string; currentPrice: number; newPrice: number; changePercent: number }[];
}

const STATUS_BADGE: Record<string, string> = {
  COMPLETE: 'bg-green-100 text-green-800',
  FAILED: 'bg-red-100 text-red-800',
  ANALYZING: 'bg-blue-100 text-blue-800',
  INITIATED: 'bg-gray-100 text-gray-800',
};

export default function AuditTrail() {
  const [cycles, setCycles] = useState<AuditCycle[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedId, setExpandedId] = useState<string | null>(null);

  useEffect(() => {
    const fetchCycles = async () => {
      try {
        const response = await api.get('/pricing-cycles');
        const data = response.data;
        setCycles(data.cycles ?? []);
        setError(null);
      } catch (err: unknown) {
        setError(err instanceof Error ? err.message : 'Failed to load audit trail');
      } finally {
        setLoading(false);
      }
    };
    fetchCycles();
  }, []);

  if (loading) {
    return (
      <div className="bg-white rounded-lg shadow border border-gray-200 p-6">
        <div className="animate-pulse space-y-3">
          <div className="h-5 bg-gray-200 rounded w-1/3" />
          <div className="h-4 bg-gray-200 rounded w-full" />
          <div className="h-4 bg-gray-200 rounded w-2/3" />
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-white rounded-lg shadow border border-gray-200 p-6">
        <p className="text-sm text-red-600">{error}</p>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-lg shadow border border-gray-200 p-6">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h2 className="text-lg font-semibold text-gray-900">Pricing Decision History</h2>
          <p className="text-xs text-gray-500 mt-0.5">
            Full audit trail for regulatory compliance • {cycles.length} cycles recorded
          </p>
        </div>
      </div>

      {cycles.length === 0 ? (
        <p className="text-sm text-gray-500 text-center py-6">No pricing cycles recorded yet.</p>
      ) : (
        <div className="overflow-hidden border border-gray-200 rounded-lg">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">Timestamp</th>
                <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">Pricing Group</th>
                <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">Objectives</th>
                <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">Status</th>
                <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">Scenarios</th>
                <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">Approval</th>
                <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">Actions</th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {cycles.map((cycle) => (
                <AuditRow
                  key={cycle.cycleId}
                  cycle={cycle}
                  isExpanded={expandedId === cycle.cycleId}
                  onToggle={() => setExpandedId(expandedId === cycle.cycleId ? null : cycle.cycleId)}
                />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function ApprovalSummary({ scenarios }: { scenarios?: AuditScenario[] }) {
  if (!scenarios || scenarios.length === 0) {
    return <span className="text-[10px] text-gray-400">—</span>;
  }

  const approved = scenarios.filter((s) => s.approvalStatus === 'APPROVED');
  const rejected = scenarios.filter((s) => s.approvalStatus === 'REJECTED');
  const autoApproved = approved.filter((s) => s.approvedBy === 'system-auto-approval');
  const humanApproved = approved.filter((s) => s.approvedBy && s.approvedBy !== 'system-auto-approval');

  // Only show "Pending" if NO scenario has been acted on (truly awaiting human decision)
  const hasAnyDecision = approved.length > 0 || rejected.length > 0;

  if (!hasAnyDecision) {
    return <span className="text-[10px] text-amber-600 font-medium">Awaiting decision</span>;
  }

  return (
    <div className="space-y-0.5">
      {autoApproved.length > 0 && (
        <span className="inline-block px-1.5 py-0.5 rounded text-[10px] font-medium bg-green-100 text-green-700">
          ⚡ Auto-approved
        </span>
      )}
      {humanApproved.length > 0 && (
        <span className="inline-block px-1.5 py-0.5 rounded text-[10px] font-medium bg-green-100 text-green-700">
          ✓ Approved
        </span>
      )}
      {rejected.length > 0 && (
        <span className="inline-block px-1.5 py-0.5 rounded text-[10px] font-medium bg-red-100 text-red-700">
          ✗ Rejected
        </span>
      )}
    </div>
  );
}

function AuditRow({ cycle, isExpanded, onToggle }: { cycle: AuditCycle; isExpanded: boolean; onToggle: () => void }) {
  const badgeClass = STATUS_BADGE[cycle.status] ?? 'bg-gray-100 text-gray-800';

  return (
    <>
      <tr className="hover:bg-gray-50 cursor-pointer" onClick={onToggle}>
        <td className="px-3 py-2 text-xs text-gray-700 whitespace-nowrap">
          {new Date(cycle.createdAt).toLocaleString()}
        </td>
        <td className="px-3 py-2 text-xs font-medium text-gray-900">
          {formatPricingGroup(cycle.pricingGroup ?? '')}
        </td>
        <td className="px-3 py-2">
          <div className="flex flex-wrap gap-1">
            {cycle.objectives?.map((obj) => (
              <span key={obj} className="px-1.5 py-0.5 bg-blue-50 text-blue-700 text-[10px] rounded">
                {obj.replace(/_/g, ' ')}
              </span>
            ))}
          </div>
        </td>
        <td className="px-3 py-2">
          <span className={`px-2 py-0.5 rounded-full text-[10px] font-medium ${badgeClass}`}>
            {cycle.status}
          </span>
        </td>
        <td className="px-3 py-2 text-xs text-gray-700">{cycle.scenarioCount}</td>
        <td className="px-3 py-2">
          <ApprovalSummary scenarios={cycle.scenarios} />
        </td>
        <td className="px-3 py-2">
          <div className="flex items-center gap-2">
            <button className="text-[10px] text-blue-600 hover:text-blue-800 font-medium">
              {isExpanded ? 'Collapse' : 'Expand'}
            </button>
            <Link
              to={`/cycles/${cycle.cycleId}`}
              className="text-[10px] text-indigo-600 hover:text-indigo-800 font-medium"
              onClick={(e) => e.stopPropagation()}
            >
              View
            </Link>
          </div>
        </td>
      </tr>
      {isExpanded && (
        <tr>
          <td colSpan={7} className="px-0 py-0">
            <AuditDetail cycle={cycle} />
          </td>
        </tr>
      )}
    </>
  );
}

function AuditDetail({ cycle }: { cycle: AuditCycle }) {
  return (
    <div className="bg-gray-50 border-t border-gray-200 p-4 space-y-4">
      {/* Inputs */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        <div className="bg-white rounded border border-gray-200 p-3">
          <p className="text-[10px] text-gray-500 uppercase font-medium mb-1">Cycle ID</p>
          <p className="text-xs text-gray-800 font-mono break-all">{cycle.cycleId}</p>
        </div>
        <div className="bg-white rounded border border-gray-200 p-3">
          <p className="text-[10px] text-gray-500 uppercase font-medium mb-1">Requested By</p>
          <p className="text-xs text-gray-800">{cycle.requestedBy ?? 'system'}</p>
        </div>
        <div className="bg-white rounded border border-gray-200 p-3">
          <p className="text-[10px] text-gray-500 uppercase font-medium mb-1">Constraints</p>
          <p className="text-xs text-gray-800">
            {cycle.constraints ? Object.entries(cycle.constraints).map(([k, v]) => `${k}: ${v}`).join(', ') : 'None'}
          </p>
        </div>
      </div>

      {/* Scenarios with audit data */}
      {cycle.scenarios && cycle.scenarios.length > 0 && (
        <div>
          <p className="text-xs font-semibold text-gray-700 mb-2">Generated Scenarios</p>
          <div className="space-y-2">
            {cycle.scenarios.sort((a, b) => (a.rank ?? 0) - (b.rank ?? 0)).map((scenario) => (
              <div key={scenario.scenarioId} className="bg-white rounded border border-gray-200 p-3">
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-bold text-gray-700">#{scenario.rank}</span>
                    <span className={`px-1.5 py-0.5 rounded text-[10px] font-medium ${
                      scenario.riskLevel === 'LOW' ? 'bg-green-100 text-green-700' :
                      scenario.riskLevel === 'MEDIUM' ? 'bg-yellow-100 text-yellow-700' :
                      'bg-red-100 text-red-700'
                    }`}>
                      {scenario.riskLevel}
                    </span>
                    <span className="text-[10px] text-gray-500">
                      Confidence: {scenario.confidenceScore}/100
                    </span>
                  </div>
                  {scenario.approvalStatus && (
                    <span className={`px-2 py-0.5 rounded-full text-[10px] font-medium ${
                      scenario.approvalStatus === 'APPROVED' ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'
                    }`}>
                      {scenario.approvalStatus}
                      {scenario.approvedAt && ` • ${new Date(scenario.approvedAt).toLocaleString()}`}
                    </span>
                  )}
                </div>

                {/* AI Rationale */}
                {scenario.aiRationale && (
                  <p className="text-[11px] text-gray-600 mb-2 italic">"{scenario.aiRationale}"</p>
                )}

                {/* Guardrail Results */}
                {scenario.guardrailResults && scenario.guardrailResults.length > 0 && (
                  <div className="flex flex-wrap gap-1 mb-2">
                    {scenario.guardrailResults.map((gr, idx) => (
                      <span key={idx} className={`px-1.5 py-0.5 rounded text-[10px] ${
                        gr.passed ? 'bg-green-50 text-green-700' : 'bg-red-50 text-red-700'
                      }`}>
                        {gr.passed ? '✓' : '✗'} {gr.rule}
                      </span>
                    ))}
                  </div>
                )}

                {/* Price Changes */}
                {scenario.priceChanges && scenario.priceChanges.length > 0 && (
                  <div className="flex flex-wrap gap-2">
                    {scenario.priceChanges.slice(0, 5).map((pc) => (
                      <span key={pc.productId} className="text-[10px] text-gray-600">
                        {pc.productName ?? pc.productId}: ${pc.currentPrice} → ${pc.newPrice} ({pc.changePercent > 0 ? '+' : ''}{pc.changePercent}%)
                      </span>
                    ))}
                    {scenario.priceChanges.length > 5 && (
                      <span className="text-[10px] text-gray-400">+{scenario.priceChanges.length - 5} more</span>
                    )}
                  </div>
                )}

                {/* Approval comment */}
                {scenario.approvalComment && (
                  <p className="text-[10px] text-gray-500 mt-1">
                    Justification: "{scenario.approvalComment}"
                  </p>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Timeline */}
      <div className="flex items-center gap-4 text-[10px] text-gray-500">
        <span>Created: {new Date(cycle.createdAt).toLocaleString()}</span>
        {cycle.completedAt && <span>Completed: {new Date(cycle.completedAt).toLocaleString()}</span>}
        {cycle.completedAt && cycle.createdAt && (
          <span>
            Duration: {Math.round((new Date(cycle.completedAt).getTime() - new Date(cycle.createdAt).getTime()) / 1000)}s
          </span>
        )}
      </div>
    </div>
  );
}
