/**
 * Static product name/category lookup for resolving product IDs to human-readable names.
 * Used in the TreeTable, CycleDetail, and AuditTrail to display friendly product names
 * instead of raw product IDs like "product-prod-home-004".
 */

export interface ProductInfo {
  name: string;
  category: string;
  subCategory: string;
}

export const PRODUCT_DIRECTORY: Record<string, ProductInfo> = {
  'prod-elec-001': { name: 'ProSound Wireless Earbuds', category: 'Electronics', subCategory: 'Audio' },
  'prod-elec-002': { name: 'SoundWave Portable Bluetooth Speaker', category: 'Electronics', subCategory: 'Audio' },
  'prod-elec-003': { name: 'FitTrack Pro Smartwatch', category: 'Electronics', subCategory: 'Wearables' },
  'prod-elec-004': { name: 'TabletX 10-inch Display', category: 'Electronics', subCategory: 'Tablets' },
  'prod-elec-005': { name: 'StudioMax Over-Ear Headphones', category: 'Electronics', subCategory: 'Audio' },
  'prod-elec-006': { name: 'QuickCharge USB-C Power Bank', category: 'Electronics', subCategory: 'Accessories' },
  'prod-groc-001': { name: 'Farm Fresh Whole Milk', category: 'Grocery', subCategory: 'Dairy' },
  'prod-groc-002': { name: 'Mountain Roast Premium Coffee', category: 'Grocery', subCategory: 'Beverages' },
  'prod-groc-003': { name: 'Artisan Sourdough Bread Loaf', category: 'Grocery', subCategory: 'Bakery' },
  'prod-groc-004': { name: 'Greek Style Yogurt Variety Pack', category: 'Grocery', subCategory: 'Dairy' },
  'prod-groc-005': { name: 'Free Range Large Eggs', category: 'Grocery', subCategory: 'Dairy' },
  'prod-groc-006': { name: 'Organic Green Tea', category: 'Grocery', subCategory: 'Beverages' },
  'prod-home-001': { name: 'LumiGlow Smart LED Floor Lamp', category: 'Home & Garden', subCategory: 'Lighting' },
  'prod-home-002': { name: 'CleanForce Cordless Stick Vacuum', category: 'Home & Garden', subCategory: 'Appliances' },
  'prod-home-003': { name: 'PureAir HEPA Air Purifier', category: 'Home & Garden', subCategory: 'Appliances' },
  'prod-home-004': { name: 'EcoTemp Smart Thermostat', category: 'Home & Garden', subCategory: 'Smart Home' },
  'prod-home-005': { name: 'PowerDrill 20V Cordless Drill Kit', category: 'Home & Garden', subCategory: 'Tools' },
  'prod-home-006': { name: 'GardenPro Automatic Sprinkler Timer', category: 'Home & Garden', subCategory: 'Garden' },
  'prod-home-007': { name: 'ComfortPlus Memory Foam Pillow', category: 'Home & Garden', subCategory: 'Bedding' },
};

/**
 * Resolves a product ID (e.g., "prod-home-004") to its ProductInfo.
 * Returns null if the product ID is not found.
 */
export function getProductInfo(productId: string): ProductInfo | null {
  return PRODUCT_DIRECTORY[productId] ?? null;
}

/**
 * Formats a pricingGroup string into a human-readable display string.
 *
 * Examples:
 * - "Electronics" → "Electronics"
 * - "Electronics-Audio" → "Electronics > Audio"
 * - "product-prod-home-004" → "EcoTemp Smart Thermostat"
 * - "product-unknown-id" → "product-unknown-id" (fallback to raw value)
 */
export function formatPricingGroup(pricingGroup: string): string {
  if (pricingGroup.startsWith('product-')) {
    const productId = pricingGroup.replace('product-', '');
    const info = PRODUCT_DIRECTORY[productId];
    if (info) {
      return info.name;
    }
    return pricingGroup; // fallback if unknown product
  }

  // Category-SubCategory format: replace first dash with " > "
  const dashIndex = pricingGroup.indexOf('-');
  if (dashIndex === -1) {
    return pricingGroup; // plain category
  }

  return `${pricingGroup.substring(0, dashIndex)} > ${pricingGroup.substring(dashIndex + 1)}`;
}
