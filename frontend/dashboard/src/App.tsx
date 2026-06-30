import { BrowserRouter, Routes, Route, Navigate, useLocation, useSearchParams, Link, useNavigate } from 'react-router-dom';
import { useState } from 'react';
import AuthGuard from './components/AuthGuard';
import AuthCallback from './components/AuthCallback';
import PricingRequestForm from './pages/PricingRequestForm';
import CycleDetail from './pages/CycleDetail';
import ArchFlowPage from './pages/ArchFlowPage';
import MethodologyPage from './pages/MethodologyPage';
import AuditTrail from './components/AuditTrail';
import FinancialMetrics from './components/FinancialMetrics';
import TreeTable from './components/TreeTable';
import StrategyComparison from './components/StrategyComparison';
import OpsTab from './components/OpsTab';
import PricePredictionTab from './components/PricePredictionTab';
import api from './lib/api';
import { login, logout } from './lib/cognito';
import { isOperationsUser, getUserEmail, getPrimaryRole } from './lib/roles';

function DashboardHome() {
  const [activeTab, setActiveTab] = useState<'overview' | 'simulations' | 'analytics' | 'audit' | 'predictions' | 'ops'>('overview');
  const opsUser = isOperationsUser();
  const userEmail = getUserEmail();
  const role = getPrimaryRole();

  const tabs = [
    { id: 'overview' as const, label: 'Overview', icon: '🏠', roles: ['PricingAnalysts', 'Operations'] },
    { id: 'simulations' as const, label: 'Simulations', icon: '🧪', roles: ['PricingAnalysts', 'Operations'] },
    { id: 'analytics' as const, label: 'Analytics', icon: '📊', roles: ['PricingAnalysts', 'Operations'] },
    { id: 'audit' as const, label: 'Audit Trail', icon: '📋', roles: ['PricingAnalysts', 'Operations'] },
    { id: 'predictions' as const, label: 'Price Predictions', icon: '🔮', roles: ['PricingAnalysts', 'Operations'] },
    { id: 'ops' as const, label: 'Operations', icon: '⚙️', roles: ['Operations'] },
  ].filter(tab => tab.roles.includes(role) || role === 'unknown');

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white shadow-sm border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4 flex items-center justify-between">
          <h1 className="text-2xl font-semibold text-gray-900">
            CCOE Dynamic Pricing Solution for Retail Transformation
          </h1>
          <div className="flex items-center gap-3">
            <span className="text-xs text-gray-500 bg-gray-100 px-2 py-1 rounded">
              {userEmail || 'user'} ({role === 'Operations' ? 'Ops' : 'Analyst'})
            </span>
            <Link
              to="/methodology"
              className="px-3 py-2 text-sm font-medium text-gray-600 hover:text-blue-600 transition-colors"
            >
              📖 Methodology
            </Link>
            <button
              onClick={logout}
              className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              Sign Out
            </button>
          </div>
        </div>
        {/* Tab Navigation */}
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <nav className="flex gap-1 -mb-px">
            {tabs.map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`px-4 py-2.5 text-sm font-medium border-b-2 transition-colors ${
                  activeTab === tab.id
                    ? 'border-blue-600 text-blue-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                }`}
              >
                <span className="mr-1.5">{tab.icon}</span>
                {tab.label}
              </button>
            ))}
          </nav>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
        {activeTab === 'overview' && <OverviewTab />}
        {activeTab === 'simulations' && <SimulationsTab />}
        {activeTab === 'analytics' && <AnalyticsTab />}
        {activeTab === 'audit' && <AuditTrail />}
        {activeTab === 'predictions' && <PricePredictionTab />}
        {activeTab === 'ops' && opsUser && <OpsTab />}
      </main>
    </div>
  );
}

