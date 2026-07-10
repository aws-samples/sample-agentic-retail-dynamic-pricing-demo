import { useState, useEffect } from "react";
import api from "../lib/api";

interface ProductData {
  id: string;
  name: string;
  basePrice: number;
  category: string;
  subcategory: string;
  costFloor: number;
  mapPrice: number | null;
}

interface ScenarioPreset {
  id: string;
  name: string;
  objectives: string[];
  scores: { competitive: number; demand: number; margin: number; market: number };
  changePct: number;
  confidence: number;
  riskLevel: "Low" | "Medium" | "High";
  revenueImpact: string;
}

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

const categoryData: Record<string, Record<string, ProductData[]>> = {
  Electronics: {
    Audio: [
      { id: "earbuds", name: "ProSound Wireless Earbuds", basePrice: 79.99, category: "Electronics", subcategory: "Audio", costFloor: 48.00, mapPrice: 69.99 },
      { id: "speaker", name: "SoundWave Bluetooth Speaker", basePrice: 49.99, category: "Electronics", subcategory: "Audio", costFloor: 30.00, mapPrice: 44.99 },
      { id: "headphones", name: "StudioMax Over-Ear Headphones", basePrice: 149.99, category: "Electronics", subcategory: "Audio", costFloor: 90.00, mapPrice: 129.99 },
    ],
    Wearables: [
      { id: "smartwatch", name: "FitTrack Pro Smartwatch", basePrice: 199.99, category: "Electronics", subcategory: "Wearables", costFloor: 120.00, mapPrice: 179.99 },
    ],
    Tablets: [
      { id: "tablet", name: "TabletX 10-inch Display", basePrice: 249.99, category: "Electronics", subcategory: "Tablets", costFloor: 155.00, mapPrice: 229.99 },
    ],
    Accessories: [
      { id: "powerbank", name: "QuickCharge USB-C Power Bank", basePrice: 39.99, category: "Electronics", subcategory: "Accessories", costFloor: 24.00, mapPrice: null },
    ],
  },
  Grocery: {
    Dairy: [
      { id: "milk", name: "Farm Fresh Whole Milk", basePrice: 4.49, category: "Grocery", subcategory: "Dairy", costFloor: 2.80, mapPrice: null },
      { id: "eggs", name: "Free Range Large Eggs", basePrice: 5.29, category: "Grocery", subcategory: "Dairy", costFloor: 3.90, mapPrice: null },
    ],
    Beverages: [
      { id: "coffee", name: "Mountain Roast Premium Coffee", basePrice: 12.99, category: "Grocery", subcategory: "Beverages", costFloor: 7.80, mapPrice: null },
      { id: "tea", name: "Organic Green Tea", basePrice: 7.99, category: "Grocery", subcategory: "Beverages", costFloor: 4.50, mapPrice: null },
    ],
    Bakery: [
      { id: "bread", name: "Artisan Sourdough Bread Loaf", basePrice: 5.99, category: "Grocery", subcategory: "Bakery", costFloor: 3.20, mapPrice: null },
    ],
  },
  "Home & Garden": {
    Lighting: [
      { id: "lamp", name: "LumiGlow Smart LED Floor Lamp", basePrice: 89.99, category: "Home & Garden", subcategory: "Lighting", costFloor: 35.00, mapPrice: null },
    ],
    Cleaning: [
      { id: "vacuum", name: "CleanForce Cordless Stick Vacuum", basePrice: 299.99, category: "Home & Garden", subcategory: "Cleaning", costFloor: 145.00, mapPrice: 269.99 },
    ],
    "Climate Control": [
      { id: "thermostat", name: "EcoTemp Smart Thermostat", basePrice: 129.99, category: "Home & Garden", subcategory: "Climate Control", costFloor: 65.00, mapPrice: null },
    ],
    Tools: [
      { id: "drill", name: "PowerDrill 20V Cordless Drill Kit", basePrice: 119.99, category: "Home & Garden", subcategory: "Tools", costFloor: 55.00, mapPrice: null },
    ],
    Garden: [
      { id: "sprinkler", name: "GardenPro Automatic Sprinkler Timer", basePrice: 59.99, category: "Home & Garden", subcategory: "Garden", costFloor: 28.00, mapPrice: null },
    ],
  },
};


// Mapping from local product IDs to DynamoDB product IDs for live price lookup
const PRODUCT_ID_MAP: Record<string, string> = {
  earbuds: "prod-elec-001",
  speaker: "prod-elec-002",
  headphones: "prod-elec-005",
  smartwatch: "prod-elec-003",
  tablet: "prod-elec-004",
  powerbank: "prod-elec-006",
  milk: "prod-groc-001",
  eggs: "prod-groc-005",
  coffee: "prod-groc-002",
  tea: "prod-groc-006",
  bread: "prod-groc-003",
  lamp: "prod-home-001",
  vacuum: "prod-home-002",
  thermostat: "prod-home-004",
  drill: "prod-home-005",
  sprinkler: "prod-home-006",
};

