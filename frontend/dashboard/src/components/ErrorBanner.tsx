import { useState } from 'react';

/** Agent display names for user-friendly error messages */
const AGENT_NAMES: Record<string, string> = {
  'orchestrator': 'Orchestrator Agent',
  'competitive-intelligence': 'Competitive Intelligence Agent',
  'demand-forecasting': 'Demand Forecasting Agent',
  'market-intelligence': 'Market Intelligence Agent',
  'strategy-synthesis': 'Strategy Synthesis Agent',
  'implementation-monitoring': 'Implementation Monitoring Agent',
};

export interface ErrorBannerProps {
  /** Error message to display */
  message: string;
  /** If the error is agent-specific, the agent identifier */
  agentId?: string;
  /** Whether the error can be retried */
  canRetry?: boolean;
  /** Callback when the user clicks Retry */
  onRetry?: () => void;
  /** Callback when the user clicks Restart Demo */
  onRestart?: () => void;
  /** Whether this is an API timeout error */
  isTimeout?: boolean;
}

/**
 * ErrorBanner displays a prominent error notification at the top of the page.
 * It supports agent-specific errors, retry actions, and full demo restart.
 * Validates: Requirements 5.5, 4.7
 */
export default function ErrorBanner({
  message,
  agentId,
  canRetry = false,
  onRetry,
  onRestart,
  isTimeout = false,
}: ErrorBannerProps) {
  const [dismissed, setDismissed] = useState(false);

  if (dismissed) {
    return null;
  }

  const agentName = agentId ? AGENT_NAMES[agentId] || agentId : null;
  const displayMessage = isTimeout
    ? 'The API request timed out. The server may be experiencing high load.'
    : message;

  return (
    <div
      role="alert"
      aria-live="assertive"
      className="w-full bg-red-50 border border-red-300 rounded-lg p-4 shadow-sm"
    >
      <div className="flex items-start gap-3">
        {/* Error icon */}
        <div className="flex-shrink-0 mt-0.5">
          <svg
            className="h-5 w-5 text-red-500"
            viewBox="0 0 20 20"
            fill="currentColor"
            aria-hidden="true"
          >
            <path
              fillRule="evenodd"
              d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.28 7.22a.75.75 0 00-1.06 1.06L8.94 10l-1.72 1.72a.75.75 0 101.06 1.06L10 11.06l1.72 1.72a.75.75 0 101.06-1.06L11.06 10l1.72-1.72a.75.75 0 00-1.06-1.06L10 8.94 8.28 7.22z"
              clipRule="evenodd"
            />
          </svg>
        </div>

        {/* Content */}
        <div className="flex-1 min-w-0">
          <h3 className="text-sm font-semibold text-red-800">
            {isTimeout ? 'Request Timeout' : 'Error'}
          </h3>

          {agentName && (
            <p className="text-sm text-red-700 mt-1">
              Agent failed:{' '}
              <span className="font-semibold text-red-900">{agentName}</span>
            </p>
          )}

          <p className="text-sm text-red-700 mt-1">{displayMessage}</p>

          {/* Action buttons */}
          <div className="flex items-center gap-3 mt-3">
            {canRetry && onRetry && (
              <button
                onClick={onRetry}
                className="inline-flex items-center px-3 py-1.5 text-sm font-medium text-white bg-red-600 rounded-md hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-red-500 focus:ring-offset-2 transition-colors"
              >
                <svg
                  className="h-4 w-4 mr-1.5"
                  viewBox="0 0 20 20"
                  fill="currentColor"
                  aria-hidden="true"
                >
                  <path
                    fillRule="evenodd"
                    d="M15.312 11.424a5.5 5.5 0 01-9.201 2.466l-.312-.311h2.433a.75.75 0 000-1.5H4.598a.75.75 0 00-.75.75v3.634a.75.75 0 001.5 0v-2.033l.312.311a7 7 0 0011.712-3.138.75.75 0 00-1.449-.39zm-9.624-2.848a.75.75 0 00.726-.94 5.5 5.5 0 019.2-2.467l.312.311H13.5a.75.75 0 000 1.5h3.634a.75.75 0 00.75-.75V2.596a.75.75 0 00-1.5 0v2.033l-.312-.311A7 7 0 004.36 7.456a.75.75 0 00.727.94z"
                    clipRule="evenodd"
                  />
                </svg>
                Retry
              </button>
            )}

            {onRestart && (
              <button
                onClick={onRestart}
                className="inline-flex items-center px-3 py-1.5 text-sm font-medium text-red-700 bg-red-100 border border-red-300 rounded-md hover:bg-red-200 focus:outline-none focus:ring-2 focus:ring-red-500 focus:ring-offset-2 transition-colors"
              >
                <svg
                  className="h-4 w-4 mr-1.5"
                  viewBox="0 0 20 20"
                  fill="currentColor"
                  aria-hidden="true"
                >
                  <path
                    fillRule="evenodd"
                    d="M2 4.75A.75.75 0 012.75 4h14.5a.75.75 0 010 1.5H2.75A.75.75 0 012 4.75zm0 10.5a.75.75 0 01.75-.75h14.5a.75.75 0 010 1.5H2.75a.75.75 0 01-.75-.75zM2 10a.75.75 0 01.75-.75h7.5a.75.75 0 010 1.5h-7.5A.75.75 0 012 10z"
                    clipRule="evenodd"
                  />
                </svg>
                Restart Demo
              </button>
            )}
          </div>
        </div>

        {/* Dismiss button */}
        <button
          onClick={() => setDismissed(true)}
          className="flex-shrink-0 p-1 text-red-400 hover:text-red-600 rounded-md hover:bg-red-100 focus:outline-none focus:ring-2 focus:ring-red-500 transition-colors"
          aria-label="Dismiss error"
        >
          <svg
            className="h-5 w-5"
            viewBox="0 0 20 20"
            fill="currentColor"
            aria-hidden="true"
          >
            <path d="M6.28 5.22a.75.75 0 00-1.06 1.06L8.94 10l-3.72 3.72a.75.75 0 101.06 1.06L10 11.06l3.72 3.72a.75.75 0 101.06-1.06L11.06 10l3.72-3.72a.75.75 0 00-1.06-1.06L10 8.94 6.28 5.22z" />
          </svg>
        </button>
      </div>
    </div>
  );
}
