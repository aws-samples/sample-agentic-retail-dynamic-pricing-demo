/**
 * Methodology dictionary and factor definitions for the Retail Dynamic Pricing system.
 * Provides structured metadata for contributing factor tooltips, the methodology
 * slide-out panel, and the standalone methodology page.
 */

export interface FactorDefinition {
  key: string;
  label: string;
  description: string;
  category: 'competitive' | 'demand' | 'market';
}

export const METHODOLOGY_DICTIONARY: Record<string, FactorDefinition> = {
  // --- Competitive Factors ---
  competitorPriceAvg: {
    key: 'competitorPriceAvg',
    label: 'Competitor Price Average',
    description:
      'Weighted average of competitor prices for the same SKU or equivalent product. Calculated from real-time competitor price feeds aggregated over the trailing 24-hour window. A value of 29.95 means the average competitor list price is $29.95. Source: Competitor API Server.',
    category: 'competitive',
  },
  competitorCount: {
    key: 'competitorCount',
    label: 'Competitor Count',
    description:
      'Number of active competitors offering the same or directly substitutable product within the tracked marketplace. Derived from daily competitor catalog scans. A value of 5 indicates five competing sellers are currently active. Source: Competitor API Server.',
    category: 'competitive',
  },
  pricePosition: {
    key: 'pricePosition',
    label: 'Price Position',
    description:
      'Ordinal rank of our price relative to competitors, where 1 = lowest priced. Calculated by sorting all tracked competitor prices ascending and inserting our current price. A value of 3 means two competitors are priced lower. Source: Competitor API Server.',
    category: 'competitive',
  },
  competitorPriceIndex: {
    key: 'competitorPriceIndex',
    label: 'Competitor Price Index',
    description:
      'Ratio of our current price to the average competitor price for the same product category. Calculated as (our_price / avg_competitor_price). A value of 1.03 means we are priced 3% above the market average; 0.97 means 3% below. Source: Competitor API Server.',
    category: 'competitive',
  },
  priceGap: {
    key: 'priceGap',
    label: 'Price Gap',
    description:
      'Absolute difference between our price and the lowest competitor price, expressed in the local currency. Calculated as (our_price − min_competitor_price). A positive value indicates we are above the cheapest competitor; negative means we are the price leader. Source: Competitor API Server.',
    category: 'competitive',
  },
  competitorPriceRange: {
    key: 'competitorPriceRange',
    label: 'Competitor Price Range',
    description:
      'The spread between the lowest and highest competitor prices for the same SKU or equivalent product. Calculated as (max_competitor_price − min_competitor_price). A value of 12.50 means the cheapest competitor is $12.50 below the most expensive. Wider ranges indicate fragmented market pricing; narrow ranges suggest price convergence. Source: Competitor API Server.',
    category: 'competitive',
  },
  marketShare: {
    key: 'marketShare',
    label: 'Market Share',
    description:
      'Estimated percentage of category unit sales captured by our product. Derived from POS transaction volumes relative to total addressable market estimates. A value of 0.18 represents an 18% unit market share. Source: ERP/POS Server + Market Signals Server.',
    category: 'competitive',
  },

  // --- Demand Factors ---
  demandVelocity: {
    key: 'demandVelocity',
    label: 'Demand Velocity',
    description:
      'Rate of unit sales per day normalized against the 30-day rolling average. Calculated as (units_sold_today / avg_daily_units_30d). A value of 1.45 indicates demand is 45% above the recent baseline; below 1.0 signals declining demand. Source: ERP/POS Server.',
    category: 'demand',
  },
  stockLevel: {
    key: 'stockLevel',
    label: 'Stock Level',
    description:
      'Current inventory quantity on hand expressed as days-of-supply remaining at the trailing 7-day sell-through rate. Calculated as (units_on_hand / avg_daily_sales_7d). A value of 14.2 means approximately 14 days of inventory remain. Source: ERP/POS Server.',
    category: 'demand',
  },
  seasonalIndex: {
    key: 'seasonalIndex',
    label: 'Seasonal Index',
    description:
      'Multiplicative seasonal adjustment factor derived from 52-week historical demand decomposition. A value of 1.25 indicates the current period historically sees 25% higher demand than the annual average; 0.80 indicates 20% lower. Source: ERP/POS Server (historical).',
    category: 'demand',
  },
  elasticity: {
    key: 'elasticity',
    label: 'Price Elasticity',
    description:
      'Point price elasticity of demand measuring percentage change in quantity demanded per 1% price change. Estimated via log-linear regression on trailing 90-day price-quantity pairs. A value of −1.91 means a 1% price increase is associated with a 1.91% decrease in units sold. Source: ERP/POS Server (regression model).',
    category: 'demand',
  },
  priceElasticity: {
    key: 'priceElasticity',
    label: 'Price Elasticity (Adjusted)',
    description:
      'Cross-validated price elasticity coefficient adjusted for promotional periods and stockout events. Uses the same regression methodology as base elasticity but excludes anomalous demand periods. A value of −2.10 indicates higher price sensitivity after adjustment. Source: ERP/POS Server (adjusted model).',
    category: 'demand',
  },
  unitsSold: {
    key: 'unitsSold',
    label: 'Units Sold',
    description:
      'Total units sold in the most recent pricing cycle evaluation window (typically 7 days). Aggregated from point-of-sale transaction records. A value of 342 means 342 units transacted during the window. Source: ERP/POS Server.',
    category: 'demand',
  },
  salesTrend: {
    key: 'salesTrend',
    label: 'Sales Trend',
    description:
      'Directional momentum of unit sales over the trailing 14-day window expressed as the slope of a linear fit to daily units sold. A positive value (e.g., 2.3) indicates an upward trend of approximately 2.3 additional units sold per day; negative values signal declining sales velocity. Source: ERP/POS Server.',
    category: 'demand',
  },
  daysOfSupply: {
    key: 'daysOfSupply',
    label: 'Days of Supply',
    description:
      'Estimated number of days current on-hand inventory will last at the prevailing sell-through rate. Calculated as (units_on_hand / avg_daily_units_sold_7d). A value of 21 means approximately 3 weeks of stock remain. Values below 7 trigger replenishment alerts; values above 60 may indicate overstock. Source: ERP/POS Server.',
    category: 'demand',
  },
  unitsSold7d: {
    key: 'unitsSold7d',
    label: 'Units Sold (7-Day)',
    description:
      'Total units sold during the trailing 7-day window. Provides a short-term demand signal that responds quickly to price changes and promotional activity. Compare against unitsSold30d to detect demand acceleration or deceleration. Source: ERP/POS Server.',
    category: 'demand',
  },
  unitsSold30d: {
    key: 'unitsSold30d',
    label: 'Units Sold (30-Day)',
    description:
      'Total units sold during the trailing 30-day window. Represents the medium-term demand baseline used for seasonal normalization and demand velocity calculations. Less sensitive to short-term noise than the 7-day metric. Source: ERP/POS Server.',
    category: 'demand',
  },
  inventoryTurnover: {
    key: 'inventoryTurnover',
    label: 'Inventory Turnover',
    description:
      'Annualized rate at which inventory is sold and replaced. Calculated as (annual_COGS / avg_inventory_value). A value of 8.5 means inventory turns over approximately 8.5 times per year, or roughly every 43 days. Source: ERP/POS Server.',
    category: 'demand',
  },

  // --- Market Factors ---
  marketTrend: {
    key: 'marketTrend',
    label: 'Market Trend',
    description:
      'Directional indicator of overall category market momentum over the trailing 30 days. Calculated as the slope coefficient of a linear regression fitted to daily category revenue. A positive value (e.g., 0.03) indicates 3% upward trend; negative indicates contraction. Source: Market Signals Server.',
    category: 'market',
  },
  inflationRate: {
    key: 'inflationRate',
    label: 'Inflation Rate',
    description:
      'Annualized consumer price inflation rate for the relevant product category. Sourced from government CPI data releases interpolated to the current period. A value of 0.034 represents 3.4% annual category inflation. Source: Market Signals Server (BLS/CPI feed).',
    category: 'market',
  },
  consumerSentiment: {
    key: 'consumerSentiment',
    label: 'Consumer Sentiment',
    description:
      'Normalized consumer confidence index specific to the retail sector, scaled 0–100. Derived from survey data and real-time social sentiment analysis. A value above 60 indicates positive spending outlook; below 40 signals cautious consumers. Source: Market Signals Server.',
    category: 'market',
  },
  marketVolatility: {
    key: 'marketVolatility',
    label: 'Market Volatility',
    description:
      'Standard deviation of daily category price movements over the trailing 14-day window, expressed as a percentage. Calculated from aggregated category price data across all tracked competitors. A value of 0.08 indicates 8% price volatility in the category. Source: Market Signals Server.',
    category: 'market',
  },
  categoryGrowth: {
    key: 'categoryGrowth',
    label: 'Category Growth',
    description:
      'Year-over-year revenue growth rate for the product category. Calculated as (current_period_revenue − prior_year_period_revenue) / prior_year_period_revenue. A value of 0.12 indicates 12% YoY category growth. Source: Market Signals Server.',
    category: 'market',
  },
  socialMentions: {
    key: 'socialMentions',
    label: 'Social Mentions',
    description:
      'Volume of brand and product mentions across monitored social media platforms over the trailing 7-day window, normalized per 1,000 category mentions. A value of 45 indicates 45 mentions per 1,000 category conversations. Spikes correlate with viral demand events and may precede demand velocity changes by 24–48 hours. Source: Market Signals Server (social listening feed).',
    category: 'market',
  },
  seasonalDemand: {
    key: 'seasonalDemand',
    label: 'Seasonal Demand Multiplier',
    description:
      'Market-wide seasonal demand multiplier reflecting macro consumer spending patterns (holidays, back-to-school, etc.). Distinct from product-level seasonalIndex in that it captures category-agnostic demand shifts. A value of 1.35 during Q4 holiday season indicates 35% elevated baseline demand. Source: Market Signals Server.',
    category: 'market',
  },
};