const scenarios: ScenarioPreset[] = [
  {
    id: "competitor-price-war",
    name: "Competitor Price War",
    objectives: ["Competitive Positioning", "Market Share Growth"],
    scores: { competitive: 0.92, demand: 0.65, margin: 0.40, market: 0.78 },
    changePct: -12,
    confidence: 84,
    riskLevel: "High",
    revenueImpact: "+8.4% projected revenue increase",
  },
  {
    id: "supply-chain-disruption",
    name: "Supply Chain Disruption",
    objectives: ["Margin Protection", "Revenue Maximization"],
    scores: { competitive: 0.45, demand: 0.72, margin: 0.85, market: 0.55 },
    changePct: 5,
    confidence: 78,
    riskLevel: "Medium",
    revenueImpact: "+2.1% projected revenue increase",
  },
  {
    id: "low-inventory-alert",
    name: "Low Inventory Alert",
    objectives: ["Revenue Maximization", "Margin Protection"],
    scores: { competitive: 0.55, demand: 0.90, margin: 0.75, market: 0.50 },
    changePct: 7,
    confidence: 81,
    riskLevel: "Medium",
    revenueImpact: "+5.6% projected revenue increase",
  },
  {
    id: "high-stock-clearance",
    name: "High Stock Clearance",
    objectives: ["Market Share Growth", "Revenue Maximization"],
    scores: { competitive: 0.68, demand: 0.40, margin: 0.30, market: 0.62 },
    changePct: -15,
    confidence: 72,
    riskLevel: "High",
    revenueImpact: "+11.2% projected revenue increase",
  },
  {
    id: "seasonal-demand-surge",
    name: "Seasonal Demand Surge",
    objectives: ["Revenue Maximization", "Competitive Positioning"],
    scores: { competitive: 0.72, demand: 0.95, margin: 0.60, market: 0.80 },
    changePct: 8,
    confidence: 92,
    riskLevel: "Low",
    revenueImpact: "+9.7% projected revenue increase",
  },
  {
    id: "new-market-entry",
    name: "New Market Entry",
    objectives: ["Market Share Growth", "Competitive Positioning"],
    scores: { competitive: 0.80, demand: 0.55, margin: 0.50, market: 0.88 },
    changePct: -10,
    confidence: 70,
    riskLevel: "Medium",
    revenueImpact: "+6.3% projected revenue increase",
  },
];

const scenarioExplanations: Record<string, Record<string, string>> = {
  "competitor-price-war": {
    competitive: "Competitors are aggressively undercutting prices across the category. Multiple price drops detected in the last 48 hours, indicating a coordinated price war strategy.",
    demand: "Customer demand remains moderate despite price war activity. Shoppers are comparison-shopping more actively but purchase intent is stable.",
    margin: "Margin flexibility is limited during a price war. Deep discounts risk eroding profitability below sustainable thresholds.",
    market: "Market dynamics strongly favor aggressive repositioning. First-mover advantage in price matching can capture significant share.",
  },
  "supply-chain-disruption": {
    competitive: "Competitors face similar supply constraints, reducing price pressure. Market-wide scarcity levels the playing field.",
    demand: "Demand is elevated due to perceived scarcity. Customers are willing to pay premium prices to secure available inventory.",
    margin: "Protecting margins is critical as replacement costs are uncertain. Higher COGS expected on next replenishment cycle.",
    market: "Market signals indicate supply normalization is 4-6 weeks away. Short-term pricing power exists for available inventory.",
  },
  "low-inventory-alert": {
    competitive: "Competitors may have similar inventory constraints. Moderate pressure to match prices while stock lasts.",
    demand: "High demand signal with limited ability to fulfill. Price optimization should maximize revenue per remaining unit.",
    margin: "Strong margin protection needed as replenishment costs may increase. Each unit sold must maximize contribution.",
    market: "Market conditions suggest maintaining price stability while inventory recovers. Avoid signaling weakness to competitors.",
  },
  "high-stock-clearance": {
    competitive: "Competitors are monitoring for clearance signals. Aggressive pricing needed to move excess inventory before seasonal shift.",
    demand: "Demand is low for current inventory levels. Price reduction needed to stimulate purchase velocity and clear warehouse space.",
    margin: "Margin sacrifice is acceptable to recover working capital. Holding costs exceed margin loss from discounting.",
    market: "Market timing favors clearance activity. End-of-cycle buyers actively seeking deals in this category.",
  },
  "seasonal-demand-surge": {
    competitive: "Competitors are raising prices to capture seasonal demand. Opportunity to competitively position while demand is strong.",
    demand: "Exceptional demand signal driven by seasonal patterns. Historical data confirms 2-3x normal purchase velocity in this period.",
    margin: "Moderate margin flexibility with strong volume offsetting per-unit reduction. Volume-based profitability strategy optimal.",
    market: "Market intelligence confirms peak season across all channels. Social media trends and search data align with historical peaks.",
  },
  "new-market-entry": {
    competitive: "Incumbent competitors have established pricing. Penetration pricing needed to gain initial market share and visibility.",
    demand: "Demand for new entrants is developing. Price positioning is critical to establishing value perception in customer minds.",
    margin: "Margin investment phase accepted for market entry. Customer acquisition cost justifies short-term margin compression.",
    market: "Market receptivity to new entrants is high. Category growth and underserved segments create opportunity for disruption.",
  },
};

