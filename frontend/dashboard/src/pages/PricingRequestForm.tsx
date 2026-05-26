import { useState } from 'react';
import api from '../lib/api';

/** Pricing group options organized by type */
const PRICING_GROUPS = [
  { label: 'Electronics', value: 'electronics', type: 'category' },
  { label: 'Electronics > Smartphones', value: 'electronics-smartphones', type: 'sub-category' },
  { label: 'Electronics > Laptops', value: 'electronics-laptops', type: 'sub-category' },
  { label: 'Electronics > Smartphones > Premium', value: 'electronics-smartphones-premium', type: 'product-family' },
  { label: 'Grocery', value: 'grocery', type: 'category' },
  { label: 'Grocery > Beverages', value: 'grocery-beverages', type: 'sub-category' },
  { label: 'Grocery > Snacks', value: 'grocery-snacks', type: 'sub-category' },
  { label: 'Grocery > Beverages > Energy Drinks', value: 'grocery-beverages-energy-drinks', type: 'product-family' },
  { label: 'Home & Garden', value: 'home-garden', type: 'category' },
  { label: 'Home & Garden > Furniture', value: 'home-garden-furniture', type: 'sub-category' },
  { label: 'Home & Garden > Outdoor', value: 'home-garden-outdoor', type: 'sub-category' },
  { label: 'Home & Garden > Furniture > Living Room', value: 'home-garden-furniture-living-room', type: 'product-family' },
];

/** Strategic objective options */
const STRATEGIC_OBJECTIVES = [
  { label: 'Revenue Maximization', value: 'revenue_maximization' },
  { label: 'Margin Protection', value: 'margin_protection' },
  { label: 'Market Share Growth', value: 'market_share_growth' },
  { label: 'Competitive Positioning', value: 'competitive_positioning' },
];

/** Channel restriction options */
const CHANNEL_OPTIONS = [
  { label: 'Online', value: 'online' },
  { label: 'In-Store', value: 'in-store' },
  { label: 'Marketplace', value: 'marketplace' },
  { label: 'Wholesale', value: 'wholesale' },
];

interface FormErrors {
  pricingGroup?: string;
  objectives?: string;
}

