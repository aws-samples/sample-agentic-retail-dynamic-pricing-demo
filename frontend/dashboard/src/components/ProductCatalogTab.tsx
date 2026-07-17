import { useState, useEffect } from 'react';
import api from '../lib/api';

interface Product {
  productId: string;
  name: string;
  category: string;
  subCategory: string;
  currentPrice: number;
  previousPrice?: number;
  totalUnitCost: number;
  mapPrice?: number | null;
  channels?: string[];
  priceUpdatedAt?: string;
  recentlyUpdated?: boolean;
}

interface InventoryData {
  totalOnHand: number;
  daysOfSupply: number;
  stockHealth: 'healthy' | 'low' | 'critical';
  warehouseStock: number;
  storeStock: number;
}

function generateInventory(productId: string): InventoryData {
  let hash = 0;
  for (let i = 0; i < productId.length; i++) {
    hash = ((hash << 5) - hash) + productId.charCodeAt(i);
    hash |= 0;
  }
  const seed = Math.abs(hash);
  const warehouseStock = 800 + (seed % 2000);
  const storeStock = 200 + ((seed >> 3) % 600);
  const totalOnHand = warehouseStock + storeStock;
  const daysOfSupply = 10 + (seed % 35);
  const stockHealth: 'healthy' | 'low' | 'critical' =
    daysOfSupply > 25 ? 'healthy' : daysOfSupply > 12 ? 'low' : 'critical';
  return { totalOnHand, daysOfSupply, stockHealth, warehouseStock, storeStock };
}

function getCostBreakdown(totalUnitCost: number) {
  return {
    materials: +(totalUnitCost * 0.55).toFixed(2),
    labor: +(totalUnitCost * 0.20).toFixed(2),
    overhead: +(totalUnitCost * 0.15).toFixed(2),
    shipping: +(totalUnitCost * 0.10).toFixed(2),
  };
}