function OverviewTab() {
  const [resetting, setResetting] = useState(false);
  const [resetDone, setResetDone] = useState(false);

  const handleReset = async () => {
    if (!confirm('Reset demo? This will clear ALL pricing cycles, scenarios, and reset product prices to original values. This cannot be undone.')) return;
    setResetting(true);
    try {
      await api.post('/reset');
      setResetDone(true);
      setTimeout(() => window.location.reload(), 1500);
    } catch {
      alert('Reset failed. Check console for details.');
    } finally {
      setResetting(false);
    }
  };

  const [seeding, setSeeding] = useState(false);
  const [seedDone, setSeedDone] = useState(false);

  const handleSeed = async () => {
    setSeeding(true);
    try {
      await api.post('/seed');
      setSeedDone(true);
      setTimeout(() => window.location.reload(), 1500);
    } catch {
      alert('Seed failed. Check console for details.');
    } finally {
      setSeeding(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Quick Actions */}
      <div className="flex items-center gap-4">
        <Link
          to="/pricing-request"
          className="inline-flex items-center px-5 py-2.5 text-sm font-medium text-white bg-blue-600 rounded-md hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 shadow-sm"
        >
          + New Pricing Request
        </Link>
        <button
          onClick={handleReset}
          disabled={resetting}
          className="inline-flex items-center px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 disabled:opacity-50"
        >
          {resetting ? 'Resetting...' : resetDone ? '✓ Reset Complete' : '↺ Reset Demo'}
        </button>
        <button
          onClick={handleSeed}
          disabled={seeding}
          className="inline-flex items-center px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 disabled:opacity-50"
        >
          {seeding ? 'Seeding...' : seedDone ? '✓ Seeded' : '📊 Seed Historical Data'}
        </button>
        <p className="text-sm text-gray-500">Reset clears all data • Seed adds 5 sample pricing cycles</p>
      </div>

      {/* System Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <AnalyticsCard label="Avg Cycle Time" value="< 2 min" subtext="vs 6-10 weeks manual" icon="⚡" color="blue" />
        <AnalyticsCard label="Scenarios per Cycle" value="3" subtext="ranked by business impact" icon="📊" color="purple" />
        <AnalyticsCard label="Guardrail Policies" value="4 active" subtext="Bedrock Guardrails enforced" icon="🛡️" color="green" />
        <AnalyticsCard label="AI Agents" value="6" subtext="on AgentCore Runtime" icon="🤖" color="indigo" />
      </div>

      {/* Strategy Comparison */}
      <StrategyComparison />


    </div>
  );
}

function SimulationsTab() {
  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-semibold text-gray-900 mb-1">Demo Simulations</h2>
        <p className="text-sm text-gray-600 mb-4">
          Run pre-configured scenarios to see how the AI pricing system responds to different market conditions.
          Select a product group for each scenario before running.
        </p>
      </div>

      {/* Market Condition Scenarios */}
      <div>
        <h3 className="text-sm font-semibold text-gray-700 uppercase tracking-wider mb-3">Market Conditions</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          <SimulationCard
            title="Supply Chain Disruption"
            description="Rising costs from supply chain issues. Agents adjust prices to protect margins while staying competitive."
            icon="🚢"
            defaultPricingGroup="Electronics-Audio"
            objectives={['margin_protection']}
            constraints={{ minMargin: 20, maxPriceChange: 15 }}
          />
          <SimulationCard
            title="Viral Demand Spike"
            description="A product goes viral. Agents balance revenue maximization against stock depletion risk."
            icon="📈"
            defaultPricingGroup="Electronics-Wearables"
            objectives={['revenue_maximization', 'market_share_growth']}
            constraints={{ minMargin: 12, maxPriceChange: 20 }}
          />
          <SimulationCard
            title="Competitor Price War"
            description="A competitor slashes prices 15%. Agents respond with competitive positioning strategies."
            icon="⚔️"
            defaultPricingGroup="Grocery-Beverages"
            objectives={['competitive_positioning', 'margin_protection']}
            constraints={{ minMargin: 10, maxPriceChange: 12 }}
          />
          <SimulationCard
            title="Seasonal Trend Shift"
            description="End-of-season transition. Agents optimize clearance pricing while protecting brand value."
            icon="🍂"
            defaultPricingGroup="Home & Garden-Garden"
            objectives={['revenue_maximization', 'competitive_positioning']}
            constraints={{ minMargin: 8, maxPriceChange: 25 }}
          />
          <SimulationCard
            title="High Stock Clearance"
            description="Excess inventory needs clearing. Agents find optimal markdown depth to move units fast."
            icon="📦"
            defaultPricingGroup="Electronics-Tablets"
            objectives={['revenue_maximization']}
            constraints={{ minMargin: 5, maxPriceChange: 30 }}
          />
          <SimulationCard
            title="Premium Positioning"
            description="Luxury segment pricing. Agents maintain premium perception while maximizing margin."
            icon="💎"
            defaultPricingGroup="Electronics-Wearables"
            objectives={['margin_protection']}
            constraints={{ minMargin: 35, maxPriceChange: 8 }}
          />
          <SimulationCard
            title="Low Inventory Alert"
            description="Stock running low on a popular item. Agents increase prices to slow demand and maximize revenue per unit."
            icon="🔻"
            defaultPricingGroup="Electronics-Audio"
            objectives={['revenue_maximization', 'margin_protection']}
            constraints={{ minMargin: 25, maxPriceChange: 12 }}
          />
        </div>
      </div>

      {/* Automation Scenarios */}
      <div>
        <h3 className="text-sm font-semibold text-gray-700 uppercase tracking-wider mb-3">Automation & Processing</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          <SimulationCard
            title="Straight-Through Processing"
            description="Low-risk auto-optimization. Fully autonomous pricing with no human intervention needed."
            icon="⚡"
            defaultPricingGroup="Home & Garden-Lighting"
            objectives={['revenue_maximization']}
            constraints={{ minMargin: 25, maxPriceChange: 5 }}
          />
        </div>
      </div>

      {/* Guardrails Enforcement Scenarios */}
      <div>
        <h3 className="text-sm font-semibold text-gray-700 uppercase tracking-wider mb-3">🛡️ Guardrails Enforcement</h3>
        <p className="text-xs text-gray-600 mb-3">
          Demonstrate how the system blocks non-compliant pricing strategies. These simulations intentionally trigger guardrail violations to show compliance enforcement in action.
        </p>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          <GuardrailDemoCard
            title="Below-Cost Rejection"
            description="Attempts to price a product below its total unit cost (COGS). The guardrail blocks this to prevent predatory loss-making."
            icon="🚫"
            guardrailType="below_cost"
            regulation="Robinson-Patman Act"
          />
          <GuardrailDemoCard
            title="MAP Violation"
            description="Attempts to advertise a product below the manufacturer's Minimum Advertised Price. Blocked to protect supplier agreements."
            icon="📋"
            guardrailType="map_violation"
            regulation="Colgate Doctrine / MAP Policy"
          />
          <GuardrailDemoCard
            title="Geographic Price Bias"
            description="Attempts to set prices with >15% variance across regions for the same product. Blocked to prevent discriminatory pricing."
            icon="🌍"
            guardrailType="geographic_bias"
            regulation="Robinson-Patman Act / EU Geo-blocking"
          />
          <GuardrailDemoCard
            title="Predatory Pricing Blocked"
            description="Attempts to use the system for predatory pricing strategy to eliminate competitors. Bedrock Guardrails block the request."
            icon="⚠️"
            guardrailType="predatory_pricing"
            regulation="Sherman Act / FTC Act"
          />
          <GuardrailDemoCard
            title="PII Protection"
            description="Attempts to include customer personal data (emails, phone numbers) in pricing analysis. System detects and blocks PII exposure."
            icon="🔒"
            guardrailType="pii_protection"
            regulation="GDPR / CCPA"
          />
          <GuardrailDemoCard
            title="Price Fixing Attempt"
            description="Attempts to coordinate prices with competitors. Bedrock Guardrails immediately block any collusion-related requests."
            icon="🤝"
            guardrailType="price_fixing"
            regulation="Sherman Act Section 1"
          />
        </div>
      </div>

      {/* Intelligent Scheduling (Production Concept) */}
      <div className="border-t border-gray-200 pt-6">
        <h3 className="text-sm font-semibold text-gray-700 uppercase tracking-wider mb-3">Intelligent Scheduling (Production-Ready)</h3>
        <p className="text-xs text-gray-600 mb-4">
          In production, pricing cycles can run autonomously based on intelligent triggers — no manual intervention required for low-risk scenarios.
        </p>

        <div className="bg-gradient-to-r from-gray-50 to-indigo-50 rounded-lg border border-gray-200 p-5">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Schedule Configuration */}
            <div>
              <h4 className="text-xs font-semibold text-gray-900 mb-3 flex items-center gap-1.5">
                <span className="text-base">⏰</span> Schedule Configuration
              </h4>
              <div className="space-y-2">
                <div className="flex items-center justify-between bg-white rounded-md p-2.5 border border-gray-200">
                  <div>
                    <span className="text-xs font-medium text-gray-800">Daily Price Review</span>
                    <p className="text-xs text-gray-500">Mon-Fri, 6:00 AM EST</p>
                  </div>
                  <span className="px-2 py-0.5 bg-emerald-100 text-emerald-700 text-xs font-medium rounded-full">Active</span>
                </div>
                <div className="flex items-center justify-between bg-white rounded-md p-2.5 border border-gray-200">
                  <div>
                    <span className="text-xs font-medium text-gray-800">Weekly Category Optimization</span>
                    <p className="text-xs text-gray-500">Every Monday, 4:00 AM EST</p>
                  </div>
                  <span className="px-2 py-0.5 bg-emerald-100 text-emerald-700 text-xs font-medium rounded-full">Active</span>
                </div>
                <div className="flex items-center justify-between bg-white rounded-md p-2.5 border border-gray-200">
                  <div>
                    <span className="text-xs font-medium text-gray-800">Monthly Strategic Review</span>
                    <p className="text-xs text-gray-500">1st of month, 8:00 AM EST</p>
                  </div>
                  <span className="px-2 py-0.5 bg-gray-100 text-gray-600 text-xs font-medium rounded-full">Paused</span>
                </div>
              </div>
            </div>

            {/* Event-Driven Triggers */}
            <div>
              <h4 className="text-xs font-semibold text-gray-900 mb-3 flex items-center gap-1.5">
                <span className="text-base">⚡</span> Event-Driven Triggers
              </h4>
              <div className="space-y-2">
                <div className="flex items-center justify-between bg-white rounded-md p-2.5 border border-gray-200">
                  <div>
                    <span className="text-xs font-medium text-gray-800">Competitor Price Drop {'>'} 10%</span>
                    <p className="text-xs text-gray-500">Auto-triggers cycle for affected category</p>
                  </div>
                  <span className="px-2 py-0.5 bg-emerald-100 text-emerald-700 text-xs font-medium rounded-full">Armed</span>
                </div>
                <div className="flex items-center justify-between bg-white rounded-md p-2.5 border border-gray-200">
                  <div>
                    <span className="text-xs font-medium text-gray-800">{'Inventory < 15% threshold'}</span>
                    <p className="text-xs text-gray-500">Triggers clearance pricing evaluation</p>
                  </div>
                  <span className="px-2 py-0.5 bg-emerald-100 text-emerald-700 text-xs font-medium rounded-full">Armed</span>
                </div>
                <div className="flex items-center justify-between bg-white rounded-md p-2.5 border border-gray-200">
                  <div>
                    <span className="text-xs font-medium text-gray-800">{'Demand Spike > 30% MoM'}</span>
                    <p className="text-xs text-gray-500">Triggers revenue maximization cycle</p>
                  </div>
                  <span className="px-2 py-0.5 bg-amber-100 text-amber-700 text-xs font-medium rounded-full">Monitor</span>
                </div>
              </div>
            </div>
          </div>

          {/* Auto-Execution Rules */}
          <div className="mt-5 pt-4 border-t border-gray-200">
            <h4 className="text-xs font-semibold text-gray-900 mb-2 flex items-center gap-1.5">
              <span className="text-base">🤖</span> Autonomous Execution Rules
            </h4>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              <div className="bg-emerald-50 border border-emerald-200 rounded-md p-3 text-center">
                <p className="text-xs font-semibold text-emerald-800">LOW Risk</p>
                <p className="text-xs text-emerald-700 mt-1">Auto-approve and implement</p>
                <p className="text-xs text-emerald-600 mt-0.5">No human intervention</p>
              </div>
              <div className="bg-amber-50 border border-amber-200 rounded-md p-3 text-center">
                <p className="text-xs font-semibold text-amber-800">MEDIUM Risk</p>
                <p className="text-xs text-amber-700 mt-1">Generate + notify analyst</p>
                <p className="text-xs text-amber-600 mt-0.5">4-hour approval window</p>
              </div>
              <div className="bg-red-50 border border-red-200 rounded-md p-3 text-center">
                <p className="text-xs font-semibold text-red-800">HIGH Risk</p>
                <p className="text-xs text-red-700 mt-1">Generate + escalate to manager</p>
                <p className="text-xs text-red-600 mt-0.5">Requires justification</p>
              </div>
            </div>
          </div>

          {/* Implementation Note */}
          <div className="mt-4 bg-blue-50 border border-blue-200 rounded-md p-3 text-xs text-blue-800">
            <strong>Production implementation:</strong> Uses Amazon EventBridge Scheduler for time-based triggers and EventBridge Rules for event-driven triggers. Each trigger invokes the pricing cycle Lambda, which orchestrates agents on AgentCore. STP (Straight-Through Processing) for LOW risk eliminates human bottlenecks while maintaining governance for high-impact decisions.
          </div>
        </div>
      </div>


    </div>
  );
}