function buildFactors(scenario: ScenarioPreset): Factor[] {
  const explanations = scenarioExplanations[scenario.id];
  return [
    {
      id: "competitive",
      name: "Competitive Pressure",
      score: scenario.scores.competitive,
      weight: 30,
      explanation: explanations.competitive,
      formula: "Score = (Avg Competitor Price Gap x 0.4) + (Price Position Rank x 0.35) + (Competitor Activity Index x 0.25)",
      components: [
        {
          name: "Avg Competitor Price Gap",
          rawValue: `${(scenario.scores.competitive * -8).toFixed(1)}%`,
          meaning: `Competitors are priced ${(scenario.scores.competitive * 8).toFixed(1)}% below your current price on average`,
          normalizedScore: scenario.scores.competitive * 0.9,
          dataSource: "Real-time price scraping (updated every 4 hours)",
        },
        {
          name: "Price Position Rank",
          rawValue: `${Math.max(1, Math.round((1 - scenario.scores.competitive) * 7))}th of 7`,
          meaning: "Your product ranking among tracked competitors by price",
          normalizedScore: scenario.scores.competitive * 0.85,
          dataSource: "Competitive intelligence platform",
        },
        {
          name: "Competitor Activity Index",
          rawValue: `${Math.round(scenario.scores.competitive * 6)} changes/week`,
          meaning: `Competitors changed prices ${Math.round(scenario.scores.competitive * 6)} times in the past week`,
          normalizedScore: Math.min(0.99, scenario.scores.competitive * 1.05),
          dataSource: "Historical price tracking database",
        },
      ],
      calculation: `Weighted component scores = ${scenario.scores.competitive.toFixed(2)}`,
    },
    {
      id: "demand",
      name: "Demand Signal",
      score: scenario.scores.demand,
      weight: 35,
      explanation: explanations.demand,
      formula: "Score = (Search Volume Trend x 0.45) + (Cart Abandonment Inverse x 0.30) + (Seasonality Factor x 0.25)",
      components: [
        {
          name: "Search Volume Trend",
          rawValue: `+${Math.round(scenario.scores.demand * 30)}% MoM`,
          meaning: `Product search volume increased ${Math.round(scenario.scores.demand * 30)}% month-over-month`,
          normalizedScore: scenario.scores.demand * 0.95,
          dataSource: "Site analytics and search logs",
        },
        {
          name: "Cart Abandonment Inverse",
          rawValue: `${Math.round((1 - scenario.scores.demand * 0.4) * 100)}% abandonment`,
          meaning: `${Math.round(scenario.scores.demand * 40 + 50)}% of users who add to cart complete purchase`,
          normalizedScore: scenario.scores.demand * 0.88,
          dataSource: "E-commerce conversion funnel data",
        },
        {
          name: "Seasonality Factor",
          rawValue: scenario.scores.demand > 0.7 ? "Peak period" : "Normal period",
          meaning: scenario.scores.demand > 0.7 ? "Current period aligns with historical peak demand" : "Demand is within normal seasonal range",
          normalizedScore: scenario.scores.demand * 0.92,
          dataSource: "3-year historical sales data",
        },
      ],
      calculation: `Weighted component scores = ${scenario.scores.demand.toFixed(2)}`,
    },
    {
      id: "margin",
      name: "Margin Constraint",
      score: scenario.scores.margin,
      weight: 20,
      explanation: explanations.margin,
      formula: "Score = (Current Margin Headroom x 0.50) + (COGS Stability x 0.30) + (MAP Compliance x 0.20)",
      components: [
        {
          name: "Current Margin Headroom",
          rawValue: `${Math.round(scenario.scores.margin * 45)}% gross margin`,
          meaning: `Current gross margin is ${Math.round(scenario.scores.margin * 45)}%, with floor at 22%`,
          normalizedScore: scenario.scores.margin * 0.85,
          dataSource: "Internal P&L and cost accounting system",
        },
        {
          name: "COGS Stability",
          rawValue: `+${(2.5 - scenario.scores.margin * 2).toFixed(1)}% QoQ`,
          meaning: `Cost of goods sold changed ${(2.5 - scenario.scores.margin * 2).toFixed(1)}% quarter-over-quarter`,
          normalizedScore: scenario.scores.margin * 0.92,
          dataSource: "Procurement and supply chain data",
        },
        {
          name: "MAP Compliance",
          rawValue: scenario.scores.margin > 0.5 ? "Above MAP" : "Near MAP floor",
          meaning: scenario.scores.margin > 0.5 ? "Recommended price remains above Minimum Advertised Price" : "Recommended price is approaching MAP floor",
          normalizedScore: scenario.scores.margin * 0.78,
          dataSource: "Vendor agreement database",
        },
      ],
      calculation: `Weighted component scores = ${scenario.scores.margin.toFixed(2)}`,
    },
    {
      id: "market",
      name: "Market Intelligence",
      score: scenario.scores.market,
      weight: 15,
      explanation: explanations.market,
      formula: "Score = (Category Growth Rate x 0.40) + (Consumer Sentiment Index x 0.35) + (Economic Indicator x 0.25)",
      components: [
        {
          name: "Category Growth Rate",
          rawValue: `+${Math.round(scenario.scores.market * 12)}% YoY`,
          meaning: `Product category is growing ${Math.round(scenario.scores.market * 12)}% year-over-year`,
          normalizedScore: scenario.scores.market * 0.9,
          dataSource: "Industry analyst reports and market research",
        },
        {
          name: "Consumer Sentiment Index",
          rawValue: `${Math.round(scenario.scores.market * 85)}/100`,
          meaning: `Consumer confidence is at ${Math.round(scenario.scores.market * 85)}/100`,
          normalizedScore: scenario.scores.market * 0.82,
          dataSource: "Consumer surveys and economic indicators",
        },
        {
          name: "Economic Indicator",
          rawValue: scenario.scores.market > 0.7 ? "Favorable" : scenario.scores.market > 0.5 ? "Neutral" : "Cautious",
          meaning: `Macroeconomic conditions are ${scenario.scores.market > 0.7 ? "favorable for growth" : scenario.scores.market > 0.5 ? "neutral" : "cautious, suggesting conservative pricing"}`,
          normalizedScore: scenario.scores.market * 0.78,
          dataSource: "Federal economic data and forecasting models",
        },
      ],
      calculation: `Weighted component scores = ${scenario.scores.market.toFixed(2)}`,
    },
  ];
}

