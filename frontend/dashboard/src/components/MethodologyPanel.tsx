import { useEffect, useCallback } from 'react';
import ReactDOM from 'react-dom';
import { METHODOLOGY_SECTIONS } from '../lib/methodologyData';

interface MethodologyPanelProps {
  isOpen: boolean;
  onClose: () => void;
  triggerRef: React.RefObject<HTMLButtonElement>;
}

export default function MethodologyPanel({ isOpen, onClose, triggerRef }: MethodologyPanelProps) {
  const handleEscape = useCallback(
    (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose();
      }
    },
    [onClose]
  );

  // Escape key listener
  useEffect(() => {
    if (isOpen) {
      document.addEventListener('keydown', handleEscape);
      return () => document.removeEventListener('keydown', handleEscape);
    }
  }, [isOpen, handleEscape]);

  // Return focus to trigger on close
  useEffect(() => {
    if (!isOpen && triggerRef.current) {
      triggerRef.current.focus();
    }
  }, [isOpen, triggerRef]);

  const categoryColors: Record<string, string> = {
    competitive: 'border-blue-500',
    demand: 'border-emerald-500',
    market: 'border-amber-500',
  };

  const categoryBadgeColors: Record<string, string> = {
    competitive: 'bg-blue-100 text-blue-800',
    demand: 'bg-emerald-100 text-emerald-800',
    market: 'bg-amber-100 text-amber-800',
  };

  return ReactDOM.createPortal(
    <>
      {/* Backdrop */}
      <div
        className={`fixed inset-0 z-50 bg-black/30 transition-opacity duration-300 ${
          isOpen ? 'opacity-100' : 'opacity-0 pointer-events-none'
        }`}
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Panel */}
      <div
        role="dialog"
        aria-modal="true"
        aria-label="Pricing Methodology"
        className={`fixed inset-y-0 right-0 z-50 w-full max-w-[480px] bg-white shadow-xl flex flex-col transition-transform duration-300 ease-in-out ${
          isOpen ? 'translate-x-0' : 'translate-x-full'
        }`}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200">
          <h2 className="text-lg font-semibold text-gray-900">Pricing Methodology</h2>
          <button
            onClick={onClose}
            className="p-2 text-gray-400 hover:text-gray-600 rounded-md hover:bg-gray-100 transition-colors"
            aria-label="Close methodology panel"
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              className="h-5 w-5"
              viewBox="0 0 20 20"
              fill="currentColor"
            >
              <path
                fillRule="evenodd"
                d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z"
                clipRule="evenodd"
              />
            </svg>
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto px-6 py-5 space-y-8">
          {METHODOLOGY_SECTIONS.map((section) => (
            <div key={section.id} className={`border-l-4 ${categoryColors[section.category]} pl-4`}>
              <div className="flex items-center gap-2 mb-2">
                <h3 className="text-base font-semibold text-gray-900">{section.title}</h3>
                <span
                  className={`text-xs font-medium px-2 py-0.5 rounded-full ${categoryBadgeColors[section.category]}`}
                >
                  {section.factors.length} factors
                </span>
              </div>
              <p className="text-sm text-gray-600 mb-4">{section.description}</p>

              <div className="space-y-3">
                {section.factors.map((factor) => (
                  <div
                    key={factor.key}
                    className="bg-gray-50 rounded-md p-3"
                  >
                    <dt className="text-sm font-medium text-gray-800">{factor.label}</dt>
                    <dd className="text-xs text-gray-600 mt-1 leading-relaxed">
                      {factor.description}
                    </dd>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>
    </>,
    document.body
  );
}
