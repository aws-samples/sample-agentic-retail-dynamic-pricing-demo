import { Link } from 'react-router-dom';
import { logout } from '../lib/cognito';
import {
  GLOSSARY_TERMS,
  METHODOLOGY_SECTIONS,
  SCORING_METHODOLOGY,
} from '../lib/methodologyData';

export default function MethodologyPage() {
  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white shadow-sm border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Link to="/" className="text-sm text-blue-600 hover:text-blue-800">
              &larr; Back
            </Link>
            <h1 className="text-2xl font-semibold text-gray-900">
              Pricing Methodology &amp; Glossary
            </h1>
          </div>
          <button
            onClick={logout}
            className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            Sign Out
          </button>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-10">
        {/* Glossary Section */}
        <section>
          <h2 className="text-xl font-semibold text-gray-900 mb-4">Glossary</h2>
          <p className="text-sm text-gray-600 mb-6">
            Key pricing terms and definitions used throughout the Dynamic Pricing platform.
          </p>
          <div className="bg-white rounded-lg border border-gray-200 shadow-sm overflow-hidden">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider w-1/4">
                    Term
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Definition
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {GLOSSARY_TERMS.map((item) => (
                  <tr key={item.term} className="hover:bg-gray-50">
                    <td className="px-6 py-4 text-sm font-medium text-gray-900 align-top">
                      {item.term}
                    </td>
                    <td className="px-6 py-4 text-sm text-gray-700">
                      {item.definition}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        {/* Factor Categories Section */}
        <section>
          <h2 className="text-xl font-semibold text-gray-900 mb-4">Factor Categories</h2>
          <p className="text-sm text-gray-600 mb-6">
            The pricing engine evaluates three categories of contributing factors to generate optimal pricing recommendations.
          </p>
          <div className="space-y-6">
            {METHODOLOGY_SECTIONS.map((section) => (
              <div
                key={section.id}
                className="bg-white rounded-lg border border-gray-200 shadow-sm p-6"
              >
                <h3 className="text-lg font-semibold text-gray-900 mb-2">
                  {section.title}
                </h3>
                <p className="text-sm text-gray-600 mb-4">{section.description}</p>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {section.factors.map((factor) => (
                    <div
                      key={factor.key}
                      className="border border-gray-100 rounded-md p-4 bg-gray-50"
                    >
                      <p className="text-sm font-medium text-gray-900 mb-1">
                        {factor.label}
                      </p>
                      <p className="text-xs text-gray-600 leading-relaxed">
                        {factor.description}
                      </p>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </section>

        {/* Scoring Methodology Section */}
        <section>
          <h2 className="text-xl font-semibold text-gray-900 mb-4">
            {SCORING_METHODOLOGY.title}
          </h2>
          <p className="text-sm text-gray-600 mb-6">
            {SCORING_METHODOLOGY.description}
          </p>
          <div className="bg-white rounded-lg border border-gray-200 shadow-sm overflow-hidden">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider w-1/5">
                    Component
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider w-[80px]">
                    Weight
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Description
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {SCORING_METHODOLOGY.components.map((component) => (
                  <tr key={component.name} className="hover:bg-gray-50">
                    <td className="px-6 py-4 text-sm font-medium text-gray-900 align-top">
                      {component.name}
                    </td>
                    <td className="px-6 py-4 text-sm font-semibold text-blue-700 align-top">
                      {component.weight}
                    </td>
                    <td className="px-6 py-4 text-sm text-gray-700">
                      {component.description}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      </main>
    </div>
  );
}
