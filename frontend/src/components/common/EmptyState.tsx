import React from 'react';

export interface EmptyStateProps {
  icon?: React.ReactNode;
  title: string;
  description?: string;
  action?: React.ReactNode;
  portalTheme?: 'auditor' | 'hr';
  className?: string;
}

export function EmptyState({
  icon,
  title,
  description,
  action,
  portalTheme = 'auditor',
  className = '',
}: EmptyStateProps) {
  const isAuditor = portalTheme === 'auditor';

  return (
    <div
      className={`flex flex-col items-center justify-center text-center p-8 sm:p-12 ${
        isAuditor ? 'text-linear-ink-muted' : 'text-slate-500'
      } ${className}`}
    >
      {icon && (
        <div
          className={`mb-3 p-3 rounded-2xl flex items-center justify-center ${
            isAuditor
              ? 'bg-linear-surface-2 text-linear-ink-subtle border border-linear-hairline'
              : 'bg-slate-100 text-slate-400 border border-slate-200/80 shadow-2xs'
          }`}
        >
          {icon}
        </div>
      )}
      <h3
        className={`text-sm font-semibold tracking-tight ${
          isAuditor ? 'text-linear-ink' : 'text-slate-900'
        }`}
      >
        {title}
      </h3>
      {description && (
        <p
          className={`text-xs mt-1 max-w-sm ${
            isAuditor ? 'text-linear-ink-subtle' : 'text-slate-500'
          }`}
        >
          {description}
        </p>
      )}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}
