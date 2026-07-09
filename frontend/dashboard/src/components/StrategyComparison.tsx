export default function StrategyComparison() {
  return (
    <div className="bg-white rounded-lg border border-gray-200 shadow-sm p-5">
      <h3 className="text-sm font-semibold text-gray-900 mb-3">Strategy Comparison</h3>
      <p className="text-xs text-gray-600 mb-4">
        Each pricing cycle generates 5 scenarios with different strategies. Here's how they compare:
      </p>
      <div className="overflow-hidden border border-gray-200 rounded-lg">
        <table className="min-w-full divide-y divide-gray-200 text-xs">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-3 py-2 text-left font-medium text-gray-500 uppercase">Strategy</th>
              <th className="px-3 py-2 text-left font-medium text-gray-500 uppercase">Approach</th>
              <th className="px-3 py-2 text-left font-medium text-gray-500 uppercase">Risk Level</th>
              <th className="px-3 py-2 text-left font-medium text-gray-500 uppercase">Price Direction</th>
              <th className="px-3 py-2 text-left font-medium text-gray-500 uppercase">Best For</th>
              <th className="px-3 py-2 text-left font-medium text-gray-500 uppercase">Approval</th>
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-gray-200">
            <tr>
              <td className="px-3 py-2 font-medium text-gray-900">Aggressive Growth</td>
              <td className="px-3 py-2 text-gray-700">Maximize revenue through higher prices where demand supports it</td>
              <td className="px-3 py-2"><span className="px-1.5 py-0.5 rounded bg-red-100 text-red-700 font-medium">HIGH</span></td>
              <td className="px-3 py-2 text-green-700 font-medium">↑ Increase</td>
              <td className="px-3 py-2 text-gray-600">Viral demand, low competition</td>
              <td className="px-3 py-2 text-gray-600">Human required (≥50 char justification)</td>
            </tr>
            <tr>
              <td className="px-3 py-2 font-medium text-gray-900">Balanced Optimization</td>
              <td className="px-3 py-2 text-gray-700">Balance revenue and margin with moderate adjustments</td>
              <td className="px-3 py-2"><span className="px-1.5 py-0.5 rounded bg-yellow-100 text-yellow-700 font-medium">MEDIUM</span></td>
              <td className="px-3 py-2 text-gray-700 font-medium">↕ Mixed</td>
              <td className="px-3 py-2 text-gray-600">Stable markets, general optimization</td>
              <td className="px-3 py-2 text-gray-600">Human review</td>
            </tr>
            <tr>
              <td className="px-3 py-2 font-medium text-gray-900">Conservative Protection</td>
              <td className="px-3 py-2 text-gray-700">Minimal, safe adjustments aligned with primary objective</td>
              <td className="px-3 py-2"><span className="px-1.5 py-0.5 rounded bg-green-100 text-green-700 font-medium">LOW</span></td>
              <td className="px-3 py-2 text-gray-700 font-medium">↕ Context-driven</td>
              <td className="px-3 py-2 text-gray-600">Safe default, STP auto-approved</td>
              <td className="px-3 py-2 text-green-700 font-medium">⚡ Auto-approved</td>
            </tr>
          </tbody>
        </table>
      </div>
      <p className="text-[10px] text-gray-500 mt-3">
        The AI generates all 5 strategies for every cycle. The system auto-approves LOW risk scenarios (straight-through processing)
        while routing MEDIUM and HIGH risk to human decision-makers with full context and rationale.
      </p>
    </div>
  );
}
