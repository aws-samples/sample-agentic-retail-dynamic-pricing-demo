/**
 * Pure SVG chart components for the Dashboard.
 * No external charting library required — keeps bundle small.
 */

// --- Donut Chart ---

interface DonutSegment {
  label: string;
  value: number;
  color: string;
}

interface DonutChartProps {
  title: string;
  segments: DonutSegment[];
  size?: number;
}

export function DonutChart({ title, segments, size = 140 }: DonutChartProps) {
  const total = segments.reduce((sum, s) => sum + s.value, 0);
  if (total === 0) {
    return (
      <div className="bg-white rounded-lg border border-gray-200 shadow-sm p-4 text-center">
        <p className="text-xs text-gray-500 font-medium uppercase mb-2">{title}</p>
        <p className="text-sm text-gray-400">No data yet</p>
      </div>
    );
  }

  const radius = size / 2 - 10;
  const innerRadius = radius * 0.6;
  const cx = size / 2;
  const cy = size / 2;

  let cumulativeAngle = -90; // Start from top

  const paths = segments.filter(s => s.value > 0).map((segment) => {
    const angle = (segment.value / total) * 360;
    const startAngle = cumulativeAngle;
    const endAngle = cumulativeAngle + angle;
    cumulativeAngle = endAngle;

    const startRad = (startAngle * Math.PI) / 180;
    const endRad = (endAngle * Math.PI) / 180;

    const x1 = cx + radius * Math.cos(startRad);
    const y1 = cy + radius * Math.sin(startRad);
    const x2 = cx + radius * Math.cos(endRad);
    const y2 = cy + radius * Math.sin(endRad);

    const ix1 = cx + innerRadius * Math.cos(startRad);
    const iy1 = cy + innerRadius * Math.sin(startRad);
    const ix2 = cx + innerRadius * Math.cos(endRad);
    const iy2 = cy + innerRadius * Math.sin(endRad);

    const largeArc = angle > 180 ? 1 : 0;

    const d = [
      `M ${x1} ${y1}`,
      `A ${radius} ${radius} 0 ${largeArc} 1 ${x2} ${y2}`,
      `L ${ix2} ${iy2}`,
      `A ${innerRadius} ${innerRadius} 0 ${largeArc} 0 ${ix1} ${iy1}`,
      'Z',
    ].join(' ');

    return { ...segment, d, percentage: Math.round((segment.value / total) * 100) };
  });

  return (
    <div className="bg-white rounded-lg border border-gray-200 shadow-sm p-4">
      <p className="text-xs text-gray-500 font-medium uppercase mb-3 text-center">{title}</p>
      <div className="flex items-center justify-center gap-4">
        <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
          {paths.map((p, i) => (
            <path key={i} d={p.d} fill={p.color} stroke="white" strokeWidth="1.5" />
          ))}
          <text x={cx} y={cy - 4} textAnchor="middle" className="text-lg font-bold fill-gray-900" fontSize="18">
            {total}
          </text>
          <text x={cx} y={cy + 12} textAnchor="middle" className="fill-gray-500" fontSize="9">
            total
          </text>
        </svg>
        <div className="space-y-1.5">
          {paths.map((p, i) => (
            <div key={i} className="flex items-center gap-2">
              <span className="w-2.5 h-2.5 rounded-full flex-shrink-0" style={{ backgroundColor: p.color }} />
              <span className="text-[11px] text-gray-700">{p.label}</span>
              <span className="text-[10px] text-gray-500 ml-auto">{p.percentage}%</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// --- Horizontal Bar Chart ---

interface BarData {
  label: string;
  value: number;
  color: string;
}

interface HorizontalBarChartProps {
  title: string;
  bars: BarData[];
  formatValue?: (v: number) => string;
}

export function HorizontalBarChart({ title, bars, formatValue }: HorizontalBarChartProps) {
  const maxValue = Math.max(...bars.map((b) => b.value), 1);
  const fmt = formatValue ?? ((v: number) => `$${(v / 1000).toFixed(1)}K`);

  if (bars.length === 0 || maxValue === 0) {
    return (
      <div className="bg-white rounded-lg border border-gray-200 shadow-sm p-4">
        <p className="text-xs text-gray-500 font-medium uppercase mb-2">{title}</p>
        <p className="text-sm text-gray-400 text-center py-4">No data yet</p>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-lg border border-gray-200 shadow-sm p-4">
      <p className="text-xs text-gray-500 font-medium uppercase mb-3">{title}</p>
      <div className="space-y-2.5">
        {bars.map((bar, i) => (
          <div key={i}>
            <div className="flex items-center justify-between mb-0.5">
              <span className="text-[11px] text-gray-700 font-medium">{bar.label}</span>
              <span className="text-[11px] text-gray-900 font-semibold">{fmt(bar.value)}</span>
            </div>
            <div className="w-full bg-gray-100 rounded-full h-3">
              <div
                className="h-3 rounded-full transition-all duration-500"
                style={{
                  width: `${(bar.value / maxValue) * 100}%`,
                  backgroundColor: bar.color,
                }}
              />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// --- Scatter Plot ---

interface ScatterPoint {
  x: number; // Revenue
  y: number; // Margin
  label: string;
  color: string;
}

interface ScatterPlotProps {
  title: string;
  points: ScatterPoint[];
  xLabel?: string;
  yLabel?: string;
}

export function ScatterPlot({ title, points, xLabel = 'Revenue', yLabel = 'Margin' }: ScatterPlotProps) {
  const width = 300;
  const height = 180;
  const padding = { top: 15, right: 15, bottom: 30, left: 40 };

  if (points.length === 0) {
    return (
      <div className="bg-white rounded-lg border border-gray-200 shadow-sm p-4">
        <p className="text-xs text-gray-500 font-medium uppercase mb-2">{title}</p>
        <p className="text-sm text-gray-400 text-center py-4">No data yet</p>
      </div>
    );
  }

  const xValues = points.map((p) => p.x);
  const yValues = points.map((p) => p.y);
  const xMin = Math.min(...xValues) * 0.9;
  const xMax = Math.max(...xValues) * 1.1;
  const yMin = Math.min(...yValues) * 0.9;
  const yMax = Math.max(...yValues) * 1.1;

  const plotWidth = width - padding.left - padding.right;
  const plotHeight = height - padding.top - padding.bottom;

  const scaleX = (v: number) => padding.left + ((v - xMin) / (xMax - xMin)) * plotWidth;
  const scaleY = (v: number) => padding.top + plotHeight - ((v - yMin) / (yMax - yMin)) * plotHeight;

  return (
    <div className="bg-white rounded-lg border border-gray-200 shadow-sm p-4">
      <p className="text-xs text-gray-500 font-medium uppercase mb-2">{title}</p>
      <svg width="100%" viewBox={`0 0 ${width} ${height}`} className="overflow-visible">
        {/* Grid lines */}
        {[0.25, 0.5, 0.75].map((frac) => (
          <line
            key={`h-${frac}`}
            x1={padding.left}
            y1={padding.top + plotHeight * frac}
            x2={width - padding.right}
            y2={padding.top + plotHeight * frac}
            stroke="#e5e7eb"
            strokeWidth="0.5"
            strokeDasharray="3,3"
          />
        ))}

        {/* Axes */}
        <line x1={padding.left} y1={padding.top + plotHeight} x2={width - padding.right} y2={padding.top + plotHeight} stroke="#9ca3af" strokeWidth="1" />
        <line x1={padding.left} y1={padding.top} x2={padding.left} y2={padding.top + plotHeight} stroke="#9ca3af" strokeWidth="1" />

        {/* Points */}
        {points.map((point, i) => (
          <g key={i}>
            <circle
              cx={scaleX(point.x)}
              cy={scaleY(point.y)}
              r="6"
              fill={point.color}
              opacity="0.8"
              stroke="white"
              strokeWidth="1.5"
            />
            <title>{`${point.label}\nRevenue: $${(point.x / 1000).toFixed(1)}K\nMargin: ${(point.y * 100).toFixed(1)}%`}</title>
          </g>
        ))}

        {/* Axis labels */}
        <text x={width / 2} y={height - 4} textAnchor="middle" fontSize="9" fill="#6b7280">{xLabel}</text>
        <text x={12} y={height / 2} textAnchor="middle" fontSize="9" fill="#6b7280" transform={`rotate(-90, 12, ${height / 2})`}>{yLabel}</text>
      </svg>

      {/* Legend */}
      <div className="flex flex-wrap gap-2 mt-2 justify-center">
        {points.map((p, i) => (
          <div key={i} className="flex items-center gap-1">
            <span className="w-2 h-2 rounded-full" style={{ backgroundColor: p.color }} />
            <span className="text-[9px] text-gray-600">{p.label}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
