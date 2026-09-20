import React, { useRef } from 'react';

export interface SegmentedControlOption<T extends string = string> {
  value: T;
  label: React.ReactNode;
  icon?: React.ReactNode;
  badge?: React.ReactNode;
}

export interface SegmentedControlProps<T extends string = string> {
  value: T;
  onChange: (value: T) => void;
  options: SegmentedControlOption<T>[];
  size?: 'xs' | 'sm' | 'md';
  portalTheme?: 'auditor' | 'hr';
  fullWidth?: boolean;
  className?: string;
  ariaLabel?: string;
}

export function SegmentedControl<T extends string = string>({
  value,
  onChange,
  options,
  size = 'sm',
  portalTheme = 'auditor',
  fullWidth = false,
  className = '',
  ariaLabel,
}: SegmentedControlProps<T>) {
  const containerRef = useRef<HTMLDivElement>(null);

  const isAuditor = portalTheme === 'auditor';

  const containerClasses = isAuditor
    ? `p-0.5 rounded-lg border border-linear-hairline bg-linear-surface-2/80 shadow-2xs ${fullWidth ? 'flex w-full' : 'inline-flex'} items-center`
    : `p-0.5 rounded-xl border border-slate-200 bg-slate-100/80 shadow-2xs ${fullWidth ? 'flex w-full' : 'inline-flex'} items-center`;

  const sizeClasses =
    size === 'xs'
      ? 'px-2 py-1 text-[11px]'
      : size === 'md'
      ? 'px-3.5 py-1.5 text-xs'
      : 'px-2.5 py-1 text-xs';

  const handleKeyDown = (e: React.KeyboardEvent, currentIndex: number) => {
    if (e.key === 'ArrowRight' || e.key === 'ArrowDown') {
      e.preventDefault();
      const nextIndex = (currentIndex + 1) % options.length;
      onChange(options[nextIndex].value);
    } else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') {
      e.preventDefault();
      const prevIndex = (currentIndex - 1 + options.length) % options.length;
      onChange(options[prevIndex].value);
    }
  };

  return (
    <div
      ref={containerRef}
      role="tablist"
      aria-label={ariaLabel}
      className={`${containerClasses} ${className}`}
    >
      {options.map((opt, idx) => {
        const isSelected = opt.value === value;

        let itemClasses = '';
        if (isAuditor) {
          itemClasses = isSelected
            ? 'bg-linear-surface-1 text-linear-ink border border-linear-hairline shadow-xs font-semibold'
            : 'text-linear-ink-muted hover:text-linear-ink border border-transparent font-medium';
        } else {
          itemClasses = isSelected
            ? 'bg-white text-slate-900 shadow-xs font-semibold border border-slate-200/80'
            : 'text-slate-500 hover:text-slate-900 border border-transparent font-medium';
        }

        return (
          <button
            key={opt.value}
            type="button"
            role="tab"
            aria-selected={isSelected}
            tabIndex={isSelected ? 0 : -1}
            onClick={() => onChange(opt.value)}
            onKeyDown={(e) => handleKeyDown(e, idx)}
            className={`flex items-center ${fullWidth ? 'flex-1 justify-center' : ''} gap-1.5 rounded-md transition-all duration-150 focus-visible:outline-none focus-visible:ring-2 ${
              isAuditor ? 'focus-visible:ring-linear-primary' : 'focus-visible:ring-slate-400'
            } ${sizeClasses} ${itemClasses}`}
          >
            {opt.icon && <span className="shrink-0">{opt.icon}</span>}
            <span>{opt.label}</span>
            {opt.badge && <span className="shrink-0 ml-1">{opt.badge}</span>}
          </button>
        );
      })}
    </div>
  );
}
