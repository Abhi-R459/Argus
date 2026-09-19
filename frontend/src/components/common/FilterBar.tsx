import React from 'react';
import { FilterChip } from './FilterChip';
import { Button } from './Button';

export interface ActiveFilterItem {
  id: string;
  label: string;
  value: string;
  onRemove: () => void;
}

export interface FilterBarProps extends React.HTMLAttributes<HTMLDivElement> {
  children?: React.ReactNode;
  activeFilters?: ActiveFilterItem[];
  onClearAll?: () => void;
  portalTheme?: 'auditor' | 'hr';
}

export function FilterBar({
  children,
  activeFilters = [],
  onClearAll,
  portalTheme = 'auditor',
  className = '',
  ...props
}: FilterBarProps) {
  const hasActiveFilters = activeFilters.length > 0;

  const bgClasses =
    portalTheme === 'auditor'
      ? 'bg-linear-surface-1 border border-linear-hairline text-linear-ink'
      : 'bg-white border border-slate-200/80 text-slate-900';


  return (
    <div
      className={`p-3 rounded-2xl flex flex-col gap-2.5 shadow-xs ${bgClasses} ${className}`}
      {...props}
    >
      {children && (
        <div className="flex flex-wrap items-center justify-between gap-3">
          {children}
        </div>
      )}

      {hasActiveFilters && (
        <div className="flex flex-wrap items-center gap-2 pt-1 border-t border-inherit/40">
          <span
            className={`text-xs ${
              portalTheme === 'auditor' ? 'text-linear-ink-muted' : 'text-slate-500'
            }`}
          >
            Active filters:
          </span>
          {activeFilters.map((filter) => (
            <FilterChip
              key={filter.id}
              label={filter.label}
              value={filter.value}
              onRemove={filter.onRemove}
              portalTheme={portalTheme}
            />
          ))}
          {onClearAll && (
            <Button
              variant="link"
              portalTheme={portalTheme}
              onClick={onClearAll}
              className="text-xs font-medium ml-1"
            >
              Clear all
            </Button>
          )}
        </div>
      )}
    </div>
  );
}
