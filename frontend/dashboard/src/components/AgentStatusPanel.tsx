import { useState, useEffect, useRef } from 'react';
import api from '../lib/api';

type AgentStatus = 'idle' | 'running' | 'completed' | 'failed' | 'awaiting_approval';

interface AgentInfo {
  id: string;
  name: string;
  status: AgentStatus;
  startTime?: string;
  endTime?: string;
  error?: string;
  intermediateResult?: string;
}

interface AgentStatusPanelProps {
  cycleId: string;
}

const AGENT_EXECUTION_ORDER = [
  { id: 'orchestrator', name: 'Orchestrator' },
  { id: 'competitive_intelligence', name: 'Competitive Intelligence' },
  { id: 'demand_forecasting', name: 'Demand Forecasting' },
  { id: 'market_intelligence', name: 'Market Intelligence' },
  { id: 'strategy_synthesis', name: 'Strategy Synthesis' },
  { id: 'implementation_monitoring', name: 'Implementation Monitoring' },
];

const STATUS_COLORS: Record<AgentStatus, string> = {
  idle: 'bg-gray-400',
  running: 'bg-blue-500',
  completed: 'bg-green-500',
  failed: 'bg-red-500',
  awaiting_approval: 'bg-amber-400',
};

const STATUS_LABELS: Record<AgentStatus, string> = {
  idle: 'Idle',
  running: 'Running',
  completed: 'Completed',
  failed: 'Failed',
  awaiting_approval: 'Awaiting Approval',
};

function StatusDot({ status }: { status: AgentStatus }) {
  return (
    <span
      className={`inline-block w-3 h-3 rounded-full ${STATUS_COLORS[status]} ${
        status === 'running' ? 'animate-pulse' : ''
      }`}
      aria-label={STATUS_LABELS[status]}
    />
  );
}

function ArrowConnector() {
  return (
    <div className="flex items-center justify-center py-1">
      <svg
        className="w-4 h-6 text-gray-400"
        fill="none"
        stroke="currentColor"
        viewBox="0 0 16 24"
        aria-hidden="true"
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth={2}
          d="M8 2v16m0 0l-4-4m4 4l4-4"
        />
      </svg>
    </div>
  );
}

export default function AgentStatusPanel({ cycleId }: AgentStatusPanelProps) {
  const [agents, setAgents] = useState<AgentInfo[]>(
    AGENT_EXECUTION_ORDER.map((a) => ({ ...a, status: 'idle' as AgentStatus }))
  );
  const [error, setError] = useState<string | null>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    if (!cycleId) return;

    const fetchStatus = async () => {
      try {
        const response = await api.get(`/agents/status`, {
          params: { cycleId },
        });

        const statusData = response.data?.agents ?? response.data?.agentStatuses ?? response.data;

        const updatedAgents: AgentInfo[] = AGENT_EXECUTION_ORDER.map((agent) => {
          const agentData = statusData?.[agent.id];
          return {
            id: agent.id,
            name: agent.name,
            status: (agentData?.status as AgentStatus) ?? 'idle',
            startTime: agentData?.startTime,
            endTime: agentData?.endTime,
            error: agentData?.error,
            intermediateResult: agentData?.intermediateResult,
          };
        });

        setAgents(updatedAgents);
        setError(null);

        // Stop polling when all agents are in a terminal state
        const allTerminal = updatedAgents.every(
          (a) => a.status === 'completed' || a.status === 'failed' || a.status === 'awaiting_approval'
        );
        if (allTerminal && intervalRef.current) {
          clearInterval(intervalRef.current);
          intervalRef.current = null;
        }
      } catch (err) {
        setError('Failed to fetch agent status');
      }
    };

    // Fetch immediately, then poll every 5 seconds
    fetchStatus();
    intervalRef.current = setInterval(fetchStatus, 5000);

    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    };
  }, [cycleId]);

  const completedCount = agents.filter((a) => a.status === 'completed').length;
  const totalCount = agents.length;

  return (
    <div className="bg-white rounded-lg shadow p-6">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold text-gray-900">Agent Pipeline</h2>
        <span className="text-sm text-gray-500">
          {completedCount}/{totalCount} completed
        </span>
      </div>

      {/* Progress bar */}
      <div className="w-full bg-gray-200 rounded-full h-2 mb-6">
        <div
          className="bg-blue-600 h-2 rounded-full transition-all duration-500"
          style={{ width: `${(completedCount / totalCount) * 100}%` }}
        />
      </div>

      {error && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-md">
          <p className="text-sm text-red-700">{error}</p>
        </div>
      )}

      {/* Agent flow */}
      <div className="space-y-0">
        {agents.map((agent, index) => (
          <div key={agent.id}>
            <div
              className={`flex items-center gap-3 p-3 rounded-md border ${
                agent.status === 'running'
                  ? 'border-blue-200 bg-blue-50'
                  : agent.status === 'failed'
                  ? 'border-red-200 bg-red-50'
                  : agent.status === 'completed'
                  ? 'border-green-200 bg-green-50'
                  : agent.status === 'awaiting_approval'
                  ? 'border-amber-200 bg-amber-50'
                  : 'border-gray-200 bg-gray-50'
              }`}
            >
              <StatusDot status={agent.status} />
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="text-xs font-medium text-gray-400">
                    Step {index + 1}
                  </span>
                  <span className="font-medium text-gray-900 text-sm truncate">
                    {agent.name}
                  </span>
                </div>
                {agent.status === 'running' && (
                  <p className="text-xs text-blue-600 mt-0.5">Processing...</p>
                )}
                {agent.status === 'awaiting_approval' && (
                  <p className="text-xs text-amber-600 mt-0.5">Waiting for human approval of a scenario</p>
                )}
                {agent.status === 'failed' && agent.error && (
                  <p className="text-xs text-red-600 mt-0.5 truncate">
                    {agent.error}
                  </p>
                )}
                {agent.intermediateResult && (
                  <p className="text-xs text-gray-500 mt-0.5 truncate">
                    {agent.intermediateResult}
                  </p>
                )}
              </div>
              <span
                className={`text-xs font-medium px-2 py-0.5 rounded-full ${
                  agent.status === 'running'
                    ? 'text-blue-700 bg-blue-100'
                    : agent.status === 'failed'
                    ? 'text-red-700 bg-red-100'
                    : agent.status === 'completed'
                    ? 'text-green-700 bg-green-100'
                    : agent.status === 'awaiting_approval'
                    ? 'text-amber-700 bg-amber-100'
                    : 'text-gray-600 bg-gray-100'
                }`}
              >
                {STATUS_LABELS[agent.status]}
              </span>
            </div>
            {index < agents.length - 1 && <ArrowConnector />}
          </div>
        ))}
      </div>
    </div>
  );
}
