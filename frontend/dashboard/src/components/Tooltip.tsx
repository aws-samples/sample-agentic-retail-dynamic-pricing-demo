import { useState, useRef, useEffect, useCallback } from 'react';
import ReactDOM from 'react-dom';

interface TooltipProps {
  content: string;
  children: React.ReactElement;
  delay?: number;
}

interface TooltipPosition {
  top: number;
  left: number;
  placement: 'above' | 'below';
}

/**
 * Computes tooltip position relative to the viewport.
 * Prefers placement above the trigger; falls back to below if insufficient space.
 * Clamps horizontally to prevent overflow.
 */
export function computeTooltipPosition(
  triggerRect: DOMRect,
  tooltipSize: { width: number; height: number },
  viewport: { width: number; height: number }
): TooltipPosition {
  const gap = 8;

  // Prefer above; if insufficient space above trigger, place below
  const spaceAbove = triggerRect.top;
  const placement = spaceAbove >= tooltipSize.height + gap ? 'above' : 'below';

  const top = placement === 'above'
    ? triggerRect.top - tooltipSize.height - gap
    : triggerRect.bottom + gap;

  // Center horizontally relative to trigger, clamped to viewport
  let left = triggerRect.left + triggerRect.width / 2 - tooltipSize.width / 2;
  left = Math.max(gap, Math.min(left, viewport.width - tooltipSize.width - gap));

  return { top, left, placement };
}

export default function Tooltip({ content, children, delay = 200 }: TooltipProps) {
  const [visible, setVisible] = useState(false);
  const [position, setPosition] = useState<TooltipPosition>({ top: 0, left: 0, placement: 'above' });
  const triggerRef = useRef<HTMLSpanElement>(null);
  const tooltipRef = useRef<HTMLDivElement>(null);
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const show = useCallback(() => {
    timeoutRef.current = setTimeout(() => {
      setVisible(true);
    }, delay);
  }, [delay]);

  const hide = useCallback(() => {
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
      timeoutRef.current = null;
    }
    setVisible(false);
  }, []);

  // Compute position after tooltip becomes visible and renders
  useEffect(() => {
    if (visible && triggerRef.current && tooltipRef.current) {
      const triggerRect = triggerRef.current.getBoundingClientRect();
      const tooltipRect = tooltipRef.current.getBoundingClientRect();
      const viewport = { width: window.innerWidth, height: window.innerHeight };

      const pos = computeTooltipPosition(
        triggerRect,
        { width: tooltipRect.width, height: tooltipRect.height },
        viewport
      );
      setPosition(pos);
    }
  }, [visible]);

  // Cleanup timeout on unmount
  useEffect(() => {
    return () => {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
      }
    };
  }, []);

  const tooltip = visible
    ? ReactDOM.createPortal(
        <div
          ref={tooltipRef}
          role="tooltip"
          className="fixed z-[9999] max-w-[300px] px-3 py-2 text-xs text-white bg-gray-900 rounded shadow-lg pointer-events-none"
          style={{ top: position.top, left: position.left }}
        >
          {content}
          {/* Arrow/caret */}
          <div
            className={`absolute left-1/2 -translate-x-1/2 w-0 h-0 border-[5px] border-transparent ${
              position.placement === 'above'
                ? 'top-full border-t-gray-900'
                : 'bottom-full border-b-gray-900'
            }`}
          />
        </div>,
        document.body
      )
    : null;

  return (
    <>
      <span
        ref={triggerRef}
        onMouseEnter={show}
        onMouseLeave={hide}
        className="inline"
      >
        {children}
      </span>
      {tooltip}
    </>
  );
}
