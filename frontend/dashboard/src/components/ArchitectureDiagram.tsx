/**
 * SVG Architecture Diagram following AWS reference architecture guidelines.
 * Shows the Dynamic Pricing for Retail solution architecture with grouped
 * service zones, directional flow, and AWS-style color coding.
 */

export default function ArchitectureDiagram() {
  return (
    <div className="bg-white rounded-lg border border-gray-200 shadow-sm p-5">
      <svg
        viewBox="0 0 1100 720"
        className="w-full"
        xmlns="http://www.w3.org/2000/svg"
      >
        {/* Arrow marker definitions */}
        <defs>
          <marker
            id="arrowOrange"
            markerWidth="8"
            markerHeight="8"
            refX="7"
            refY="4"
            orient="auto"
          >
            <path d="M0,0 L8,4 L0,8 Z" fill="#FF9900" />
          </marker>
          <marker
            id="arrowGray"
            markerWidth="8"
            markerHeight="8"
            refX="7"
            refY="4"
            orient="auto"
          >
            <path d="M0,0 L8,4 L0,8 Z" fill="#6B7280" />
          </marker>
        </defs>

        {/* Background */}
        <rect
          x="0"
          y="0"
          width="1100"
          height="720"
          rx="8"
          fill="#FAFBFC"
          stroke="#E2E8F0"
          strokeWidth="1"
        />

        {/* ===== Title Block (top-left) ===== */}
        <text
          x="24"
          y="28"
          fontSize="14"
          fontWeight="bold"
          fill="#232F3E"
        >
          CCOE Dynamic Pricing Solution for Retail Transformation — Architecture
        </text>
        <text
          x="24"
          y="46"
          fontSize="11"
          fill="#6B7280"
        >
          AWS Reference Architecture
        </text>

        {/* ===== Legend (top-right) ===== */}
        <g transform="translate(780, 10)">
          {/* Legend border */}
          <rect
            x="0"
            y="0"
            width="310"
            height="48"
            rx="4"
            fill="white"
            stroke="#E2E8F0"
            strokeWidth="1"
          />

          {/* Presentation Layer swatch */}
          <rect x="10" y="8" width="12" height="12" rx="2" fill="#FFF8F0" stroke="#FF9900" strokeWidth="1.5" />
          <text x="26" y="17" fontSize="7.5" fill="#4B5563">Presentation</text>

          {/* Application Layer swatch */}
          <rect x="10" y="26" width="12" height="12" rx="2" fill="#F0FFF4" stroke="#1B660F" strokeWidth="1.5" />
          <text x="26" y="35" fontSize="7.5" fill="#4B5563">Application</text>

          {/* AI/ML Layer swatch */}
          <rect x="100" y="8" width="12" height="12" rx="2" fill="#F5F0FF" stroke="#6B21A8" strokeWidth="1.5" />
          <text x="116" y="17" fontSize="7.5" fill="#4B5563">AI/ML</text>

          {/* Integration Layer swatch */}
          <rect x="100" y="26" width="12" height="12" rx="2" fill="#FFF9E6" stroke="#D97706" strokeWidth="1.5" />
          <text x="116" y="35" fontSize="7.5" fill="#4B5563">Integration</text>

          {/* Process Flow swatch */}
          <rect x="180" y="8" width="12" height="12" rx="2" fill="#F0F8FF" stroke="#0073BB" strokeWidth="1.5" />
          <text x="196" y="17" fontSize="7.5" fill="#4B5563">Process Flow</text>

          {/* Arrow direction indicator */}
          <line x1="185" y1="32" x2="205" y2="32" stroke="#FF9900" strokeWidth="1.5" markerEnd="url(#arrowOrange)" />
          <text x="212" y="35" fontSize="7.5" fill="#4B5563">Data flow</text>
        </g>

        {/* ===== Layer Zones (implemented in tasks 4.2–4.5) ===== */}

        {/* ===== Presentation Layer Zone ===== */}
        <g>
          {/* Zone box */}
          <rect
            x="20"
            y="60"
            width="1060"
            height="80"
            rx="6"
            fill="#FFF8F0"
            stroke="#FF9900"
            strokeWidth="1.5"
          />
          {/* Zone label */}
          <text x="32" y="76" fontSize="10" fontWeight="bold" fill="#8B5E00">
            Presentation Layer
          </text>

          {/* Node: Amazon CloudFront */}
          <rect x="40" y="86" width="180" height="44" rx="6" fill="white" stroke="#FF9900" strokeWidth="1" />
          <text x="130" y="104" fontSize="10" fontWeight="bold" fill="#8B5E00" textAnchor="middle">
            Amazon CloudFront
          </text>
          <text x="130" y="118" fontSize="8.5" fill="#92400E" textAnchor="middle">
            CDN
          </text>

          {/* Node: Amazon S3 */}
          <rect x="236" y="86" width="180" height="44" rx="6" fill="white" stroke="#FF9900" strokeWidth="1" />
          <text x="326" y="104" fontSize="10" fontWeight="bold" fill="#8B5E00" textAnchor="middle">
            Amazon S3
          </text>
          <text x="326" y="118" fontSize="8.5" fill="#92400E" textAnchor="middle">
            Static Hosting
          </text>

          {/* Node: Amazon Cognito */}
          <rect x="432" y="86" width="180" height="44" rx="6" fill="white" stroke="#FF9900" strokeWidth="1" />
          <text x="522" y="104" fontSize="10" fontWeight="bold" fill="#8B5E00" textAnchor="middle">
            Amazon Cognito
          </text>
          <text x="522" y="118" fontSize="8.5" fill="#92400E" textAnchor="middle">
            Auth
          </text>

          {/* Node: Dashboard */}
          <rect x="628" y="86" width="180" height="44" rx="6" fill="white" stroke="#FF9900" strokeWidth="1" />
          <text x="718" y="104" fontSize="10" fontWeight="bold" fill="#8B5E00" textAnchor="middle">
            Dashboard
          </text>
          <text x="718" y="118" fontSize="8.5" fill="#92400E" textAnchor="middle">
            React SPA
          </text>

          {/* Node: Storefront */}
          <rect x="824" y="86" width="180" height="44" rx="6" fill="white" stroke="#FF9900" strokeWidth="1" />
          <text x="914" y="104" fontSize="10" fontWeight="bold" fill="#8B5E00" textAnchor="middle">
            Storefront
          </text>
          <text x="914" y="118" fontSize="8.5" fill="#92400E" textAnchor="middle">
            React SPA
          </text>
        </g>

        {/* Application Layer zone — Task 4.3 */}
        <g>
          {/* Zone box */}
          <rect
            x="20"
            y="160"
            width="1060"
            height="90"
            rx="6"
            fill="#F0FFF4"
            stroke="#1B660F"
            strokeWidth="1.5"
          />
          {/* Zone label */}
          <text x="32" y="178" fontSize="10" fontWeight="bold" fill="#1B660F">
            Application Layer
          </text>

          {/* Amazon API Gateway node */}
          <rect x="80" y="188" width="200" height="50" rx="6" fill="white" stroke="#1B660F" strokeWidth="1" />
          <text x="180" y="210" fontSize="10" fontWeight="bold" fill="#1B660F" textAnchor="middle">
            Amazon API Gateway
          </text>
          <text x="180" y="224" fontSize="9" fill="#1B660F" textAnchor="middle">
            REST API
          </text>

          {/* AWS Lambda node */}
          <rect x="340" y="188" width="200" height="50" rx="6" fill="white" stroke="#1B660F" strokeWidth="1" />
          <text x="440" y="210" fontSize="10" fontWeight="bold" fill="#1B660F" textAnchor="middle">
            AWS Lambda
          </text>
          <text x="440" y="224" fontSize="9" fill="#1B660F" textAnchor="middle">
            API Handlers
          </text>

          {/* Amazon DynamoDB node */}
          <rect x="600" y="188" width="280" height="50" rx="6" fill="white" stroke="#1B660F" strokeWidth="1" />
          <text x="740" y="210" fontSize="10" fontWeight="bold" fill="#1B660F" textAnchor="middle">
            Amazon DynamoDB
          </text>
          <text x="740" y="224" fontSize="9" fill="#1B660F" textAnchor="middle">
            Products, Cycles, Scenarios, Approvals
          </text>
        </g>

        {/* Directional arrows: Presentation Layer → Application Layer */}
        <line x1="250" y1="142" x2="250" y2="158" stroke="#FF9900" strokeWidth="1.5" markerEnd="url(#arrowOrange)" />
        <line x1="550" y1="142" x2="550" y2="158" stroke="#FF9900" strokeWidth="1.5" markerEnd="url(#arrowOrange)" />
        <line x1="850" y1="142" x2="850" y2="158" stroke="#FF9900" strokeWidth="1.5" markerEnd="url(#arrowOrange)" />

        {/* Directional arrows: Application Layer → AI/ML Layer */}
        <line x1="250" y1="252" x2="250" y2="268" stroke="#FF9900" strokeWidth="1.5" markerEnd="url(#arrowOrange)" />
        <line x1="550" y1="252" x2="550" y2="268" stroke="#FF9900" strokeWidth="1.5" markerEnd="url(#arrowOrange)" />
        <line x1="850" y1="252" x2="850" y2="268" stroke="#FF9900" strokeWidth="1.5" markerEnd="url(#arrowOrange)" />

        {/* ===== AI/ML Layer Zone ===== */}
        <g>
          {/* Zone box */}
          <rect
            x="20"
            y="270"
            width="1060"
            height="210"
            rx="6"
            fill="#F5F0FF"
            stroke="#6B21A8"
            strokeWidth="1.5"
          />
          {/* Zone label */}
          <text x="32" y="288" fontSize="10" fontWeight="bold" fill="#6B21A8">
            AI/ML Layer
          </text>

          {/* --- AgentCore Runtime sub-group --- */}
          <rect
            x="32"
            y="296"
            width="680"
            height="130"
            rx="4"
            fill="none"
            stroke="#6B21A8"
            strokeWidth="1"
            strokeDasharray="4,2"
          />
          <text x="44" y="310" fontSize="9" fontWeight="bold" fill="#6B21A8">
            AgentCore Runtime
          </text>

          {/* Orchestrator Agent (larger/prominent) */}
          <rect x="44" y="316" width="200" height="48" rx="6" fill="white" stroke="#6B21A8" strokeWidth="1.2" />
          <text x="144" y="336" fontSize="10" fontWeight="bold" fill="#6B21A8" textAnchor="middle">
            Orchestrator Agent
          </text>
          <text x="144" y="350" fontSize="8.5" fill="#7C3AED" textAnchor="middle">
            Claude Opus 4
          </text>

          {/* Competitive Intel Agent */}
          <rect x="256" y="316" width="148" height="44" rx="6" fill="white" stroke="#6B21A8" strokeWidth="1" />
          <text x="330" y="334" fontSize="9" fontWeight="bold" fill="#6B21A8" textAnchor="middle">
            Competitive Intel Agent
          </text>
          <text x="330" y="348" fontSize="8" fill="#7C3AED" textAnchor="middle">
            Claude Sonnet 4
          </text>

          {/* Demand Forecasting Agent */}
          <rect x="416" y="316" width="148" height="44" rx="6" fill="white" stroke="#6B21A8" strokeWidth="1" />
          <text x="490" y="334" fontSize="9" fontWeight="bold" fill="#6B21A8" textAnchor="middle">
            Demand Forecasting Agent
          </text>
          <text x="490" y="348" fontSize="8" fill="#7C3AED" textAnchor="middle">
            Claude Sonnet 4
          </text>

          {/* Market Intelligence Agent */}
          <rect x="576" y="316" width="126" height="44" rx="6" fill="white" stroke="#6B21A8" strokeWidth="1" />
          <text x="639" y="334" fontSize="8.5" fontWeight="bold" fill="#6B21A8" textAnchor="middle">
            Market Intelligence
          </text>
          <text x="639" y="348" fontSize="8" fill="#7C3AED" textAnchor="middle">
            Claude Sonnet 4
          </text>

          {/* Strategy Synthesis Agent */}
          <rect x="44" y="372" width="168" height="44" rx="6" fill="white" stroke="#6B21A8" strokeWidth="1" />
          <text x="128" y="390" fontSize="9" fontWeight="bold" fill="#6B21A8" textAnchor="middle">
            Strategy Synthesis Agent
          </text>
          <text x="128" y="404" fontSize="8" fill="#7C3AED" textAnchor="middle">
            Claude Sonnet 4
          </text>

          {/* Implementation Monitor Agent */}
          <rect x="224" y="372" width="180" height="44" rx="6" fill="white" stroke="#6B21A8" strokeWidth="1" />
          <text x="314" y="390" fontSize="9" fontWeight="bold" fill="#6B21A8" textAnchor="middle">
            Implementation Monitor Agent
          </text>
          <text x="314" y="404" fontSize="8" fill="#7C3AED" textAnchor="middle">
            Claude Sonnet 4
          </text>

          {/* --- AgentCore Services sub-group --- */}
          <rect
            x="32"
            y="432"
            width="680"
            height="40"
            rx="4"
            fill="none"
            stroke="#6B21A8"
            strokeWidth="1"
            strokeDasharray="4,2"
          />
          <text x="44" y="446" fontSize="9" fontWeight="bold" fill="#6B21A8">
            AgentCore Services
          </text>

          {/* Gateway */}
          <rect x="170" y="436" width="100" height="30" rx="6" fill="white" stroke="#6B21A8" strokeWidth="1" />
          <text x="220" y="455" fontSize="9" fontWeight="bold" fill="#6B21A8" textAnchor="middle">
            Gateway
          </text>

          {/* Memory */}
          <rect x="282" y="436" width="100" height="30" rx="6" fill="white" stroke="#6B21A8" strokeWidth="1" />
          <text x="332" y="455" fontSize="9" fontWeight="bold" fill="#6B21A8" textAnchor="middle">
            Memory
          </text>

          {/* Identity */}
          <rect x="394" y="436" width="100" height="30" rx="6" fill="white" stroke="#6B21A8" strokeWidth="1" />
          <text x="444" y="455" fontSize="9" fontWeight="bold" fill="#6B21A8" textAnchor="middle">
            Identity
          </text>

          {/* Observability */}
          <rect x="506" y="436" width="110" height="30" rx="6" fill="white" stroke="#6B21A8" strokeWidth="1" />
          <text x="561" y="455" fontSize="9" fontWeight="bold" fill="#6B21A8" textAnchor="middle">
            Observability
          </text>

          {/* --- Amazon Bedrock Guardrails --- */}
          <rect x="730" y="296" width="200" height="60" rx="6" fill="white" stroke="#6B21A8" strokeWidth="1.2" />
          <text x="830" y="318" fontSize="9.5" fontWeight="bold" fill="#6B21A8" textAnchor="middle">
            Amazon Bedrock Guardrails
          </text>
          <text x="830" y="334" fontSize="8" fill="#7C3AED" textAnchor="middle">
            4 Denied Topic Policies
          </text>

          {/* --- Amazon Bedrock Foundation Models --- */}
          <rect x="730" y="368" width="200" height="50" rx="6" fill="white" stroke="#6B21A8" strokeWidth="1.2" />
          <text x="830" y="390" fontSize="9.5" fontWeight="bold" fill="#6B21A8" textAnchor="middle">
            Amazon Bedrock
          </text>
          <text x="830" y="404" fontSize="8" fill="#7C3AED" textAnchor="middle">
            Foundation Models
          </text>
        </g>

        {/* ===== Directional arrows: AI/ML Layer → Integration Layer ===== */}
        <line x1="250" y1="482" x2="250" y2="498" stroke="#FF9900" strokeWidth="1.5" markerEnd="url(#arrowOrange)" />
        <line x1="550" y1="482" x2="550" y2="498" stroke="#FF9900" strokeWidth="1.5" markerEnd="url(#arrowOrange)" />
        <line x1="850" y1="482" x2="850" y2="498" stroke="#FF9900" strokeWidth="1.5" markerEnd="url(#arrowOrange)" />

        {/* ===== Integration Layer Zone ===== */}
        <g>
          {/* Zone box */}
          <rect
            x="20"
            y="500"
            width="1060"
            height="80"
            rx="6"
            fill="#FFF9E6"
            stroke="#D97706"
            strokeWidth="1.5"
          />
          {/* Zone label */}
          <text x="32" y="516" fontSize="10" fontWeight="bold" fill="#92400E">
            Integration Layer
          </text>

          {/* Competitor API MCP Server */}
          <rect x="40" y="524" width="240" height="44" rx="6" fill="white" stroke="#D97706" strokeWidth="1" />
          <text x="160" y="542" fontSize="9.5" fontWeight="bold" fill="#92400E" textAnchor="middle">
            Competitor API MCP Server
          </text>
          <text x="160" y="556" fontSize="8.5" fill="#B45309" textAnchor="middle">
            Lambda
          </text>

          {/* ERP/POS MCP Server */}
          <rect x="296" y="524" width="240" height="44" rx="6" fill="white" stroke="#D97706" strokeWidth="1" />
          <text x="416" y="542" fontSize="9.5" fontWeight="bold" fill="#92400E" textAnchor="middle">
            ERP/POS MCP Server
          </text>
          <text x="416" y="556" fontSize="8.5" fill="#B45309" textAnchor="middle">
            Lambda
          </text>

          {/* Market Signals MCP Server */}
          <rect x="552" y="524" width="240" height="44" rx="6" fill="white" stroke="#D97706" strokeWidth="1" />
          <text x="672" y="542" fontSize="9.5" fontWeight="bold" fill="#92400E" textAnchor="middle">
            Market Signals MCP Server
          </text>
          <text x="672" y="556" fontSize="8.5" fill="#B45309" textAnchor="middle">
            Lambda
          </text>

          {/* Cost & Finance MCP Server */}
          <rect x="808" y="524" width="240" height="44" rx="6" fill="white" stroke="#D97706" strokeWidth="1" />
          <text x="928" y="542" fontSize="9.5" fontWeight="bold" fill="#92400E" textAnchor="middle">
            Cost &amp; Finance MCP Server
          </text>
          <text x="928" y="556" fontSize="8.5" fill="#B45309" textAnchor="middle">
            Lambda
          </text>
        </g>

        {/* ===== Directional arrows: Integration Layer → Process Flow ===== */}
        <line x1="250" y1="582" x2="250" y2="598" stroke="#FF9900" strokeWidth="1.5" markerEnd="url(#arrowOrange)" />
        <line x1="550" y1="582" x2="550" y2="598" stroke="#FF9900" strokeWidth="1.5" markerEnd="url(#arrowOrange)" />
        <line x1="850" y1="582" x2="850" y2="598" stroke="#FF9900" strokeWidth="1.5" markerEnd="url(#arrowOrange)" />

        {/* ===== End-to-End Process Flow Zone ===== */}
        <g>
          {/* Zone box */}
          <rect
            x="20"
            y="600"
            width="1060"
            height="110"
            rx="6"
            fill="#F0F8FF"
            stroke="#0073BB"
            strokeWidth="1.5"
          />
          {/* Zone label */}
          <text x="32" y="616" fontSize="10" fontWeight="bold" fill="#0073BB">
            End-to-End Process Flow
          </text>

          {/* Step 1: Request */}
          <rect x="32" y="624" width="130" height="38" rx="6" fill="white" stroke="#0073BB" strokeWidth="1" />
          <text x="97" y="639" fontSize="8" fontWeight="bold" fill="#0073BB" textAnchor="middle">
            1. Request
          </text>
          <text x="97" y="651" fontSize="7" fill="#1E40AF" textAnchor="middle">
            Product Manager
          </text>

          {/* Arrow 1→2 */}
          <line x1="164" y1="643" x2="176" y2="643" stroke="#0073BB" strokeWidth="1" markerEnd="url(#arrowGray)" />

          {/* Step 2: Orchestrate */}
          <rect x="178" y="624" width="130" height="38" rx="6" fill="white" stroke="#0073BB" strokeWidth="1" />
          <text x="243" y="639" fontSize="8" fontWeight="bold" fill="#0073BB" textAnchor="middle">
            2. Orchestrate
          </text>
          <text x="243" y="651" fontSize="7" fill="#1E40AF" textAnchor="middle">
            Parallel agents
          </text>

          {/* Arrow 2→3 */}
          <line x1="310" y1="643" x2="322" y2="643" stroke="#0073BB" strokeWidth="1" markerEnd="url(#arrowGray)" />

          {/* Step 3: Gather Intel */}
          <rect x="324" y="624" width="130" height="38" rx="6" fill="white" stroke="#0073BB" strokeWidth="1" />
          <text x="389" y="639" fontSize="8" fontWeight="bold" fill="#0073BB" textAnchor="middle">
            3. Gather Intel
          </text>
          <text x="389" y="651" fontSize="7" fill="#1E40AF" textAnchor="middle">
            MCP Servers
          </text>

          {/* Arrow 3→4 */}
          <line x1="456" y1="643" x2="468" y2="643" stroke="#0073BB" strokeWidth="1" markerEnd="url(#arrowGray)" />

          {/* Step 4: Synthesize */}
          <rect x="470" y="624" width="130" height="38" rx="6" fill="white" stroke="#0073BB" strokeWidth="1" />
          <text x="535" y="639" fontSize="8" fontWeight="bold" fill="#0073BB" textAnchor="middle">
            4. Synthesize
          </text>
          <text x="535" y="651" fontSize="7" fill="#1E40AF" textAnchor="middle">
            5 ranked scenarios
          </text>

          {/* Arrow 4→5 */}
          <line x1="602" y1="643" x2="614" y2="643" stroke="#0073BB" strokeWidth="1" markerEnd="url(#arrowGray)" />

          {/* Step 5: Guardrails */}
          <rect x="616" y="624" width="130" height="38" rx="6" fill="white" stroke="#0073BB" strokeWidth="1" />
          <text x="681" y="639" fontSize="8" fontWeight="bold" fill="#0073BB" textAnchor="middle">
            5. Guardrails
          </text>
          <text x="681" y="651" fontSize="7" fill="#1E40AF" textAnchor="middle">
            Policy validation
          </text>

          {/* Arrow 5→6 */}
          <line x1="748" y1="643" x2="760" y2="643" stroke="#0073BB" strokeWidth="1" markerEnd="url(#arrowGray)" />

          {/* Step 6: Approve */}
          <rect x="762" y="624" width="130" height="38" rx="6" fill="white" stroke="#0073BB" strokeWidth="1" />
          <text x="827" y="639" fontSize="8" fontWeight="bold" fill="#0073BB" textAnchor="middle">
            6. Approve
          </text>
          <text x="827" y="651" fontSize="7" fill="#1E40AF" textAnchor="middle">
            HITL or Auto
          </text>

          {/* Arrow 6→7 */}
          <line x1="894" y1="643" x2="906" y2="643" stroke="#0073BB" strokeWidth="1" markerEnd="url(#arrowGray)" />

          {/* Step 7: Implement */}
          <rect x="908" y="624" width="130" height="38" rx="6" fill="white" stroke="#0073BB" strokeWidth="1" />
          <text x="973" y="639" fontSize="8" fontWeight="bold" fill="#0073BB" textAnchor="middle">
            7. Implement
          </text>
          <text x="973" y="651" fontSize="7" fill="#1E40AF" textAnchor="middle">
            Update prices
          </text>

          {/* Timing bar */}
          <text x="550" y="680" fontSize="9" fill="#0073BB" textAnchor="middle" fontStyle="italic">
            {'< 2 minutes end-to-end (vs 6-10 weeks traditional)'}
          </text>

          {/* Feedback loop: dashed line from step 7 back to step 1 */}
          <path
            d="M 973 664 L 973 694 L 97 694 L 97 664"
            fill="none"
            stroke="#6B7280"
            strokeWidth="1"
            strokeDasharray="4,3"
            markerEnd="url(#arrowGray)"
          />
          <text x="535" y="703" fontSize="7.5" fill="#6B7280" textAnchor="middle">
            Continuous feedback loop
          </text>
        </g>
      </svg>
    </div>
  );
}
