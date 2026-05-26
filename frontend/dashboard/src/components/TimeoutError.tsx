import { useState, useEffect, useCallback, useRef } from 'react';

export interface TimeoutErrorProps {
  /** Error message describing the timeout */
  message?: string;
  /** Countdown duration in seconds before auto-retry (default: 30) */
  countdownSeconds?: number;
  /** Callback when retry is triggered (manual or auto) */
  onRetry: () => void;
  /** Callback when the user clicks Restart Demo */
  onRestart?: () => void;
  /** Whether auto-retry is enabled (default: true) */
  autoRetry?: boolean;
}

/**
 * TimeoutError displays an API timeout error with a countdown timer for automatic retry.
 * The user can manually retry immediately or wait for the countdown to complete.
 * Validates: Requirements 5.5, 4.7
 */
export default function TimeoutError({
  message = 'The API request timed out. This may be due to high server load or network issues.',
  countdownSeconds = 30,
  onRetry,
  onRestart,
  autoRetry = true,
}: TimeoutErrorProps) {
  const [secondsRemaining, setSecondsRemaining] = useState(countdownSeconds);
  const [isPaused, setIsPaused] = useState(!autoRetry);
  const [dismissed, setDismissed] = useState(false);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const clearCountdown = useCallback(() => {
    if (intervalRef.current !== null) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
  }, []);

  useEffect(() => {
    if (isPaused || dismissed) {
      clearCountdown();
      return;
    }

    intervalRef.current = setInterval(() => {
      setSecondsRemaining((prev) => {
        if (prev <= 1) {
          clearCountdown();
          onRetry();
          return 0;
        }
        return prev - 1;
      });
    }, 1000);

    return clearCountdown;
  }, [isPaused, dismissed, clearCountdown, onRetry]);

  const handleManualRetry = () => {
    clearCountdown();
    setDismissed(true);
    onRetry();
  };

  const handlePauseResume = () => {
    setIsPaused((prev) => !prev);
  };

  if (dismissed) {
    return null;
  }

  const progress = ((countdownSeconds - secondsRemaining) / countdownSeconds) * 100;

  return (
    <div
      role="alert"
      aria-live="assertive"
      className="w-full bg-amber-50 border border-amber-300 rounded-lg shadow-sm overflow-hidden"
    >
      {/* Progress bar */}
      {autoRetry && !isPaused && (
        <div className="h-1 bg-amber-100">
          <div
            className="h-full bg-amber-500 transition-all duration-1000 ease-linear"
            style={{ width: `${progress}%` }}
            role="progressbar"
            aria-valuenow={secondsRemaining}
            aria-valuemin={0}
            aria-valuemax={countdownSeconds}
            aria-label={`Auto-retry in ${secondsRemaining} seconds`}
          />
        </div>
      )}

      <div className="p-4">
        <div className="flex items-start gap-3">
          {/* Timeout icon */}
          <div className="flex-shrink-0 mt-0.5">
            <svg
              className="h-5 w-5 text-amber-500"
              viewBox="0 0 20 20"
              fill="currentColor"
              aria-hidden="true"
            >
              <path
                fillRule="evenodd"
                d="M10 18a8 8 0 100-16 8 8 0 000 16zm.75-13a.75.75 0 00-1.5 0v5c0 .414.336.75.75.75h4a.75.75 0 000-1.5h-3.25V5z"
                clipRule="evenodd"
              />
            </svg>
          </div>

          {/* Content */}
          <div className="flex-1 min-w-0">
            <h3 className="text-sm font-semibold text-amber-800">
              API Request Timeout
            </h3>

            <p className="text-sm text-amber-700 mt-1">{message}</p>

            {/* Countdown display */}
            {autoRetry && secondsRemaining > 0 && (
              <p className="text-sm text-amber-600 mt-2">
                {isPaused ? (
                  'Auto-retry paused'
                ) : (
                  <>
                    Retrying automatically in{' '}
                    <span className="font-semibold text-amber-800">
                      {secondsRemaining}s
                    </span>
                  </>
                )}
              </p>
            )}

            {/* Action buttons */}
            <div className="flex items-center gap-3 mt-3">
              <button
                onClick={handleManualRetry}
                className="inline-flex items-center px-3 py-1.5 text-sm font-medium text-white bg-amber-600 rounded-md hover:bg-amber-700 focus:outline-none focus:ring-2 focus:ring-amber-500 focus:ring-offset-2 transition-colors"
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
                Retry Now
              </button>

              {autoRetry && (
                <button
                  onClick={handlePauseResume}
                  className="inline-flex items-center px-3 py-1.5 text-sm font-medium text-amber-700 bg-amber-100 border border-amber-300 rounded-md hover:bg-amber-200 focus:outline-none focus:ring-2 focus:ring-amber-500 focus:ring-offset-2 transition-colors"
                >
                  {isPaused ? 'Resume Countdown' : 'Pause'}
                </button>
              )}

              {onRestart && (
                <button
                  onClick={onRestart}
                  className="inline-flex items-center px-3 py-1.5 text-sm font-medium text-red-700 bg-red-100 border border-red-300 rounded-md hover:bg-red-200 focus:outline-none focus:ring-2 focus:ring-red-500 focus:ring-offset-2 transition-colors"
                >
                  Restart Demo
                </button>
              )}
            </div>
          </div>

          {/* Dismiss button */}
          <button
            onClick={() => setDismissed(true)}
            className="flex-shrink-0 p-1 text-amber-400 hover:text-amber-600 rounded-md hover:bg-amber-100 focus:outline-none focus:ring-2 focus:ring-amber-500 transition-colors"
            aria-label="Dismiss timeout error"
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
    </div>
  );
}