function AnalyticsTab() {
  return (
    <div className="space-y-6">
      <FinancialMetrics />
      <TreeTable />
    </div>
  );
}

function AnalyticsCard({ label, value, subtext, icon, color }: {
  label: string; value: string; subtext: string; icon: string; color: string;
}) {
  const colorMap: Record<string, string> = {
    blue: 'bg-blue-50 border-blue-200',
    purple: 'bg-purple-50 border-purple-200',
    green: 'bg-green-50 border-green-200',
    indigo: 'bg-indigo-50 border-indigo-200',
  };
  return (
    <div className={`rounded-lg border p-4 ${colorMap[color] ?? 'bg-gray-50 border-gray-200'}`}>
      <div className="flex items-center gap-2 mb-1">
        <span className="text-lg">{icon}</span>
        <p className="text-xs text-gray-500 font-medium uppercase">{label}</p>
      </div>
      <p className="text-xl font-bold text-gray-900">{value}</p>
      <p className="text-[10px] text-gray-500 mt-0.5">{subtext}</p>
    </div>
  );
}

const SIMULATION_PRODUCT_OPTIONS = [
  { label: 'Electronics (all)', value: 'Electronics' },
  { label: 'Electronics > Audio', value: 'Electronics-Audio' },
  { label: 'Electronics > Wearables', value: 'Electronics-Wearables' },
  { label: 'Electronics > Tablets', value: 'Electronics-Tablets' },
  { label: 'Grocery (all)', value: 'Grocery' },
  { label: 'Grocery > Dairy', value: 'Grocery-Dairy' },
  { label: 'Grocery > Beverages', value: 'Grocery-Beverages' },
  { label: 'Home & Garden (all)', value: 'Home & Garden' },
  { label: 'Home & Garden > Garden', value: 'Home & Garden-Garden' },
  { label: 'Home & Garden > Lighting', value: 'Home & Garden-Lighting' },
  { label: 'Home & Garden > Tools', value: 'Home & Garden-Tools' },
  { label: 'ProSound Wireless Earbuds', value: 'product-prod-elec-001' },
  { label: 'FitTrack Pro Smartwatch', value: 'product-prod-elec-003' },
  { label: 'Mountain Roast Coffee', value: 'product-prod-groc-002' },
  { label: 'CleanForce Stick Vacuum', value: 'product-prod-home-002' },
  { label: 'EcoTemp Smart Thermostat', value: 'product-prod-home-004' },
];

