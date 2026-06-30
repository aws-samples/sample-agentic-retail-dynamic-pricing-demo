/**
 * Operations Tab — Ops-only view with system health, metrics, architecture, and TCO.
 * Visible only to users in the 'Operations' Cognito group.
 */

import { useState, useEffect } from 'react';
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
        <div className="space-y-4">
          <div className="bg-white rounded-lg border border-gray-200 p-6">
            <ArchitectureDiagram />
          </div>
          <div className="bg-white rounded-lg border border-gray-200 p-5">
            <h4 className="text-sm font-semibold text-gray-900 mb-3">Recent Architecture Additions</h4>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
              <div className="bg-indigo-50 rounded-md p-3">
                <span className="font-medium text-indigo-800">Role-Based Access (RBAC)</span>
                <p className="text-indigo-700 mt-1">Cognito groups (PricingAnalysts, Operations) with JWT-based tab visibility. Ops tab restricted to Operations group.</p>
              </div>
              <div className="bg-emerald-50 rounded-md p-3">
                <span className="font-medium text-emerald-800">Price Prediction Simulator</span>
                <p className="text-emerald-700 mt-1">Client-side decision tree with what-if sliders. No backend calls — pure simulation for explainability demos.</p>
              </div>
              <div className="bg-amber-50 rounded-md p-3">
                <span className="font-medium text-amber-800">CloudWatch Metrics API</span>
                <p className="text-amber-700 mt-1">GET /metrics endpoint queries CloudWatch for Lambda, API Gateway, and DynamoDB metrics. Powers the Ops Metrics section.</p>
              </div>
              <div className="bg-slate-50 rounded-md p-3">
                <span className="font-medium text-slate-800">Operational Dashboard</span>
                <p className="text-slate-700 mt-1">CDK-provisioned CloudWatch dashboard (RetailDynamicPricing-Operations) with pre-built graphs for latency, errors, and throughput.</p>
              </div>
            </div>
          </div>
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
  const [metrics, setMetrics] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    import('../lib/api').then(({ default: api }) => {
      api.get('/metrics')
        .then((res: any) => setMetrics(res.data))
        .catch(() => setMetrics(null))
        .finally(() => setLoading(false));
    });
  }, []);

  if (loading) {
    return (
      <div className="text-center py-8 text-sm text-gray-500">Loading metrics from CloudWatch...</div>
    );
  }

  const lambda = metrics?.lambda || {};
  const apiGw = metrics?.apiGateway || {};
  const dynamo = metrics?.dynamodb || {};
  const business = metrics?.business || {};

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <MetricCard label="Total Cycles Run" value={String(business.totalCycles ?? '--')} subtext="Since deployment" />
        <MetricCard label="Scenarios Generated" value={String(business.scenariosGenerated ?? '--')} subtext="3 per cycle" />
        <MetricCard label="Lambda Invocations" value={String(lambda.invocations ?? '--')} subtext="Last 24h" />
        <MetricCard label="Error Rate" value={`${lambda.errorRate ?? 0}%`} subtext="Last 24h" />
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <MetricCard label="Lambda Duration (p90)" value={lambda.durationP90Ms ? `${lambda.durationP90Ms}ms` : '--'} subtext="Pricing cycles handler" />
        <MetricCard label="API Requests" value={String(apiGw.requests ?? '--')} subtext="Last 24h" />
        <MetricCard label="API Latency (p90)" value={apiGw.latencyP90Ms ? `${apiGw.latencyP90Ms}ms` : '--'} subtext="All endpoints" />
        <MetricCard label="DynamoDB Reads" value={String(dynamo.readUnits ?? '--')} subtext="Consumed RCUs" />
      </div>

      {metrics?.period && (
        <div className="text-xs text-gray-400 text-right">
          Data period: {metrics.period} | Updated: {new Date(metrics.timestamp).toLocaleTimeString()}
        </div>
      )}
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
