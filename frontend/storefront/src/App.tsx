import { Routes, Route } from 'react-router-dom';

function App() {
  return (
    <div className="min-h-screen flex flex-col">
      <header className="bg-white shadow-sm border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            <div className="flex items-center gap-2">
              <span className="text-2xl font-bold text-brand-600">🛒</span>
              <h1 className="text-xl font-semibold text-gray-900">
                Retail Store
              </h1>
            </div>
            <nav className="flex items-center gap-6">
              <a
                href="/"
                className="text-sm font-medium text-gray-700 hover:text-brand-600 transition-colors"
              >
                Products
              </a>
            </nav>
          </div>
        </div>
      </header>

      <main className="flex-1">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          <Routes>
            <Route
              path="/"
              element={
                <div className="text-center py-12">
                  <h2 className="text-2xl font-semibold text-gray-700">
                    Product Catalog
                  </h2>
                  <p className="mt-2 text-gray-500">
                    Browse our products with live dynamic pricing.
                  </p>
                </div>
              }
            />
            <Route
              path="/products/:id"
              element={
                <div className="text-center py-12">
                  <h2 className="text-2xl font-semibold text-gray-700">
                    Product Detail
                  </h2>
                  <p className="mt-2 text-gray-500">
                    Product details will be displayed here.
                  </p>
                </div>
              }
            />
          </Routes>
        </div>
      </main>

      <footer className="bg-white border-t border-gray-200 py-4">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <p className="text-center text-sm text-gray-500">
            &copy; {new Date().getFullYear()} Retail Dynamic Pricing Demo
          </p>
        </div>
      </footer>
    </div>
  );
}

export default App;
