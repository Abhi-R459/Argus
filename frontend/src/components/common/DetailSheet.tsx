import React, { useEffect, useRef } from 'react';
import { createPortal } from 'react-dom';
import { X } from 'lucide-react';
import { ErrorBoundary } from './ErrorBoundary';
import { useModalTransition } from '../../hooks/useModalTransition';

export interface DetailSheetProps {
  isOpen: boolean;
  onClose: () => void;
  title: React.ReactNode;
  subtitle?: React.ReactNode;
  headerBadge?: React.ReactNode;
  children: React.ReactNode;
  footer?: React.ReactNode;
  portalTheme?: 'auditor' | 'hr';
  mode?: 'docked' | 'drawer' | 'responsive' | 'modal';
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
  const { isRendered, isVisible } = useModalTransition(isOpen, 240);

  // Cache last non-null content so modal content stays rendered during smooth exit transition
  const cachedContent = useRef({
    title,
    subtitle,
    headerBadge,
    children,
    footer,
  });

  if (isOpen) {
    cachedContent.current = {
      title,
      subtitle,
      headerBadge,
      children,
      footer,
    };
  }

  const activeTitle = isOpen ? title : cachedContent.current.title;
  const activeSubtitle = isOpen ? subtitle : cachedContent.current.subtitle;
  const activeHeaderBadge = isOpen ? headerBadge : cachedContent.current.headerBadge;
  const activeChildren = isOpen ? children : cachedContent.current.children;
  const activeFooter = isOpen ? footer : cachedContent.current.footer;

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

  // Centered Modal Dialog (Matching Add Personnel Dialog)
  if (mode === 'modal') {
    if (!isRendered) return null;

    return createPortal(
      <div
        className={`fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-6 bg-slate-950/65 modal-backdrop overflow-y-auto ${
          isVisible ? 'modal-backdrop-open' : ''
        }`}
      >
        {/* Backdrop click dismiss */}
        <div className="fixed inset-0" onClick={onClose} aria-hidden="true" />

        {/* Centered Modal Card with smooth pop up and going back transitions */}
        <div
          role="dialog"
          aria-modal="true"
          className={`relative z-10 w-full rounded-2xl shadow-2xl border overflow-hidden flex flex-col my-auto modal-dialog-card ${
            isVisible ? 'modal-dialog-card-open' : ''
          } ${
            widthClass || (isAuditor ? 'max-w-2xl lg:max-w-3xl' : 'max-w-2xl')
          } ${containerThemeClasses} ${className}`}
        >
          {/* Pinned Header */}
          <div className={`px-6 py-4 shrink-0 flex items-center justify-between gap-3 ${headerBg}`}>
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2.5">
                <h3 className="text-base font-bold truncate tracking-tight">{activeTitle}</h3>
                {activeHeaderBadge}
              </div>
              {activeSubtitle && (
                <div className={`text-xs ${subtitleColor} truncate mt-0.5 font-normal`}>
                  {activeSubtitle}
                </div>
              )}
            </div>
            <button
              type="button"
              onClick={onClose}
              className={closeButtonClasses}
              title="Close modal (Esc)"
              aria-label="Close modal"
            >
              <X className="w-4 h-4" />
            </button>
          </div>

          {/* Scrollable Body */}
          <div className="flex-1 overflow-y-auto p-6 space-y-4 max-h-[calc(90dvh-8rem)]">
            <ErrorBoundary portalTheme={portalTheme} fallbackTitle="Inspector Error">
              {activeChildren}
            </ErrorBoundary>
          </div>

          {/* Pinned Footer */}
          {activeFooter && (
            <div className={`px-6 py-3.5 shrink-0 ${footerBg}`}>
              {activeFooter}
            </div>
          )}
        </div>
      </div>,
      document.body
    );
  }

  // Drawer (fixed right overlay)
  if (mode === 'drawer') {
    if (!isRendered) return null;

    return createPortal(
      <div
        className={`fixed inset-0 z-50 flex justify-end bg-slate-950/45 modal-backdrop overflow-hidden ${
          isVisible ? 'modal-backdrop-open' : ''
        }`}
      >
        <div
          className="fixed inset-0"
          onClick={onClose}
          aria-hidden="true"
        />
        <aside
          className={`relative z-10 flex flex-col h-full shadow-2xl border-l overflow-hidden drawer-slide-right ${
            isVisible ? 'drawer-slide-right-open' : ''
          } ${widthClass} ${containerThemeClasses} ${className}`}
          aria-label="Detail Sheet"
        >
          {/* Pinned Header */}
          <div className={`px-5 py-3.5 shrink-0 flex items-center justify-between gap-2 ${headerBg}`}>
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2">
                <h3 className="text-sm font-semibold truncate tracking-tight">{activeTitle}</h3>
                {activeHeaderBadge}
              </div>
              {activeSubtitle && (
                <div className={`text-xs ${subtitleColor} truncate mt-0.5 font-normal`}>
                  {activeSubtitle}
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
              {activeChildren}
            </ErrorBoundary>
          </div>

          {/* Pinned Footer */}
          {activeFooter && (
            <div className={`px-5 py-3.5 shrink-0 ${footerBg}`}>
              {activeFooter}
            </div>
          )}
        </aside>
      </div>,
      document.body
    );
  }

  // Non-portal / docked modes require isOpen to be true
  if (!isOpen) return null;

  // Responsive mode: Fixed overlay on mobile/tablet (<xl), docked inline on large desktop (>=xl)
  if (mode === 'docked') {
    return (
      <aside
        className={`shrink-0 flex flex-col sticky top-8 self-start max-h-[calc(100dvh-8rem)] border rounded-2xl overflow-hidden ${widthClass} ${containerThemeClasses} ${className}`}
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

  // Responsive: Docked on desktop (>=xl), drawer overlay on mobile/tablet (<xl)
  const mobileOverlay = (
    <div
      className={`xl:hidden fixed inset-0 z-50 flex justify-end bg-slate-950/45 modal-backdrop overflow-hidden ${
        isVisible ? 'modal-backdrop-open' : ''
      }`}
    >
      <div className="fixed inset-0" onClick={onClose} aria-hidden="true" />
      <aside
        className={`relative z-10 flex flex-col h-full w-full max-w-md shadow-2xl border-l overflow-hidden drawer-slide-right ${
          isVisible ? 'drawer-slide-right-open' : ''
        } ${containerThemeClasses}`}
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
  );

  return (
    <>
      {typeof document !== 'undefined' && createPortal(mobileOverlay, document.body)}

      {/* Desktop docked pane (>=xl) */}
      <aside
        className={`hidden xl:flex shrink-0 flex-col sticky top-8 self-start max-h-[calc(100dvh-8rem)] border rounded-2xl overflow-hidden ${widthClass} ${containerThemeClasses} ${className}`}
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
