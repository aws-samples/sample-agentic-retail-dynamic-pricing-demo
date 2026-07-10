import { PRODUCT_DIRECTORY } from './productNames';

export interface TreeNode {
  id: string;
  name: string;
  level: 'category' | 'subcategory' | 'product';
  revenue: number;
  avgMargin: number;
  priceChangesCount: number;
  avgChangePercent: number;
  children: TreeNode[];
}

interface PriceChange {
  productId: string;
  currentPrice: number;
  newPrice: number;
  changePercent: number;
}

interface ScenarioData {
  scenarioId: string;
  rank: number;
  projectedRevenue: number;
  projectedMargin: number;
  riskLevel: string;
  approvalStatus?: string;
  approvedBy?: string;
  priceChanges?: PriceChange[];
}

interface CycleData {
  cycleId: string;
  status: string;
  pricingGroup: string;
  scenarioCount: number;
  createdAt: string;
  completedAt?: string;
  scenarios?: ScenarioData[];
}

/**
 * Parses a pricingGroup string into its hierarchy level and components.
 *
 * Rules:
 * - Starts with "product-" → Product leaf (category = "Individual Products")
 * - Contains a dash (but not "product-") → Split on FIRST dash: Category + SubCategory
 * - No dash and not "product-" → Category level only
 *
 * Known categories: Electronics, Grocery, Home & Garden
 * The dash separator only applies between Category and SubCategory segments.
 */
export function parsePricingGroup(pricingGroup: string): {
  level: 'category' | 'subcategory' | 'product';
  category: string;
  subcategory?: string;
  productId?: string;
  productName?: string;
} {
  if (pricingGroup.startsWith('product-')) {
    const rawId = pricingGroup.replace('product-', '');
    const info = PRODUCT_DIRECTORY[rawId];
    if (info) {
      return {
        level: 'product',
        category: info.category,
        subcategory: info.subCategory,
        productId: rawId,
        productName: info.name,
      };
    }
    // Fallback for unknown product IDs
    return {
      level: 'product',
      category: 'Other',
      productId: rawId,
      productName: rawId,
    };
  }

  const dashIndex = pricingGroup.indexOf('-');
  if (dashIndex === -1) {
    return {
      level: 'category',
      category: pricingGroup,
    };
  }

  return {
    level: 'subcategory',
    category: pricingGroup.substring(0, dashIndex),
    subcategory: pricingGroup.substring(dashIndex + 1),
  };
}

/**
 * Aggregates metrics from approved scenarios within a cycle.
 * When distributeByProduct is true, also returns per-product breakdowns.
 */
function aggregateApprovedScenarios(scenarios: ScenarioData[]): {
  revenue: number;
  margins: number[];
  priceChangesCount: number;
  changePercents: number[];
  /** Per-product breakdown from priceChanges (productId -> metrics) */
  productBreakdown: Map<string, { revenue: number; margins: number[]; priceChangesCount: number; changePercents: number[] }>;
} {
  const approved = scenarios.filter((s) => s.approvalStatus === 'APPROVED');

  const revenue = approved.reduce((sum, s) => sum + (s.projectedRevenue ?? 0), 0);
  const margins = approved.map((s) => s.projectedMargin ?? 0);
  const allChanges = approved.flatMap((s) => s.priceChanges ?? []);
  const priceChangesCount = allChanges.length;
  const changePercents = allChanges.map((c) => c.changePercent ?? 0);

  // Build per-product breakdown from priceChanges
  const productBreakdown = new Map<string, { revenue: number; margins: number[]; priceChangesCount: number; changePercents: number[] }>();
  for (const scenario of approved) {
    const changes = scenario.priceChanges ?? [];
    const numProducts = changes.length || 1;
    const revenuePerProduct = (scenario.projectedRevenue ?? 0) / numProducts;
    for (const change of changes) {
      const pid = change.productId;
      if (!pid) continue;
      if (!productBreakdown.has(pid)) {
        productBreakdown.set(pid, { revenue: 0, margins: [], priceChangesCount: 0, changePercents: [] });
      }
      const entry = productBreakdown.get(pid)!;
      entry.revenue += revenuePerProduct;
      entry.margins.push(scenario.projectedMargin ?? 0);
      entry.priceChangesCount += 1;
      entry.changePercents.push(change.changePercent ?? 0);
    }
  }

  return { revenue, margins, priceChangesCount, changePercents, productBreakdown };
}