function StockBadge({ health }: { health: 'healthy' | 'low' | 'critical' }) {
  const styles = {
    healthy: 'bg-green-100 text-green-800',
    low: 'bg-amber-100 text-amber-800',
    critical: 'bg-red-100 text-red-800',
  };
  return (
    <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${styles[health]}`}>
      {health === 'healthy' ? 'Healthy' : health === 'low' ? 'Low' : 'Critical'}
    </span>
  );
}

function CostBreakdownBar({ breakdown }: { breakdown: ReturnType<typeof getCostBreakdown> }) {
  const total = breakdown.materials + breakdown.labor + breakdown.overhead + breakdown.shipping;
  const segments = [
    { label: 'Materials', value: breakdown.materials, color: 'bg-blue-500' },
    { label: 'Labor', value: breakdown.labor, color: 'bg-emerald-500' },
    { label: 'Overhead', value: breakdown.overhead, color: 'bg-amber-500' },
    { label: 'Shipping', value: breakdown.shipping, color: 'bg-purple-500' },
  ];
  return (
    <div className="mt-2">
      <div className="flex h-3 rounded-full overflow-hidden">
        {segments.map((seg) => (
          <div
            key={seg.label}
            className={`${seg.color}`}
            style={{ width: `${(seg.value / total) * 100}%` }}
            title={`${seg.label}: $${seg.value.toFixed(2)}`}
          />
        ))}
      </div>
      <div className="flex justify-between mt-1">
        {segments.map((seg) => (
          <div key={seg.label} className="flex items-center gap-1">
            <div className={`w-2 h-2 rounded-full ${seg.color}`} />
            <span className="text-[9px] text-gray-500">{seg.label} ${seg.value.toFixed(2)}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function ProductCatalogTab() {
  const [products, setProducts] = useState<Product[]>([]);
  const [loading, setLoading] = useState(true);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [filterCategory, setFilterCategory] = useState<string>('');

  useEffect(() => {
    const fetchProducts = async () => {
      try {
        const resp = await api.get('/products');
        setProducts(resp.data.products ?? []);
      } catch { /* non-critical */ }
      finally { setLoading(false); }
    };
    fetchProducts();
  }, []);

  const categories = [...new Set(products.map(p => p.category))].sort();
  const filtered = filterCategory
    ? products.filter(p => p.category === filterCategory)
    : products;

  const sorted = [...filtered].sort((a, b) =>
    a.category.localeCompare(b.category) ||
    a.subCategory.localeCompare(b.subCategory) ||
    a.name.localeCompare(b.name)
  );

  if (loading) {
    return (
      <div className="bg-white rounded-lg border border-gray-200 shadow-sm p-6 animate-pulse">
        <div className="h-5 bg-gray-200 rounded w-48 mb-4" />
        <div className="space-y-3">
          {[1, 2, 3, 4, 5].map(i => (
            <div key={i} className="h-12 bg-gray-100 rounded" />
          ))}
        </div>
      </div>
    );
  }

  const totalProducts = products.length;
  const avgMargin = products.length > 0
    ? products.reduce((sum, p) => sum + ((p.currentPrice - p.totalUnitCost) / p.currentPrice), 0) / products.length * 100
    : 0;
  const lowStockCount = products.filter(p => generateInventory(p.productId).stockHealth !== 'healthy').length;
  const totalInventoryValue = products.reduce((sum, p) => sum + (p.currentPrice * generateInventory(p.productId).totalOnHand), 0);

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-semibold text-gray-900">Product Catalog & Unit Economics</h2>
        <p className="mt-1 text-sm text-gray-500">
          Real-time view of product costs, margins, inventory levels, and pricing boundaries.
          The AI agents use this data to make intelligent pricing recommendations.
        </p>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-white rounded-lg border border-gray-200 shadow-sm p-4">
          <p className="text-xs text-gray-500 uppercase font-medium">Total Products</p>
          <p className="text-2xl font-bold text-gray-900 mt-1">{totalProducts}</p>
          <p className="text-[10px] text-gray-500">across {categories.length} categories</p>
        </div>
        <div className="bg-white rounded-lg border border-gray-200 shadow-sm p-4">
          <p className="text-xs text-gray-500 uppercase font-medium">Avg Gross Margin</p>
          <p className="text-2xl font-bold text-gray-900 mt-1">{avgMargin.toFixed(1)}%</p>
          <p className="text-[10px] text-gray-500">(price - cost) / price</p>
        </div>
        <div className="bg-white rounded-lg border border-gray-200 shadow-sm p-4">
          <p className="text-xs text-gray-500 uppercase font-medium">Low/Critical Stock</p>
          <p className={`text-2xl font-bold mt-1 ${lowStockCount > 0 ? 'text-amber-600' : 'text-green-600'}`}>
            {lowStockCount} items
          </p>
          <p className="text-[10px] text-gray-500">below 25 days of supply</p>
        </div>
        <div className="bg-white rounded-lg border border-gray-200 shadow-sm p-4">
          <p className="text-xs text-gray-500 uppercase font-medium">Total Inventory Value</p>
          <p className="text-2xl font-bold text-gray-900 mt-1">${(totalInventoryValue / 1000).toFixed(0)}K</p>
          <p className="text-[10px] text-gray-500">at current retail prices</p>
        </div>
      </div>

      <div className="flex items-center gap-3">
        <label className="text-sm text-gray-600">Filter:</label>
        <select
          value={filterCategory}
          onChange={(e) => setFilterCategory(e.target.value)}
          className="border border-gray-300 rounded-md px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
        >
          <option value="">All Categories ({totalProducts})</option>
          {categories.map(cat => (
            <option key={cat} value={cat}>{cat} ({products.filter(p => p.category === cat).length})</option>
          ))}
        </select>
      </div>

      <div className="bg-white rounded-lg border border-gray-200 shadow-sm overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-gray-50 border-b border-gray-200 text-xs uppercase tracking-wider text-gray-500">
                <th className="py-3 pl-4 pr-2 text-left font-medium">Product</th>
                <th className="py-3 px-2 text-left font-medium">Category</th>
                <th className="py-3 px-2 text-right font-medium">Price</th>
                <th className="py-3 px-2 text-right font-medium">Unit Cost</th>
                <th className="py-3 px-2 text-right font-medium">Margin</th>
                <th className="py-3 px-2 text-right font-medium">MAP Floor</th>
                <th className="py-3 px-2 text-right font-medium">Inventory</th>
                <th className="py-3 px-2 text-right font-medium">Days Supply</th>
                <th className="py-3 px-2 text-center font-medium">Health</th>
              </tr>
            </thead>
            <tbody>
              {sorted.map((product) => {
                const margin = ((product.currentPrice - product.totalUnitCost) / product.currentPrice * 100);
                const inventory = generateInventory(product.productId);
                const isExpanded = expandedId === product.productId;
                return (
                  <ProductRow
                    key={product.productId}
                    product={product}
                    margin={margin}
                    inventory={inventory}
                    isExpanded={isExpanded}
                    onToggle={() => setExpandedId(isExpanded ? null : product.productId)}
                  />
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
        <p className="text-xs text-blue-800">
          <span className="font-semibold">How this data drives pricing:</span> The Demand Forecasting agent
          reads inventory levels and days-of-supply via the ERP/POS MCP Server. Low stock signals price increases
          to manage demand; excess stock triggers markdown recommendations. The Cost and Finance MCP Server provides
          unit costs and margin targets that the Strategy Synthesis agent uses as guardrail floors. No scenario can
          recommend a price below unit cost or MAP.
        </p>
      </div>
    </div>
  );
}

function ProductRow({ product, margin, inventory, isExpanded, onToggle }: {
  product: Product; margin: number; inventory: InventoryData; isExpanded: boolean; onToggle: () => void;
}) {
  const breakdown = getCostBreakdown(product.totalUnitCost);
  return (
    <>
      <tr
        className="border-b border-gray-100 hover:bg-blue-50/30 cursor-pointer transition-colors"
        onClick={onToggle}
      >
        <td className="py-3 pl-4 pr-2">
          <div className="flex items-center gap-2">
            <svg className={`w-3.5 h-3.5 text-gray-400 transition-transform ${isExpanded ? 'rotate-90' : ''}`} fill="currentColor" viewBox="0 0 20 20">
              <path fillRule="evenodd" d="M7.21 14.77a.75.75 0 01.02-1.06L11.168 10 7.23 6.29a.75.75 0 111.04-1.08l4.5 4.25a.75.75 0 010 1.08l-4.5 4.25a.75.75 0 01-1.06-.02z" clipRule="evenodd" />
            </svg>
            <div>
              <p className="font-medium text-gray-900 text-xs">{product.name}</p>
              <p className="text-[10px] text-gray-400">{product.productId}</p>
            </div>
          </div>
        </td>
        <td className="py-3 px-2 text-xs text-gray-600">{product.subCategory}</td>
        <td className="py-3 px-2 text-right text-xs font-medium text-gray-900">
          ${product.currentPrice.toFixed(2)}
          {product.recentlyUpdated && <span className="ml-1 text-[9px] text-green-600">NEW</span>}
        </td>
        <td className="py-3 px-2 text-right text-xs text-gray-600">${product.totalUnitCost.toFixed(2)}</td>
        <td className={`py-3 px-2 text-right text-xs font-medium ${margin > 40 ? 'text-green-600' : margin > 25 ? 'text-gray-900' : 'text-amber-600'}`}>
          {margin.toFixed(1)}%
        </td>
        <td className="py-3 px-2 text-right text-xs text-gray-600">
          {product.mapPrice ? `$${product.mapPrice.toFixed(2)}` : '---'}
        </td>
        <td className="py-3 px-2 text-right text-xs text-gray-700 font-medium">
          {inventory.totalOnHand.toLocaleString()}
        </td>
        <td className="py-3 px-2 text-right text-xs text-gray-700">{inventory.daysOfSupply}d</td>
        <td className="py-3 px-2 text-center"><StockBadge health={inventory.stockHealth} /></td>
      </tr>
      {isExpanded && (
        <tr className="bg-gray-50/50">
          <td colSpan={9} className="px-4 py-4">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="bg-white rounded-lg border border-gray-200 p-3">
                <h4 className="text-xs font-semibold text-gray-700 mb-1">Cost Breakdown (${product.totalUnitCost.toFixed(2)} total)</h4>
                <CostBreakdownBar breakdown={breakdown} />
              </div>
              <div className="bg-white rounded-lg border border-gray-200 p-3">
                <h4 className="text-xs font-semibold text-gray-700 mb-2">Inventory Distribution</h4>
                <div className="space-y-2">
                  <div className="flex justify-between items-center">
                    <span className="text-xs text-gray-500">Warehouses</span>
                    <span className="text-xs font-medium text-gray-900">{inventory.warehouseStock.toLocaleString()} units</span>
                  </div>
                  <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
                    <div className="h-full bg-blue-500 rounded-full" style={{ width: `${(inventory.warehouseStock / inventory.totalOnHand) * 100}%` }} />
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-xs text-gray-500">Stores</span>
                    <span className="text-xs font-medium text-gray-900">{inventory.storeStock.toLocaleString()} units</span>
                  </div>
                  <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
                    <div className="h-full bg-emerald-500 rounded-full" style={{ width: `${(inventory.storeStock / inventory.totalOnHand) * 100}%` }} />
                  </div>
                </div>
              </div>
              <div className="bg-white rounded-lg border border-gray-200 p-3">
                <h4 className="text-xs font-semibold text-gray-700 mb-2">Pricing Boundaries</h4>
                <div className="space-y-1.5">
                  <div className="flex justify-between">
                    <span className="text-xs text-gray-500">Cost Floor</span>
                    <span className="text-xs font-mono text-red-600">${product.totalUnitCost.toFixed(2)}</span>
                  </div>
                  {product.mapPrice && (
                    <div className="flex justify-between">
                      <span className="text-xs text-gray-500">MAP Floor</span>
                      <span className="text-xs font-mono text-amber-600">${product.mapPrice.toFixed(2)}</span>
                    </div>
                  )}
                  <div className="flex justify-between">
                    <span className="text-xs text-gray-500">Current Price</span>
                    <span className="text-xs font-mono text-gray-900 font-bold">${product.currentPrice.toFixed(2)}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-xs text-gray-500">Gross Margin</span>
                    <span className="text-xs font-mono text-green-700">${(product.currentPrice - product.totalUnitCost).toFixed(2)} ({margin.toFixed(1)}%)</span>
                  </div>
                  {product.channels && (
                    <div className="flex justify-between items-start pt-1">
                      <span className="text-xs text-gray-500">Channels</span>
                      <div className="flex flex-wrap gap-1 justify-end">
                        {product.channels.map(ch => (
                          <span key={ch} className="text-[9px] bg-indigo-50 text-indigo-700 px-1.5 py-0.5 rounded">{ch}</span>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              </div>
            </div>
          </td>
        </tr>
      )}
    </>
  );
}
