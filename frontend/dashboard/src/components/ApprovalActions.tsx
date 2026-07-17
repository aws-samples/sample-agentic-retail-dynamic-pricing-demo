import { useState } from 'react';
import api from '../lib/api';

export interface ApprovalActionsProps {
  scenarioId: string;
  cycleId: string;
  riskLevel: 'LOW' | 'MEDIUM' | 'HIGH';
  statusLabel: string;
}

type ApprovalAction = 'approve' | 'reject';

interface SubmissionState {
  status: 'idle' | 'submitting' | 'success' | 'error';
  message: string;
}

const MIN_HIGH_RISK_CHARS = 50;

export default function ApprovalActions({
  scenarioId,
  cycleId,
  riskLevel,
  statusLabel,
}: ApprovalActionsProps) {
  const [comment, setComment] = useState('');
  const [submission, setSubmission] = useState<SubmissionState>({
    status: 'idle',
    message: '',
  });
  const [lastAction, setLastAction] = useState<ApprovalAction | null>(null);

  const isHighRisk = riskLevel === 'HIGH';
  const charCount = comment.length;
  const meetsHighRiskMinimum = charCount >= MIN_HIGH_RISK_CHARS;
  const hasComment = comment.trim().length > 0;

  const canSubmit =
    hasComment && (!isHighRisk || meetsHighRiskMinimum) && submission.status !== 'submitting';

  async function handleAction(action: ApprovalAction) {
    if (!canSubmit) return;

    setLastAction(action);
    setSubmission({ status: 'submitting', message: '' });

    try {
      await api.post('/approvals', {
        scenarioId,
        cycleId,
        action: action === 'approve' ? 'APPROVED' : 'REJECTED',
        comment: comment.trim(),
        riskLevel,
      });

      setSubmission({
        status: 'success',
        message: action === 'approve' ? 'Scenario approved' : 'Scenario rejected',
      });
    } catch (err: unknown) {
      const errorMessage =
        err instanceof Error ? err.message : 'An unexpected error occurred';
      setSubmission({
        status: 'error',
        message: `Failed to ${action} scenario: ${errorMessage}`,
      });
    }
  }

  return (
    <div className="rounded-lg border border-gray-200 bg-white p-4 space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-medium text-gray-900">Approval Actions</h3>
        <span
          className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${
            riskLevel === 'HIGH'
              ? 'bg-red-100 text-red-800'
              : riskLevel === 'MEDIUM'
                ? 'bg-yellow-100 text-yellow-800'
                : 'bg-green-100 text-green-800'
          }`}
        >
          {statusLabel}
        </span>
      </div>

      {isHighRisk && (
        <div className="flex items-start gap-2 rounded-md bg-red-50 border border-red-200 p-3">
          <svg
            className="h-5 w-5 text-red-600 shrink-0 mt-0.5"
            fill="none"
            viewBox="0 0 24 24"
            strokeWidth={1.5}
            stroke="currentColor"
            aria-hidden="true"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126ZM12 15.75h.007v.008H12v-.008Z"
            />
          </svg>
          <p className="text-sm text-red-700">
            High risk scenario — justification must be at least {MIN_HIGH_RISK_CHARS} characters.
          </p>
        </div>
      )}

      <div className="space-y-1">
        <label htmlFor="approval-comment" className="block text-sm font-medium text-gray-700">
          Comment <span className="text-red-500">*</span>
        </label>
        <textarea
          id="approval-comment"
          rows={3}
          value={comment}
          onChange={(e) => setComment(e.target.value)}
          disabled={submission.status === 'submitting'}
          placeholder={
            isHighRisk
              ? `Provide justification (minimum ${MIN_HIGH_RISK_CHARS} characters)...`
              : 'Provide a comment for this action...'
          }
          className={`block w-full rounded-md border px-3 py-2 text-sm shadow-sm placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 disabled:bg-gray-50 disabled:text-gray-500 ${
            isHighRisk && charCount > 0 && !meetsHighRiskMinimum
              ? 'border-red-300'
              : 'border-gray-300'
          }`}
        />
        {isHighRisk && (
          <p
            className={`text-xs ${
              charCount > 0 && !meetsHighRiskMinimum ? 'text-red-600' : 'text-gray-500'
            }`}
          >
            {charCount}/{MIN_HIGH_RISK_CHARS} characters
            {charCount > 0 && !meetsHighRiskMinimum && ' (minimum not met)'}
          </p>
        )}
      </div>

      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={() => handleAction('approve')}
          disabled={!canSubmit}
          className="inline-flex items-center rounded-md bg-green-600 px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-green-700 focus:outline-none focus:ring-2 focus:ring-green-500 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {submission.status === 'submitting' && lastAction === 'approve' ? (
            <>
              <svg
                className="animate-spin -ml-0.5 mr-2 h-4 w-4 text-white"
                fill="none"
                viewBox="0 0 24 24"
                aria-hidden="true"
              >
                <circle
                  className="opacity-25"
                  cx="12"
                  cy="12"
                  r="10"
                  stroke="currentColor"
                  strokeWidth="4"
                />
                <path
                  className="opacity-75"
                  fill="currentColor"
                  d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
                />
              </svg>
              Approving…
            </>
          ) : (
            'Approve'
          )}
        </button>

        <button
          type="button"
          onClick={() => handleAction('reject')}
          disabled={!canSubmit}
          className="inline-flex items-center rounded-md bg-red-600 px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-red-500 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {submission.status === 'submitting' && lastAction === 'reject' ? (
            <>
              <svg
                className="animate-spin -ml-0.5 mr-2 h-4 w-4 text-white"
                fill="none"
                viewBox="0 0 24 24"
                aria-hidden="true"
              >
                <circle
                  className="opacity-25"
                  cx="12"
                  cy="12"
                  r="10"
                  stroke="currentColor"
                  strokeWidth="4"
                />
                <path
                  className="opacity-75"
                  fill="currentColor"
                  d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
                />
              </svg>
              Rejecting…
            </>
          ) : (
            'Reject'
          )}
        </button>
      </div>

      {submission.status === 'success' && (
        <div className="flex items-center gap-2 rounded-md bg-green-50 border border-green-200 p-3">
          <svg
            className="h-5 w-5 text-green-600 shrink-0"
            fill="none"
            viewBox="0 0 24 24"
            strokeWidth={2}
            stroke="currentColor"
            aria-hidden="true"
          >
            <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
          </svg>
          <p className="text-sm text-green-700">{submission.message}</p>
        </div>
      )}

      {submission.status === 'error' && (
        <div className="flex items-start gap-2 rounded-md bg-red-50 border border-red-200 p-3">
          <svg
            className="h-5 w-5 text-red-600 shrink-0 mt-0.5"
            fill="none"
            viewBox="0 0 24 24"
            strokeWidth={2}
            stroke="currentColor"
            aria-hidden="true"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M6 18L18 6M6 6l12 12"
            />
          </svg>
          <p className="text-sm text-red-700">{submission.message}</p>
        </div>
      )}
    </div>
  );
}
