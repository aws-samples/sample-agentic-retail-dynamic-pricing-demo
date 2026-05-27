/**
 * SVG Architecture Diagram showing AWS services and end-to-end process flow
 * for the Dynamic Pricing for Retail solution.
 */

export default function ArchitectureDiagram() {
  return (
    <div className="bg-white rounded-lg border border-gray-200 shadow-sm p-5">
      <h3 className="text-sm font-semibold text-gray-900 mb-1">Solution Architecture</h3>
      <p className="text-[10px] text-gray-500 mb-4">End-to-end process flow with AWS services</p>

      <svg viewBox="0 0 900 520" className="w-full" xmlns="http://www.w3.org/2000/svg">
        {/* Background sections */}
        <rect x="10" y="10" width="880" height="500" rx="8" fill="#f8fafc" stroke="#e2e8f0" strokeWidth="1" />

        {/* Section: User Layer */}
        <rect x="20" y="20" width="860" height="65" rx="6" fill="#eff6ff" stroke="#bfdbfe" strokeWidth="1" />
        <text x="35" y="40" fontSize="9" fill="#1e40af" fontWeight="bold">USER LAYER</text>

        {/* Dashboard */}
        <rect x="40" y="48" width="110" height="30" rx="4" fill="white" stroke="#3b82f6" strokeWidth="1.5" />
        <text x="95" y="67" fontSize="8" fill="#1e40af" textAnchor="middle" fontWeight="600">Dashboard (React)</text>

        {/* Storefront */}
        <rect x="170" y="48" width="110" height="30" rx="4" fill="white" stroke="#3b82f6" strokeWidth="1.5" />
        <text x="225" y="67" fontSize="8" fill="#1e40af" textAnchor="middle" fontWeight="600">Storefront (React)</text>

        {/* CloudFront */}
        <rect x="310" y="48" width="100" height="30" rx="4" fill="#fef3c7" stroke="#f59e0b" strokeWidth="1.5" />
        <text x="360" y="67" fontSize="8" fill="#92400e" textAnchor="middle" fontWeight="600">CloudFront CDN</text>

        {/* Cognito */}
        <rect x="430" y="48" width="100" height="30" rx="4" fill="#fef3c7" stroke="#f59e0b" strokeWidth="1.5" />
        <text x="480" y="67" fontSize="8" fill="#92400e" textAnchor="middle" fontWeight="600">Amazon Cognito</text>

        {/* S3 */}
        <rect x="550" y="48" width="80" height="30" rx="4" fill="#fef3c7" stroke="#f59e0b" strokeWidth="1.5" />
        <text x="590" y="67" fontSize="8" fill="#92400e" textAnchor="middle" fontWeight="600">S3 Hosting</text>

        {/* Section: API Layer */}
        <rect x="20" y="95" width="860" height="60" rx="6" fill="#f0fdf4" stroke="#bbf7d0" strokeWidth="1" />
        <text x="35" y="115" fontSize="9" fill="#166534" fontWeight="bold">API LAYER</text>

        {/* API Gateway */}
        <rect x="40" y="120" width="130" height="28" rx="4" fill="white" stroke="#16a34a" strokeWidth="1.5" />
        <text x="105" y="138" fontSize="8" fill="#166534" textAnchor="middle" fontWeight="600">API Gateway (REST)</text>

        {/* Lambda */}
        <rect x="200" y="120" width="160" height="28" rx="4" fill="white" stroke="#16a34a" strokeWidth="1.5" />
        <text x="280" y="138" fontSize="8" fill="#166534" textAnchor="middle" fontWeight="600">Lambda (Thin API Wrapper)</text>

        {/* Arrow API to Lambda */}
        <line x1="170" y1="134" x2="200" y2="134" stroke="#16a34a" strokeWidth="1.5" markerEnd="url(#arrowGreen)" />

        {/* DynamoDB */}
        <rect x="400" y="120" width="120" height="28" rx="4" fill="white" stroke="#16a34a" strokeWidth="1.5" />
        <text x="460" y="138" fontSize="8" fill="#166534" textAnchor="middle" fontWeight="600">Amazon DynamoDB</text>

        {/* Arrow Lambda to DynamoDB */}
        <line x1="360" y1="134" x2="400" y2="134" stroke="#16a34a" strokeWidth="1.5" markerEnd="url(#arrowGreen)" />

        {/* DynamoDB tables */}
        <text x="545" y="128" fontSize="7" fill="#6b7280">Products • PricingCycles</text>
        <text x="545" y="140" fontSize="7" fill="#6b7280">PricingScenarios • Approvals</text>

        {/* Section: AgentCore Layer */}
        <rect x="20" y="165" width="860" height="200" rx="6" fill="#faf5ff" stroke="#e9d5ff" strokeWidth="1" />
        <text x="35" y="185" fontSize="9" fill="#6b21a8" fontWeight="bold">AMAZON BEDROCK AGENTCORE</text>

        {/* AgentCore Runtime box */}
        <rect x="40" y="195" width="380" height="155" rx="5" fill="white" stroke="#a855f7" strokeWidth="1.5" strokeDasharray="4,2" />
        <text x="55" y="212" fontSize="8" fill="#7c3aed" fontWeight="bold">AgentCore Runtime (Serverless)</text>

        {/* Orchestrator Agent */}
        <rect x="55" y="220" width="140" height="35" rx="4" fill="#ede9fe" stroke="#8b5cf6" strokeWidth="1.5" />
        <text x="125" y="237" fontSize="7.5" fill="#5b21b6" textAnchor="middle" fontWeight="700">Orchestrator Agent</text>
        <text x="125" y="249" fontSize="6.5" fill="#7c3aed" textAnchor="middle">Claude Opus 4</text>

        {/* Intelligence Agents */}
        <rect x="55" y="265" width="105" height="32" rx="4" fill="#dbeafe" stroke="#3b82f6" strokeWidth="1" />
        <text x="107" y="279" fontSize="6.5" fill="#1e40af" textAnchor="middle" fontWeight="600">Competitive Intel</text>
        <text x="107" y="290" fontSize="6" fill="#3b82f6" textAnchor="middle">Claude Sonnet 4</text>

        <rect x="170" y="265" width="105" height="32" rx="4" fill="#dbeafe" stroke="#3b82f6" strokeWidth="1" />
        <text x="222" y="279" fontSize="6.5" fill="#1e40af" textAnchor="middle" fontWeight="600">Demand Forecasting</text>
        <text x="222" y="290" fontSize="6" fill="#3b82f6" textAnchor="middle">Claude Sonnet 4</text>

        <rect x="285" y="265" width="105" height="32" rx="4" fill="#dbeafe" stroke="#3b82f6" strokeWidth="1" />
        <text x="337" y="279" fontSize="6.5" fill="#1e40af" textAnchor="middle" fontWeight="600">Market Intelligence</text>
        <text x="337" y="290" fontSize="6" fill="#3b82f6" textAnchor="middle">Claude Sonnet 4</text>

        {/* Strategy Synthesis */}
        <rect x="55" y="305" width="160" height="32" rx="4" fill="#dcfce7" stroke="#16a34a" strokeWidth="1" />
        <text x="135" y="319" fontSize="6.5" fill="#166534" textAnchor="middle" fontWeight="600">Strategy Synthesis Agent</text>
        <text x="135" y="330" fontSize="6" fill="#16a34a" textAnchor="middle">Claude Sonnet 4</text>

        {/* Implementation Monitoring */}
        <rect x="230" y="305" width="160" height="32" rx="4" fill="#fef9c3" stroke="#ca8a04" strokeWidth="1" />
        <text x="310" y="319" fontSize="6.5" fill="#854d0e" textAnchor="middle" fontWeight="600">Implementation Monitor</text>
        <text x="310" y="330" fontSize="6" fill="#ca8a04" textAnchor="middle">Claude Sonnet 4</text>

        {/* AgentCore Services */}
        <rect x="440" y="195" width="200" height="155" rx="5" fill="white" stroke="#a855f7" strokeWidth="1.5" strokeDasharray="4,2" />
        <text x="455" y="212" fontSize="8" fill="#7c3aed" fontWeight="bold">AgentCore Services</text>

        <rect x="455" y="222" width="85" height="24" rx="3" fill="#f3e8ff" stroke="#c084fc" strokeWidth="1" />
        <text x="497" y="238" fontSize="7" fill="#7c3aed" textAnchor="middle" fontWeight="600">Gateway</text>

        <rect x="550" y="222" width="75" height="24" rx="3" fill="#f3e8ff" stroke="#c084fc" strokeWidth="1" />
        <text x="587" y="238" fontSize="7" fill="#7c3aed" textAnchor="middle" fontWeight="600">Memory</text>

        <rect x="455" y="254" width="85" height="24" rx="3" fill="#f3e8ff" stroke="#c084fc" strokeWidth="1" />
        <text x="497" y="270" fontSize="7" fill="#7c3aed" textAnchor="middle" fontWeight="600">Identity</text>

        <rect x="550" y="254" width="75" height="24" rx="3" fill="#f3e8ff" stroke="#c084fc" strokeWidth="1" />
        <text x="587" y="270" fontSize="7" fill="#7c3aed" textAnchor="middle" fontWeight="600">Observability</text>

        {/* Guardrails */}
        <rect x="455" y="290" width="170" height="28" rx="3" fill="#fef2f2" stroke="#ef4444" strokeWidth="1.5" />
        <text x="540" y="305" fontSize="7" fill="#991b1b" textAnchor="middle" fontWeight="700">🛡️ Bedrock Guardrails</text>
        <text x="540" y="314" fontSize="6" fill="#dc2626" textAnchor="middle">4 Denied Topic Policies</text>

        {/* Foundation Models */}
        <rect x="455" y="325" width="170" height="22" rx="3" fill="#f0f9ff" stroke="#0ea5e9" strokeWidth="1" />
        <text x="540" y="340" fontSize="7" fill="#0c4a6e" textAnchor="middle" fontWeight="600">Foundation Models (Bedrock)</text>

        {/* MCP Servers */}
        <rect x="660" y="195" width="210" height="155" rx="5" fill="white" stroke="#f59e0b" strokeWidth="1.5" strokeDasharray="4,2" />
        <text x="675" y="212" fontSize="8" fill="#92400e" fontWeight="bold">MCP SERVERS (Lambda)</text>

        <rect x="675" y="222" width="180" height="22" rx="3" fill="#fff7ed" stroke="#fb923c" strokeWidth="1" />
        <text x="765" y="237" fontSize="7" fill="#9a3412" textAnchor="middle" fontWeight="600">🏪 Competitor API Server</text>

        <rect x="675" y="250" width="180" height="22" rx="3" fill="#fff7ed" stroke="#fb923c" strokeWidth="1" />
        <text x="765" y="265" fontSize="7" fill="#9a3412" textAnchor="middle" fontWeight="600">📊 ERP / POS Server</text>

        <rect x="675" y="278" width="180" height="22" rx="3" fill="#fff7ed" stroke="#fb923c" strokeWidth="1" />
        <text x="765" y="293" fontSize="7" fill="#9a3412" textAnchor="middle" fontWeight="600">🌐 Market Signals Server</text>

        <rect x="675" y="306" width="180" height="22" rx="3" fill="#fff7ed" stroke="#fb923c" strokeWidth="1" />
        <text x="765" y="321" fontSize="7" fill="#9a3412" textAnchor="middle" fontWeight="600">💰 Cost & Finance Server</text>

        {/* Section: Process Flow */}
        <rect x="20" y="375" width="860" height="125" rx="6" fill="#f0f9ff" stroke="#bae6fd" strokeWidth="1" />
        <text x="35" y="395" fontSize="9" fill="#0c4a6e" fontWeight="bold">END-TO-END PROCESS FLOW</text>

        {/* Flow steps */}
        <rect x="40" y="405" width="90" height="40" rx="4" fill="white" stroke="#0ea5e9" strokeWidth="1.5" />
        <text x="85" y="422" fontSize="7" fill="#0c4a6e" textAnchor="middle" fontWeight="600">1. Request</text>
        <text x="85" y="434" fontSize="6" fill="#0369a1" textAnchor="middle">Product Manager</text>

        <text x="140" y="425" fontSize="12" fill="#0ea5e9">→</text>

        <rect x="155" y="405" width="90" height="40" rx="4" fill="white" stroke="#0ea5e9" strokeWidth="1.5" />
        <text x="200" y="422" fontSize="7" fill="#0c4a6e" textAnchor="middle" fontWeight="600">2. Orchestrate</text>
        <text x="200" y="434" fontSize="6" fill="#0369a1" textAnchor="middle">Parallel agents</text>

        <text x="255" y="425" fontSize="12" fill="#0ea5e9">→</text>

        <rect x="270" y="405" width="90" height="40" rx="4" fill="white" stroke="#0ea5e9" strokeWidth="1.5" />
        <text x="315" y="422" fontSize="7" fill="#0c4a6e" textAnchor="middle" fontWeight="600">3. Gather Intel</text>
        <text x="315" y="434" fontSize="6" fill="#0369a1" textAnchor="middle">MCP Servers</text>

        <text x="370" y="425" fontSize="12" fill="#0ea5e9">→</text>

        <rect x="385" y="405" width="90" height="40" rx="4" fill="white" stroke="#0ea5e9" strokeWidth="1.5" />
        <text x="430" y="422" fontSize="7" fill="#0c4a6e" textAnchor="middle" fontWeight="600">4. Synthesize</text>
        <text x="430" y="434" fontSize="6" fill="#0369a1" textAnchor="middle">3 ranked scenarios</text>

        <text x="485" y="425" fontSize="12" fill="#0ea5e9">→</text>

        <rect x="500" y="405" width="90" height="40" rx="4" fill="white" stroke="#0ea5e9" strokeWidth="1.5" />
        <text x="545" y="422" fontSize="7" fill="#0c4a6e" textAnchor="middle" fontWeight="600">5. Guardrails</text>
        <text x="545" y="434" fontSize="6" fill="#0369a1" textAnchor="middle">Policy validation</text>

        <text x="600" y="425" fontSize="12" fill="#0ea5e9">→</text>

        <rect x="615" y="405" width="90" height="40" rx="4" fill="white" stroke="#16a34a" strokeWidth="1.5" />
        <text x="660" y="422" fontSize="7" fill="#166534" textAnchor="middle" fontWeight="600">6. Approve</text>
        <text x="660" y="434" fontSize="6" fill="#16a34a" textAnchor="middle">HITL or Auto</text>

        <text x="715" y="425" fontSize="12" fill="#16a34a">→</text>

        <rect x="730" y="405" width="90" height="40" rx="4" fill="white" stroke="#16a34a" strokeWidth="1.5" />
        <text x="775" y="422" fontSize="7" fill="#166534" textAnchor="middle" fontWeight="600">7. Implement</text>
        <text x="775" y="434" fontSize="6" fill="#16a34a" textAnchor="middle">Update prices</text>

        {/* Timing */}
        <rect x="40" y="455" width="780" height="3" rx="1.5" fill="#e0f2fe" />
        <rect x="40" y="455" width="780" height="3" rx="1.5" fill="#0ea5e9" opacity="0.6" />
        <text x="430" y="475" fontSize="8" fill="#0c4a6e" textAnchor="middle" fontWeight="bold">~55 seconds end-to-end (vs 6-10 weeks traditional)</text>

        {/* Feedback loop */}
        <path d="M 775 445 L 775 485 L 85 485 L 85 445" fill="none" stroke="#6b7280" strokeWidth="1" strokeDasharray="4,2" markerEnd="url(#arrowGray)" />
        <text x="430" y="493" fontSize="7" fill="#6b7280" textAnchor="middle">Continuous monitoring → variance detection → corrective recommendations (closed-loop)</text>

        {/* Arrow markers */}
        <defs>
          <marker id="arrowGreen" markerWidth="6" markerHeight="6" refX="5" refY="3" orient="auto">
            <path d="M0,0 L6,3 L0,6 Z" fill="#16a34a" />
          </marker>
          <marker id="arrowGray" markerWidth="6" markerHeight="6" refX="5" refY="3" orient="auto">
            <path d="M0,0 L6,3 L0,6 Z" fill="#6b7280" />
          </marker>
        </defs>
      </svg>
    </div>
  );
}
