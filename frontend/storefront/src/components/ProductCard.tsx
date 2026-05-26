import { Link } from 'react-router-dom';
import { Product } from '../types/product';

interface ProductCardProps {
  product: Product;
}

export default function ProductCard({ product }: ProductCardProps) {
  const priceChanged = product.currentPrice !== product.previousPrice;
  const priceIncreased = product.currentPrice > product.previousPrice;

  return (
    <Link
      to={`/products/${product.productId}`}
      className="bg-white rounded-lg shadow-sm border border-gray-200 overflow-hidden hover:shadow-md transition-shadow block"
    >
      <div className="aspect-square bg-gray-100 overflow-hidden">
        <img
          src={product.imageUrl}
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

        <div className="flex items-center gap-2">
          <span className="text-lg font-bold text-gray-900">
            ${product.currentPrice.toFixed(2)}
          </span>

          {priceChanged && (
            <span
              className={`text-xs line-through ${
                priceIncreased ? 'text-gray-400' : 'text-red-400'
              }`}
            >
              ${product.previousPrice.toFixed(2)}
            </span>
          )}

          {product.recentlyUpdated && (
            <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800">
              Recently Updated
            </span>
          )}
        </div>
      </div>
    </Link>
  );
}
