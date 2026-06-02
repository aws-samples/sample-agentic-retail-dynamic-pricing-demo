import { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import api from '../lib/api';
import { Product } from '../types/product';
import { getProductImage } from '../lib/productImageMap';

export default function ProductDetail() {
  const { id } = useParams<{ id: string }>();
  const [product, setProduct] = useState<Product | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    fetchProduct(id);
  }, [id]);

  async function fetchProduct(productId: string) {
    try {
      setLoading(true);
      setError(null);
      const response = await api.get<Product>(`/products/${productId}`);
      setProduct(response.data);
    } catch (err: unknown) {
      if (
        err &&
        typeof err === 'object' &&
        'response' in err &&
        (err as { response?: { status?: number } }).response?.status === 404
      ) {
        setError('Product not found. It may have been removed or the link is incorrect.');
      } else {
        setError('Unable to load product details. Please try again later.');
      }
    } finally {
      setLoading(false);
    }
  }

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center py-20">
        <div className="animate-spin rounded-full h-10 w-10 border-4 border-brand-600 border-t-transparent" />
        <p className="mt-4 text-sm text-gray-500">Loading product details...</p>
      </div>
    );
  }

  if (error || !product) {
    return (
      <div className="flex flex-col items-center justify-center py-20">
        <div className="bg-red-50 border border-red-200 rounded-lg p-6 max-w-md text-center">
          <svg
            className="mx-auto h-10 w-10 text-red-400"
            fill="none"
            viewBox="0 0 24 24"
            strokeWidth={1.5}
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M12 9v3.75m9-.75a9 9 0 1 1-18 0 9 9 0 0 1 18 0Zm-9 3.75h.008v.008H12v-.008Z"
            />
          </svg>
          <p className="mt-3 text-sm text-red-700">
            {error || 'Product not found.'}
          </p>
          <Link
            to="/"
            className="mt-4 inline-block px-4 py-2 text-sm font-medium text-white bg-brand-600 rounded-md hover:bg-brand-700 transition-colors"
          >
            Back to Catalog
          </Link>
        </div>
      </div>
    );
  }

  const hasPreviousPrice = product.previousPrice != null && product.previousPrice > 0;
  const priceChanged = hasPreviousPrice && product.currentPrice !== product.previousPrice;
  const priceIncreased = priceChanged && product.currentPrice > product.previousPrice!;

  return (
    <div>
      <Link
        to="/"
        className="inline-flex items-center gap-1 text-sm font-medium text-brand-600 hover:text-brand-700 transition-colors mb-6"
      >
        <svg
          className="h-4 w-4"
          fill="none"
          viewBox="0 0 24 24"
          strokeWidth={2}
          stroke="currentColor"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M15.75 19.5 8.25 12l7.5-7.5"
          />
        </svg>
        Back to Catalog
      </Link>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
        {/* Product Image */}
        <div className="bg-gray-100 rounded-lg overflow-hidden aspect-square">
          <img
            src={getProductImage(product.productId, product.category)}
            alt={product.name}
            className="w-full h-full object-cover"
            loading="lazy"
          />
        </div>

        {/* Product Info */}
        <div className="flex flex-col">
          <p className="text-sm text-gray-500 uppercase tracking-wide">
            {product.category} &middot; {product.subCategory}
          </p>

          <h2 className="mt-2 text-2xl font-bold text-gray-900">
            {product.name}
          </h2>

          {product.recentlyUpdated && (
            <span className="mt-2 inline-flex items-center self-start px-2.5 py-1 rounded-full text-xs font-medium bg-green-100 text-green-800">
              Recently Updated
            </span>
          )}

          {/* Pricing */}
          <div className="mt-6 flex items-baseline gap-3">
            <span className="text-3xl font-bold text-gray-900">
              ${(product.currentPrice ?? 0).toFixed(2)}
            </span>

            {hasPreviousPrice && priceChanged && (
              <span
                className={`text-lg line-through ${
                  priceIncreased ? 'text-gray-400' : 'text-red-400'
                }`}
              >
                ${(product.previousPrice ?? 0).toFixed(2)}
              </span>
            )}

            {hasPreviousPrice && priceChanged && (
              <span
                className={`inline-flex items-center gap-0.5 text-sm font-medium ${
                  priceIncreased ? 'text-red-600' : 'text-green-600'
                }`}
              >
                {priceIncreased ? '↑' : '↓'}
                {Math.abs(
                  ((product.currentPrice - product.previousPrice!) /
                    product.previousPrice!) *
                    100
                ).toFixed(1)}
                %
              </span>
            )}
          </div>

          {/* Description */}
          <div className="mt-6">
            <h3 className="text-sm font-semibold text-gray-900">Description</h3>
            <p className="mt-2 text-sm text-gray-600 leading-relaxed">
              {product.description}
            </p>
          </div>

          {/* Product Details */}
          <div className="mt-6 border-t border-gray-200 pt-6">
            <h3 className="text-sm font-semibold text-gray-900 mb-3">
              Product Details
            </h3>
            <dl className="grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-3 text-sm">
              {product.productFamily && (
                <div>
                  <dt className="text-gray-500">Product Family</dt>
                  <dd className="mt-0.5 font-medium text-gray-900">
                    {product.productFamily}
                  </dd>
                </div>
              )}
              <div>
                <dt className="text-gray-500">Category</dt>
                <dd className="mt-0.5 font-medium text-gray-900">
                  {product.category}
                </dd>
              </div>
              <div>
                <dt className="text-gray-500">Sub-Category</dt>
                <dd className="mt-0.5 font-medium text-gray-900">
                  {product.subCategory}
                </dd>
              </div>
              {product.channels && product.channels.length > 0 && (
                <div>
                  <dt className="text-gray-500">Channels</dt>
                  <dd className="mt-0.5 flex flex-wrap gap-1">
                    {product.channels.map((channel) => (
                      <span
                        key={channel}
                        className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-blue-50 text-blue-700"
                      >
                        {channel}
                      </span>
                    ))}
                  </dd>
                </div>
              )}
              {product.regions && product.regions.length > 0 && (
                <div>
                  <dt className="text-gray-500">Regions</dt>
                  <dd className="mt-0.5 flex flex-wrap gap-1">
                    {product.regions.map((region) => (
                      <span
                        key={region}
                        className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-purple-50 text-purple-700"
                      >
                        {region}
                      </span>
                    ))}
                  </dd>
                </div>
              )}
            </dl>
          </div>

          {/* Last Updated */}
          <div className="mt-6 border-t border-gray-200 pt-4">
            <p className="text-xs text-gray-400">
              Price last updated:{' '}
              {(() => {
                if (!product.priceUpdatedAt) return 'N/A';
                const date = new Date(product.priceUpdatedAt);
                if (isNaN(date.getTime())) return 'N/A';
                return date.toLocaleDateString(undefined, {
                  year: 'numeric',
                  month: 'long',
                  day: 'numeric',
                  hour: '2-digit',
                  minute: '2-digit',
                });
              })()}
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
