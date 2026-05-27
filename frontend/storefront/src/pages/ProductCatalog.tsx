import { useState, useEffect, useRef } from 'react';
import api from '../lib/api';
import { Product } from '../types/product';
import ProductCard from '../components/ProductCard';

const RETRY_INTERVAL_MS = 10_000;
const MAX_RETRIES = 5;

export default function ProductCatalog() {
  const [products, setProducts] = useState<Product[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const retryCount = useRef(0);
  const retryTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    fetchProducts();

    return () => {
      if (retryTimer.current) {
        clearTimeout(retryTimer.current);
      }
    };
  }, []);

  async function fetchProducts() {
    try {
      setLoading(true);
      setError(null);

      const response = await api.get('/products');
      const data = response.data;
      setProducts(data.products ?? data ?? []);
      retryCount.current = 0;
      setLoading(false);
    } catch {
      retryCount.current += 1;

      if (retryCount.current >= MAX_RETRIES) {
        setError(
          'Product information is temporarily unavailable. Please try again later.'
        );
        setLoading(false);
      } else {
        retryTimer.current = setTimeout(fetchProducts, RETRY_INTERVAL_MS);
      }
    }
  }

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center py-20">
        <div className="animate-spin rounded-full h-10 w-10 border-4 border-brand-600 border-t-transparent" />
        <p className="mt-4 text-sm text-gray-500">Loading products...</p>
      </div>
    );
  }

  if (error) {
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
          <p className="mt-3 text-sm text-red-700">{error}</p>
          <button
            onClick={() => {
              retryCount.current = 0;
              fetchProducts();
            }}
            className="mt-4 px-4 py-2 text-sm font-medium text-white bg-brand-600 rounded-md hover:bg-brand-700 transition-colors"
          >
            Try Again
          </button>
        </div>
      </div>
    );
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-2xl font-semibold text-gray-900">
          Product Catalog
        </h2>
        <p className="text-sm text-gray-500">
          {products.length} {products.length === 1 ? 'product' : 'products'}
        </p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-6">
        {products.map((product) => (
          <ProductCard key={product.productId} product={product} />
        ))}
      </div>

      {products.length === 0 && (
        <p className="text-center text-gray-500 py-12">
          No products available at this time.
        </p>
      )}
    </div>
  );
}
