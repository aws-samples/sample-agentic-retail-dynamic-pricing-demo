import { Link } from 'react-router-dom';
import { logout } from '../lib/cognito';
import ArchitectureDiagram from '../components/ArchitectureDiagram';

export default function ArchFlowPage() {
  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white shadow-sm border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Link to="/" className="text-sm text-blue-600 hover:text-blue-800">
              &larr; Back
            </Link>
            <h1 className="text-2xl font-semibold text-gray-900">
              Architecture &amp; Flow
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
        <div className="space-y-6">
          {/* Section 1: Solution Architecture Diagram */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
            <div className="lg:col-span-2">
              <ArchitectureDiagram />
            </div>

            {/* Section 2: How a Pricing Request is Processed */}
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
                    <p className="text-gray-500 mt-0.5">Each agent calls its MCP Server (Competitor API, ERP/POS, Market Signals, Cost &amp; Finance) via the AgentCore Gateway to gather real-time intelligence.</p>
                  </div>
                </li>
                <li className="flex gap-2">
                  <span className="flex-shrink-0 w-5 h-5 rounded-full bg-green-100 text-green-700 flex items-center justify-center text-[10px] font-bold">4</span>
                  <div>
                    <p className="font-semibold text-gray-900">Strategy Synthesis</p>
                    <p className="text-gray-500 mt-0.5">The Strategy Synthesis Agent combines all intelligence into 5 ranked pricing scenarios (Aggressive Growth, Market Share Capture, Balanced Optimization, Margin Protection, Conservative Protection), each with projected impact.</p>
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
                    <p className="font-semibold text-gray-900">Price Implementation &amp; Monitoring</p>
                    <p className="text-gray-500 mt-0.5">Approved prices are applied. The Implementation Monitor agent tracks variance and triggers corrective recommendations if actuals deviate from projections.</p>
                  </div>
                </li>
              </ol>
              <div className="mt-4 pt-3 border-t border-gray-100">
                <p className="text-[10px] text-gray-500 leading-relaxed">
                  <span className="font-semibold text-gray-700">Total time:</span> under 2 minutes end-to-end. The entire loop is closed — monitoring feeds back into future pricing decisions via AgentCore Memory.
                </p>
              </div>
            </div>
          </div>

          {/* Section 3, 4, 5: Architecture, Data Sources, Compliance */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {/* Section 3: Architecture details */}
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

            {/* Section 4: Data Sources (MCP Servers) */}
            <div className="bg-white rounded-lg shadow border border-gray-200 p-4">
              <p className="text-xs text-gray-500 uppercase tracking-wider mb-2">Data Sources (MCP Servers)</p>
              <div className="space-y-1.5 text-xs text-gray-700">
                <p>• <span className="font-medium text-blue-700">Competitor API</span> — real-time price monitoring</p>
                <p>• <span className="font-medium text-purple-700">ERP/POS</span> — sales history, inventory, elasticity</p>
                <p>• <span className="font-medium text-teal-700">Market Signals</span> — trends, sentiment, inflation</p>
                <p>• <span className="font-medium text-amber-700">Cost &amp; Finance</span> — COGS, margins, constraints</p>
              </div>
            </div>

            {/* Section 5: Compliance & Governance */}
            <div className="bg-white rounded-lg shadow border border-gray-200 p-4">
              <p className="text-xs text-gray-500 uppercase tracking-wider mb-2">Compliance &amp; Governance</p>
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
      </main>
    </div>
  );
}
