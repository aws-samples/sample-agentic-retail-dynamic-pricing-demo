import { useState } from 'react';

interface Schedule {
  name: string;
  frequency: string;
  time: string;
  enabled: boolean;
  description: string;
}

interface Trigger {
  name: string;
  threshold: number;
  unit: string;
  description: string;
  armed: boolean;
}

interface ExecutionRule {
  level: 'LOW' | 'MEDIUM' | 'HIGH';
  autoApprove: boolean;
  approvalWindow: string;
  escalationTarget: string;
}

const frequencyOptions = ['Daily', 'Weekdays Only', 'Weekly', 'Bi-weekly', 'Monthly'];
const approvalWindowOptions = ['2 hours', '4 hours', '8 hours', '24 hours'];
const escalationTargetOptions = ['Senior Analyst', 'Pricing Manager', 'VP Pricing'];

function Toggle({ enabled, onToggle }: { enabled: boolean; onToggle: () => void }) {
  return (
    <button
      type="button"
      onClick={onToggle}
      className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 ${
        enabled ? 'bg-blue-600' : 'bg-gray-300'
      }`}
    >
      <span
        className={`inline-block h-4 w-4 transform rounded-full bg-white shadow transition-transform duration-200 ease-in-out ${
          enabled ? 'translate-x-6' : 'translate-x-1'
        }`}
      />
    </button>
  );
}

function StatusBadge({ active, activeLabel, inactiveLabel }: { active: boolean; activeLabel: string; inactiveLabel: string }) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${
        active
          ? 'bg-green-100 text-green-800'
          : 'bg-gray-100 text-gray-600'
      }`}
    >
      <span
        className={`mr-1.5 h-1.5 w-1.5 rounded-full ${
          active ? 'bg-green-500' : 'bg-gray-400'
        }`}
      />
      {active ? activeLabel : inactiveLabel}
    </span>
  );
}

