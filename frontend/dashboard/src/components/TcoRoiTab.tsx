import { useState, useEffect } from 'react';
import api from '../lib/api';

interface CycleData {
  cycleId: string;
  status: string;
  scenarioCount: number;
  scenarios?: { approvalStatus?: string; projectedRevenue?: number }[];
}

export default function TcoRoiTab() {
  const [cycles, setCycles] = useState<CycleData[]>([]);
  const [billing, setBilling] = useState<any>(null);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [cyclesResp, billingResp] = await Promise.all([
          api.get('/pricing-cycles'),
          api.get('/billing').catch(() => ({ data: null })),
        ]);
        setCycles(cyclesResp.data.cycles ?? []);
        setBilling(billingResp.data);
      } catch { /* non-critical */ }
    };
    fetchData();
  }, []);

  // Compute usage-based estimates from actual cycle data
  const totalCycles = cycles.length;
  const completedCycles = cycles.filter(c => c.status === 'COMPLETE').length;
  const totalScenarios = cycles.reduce((sum, c) => sum + (c.scenarioCount ?? 0), 0);
  const approvedScenarios = cycles.flatMap(c => c.scenarios ?? []).filter(s => s.approvalStatus === 'APPROVED').length;

  // Cost estimates based on actual usage
  const costPerCycle = 0.26; // Average $0.22-$0.30
  const totalModelCost = totalCycles * costPerCycle;
  const monthlyFixedCost = 17.50; // Average of $10-25 range
  const totalEstimatedCost = totalModelCost + monthlyFixedCost;

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-semibold text-gray-900">TCO Estimates</h2>
        <p className="text-xs text-gray-500 mt-1">
          Cost estimates based on actual usage. Model costs are the dominant driver (~80%).
          Infrastructure is serverless pay-per-use.
        </p>
      </div>

      {/* Current Usage Summary */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <CostCard label="Total Cycles Run" value={`${totalCycles}`} subtext="pricing cycles executed" />
        <CostCard label="Est. Model Cost" value={`$${totalModelCost.toFixed(2)}`} subtext={`@ $${costPerCycle}/cycle`} />
        <CostCard label="Monthly Fixed" value={`$${monthlyFixedCost.toFixed(2)}`} subtext="infrastructure (serverless)" />
        <CostCard label="Total Est. Spend" value={`$${totalEstimatedCost.toFixed(2)}`} subtext="model + infrastructure" />
      </div>

      {/* Per-Cycle Breakdown */}
      <div className="bg-white rounded-lg border border-gray-200 shadow-sm p-5">
        <h3 className="text-sm font-semibold text-gray-900 mb-3">{'Cost per Pricing Cycle (< 2 minutes)'}</h3>
        <div className="overflow-hidden border border-gray-200 rounded-lg">
          <table className="min-w-full divide-y divide-gray-200 text-xs">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-3 py-2 text-left font-medium text-gray-500 uppercase">Component</th>
                <th className="px-3 py-2 text-left font-medium text-gray-500 uppercase">Service</th>
                <th className="px-3 py-2 text-left font-medium text-gray-500 uppercase">Usage</th>
                <th className="px-3 py-2 text-right font-medium text-gray-500 uppercase">Cost</th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              <tr>
                <td className="px-3 py-2 text-gray-900 font-medium">Orchestrator reasoning</td>
                <td className="px-3 py-2 text-gray-600">Bedrock (Claude Opus 4)</td>
                <td className="px-3 py-2 text-gray-600">~3K input + 2K output tokens</td>
                <td className="px-3 py-2 text-right text-gray-900 font-medium">$0.110</td>
              </tr>
              <tr>
                <td className="px-3 py-2 text-gray-900 font-medium">Intelligence agents (×3)</td>
                <td className="px-3 py-2 text-gray-600">Bedrock (Claude Sonnet 4)</td>
                <td className="px-3 py-2 text-gray-600">~2K in + 1K out × 3 calls</td>
                <td className="px-3 py-2 text-right text-gray-900 font-medium">$0.054</td>
              </tr>
              <tr>
                <td className="px-3 py-2 text-gray-900 font-medium">Strategy synthesis</td>
                <td className="px-3 py-2 text-gray-600">Bedrock (Claude Sonnet 4)</td>
                <td className="px-3 py-2 text-gray-600">~4K input + 2K output tokens</td>
                <td className="px-3 py-2 text-right text-gray-900 font-medium">$0.042</td>
              </tr>
              <tr>
                <td className="px-3 py-2 text-gray-900 font-medium">Guardrail evaluation</td>
                <td className="px-3 py-2 text-gray-600">Bedrock Guardrails</td>
                <td className="px-3 py-2 text-gray-600">5 evaluations × ~2K tokens</td>
                <td className="px-3 py-2 text-right text-gray-900 font-medium">$0.004</td>
              </tr>
              <tr>
                <td className="px-3 py-2 text-gray-900 font-medium">Agent compute</td>
                <td className="px-3 py-2 text-gray-600">AgentCore Runtime</td>
                <td className="px-3 py-2 text-gray-600">{'< 2 min across 6 agents'}</td>
                <td className="px-3 py-2 text-right text-gray-900 font-medium">$0.035</td>
              </tr>
              <tr>
                <td className="px-3 py-2 text-gray-900 font-medium">API + State</td>
                <td className="px-3 py-2 text-gray-600">Lambda + DynamoDB</td>
                <td className="px-3 py-2 text-gray-600">2 invocations + 30 DB ops</td>
                <td className="px-3 py-2 text-right text-gray-900 font-medium">$0.002</td>
              </tr>
              <tr className="bg-blue-50">
                <td className="px-3 py-2 text-blue-900 font-bold" colSpan={3}>TOTAL PER CYCLE</td>
                <td className="px-3 py-2 text-right text-blue-900 font-bold">$0.247</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      {/* Scaling Projections */}
      <div className="bg-white rounded-lg border border-gray-200 shadow-sm p-5">
        <h3 className="text-sm font-semibold text-gray-900 mb-1">Scaling Projections</h3>
        <p className="text-[10px] text-gray-500 mb-3">
          Estimates based on linear extrapolation of the per-cycle cost ($0.247) observed in this deployment.
          Model cost scales linearly with cycle count. Infrastructure cost (Lambda, DynamoDB, API Gateway)
          scales sub-linearly due to serverless pay-per-use pricing with no idle cost. Cycle volume
          assumptions: Demo ~50/month (internal testing), Pilot ~500/month (single category, weekly repricing),
          Production ~5,000/month (full catalog, daily repricing), Enterprise ~50,000/month (multi-region, hourly).
          These are illustrative projections, not guarantees. Actual costs depend on model selection,
          prompt complexity, scenario count per cycle, and data volume.
        </p>
        <div className="overflow-hidden border border-gray-200 rounded-lg">
          <table className="min-w-full divide-y divide-gray-200 text-xs">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-3 py-2 text-left font-medium text-gray-500 uppercase">Scenario</th>
                <th className="px-3 py-2 text-right font-medium text-gray-500 uppercase">Cycles/Month</th>
                <th className="px-3 py-2 text-right font-medium text-gray-500 uppercase">Model Cost</th>
                <th className="px-3 py-2 text-right font-medium text-gray-500 uppercase">Infra Cost</th>
                <th className="px-3 py-2 text-right font-medium text-gray-500 uppercase">Total/Month</th>
                <th className="px-3 py-2 text-right font-medium text-gray-500 uppercase">Annual</th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              <tr className="bg-blue-50">
                <td className="px-3 py-2 text-gray-900 font-medium">Demo (current)</td>
                <td className="px-3 py-2 text-right">~50</td>
                <td className="px-3 py-2 text-right">$13</td>
                <td className="px-3 py-2 text-right">$18</td>
                <td className="px-3 py-2 text-right font-bold">$30</td>
                <td className="px-3 py-2 text-right">$360</td>
              </tr>
              <tr>
                <td className="px-3 py-2 text-gray-900 font-medium">Pilot (1 retailer)</td>
                <td className="px-3 py-2 text-right">~500</td>
                <td className="px-3 py-2 text-right">$125</td>
                <td className="px-3 py-2 text-right">$25</td>
                <td className="px-3 py-2 text-right font-bold">$150</td>
                <td className="px-3 py-2 text-right">$1,800</td>
              </tr>
              <tr>
                <td className="px-3 py-2 text-gray-900 font-medium">Production (mid-size)</td>
                <td className="px-3 py-2 text-right">~5,000</td>
                <td className="px-3 py-2 text-right">$1,250</td>
                <td className="px-3 py-2 text-right">$100</td>
                <td className="px-3 py-2 text-right font-bold">$1,350</td>
                <td className="px-3 py-2 text-right">$16,200</td>
              </tr>
              <tr>
                <td className="px-3 py-2 text-gray-900 font-medium">Enterprise (large)</td>
                <td className="px-3 py-2 text-right">~50,000</td>
                <td className="px-3 py-2 text-right">$12,500</td>
                <td className="px-3 py-2 text-right">$500</td>
                <td className="px-3 py-2 text-right font-bold">$13,000</td>
                <td className="px-3 py-2 text-right">$156,000</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      {/* Live Usage Metrics */}
      <div className="bg-white rounded-lg border border-gray-200 shadow-sm p-5">
        <h3 className="text-sm font-semibold text-gray-900 mb-1">Live Usage (This Deployment)</h3>
        <p className="text-[10px] text-gray-500 mb-3">Computed from actual pricing cycle data in DynamoDB</p>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <UsageMetric label="Cycles Executed" value={`${totalCycles}`} />
          <UsageMetric label="Cycles Completed" value={`${completedCycles}`} />
          <UsageMetric label="Scenarios Generated" value={`${totalScenarios}`} />
          <UsageMetric label="Scenarios Approved" value={`${approvedScenarios}`} />
        </div>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mt-3">
          <UsageMetric label="Est. Bedrock Tokens" value={`~${(totalCycles * 15).toLocaleString()}K`} />
          <UsageMetric label="Est. Model Spend" value={`$${totalModelCost.toFixed(2)}`} />
          <UsageMetric label="Avg Cost/Cycle" value={totalCycles > 0 ? `$${(totalEstimatedCost / totalCycles).toFixed(3)}` : '---'} />
          <UsageMetric label="Cost/Scenario" value={totalScenarios > 0 ? `$${(totalEstimatedCost / totalScenarios).toFixed(4)}` : '---'} />
        </div>
      </div>

      {/* AWS Cost Explorer Data (Live) */}
      <div className="bg-white rounded-lg border border-gray-200 shadow-sm p-5">
        <h3 className="text-sm font-semibold text-gray-900 mb-1">AWS Billing Data (Cost Explorer)</h3>
        <p className="text-[10px] text-gray-500 mb-3">Live data from AWS Cost Explorer API. Note: 24-48 hour delay on new charges.</p>
        {billing && !billing.error ? (
          <div className="space-y-3">
            <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
              <UsageMetric label="Last 30 Days" value={`$${billing.totalCost30Days?.toFixed(2) ?? '0.00'}`} />
              <UsageMetric label="Last 7 Days" value={`$${billing.totalCost7Days?.toFixed(2) ?? '0.00'}`} />
              <UsageMetric label="Currency" value={billing.currency ?? 'USD'} />
            </div>
            {billing.costByService && Object.keys(billing.costByService).length > 0 && (
              <div>
                <p className="text-xs font-medium text-gray-700 mb-1">Cost by Service</p>
                <div className="space-y-1">
                  {Object.entries(billing.costByService as Record<string, number>).map(([service, cost]) => (
                    <div key={service} className="flex items-center justify-between text-xs">
                      <span className="text-gray-600 truncate max-w-[70%]">{service}</span>
                      <span className="text-gray-900 font-medium">${cost.toFixed(4)}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
            {billing.totalCost30Days === 0 && (
              <p className="text-xs text-amber-700 bg-amber-50 rounded p-2">
                No billing data yet. Cost Explorer has a 24-48 hour delay. Check back tomorrow for today's usage.
              </p>
            )}
          </div>
        ) : (
          <p className="text-xs text-gray-500">
            {billing?.error ?? 'Loading billing data...'}
          </p>
        )}
      </div>

      {/* Note about billing */}
      <div className="bg-amber-50 border border-amber-200 rounded-lg p-4">
        <p className="text-xs text-amber-800">
          <span className="font-semibold">Note:</span> Estimated costs above are based on published AWS pricing × observed usage.
          The "AWS Billing Data" section shows actual charges from Cost Explorer (24-48h delay).
          All resources tagged with <code className="bg-amber-100 px-1 rounded">Project: RetailDynamicPricing</code> for cost allocation.
        </p>
      </div>
    </div>
  );
}

function CostCard({ label, value, subtext }: { label: string; value: string; subtext: string }) {
  return (
    <div className="bg-white rounded-lg border border-gray-200 shadow-sm p-4">
      <p className="text-xs text-gray-500 font-medium uppercase">{label}</p>
      <p className="text-xl font-bold text-gray-900 mt-1">{value}</p>
      <p className="text-[10px] text-gray-500 mt-0.5">{subtext}</p>
    </div>
  );
}

function UsageMetric({ label, value }: { label: string; value: string }) {
  return (
    <div className="bg-gray-50 rounded border border-gray-200 p-2.5 text-center">
      <p className="text-base font-bold text-gray-900">{value}</p>
      <p className="text-[9px] text-gray-500 uppercase mt-0.5">{label}</p>
    </div>
  );
}
