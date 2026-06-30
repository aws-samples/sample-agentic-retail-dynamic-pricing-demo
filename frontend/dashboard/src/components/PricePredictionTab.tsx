import { useState } from "react";

interface SubComponent {
  name: string;
  rawValue: string;
  meaning: string;
  normalizedScore: number;
  dataSource: string;
}

interface Factor {
  id: string;
  name: string;
  score: number;
  weight: number;
  explanation: string;
  formula: string;
  components: SubComponent[];
  calculation: string;
}

interface Product {
  id: string;
  name: string;
  basePrice: number;
  recommendedPrice: number;
  confidence: number;
  riskLevel: "Low" | "Medium" | "High";
  revenueImpact: string;
}

const products: Product[] = [
  {
    id: "earbuds",
    name: "ProSound Wireless Earbuds",
    basePrice: 79.99,
    recommendedPrice: 74.99,
    confidence: 87,
    riskLevel: "Low",
    revenueImpact: "+4.2% projected revenue increase",
  },
  {
    id: "smartwatch",
    name: "FitTrack Pro Smartwatch",
    basePrice: 199.99,
    recommendedPrice: 189.99,
    confidence: 82,
    riskLevel: "Medium",
    revenueImpact: "+6.8% projected revenue increase",
  },
  {
    id: "vacuum",
    name: "CleanForce Cordless Stick Vacuum",
    basePrice: 299.99,
    recommendedPrice: 284.99,
    confidence: 79,
    riskLevel: "Medium",
    revenueImpact: "+3.1% projected revenue increase",
  },
  {
    id: "milk",
    name: "Farm Fresh Whole Milk",
    basePrice: 4.49,
    recommendedPrice: 4.29,
    confidence: 91,
    riskLevel: "Low",
    revenueImpact: "+2.5% projected revenue increase",
  },
  {
    id: "coffee",
    name: "Mountain Roast Premium Coffee",
    basePrice: 12.99,
    recommendedPrice: 11.99,
    confidence: 85,
    riskLevel: "Low",
    revenueImpact: "+5.3% projected revenue increase",
  },
];