export default function PricingRequestForm() {
  const [pricingGroup, setPricingGroup] = useState('');
  const [objectives, setObjectives] = useState<string[]>([]);
  const [minMargin, setMinMargin] = useState('');
  const [maxPriceChange, setMaxPriceChange] = useState('');
  const [channelRestrictions, setChannelRestrictions] = useState<string[]>([]);
  const [errors, setErrors] = useState<FormErrors>({});
  const [submitting, setSubmitting] = useState(false);
  const [successMessage, setSuccessMessage] = useState('');
  const [errorMessage, setErrorMessage] = useState('');

  function handleObjectiveToggle(value: string) {
    setObjectives((prev) =>
      prev.includes(value) ? prev.filter((o) => o !== value) : [...prev, value],
    );
  }

  function handleChannelToggle(value: string) {
    setChannelRestrictions((prev) =>
      prev.includes(value) ? prev.filter((c) => c !== value) : [...prev, value],
    );
  }

  function validate(): boolean {
    const newErrors: FormErrors = {};

    if (!pricingGroup) {
      newErrors.pricingGroup = 'Pricing group is required.';
    }

    if (objectives.length === 0) {
      newErrors.objectives = 'At least one strategic objective must be selected.';
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSuccessMessage('');
    setErrorMessage('');

    if (!validate()) {
      return;
    }

    setSubmitting(true);

    try {
      const payload = {
        pricingGroup,
        objectives,
        constraints: {
          minMargin: minMargin ? parseFloat(minMargin) : undefined,
          maxPriceChange: maxPriceChange ? parseFloat(maxPriceChange) : undefined,
          channelRestrictions: channelRestrictions.length > 0 ? channelRestrictions : undefined,
        },
      };

      const response = await api.post('/pricing-cycles', payload);
      const cycleId = response.data.cycleId;
      setSuccessMessage(`Pricing cycle initiated successfully. Cycle ID: ${cycleId}`);

      // Reset form
      setPricingGroup('');
      setObjectives([]);
      setMinMargin('');
      setMaxPriceChange('');
      setChannelRestrictions([]);
      setErrors({});
    } catch (err: unknown) {
      const message =
        err instanceof Error ? err.message : 'Failed to submit pricing request. Please try again.';
      setErrorMessage(message);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="max-w-2xl mx-auto">
      <h2 className="text-xl font-semibold text-gray-900 mb-6">New Pricing Request</h2>

      {successMessage && (
        <div className="mb-6 bg-green-50 border border-green-200 rounded-md p-4">
          <p className="text-sm text-green-800">{successMessage}</p>
        </div>
      )}

      {errorMessage && (
        <div className="mb-6 bg-red-50 border border-red-200 rounded-md p-4">
          <p className="text-sm text-red-700">{errorMessage}</p>
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-6 bg-white p-6 rounded-lg shadow-sm border border-gray-200">
        {/* Pricing Group Dropdown */}
        <div>
          <label htmlFor="pricing-group" className="block text-sm font-medium text-gray-700 mb-1">
            Pricing Group <span className="text-red-500">*</span>
          </label>
          <select
            id="pricing-group"
            value={pricingGroup}
            onChange={(e) => setPricingGroup(e.target.value)}
            className={`w-full rounded-md border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 ${
              errors.pricingGroup ? 'border-red-300' : 'border-gray-300'
            }`}
          >
            <option value="">Select a pricing group</option>
            <optgroup label="Category">
              {PRICING_GROUPS.filter((g) => g.type === 'category').map((g) => (
                <option key={g.value} value={g.value}>
                  {g.label}
                </option>
              ))}
            </optgroup>
            <optgroup label="Sub-Category">
              {PRICING_GROUPS.filter((g) => g.type === 'sub-category').map((g) => (
                <option key={g.value} value={g.value}>
                  {g.label}
                </option>
              ))}
            </optgroup>
            <optgroup label="Product Family">
              {PRICING_GROUPS.filter((g) => g.type === 'product-family').map((g) => (
                <option key={g.value} value={g.value}>
                  {g.label}
                </option>
              ))}
            </optgroup>
          </select>
          {errors.pricingGroup && (
            <p className="mt-1 text-sm text-red-600">{errors.pricingGroup}</p>
          )}
        </div>

        {/* Strategic Objectives */}
        <div>
          <fieldset>
            <legend className="block text-sm font-medium text-gray-700 mb-2">
              Strategic Objectives <span className="text-red-500">*</span>
            </legend>
            <div className="space-y-2">
              {STRATEGIC_OBJECTIVES.map((obj) => (
                <label key={obj.value} className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={objectives.includes(obj.value)}
                    onChange={() => handleObjectiveToggle(obj.value)}
                    className="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                  />
                  <span className="text-sm text-gray-700">{obj.label}</span>
                </label>
              ))}
            </div>
            {errors.objectives && (
              <p className="mt-1 text-sm text-red-600">{errors.objectives}</p>
            )}
          </fieldset>
        </div>

        {/* Business Constraints */}
        <div>
          <h3 className="text-sm font-medium text-gray-700 mb-3">Business Constraints</h3>
          <div className="space-y-4">
            {/* Min Margin */}
            <div>
              <label htmlFor="min-margin" className="block text-sm text-gray-600 mb-1">
                Minimum Margin (%)
              </label>
              <input
                id="min-margin"
                type="number"
                min="0"
                max="100"
                step="0.1"
                value={minMargin}
                onChange={(e) => setMinMargin(e.target.value)}
                placeholder="e.g. 15"
                className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>

            {/* Max Price Change */}
            <div>
              <label htmlFor="max-price-change" className="block text-sm text-gray-600 mb-1">
                Maximum Price Change (%)
              </label>
              <input
                id="max-price-change"
                type="number"
                min="0"
                max="100"
                step="0.1"
                value={maxPriceChange}
                onChange={(e) => setMaxPriceChange(e.target.value)}
                placeholder="e.g. 10"
                className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>

            {/* Channel Restrictions */}
            <div>
              <span className="block text-sm text-gray-600 mb-2">Channel Restrictions</span>
              <div className="flex flex-wrap gap-3">
                {CHANNEL_OPTIONS.map((ch) => (
                  <label key={ch.value} className="flex items-center gap-1.5 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={channelRestrictions.includes(ch.value)}
                      onChange={() => handleChannelToggle(ch.value)}
                      className="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                    />
                    <span className="text-sm text-gray-700">{ch.label}</span>
                  </label>
                ))}
              </div>
            </div>
          </div>
        </div>

        {/* Submit Button */}
        <div className="pt-2">
          <button
            type="submit"
            disabled={submitting}
            className="w-full flex justify-center py-2.5 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {submitting ? 'Submitting...' : 'Initiate Pricing Cycle'}
          </button>
        </div>
      </form>
    </div>
  );
}
