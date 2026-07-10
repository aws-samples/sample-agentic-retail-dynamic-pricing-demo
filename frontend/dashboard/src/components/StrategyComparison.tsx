export default function StrategyComparison() {
  return (
    <div className="bg-white rounded-lg border border-gray-200 shadow-sm p-5 space-y-5">
      <div>
        <h3 className="text-sm font-semibold text-gray-900 mb-1">How Pricing Scenarios Are Generated</h3>
        <p className="text-xs text-gray-600">
          Each pricing cycle generates 5 ranked scenarios. The selected <strong>objective</strong> sets the price direction,
          and each <strong>strategy</strong> applies a different level of aggressiveness within that direction.
        </p>
      </div>

      {/* Objective to Direction Mapping */}
      <div>
        <h4 className="text-xs font-semibold text-gray-700 mb-2">Step 1: Objective Sets the Direction</h4>
        <div className="grid grid-cols-2 gap-2">
          <div className="border border-green-200 bg-green-50 rounded-lg p-2.5">
            <p className="text-xs font-semibold text-green-800">Revenue Maximization</p>
            <p className="text-[10px] text-green-700 mt-0.5">All strategies shift toward price <strong>increases</strong> to capture more revenue per unit</p>
          </div>
          <div className="border border-blue-200 bg-blue-50 rounded-lg p-2.5">
            <p className="text-xs font-semibold text-blue-800">Market Share Growth</p>
            <p className="text-[10px] text-blue-700 mt-0.5">All strategies shift toward price <strong>decreases</strong> to attract more volume</p>
          </div>
          <div className="border border-purple-200 bg-purple-50 rounded-lg p-2.5">
            <p className="text-xs font-semibold text-purple-800">Margin Protection</p>
            <p className="text-[10px] text-purple-700 mt-0.5">All strategies shift toward price <strong>increases</strong> to protect per-unit profit</p>
          </div>
          <div className="border border-amber-200 bg-amber-50 rounded-lg p-2.5">
            <p className="text-xs font-semibold text-amber-800">Competitive Positioning</p>
            <p className="text-[10px] text-amber-700 mt-0.5">All strategies shift toward <strong>matching/undercutting</strong> competitor prices</p>
          </div>
        </div>
      </div>

      {/* Strategy to Aggressiveness Mapping */}
      <div>
        <h4 className="text-xs font-semibold text-gray-700 mb-2">Step 2: Strategies Vary the Aggressiveness</h4>
        <div className="overflow-hidden border border-gray-200 rounded-lg">
          <table className="min-w-full divide-y divide-gray-200 text-xs">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-3 py-2 text-left font-medium text-gray-500 uppercase">Rank</th>
                <th className="px-3 py-2 text-left font-medium text-gray-500 uppercase">Strategy</th>
                <th className="px-3 py-2 text-left font-medium text-gray-500 uppercase">Approach</th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              <tr>
                <td className="px-3 py-2 font-bold text-gray-900">1</td>
                <td className="px-3 py-2 font-medium text-gray-900">Aggressive Growth</td>
                <td className="px-3 py-2 text-gray-700">Largest price move in the direction of the objective</td>
              </tr>
              <tr>
                <td className="px-3 py-2 font-bold text-gray-900">2</td>
                <td className="px-3 py-2 font-medium text-gray-900">Market Share Capture</td>
                <td className="px-3 py-2 text-gray-700">Large move, volume-focused</td>
              </tr>
              <tr>
                <td className="px-3 py-2 font-bold text-gray-900">3</td>
                <td className="px-3 py-2 font-medium text-gray-900">Balanced Optimization</td>
                <td className="px-3 py-2 text-gray-700">Moderate adjustment balancing all factors</td>
              </tr>
              <tr>
                <td className="px-3 py-2 font-bold text-gray-900">4</td>
                <td className="px-3 py-2 font-medium text-gray-900">Margin Protection</td>
                <td className="px-3 py-2 text-gray-700">Moderate, profit-preserving adjustment</td>
              </tr>
              <tr>
                <td className="px-3 py-2 font-bold text-gray-900">5</td>
                <td className="px-3 py-2 font-medium text-gray-900">Conservative Protection</td>
                <td className="px-3 py-2 text-gray-700">Minimal move that still achieves the objective</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      {/* Risk Classification */}
      <div>
        <h4 className="text-xs font-semibold text-gray-700 mb-2">Step 3: Risk Assigned by Relative Price Impact</h4>
        <p className="text-[10px] text-gray-600 mb-2">
          Risk is not fixed per strategy name. It is computed by comparing the actual price change magnitude across all 5 scenarios in the batch:
        </p>
        <div className="overflow-hidden border border-gray-200 rounded-lg">
          <table className="min-w-full divide-y divide-gray-200 text-xs">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-3 py-2 text-left font-medium text-gray-500 uppercase">Risk</th>
                <th className="px-3 py-2 text-left font-medium text-gray-500 uppercase">Assignment Rule</th>
                <th className="px-3 py-2 text-left font-medium text-gray-500 uppercase">Approval Path</th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              <tr className="bg-green-50/50">
                <td className="px-3 py-2"><span className="px-1.5 py-0.5 rounded bg-green-100 text-green-700 font-medium">LOW</span></td>
                <td className="px-3 py-2 text-gray-700">Scenario with the smallest price change in the batch (unless it exceeds 20%)</td>
                <td className="px-3 py-2 text-green-700 font-medium">Auto-approved (STP)</td>
              </tr>
              <tr>
                <td className="px-3 py-2"><span className="px-1.5 py-0.5 rounded bg-yellow-100 text-yellow-700 font-medium">MEDIUM</span></td>
                <td className="px-3 py-2 text-gray-700">Middle-range scenarios (moderate price impact relative to the batch)</td>
                <td className="px-3 py-2 text-gray-600">Human review</td>
              </tr>
              <tr>
                <td className="px-3 py-2"><span className="px-1.5 py-0.5 rounded bg-red-100 text-red-700 font-medium">HIGH</span></td>
                <td className="px-3 py-2 text-gray-700">Scenarios with the largest price changes in the batch</td>
                <td className="px-3 py-2 text-gray-600">Human + 50-char justification</td>
              </tr>
            </tbody>
          </table>
        </div>
        <p className="text-[10px] text-gray-500 mt-2">
          This means the same strategy (e.g., Conservative Protection) might be LOW risk in one context and MEDIUM in another — depending on how much price movement the objectives and constraints produce. The system always ensures at least one STP-eligible option exists per cycle.
        </p>
      </div>

      {/* Key Insight */}
      <div className="bg-indigo-50 border border-indigo-200 rounded-lg p-3">
        <p className="text-xs text-indigo-800">
          <span className="font-semibold">Key insight:</span> The objective determines <em>which direction</em> prices move.
          The strategy determines <em>how far</em>. A Product Manager picks the objective (what they want to achieve),
          then chooses from 5 options representing different risk appetites — from aggressive moves requiring executive
          justification to safe changes that execute autonomously.
        </p>
      </div>

      {/* Example */}
      <div>
        <h4 className="text-xs font-semibold text-gray-700 mb-2">Example: Same 5 Strategies, Different Objectives</h4>
        <div className="grid grid-cols-2 gap-3">
          <div className="border border-gray-200 rounded-lg p-3">
            <p className="text-xs font-semibold text-gray-800 mb-1">Objective: Revenue Maximization</p>
            <div className="space-y-0.5 text-[10px] text-gray-600">
              <p>1. Aggressive Growth: <span className="font-medium text-green-700">+18%</span></p>
              <p>2. Market Share Capture: <span className="font-medium text-green-700">+12%</span></p>
              <p>3. Balanced Optimization: <span className="font-medium text-green-700">+7%</span></p>
              <p>4. Margin Protection: <span className="font-medium text-green-700">+5%</span></p>
              <p>5. Conservative Protection: <span className="font-medium text-green-700">+2%</span></p>
            </div>
          </div>
          <div className="border border-gray-200 rounded-lg p-3">
            <p className="text-xs font-semibold text-gray-800 mb-1">Objective: Market Share Growth</p>
            <div className="space-y-0.5 text-[10px] text-gray-600">
              <p>1. Aggressive Growth: <span className="font-medium text-red-700">-18%</span></p>
              <p>2. Market Share Capture: <span className="font-medium text-red-700">-14%</span></p>
              <p>3. Balanced Optimization: <span className="font-medium text-red-700">-7%</span></p>
              <p>4. Margin Protection: <span className="font-medium text-amber-700">-3%</span></p>
              <p>5. Conservative Protection: <span className="font-medium text-red-700">-1%</span></p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