export interface MethodologySection {
  id: string;
  title: string;
  category: 'competitive' | 'demand' | 'market';
  description: string;
  factors: FactorDefinition[];
}

export const METHODOLOGY_SECTIONS: MethodologySection[] = [
  {
    id: 'competitive',
    title: 'Competitive Intelligence Factors',
    category: 'competitive',
    description:
      'Competitive factors quantify our pricing position relative to the marketplace. These signals are ingested from real-time competitor price feeds, marketplace scraping pipelines, and catalog matching algorithms. The pricing engine uses competitive signals to ensure price competitiveness while protecting margin targets.',
    factors: Object.values(METHODOLOGY_DICTIONARY).filter((f) => f.category === 'competitive'),
  },
  {
    id: 'demand',
    title: 'Demand & Inventory Factors',
    category: 'demand',
    description:
      'Demand factors capture the velocity, elasticity, and inventory health of each product. These signals originate from ERP and POS transaction systems, demand forecasting models, and inventory management platforms. The pricing engine uses demand signals to optimize sell-through rates and prevent overstock or stockout conditions.',
    factors: Object.values(METHODOLOGY_DICTIONARY).filter((f) => f.category === 'demand'),
  },
  {
    id: 'market',
    title: 'Market & Macro Factors',
    category: 'market',
    description:
      'Market factors represent broader economic and consumer behavior trends that influence pricing decisions beyond product-specific signals. These include inflation indices, consumer confidence metrics, and category-level growth rates sourced from government data feeds and market research providers.',
    factors: Object.values(METHODOLOGY_DICTIONARY).filter((f) => f.category === 'market'),
  },
];