function SimulationCard({
  title, description, icon, defaultPricingGroup, objectives, constraints,
}: {
  title: string;
  description: string;
  icon: string;
  defaultPricingGroup: string;
  objectives: string[];
  constraints: Record<string, number>;
}) {
  const [loading, setLoading] = useState(false);
  const [selectedGroup, setSelectedGroup] = useState(defaultPricingGroup);
  const navigate = useNavigate();

  const handleRun = async () => {
    setLoading(true);
    try {
      const response = await api.post('/pricing-cycles', {
        pricingGroup: selectedGroup,
        objectives,
        constraints,
      });
      const cycleId = response.data.cycleId;
      navigate(`/cycles/${cycleId}`);
    } catch {
      setLoading(false);
    }
  };

  return (
    <div className="bg-white rounded-lg border border-gray-200 shadow-sm p-5 flex flex-col">
      <div className="flex items-center gap-2 mb-2">
        <span className="text-2xl">{icon}</span>
        <h3 className="text-sm font-semibold text-gray-900">{title}</h3>
      </div>
      <p className="text-xs text-gray-600 mb-3">{description}</p>
      <select
        value={selectedGroup}
        onChange={(e) => setSelectedGroup(e.target.value)}
        className="w-full mb-3 px-2 py-1.5 text-xs border border-gray-300 rounded-md focus:outline-none focus:ring-1 focus:ring-indigo-500"
      >
        {SIMULATION_PRODUCT_OPTIONS.map((opt) => (
          <option key={opt.value} value={opt.value}>{opt.label}</option>
        ))}
      </select>
      <button
        onClick={handleRun}
        disabled={loading}
        className="w-full px-3 py-2 text-xs font-medium text-white bg-indigo-600 rounded-md hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
      >
        {loading ? 'Triggering...' : 'Run Simulation →'}
      </button>
    </div>
  );
}

