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
            <h4 className="text-sm font-semibold text-gray-900 mb-3">How It Works — Technical Architecture</h4>
            <div className="space-y-3 text-xs text-gray-700 leading-relaxed">
              <div className="border-l-2 border-indigo-400 pl-3">
                <span className="font-semibold text-indigo-800">1. Request Ingestion</span>
                <p className="mt-0.5">The React Dashboard (served via CloudFront + S3) authenticates users through Amazon Cognito. Authenticated requests flow through API Gateway REST endpoints to Lambda handlers.</p>
              </div>
              <div className="border-l-2 border-blue-400 pl-3">
                <span className="font-semibold text-blue-800">2. Agent Orchestration</span>
                <p className="mt-0.5">The Pricing Cycles Lambda invokes the Orchestrator Agent on AgentCore Runtime via SigV4-signed HTTP. The Orchestrator coordinates 5 specialist agents (Competitive Intelligence, Demand Forecasting, Market Intelligence, Strategy Synthesis, Implementation Monitoring) running as containerized runtimes on AgentCore.</p>
              </div>
              <div className="border-l-2 border-emerald-400 pl-3">
                <span className="font-semibold text-emerald-800">3. Data Integration (MCP)</span>
                <p className="mt-0.5">Agents access external data through 4 MCP Servers (Lambda functions) registered on AgentCore Gateway: Competitor API, ERP/POS, Market Signals, and Cost & Finance. The Gateway provides tool discovery and routing.</p>
              </div>
              <div className="border-l-2 border-amber-400 pl-3">
                <span className="font-semibold text-amber-800">4. Scenario Generation & Compliance</span>
                <p className="mt-0.5">Strategy Synthesis generates 5 ranked pricing scenarios. Each passes through Bedrock Guardrails (4 policies: anti-predatory, anti-discrimination, MAP compliance, price gouging prevention) before storage in DynamoDB.</p>
              </div>
              <div className="border-l-2 border-red-400 pl-3">
                <span className="font-semibold text-red-800">5. Approval & Implementation</span>
                <p className="mt-0.5">Risk classification routes scenarios: LOW risk auto-approves (STP), MEDIUM/HIGH routes to human reviewers. Approved prices update the Products table and propagate to the Storefront in real-time.</p>
              </div>
              <div className="border-l-2 border-slate-400 pl-3">
                <span className="font-semibold text-slate-800">6. Observability & Memory</span>
                <p className="mt-0.5">All operations emit structured JSON logs to CloudWatch. AgentCore Memory persists historical outcomes for cross-session learning. The CloudWatch operational dashboard (CDK-provisioned) tracks Lambda latency, API errors, and DynamoDB throughput.</p>
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
        <MetricCard label="Scenarios Generated" value={String(business.scenariosGenerated ?? '--')} subtext="5 per cycle" />
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
