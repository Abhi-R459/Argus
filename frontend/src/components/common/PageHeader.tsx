import React from 'react';

export interface PageHeaderProps {
  title: string;
  description?: React.ReactNode;
  eyebrow?: string;
  icon?: React.ReactNode;
  action?: React.ReactNode;
  portalTheme?: 'auditor' | 'hr';
  className?: string;
}

/** Consistent page context and action placement across both Argus workspaces. */
export function PageHeader({
  title,
  description,
  eyebrow,
  icon,
  action,
  portalTheme = 'auditor',
  className = '',
}: PageHeaderProps) {
  const isAuditor = portalTheme === 'auditor';

  return (
    <header
      className={`argus-page-header flex flex-col gap-4 border-b pb-6 sm:flex-row sm:items-end sm:justify-between ${
        isAuditor ? 'border-linear-hairline' : 'border-portal-hairline'
      } ${className}`}
    >
      <div className="min-w-0">
        {eyebrow && (
          <p
            className={`mb-1 text-xs font-medium ${
              isAuditor ? 'text-linear-ink-subtle' : 'text-portal-ink-muted'
            }`}
          >
            {eyebrow}
          </p>
        )}
        <div className="flex items-center gap-3">
          {icon && (
            <span
              aria-hidden="true"
              className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-xl border ${
                isAuditor
                  ? 'border-linear-primary/25 bg-linear-primary/10 text-linear-primary'
                  : 'border-portal-hairline bg-portal-surface-2 text-portal-ink-muted'
              }`}
            >
              {icon}
            </span>
          )}
          <h1
            className={`text-2xl font-semibold tracking-tight leading-8 sm:text-[26px] ${
              isAuditor ? 'text-linear-ink' : 'text-portal-ink'
            }`}
          >
            {title}
          </h1>
        </div>
        {description && (
          <p
            className={`mt-2 max-w-3xl text-sm leading-6 ${
              isAuditor ? 'text-linear-ink-muted' : 'text-portal-ink-muted'
            }`}
          >
            {description}
          </p>
        )}
      </div>
      {action && <div className="flex shrink-0 flex-wrap items-center gap-2">{action}</div>}
    </header>
  );
}

export default PageHeader;