const factors: Factor[] = [
  {
    id: "competitive",
    name: "Competitive Pressure",
    score: 0.72,
    weight: 30,
    explanation:
      "Measures how aggressively competitors are pricing similar products. A score of 0.72 indicates moderate competitive pressure — competitors are pricing slightly below your current price, suggesting a price adjustment may capture more market share.",
    formula:
      "Score = (Avg Competitor Price Gap × 0.4) + (Price Position Rank × 0.35) + (Competitor Activity Index × 0.25)",
    components: [
      {
        name: "Avg Competitor Price Gap",
        rawValue: "-6.2%",
        meaning:
          "Competitors are priced 6.2% below your current price on average",
        normalizedScore: 0.68,
        dataSource: "Real-time price scraping (updated every 4 hours)",
      },
      {
        name: "Price Position Rank",
        rawValue: "4th of 7",
        meaning:
          "Your product is the 4th cheapest among 7 tracked competitors",
        normalizedScore: 0.57,
        dataSource: "Competitive intelligence platform",
      },
      {
        name: "Competitor Activity Index",
        rawValue: "3 changes/week",
        meaning:
          "Competitors changed prices 3 times in the past week, indicating active repricing",
        normalizedScore: 0.91,
        dataSource: "Historical price tracking database",
      },
    ],
    calculation:
      "(0.68 × 0.4) + (0.57 × 0.35) + (0.91 × 0.25) = 0.272 + 0.200 + 0.228 = 0.72",
  },
  {
    id: "demand",
    name: "Demand Signal",
    score: 0.85,
    weight: 35,
    explanation:
      "Captures current and predicted customer demand intensity. A score of 0.85 indicates strong demand signals — search volume and add-to-cart rates are trending upward, suggesting customers are actively seeking this product.",
    formula:
      "Score = (Search Volume Trend × 0.45) + (Cart Abandonment Inverse × 0.30) + (Seasonality Factor × 0.25)",
    components: [
      {
        name: "Search Volume Trend",
        rawValue: "+23% MoM",
        meaning:
          "Product search volume increased 23% month-over-month, indicating growing interest",
        normalizedScore: 0.89,
        dataSource: "Site analytics and search logs",
      },
      {
        name: "Cart Abandonment Inverse",
        rawValue: "32% abandonment",
        meaning:
          "68% of users who add to cart complete purchase — strong conversion signal",
        normalizedScore: 0.78,
        dataSource: "E-commerce conversion funnel data",
      },
      {
        name: "Seasonality Factor",
        rawValue: "Peak period",
        meaning:
          "Current period aligns with historical peak demand for this category",
        normalizedScore: 0.88,
        dataSource: "3-year historical sales data",
      },
    ],
    calculation:
      "(0.89 × 0.45) + (0.78 × 0.30) + (0.88 × 0.25) = 0.401 + 0.234 + 0.220 = 0.85",
  },
  {
    id: "margin",
    name: "Margin Constraint",
    score: 0.6,
    weight: 20,
    explanation:
      "Evaluates the pricing floor based on cost structure and minimum acceptable profit margins. A score of 0.60 indicates moderate margin flexibility — there is room to adjust price downward while maintaining acceptable profitability.",
    formula:
      "Score = (Current Margin Headroom × 0.50) + (COGS Stability × 0.30) + (MAP Compliance × 0.20)",
    components: [
      {
        name: "Current Margin Headroom",
        rawValue: "34% gross margin",
        meaning:
          "Current gross margin is 34%, with floor at 22% — leaving 12 percentage points of flexibility",
        normalizedScore: 0.55,
        dataSource: "Internal P&L and cost accounting system",
      },
      {
        name: "COGS Stability",
        rawValue: "+1.2% QoQ",
        meaning:
          "Cost of goods sold increased only 1.2% quarter-over-quarter — stable supply costs",
        normalizedScore: 0.72,
        dataSource: "Procurement and supply chain data",
      },
      {
        name: "MAP Compliance",
        rawValue: "Above MAP",
        meaning:
          "Recommended price remains above Minimum Advertised Price — no vendor conflict",
        normalizedScore: 0.53,
        dataSource: "Vendor agreement database",
      },
    ],
    calculation:
      "(0.55 × 0.50) + (0.72 × 0.30) + (0.53 × 0.20) = 0.275 + 0.216 + 0.106 = 0.60",
  },
  {
    id: "market",
    name: "Market Intelligence",
    score: 0.45,
    weight: 15,
    explanation:
      "Incorporates external market signals and broader economic indicators. A score of 0.45 indicates mixed market signals — while category growth is positive, consumer confidence is softening, warranting a cautious pricing approach.",
    formula:
      "Score = (Category Growth Rate × 0.40) + (Consumer Sentiment Index × 0.35) + (Economic Indicator × 0.25)",
    components: [
      {
        name: "Category Growth Rate",
        rawValue: "+8% YoY",
        meaning:
          "Product category is growing 8% year-over-year — healthy market expansion",
        normalizedScore: 0.62,
        dataSource: "Industry analyst reports and market research",
      },
      {
        name: "Consumer Sentiment Index",
        rawValue: "62/100",
        meaning:
          "Consumer confidence is below average at 62/100, suggesting price sensitivity is elevated",
        normalizedScore: 0.35,
        dataSource: "Consumer surveys and economic indicators",
      },
      {
        name: "Economic Indicator",
        rawValue: "Neutral",
        meaning:
          "Macroeconomic conditions are neutral — neither strongly supporting nor hindering demand",
        normalizedScore: 0.38,
        dataSource: "Federal economic data and forecasting models",
      },
    ],
    calculation:
      "(0.62 × 0.40) + (0.35 × 0.35) + (0.38 × 0.25) = 0.248 + 0.123 + 0.095 = 0.45",
  },
];

interface GlossaryTerm {
  term: string;
  definition: string;
}

const glossary: GlossaryTerm[] = [
  {
    term: "Elasticity",
    definition:
      "A measure of how much demand for a product changes when its price changes. High elasticity means small price changes cause large demand shifts.",
  },
  {
    term: "COGS",
    definition:
      "Cost of Goods Sold — the direct costs attributable to producing the goods sold, including materials, labor, and manufacturing overhead.",
  },
  {
    term: "MAP",
    definition:
      "Minimum Advertised Price — the lowest price a retailer can advertise a product for, set by the manufacturer to protect brand value.",
  },
  {
    term: "Margin",
    definition:
      "The difference between the selling price and cost, expressed as a percentage of the selling price. Gross margin excludes operating expenses.",
  },
  {
    term: "MoM Trend",
    definition:
      "Month-over-Month Trend — the percentage change in a metric compared to the previous month, used to identify short-term momentum.",
  },
  {
    term: "Seasonality",
    definition:
      "Predictable fluctuations in demand that occur at regular intervals (weekly, monthly, annually) based on time-related patterns.",
  },
  {
    term: "Price Sensitivity",
    definition:
      "The degree to which consumers alter their purchasing behavior in response to price changes. Higher sensitivity means customers are more likely to switch or stop buying.",
  },
];

