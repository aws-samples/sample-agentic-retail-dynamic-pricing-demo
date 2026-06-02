import { Link } from 'react-router-dom';
import { Product } from '../types/product';
import { getProductImage } from '../lib/productImageMap';

interface ProductCardProps {
  product: Product;
}

export default function ProductCard({ product }: ProductCardProps) {
  const hasPreviousPrice = product.previousPrice != null && product.previousPrice > 0;
  const priceChanged = hasPreviousPrice && product.currentPrice !== product.previousPrice;
  const priceIncreased = hasPreviousPrice && product.currentPrice > product.previousPrice!;

  return (
    <Link
      to={`/products/${product.productId}`}
      className="bg-white rounded-lg shadow-sm border border-gray-200 overflow-hidden hover:shadow-md transition-shadow block"
    >
      <div className="aspect-square bg-gray-100 overflow-hidden">
        <img
          src={getProductImage(product.productId, product.category)}
          alt={product.name}
          className="w-full h-full object-cover"
          loading="lazy"
        />
      </div>

      <div className="p-4">
        <p className="text-xs text-gray-500 uppercase tracking-wide mb-1">
          {product.category} &middot; {product.subCategory}
        </p>

        <h3 className="text-sm font-semibold text-gray-900 line-clamp-2 mb-2">
          {product.name}
        </h3>

        <p className="text-xs text-gray-600 line-clamp-2 mb-3">
          {product.description}
        </p>

        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-lg font-bold text-gray-900">
            ${product.currentPrice.toFixed(2)}
          </span>

          {priceChanged && hasPreviousPrice && (
            <>
              <span
                className={`text-sm line-through ${
                  priceIncreased ? 'text-gray-400' : 'text-red-400'
                }`}
              >
                ${product.previousPrice!.toFixed(2)}
              </span>
              <span className={`inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-bold ${
                priceIncreased
                  ? 'bg-red-100 text-red-700'
                  : 'bg-green-100 text-green-700'
              }`}>
                {priceIncreased ? '↑' : '↓'} {Math.abs(((product.currentPrice - product.previousPrice!) / product.previousPrice!) * 100).toFixed(1)}%
              </span>
            </>
          )}

          {product.recentlyUpdated && (
            <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-medium bg-blue-100 text-blue-800 animate-pulse">
              AI Optimized
            </span>
          )}
        </div>
      </div>
    </Link>
  );
}
