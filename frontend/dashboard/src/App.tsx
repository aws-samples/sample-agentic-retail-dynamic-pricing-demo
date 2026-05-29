import { BrowserRouter, Routes, Route, Navigate, useLocation, useSearchParams, Link, useNavigate } from 'react-router-dom';
import { useState } from 'react';
import AuthGuard from './components/AuthGuard';
import AuthCallback from './components/AuthCallback';
import PricingRequestForm from './pages/PricingRequestForm';
import CycleDetail from './pages/CycleDetail';
import AuditTrail from './components/AuditTrail';
import FinancialMetrics from './components/FinancialMetrics';
import ArchitectureDiagram from './components/ArchitectureDiagram';
import TcoRoiTab from './components/TcoRoiTab';
import api from './lib/api';
import { login, logout } from './lib/cognito';

function DashboardHome() {
  const [activeTab, setActiveTab] = useState<'overview' | 'simulations' | 'analytics' | 'audit' | 'tco'>('overview');

  const tabs = [
    { id: 'overview' as const, label: 'Overview', icon: '🏠' },
    { id: 'simulations' as const, label: 'Simulations', icon: '🧪' },
    { id: 'analytics' as const, label: 'Analytics', icon: '📊' },
    { id: 'audit' as const, label: 'Audit Trail', icon: '📋' },
    { id: 'tco' as const, label: 'TCO & ROI', icon: '💰' },
  ];

  return (
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
        {activeTab === 'tco' && <TcoRoiTab />}
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
        <AnalyticsCard label="Avg Cycle Time" value="~55s" subtext="vs 6-10 weeks manual" icon="⚡" color="blue" />
        <AnalyticsCard label="Scenarios per Cycle" value="3" subtext="ranked by business impact" icon="📊" color="purple" />
        <AnalyticsCard label="Guardrail Policies" value="4 active" subtext="Bedrock Guardrails enforced" icon="🛡️" color="green" />
        <AnalyticsCard label="AI Agents" value="6" subtext="on AgentCore Runtime" icon="🤖" color="indigo" />
      </div>

      {/* Architecture Diagram + Process Flow Explainer */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="lg:col-span-2">
          <ArchitectureDiagram />
        </div>
        <div className="bg-white rounded-lg border border-gray-200 shadow-sm p-5 flex flex-col">
          <h3 className="text-sm font-semibold text-gray-900 mb-1">How a Pricing Request is Processed</h3>
          <p className="text-[10px] text-gray-500 mb-4">Step-by-step flow from request to price update</p>
          <ol className="space-y-3 text-xs text-gray-700">
            <li className="flex gap-2">
              <span className="flex-shrink-0 w-5 h-5 rounded-full bg-blue-100 text-blue-700 flex items-center justify-center text-[10px] font-bold">1</span>
              <div>
                <p className="font-semibold text-gray-900">Pricing Request Submitted</p>
                <p className="text-gray-500 mt-0.5">A product manager submits a request via the Dashboard, specifying the product group, objectives (e.g. margin protection), and constraints.</p>
              </div>
            </li>
            <li className="flex gap-2">
              <span className="flex-shrink-0 w-5 h-5 rounded-full bg-purple-100 text-purple-700 flex items-center justify-center text-[10px] font-bold">2</span>
              <div>
                <p className="font-semibold text-gray-900">Orchestrator Dispatches Agents</p>
                <p className="text-gray-500 mt-0.5">The Orchestrator Agent (Claude Opus 4) breaks the task into parallel sub-tasks and dispatches Competitive Intel, Demand Forecasting, and Market Intelligence agents simultaneously.</p>
              </div>
            </li>
            <li className="flex gap-2">
              <span className="flex-shrink-0 w-5 h-5 rounded-full bg-amber-100 text-amber-700 flex items-center justify-center text-[10px] font-bold">3</span>
              <div>
                <p className="font-semibold text-gray-900">MCP Servers Provide Data</p>
                <p className="text-gray-500 mt-0.5">Each agent calls its MCP Server (Competitor API, ERP/POS, Market Signals, Cost & Finance) via the AgentCore Gateway to gather real-time intelligence.</p>
              </div>
            </li>
            <li className="flex gap-2">
              <span className="flex-shrink-0 w-5 h-5 rounded-full bg-green-100 text-green-700 flex items-center justify-center text-[10px] font-bold">4</span>
              <div>
                <p className="font-semibold text-gray-900">Strategy Synthesis</p>
                <p className="text-gray-500 mt-0.5">The Strategy Synthesis Agent combines all intelligence into 3 ranked pricing scenarios (Aggressive, Balanced, Conservative), each with projected impact.</p>
              </div>
            </li>
            <li className="flex gap-2">
              <span className="flex-shrink-0 w-5 h-5 rounded-full bg-red-100 text-red-700 flex items-center justify-center text-[10px] font-bold">5</span>
              <div>
                <p className="font-semibold text-gray-900">Guardrail Validation</p>
                <p className="text-gray-500 mt-0.5">Bedrock Guardrails check all scenarios against 4 denied-topic policies (anti-competitive, discriminatory, predatory pricing, PII exposure).</p>
              </div>
            </li>
            <li className="flex gap-2">
              <span className="flex-shrink-0 w-5 h-5 rounded-full bg-indigo-100 text-indigo-700 flex items-center justify-center text-[10px] font-bold">6</span>
              <div>
                <p className="font-semibold text-gray-900">Risk-Based Approval</p>
                <p className="text-gray-500 mt-0.5">LOW risk → auto-approved (STP). MEDIUM/HIGH risk → routed to human decision-maker with full context and AI rationale.</p>
              </div>
            </li>
            <li className="flex gap-2">
              <span className="flex-shrink-0 w-5 h-5 rounded-full bg-teal-100 text-teal-700 flex items-center justify-center text-[10px] font-bold">7</span>
              <div>
                <p className="font-semibold text-gray-900">Price Implementation & Monitoring</p>
                <p className="text-gray-500 mt-0.5">Approved prices are applied. The Implementation Monitor agent tracks variance and triggers corrective recommendations if actuals deviate from projections.</p>
              </div>
            </li>
          </ol>
          <div className="mt-4 pt-3 border-t border-gray-100">
            <p className="text-[10px] text-gray-500 leading-relaxed">
              <span className="font-semibold text-gray-700">Total time:</span> ~55 seconds end-to-end. The entire loop is closed — monitoring feeds back into future pricing decisions via AgentCore Memory.
            </p>
          </div>
        </div>
      </div>

      {/* Architecture & Data Sources */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-white rounded-lg shadow border border-gray-200 p-4">
          <p className="text-xs text-gray-500 uppercase tracking-wider mb-2">Architecture</p>
          <div className="space-y-1.5 text-xs text-gray-700">
            <p>• <span className="font-medium">Runtime:</span> Amazon Bedrock AgentCore</p>
            <p>• <span className="font-medium">Framework:</span> Strands Agents SDK</p>
            <p>• <span className="font-medium">Model:</span> Claude Sonnet 4 / Opus 4</p>
            <p>• <span className="font-medium">Gateway:</span> 4 MCP Server targets</p>
            <p>• <span className="font-medium">Memory:</span> AgentCore Memory (provisioned)</p>
          </div>
        </div>
        <div className="bg-white rounded-lg shadow border border-gray-200 p-4">
          <p className="text-xs text-gray-500 uppercase tracking-wider mb-2">Data Sources (MCP Servers)</p>
          <div className="space-y-1.5 text-xs text-gray-700">
            <p>• <span className="font-medium text-blue-700">Competitor API</span> — real-time price monitoring</p>
            <p>• <span className="font-medium text-purple-700">ERP/POS</span> — sales history, inventory, elasticity</p>
            <p>• <span className="font-medium text-teal-700">Market Signals</span> — trends, sentiment, inflation</p>
            <p>• <span className="font-medium text-amber-700">Cost & Finance</span> — COGS, margins, constraints</p>
          </div>
        </div>
        <div className="bg-white rounded-lg shadow border border-gray-200 p-4">
          <p className="text-xs text-gray-500 uppercase tracking-wider mb-2">Compliance & Governance</p>
          <div className="space-y-1.5 text-xs text-gray-700">
            <p>• <span className="font-medium">Guardrails:</span> Anti-competitive, discriminatory, predatory pricing blocked</p>
            <p>• <span className="font-medium">Audit:</span> Full decision traceability</p>
            <p>• <span className="font-medium">HITL:</span> Risk-based approval routing</p>
            <p>• <span className="font-medium">STP:</span> LOW risk auto-approved</p>
            <p>• <span className="font-medium">PII:</span> Anonymized in agent responses</p>
          </div>
        </div>
      </div>
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

      {/* Strategy Comparison */}
      <div className="bg-white rounded-lg border border-gray-200 shadow-sm p-5">
        <h3 className="text-sm font-semibold text-gray-900 mb-3">Strategy Comparison</h3>
        <p className="text-xs text-gray-600 mb-4">
          Each pricing cycle generates 3 scenarios with different strategies. Here's how they compare:
        </p>
        <div className="overflow-hidden border border-gray-200 rounded-lg">
          <table className="min-w-full divide-y divide-gray-200 text-xs">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-3 py-2 text-left font-medium text-gray-500 uppercase">Strategy</th>
                <th className="px-3 py-2 text-left font-medium text-gray-500 uppercase">Approach</th>
                <th className="px-3 py-2 text-left font-medium text-gray-500 uppercase">Risk Level</th>
                <th className="px-3 py-2 text-left font-medium text-gray-500 uppercase">Price Direction</th>
                <th className="px-3 py-2 text-left font-medium text-gray-500 uppercase">Best For</th>
                <th className="px-3 py-2 text-left font-medium text-gray-500 uppercase">Approval</th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              <tr>
                <td className="px-3 py-2 font-medium text-gray-900">Aggressive Growth</td>
                <td className="px-3 py-2 text-gray-700">Maximize revenue through higher prices where demand supports it</td>
                <td className="px-3 py-2"><span className="px-1.5 py-0.5 rounded bg-red-100 text-red-700 font-medium">HIGH</span></td>
                <td className="px-3 py-2 text-green-700 font-medium">↑ Increase</td>
                <td className="px-3 py-2 text-gray-600">Viral demand, low competition</td>
                <td className="px-3 py-2 text-gray-600">Human required (≥50 char justification)</td>
              </tr>
              <tr>
                <td className="px-3 py-2 font-medium text-gray-900">Balanced Optimization</td>
                <td className="px-3 py-2 text-gray-700">Balance revenue and margin with moderate adjustments</td>
                <td className="px-3 py-2"><span className="px-1.5 py-0.5 rounded bg-yellow-100 text-yellow-700 font-medium">MEDIUM</span></td>
                <td className="px-3 py-2 text-gray-700 font-medium">↕ Mixed</td>
                <td className="px-3 py-2 text-gray-600">Stable markets, general optimization</td>
                <td className="px-3 py-2 text-gray-600">Human review</td>
              </tr>
              <tr>
                <td className="px-3 py-2 font-medium text-gray-900">Conservative Protection</td>
                <td className="px-3 py-2 text-gray-700">Minimal, safe adjustments aligned with primary objective</td>
                <td className="px-3 py-2"><span className="px-1.5 py-0.5 rounded bg-green-100 text-green-700 font-medium">LOW</span></td>
                <td className="px-3 py-2 text-gray-700 font-medium">↕ Context-driven</td>
                <td className="px-3 py-2 text-gray-600">Safe default, STP auto-approved</td>
                <td className="px-3 py-2 text-green-700 font-medium">⚡ Auto-approved</td>
              </tr>
            </tbody>
          </table>
        </div>
        <p className="text-[10px] text-gray-500 mt-3">
          The AI generates all 3 strategies for every cycle. The system auto-approves LOW risk scenarios (straight-through processing)
          while routing MEDIUM and HIGH risk to human decision-makers with full context and rationale.
        </p>
      </div>
    </div>
  );
}

function AnalyticsTab() {
  return (
    <div>
      <FinancialMetrics />
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
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
