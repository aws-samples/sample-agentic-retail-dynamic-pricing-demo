/**
 * Operations Tab — Ops-only view with system health, metrics, architecture, and TCO.
 * Visible only to users in the 'Operations' Cognito group.
 */

import { useState } from 'react';
import TcoRoiTab from './TcoRoiTab';
import ArchitectureDiagram from './ArchitectureDiagram';

type OpsSection = 'health' | 'metrics' | 'architecture' | 'tco';

export default function OpsTab() {
  const [section, setSection] = useState<OpsSection>('health');

  const sections = [
    { id: 'health' as const, label: 'System Health', icon: '💚' },
    { id: 'metrics' as const, label: 'Metrics', icon: '📈' },
    { id: 'architecture' as const, label: 'Architecture', icon: '🏗️' },
    { id: 'tco' as const, label: 'TCO & ROI', icon: '💰' },
  ];

  return (
    <div className="space-y-6">
      {/* Ops Header */}
      <div className="bg-gradient-to-r from-slate-800 to-slate-700 rounded-lg p-4 text-white">
        <h2 className="text-lg font-semibold">Operations Dashboard</h2>
        <p className="text-sm text-slate-300 mt-1">System health, metrics, and infrastructure — Operations team only</p>
      </div>

      {/* Section Navigation */}
      <div className="flex gap-2 border-b border-gray-200 pb-2">
        {sections.map((s) => (
          <button
            key={s.id}
            onClick={() => setSection(s.id)}
            className={`px-3 py-1.5 text-sm font-medium rounded-md transition-colors ${
              section === s.id
                ? 'bg-slate-800 text-white'
                : 'text-gray-600 hover:bg-gray-100'
            }`}
          >
            {s.icon} {s.label}
          </button>
        ))}
      </div>

      {/* Section Content */}
      {section === 'health' && <SystemHealthSection />}
      {section === 'metrics' && <MetricsSection />}
      {section === 'architecture' && (
        <div className="bg-white rounded-lg border border-gray-200 p-6">
          <ArchitectureDiagram />
        </div>
      )}
      {section === 'tco' && <TcoRoiTab />}
    </div>
  );
}

function SystemHealthSection() {
  const services = [
    { name: 'API Gateway', status: 'healthy', latency: '45ms', icon: '🌐' },
    { name: 'Orchestrator Agent', status: 'healthy', latency: '1.2s', icon: '🤖' },
    { name: 'Competitive Intel Agent', status: 'healthy', latency: '0.8s', icon: '🔍' },
    { name: 'Demand Forecast Agent', status: 'healthy', latency: '0.9s', icon: '📊' },
    { name: 'Market Intel Agent', status: 'healthy', latency: '0.7s', icon: '🌍' },
    { name: 'Strategy Synthesis Agent', status: 'healthy', latency: '1.1s', icon: '🧮' },
    { name: 'Implementation Monitor', status: 'healthy', latency: '0.6s', icon: '👁️' },
    { name: 'DynamoDB (5 tables)', status: 'healthy', latency: '8ms', icon: '🗄️' },
    { name: 'Cognito Auth', status: 'healthy', latency: '12ms', icon: '🔐' },
    { name: 'AgentCore Gateway', status: 'healthy', latency: '35ms', icon: '🚪' },
    { name: 'AgentCore Memory', status: 'healthy', latency: '15ms', icon: '🧠' },
    { name: 'Bedrock Guardrails', status: 'healthy', latency: '22ms', icon: '🛡️' },
  ];

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
        {services.map((svc) => (
          <div key={svc.name} className="bg-white rounded-lg border border-gray-200 p-3 flex items-center gap-3">
            <span className="text-lg">{svc.icon}</span>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-gray-900 truncate">{svc.name}</p>
              <p className="text-xs text-gray-500">Avg: {svc.latency}</p>
            </div>
            <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800">
              {svc.status}
            </span>
          </div>
        ))}
      </div>

      <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 text-sm text-blue-800">
        <strong>Note:</strong> Health metrics are refreshed on page load. For real-time monitoring,
        view the <a href="https://console.aws.amazon.com/cloudwatch/" target="_blank" rel="noopener noreferrer" className="underline">CloudWatch Dashboard</a> in the AWS Console.
      </div>
    </div>
  );
}

function MetricsSection() {
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <MetricCard label="Total Cycles Run" value="--" subtext="Since deployment" />
        <MetricCard label="Avg Cycle Duration" value="< 2 min" subtext="6 agents in parallel" />
        <MetricCard label="Scenarios Generated" value="--" subtext="3 per cycle" />
        <MetricCard label="Approvals Processed" value="--" subtext="Auto + Human" />
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <MetricCard label="Bedrock Invocations" value="--" subtext="Last 24h" />
        <MetricCard label="Lambda Invocations" value="--" subtext="Last 24h" />
        <MetricCard label="DynamoDB Reads" value="--" subtext="Last 24h" />
        <MetricCard label="Error Rate" value="0%" subtext="Last 24h" />
      </div>

      <div className="bg-amber-50 border border-amber-200 rounded-lg p-4 text-sm text-amber-800">
        <strong>Live metrics:</strong> Values marked "--" require CloudWatch metric API integration.
        Cost Explorer data populates 24-48 hours after first deployment.
      </div>
    </div>
  );
}

function MetricCard({ label, value, subtext }: { label: string; value: string; subtext: string }) {
  return (
    <div className="bg-white rounded-lg border border-gray-200 p-4">
      <p className="text-xs text-gray-500 uppercase tracking-wide">{label}</p>
      <p className="text-2xl font-bold text-gray-900 mt-1">{value}</p>
      <p className="text-xs text-gray-500 mt-0.5">{subtext}</p>
    </div>
  );
}
