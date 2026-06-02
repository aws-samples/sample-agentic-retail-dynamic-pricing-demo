import { useParams, Link } from 'react-router-dom';
import { useState, useEffect, useRef } from 'react';
import api from '../lib/api';
import { formatPricingGroup } from '../lib/productNames';
import PipelineSidebar from '../components/PipelineSidebar';
import ScenarioList from '../components/ScenarioList';

type CycleStatus = 'INITIATED' | 'ANALYZING' | 'SYNTHESIZING' | 'COMPLETE' | 'FAILED';

interface CycleData {
  cycleId: string;
  status: CycleStatus;
  pricingGroup: string;
  objectives: string[];
  constraints: Record<string, unknown>;
  scenarioCount: number;
  requestedBy: string;
  createdAt: string;
  completedAt?: string;
}

const STATUS_CONFIG: Record<CycleStatus, { label: string; color: string; bg: string }> = {
  INITIATED: { label: 'Initiated', color: 'text-blue-700', bg: 'bg-blue-100' },
  ANALYZING: { label: 'Analyzing', color: 'text-indigo-700', bg: 'bg-indigo-100' },
  SYNTHESIZING: { label: 'Synthesizing', color: 'text-purple-700', bg: 'bg-purple-100' },
  COMPLETE: { label: 'Complete', color: 'text-green-700', bg: 'bg-green-100' },
  FAILED: { label: 'Failed', color: 'text-red-700', bg: 'bg-red-100' },
};

export default function CycleDetail() {
  const { cycleId } = useParams<{ cycleId: string }>();
  const [cycle, setCycle] = useState<CycleData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    if (!cycleId) return;

    const fetchCycle = async () => {
      try {
        const response = await api.get(`/pricing-cycles/${cycleId}`);
        setCycle(response.data);
        setError(null);

        const status = response.data.status as CycleStatus;
        if ((status === 'COMPLETE' || status === 'FAILED') && intervalRef.current) {
          clearInterval(intervalRef.current);
          intervalRef.current = null;
        }
      } catch (err: unknown) {
        const message = err instanceof Error ? err.message : 'Failed to load cycle';
        setError(message);
      } finally {
        setLoading(false);
      }
    };

    fetchCycle();
    intervalRef.current = setInterval(fetchCycle, 5000);

    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    };
  }, [cycleId]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-blue-600" />
        <span className="ml-4 text-gray-600 text-lg">Loading pricing cycle...</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="max-w-4xl mx-auto py-8">
        <div className="bg-red-50 border border-red-200 rounded-lg p-6">
          <p className="text-red-700">{error}</p>
          <Link to="/" className="mt-4 inline-block text-sm text-blue-600 hover:text-blue-800">
            ← Back to Dashboard
          </Link>
        </div>
      </div>
    );
  }

  if (!cycle || !cycleId) return null;

  const statusConfig = STATUS_CONFIG[cycle.status] ?? STATUS_CONFIG.INITIATED;
  const isActive = cycle.status === 'ANALYZING' || cycle.status === 'SYNTHESIZING' || cycle.status === 'INITIATED';

  return (
    <div className="flex gap-6">
      {/* Left Sidebar - Pipeline */}
      <div className="w-64 flex-shrink-0">
        <PipelineSidebar cycleId={cycleId} cycleStatus={cycle.status} />
      </div>

      {/* Main Content */}
      <div className="flex-1 min-w-0 space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <Link to="/" className="text-sm text-blue-600 hover:text-blue-800 mb-1 inline-block">
              ← Back to Dashboard
            </Link>
            <h2 className="text-xl font-semibold text-gray-900">
              Pricing Cycle: {formatPricingGroup(cycle.pricingGroup)}
            </h2>
            <p className="text-sm text-gray-500 mt-1">
              Started: {new Date(cycle.createdAt).toLocaleString()}
              {cycle.completedAt && ` • Completed: ${new Date(cycle.completedAt).toLocaleString()}`}
            </p>
          </div>
          <span className={`px-3 py-1.5 rounded-full text-sm font-medium ${statusConfig.color} ${statusConfig.bg}`}>
            {isActive && (
              <span className="inline-block w-2 h-2 rounded-full bg-current mr-2 animate-pulse" />
            )}
            {statusConfig.label}
          </span>
        </div>

        {/* Cycle Summary Cards */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <div className="bg-white rounded-lg shadow p-4 border border-gray-100">
            <p className="text-xs text-gray-500 uppercase tracking-wider">Pricing Group</p>
            <p className="text-base font-semibold text-gray-900 mt-1">{formatPricingGroup(cycle.pricingGroup)}</p>
          </div>
          <div className="bg-white rounded-lg shadow p-4 border border-gray-100">
            <p className="text-xs text-gray-500 uppercase tracking-wider">Objectives</p>
            <div className="flex flex-wrap gap-1 mt-1">
              {cycle.objectives.map((obj) => (
                <span key={obj} className="px-2 py-0.5 bg-blue-50 text-blue-700 text-xs rounded-full font-medium">
                  {obj.replace(/_/g, ' ')}
                </span>
              ))}
            </div>
          </div>
          <div className="bg-white rounded-lg shadow p-4 border border-gray-100">
            <p className="text-xs text-gray-500 uppercase tracking-wider">Scenarios Generated</p>
            <p className="text-2xl font-bold text-gray-900 mt-1">{cycle.scenarioCount}</p>
          </div>
        </div>

        {/* Active state - show processing message */}
        {isActive && (
          <div className="bg-indigo-50 border border-indigo-200 rounded-lg p-5">
            <div className="flex items-center gap-3">
              <div className="animate-spin rounded-full h-5 w-5 border-2 border-indigo-600 border-t-transparent" />
              <div>
                <p className="text-sm font-medium text-indigo-900">AI Agents Processing</p>
                <p className="text-xs text-indigo-700 mt-0.5">
                  Multiple specialized agents are analyzing market data, competitor pricing, and demand signals in parallel.
                  Watch the pipeline on the left for real-time progress.
                </p>
              </div>
            </div>
          </div>
        )}

        {/* Scenarios (shows once agents complete) */}
        {(cycle.status === 'COMPLETE' || cycle.scenarioCount > 0) && (
          <ScenarioList cycleId={cycleId} />
        )}

        {/* Failed state */}
        {cycle.status === 'FAILED' && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-6">
            <h3 className="text-lg font-medium text-red-800">Pricing Cycle Failed</h3>
            <p className="text-sm text-red-700 mt-2">
              The pricing cycle encountered an error during execution. Check the pipeline sidebar for details.
            </p>
            <Link
              to="/pricing-request"
              className="mt-4 inline-flex items-center px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-md hover:bg-blue-700"
            >
              Start New Cycle
            </Link>
          </div>
        )}
      </div>
    </div>
  );
}