function ScoreBar({ score, color }: { score: number; color: string }) {
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-2 bg-gray-100 rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full ${color}`}
          style={{ width: `${score * 100}%` }}
        />
      </div>
      <span className="text-xs font-medium text-gray-600 w-10 text-right">
        {(score * 100).toFixed(0)}%
      </span>
    </div>
  );
}

function FactorCard({ factor }: { factor: Factor }) {
  const [expanded, setExpanded] = useState(false);

  const getScoreColor = (score: number) => {
    if (score >= 0.7) return "bg-emerald-500";
    if (score >= 0.5) return "bg-amber-500";
    return "bg-red-400";
  };

  return (
    <div className="bg-white rounded-lg border border-gray-200 shadow-sm overflow-hidden">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full px-4 py-3 flex items-center justify-between hover:bg-gray-50 transition-colors"
        aria-expanded={expanded}
        aria-label={`${factor.name} factor details`}
      >
        <div className="flex items-center gap-3">
          <div
            className={`w-2 h-2 rounded-full ${getScoreColor(factor.score)}`}
          />
          <span className="text-sm font-medium text-gray-900">
            {factor.name}
          </span>
          <span className="text-xs text-gray-500">
            (weight: {factor.weight}%)
          </span>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-sm font-semibold text-gray-700">
            {factor.score.toFixed(2)}
          </span>
          <svg
            className={`w-4 h-4 text-gray-400 transition-transform ${
              expanded ? "rotate-180" : ""
            }`}
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M19 9l-7 7-7-7"
            />
          </svg>
        </div>
      </button>

      {expanded && (
        <div className="px-4 pb-4 border-t border-gray-100">
          <div className="mt-3 space-y-4">
            <div>
              <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1">
                Explanation
              </h4>
              <p className="text-sm text-gray-700 leading-relaxed">
                {factor.explanation}
              </p>
            </div>

            <div>
              <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1">
                Formula
              </h4>
              <code className="text-xs bg-gray-50 text-gray-800 px-2 py-1 rounded block">
                {factor.formula}
              </code>
            </div>

            <div>
              <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">
                Component Breakdown
              </h4>
              <div className="space-y-3">
                {factor.components.map((comp) => (
                  <div
                    key={comp.name}
                    className="bg-gray-50 rounded-md p-3 space-y-1"
                  >
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-medium text-gray-900">
                        {comp.name}
                      </span>
                      <span className="text-xs font-mono text-indigo-600">
                        {comp.rawValue}
                      </span>
                    </div>
                    <p className="text-xs text-gray-600">{comp.meaning}</p>
                    <div className="flex items-center justify-between pt-1">
                      <ScoreBar
                        score={comp.normalizedScore}
                        color={getScoreColor(comp.normalizedScore)}
                      />
                    </div>
                    <p className="text-xs text-gray-400 italic">
                      Source: {comp.dataSource}
                    </p>
                  </div>
                ))}
              </div>
            </div>

            <div>
              <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1">
                Final Calculation
              </h4>
              <code className="text-xs bg-indigo-50 text-indigo-800 px-2 py-1 rounded block">
                {factor.calculation}
              </code>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function PricePredictionTab() {
  const [selectedProductId, setSelectedProductId] = useState<string>("");
  const [showResults, setShowResults] = useState(false);
  const [isSimulating, setIsSimulating] = useState(false);

  const selectedProduct = products.find((p) => p.id === selectedProductId);

  const handleSimulate = () => {
    if (!selectedProductId) return;
    setIsSimulating(true);
    setTimeout(() => {
      setIsSimulating(false);
      setShowResults(true);
    }, 800);
  };

  const getRiskColor = (risk: string) => {
    switch (risk) {
      case "Low":
        return "bg-emerald-100 text-emerald-800";
      case "Medium":
        return "bg-amber-100 text-amber-800";
      case "High":
        return "bg-red-100 text-red-800";
      default:
        return "bg-gray-100 text-gray-800";
    }
  };

  const weightedScore = factors.reduce(
    (sum, f) => sum + f.score * (f.weight / 100),
    0
  );

  return (
    <div className="space-y-6">
      <div className="bg-white rounded-lg border border-gray-200 shadow-sm p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-1">
          Price Prediction Simulator
        </h2>
        <p className="text-sm text-gray-500 mb-4">
          Explore how AI pricing recommendations are derived through a
          multi-factor decision tree with full explainability.
        </p>

        <div className="flex items-end gap-3">
          <div className="flex-1">
            <label
              htmlFor="product-select"
              className="block text-xs font-medium text-gray-700 mb-1"
            >
              Select Product
            </label>
            <select
              id="product-select"
              value={selectedProductId}
              onChange={(e) => {
                setSelectedProductId(e.target.value);
                setShowResults(false);
              }}
              className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
            >
              <option value="">Choose a product...</option>
              {products.map((product) => (
                <option key={product.id} value={product.id}>
                  {product.name} — ${product.basePrice.toFixed(2)}
                </option>
              ))}
            </select>
          </div>
          <button
            onClick={handleSimulate}
            disabled={!selectedProductId || isSimulating}
            className="px-4 py-2 bg-indigo-600 text-white text-sm font-medium rounded-md hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {isSimulating ? (
              <span className="flex items-center gap-2">
                <svg
                  className="animate-spin h-4 w-4"
                  viewBox="0 0 24 24"
                  fill="none"
                >
                  <circle
                    className="opacity-25"
                    cx="12"
                    cy="12"
                    r="10"
                    stroke="currentColor"
                    strokeWidth="4"
                  />
                  <path
                    className="opacity-75"
                    fill="currentColor"
                    d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
                  />
                </svg>
                Simulating...
              </span>
            ) : (
              "Simulate"
            )}
          </button>
        </div>
      </div>

      {showResults && selectedProduct && (
        <>
          <div className="bg-white rounded-lg border border-gray-200 shadow-sm p-6">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-sm font-semibold text-gray-900">
                Decision Tree — Factor Scores
              </h3>
              <div className="text-xs text-gray-500">
                Weighted Score:{" "}
                <span className="font-semibold text-indigo-600">
                  {weightedScore.toFixed(3)}
                </span>
              </div>
            </div>
            <p className="text-xs text-gray-500 mb-4">
              Click each factor to expand and see the full explanation, formula,
              and component breakdown.
            </p>
            <div className="space-y-2">
              {factors.map((factor) => (
                <FactorCard key={factor.id} factor={factor} />
              ))}
            </div>
          </div>

          <div className="bg-white rounded-lg border border-gray-200 shadow-sm p-6">
            <h3 className="text-sm font-semibold text-gray-900 mb-4">
              Pricing Recommendation
            </h3>
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
              <div className="bg-indigo-50 rounded-lg p-4 text-center">
                <p className="text-xs text-indigo-600 font-medium mb-1">
                  Recommended Price
                </p>
                <p className="text-2xl font-bold text-indigo-900">
                  ${selectedProduct.recommendedPrice.toFixed(2)}
                </p>
                <p className="text-xs text-gray-500 mt-1">
                  from ${selectedProduct.basePrice.toFixed(2)}
                </p>
              </div>
              <div className="bg-gray-50 rounded-lg p-4 text-center">
                <p className="text-xs text-gray-600 font-medium mb-1">
                  Confidence Score
                </p>
                <p className="text-2xl font-bold text-gray-900">
                  {selectedProduct.confidence}%
                </p>
                <p className="text-xs text-gray-500 mt-1">model certainty</p>
              </div>
              <div className="bg-gray-50 rounded-lg p-4 text-center">
                <p className="text-xs text-gray-600 font-medium mb-1">
                  Risk Level
                </p>
                <span
                  className={`inline-block mt-1 px-2 py-1 rounded-full text-xs font-medium ${getRiskColor(
                    selectedProduct.riskLevel
                  )}`}
                >
                  {selectedProduct.riskLevel}
                </span>
                <p className="text-xs text-gray-500 mt-2">
                  based on market volatility
                </p>
              </div>
              <div className="bg-emerald-50 rounded-lg p-4 text-center">
                <p className="text-xs text-emerald-600 font-medium mb-1">
                  Revenue Impact
                </p>
                <p className="text-sm font-semibold text-emerald-900 mt-2">
                  {selectedProduct.revenueImpact}
                </p>
                <p className="text-xs text-gray-500 mt-1">30-day forecast</p>
              </div>
            </div>
          </div>

          <div className="bg-white rounded-lg border border-gray-200 shadow-sm p-6">
            <h3 className="text-sm font-semibold text-gray-900 mb-3">
              Glossary — Retail Pricing Terms
            </h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {glossary.map((item) => (
                <div key={item.term} className="flex gap-2">
                  <span className="text-xs font-semibold text-indigo-700 whitespace-nowrap min-w-[100px]">
                    {item.term}
                  </span>
                  <span className="text-xs text-gray-600">
                    {item.definition}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </>
      )}
    </div>
  );
}

export default PricePredictionTab;
