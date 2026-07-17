import { useState, useMemo } from 'react';

// --- Types ---

interface AgentInteraction {
  timestamp: string; // HH:MM:SS.mmm
  agentId: string;
  agentName: string;
  action: string;
  duration_ms: number;
  status: 'completed' | 'running' | 'failed';
}

interface ProcessFlowStep {
  order: number;
  agentName: string;
  action: string;
  duration_ms: number;
  status: 'completed' | 'running' | 'failed' | 'pending';
}

interface AISidebarProps {
  cycleId: string;
}

// --- Mock Data Generators ---

function generateMockRationale(cycleId: string): string {
  return (
    `Based on analysis of cycle ${cycleId}, the top-ranked scenario (Scenario #1) is recommended ` +
    `because it achieves a 12.4% projected revenue increase while maintaining margins within ` +
    `2 percentage points of current levels. The Competitive Intelligence Agent identified a ` +
    `pricing gap of 8-15% below key competitors in the premium segment. The Demand Forecasting ` +
    `Agent projects a price elasticity of -0.7 for this category, indicating moderate sensitivity ` +
    `that supports a measured price increase. The Market Intelligence Agent confirmed favorable ` +
    `macroeconomic conditions with consumer confidence trending upward (+3.2% MoM). ` +
    `All guardrails passed: prices remain above cost floor, MAP compliance verified, and ` +
    `geographic variance is within the 15% threshold.`
  );
}

function generateMockProcessFlow(): ProcessFlowStep[] {
  return [
    { order: 1, agentName: 'Orchestrator Agent', action: 'Initialize pricing cycle', duration_ms: 245, status: 'completed' },
    { order: 2, agentName: 'Competitive Intelligence Agent', action: 'Analyze competitor pricing', duration_ms: 3420, status: 'completed' },
    { order: 3, agentName: 'Demand Forecasting Agent', action: 'Forecast demand & elasticity', duration_ms: 4180, status: 'completed' },
    { order: 4, agentName: 'Market Intelligence Agent', action: 'Analyze market signals', duration_ms: 3890, status: 'completed' },
    { order: 5, agentName: 'Strategy Synthesis Agent', action: 'Generate & rank scenarios', duration_ms: 8750, status: 'completed' },
    { order: 6, agentName: 'Strategy Synthesis Agent', action: 'Apply guardrails', duration_ms: 1230, status: 'completed' },
    { order: 7, agentName: 'Orchestrator Agent', action: 'Assemble final output', duration_ms: 380, status: 'completed' },
  ];
}

function generateMockLogs(): AgentInteraction[] {
  const agents = [
    { id: 'orchestrator', name: 'Orchestrator Agent' },
    { id: 'competitive-intel', name: 'Competitive Intelligence Agent' },
    { id: 'demand-forecast', name: 'Demand Forecasting Agent' },
    { id: 'market-intel', name: 'Market Intelligence Agent' },
    { id: 'strategy-synthesis', name: 'Strategy Synthesis Agent' },
    { id: 'impl-monitor', name: 'Implementation Monitoring Agent' },
  ];

  const actions = [
    'invoke_agent', 'query_mcp_server', 'parse_response', 'validate_schema',
    'apply_guardrail', 'calculate_score', 'rank_scenarios', 'store_result',
    'check_timeout', 'retry_request', 'emit_metric', 'log_interaction',
    'fetch_competitor_prices', 'analyze_elasticity', 'detect_sentiment',
    'compute_variance', 'evaluate_risk', 'classify_scenario', 'persist_memory',
    'correlate_trace', 'aggregate_signals', 'normalize_data',
  ];

  const statuses: Array<'completed' | 'running' | 'failed'> = ['completed', 'completed', 'completed', 'completed', 'completed', 'failed'];

  const logs: AgentInteraction[] = [];
  let baseHour = 10;
  let baseMinute = 30;
  let baseSecond = 0;
  let baseMs = 0;

  for (let i = 0; i < 120; i++) {
    const agent = agents[Math.floor(Math.random() * agents.length)];
    const action = actions[Math.floor(Math.random() * actions.length)];
    const status = statuses[Math.floor(Math.random() * statuses.length)];
    const duration = Math.floor(Math.random() * 5000) + 10;

    baseMs += Math.floor(Math.random() * 800) + 50;
    if (baseMs >= 1000) {
      baseSecond += Math.floor(baseMs / 1000);
      baseMs = baseMs % 1000;
    }
    if (baseSecond >= 60) {
      baseMinute += Math.floor(baseSecond / 60);
      baseSecond = baseSecond % 60;
    }
    if (baseMinute >= 60) {
      baseHour += Math.floor(baseMinute / 60);
      baseMinute = baseMinute % 60;
    }

    const timestamp = `${String(baseHour).padStart(2, '0')}:${String(baseMinute).padStart(2, '0')}:${String(baseSecond).padStart(2, '0')}.${String(baseMs).padStart(3, '0')}`;

    logs.push({
      timestamp,
      agentId: agent.id,
      agentName: agent.name,
      action,
      duration_ms: duration,
      status,
    });
  }

  return logs;
}