export interface GlossaryTerm {
  term: string;
  definition: string;
}

export const GLOSSARY_TERMS: GlossaryTerm[] = [
  {
    term: 'Composite Score',
    definition:
      'A weighted aggregate score (0–10 scale) that combines projected revenue impact, margin preservation, competitive positioning, and risk assessment into a single decision metric for each pricing scenario.',
  },
  {
    term: 'Confidence Score',
    definition:
      'A 0–100 measure of data completeness and model agreement. Higher scores indicate strong alignment across all contributing data sources and low prediction uncertainty.',
  },
  {
    term: 'Price Elasticity',
    definition:
      'The percentage change in quantity demanded resulting from a 1% change in price. Negative values (typical) indicate demand decreases as price rises. More negative values signal higher price sensitivity.',
  },
  {
    term: 'Demand Velocity',
    definition:
      'The normalized rate of unit sales relative to the recent historical baseline. Values above 1.0 indicate accelerating demand; below 1.0 indicate decelerating demand.',
  },
  {
    term: 'Guardrail',
    definition:
      'A business rule constraint that pricing recommendations must satisfy before approval. Examples include maximum price change percentage, minimum margin floor, and competitor price bounds.',
  },
  {
    term: 'Pricing Cycle',
    definition:
      'A single execution of the pricing optimization pipeline for a specific product group. Each cycle evaluates market conditions, generates candidate scenarios, and produces ranked recommendations.',
  },
  {
    term: 'Pricing Group',
    definition:
      'A hierarchical identifier encoding the product taxonomy level at which a pricing cycle operates. Encoded as "Category", "Category-SubCategory", or "product-{id}".',
  },
  {
    term: 'Scenario',
    definition:
      'A candidate pricing recommendation generated by the optimization engine within a pricing cycle. Each scenario represents a distinct price-setting strategy with projected financial outcomes.',
  },
  {
    term: 'Risk Level',
    definition:
      'A categorical assessment (LOW, MEDIUM, HIGH) of the potential adverse impact of a pricing change. Factors include magnitude of change, competitive response probability, and demand uncertainty.',
  },
  {
    term: 'Projected Revenue',
    definition:
      'The forecasted revenue impact over the planning horizon if the pricing scenario is approved and implemented. Based on demand elasticity models and historical conversion rates.',
  },
  {
    term: 'Market Share Impact',
    definition:
      'The estimated percentage-point change in unit market share resulting from the proposed price adjustment, modeled via competitive response simulation.',
  },
  {
    term: 'Inventory Turnover',
    definition:
      'The annualized rate at which inventory is sold and replenished. Higher turnover indicates efficient inventory utilization; lower turnover may signal overstock risk.',
  },
];