function ScoreBar({ score, color }: { score: number; color: string }) {
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-2 bg-gray-100 rounded-full overflow-hidden">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${Math.min(100, score * 100)}%` }} />
      </div>
      <span className="text-xs font-medium text-gray-600 w-10 text-right">
        {(Math.min(1, score) * 100).toFixed(0)}%
      </span>
    </div>
  );
}

function getScoreColor(score: number) {
  if (score >= 0.7) return "bg-emerald-500";
  if (score >= 0.5) return "bg-amber-500";
  return "bg-red-400";
}

function FactorCard({ factor }: { factor: Factor }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="bg-white rounded-lg border border-gray-200 shadow-sm overflow-hidden">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full px-4 py-3 flex items-center justify-between hover:bg-gray-50 transition-colors"
        aria-expanded={expanded}
        aria-label={`${factor.name} factor details`}
      >
        <div className="flex items-center gap-3">
          <div className={`w-2 h-2 rounded-full ${getScoreColor(factor.score)}`} />
          <span className="text-sm font-medium text-gray-900">{factor.name}</span>
          <span className="text-xs text-gray-500">(weight: {factor.weight}%)</span>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-sm font-semibold text-gray-700">{factor.score.toFixed(2)}</span>
          <svg
            className={`w-4 h-4 text-gray-400 transition-transform ${expanded ? "rotate-180" : ""}`}
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
          </svg>
        </div>
      </button>

      {expanded && (
        <div className="px-4 pb-4 border-t border-gray-100">
          <div className="mt-3 space-y-4">
            <div>
              <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1">Explanation</h4>
              <p className="text-sm text-gray-700 leading-relaxed">{factor.explanation}</p>
            </div>
            <div>
              <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1">Formula</h4>
              <code className="text-xs bg-gray-50 text-gray-800 px-2 py-1 rounded block">{factor.formula}</code>
            </div>
            <div>
              <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">Component Breakdown</h4>
              <div className="space-y-3">
                {factor.components.map((comp) => (
                  <div key={comp.name} className="bg-gray-50 rounded-md p-3 space-y-1">
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-medium text-gray-900">{comp.name}</span>
                      <span className="text-xs font-mono text-indigo-600">{comp.rawValue}</span>
                    </div>
                    <p className="text-xs text-gray-600">{comp.meaning}</p>
                    <div className="flex items-center justify-between pt-1">
                      <ScoreBar score={comp.normalizedScore} color={getScoreColor(comp.normalizedScore)} />
                    </div>
                    <p className="text-xs text-gray-400 italic">Source: {comp.dataSource}</p>
                  </div>
                ))}
              </div>
            </div>
            <div>
              <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1">Final Calculation</h4>
              <code className="text-xs bg-indigo-50 text-indigo-800 px-2 py-1 rounded block">{factor.calculation}</code>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function WhatIfSlider({ label, description, min, max, step, unit, defaultValue, onChange }: {
  label: string; description: string; min: number; max: number; step: number; unit: string; defaultValue: number; onChange: (value: number) => void;
}) {
  const [value, setValue] = useState(defaultValue);

  const handleChange = (newValue: number) => {
    setValue(newValue);
    onChange(newValue);
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-1">
        <span className="text-xs font-medium text-gray-700">{label}</span>
        <span className={`text-xs font-mono font-semibold ${value > 0 ? 'text-emerald-600' : value < 0 ? 'text-red-600' : 'text-gray-500'}`}>
          {value > 0 ? '+' : ''}{value}{unit}
        </span>
      </div>
      <p className="text-xs text-gray-400 mb-2">{description}</p>
      <input
        type="range"
        min={min} max={max} step={step} value={value}
        onChange={(e) => handleChange(Number(e.target.value))}
        className="w-full h-1.5 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-indigo-600"
      />
      <div className="flex justify-between text-xs text-gray-400 mt-0.5">
        <span>{min}{unit}</span>
        <span>{max}{unit}</span>
      </div>
    </div>
  );
}

function WhatIfAnalysis() {
  const [wiCategory, setWiCategory] = useState<string>("");
  const [wiSubcategory, setWiSubcategory] = useState<string>("");
  const [wiProductId, setWiProductId] = useState<string>("");
  const [adjustments, setAdjustments] = useState({ competitor: 0, demand: 0, cogs: 0, sentiment: 0 }); const [wiLivePrices, setWiLivePrices] = useState<Record<string, number>>({});  useEffect(() => { const fetchPrices = async () => { try { const resp = await api.get("/products"); const pm: Record<string, number> = {}; for (const p of resp.data.products ?? []) { pm[p.productId] = parseFloat(p.currentPrice); } setWiLivePrices(pm); } catch { /* ok */ } }; fetchPrices(); }, []);  const getLivePrice = (prod: ProductData): number => { const dbId = PRODUCT_ID_MAP[prod.id]; if (dbId && wiLivePrices[dbId] && wiLivePrices[dbId] > 0) return wiLivePrices[dbId]; return prod.basePrice; };

  const wiCategories = Object.keys(categoryData);
  const wiSubcategories = wiCategory ? Object.keys(categoryData[wiCategory]) : [];
  const wiProducts = wiCategory && wiSubcategory ? categoryData[wiCategory][wiSubcategory] || [] : [];

  // Resolve products for the what-if scope
  const getWiProducts = (): ProductData[] => {
    if (wiProductId) {
      const product = wiProducts.find((p) => p.id === wiProductId);
      return product ? [product] : [];
    }
    if (wiSubcategory && wiCategory) {
      return categoryData[wiCategory][wiSubcategory] || [];
    }
    if (wiCategory) {
      return Object.values(categoryData[wiCategory]).flat();
    }
    return [];
  };

  const whatIfProducts = getWiProducts();
  const hasSelection = wiCategory !== "";

  return (
    <div className="bg-white rounded-lg border border-gray-200 shadow-sm p-6">
      <h2 className="text-lg font-semibold text-gray-900 mb-1">What-If Analysis</h2>
      <p className="text-sm text-gray-500 mb-4">
        Select a product scope and adjust market conditions to see real-time impact on pricing from current catalog prices.
      </p>

      {/* Product scope picker */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
        <div>
          <label htmlFor="wi-category" className="block text-xs font-medium text-gray-700 mb-1">Category</label>
          <select
            id="wi-category"
            value={wiCategory}
            onChange={(e) => { setWiCategory(e.target.value); setWiSubcategory(""); setWiProductId(""); }}
            className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-amber-500 focus:border-amber-500"
          >
            <option value="">Select category...</option>
            {wiCategories.map((cat) => (
              <option key={cat} value={cat}>{cat}</option>
            ))}
          </select>
        </div>
        <div>
          <label htmlFor="wi-subcategory" className="block text-xs font-medium text-gray-700 mb-1">Subcategory (optional)</label>
          <select
            id="wi-subcategory"
            value={wiSubcategory}
            onChange={(e) => { setWiSubcategory(e.target.value); setWiProductId(""); }}
            disabled={!wiCategory}
            className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-amber-500 focus:border-amber-500 disabled:bg-gray-50 disabled:text-gray-400"
          >
            <option value="">All subcategories</option>
            {wiSubcategories.map((sub) => (
              <option key={sub} value={sub}>{sub}</option>
            ))}
          </select>
        </div>
        <div>
          <label htmlFor="wi-product" className="block text-xs font-medium text-gray-700 mb-1">Product (optional)</label>
          <select
            id="wi-product"
            value={wiProductId}
            onChange={(e) => setWiProductId(e.target.value)}
            disabled={!wiSubcategory}
            className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-amber-500 focus:border-amber-500 disabled:bg-gray-50 disabled:text-gray-400"
          >
            <option value="">All products</option>
            {wiProducts.map((prod) => (
              <option key={prod.id} value={prod.id}>{prod.name}</option>
            ))}
          </select>
        </div>
      </div>

      {/* Sliders — always visible once a category is selected */}
      {hasSelection && (
        <>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
            <WhatIfSlider
              label="Competitor Price Change"
              description="What if competitors drop or raise prices?"
              min={-20} max={20} step={1} unit="%"
              defaultValue={0}
              onChange={(v) => setAdjustments(a => ({ ...a, competitor: v }))}
            />
            <WhatIfSlider
              label="Demand Change"
              description="What if demand increases or decreases?"
              min={-30} max={30} step={5} unit="%"
              defaultValue={0}
              onChange={(v) => setAdjustments(a => ({ ...a, demand: v }))}
            />
            <WhatIfSlider
              label="COGS Increase"
              description="What if supply costs rise?"
              min={0} max={25} step={1} unit="%"
              defaultValue={0}
              onChange={(v) => setAdjustments(a => ({ ...a, cogs: v }))}
            />
            <WhatIfSlider
              label="Market Sentiment Shift"
              description="What if consumer confidence changes?"
              min={-30} max={30} step={5} unit=" pts"
              defaultValue={0}
              onChange={(v) => setAdjustments(a => ({ ...a, sentiment: v }))}
            />
          </div>

          {/* Real-time impact table */}
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 border-b border-gray-200">
                <tr>
                  <th className="px-3 py-2 text-left font-medium text-gray-500">Product</th>
                  <th className="px-3 py-2 text-left font-medium text-gray-500">Subcategory</th>
                  <th className="px-3 py-2 text-right font-medium text-gray-500">Current Price</th>
                  <th className="px-3 py-2 text-right font-medium text-gray-500">Adjusted Price</th>
                  <th className="px-3 py-2 text-right font-medium text-gray-500">Price Change</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {whatIfProducts.map((prod) => {
                  const wiLivePrice = getLivePrice(prod); const adjusted = +(wiLivePrice
                    * (1 + adjustments.competitor / 200)
                    * (1 + adjustments.demand / 150)
                    * (1 + adjustments.cogs / 100)
                    * (1 + adjustments.sentiment / 200)
                  ).toFixed(2);
                  const impact = ((adjusted - wiLivePrice) / wiLivePrice * 100).toFixed(1);
                  return (
                    <tr key={prod.id} className="hover:bg-gray-50">
                      <td className="px-3 py-2 text-gray-900 font-medium">{prod.name}</td>
                      <td className="px-3 py-2 text-gray-500">{prod.subcategory}</td>
                      <td className="px-3 py-2 text-right text-gray-700">${wiLivePrice.toFixed(2)}</td>
                      <td className="px-3 py-2 text-right font-semibold text-amber-700">${adjusted.toFixed(2)}</td>
                      <td className={`px-3 py-2 text-right font-medium ${Number(impact) > 0 ? 'text-emerald-600' : Number(impact) < 0 ? 'text-red-600' : 'text-gray-500'}`}>
                        {Number(impact) > 0 ? '+' : ''}{impact}%
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          <div className="mt-4 bg-amber-50 rounded-lg p-3 text-xs text-amber-800">
            <strong>Note:</strong> This shows directional pricing impact from current catalog prices based on market condition changes.
            No scenario or simulation run is required. In production, these shifts would trigger an automated agent re-evaluation.
          </div>
        </>
      )}

      {!hasSelection && (
        <div className="text-center py-8 text-gray-400">
          <p className="text-sm">Select a category above to start exploring pricing sensitivity.</p>
        </div>
      )}
    </div>
  );
}

function PricePredictionTab() {
  const [selectedCategory, setSelectedCategory] = useState<string>("");
  const [selectedSubcategory, setSelectedSubcategory] = useState<string>("");
  const [selectedProductId, setSelectedProductId] = useState<string>("");
  const [selectedScenarioId, setSelectedScenarioId] = useState<string>("");
  const [showResults, setShowResults] = useState(false);
  const [isSimulating, setIsSimulating] = useState(false);
  const [livePrices, setLivePrices] = useState<Record<string, number>>({});

  useEffect(() => {
    const fetchLivePrices = async () => {
      try {
        const resp = await api.get('/products');
        const priceMap: Record<string, number> = {};
        for (const p of resp.data.products ?? []) {
          priceMap[p.productId] = parseFloat(p.currentPrice);
        }
        setLivePrices(priceMap);
      } catch { /* non-critical */ }
    };
    fetchLivePrices();
  }, []);

  // Helper: get live price for a product, falling back to static basePrice
  const getLivePrice = (prod: ProductData): number => {
    const dbId = PRODUCT_ID_MAP[prod.id];
    if (dbId && livePrices[dbId] && livePrices[dbId] > 0) {
      return livePrices[dbId];
    }
    return prod.basePrice;
  };

  const categories = Object.keys(categoryData);
  const subcategories = selectedCategory ? Object.keys(categoryData[selectedCategory]) : [];
  const products = selectedCategory && selectedSubcategory ? categoryData[selectedCategory][selectedSubcategory] || [] : [];
  const selectedProduct = products.find((p) => p.id === selectedProductId);
  const selectedScenario = scenarios.find((s) => s.id === selectedScenarioId);

  // Resolve the effective product list based on selection level
  const getSimulationProducts = (): ProductData[] => {
    if (selectedProductId) {
      const product = products.find((p) => p.id === selectedProductId);
      return product ? [product] : [];
    }
    if (selectedSubcategory && selectedCategory) {
      return categoryData[selectedCategory][selectedSubcategory] || [];
    }
    if (selectedCategory) {
      return Object.values(categoryData[selectedCategory]).flat();
    }
    return [];
  };

  const simulationProducts = getSimulationProducts();

  const handleCategoryChange = (value: string) => {
    setSelectedCategory(value);
    setSelectedSubcategory("");
    setSelectedProductId("");
    setShowResults(false);
  };

  const handleSubcategoryChange = (value: string) => {
    setSelectedSubcategory(value);
    setSelectedProductId("");
    setShowResults(false);
  };

  const handleProductChange = (value: string) => {
    setSelectedProductId(value);
    setShowResults(false);
  };

  const handleScenarioChange = (value: string) => {
    setSelectedScenarioId(value);
    setShowResults(false);
  };

  const canSimulate = selectedCategory && selectedScenarioId;

  const handleSimulate = () => {
    if (!canSimulate) return;
    setIsSimulating(true);
    setTimeout(() => {
      setIsSimulating(false);
      setShowResults(true);
    }, 800);
  };

  const currentFactors = selectedScenario ? buildFactors(selectedScenario) : [];
  const weightedScore = currentFactors.reduce((sum, f) => sum + f.score * (f.weight / 100), 0);
  const rawRecommendedPrice = selectedProduct && selectedScenario
    ? +(getLivePrice(selectedProduct) * (1 + selectedScenario.changePct / 100)).toFixed(2)
    : 0;
 const singleFloor = selectedProduct ? Math.max(selectedProduct.costFloor, selectedProduct.mapPrice ?? 0) : 0;
 const recommendedPrice = rawRecommendedPrice < singleFloor && singleFloor > 0 ? singleFloor : rawRecommendedPrice;

  const getRiskColor = (risk: string) => {
    switch (risk) {
      case "Low": return "bg-emerald-100 text-emerald-800";
      case "Medium": return "bg-amber-100 text-amber-800";
      case "High": return "bg-red-100 text-red-800";
      default: return "bg-gray-100 text-gray-800";
    }
  };

  return (
    <div className="space-y-6">
      <div className="bg-blue-50 border border-blue-200 rounded-lg px-4 py-3 flex items-start gap-3">
        <svg className="w-5 h-5 text-blue-500 mt-0.5 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
        <p className="text-sm text-blue-800">
          This is a read-only simulation. No changes are applied to the product catalog.
        </p>
      </div>

      <div className="bg-white rounded-lg border border-gray-200 shadow-sm p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-1">Price Prediction Simulator</h2>
        <p className="text-sm text-gray-500 mb-4">
          Select a category, subcategory, or individual product and a scenario to explore how AI pricing recommendations are derived through a multi-factor decision tree.
        </p>
        <div className="bg-amber-50 border border-amber-200 rounded-md px-3 py-2 mb-4">
          <p className="text-xs text-amber-800">
            <span className="font-semibold">Note:</span> This simulator shows the theoretical maximum price impact if the selected scenario fully materializes — think of it as a sensitivity analysis. The actual Pricing Cycle (Simulations tab) generates 5 risk-graded strategies ranging from aggressive to conservative, with only the safest option auto-approved. The simulator answers &quot;what could happen?&quot; while the pricing cycle answers &quot;what should we do?&quot;
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
          <div>
            <label htmlFor="category-select" className="block text-xs font-medium text-gray-700 mb-1">Category</label>
            <select
              id="category-select"
              value={selectedCategory}
              onChange={(e) => handleCategoryChange(e.target.value)}
              className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
            >
              <option value="">Select category...</option>
              {categories.map((cat) => (
                <option key={cat} value={cat}>{cat}</option>
              ))}
            </select>
          </div>
          <div>
            <label htmlFor="subcategory-select" className="block text-xs font-medium text-gray-700 mb-1">Subcategory</label>
            <select
              id="subcategory-select"
              value={selectedSubcategory}
              onChange={(e) => handleSubcategoryChange(e.target.value)}
              disabled={!selectedCategory}
              className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 disabled:bg-gray-50 disabled:text-gray-400"
            >
              <option value="">Select subcategory...</option>
              {subcategories.map((sub) => (
                <option key={sub} value={sub}>{sub}</option>
              ))}
            </select>
          </div>
          <div>
            <label htmlFor="product-select" className="block text-xs font-medium text-gray-700 mb-1">Product</label>
            <select
              id="product-select"
              value={selectedProductId}
              onChange={(e) => handleProductChange(e.target.value)}
              disabled={!selectedSubcategory}
              className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 disabled:bg-gray-50 disabled:text-gray-400"
            >
              <option value="">Select product...</option>
              {products.map((prod) => (
                <option key={prod.id} value={prod.id}>{prod.name}</option>
              ))}
            </select>
          </div>
        </div>

        <div className="flex items-end gap-3">
          <div className="flex-1">
            <label htmlFor="scenario-select" className="block text-xs font-medium text-gray-700 mb-1">Scenario Preset</label>
            <select
              id="scenario-select"
              value={selectedScenarioId}
              onChange={(e) => handleScenarioChange(e.target.value)}
              className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
            >
              <option value="">Choose a scenario...</option>
              {scenarios.map((s) => (
                <option key={s.id} value={s.id}>{s.name}</option>
              ))}
            </select>
          </div>
          <button
            onClick={handleSimulate}
            disabled={!canSimulate || isSimulating}
            className="px-4 py-2 bg-indigo-600 text-white text-sm font-medium rounded-md hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {isSimulating ? (
              <span className="flex items-center gap-2">
                <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24" fill="none">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
                Simulating...
              </span>
            ) : (
              "Simulate"
            )}
          </button>
        </div>

        {selectedScenario && (
          <div className="mt-3">
            <span className="text-xs text-gray-500 mr-2">Strategic Objectives:</span>
            {selectedScenario.objectives.map((obj) => (
              <span
                key={obj}
                className="inline-block bg-indigo-50 text-indigo-700 text-xs font-medium px-2.5 py-0.5 rounded-full mr-2 mb-1"
              >
                {obj}
              </span>
            ))}
          </div>
        )}
      </div>

      {showResults && simulationProducts.length > 0 && selectedScenario && (
        <>
          <div className="bg-white rounded-lg border border-gray-200 shadow-sm p-6">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-sm font-semibold text-gray-900">Decision Tree — Factor Scores</h3>
              <div className="text-xs text-gray-500 flex items-center gap-1">
                Weighted Score: <span className="font-semibold text-indigo-600">{weightedScore.toFixed(3)}</span>
                <span className="relative group">
                  <svg className="w-3.5 h-3.5 text-gray-400 cursor-help" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                  <span className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 w-72 p-2 bg-gray-900 text-white text-xs rounded-lg opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none z-10">
                    <strong>Formula:</strong> Sum of (Factor Score x Weight) for each factor.<br/>
                    {currentFactors.map(f => `(${f.score.toFixed(2)} x ${f.weight}%)`).join(' + ')} = {weightedScore.toFixed(3)}
                  </span>
                </span>
              </div>
            </div>
            <p className="text-xs text-gray-500 mb-4">
              Click each factor to expand and see the full explanation, formula, and component breakdown.
            </p>
            <div className="space-y-2">
              {currentFactors.map((factor) => (
                <FactorCard key={factor.id} factor={factor} />
              ))}
            </div>
          </div>

          <div className="bg-white rounded-lg border border-gray-200 shadow-sm p-6">
            <h3 className="text-sm font-semibold text-gray-900 mb-4">Pricing Recommendation{simulationProducts.length > 1 ? 's' : ''}</h3>
            {simulationProducts.length === 1 && selectedProduct ? (
              <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                <div className="bg-indigo-50 rounded-lg p-4 text-center">
                  <p className="text-xs text-indigo-600 font-medium mb-1">Recommended Price</p>
                  <p className="text-2xl font-bold text-indigo-900">${recommendedPrice.toFixed(2)}</p>
                  <p className="text-xs text-gray-500 mt-1">from ${getLivePrice(selectedProduct).toFixed(2)}</p>
                </div>
                <div className="bg-gray-50 rounded-lg p-4 text-center">
                  <p className="text-xs text-gray-600 font-medium mb-1">Confidence Score</p>
                  <p className="text-2xl font-bold text-gray-900">{selectedScenario.confidence}%</p>
                  <p className="text-xs text-gray-500 mt-1">model certainty</p>
                </div>
                <div className="bg-gray-50 rounded-lg p-4 text-center">
                  <p className="text-xs text-gray-600 font-medium mb-1">Risk Level</p>
                  <span className={`inline-block mt-1 px-2 py-1 rounded-full text-xs font-medium ${getRiskColor(selectedScenario.riskLevel)}`}>
                    {selectedScenario.riskLevel}
                  </span>
                  <p className="text-xs text-gray-500 mt-2">based on market volatility</p>
                </div>
                <div className="bg-emerald-50 rounded-lg p-4 text-center">
                  <p className="text-xs text-emerald-600 font-medium mb-1">Revenue Impact</p>
                  <p className="text-sm font-semibold text-emerald-900 mt-2">{selectedScenario.revenueImpact}</p>
                  <p className="text-xs text-gray-500 mt-1">30-day forecast</p>
                </div>
              </div>
            ) : (
              <>
                <p className="text-xs text-gray-500 mb-3">
                  Simulating {simulationProducts.length} product{simulationProducts.length > 1 ? 's' : ''} in {selectedCategory}{selectedSubcategory ? ` > ${selectedSubcategory}` : ' (all subcategories)'}
                </p>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead className="bg-gray-50 border-b border-gray-200">
                      <tr>
                        <th className="px-3 py-2 text-left font-medium text-gray-500">Product</th>
                        <th className="px-3 py-2 text-left font-medium text-gray-500">Subcategory</th>
                        <th className="px-3 py-2 text-right font-medium text-gray-500">Current</th>
                        <th className="px-3 py-2 text-right font-medium text-gray-500">Recommended</th>
                        <th className="px-3 py-2 text-right font-medium text-gray-500">Change</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-100">
                      {simulationProducts.map((prod) => {
                        const liveP = getLivePrice(prod); const rawPrice = +(liveP * (1 + selectedScenario.changePct / 100)).toFixed(2); const floor = Math.max(prod.costFloor, prod.mapPrice ?? 0); const recPrice = rawPrice < floor ? +floor.toFixed(2) : rawPrice; const guardrailApplied = rawPrice < floor;
                        const pctChange = ((recPrice - liveP) / liveP * 100).toFixed(1);
                        return (
                          <tr key={prod.id} className="hover:bg-gray-50">
                            <td className="px-3 py-2 text-gray-900 font-medium">{prod.name}</td>
                            <td className="px-3 py-2 text-gray-500">{prod.subcategory}</td>
                            <td className="px-3 py-2 text-right text-gray-700">${liveP.toFixed(2)}</td>
                            <td className="px-3 py-2 text-right font-semibold text-indigo-700">${recPrice.toFixed(2)}{guardrailApplied && <span className="ml-1 text-[9px] bg-amber-100 text-amber-700 px-1 py-0.5 rounded">MAP</span>}</td>
                            <td className={`px-3 py-2 text-right font-medium ${Number(pctChange) < 0 ? 'text-red-600' : 'text-emerald-600'}`}>
                              {Number(pctChange) > 0 ? '+' : ''}{pctChange}%
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
                <div className="mt-4 grid grid-cols-3 gap-4">
                  <div className="bg-gray-50 rounded-lg p-3 text-center">
                    <p className="text-xs text-gray-600 font-medium">Confidence</p>
                    <p className="text-lg font-bold text-gray-900">{selectedScenario.confidence}%</p>
                  </div>
                  <div className="bg-gray-50 rounded-lg p-3 text-center">
                    <p className="text-xs text-gray-600 font-medium">Risk Level</p>
                    <span className={`inline-block mt-1 px-2 py-1 rounded-full text-xs font-medium ${getRiskColor(selectedScenario.riskLevel)}`}>
                      {selectedScenario.riskLevel}
                    </span>
                  </div>
                  <div className="bg-emerald-50 rounded-lg p-3 text-center">
                    <p className="text-xs text-emerald-600 font-medium">Revenue Impact</p>
                    <p className="text-sm font-semibold text-emerald-900 mt-1">{selectedScenario.revenueImpact}</p>
                  </div>
                </div>
              </>
            )}
          </div>
        </>
      )}

      {/* Standalone What-If Analysis */}
      <WhatIfAnalysis />

    </div>
  );
}

export default PricePredictionTab;