export default function SchedulingTab() {
  const [schedules, setSchedules] = useState<Schedule[]>([
    { name: 'Daily Price Review', frequency: 'Weekdays Only', time: '06:00', enabled: true, description: 'Runs a full pricing cycle across all active product categories every weekday morning before market open. Analyzes overnight competitor changes and demand signals to recommend pre-market adjustments.' },
    { name: 'Category Optimization', frequency: 'Weekly', time: '04:00', enabled: true, description: 'Deep optimization pass on each category in rotation (Electronics Monday, Grocery Wednesday, Home & Garden Friday). Uses extended analysis windows for seasonal trend detection and margin recalibration.' },
    { name: 'Strategic Review', frequency: 'Monthly', time: '08:00', enabled: false, description: 'Comprehensive portfolio-level pricing strategy review. Evaluates 90-day performance trends, recalibrates risk thresholds, and generates executive summary with recommendations for the pricing committee.' },
  ]);

  const [triggers, setTriggers] = useState<Trigger[]>([
    { name: 'Competitor Price Drop', threshold: 10, unit: '%', description: 'Triggers immediate competitive response analysis when a competitor drops price by this threshold or more.', armed: true },
    { name: 'Inventory Threshold', threshold: 15, unit: '%', description: 'Initiates markdown optimization when stock levels fall below threshold percentage of capacity.', armed: true },
    { name: 'Demand Spike', threshold: 30, unit: '% MoM', description: 'Activates dynamic pricing uplift when month-over-month demand exceeds threshold.', armed: false },
  ]);

  const [executionRules, setExecutionRules] = useState<ExecutionRule[]>([
    { level: 'LOW', autoApprove: true, approvalWindow: '', escalationTarget: '' },
    { level: 'MEDIUM', autoApprove: false, approvalWindow: '4 hours', escalationTarget: '' },
    { level: 'HIGH', autoApprove: false, approvalWindow: '', escalationTarget: 'Pricing Manager' },
  ]);

  const [showToast, setShowToast] = useState(false);

  const handleScheduleToggle = (index: number) => {
    setSchedules((prev) =>
      prev.map((s, i) => (i === index ? { ...s, enabled: !s.enabled } : s))
    );
  };

  const handleScheduleFrequency = (index: number, frequency: string) => {
    setSchedules((prev) =>
      prev.map((s, i) => (i === index ? { ...s, frequency } : s))
    );
  };

  const handleScheduleTime = (index: number, time: string) => {
    setSchedules((prev) =>
      prev.map((s, i) => (i === index ? { ...s, time } : s))
    );
  };

  const handleTriggerToggle = (index: number) => {
    setTriggers((prev) =>
      prev.map((t, i) => (i === index ? { ...t, armed: !t.armed } : t))
    );
  };

  const handleTriggerThreshold = (index: number, threshold: number) => {
    setTriggers((prev) =>
      prev.map((t, i) => (i === index ? { ...t, threshold } : t))
    );
  };

  const handleAutoApproveToggle = (index: number) => {
    setExecutionRules((prev) =>
      prev.map((r, i) => (i === index ? { ...r, autoApprove: !r.autoApprove } : r))
    );
  };

  const handleApprovalWindow = (index: number, approvalWindow: string) => {
    setExecutionRules((prev) =>
      prev.map((r, i) => (i === index ? { ...r, approvalWindow } : r))
    );
  };

  const handleEscalationTarget = (index: number, escalationTarget: string) => {
    setExecutionRules((prev) =>
      prev.map((r, i) => (i === index ? { ...r, escalationTarget } : r))
    );
  };

  const handleSave = () => {
    setShowToast(true);
    setTimeout(() => setShowToast(false), 3000);
  };

  const riskColors: Record<string, { bg: string; text: string; border: string }> = {
    LOW: { bg: 'bg-green-50', text: 'text-green-700', border: 'border-green-200' },
    MEDIUM: { bg: 'bg-yellow-50', text: 'text-yellow-700', border: 'border-yellow-200' },
    HIGH: { bg: 'bg-red-50', text: 'text-red-700', border: 'border-red-200' },
  };

  return (
    <div className="space-y-6">
      {/* Toast */}
      {showToast && (
        <div className="fixed top-4 right-4 z-50 rounded-lg bg-green-50 border border-green-200 px-4 py-3 shadow-lg">
          <div className="flex items-center gap-2">
            <svg className="h-5 w-5 text-green-600" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <p className="text-sm text-green-800">
              Configuration saved successfully. Changes will take effect on next scheduled run.
            </p>
          </div>
        </div>
      )}

      {/* Header */}
      <div>
        <h2 className="text-xl font-semibold text-gray-900">Intelligent Pricing Scheduler</h2>
        <p className="mt-1 text-sm text-gray-500">
          Configure autonomous pricing cycles that run on schedule or respond to market events. 
          The system orchestrates multi-agent workflows to analyze, recommend, and execute pricing decisions with governance controls.
        </p>
      </div>

      {/* Schedule Configuration */}
      <div className="bg-white rounded-lg border border-gray-200 shadow-sm p-5">
        <h3 className="text-base font-medium text-gray-900 mb-4">Schedule Configuration</h3>
        <div className="space-y-4">
          {schedules.map((schedule, index) => (
            <div
              key={schedule.name}
              className="flex flex-col sm:flex-row sm:items-center gap-3 rounded-lg border border-gray-100 bg-gray-50 p-4"
            >
              <div className="flex items-center gap-3 min-w-[200px]">
                <Toggle enabled={schedule.enabled} onToggle={() => handleScheduleToggle(index)} />
                <span className="text-sm font-medium text-gray-900">{schedule.name}</span>
              </div>

              <div className="flex flex-wrap items-center gap-3 flex-1">
                <select
                  value={schedule.frequency}
                  onChange={(e) => handleScheduleFrequency(index, e.target.value)}
                  className="rounded-md border border-gray-300 bg-white px-3 py-1.5 text-sm text-gray-700 shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                >
                  {frequencyOptions.map((opt) => (
                    <option key={opt} value={opt}>{opt}</option>
                  ))}
                </select>

                <input
                  type="time"
                  value={schedule.time}
                  onChange={(e) => handleScheduleTime(index, e.target.value)}
                  className="rounded-md border border-gray-300 bg-white px-3 py-1.5 text-sm text-gray-700 shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                />

                <StatusBadge active={schedule.enabled} activeLabel="Active" inactiveLabel="Paused" />
              </div>
              <p className="mt-2 text-xs text-gray-500 pl-14">{schedule.description}</p>
            </div>
          ))}
        </div>
      </div>

      {/* Event-Driven Triggers */}
      <div className="bg-white rounded-lg border border-gray-200 shadow-sm p-5">
        <h3 className="text-base font-medium text-gray-900 mb-4">Event-Driven Triggers</h3>
        <div className="space-y-4">
          {triggers.map((trigger, index) => (
            <div
              key={trigger.name}
              className="rounded-lg border border-gray-100 bg-gray-50 p-4"
            >
              <div className="flex flex-col sm:flex-row sm:items-center gap-3">
                <div className="flex items-center gap-3 min-w-[200px]">
                  <Toggle enabled={trigger.armed} onToggle={() => handleTriggerToggle(index)} />
                  <span className="text-sm font-medium text-gray-900">{trigger.name}</span>
                </div>

                <div className="flex items-center gap-2 flex-1">
                  <label className="text-sm text-gray-500">Threshold:</label>
                  <input
                    type="number"
                    value={trigger.threshold}
                    onChange={(e) => handleTriggerThreshold(index, Number(e.target.value))}
                    className="w-20 rounded-md border border-gray-300 bg-white px-2 py-1.5 text-sm text-gray-700 shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                  />
                  <span className="text-sm text-gray-500">{trigger.unit}</span>

                  <div className="ml-auto">
                    <StatusBadge active={trigger.armed} activeLabel="Armed" inactiveLabel="Disarmed" />
                  </div>
                </div>
              </div>
              <p className="mt-2 text-xs text-gray-500 pl-14">{trigger.description}</p>
            </div>
          ))}
        </div>
      </div>

      {/* Autonomous Execution Rules */}
      <div className="bg-white rounded-lg border border-gray-200 shadow-sm p-5">
        <h3 className="text-base font-medium text-gray-900 mb-4">Autonomous Execution Rules</h3>
        <div className="space-y-4">
          {executionRules.map((rule, index) => {
            const colors = riskColors[rule.level];
            return (
              <div
                key={rule.level}
                className={`rounded-lg border p-4 ${colors.border} ${colors.bg}`}
              >
                <div className="flex flex-col sm:flex-row sm:items-center gap-3">
                  <span className={`inline-flex items-center rounded-md px-2.5 py-1 text-xs font-bold ${colors.text} ${colors.bg} border ${colors.border}`}>
                    {rule.level} RISK
                  </span>

                  {rule.level === 'LOW' && (
                    <div className="flex items-center gap-3">
                      <Toggle enabled={rule.autoApprove} onToggle={() => handleAutoApproveToggle(index)} />
                      <span className="text-sm text-gray-700">Auto-approve (STP — Straight-Through Processing)</span>
                    </div>
                  )}

                  {rule.level === 'MEDIUM' && (
                    <div className="flex items-center gap-3">
                      <label className="text-sm text-gray-700">Approval window:</label>
                      <select
                        value={rule.approvalWindow}
                        onChange={(e) => handleApprovalWindow(index, e.target.value)}
                        className="rounded-md border border-gray-300 bg-white px-3 py-1.5 text-sm text-gray-700 shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                      >
                        {approvalWindowOptions.map((opt) => (
                          <option key={opt} value={opt}>{opt}</option>
                        ))}
                      </select>
                      <span className="text-xs text-gray-500">Auto-rejects if not approved within window</span>
                    </div>
                  )}

                  {rule.level === 'HIGH' && (
                    <div className="flex items-center gap-3">
                      <label className="text-sm text-gray-700">Escalation target:</label>
                      <select
                        value={rule.escalationTarget}
                        onChange={(e) => handleEscalationTarget(index, e.target.value)}
                        className="rounded-md border border-gray-300 bg-white px-3 py-1.5 text-sm text-gray-700 shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                      >
                        {escalationTargetOptions.map((opt) => (
                          <option key={opt} value={opt}>{opt}</option>
                        ))}
                      </select>
                      <span className="text-xs text-gray-500">Requires manual approval before execution</span>
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Save Button */}
      <div className="flex justify-end">
        <button
          type="button"
          onClick={handleSave}
          className="rounded-lg bg-blue-600 px-5 py-2.5 text-sm font-medium text-white shadow-sm hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 transition-colors"
        >
          Save Configuration
        </button>
      </div>

      {/* Production Note */}
      <div className="rounded-lg border border-blue-200 bg-blue-50 p-4">
        <div className="flex gap-3">
          <svg className="h-5 w-5 text-blue-600 mt-0.5 shrink-0" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" d="M11.25 11.25l.041-.02a.75.75 0 011.063.852l-.708 2.836a.75.75 0 001.063.853l.041-.021M21 12a9 9 0 11-18 0 9 9 0 0118 0zm-9-3.75h.008v.008H12V8.25z" />
          </svg>
          <div>
            <p className="text-sm font-medium text-blue-800">Production Implementation</p>
            <p className="mt-1 text-xs text-blue-700">
              Uses Amazon EventBridge Scheduler for time-based triggers and EventBridge Rules for event-driven triggers. 
              Each trigger invokes the pricing cycle Lambda, which orchestrates agents on AgentCore. 
              STP (Straight-Through Processing) for LOW risk eliminates human bottlenecks while maintaining governance for high-impact decisions.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
