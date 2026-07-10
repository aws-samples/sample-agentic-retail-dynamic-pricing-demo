import { useState, useEffect, useRef } from 'react';
import api from '../lib/api';

type StepStatus = 'idle' | 'running' | 'completed' | 'failed' | 'awaiting_approval' | 'blocked';

interface PipelineStep {
  id: string;
  label: string;
  description: string;
  status: StepStatus;
}

interface PipelineSidebarProps {
  cycleId: string;
  cycleStatus: string;
}

const PIPELINE_STEPS: Omit<PipelineStep, 'status'>[] = [
  { id: 'trigger', label: 'Cycle Triggered', description: 'Pricing request initiated' },
  { id: 'orchestrator', label: 'Orchestrator', description: 'Coordinating agent pipeline' },
  { id: 'competitive_intelligence', label: 'Competitive Intelligence', description: 'Analyzing competitor prices & positioning' },
  { id: 'demand_forecasting', label: 'Demand Forecasting', description: 'Calculating price elasticity & demand curves' },
  { id: 'market_intelligence', label: 'Market Intelligence', description: 'Assessing market trends & signals' },
  { id: 'knowledge_base', label: 'Knowledge Base Query', description: 'Retrieving historical pricing patterns' },
  { id: 'strategy_synthesis', label: 'Strategy Synthesis', description: 'Generating ranked pricing scenarios' },
  { id: 'guardrail_validation', label: 'Guardrail Validation', description: 'Compliance & policy checks' },
  { id: 'implementation_monitoring', label: 'Implementation', description: 'Executing approved price changes' },
  { id: 'publishing', label: 'Publishing', description: 'Updating all sales channels' },
];

const STATUS_ICONS: Record<StepStatus, { icon: string; color: string; bg: string }> = {
  idle: { icon: '○', color: 'text-gray-400', bg: 'bg-gray-100' },
  running: { icon: '◉', color: 'text-blue-600', bg: 'bg-blue-50' },
  completed: { icon: '✓', color: 'text-green-600', bg: 'bg-green-50' },
  failed: { icon: '✗', color: 'text-red-600', bg: 'bg-red-50' },
  awaiting_approval: { icon: '⏸', color: 'text-amber-600', bg: 'bg-amber-50' },
  blocked: { icon: '🛡', color: 'text-red-600', bg: 'bg-red-50' },
};

export default function PipelineSidebar({ cycleId, cycleStatus }: PipelineSidebarProps) {
  const [steps, setSteps] = useState<PipelineStep[]>(
    PIPELINE_STEPS.map((s) => ({ ...s, status: 'idle' as StepStatus }))
  );
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    if (!cycleId) return;

    const fetchStatus = async () => {
      try {
        const response = await api.get('/agents/status', { params: { cycleId } });
        const agents = response.data?.agents ?? response.data?.agentStatuses ?? {};

        setSteps(PIPELINE_STEPS.map((step) => {
          // Map pipeline steps to agent statuses
          if (step.id === 'trigger') {
            return { ...step, status: 'completed' as StepStatus };
          }
          if (step.id === 'knowledge_base') {
            // Knowledge base runs with intelligence agents
            const ciStatus = agents?.competitive_intelligence?.status;
            if (ciStatus === 'completed') return { ...step, status: 'completed' as StepStatus };
            if (ciStatus === 'running') return { ...step, status: 'running' as StepStatus };
            return { ...step, status: 'idle' as StepStatus };
          }
          if (step.id === 'guardrail_validation') {
            // Guardrails run after synthesis
            const synthStatus = agents?.strategy_synthesis?.status;
            if (synthStatus === 'completed') return { ...step, status: 'completed' as StepStatus };
            if (synthStatus === 'running') return { ...step, status: 'running' as StepStatus };
            return { ...step, status: 'idle' as StepStatus };
          }
          if (step.id === 'publishing') {
            // Publishing happens after implementation
            const implStatus = agents?.implementation_monitoring?.status;
            if (implStatus === 'completed') return { ...step, status: 'completed' as StepStatus };
            if (implStatus === 'running') return { ...step, status: 'running' as StepStatus };
            return { ...step, status: 'idle' as StepStatus };
          }
          // Direct agent mapping
          const agentData = agents?.[step.id];
          const status = (agentData?.status as StepStatus) ?? 'idle';
          return { ...step, status };
        }));
      } catch {
        // Silently handle polling errors
      }
    };

    fetchStatus();
    intervalRef.current = setInterval(fetchStatus, 3000);

    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    };
  }, [cycleId]);

  // Stop polling when cycle is done
  useEffect(() => {
    if ((cycleStatus === 'COMPLETE' || cycleStatus === 'FAILED') && intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
  }, [cycleStatus]);

  const completedCount = steps.filter((s) => s.status === 'completed').length;

  return (
    <div className="bg-white rounded-lg shadow-lg border border-gray-200 p-4 h-fit sticky top-4">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-bold text-gray-900 uppercase tracking-wider">
          AI Pipeline Execution
        </h3>
        <span className="text-xs text-gray-500 font-medium">
          {completedCount}/{steps.length}
        </span>
      </div>

      {/* Progress bar */}
      <div className="w-full bg-gray-200 rounded-full h-1.5 mb-4">
        <div
          className="bg-gradient-to-r from-blue-500 to-green-500 h-1.5 rounded-full transition-all duration-700"
          style={{ width: `${(completedCount / steps.length) * 100}%` }}
        />
      </div>

      {/* Pipeline steps */}
      <div className="space-y-0.5">
        {steps.map((step, index) => {
          const config = STATUS_ICONS[step.status];
          const isActive = step.status === 'running';

          return (
            <div key={step.id}>
              <div
                className={`flex items-start gap-2.5 px-2.5 py-2 rounded-md transition-all duration-300 ${config.bg} ${
                  isActive ? 'ring-1 ring-blue-300' : ''
                }`}
              >
                {/* Status icon */}
                <span className={`text-sm font-bold mt-0.5 ${config.color} ${isActive ? 'animate-pulse' : ''}`}>
                  {config.icon}
                </span>

                {/* Step info */}
                <div className="flex-1 min-w-0">
                  <p className={`text-xs font-semibold ${
                    step.status === 'idle' ? 'text-gray-400' : 'text-gray-800'
                  }`}>
                    {step.label}
                  </p>
                  {step.status !== 'idle' && (
                    <p className={`text-[10px] mt-0.5 ${
                      isActive ? 'text-blue-600' :
                      step.status === 'awaiting_approval' ? 'text-amber-600' :
                      step.status === 'completed' ? 'text-green-600' :
                      'text-gray-500'
                    }`}>
                      {step.status === 'awaiting_approval' ? 'Waiting for human decision' :
                       step.status === 'completed' && step.id === 'guardrail_validation' ? 'All policies passed ✓' :
                       step.status === 'completed' ? '✓ Done' :
                       step.description}
                    </p>
                  )}
                </div>
              </div>

              {/* Connector line */}
              {index < steps.length - 1 && (
                <div className="flex justify-start ml-[14px] py-0.5">
                  <div className={`w-0.5 h-2 ${
                    step.status === 'completed' ? 'bg-green-300' :
                    step.status === 'running' ? 'bg-blue-300' :
                    'bg-gray-200'
                  }`} />
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
