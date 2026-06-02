import { useState, useEffect, useCallback } from 'react';
import api from '../lib/api';
import { buildTreeFromCycles, TreeNode } from '../lib/treeAggregation';

function formatRevenue(value: number): string {
  if (value === 0) return '$0';
  if (value >= 1000) return `$${(value / 1000).toFixed(1)}K`;
  return `$${value.toFixed(0)}`;
}

function formatMargin(value: number): string {
  if (value === 0) return '0.0%';
  return `${(value * 100).toFixed(1)}%`;
}

function formatChangePercent(value: number): string {
  if (value === 0) return '0.0%';
  const prefix = value > 0 ? '+' : '';
  return `${prefix}${value.toFixed(1)}%`;
}

function ChevronRight({ className }: { className?: string }) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 20 20"
      fill="currentColor"
      className={className ?? 'w-4 h-4'}
    >
      <path
        fillRule="evenodd"
        d="M7.21 14.77a.75.75 0 01.02-1.06L11.168 10 7.23 6.29a.75.75 0 111.04-1.08l4.5 4.25a.75.75 0 010 1.08l-4.5 4.25a.75.75 0 01-1.06-.02z"
        clipRule="evenodd"
      />
    </svg>
  );
}

function ChevronDown({ className }: { className?: string }) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 20 20"
      fill="currentColor"
      className={className ?? 'w-4 h-4'}
    >
      <path
        fillRule="evenodd"
        d="M5.23 7.21a.75.75 0 011.06.02L10 11.168l3.71-3.938a.75.75 0 111.08 1.04l-4.25 4.5a.75.75 0 01-1.08 0l-4.25-4.5a.75.75 0 01.02-1.06z"
        clipRule="evenodd"
      />
    </svg>
  );
}

function getPaddingClass(level: 'category' | 'subcategory' | 'product'): string {
  switch (level) {
    case 'category':
      return 'pl-4';
    case 'subcategory':
      return 'pl-8';
    case 'product':
      return 'pl-12';
  }
}

function LoadingSkeleton() {
  return (
    <div className="bg-white rounded-lg border border-gray-200 shadow-sm p-6 animate-pulse">
      <div className="h-5 bg-gray-200 rounded w-48 mb-4" />
      <div className="space-y-3">
        {[1, 2, 3, 4, 5].map((i) => (
          <div key={i} className="flex gap-4">
            <div className="h-4 bg-gray-200 rounded w-1/4" />
            <div className="h-4 bg-gray-200 rounded w-1/6" />
            <div className="h-4 bg-gray-200 rounded w-1/6" />
            <div className="h-4 bg-gray-200 rounded w-1/6" />
            <div className="h-4 bg-gray-200 rounded w-1/6" />
          </div>
        ))}
      </div>
    </div>
  );
}

interface TreeRowProps {
  node: TreeNode;
  expanded: Set<string>;
  onToggle: (id: string) => void;
}

function TreeRow({ node, expanded, onToggle }: TreeRowProps) {
  const isExpanded = expanded.has(node.id);
  const hasChildren = node.children.length > 0;
  const paddingClass = getPaddingClass(node.level);

  const levelStyles: Record<string, string> = {
    category: 'font-semibold text-gray-900 bg-gray-50',
    subcategory: 'font-medium text-gray-800',
    product: 'text-gray-600',
  };

  return (
    <>
      <tr
        className={`border-b border-gray-100 hover:bg-blue-50/30 transition-colors ${hasChildren ? 'cursor-pointer' : ''} ${levelStyles[node.level]}`}
        onClick={() => hasChildren && onToggle(node.id)}
      >
        <td className={`py-3 ${paddingClass} pr-4`}>
          <div className="flex items-center gap-1.5">
            {hasChildren ? (
              <span className="text-gray-400 flex-shrink-0">
                {isExpanded ? (
                  <ChevronDown className="w-4 h-4" />
                ) : (
                  <ChevronRight className="w-4 h-4" />
                )}
              </span>
            ) : (
              <span className="w-4 flex-shrink-0" />
            )}
            <span className="truncate">{node.name}</span>
          </div>
        </td>
        <td className="py-3 px-4 text-right tabular-nums">{formatRevenue(node.revenue)}</td>
        <td className="py-3 px-4 text-right tabular-nums">{formatMargin(node.avgMargin)}</td>
        <td className="py-3 px-4 text-right tabular-nums">{node.priceChangesCount}</td>
        <td className="py-3 px-4 text-right tabular-nums">
          <span
            className={
              node.avgChangePercent > 0
                ? 'text-green-600'
                : node.avgChangePercent < 0
                  ? 'text-red-600'
                  : ''
            }
          >
            {formatChangePercent(node.avgChangePercent)}
          </span>
        </td>
      </tr>
      {isExpanded &&
        node.children.map((child) => (
          <TreeRow key={child.id} node={child} expanded={expanded} onToggle={onToggle} />
        ))}
    </>
  );
}

export default function TreeTable() {
  const [tree, setTree] = useState<TreeNode[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<Set<string>>(new Set());

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await api.get('/pricing-cycles');
      const cycles = response.data.cycles ?? [];
      const treeData = buildTreeFromCycles(cycles);
      setTree(treeData);
    } catch {
      setError('Failed to load pricing data. Please try again.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handleToggle = useCallback((id: string) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  }, []);

  if (loading) {
    return <LoadingSkeleton />;
  }

  if (error) {
    return (
      <div className="bg-white rounded-lg border border-gray-200 shadow-sm p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-3">Performance by Category</h2>
        <div className="flex items-center justify-between bg-red-50 border border-red-200 rounded-md p-4">
          <p className="text-sm text-red-700">{error}</p>
          <button
            onClick={fetchData}
            className="ml-4 px-3 py-1.5 text-sm font-medium text-red-700 bg-white border border-red-300 rounded-md hover:bg-red-50 transition-colors"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  if (tree.length === 0) {
    return (
      <div className="bg-white rounded-lg border border-gray-200 shadow-sm p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-3">Performance by Category</h2>
        <p className="text-sm text-gray-500">No pricing data available.</p>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-lg border border-gray-200 shadow-sm overflow-hidden">
      <div className="px-6 py-4 border-b border-gray-200">
        <h2 className="text-lg font-semibold text-gray-900">Performance by Category</h2>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-gray-50 border-b border-gray-200 text-xs uppercase tracking-wider text-gray-500">
              <th className="py-3 pl-4 pr-4 text-left font-medium">Name</th>
              <th className="py-3 px-4 text-right font-medium">Projected Revenue</th>
              <th className="py-3 px-4 text-right font-medium">Avg Margin</th>
              <th className="py-3 px-4 text-right font-medium">Price Changes</th>
              <th className="py-3 px-4 text-right font-medium">Avg Price Change %</th>
            </tr>
          </thead>
          <tbody>
            {tree.map((node) => (
              <TreeRow
                key={node.id}
                node={node}
                expanded={expanded}
                onToggle={handleToggle}
              />
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