export interface ScoringMethodology {
  title: string;
  description: string;
  components: { name: string; weight: string; description: string }[];
}

export const SCORING_METHODOLOGY: ScoringMethodology = {
  title: 'Scoring Methodology',
  description:
    'Each pricing scenario is evaluated using a multi-factor scoring model that produces a Composite Score and a Confidence Score. These scores drive the ranking of candidate scenarios and inform human-in-the-loop approval decisions.',
  components: [
    {
      name: 'Revenue Impact',
      weight: '30%',
      description:
        'Projected revenue change relative to the status-quo baseline, weighted by demand elasticity estimates and seasonal adjustment factors.',
    },
    {
      name: 'Margin Preservation',
      weight: '25%',
      description:
        'Degree to which the proposed price maintains or improves gross margin percentage relative to cost-of-goods-sold and minimum margin guardrails.',
    },
    {
      name: 'Competitive Position',
      weight: '20%',
      description:
        'Alignment of the proposed price with competitive market positioning targets. Penalizes prices that fall outside the acceptable competitive price index band.',
    },
    {
      name: 'Demand Alignment',
      weight: '15%',
      description:
        'Consistency of the proposed price direction with current demand velocity signals and inventory health indicators.',
    },
    {
      name: 'Risk Assessment',
      weight: '10%',
      description:
        'Inverse risk penalty based on the magnitude of price change, guardrail proximity, and market volatility conditions.',
    },
  ],
};

/**
 * Normalizes a factor key by converting snake_case to camelCase and stripping spaces.
 */
function normalizeFactorKey(key: string): string {
  // Strip spaces
  let normalized = key.replace(/\s+/g, '');
  // Convert snake_case to camelCase
  normalized = normalized.replace(/_([a-zA-Z])/g, (_, char) => char.toUpperCase());
  return normalized;
}

/**
 * Returns the methodology description for a given factor key, or null if not found.
 * Normalizes the key (converts snake_case to camelCase, strips spaces) before lookup.
 */
export function getFactorTooltip(factorKey: string): string | null {
  const normalized = normalizeFactorKey(factorKey);
  return METHODOLOGY_DICTIONARY[normalized]?.description ?? null;
}
