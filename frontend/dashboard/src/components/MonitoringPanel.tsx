import { useEffect, useState, useCallback } from 'react';
import api from '../lib/api';

interface MonitoringMetrics {
  projectedRevenue: number;
  projectedMargin: number;
  actualRevenue: number | null;
  actualMargin: number | null;
  revenueVariance: number | null;
  marginVariance: number | null;
  conversionRate: number | null;
}

interface CorrectiveAction {
  action: string;
  expected_impact: string;
  risk: string;
}

interface MonitoringData {
  scenarioId: string;
  cycleId: string;
  approvalStatus: string;
  status: string;
  metrics: MonitoringMetrics;
  varianceStatus: string | null;
  breachedThresholds?: string[];
  lastUpdated: string | null;
  correctiveActions?: CorrectiveAction[];
}

interface MonitoringPanelProps {
  scenarioId: string;
}

const AUTO_REFRESH_INTERVAL = 60_000; // 60 seconds

/**
 * MonitoringPanel displays actual vs. projected performance for an active
 * pricing implementation. Shows variance alerts and recommended corrective
 * actions when thresholds are breached.
 *
 * Requirements: 9.6, 9.4, 9.5
 */
export default function MonitoringPanel({ scenarioId }: MonitoringPanelProps) {
  const [data, setData] = useState<MonitoringData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [approvingAction, setApprovingAction] = useState<number | null>(null);

  const fetchMonitoringData = useCallback(async () => {
    try {
      const response = await api.get(`/monitoring/${scenarioId}`);
      const body = typeof response.data === 'string'
        ? JSON.parse(response.data)
        : response.data;

      // If no corrective actions from API, provide defaults when variance is breached
      if (body.varianceStatus === 'threshold_breached' && !body.correctiveActions) {
        body.correctiveActions = generateDefaultCorrectiveActions(body.breachedThresholds || []);
      }

      setData(body);
      setError(null);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to fetch monitoring data';
      setError(message);
    } finally {
      setLoading(false);
    }
  }, [scenarioId]);

  useEffect(() => {
    fetchMonitoringData();
    const interval = setInterval(fetchMonitoringData, AUTO_REFRESH_INTERVAL);
    return () => clearInterval(interval);
  }, [fetchMonitoringData]);

  const handleApproveAction = async (index: number) => {
    setApprovingAction(index);
    try {
      await api.post('/approvals', {
        scenarioId,
        action: 'APPROVED',
        comment: `Approved corrective action: ${data?.correctiveActions?.[index]?.action}`,
        type: 'corrective_action',
      });
      // Refresh data after approval
      await fetchMonitoringData();
    } catch {
      // Silently handle - the user can retry
    } finally {
      setApprovingAction(null);
    }
  };

  if (loading) {
    return (
      <div className="bg-white rounded-lg shadow p-6">
        <div className="animate-pulse space-y-4">
          <div className="h-6 bg-gray-200 rounded w-1/3"></div>
          <div className="h-4 bg-gray-200 rounded w-full"></div>
          <div className="h-4 bg-gray-200 rounded w-2/3"></div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-white rounded-lg shadow p-6">
        <div className="text-red-600 text-sm">
          <p className="font-medium">Error loading monitoring data</p>
          <p className="mt-1">{error}</p>
        </div>
      </div>
    );
  }

  if (!data) {
    return null;
  }

  const { metrics, varianceStatus, breachedThresholds, correctiveActions } = data;

  return (
    <div className="bg-white rounded-lg shadow p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold text-gray-900">Continuous Monitoring</h3>
        <div className="flex items-center gap-2">
          <StatusBadge status={varianceStatus} />
          {data.lastUpdated && (
            <span className="text-xs text-gray-500">
              Updated: {new Date(data.lastUpdated).toLocaleTimeString()}
            </span>
          )}
        </div>
      </div>

      {/* Variance Alert Banner */}
      {varianceStatus === 'threshold_breached' && breachedThresholds && breachedThresholds.length > 0 && (
        <div className="bg-red-50 border border-red-200 rounded-md p-4">
          <div className="flex items-start">
            <span className="text-red-500 text-lg mr-2">⚠️</span>
            <div>
              <p className="text-sm font-medium text-red-800">
                Performance Variance Detected
              </p>
              <p className="text-sm text-red-700 mt-1">
                Thresholds breached: {breachedThresholds.map(t => t.charAt(0).toUpperCase() + t.slice(1)).join(', ')}
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Metrics Comparison */}
      <div className="space-y-4">
        <h4 className="text-sm font-medium text-gray-700">Performance Metrics</h4>

        <MetricBar
          label="Revenue"
          projected={metrics.projectedRevenue}
          actual={metrics.actualRevenue}
          variancePercent={metrics.revenueVariance}
          format="currency"
        />

        <MetricBar
          label="Margin"
          projected={metrics.projectedMargin}
          actual={metrics.actualMargin}
          variancePercent={metrics.marginVariance}
          format="percentage"
        />

        {metrics.conversionRate !== null && (
          <div className="flex items-center justify-between text-sm">
            <span className="text-gray-600">Conversion Rate</span>
            <span className="font-medium text-gray-900">
              {(metrics.conversionRate * 100).toFixed(2)}%
            </span>
          </div>
        )}
      </div>

      {/* Corrective Actions */}
      {correctiveActions && correctiveActions.length > 0 && (
        <div className="space-y-3">
          <h4 className="text-sm font-medium text-gray-700">Recommended Corrective Actions</h4>
          <div className="space-y-2">
            {correctiveActions.map((ca, index) => (
              <div
                key={index}
                className="border border-gray-200 rounded-md p-3 space-y-2"
              >
                <p className="text-sm font-medium text-gray-900">{ca.action}</p>
                <div className="flex items-center gap-4 text-xs text-gray-500">
                  <span>Impact: {ca.expected_impact}</span>
                  <span className={`px-1.5 py-0.5 rounded ${
                    ca.risk.toLowerCase().startsWith('low')
                      ? 'bg-green-100 text-green-700'
                      : ca.risk.toLowerCase().startsWith('medium')
                        ? 'bg-yellow-100 text-yellow-700'
                        : 'bg-red-100 text-red-700'
                  }`}>
                    {ca.risk}
                  </span>
                </div>
                <button
                  onClick={() => handleApproveAction(index)}
                  disabled={approvingAction === index}
                  className="mt-1 px-3 py-1.5 text-xs font-medium text-white bg-blue-600 rounded hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  {approvingAction === index ? 'Approving...' : 'Approve Adjustment'}
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Auto-refresh indicator */}
      <p className="text-xs text-gray-400 text-right">
        Auto-refreshes every 60 seconds
      </p>
    </div>
  );
}

/* ─── Sub-components ─── */

function StatusBadge({ status }: { status: string | null }) {
  if (!status) {
    return (
      <span className="px-2 py-1 text-xs font-medium rounded-full bg-gray-100 text-gray-600">
        Awaiting Data
      </span>
    );
  }

  if (status === 'within_bounds') {
    return (
      <span className="px-2 py-1 text-xs font-medium rounded-full bg-green-100 text-green-700">
        Within Bounds
      </span>
    );
  }

  if (status === 'threshold_breached') {
    return (
      <span className="px-2 py-1 text-xs font-medium rounded-full bg-red-100 text-red-700">
        Threshold Breached
      </span>
    );
  }

  return (
    <span className="px-2 py-1 text-xs font-medium rounded-full bg-gray-100 text-gray-600">
      {status}
    </span>
  );
}

interface MetricBarProps {
  label: string;
  projected: number;
  actual: number | null;
  variancePercent: number | null;
  format: 'currency' | 'percentage';
}

function MetricBar({ label, projected, actual, variancePercent, format }: MetricBarProps) {
  const formatValue = (value: number) => {
    if (format === 'currency') {
      return `$${value.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
    }
    return `${(value * 100).toFixed(2)}%`;
  };

  // Calculate bar widths relative to the larger value
  const maxVal = actual !== null ? Math.max(Math.abs(projected), Math.abs(actual)) : Math.abs(projected);
  const projectedWidth = maxVal > 0 ? (Math.abs(projected) / maxVal) * 100 : 0;
  const actualWidth = actual !== null && maxVal > 0 ? (Math.abs(actual) / maxVal) * 100 : 0;

  const varianceColor = variancePercent === null
    ? 'text-gray-500'
    : variancePercent > 0.10
      ? 'text-red-600'
      : variancePercent > 0.05
        ? 'text-yellow-600'
        : 'text-green-600';

  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between text-sm">
        <span className="text-gray-600">{label}</span>
        {variancePercent !== null && (
          <span className={`text-xs font-medium ${varianceColor}`}>
            {(variancePercent * 100).toFixed(1)}% variance
          </span>
        )}
      </div>

      {/* Projected bar */}
      <div className="flex items-center gap-2">
        <span className="text-xs text-gray-500 w-16">Projected</span>
        <div className="flex-1 bg-gray-100 rounded-full h-4 overflow-hidden">
          <div
            className="bg-blue-400 h-full rounded-full transition-all duration-300"
            style={{ width: `${projectedWidth}%` }}
          ></div>
        </div>
        <span className="text-xs font-medium text-gray-700 w-24 text-right">
          {formatValue(projected)}
        </span>
      </div>

      {/* Actual bar */}
      <div className="flex items-center gap-2">
        <span className="text-xs text-gray-500 w-16">Actual</span>
        <div className="flex-1 bg-gray-100 rounded-full h-4 overflow-hidden">
          {actual !== null ? (
            <div
              className={`h-full rounded-full transition-all duration-300 ${
                variancePercent !== null && variancePercent > 0.10
                  ? 'bg-red-400'
                  : 'bg-green-400'
              }`}
              style={{ width: `${actualWidth}%` }}
            ></div>
          ) : (
            <div className="h-full bg-gray-200 rounded-full w-0"></div>
          )}
        </div>
        <span className="text-xs font-medium text-gray-700 w-24 text-right">
          {actual !== null ? formatValue(actual) : '—'}
        </span>
      </div>
    </div>
  );
}

/* ─── Helpers ─── */

function generateDefaultCorrectiveActions(breachedThresholds: string[]): CorrectiveAction[] {
  const actions: CorrectiveAction[] = [];

  if (breachedThresholds.includes('revenue')) {
    actions.push(
      {
        action: 'Reduce price by 2-3% to stimulate demand',
        expected_impact: 'Increase revenue by 5-8% within 48 hours',
        risk: 'Medium - may reduce margin',
      },
      {
        action: 'Increase promotional visibility on high-traffic channels',
        expected_impact: 'Boost conversion rate by 10-15%',
        risk: 'Low - marketing spend only',
      },
    );
  }

  if (breachedThresholds.includes('margin')) {
    actions.push(
      {
        action: 'Increase price by 1-2% to restore target margin',
        expected_impact: 'Restore margin within 1-2 percentage points of target',
        risk: 'Medium - may reduce conversion rate',
      },
      {
        action: 'Shift promotional spend to higher-margin channels',
        expected_impact: 'Improve blended margin by 0.5-1 percentage points',
        risk: 'Low - reallocation only',
      },
    );
  }

  if (actions.length === 0) {
    actions.push({
      action: 'Initiate abbreviated pricing cycle for reassessment',
      expected_impact: 'Updated scenario within 24 hours',
      risk: 'Low - data-driven adjustment',
    });
  }

  return actions;
}