interface GuardrailDemoResult {
  rule: string;
  passed: boolean;
  reason: string | null;
  scenario: {
    productId: string;
    productName: string;
    attemptedPrice: number;
    costOrThreshold: number;
  };
}

function GuardrailDemoCard({
  title, description, icon, guardrailType, regulation,
}: {
  title: string;
  description: string;
  icon: string;
  guardrailType: string;
  regulation: string;
}) {
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<GuardrailDemoResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleRun = async () => {
    setLoading(true);
    setResult(null);
    setError(null);
    try {
      const response = await api.post('/guardrails/demo', {
        guardrailType,
      });
      setResult(response.data);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Guardrail demo failed';
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="bg-white rounded-lg border border-gray-200 shadow-sm p-5 flex flex-col">
      <div className="flex items-center gap-2 mb-2">
        <span className="text-2xl">{icon}</span>
        <h3 className="text-sm font-semibold text-gray-900">{title}</h3>
      </div>
      <p className="text-xs text-gray-600 mb-2">{description}</p>
      <p className="text-[10px] text-gray-400 mb-3 italic">Regulation: {regulation}</p>

      <button
        onClick={handleRun}
        disabled={loading}
        className="w-full px-3 py-2 text-xs font-medium text-white bg-red-600 rounded-md hover:bg-red-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors mb-3"
      >
        {loading ? 'Testing Guardrail...' : '🛡️ Test Guardrail →'}
      </button>

      {/* Result display */}
      {result && (
        <div className={`rounded-md border p-3 text-xs ${
          result.passed
            ? 'bg-green-50 border-green-200'
            : 'bg-red-50 border-red-200'
        }`}>
          <div className="flex items-center gap-1.5 mb-1.5">
            <span className={`font-bold ${result.passed ? 'text-green-700' : 'text-red-700'}`}>
              {result.passed ? '✓ PASSED' : '✗ BLOCKED'}
            </span>
            <span className="text-gray-500">— {result.rule}</span>
          </div>
          {result.scenario && (
            <div className="text-gray-600 space-y-0.5 mb-1.5">
              <p><span className="font-medium">Product:</span> {result.scenario.productName}</p>
              <p><span className="font-medium">Attempted Price:</span> ${result.scenario.attemptedPrice.toFixed(2)}</p>
              <p><span className="font-medium">Threshold:</span> ${result.scenario.costOrThreshold.toFixed(2)}</p>
            </div>
          )}
          {result.reason && (
            <p className={`font-medium ${result.passed ? 'text-green-700' : 'text-red-700'}`}>
              {result.reason}
            </p>
          )}
        </div>
      )}

      {error && (
        <div className="rounded-md border border-red-200 bg-red-50 p-3 text-xs text-red-700">
          {error}
        </div>
      )}
    </div>
  );
}

function LoginPage() {
  const location = useLocation();
  const [searchParams] = useSearchParams();

  // Get error from URL params (e.g., from AuthCallback or API 401 redirect) or from route state
  const urlError = searchParams.get('error');
  const stateError = (location.state as { error?: string })?.error;

  let errorMessage: string | null = null;
  if (urlError === 'auth_failed') {
    errorMessage = 'Authentication failed. Please try again.';
  } else if (urlError === 'session_expired') {
    errorMessage = 'Your session has expired. Please sign in again.';
  } else if (stateError) {
    errorMessage = stateError;
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <div className="max-w-md w-full space-y-8 p-8 bg-white rounded-lg shadow">
        <h2 className="text-center text-3xl font-bold text-gray-900">
          Sign In
        </h2>
        <p className="text-center text-gray-600">
          Please sign in with your credentials to access the dashboard.
        </p>
        {errorMessage && (
          <div className="bg-red-50 border border-red-200 rounded-md p-3">
            <p className="text-sm text-red-700 text-center">{errorMessage}</p>
          </div>
        )}
        <button
          onClick={login}
          className="w-full flex justify-center py-3 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
        >
          Sign in with Cognito
        </button>
      </div>
    </div>
  );
}

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/callback" element={<AuthCallback />} />
        <Route
          path="/"
          element={
            <AuthGuard>
              <DashboardHome />
            </AuthGuard>
          }
        />
        <Route
          path="/pricing-request"
          element={
            <AuthGuard>
              <div className="min-h-screen bg-gray-50">
                <header className="bg-white shadow-sm border-b border-gray-200">
                  <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4 flex items-center justify-between">
                    <div className="flex items-center gap-4">
                      <Link to="/" className="text-sm text-blue-600 hover:text-blue-800">&larr; Back</Link>
                      <h1 className="text-2xl font-semibold text-gray-900">
                        Dynamic Pricing for Retail
                      </h1>
                    </div>
                    <button
                      onClick={logout}
                      className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-blue-500"
                    >
                      Sign Out
                    </button>
                  </div>
                </header>
                <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
                  <PricingRequestForm />
                </main>
              </div>
            </AuthGuard>
          }
        />
        <Route
          path="/cycles/:cycleId"
          element={
            <AuthGuard>
              <div className="min-h-screen bg-gray-50">
                <header className="bg-white shadow-sm border-b border-gray-200">
                  <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4 flex items-center justify-between">
                    <h1 className="text-2xl font-semibold text-gray-900">
                      Dynamic Pricing for Retail
                    </h1>
                    <button
                      onClick={logout}
                      className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-blue-500"
                    >
                      Sign Out
                    </button>
                  </div>
                </header>
                <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
                  <CycleDetail />
                </main>
              </div>
            </AuthGuard>
          }
        />
        <Route
          path="/arch-flow"
          element={
            <AuthGuard>
              <ArchFlowPage />
            </AuthGuard>
          }
        />
        <Route
          path="/methodology"
          element={
            <AuthGuard>
              <MethodologyPage />
            </AuthGuard>
          }
        />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
