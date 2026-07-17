import { useState, useEffect } from 'react';
import api from '../lib/api';
import { DonutChart } from './Charts';

interface CycleData {
  cycleId: string;
  status: string;
  pricingGroup: string;
  scenarioCount: number;
  createdAt: string;
  completedAt?: string;
  scenarios?: ScenarioData[];
}

interface ScenarioData {
  scenarioId: string;
  rank: number;
  projectedRevenue: number;
  projectedMargin: number;
  riskLevel: string;
  approvalStatus?: string;
  approvedBy?: string;
  priceChanges?: { productId: string; currentPrice: number; newPrice: number; changePercent: number }[];
}

export default function FinancialMetrics() {
  const [cycles, setCycles] = useState<CycleData[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const response = await api.get('/pricing-cycles');
        setCycles(response.data.cycles ?? []);
      } catch {
        // Silently handle — metrics are non-critical
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, []);

  if (loading) {
    return (
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
        {[1, 2, 3, 4].map((i) => (
          <div key={i} className="bg-white rounded-lg border border-gray-200 p-4 animate-pulse">
            <div className="h-4 bg-gray-200 rounded w-2/3 mb-2" />
            <div className="h-6 bg-gray-200 rounded w-1/2" />
          </div>
        ))}
      </div>
    );
  }

  // Compute financial metrics from approved scenarios
  const completedCycles = cycles.filter((c) => c.status === 'COMPLETE');
  const allScenarios = cycles.flatMap((c) => c.scenarios ?? []);
  const approvedScenarios = allScenarios.filter((s) => s.approvalStatus === 'APPROVED');

  // Total projected revenue from approved scenarios
  const totalProjectedRevenue = approvedScenarios.reduce(
    (sum, s) => sum + (s.projectedRevenue ?? 0), 0
  );

  // Average projected margin from approved scenarios
  const avgProjectedMargin = approvedScenarios.length > 0
    ? approvedScenarios.reduce((sum, s) => sum + (s.projectedMargin ?? 0), 0) / approvedScenarios.length
    : 0;

  // Total price changes implemented
  const totalPriceChanges = approvedScenarios.reduce(
    (sum, s) => sum + (s.priceChanges?.length ?? 0), 0
  );

  // Average price change percentage
  const allChanges = approvedScenarios.flatMap((s) => s.priceChanges ?? []);
  const avgPriceChange = allChanges.length > 0
    ? allChanges.reduce((sum, c) => sum + (c.changePercent ?? 0), 0) / allChanges.length
    : 0;

  // Auto-approved vs human-approved ratio
  const autoApproved = approvedScenarios.filter((s) => s.approvedBy === 'system-auto-approval').length;
  const humanApproved = approvedScenarios.length - autoApproved;

  // Cycle completion rate
  const completionRate = cycles.length > 0
    ? Math.round((completedCycles.length / cycles.length) * 100)
    : 0;

  return (
    <div className="mb-8">
      <h2 className="text-lg font-semibold text-gray-900 mb-3">Financial Impact & Performance</h2>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <MetricCard
          label="Projected Revenue"
          value={totalProjectedRevenue > 0 ? `$${(totalProjectedRevenue / 1000).toFixed(1)}K` : '$0'}
          subtext={`from ${approvedScenarios.length} approved scenarios`}
          trend={totalProjectedRevenue > 0 ? 'up' : 'neutral'}
        />
        <MetricCard
          label="Avg Projected Margin"
          value={avgProjectedMargin > 0 ? `${(avgProjectedMargin * 100).toFixed(1)}%` : '—'}
          subtext="across approved scenarios"
          trend={avgProjectedMargin > 0.15 ? 'up' : 'neutral'}
        />
        <MetricCard
          label="Price Changes Applied"
          value={`${totalPriceChanges}`}
          subtext={`avg ${avgPriceChange >= 0 ? '+' : ''}${avgPriceChange.toFixed(1)}% change`}
          trend={avgPriceChange > 0 ? 'up' : avgPriceChange < 0 ? 'down' : 'neutral'}
        />
        <MetricCard
          label="Automation Rate"
          value={approvedScenarios.length > 0 ? `${Math.round((autoApproved / approvedScenarios.length) * 100)}%` : '—'}
          subtext={`${autoApproved} auto / ${humanApproved} human`}
          trend="neutral"
        />
      </div>

      {/* Secondary metrics row */}
      <div className="grid grid-cols-3 md:grid-cols-6 gap-3 mt-3">
        <MiniMetric label="Total Cycles" value={`${cycles.length}`} />
        <MiniMetric label="Completed" value={`${completedCycles.length}`} />
        <MiniMetric label="Completion Rate" value={`${completionRate}%`} />
        <MiniMetric label="Scenarios Generated" value={`${allScenarios.length}`} />
        <MiniMetric label="Approved" value={`${approvedScenarios.length}`} />
        <MiniMetric label="Products Repriced" value={`${totalPriceChanges}`} />
      </div>

      {/* Charts Row */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mt-4">
        <DonutChart
          title="Approval Distribution"
          segments={[
            { label: 'Auto-approved', value: autoApproved, color: '#10b981' },
            { label: 'Human-approved', value: humanApproved, color: '#3b82f6' },
            { label: 'Rejected', value: allScenarios.filter(s => s.approvalStatus === 'REJECTED').length, color: '#ef4444' },
            { label: 'Awaiting decision', value: allScenarios.filter(s => !s.approvalStatus || s.approvalStatus === 'NONE').length, color: '#d1d5db' },
          ]}
        />
        <DonutChart
          title="Risk Classification"
          segments={[
            { label: 'LOW', value: allScenarios.filter(s => s.riskLevel === 'LOW').length, color: '#10b981' },
            { label: 'MEDIUM', value: allScenarios.filter(s => s.riskLevel === 'MEDIUM').length, color: '#f59e0b' },
            { label: 'HIGH', value: allScenarios.filter(s => s.riskLevel === 'HIGH').length, color: '#ef4444' },
          ]}
        />
        <RevenueByCategoryTree cycles={cycles} />
      </div>

      {/* Scatter Plot - removed per user request */}
    </div>
  );
}

function _computeRevenueByCategory(cycles: CycleData[]) {
  const categoryRevenue: Record<string, number> = {};
  const subcategoryRevenue: Record<string, number> = {};
  const categoryColors: Record<string, string> = {
    'Electronics': '#3b82f6',
    'Grocery': '#10b981',
    'Home & Garden': '#8b5cf6',
    'Individual Products': '#f59e0b',
  };
  const subcategoryColors: Record<string, string> = {
    'Audio': '#60a5fa',
    'Wearables': '#93c5fd',
    'Tablets': '#bfdbfe',
    'Accessories': '#dbeafe',
    'Dairy': '#34d399',
    'Beverages': '#6ee7b7',
    'Bakery': '#a7f3d0',
    'Lighting': '#a78bfa',
    'Appliances': '#c4b5fd',
    'Smart Home': '#ddd6fe',
    'Tools': '#ede9fe',
    'Garden': '#f5f3ff',
    'Bedding': '#e9d5ff',
  };

  for (const cycle of cycles) {
    const group = cycle.pricingGroup ?? '';
    let category: string;
    if (group.startsWith('product-')) {
      category = 'Individual Products';
    } else {
      category = group.split('-')[0] || group;
    }
    const approved = (cycle.scenarios ?? []).filter(s => s.approvalStatus === 'APPROVED');
    const revenue = approved.reduce((sum, s) => sum + (s.projectedRevenue ?? 0), 0);
    categoryRevenue[category] = (categoryRevenue[category] ?? 0) + revenue;

    // Distribute to subcategories using priceChanges product IDs
    for (const scenario of approved) {
      const changes = scenario.priceChanges ?? [];
      const numProducts = changes.length || 1;
      const revenuePerProduct = (scenario.projectedRevenue ?? 0) / numProducts;
      for (const change of changes) {
        const pid = change.productId;
        if (!pid) continue;
        const subCat = _getSubCategory(pid);
        if (subCat) {
          const key = `${category} > ${subCat}`;
          subcategoryRevenue[key] = (subcategoryRevenue[key] ?? 0) + revenuePerProduct;
        }
      }
    }
  }

  // Combine: show categories first, then subcategories indented
  const bars: { label: string; value: number; color: string }[] = [];

  const sortedCategories = Object.entries(categoryRevenue)
    .filter(([, v]) => v > 0)
    .sort((a, b) => b[1] - a[1]);

  for (const [category, value] of sortedCategories) {
    bars.push({
      label: category,
      value,
      color: categoryColors[category] ?? '#6b7280',
    });
    // Add subcategories under this category
    const subEntries = Object.entries(subcategoryRevenue)
      .filter(([key]) => key.startsWith(`${category} > `))
      .sort((a, b) => b[1] - a[1]);
    for (const [subKey, subValue] of subEntries) {
      const subName = subKey.split(' > ')[1];
      bars.push({
        label: `  ${subName}`,
        value: subValue,
        color: subcategoryColors[subName] ?? '#9ca3af',
      });
    }
  }

  return bars;
}

function _getSubCategory(productId: string): string | null {
  const directory: Record<string, string> = {
    'prod-elec-001': 'Audio',
    'prod-elec-002': 'Audio',
    'prod-elec-003': 'Wearables',
    'prod-elec-004': 'Tablets',
    'prod-elec-005': 'Audio',
    'prod-elec-006': 'Accessories',
    'prod-groc-001': 'Dairy',
    'prod-groc-002': 'Beverages',
    'prod-groc-003': 'Bakery',
    'prod-groc-004': 'Dairy',
    'prod-groc-005': 'Dairy',
    'prod-groc-006': 'Beverages',
    'prod-home-001': 'Lighting',
    'prod-home-002': 'Appliances',
    'prod-home-003': 'Appliances',
    'prod-home-004': 'Smart Home',
    'prod-home-005': 'Tools',
    'prod-home-006': 'Garden',
    'prod-home-007': 'Bedding',
  };
  return directory[productId] ?? null;
}

function RevenueByCategoryTree({ cycles }: { cycles: CycleData[] }) {
  const [expanded, setExpanded] = useState<Set<string>>(new Set());

  const tree = _computeRevenueByCategory(cycles);

  interface RevenueNode { label: string; value: number; color: string; children: RevenueNode[] }
  const categoryNodes: RevenueNode[] = [];
  let currentCategory: RevenueNode | null = null;

  for (const bar of tree) {
    if (!bar.label.startsWith('  ')) {
      currentCategory = { label: bar.label, value: bar.value, color: bar.color, children: [] };
      categoryNodes.push(currentCategory);
    } else if (currentCategory) {
      currentCategory.children.push({ label: bar.label.trim(), value: bar.value, color: bar.color, children: [] });
    }
  }

  const toggle = (id: string) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const formatValue = (v: number) => v >= 1000 ? `$${(v / 1000).toFixed(1)}K` : `$${v.toFixed(0)}`;
  const maxValue = Math.max(...categoryNodes.map(n => n.value), 1);

  if (categoryNodes.length === 0) {
    return (
      <div className="bg-white rounded-lg border border-gray-200 shadow-sm p-4">
        <h3 className="text-sm font-semibold text-gray-900 mb-2">Revenue by Category</h3>
        <p className="text-xs text-gray-500">No revenue data yet.</p>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-lg border border-gray-200 shadow-sm p-4">
      <h3 className="text-sm font-semibold text-gray-900 mb-3">Revenue by Category</h3>
      <div className="space-y-1">
        {categoryNodes.map((cat) => (
          <div key={cat.label}>
            <button
              onClick={() => cat.children.length > 0 && toggle(cat.label)}
              className="w-full flex items-center gap-2 py-1.5 px-1 rounded hover:bg-gray-50 transition-colors"
            >
              {cat.children.length > 0 ? (
                <svg className={`w-3 h-3 text-gray-400 transition-transform ${expanded.has(cat.label) ? 'rotate-90' : ''}`} fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M7.21 14.77a.75.75 0 01.02-1.06L11.168 10 7.23 6.29a.75.75 0 111.04-1.08l4.5 4.25a.75.75 0 010 1.08l-4.5 4.25a.75.75 0 01-1.06-.02z" clipRule="evenodd" />
                </svg>
              ) : <span className="w-3" />}
              <span className="text-xs font-semibold text-gray-900 flex-shrink-0">{cat.label}</span>
              <div className="flex-1 mx-2 h-3 bg-gray-100 rounded-full overflow-hidden">
                <div className="h-full rounded-full" style={{ width: `${(cat.value / maxValue) * 100}%`, backgroundColor: cat.color }} />
              </div>
              <span className="text-xs font-medium text-gray-700 flex-shrink-0">{formatValue(cat.value)}</span>
            </button>
            {expanded.has(cat.label) && cat.children.length > 0 && (
              <div className="ml-5 space-y-0.5 pb-1">
                {cat.children.map((sub) => (
                  <div key={sub.label} className="flex items-center gap-2 py-1 px-1">
                    <span className="w-3" />
                    <span className="text-xs text-gray-600 flex-shrink-0">{sub.label}</span>
                    <div className="flex-1 mx-2 h-2 bg-gray-100 rounded-full overflow-hidden">
                      <div className="h-full rounded-full" style={{ width: `${(sub.value / cat.value) * 100}%`, backgroundColor: sub.color }} />
                    </div>
                    <span className="text-xs text-gray-500 flex-shrink-0">{formatValue(sub.value)}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

function MetricCard({ label, value, subtext, trend }: {
  label: string; value: string; subtext: string; trend: 'up' | 'down' | 'neutral';
}) {
  const trendIcon = trend === 'up' ? '↑' : trend === 'down' ? '↓' : '';
  const trendColor = trend === 'up' ? 'text-green-600' : trend === 'down' ? 'text-red-600' : '';

  return (
    <div className="bg-white rounded-lg border border-gray-200 shadow-sm p-4">
      <p className="text-xs text-gray-500 font-medium uppercase tracking-wider">{label}</p>
      <div className="flex items-baseline gap-1 mt-1">
        <p className="text-2xl font-bold text-gray-900">{value}</p>
        {trendIcon && <span className={`text-sm font-medium ${trendColor}`}>{trendIcon}</span>}
      </div>
      <p className="text-[10px] text-gray-500 mt-0.5">{subtext}</p>
    </div>
  );
}

function MiniMetric({ label, value }: { label: string; value: string }) {
  return (
    <div className="bg-gray-50 rounded border border-gray-200 p-2 text-center">
      <p className="text-lg font-bold text-gray-900">{value}</p>
      <p className="text-[9px] text-gray-500 uppercase">{label}</p>
    </div>
  );
}