/**
 * Transforms flat cycle data into a hierarchical tree structure.
 *
 * Aggregation rules:
 * - revenue = sum of projectedRevenue from approved scenarios
 * - avgMargin = average of projectedMargin from approved scenarios
 * - priceChangesCount = total count of priceChanges from approved scenarios
 * - avgChangePercent = average of all changePercent values from approved scenarios
 * - Parent nodes aggregate from their children
 * - Categories are sorted alphabetically
 */
export function buildTreeFromCycles(cycles: CycleData[]): TreeNode[] {
  // Maps for building the tree
  const categoryMap = new Map<string, {
    subcategories: Map<string, {
      products: Map<string, { revenue: number; margins: number[]; priceChangesCount: number; changePercents: number[] }>;
      revenue: number;
      margins: number[];
      priceChangesCount: number;
      changePercents: number[];
    }>;
    directRevenue: number;
    directMargins: number[];
    directPriceChangesCount: number;
    directChangePercents: number[];
  }>();

  for (const cycle of cycles) {
    const parsed = parsePricingGroup(cycle.pricingGroup ?? '');
    const metrics = aggregateApprovedScenarios(cycle.scenarios ?? []);

    // Ensure category exists
    if (!categoryMap.has(parsed.category)) {
      categoryMap.set(parsed.category, {
        subcategories: new Map(),
        directRevenue: 0,
        directMargins: [],
        directPriceChangesCount: 0,
        directChangePercents: [],
      });
    }
    const categoryEntry = categoryMap.get(parsed.category)!;

    if (parsed.level === 'category') {
      // Category-level cycle: distribute priceChanges to subcategory/product nodes
      // using PRODUCT_DIRECTORY lookup for each productId
      if (metrics.productBreakdown.size > 0) {
        for (const [productId, productMetrics] of metrics.productBreakdown) {
          const productInfo = PRODUCT_DIRECTORY[productId];
          const subName = productInfo?.subCategory ?? 'Other';

          if (!categoryEntry.subcategories.has(subName)) {
            categoryEntry.subcategories.set(subName, {
              products: new Map(),
              revenue: 0,
              margins: [],
              priceChangesCount: 0,
              changePercents: [],
            });
          }
          const subEntry = categoryEntry.subcategories.get(subName)!;

          // Add to subcategory totals
          subEntry.revenue += productMetrics.revenue;
          subEntry.margins.push(...productMetrics.margins);
          subEntry.priceChangesCount += productMetrics.priceChangesCount;
          subEntry.changePercents.push(...productMetrics.changePercents);

          // Add product node
          if (!subEntry.products.has(productId)) {
            subEntry.products.set(productId, { revenue: 0, margins: [], priceChangesCount: 0, changePercents: [] });
          }
          const prodEntry = subEntry.products.get(productId)!;
          prodEntry.revenue += productMetrics.revenue;
          prodEntry.margins.push(...productMetrics.margins);
          prodEntry.priceChangesCount += productMetrics.priceChangesCount;
          prodEntry.changePercents.push(...productMetrics.changePercents);
        }
      } else {
        // No priceChanges detail - fall back to direct aggregation
        categoryEntry.directRevenue += metrics.revenue;
        categoryEntry.directMargins.push(...metrics.margins);
        categoryEntry.directPriceChangesCount += metrics.priceChangesCount;
        categoryEntry.directChangePercents.push(...metrics.changePercents);
      }
    } else if (parsed.level === 'subcategory') {
      const subName = parsed.subcategory!;
      if (!categoryEntry.subcategories.has(subName)) {
        categoryEntry.subcategories.set(subName, {
          products: new Map(),
          revenue: 0,
          margins: [],
          priceChangesCount: 0,
          changePercents: [],
        });
      }
      const subEntry = categoryEntry.subcategories.get(subName)!;
      subEntry.revenue += metrics.revenue;
      subEntry.margins.push(...metrics.margins);
      subEntry.priceChangesCount += metrics.priceChangesCount;
      subEntry.changePercents.push(...metrics.changePercents);
    } else if (parsed.level === 'product') {
      // Product-level → place under real category and subcategory
      const subName = parsed.subcategory ?? 'Other';
      if (!categoryEntry.subcategories.has(subName)) {
        categoryEntry.subcategories.set(subName, {
          products: new Map(),
          revenue: 0,
          margins: [],
          priceChangesCount: 0,
          changePercents: [],
        });
      }
      const subEntry = categoryEntry.subcategories.get(subName)!;
      subEntry.revenue += metrics.revenue;
      subEntry.margins.push(...metrics.margins);
      subEntry.priceChangesCount += metrics.priceChangesCount;
      subEntry.changePercents.push(...metrics.changePercents);
    }
  }

  // Build the tree nodes
  const result: TreeNode[] = [];

  for (const [categoryName, categoryEntry] of categoryMap) {
    const children: TreeNode[] = [];

    // Add subcategory children
    for (const [subName, subEntry] of categoryEntry.subcategories) {
      // Build product children for this subcategory
      const productChildren: TreeNode[] = [];
      for (const [productId, prodMetrics] of subEntry.products) {
        const productInfo = PRODUCT_DIRECTORY[productId];
        productChildren.push({
          id: `${categoryName}-${subName}-${productId}`,
          name: productInfo?.name ?? productId,
          level: 'product',
          revenue: prodMetrics.revenue,
          avgMargin: prodMetrics.margins.length > 0
            ? prodMetrics.margins.reduce((a, b) => a + b, 0) / prodMetrics.margins.length
            : 0,
          priceChangesCount: prodMetrics.priceChangesCount,
          avgChangePercent: prodMetrics.changePercents.length > 0
            ? prodMetrics.changePercents.reduce((a, b) => a + b, 0) / prodMetrics.changePercents.length
            : 0,
          children: [],
        });
      }
      // Sort products alphabetically
      productChildren.sort((a, b) => a.name.localeCompare(b.name));

      children.push({
        id: `${categoryName}-${subName}`,
        name: subName,
        level: 'subcategory',
        revenue: subEntry.revenue,
        avgMargin: subEntry.margins.length > 0
          ? subEntry.margins.reduce((a, b) => a + b, 0) / subEntry.margins.length
          : 0,
        priceChangesCount: subEntry.priceChangesCount,
        avgChangePercent: subEntry.changePercents.length > 0
          ? subEntry.changePercents.reduce((a, b) => a + b, 0) / subEntry.changePercents.length
          : 0,
        children: productChildren,
      });
    }

    // Sort subcategories alphabetically
    children.sort((a, b) => a.name.localeCompare(b.name));

    // Aggregate category metrics: sum of children + direct metrics
    const allMargins = [
      ...categoryEntry.directMargins,
      ...Array.from(categoryEntry.subcategories.values()).flatMap((s) => s.margins),
    ];
    const allChangePercents = [
      ...categoryEntry.directChangePercents,
      ...Array.from(categoryEntry.subcategories.values()).flatMap((s) => s.changePercents),
    ];
    const totalRevenue = categoryEntry.directRevenue +
      Array.from(categoryEntry.subcategories.values()).reduce((sum, s) => sum + s.revenue, 0);
    const totalPriceChanges = categoryEntry.directPriceChangesCount +
      Array.from(categoryEntry.subcategories.values()).reduce((sum, s) => sum + s.priceChangesCount, 0);

    result.push({
      id: categoryName,
      name: categoryName,
      level: 'category',
      revenue: totalRevenue,
      avgMargin: allMargins.length > 0
        ? allMargins.reduce((a, b) => a + b, 0) / allMargins.length
        : 0,
      priceChangesCount: totalPriceChanges,
      avgChangePercent: allChangePercents.length > 0
        ? allChangePercents.reduce((a, b) => a + b, 0) / allChangePercents.length
        : 0,
      children,
    });
  }

  // Sort categories alphabetically
  result.sort((a, b) => a.name.localeCompare(b.name));

  return result;
}
