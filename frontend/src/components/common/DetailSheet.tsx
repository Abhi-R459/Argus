import React, { useEffect } from 'react';
import { X } from 'lucide-react';
import { ErrorBoundary } from './ErrorBoundary';

export interface DetailSheetProps {
  isOpen: boolean;
  onClose: () => void;
  title: React.ReactNode;
  subtitle?: React.ReactNode;
  headerBadge?: React.ReactNode;
  children: React.ReactNode;
  footer?: React.ReactNode;
  portalTheme?: 'auditor' | 'hr';
  mode?: 'docked' | 'drawer' | 'responsive';
  widthClass?: string;
  className?: string;
}

export function DetailSheet({
  isOpen,
  onClose,
  title,
  subtitle,
  headerBadge,
  children,
  footer,
  portalTheme = 'auditor',
  mode = 'responsive',
  widthClass = 'w-full lg:w-[420px]',
  className = '',
}: DetailSheetProps) {
  // Handle ESC key listener
  useEffect(() => {
    if (!isOpen) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        const active = document.activeElement;
        const isInput =
          active &&
          (active.tagName === 'INPUT' ||
            active.tagName === 'TEXTAREA' ||
            active.tagName === 'SELECT');
        if (!isInput) {
          onClose();
        }
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  const isAuditor = portalTheme === 'auditor';

  const containerThemeClasses = isAuditor
    ? 'bg-linear-surface-1 text-linear-ink border-linear-hairline shadow-lg'
    : 'bg-white text-slate-900 border-slate-200 shadow-xl';

  const headerBg = isAuditor
    ? 'bg-linear-surface-2/80 border-b border-linear-hairline backdrop-blur-md'
    : 'bg-slate-50 border-b border-slate-200';

  const footerBg = isAuditor
    ? 'bg-linear-surface-2/70 border-t border-linear-hairline backdrop-blur-md'
    : 'bg-slate-50/80 border-t border-slate-200 backdrop-blur-sm';

  const subtitleColor = isAuditor ? 'text-linear-ink-muted' : 'text-slate-500';

  const closeButtonClasses = isAuditor
    ? 'p-1.5 rounded-lg text-linear-ink-muted hover:text-linear-ink hover:bg-linear-surface-3 transition-colors duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-linear-primary'
    : 'p-1.5 rounded-lg text-slate-400 hover:text-slate-700 hover:bg-slate-100 transition-colors duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-400';

  // Responsive mode: Fixed overlay on mobile, docked inline on desktop
  if (mode === 'docked') {
    return (
      <aside
        className={`shrink-0 flex flex-col sticky top-6 self-start max-h-[calc(100dvh-3.5rem)] border rounded-2xl overflow-hidden ${widthClass} ${containerThemeClasses} ${className}`}
        aria-label="Detail Inspector"
      >
        {/* Pinned Header */}
        <div className={`px-4 py-3 shrink-0 flex items-center justify-between gap-2 ${headerBg}`}>
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2">
              <h3 className="text-sm font-semibold truncate tracking-tight">{title}</h3>
              {headerBadge}
            </div>
            {subtitle && (
              <div className={`text-xs ${subtitleColor} truncate mt-0.5 font-normal`}>
                {subtitle}
              </div>
            )}
          </div>
          <button
            type="button"
            onClick={onClose}
            className={closeButtonClasses}
            title="Close inspector (Esc)"
            aria-label="Close inspector"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Scrollable Body */}
        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          <ErrorBoundary portalTheme={portalTheme} fallbackTitle="Inspector Error">
            {children}
          </ErrorBoundary>
        </div>

        {/* Pinned Footer */}
        {footer && (
          <div className={`px-4 py-3 shrink-0 ${footerBg}`}>
            {footer}
          </div>
        )}
      </aside>
    );
  }

  // Drawer (fixed right overlay)
  if (mode === 'drawer') {
    return (
      <div className="fixed inset-0 z-50 flex justify-end bg-slate-950/45 backdrop-blur-xs animate-in fade-in duration-200">
        <div
          className="fixed inset-0"
          onClick={onClose}
          aria-hidden="true"
        />
        <aside
          className={`relative z-10 flex flex-col h-full shadow-2xl border-l animate-in slide-in-from-right duration-240 overflow-hidden ${widthClass} ${containerThemeClasses} ${className}`}
          aria-label="Detail Sheet"
        >
          {/* Pinned Header */}
          <div className={`px-5 py-3.5 shrink-0 flex items-center justify-between gap-2 ${headerBg}`}>
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2">
                <h3 className="text-sm font-semibold truncate tracking-tight">{title}</h3>
                {headerBadge}
              </div>
              {subtitle && (
                <div className={`text-xs ${subtitleColor} truncate mt-0.5 font-normal`}>
                  {subtitle}
                </div>
              )}
            </div>
            <button
              type="button"
              onClick={onClose}
              className={closeButtonClasses}
              title="Close sheet (Esc)"
              aria-label="Close sheet"
            >
              <X className="w-4 h-4" />
            </button>
          </div>

          {/* Scrollable Body */}
          <div className="flex-1 overflow-y-auto p-5 space-y-4">
            <ErrorBoundary portalTheme={portalTheme} fallbackTitle="Inspector Error">
              {children}
            </ErrorBoundary>
          </div>

          {/* Pinned Footer */}
          {footer && (
            <div className={`px-5 py-3.5 shrink-0 ${footerBg}`}>
              {footer}
            </div>
          )}
        </aside>
      </div>
    );
  }

  // Responsive: Docked on desktop, drawer overlay on mobile
  return (
    <>
      {/* Mobile drawer overlay */}
      <div className="lg:hidden fixed inset-0 z-50 flex justify-end bg-slate-950/45 backdrop-blur-xs animate-in fade-in duration-200">
        <div className="fixed inset-0" onClick={onClose} aria-hidden="true" />
        <aside
          className={`relative z-10 flex flex-col h-full w-full max-w-md shadow-2xl border-l animate-in slide-in-from-right duration-240 overflow-hidden ${containerThemeClasses}`}
        >
          <div className={`px-4 py-3 shrink-0 flex items-center justify-between gap-2 ${headerBg}`}>
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2">
                <h3 className="text-sm font-semibold truncate tracking-tight">{title}</h3>
                {headerBadge}
              </div>
              {subtitle && (
                <div className={`text-xs ${subtitleColor} truncate mt-0.5 font-normal`}>{subtitle}</div>
              )}
            </div>
            <button
              type="button"
              onClick={onClose}
              className={closeButtonClasses}
              title="Close drawer (Esc)"
              aria-label="Close drawer"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
          <div className="flex-1 overflow-y-auto p-4 space-y-4">
            <ErrorBoundary portalTheme={portalTheme} fallbackTitle="Inspector Error">
              {children}
            </ErrorBoundary>
          </div>
          {footer && <div className={`px-4 py-3 shrink-0 ${footerBg}`}>{footer}</div>}
        </aside>
      </div>

      {/* Desktop docked pane */}
      <aside
        className={`hidden lg:flex shrink-0 flex-col sticky top-6 self-start max-h-[calc(100dvh-3.5rem)] border rounded-2xl overflow-hidden ${widthClass} ${containerThemeClasses} ${className}`}
        aria-label="Detail Inspector"
      >
        <div className={`px-4 py-3 shrink-0 flex items-center justify-between gap-2 ${headerBg}`}>
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2">
              <h3 className="text-sm font-semibold truncate tracking-tight">{title}</h3>
              {headerBadge}
            </div>
            {subtitle && (
              <div className={`text-xs ${subtitleColor} truncate mt-0.5 font-normal`}>{subtitle}</div>
            )}
          </div>
          <button
            type="button"
            onClick={onClose}
            className={closeButtonClasses}
            title="Close inspector (Esc)"
            aria-label="Close inspector"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          <ErrorBoundary portalTheme={portalTheme} fallbackTitle="Inspector Error">
            {children}
          </ErrorBoundary>
        </div>
        {footer && <div className={`px-4 py-3 shrink-0 ${footerBg}`}>{footer}</div>}
      </aside>
    </>
  );
}
