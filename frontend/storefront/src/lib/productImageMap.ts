/**
 * Client-side mapping of product IDs to relevant image URLs.
 * Used by ProductCard and ProductDetail to display product-appropriate images.
 *
 * Sources: Unsplash (free, no attribution required for use)
 */

export const PRODUCT_IMAGE_MAP: Record<string, string> = {
  // ─── Electronics ─────────────────────────────────────────────────────────────
  'prod-elec-001':
    'https://images.unsplash.com/photo-1606220588913-b3aacb4d2f46?w=400&h=400&fit=crop', // ProSound Wireless Earbuds
  'prod-elec-002':
    'https://images.unsplash.com/photo-1608043152269-423dbba4e7e1?w=400&h=400&fit=crop', // SoundWave Portable Bluetooth Speaker
  'prod-elec-003':
    'https://images.unsplash.com/photo-1579586337278-3befd40fd17a?w=400&h=400&fit=crop', // FitTrack Pro Smartwatch
  'prod-elec-004':
    'https://images.unsplash.com/photo-1544244015-0df4b3ffc6b0?w=400&h=400&fit=crop', // TabletX 10-inch Display
  'prod-elec-005':
    'https://images.unsplash.com/photo-1505740420928-5e560c06d30e?w=400&h=400&fit=crop', // StudioMax Over-Ear Headphones
  'prod-elec-006':
    'https://images.unsplash.com/photo-1609091839311-d5365f9ff1c5?w=400&h=400&fit=crop', // QuickCharge USB-C Power Bank

  // ─── Grocery ─────────────────────────────────────────────────────────────────
  'prod-groc-001':
    'https://images.unsplash.com/photo-1563636619-e9143da7973b?w=400&h=400&fit=crop', // Farm Fresh Whole Milk (1 Gallon)
  'prod-groc-002':
    'https://images.unsplash.com/photo-1559056199-641a0ac8b55e?w=400&h=400&fit=crop', // Mountain Roast Premium Coffee
  'prod-groc-003':
    'https://images.unsplash.com/photo-1586444248902-2f64eddc13df?w=400&h=400&fit=crop', // Artisan Sourdough Bread Loaf
  'prod-groc-004':
    'https://images.unsplash.com/photo-1488477181946-6428a0291777?w=400&h=400&fit=crop', // Greek Style Yogurt Variety Pack
  'prod-groc-005':
    'https://images.unsplash.com/photo-1582722872445-44dc5f7e3c8f?w=400&h=400&fit=crop', // Free Range Large Eggs (Dozen)
  'prod-groc-006':
    'https://images.unsplash.com/photo-1627435601361-ec25f5b1d0e5?w=400&h=400&fit=crop', // Organic Green Tea (20 bags)

  // ─── Home & Garden ───────────────────────────────────────────────────────────
  'prod-home-001':
    'https://images.unsplash.com/photo-1610886420198-5e3ed5ed84c9?w=400&h=400&fit=crop', // LumiGlow Smart LED Floor Lamp
  'prod-home-002':
    'https://images.unsplash.com/photo-1722710070534-e31f0290d8de?w=400&h=400&fit=crop', // CleanForce Cordless Stick Vacuum
  'prod-home-003':
    'https://images.unsplash.com/photo-1632928274371-878938e4d825?w=400&h=400&fit=crop', // PureAir HEPA Air Purifier
  'prod-home-004':
    'https://images.unsplash.com/photo-1636569608385-58efc32690ea?w=400&h=400&fit=crop', // EcoTemp Smart Thermostat
  'prod-home-005':
    'https://images.unsplash.com/photo-1504148455328-c376907d081c?w=400&h=400&fit=crop', // PowerDrill 20V Cordless Drill Kit
  'prod-home-006':
    'https://images.unsplash.com/photo-1718565524318-b58b8b86b813?w=400&h=400&fit=crop', // GardenPro Automatic Sprinkler Timer
  'prod-home-007':
    'https://images.unsplash.com/photo-1584100936595-c0654b55a2e2?w=400&h=400&fit=crop', // ComfortPlus Memory Foam Pillow
};

export const CATEGORY_FALLBACKS: Record<string, string> = {
  Electronics:
    'https://images.unsplash.com/photo-1518770660439-4636190af475?w=400&h=400&fit=crop',
  Grocery:
    'https://images.unsplash.com/photo-1542838132-92c53300491e?w=400&h=400&fit=crop',
  'Home & Garden':
    'https://images.unsplash.com/photo-1556909114-f6e7ad7d3136?w=400&h=400&fit=crop',
};

const DEFAULT_FALLBACK =
  'https://images.unsplash.com/photo-1518770660439-4636190af475?w=400&h=400&fit=crop';

/**
 * Resolves the best image URL for a product using a fallback chain:
 * 1. Exact product ID match in PRODUCT_IMAGE_MAP
 * 2. Category-level fallback from CATEGORY_FALLBACKS
 * 3. Generic default fallback (electronics)
 */
export function getProductImage(productId: string, category: string): string {
  return (
    PRODUCT_IMAGE_MAP[productId] ??
    CATEGORY_FALLBACKS[category] ??
    DEFAULT_FALLBACK
  );
}