// --- Status Badge ---

function StatusBadge({ status }: { status: string }) {
  const colors: Record<string, string> = {
    completed: 'bg-green-100 text-green-800',
    running: 'bg-blue-100 text-blue-800',
    failed: 'bg-red-100 text-red-800',
    pending: 'bg-gray-100 text-gray-600',
  };

  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${colors[status] || colors.pending}`}>
      {status}
    </span>
  );
}

// --- Main Component ---

export default function AISidebar({ cycleId }: AISidebarProps) {
  const [isOpen, setIsOpen] = useState(true);
  const [activeTab, setActiveTab] = useState<'rationale' | 'flow' | 'logs'>('rationale');

  const rationale = useMemo(() => generateMockRationale(cycleId), [cycleId]);
  const processFlow = useMemo(() => generateMockProcessFlow(), []);
  const logs = useMemo(() => generateMockLogs(), []);

  return (
    <div
      className={`fixed top-0 right-0 h-full bg-white border-l border-gray-200 shadow-lg transition-all duration-300 z-40 flex flex-col ${
        isOpen ? 'w-96' : 'w-10'
      }`}
    >
      {/* Toggle Button */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="absolute top-4 -left-3 w-6 h-6 bg-blue-600 text-white rounded-full flex items-center justify-center text-xs hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 shadow-md"
        aria-label={isOpen ? 'Collapse AI sidebar' : 'Expand AI sidebar'}
      >
        {isOpen ? '›' : '‹'}
      </button>

      {isOpen && (
        <>
          {/* Header */}
          <div className="px-4 py-3 border-b border-gray-200 flex-shrink-0">
            <h2 className="text-lg font-semibold text-gray-900">AI Insights</h2>
            <p className="text-xs text-gray-500 mt-0.5">Cycle: {cycleId}</p>
          </div>

          {/* Tabs */}
          <div className="flex border-b border-gray-200 flex-shrink-0">
            <button
              onClick={() => setActiveTab('rationale')}
              className={`flex-1 px-3 py-2 text-sm font-medium border-b-2 transition-colors ${
                activeTab === 'rationale'
                  ? 'border-blue-600 text-blue-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700'
              }`}
            >
              Rationale
            </button>
            <button
              onClick={() => setActiveTab('flow')}
              className={`flex-1 px-3 py-2 text-sm font-medium border-b-2 transition-colors ${
                activeTab === 'flow'
                  ? 'border-blue-600 text-blue-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700'
              }`}
            >
              Process Flow
            </button>
            <button
              onClick={() => setActiveTab('logs')}
              className={`flex-1 px-3 py-2 text-sm font-medium border-b-2 transition-colors ${
                activeTab === 'logs'
                  ? 'border-blue-600 text-blue-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700'
              }`}
            >
              Logs ({logs.length})
            </button>
          </div>

          {/* Content */}
          <div className="flex-1 overflow-y-auto">
            {activeTab === 'rationale' && (
              <RationaleSection rationale={rationale} />
            )}
            {activeTab === 'flow' && (
              <ProcessFlowSection steps={processFlow} />
            )}
            {activeTab === 'logs' && (
              <LogsSection logs={logs} />
            )}
          </div>
        </>
      )}
    </div>
  );
}

// --- Rationale Section ---

function RationaleSection({ rationale }: { rationale: string }) {
  return (
    <div className="p-4">
      <h3 className="text-sm font-semibold text-gray-900 mb-2">AI Rationale</h3>
      <p className="text-sm text-gray-700 leading-relaxed">{rationale}</p>

      <div className="mt-4 p-3 bg-blue-50 rounded-lg border border-blue-100">
        <h4 className="text-xs font-semibold text-blue-800 mb-1">Key Factors</h4>
        <ul className="text-xs text-blue-700 space-y-1">
          <li>• Competitive gap: 8-15% below premium segment peers</li>
          <li>• Price elasticity: -0.7 (moderate sensitivity)</li>
          <li>• Consumer confidence: +3.2% MoM trend</li>
          <li>• All guardrails passed (cost floor, MAP, geo-variance)</li>
        </ul>
      </div>

      <div className="mt-4 p-3 bg-green-50 rounded-lg border border-green-100">
        <h4 className="text-xs font-semibold text-green-800 mb-1">Projected Impact</h4>
        <ul className="text-xs text-green-700 space-y-1">
          <li>• Revenue: +12.4% projected increase</li>
          <li>• Margin: within 2pp of current levels</li>
          <li>• Risk Level: LOW (auto-approve eligible)</li>
        </ul>
      </div>
    </div>
  );
}

// --- Process Flow Section ---

function ProcessFlowSection({ steps }: { steps: ProcessFlowStep[] }) {
  return (
    <div className="p-4">
      <h3 className="text-sm font-semibold text-gray-900 mb-3">Agent Process Flow</h3>
      <div className="relative">
        {/* Timeline line */}
        <div className="absolute left-4 top-2 bottom-2 w-0.5 bg-gray-200" />

        <div className="space-y-4">
          {steps.map((step) => (
            <div key={step.order} className="relative flex items-start pl-10">
              {/* Timeline dot */}
              <div
                className={`absolute left-2.5 w-3 h-3 rounded-full border-2 ${
                  step.status === 'completed'
                    ? 'bg-green-500 border-green-500'
                    : step.status === 'running'
                    ? 'bg-blue-500 border-blue-500 animate-pulse'
                    : step.status === 'failed'
                    ? 'bg-red-500 border-red-500'
                    : 'bg-gray-300 border-gray-300'
                }`}
              />

              <div className="flex-1 min-w-0">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-medium text-gray-900 truncate">
                    {step.agentName}
                  </span>
                  <StatusBadge status={step.status} />
                </div>
                <p className="text-xs text-gray-500 mt-0.5">{step.action}</p>
                <p className="text-xs text-gray-400 mt-0.5">
                  Duration: {step.duration_ms.toLocaleString()}ms
                </p>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Total duration */}
      <div className="mt-4 pt-3 border-t border-gray-200">
        <div className="flex justify-between text-xs">
          <span className="text-gray-500">Total pipeline duration</span>
          <span className="font-medium text-gray-900">
            {steps.reduce((sum, s) => sum + s.duration_ms, 0).toLocaleString()}ms
          </span>
        </div>
      </div>
    </div>
  );
}

// --- Logs Section ---

function LogsSection({ logs }: { logs: AgentInteraction[] }) {
  const [filter, setFilter] = useState('');

  const filteredLogs = useMemo(() => {
    if (!filter) return logs;
    const lower = filter.toLowerCase();
    return logs.filter(
      (log) =>
        log.agentName.toLowerCase().includes(lower) ||
        log.action.toLowerCase().includes(lower) ||
        log.agentId.toLowerCase().includes(lower)
    );
  }, [logs, filter]);

  return (
    <div className="flex flex-col h-full">
      {/* Filter */}
      <div className="p-3 border-b border-gray-100 flex-shrink-0">
        <input
          type="text"
          placeholder="Filter by agent or action..."
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          className="w-full px-3 py-1.5 text-xs border border-gray-300 rounded-md focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500"
        />
        <p className="text-xs text-gray-400 mt-1">
          Showing {filteredLogs.length} of {logs.length} entries
        </p>
      </div>

      {/* Log entries */}
      <div className="flex-1 overflow-y-auto">
        <table className="w-full text-xs">
          <thead className="sticky top-0 bg-gray-50 border-b border-gray-200">
            <tr>
              <th className="px-3 py-2 text-left font-medium text-gray-500">Time</th>
              <th className="px-3 py-2 text-left font-medium text-gray-500">Agent</th>
              <th className="px-3 py-2 text-left font-medium text-gray-500">Action</th>
              <th className="px-3 py-2 text-right font-medium text-gray-500">Duration</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {filteredLogs.map((log, idx) => (
              <tr
                key={idx}
                className={`hover:bg-gray-50 ${
                  log.status === 'failed' ? 'bg-red-50' : ''
                }`}
              >
                <td className="px-3 py-1.5 font-mono text-gray-600 whitespace-nowrap">
                  {log.timestamp}
                </td>
                <td className="px-3 py-1.5 text-gray-800 truncate max-w-[100px]" title={log.agentName}>
                  {log.agentName.replace(' Agent', '')}
                </td>
                <td className="px-3 py-1.5 text-gray-600 truncate max-w-[100px]" title={log.action}>
                  {log.action}
                </td>
                <td className="px-3 py-1.5 text-right font-mono text-gray-600 whitespace-nowrap">
                  {log.duration_ms}ms
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
