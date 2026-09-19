import React from 'react';

export interface DataTableRootProps extends React.HTMLAttributes<HTMLDivElement> {
  children: React.ReactNode;
  portalTheme?: 'auditor' | 'hr';
  maxHeight?: string;
}

export function DataTableRoot({
  children,
  className = '',
  portalTheme = 'auditor',
  maxHeight,
  ...props
}: DataTableRootProps) {
  const baseClasses =
    portalTheme === 'auditor'
      ? 'w-full rounded-xl border border-linear-hairline bg-linear-surface-1 shadow-sm'
      : 'w-full rounded-2xl border border-slate-200/80 bg-white shadow-xs';

  return (
    <div className={`${baseClasses} ${className}`} {...props}>
      <div
        className="w-full overflow-x-auto rounded-[inherit]"
        style={maxHeight ? { maxHeight, overflowY: 'auto' } : undefined}
      >
        <table className="w-full text-left border-collapse">{children}</table>
      </div>
    </div>
  );
}

export interface DataTableHeaderProps extends React.HTMLAttributes<HTMLTableSectionElement> {
  children: React.ReactNode;
  portalTheme?: 'auditor' | 'hr';
}

export function DataTableHeader({
  children,
  className = '',
  portalTheme = 'auditor',
  ...props
}: DataTableHeaderProps) {
  const headerBg =
    portalTheme === 'auditor'
      ? 'sticky top-0 z-10 bg-linear-surface-2/95 backdrop-blur-xs border-b border-linear-hairline text-linear-ink-muted shadow-2xs'
      : 'sticky top-0 z-10 bg-slate-50/95 backdrop-blur-xs border-b border-slate-200 text-slate-600 shadow-2xs';

  return (
    <thead className={`${headerBg} ${className}`} {...props}>
      {children}
    </thead>
  );
}

export interface DataTableHeadCellProps extends React.ThHTMLAttributes<HTMLTableCellElement> {
  children?: React.ReactNode;
  align?: 'left' | 'center' | 'right';
}

export function DataTableHeadCell({
  children,
  className = '',
  align = 'left',
  ...props
}: DataTableHeadCellProps) {
  const alignClass =
    align === 'right' ? 'text-right' : align === 'center' ? 'text-center' : 'text-left';

  return (
    <th
      className={`px-3.5 py-2.5 text-[11px] font-semibold uppercase tracking-wider select-none ${alignClass} ${className}`}
      {...props}
    >
      {children}
    </th>
  );
}

export interface DataTableBodyProps extends React.HTMLAttributes<HTMLTableSectionElement> {
  children: React.ReactNode;
  portalTheme?: 'auditor' | 'hr';
}

export function DataTableBody({
  children,
  className = '',
  portalTheme = 'auditor',
  ...props
}: DataTableBodyProps) {
  const divideClass =
    portalTheme === 'auditor'
      ? 'divide-y divide-linear-hairline/40'
      : 'divide-y divide-slate-100';

  return (
    <tbody className={`${divideClass} ${className}`} {...props}>
      {children}
    </tbody>
  );
}

export interface DataTableRowProps extends React.HTMLAttributes<HTMLTableRowElement> {
  children: React.ReactNode;
  isSelected?: boolean;
  isFocused?: boolean;
  isTampered?: boolean;
  isFresh?: boolean;
  portalTheme?: 'auditor' | 'hr';
}

export const DataTableRow = React.forwardRef<HTMLTableRowElement, DataTableRowProps>(
  (
    {
      children,
      className = '',
      isSelected = false,
      isFocused = false,
      isTampered = false,
      isFresh = false,
      portalTheme = 'auditor',
      ...props
    },
    ref
  ) => {
    let stateClasses = '';

    if (portalTheme === 'auditor') {
      if (isTampered) {
        stateClasses = 'bg-grafana-orange/15 border-l-2 border-grafana-orange text-grafana-orange';
      } else if (isSelected) {
        stateClasses = 'bg-linear-primary/15 border-l-2 border-linear-primary font-medium';
      } else if (isFresh) {
        stateClasses = 'bg-linear-primary/15 transition-colors duration-500';
      } else {
        stateClasses = 'hover:bg-linear-surface-2/60 border-l-2 border-transparent transition-colors duration-100';
      }

      if (isFocused && !isSelected) {
        stateClasses += ' ring-1 ring-inset ring-linear-primary/70 bg-linear-surface-2/50';
      }
    } else {
      // HR portal
      if (isTampered) {
        stateClasses = 'bg-rose-50 border-l-2 border-rose-500 text-rose-700';
      } else if (isSelected) {
        stateClasses = 'bg-slate-100/90 border-l-2 border-slate-900 font-medium';
      } else if (isFresh) {
        stateClasses = 'bg-blue-50/60 transition-colors duration-500';
      } else {
        stateClasses = 'hover:bg-slate-50/80 border-l-2 border-transparent transition-colors duration-100';
      }

      if (isFocused && !isSelected) {
        stateClasses += ' ring-1 ring-inset ring-slate-400/60 bg-slate-50/60';
      }
    }

    return (
      <tr
        ref={ref}
        data-focused={isFocused ? 'true' : undefined}
        className={`group cursor-pointer text-xs min-h-[44px] transition-colors ${stateClasses} ${className}`}
        {...props}
      >
        {children}
      </tr>
    );
  }
);
DataTableRow.displayName = 'DataTableRow';

export interface DataTableCellProps extends React.TdHTMLAttributes<HTMLTableCellElement> {
  children: React.ReactNode;
  align?: 'left' | 'center' | 'right';
  tabularNums?: boolean;
  mono?: boolean;
}

export function DataTableCell({
  children,
  className = '',
  align = 'left',
  tabularNums = false,
  mono = false,
  ...props
}: DataTableCellProps) {
  const alignClass =
    align === 'right' ? 'text-right' : align === 'center' ? 'text-center' : 'text-left';
  const numClass = tabularNums ? 'tabular-nums' : '';
  const monoClass = mono ? 'font-mono' : '';

  return (
    <td
      className={`px-3.5 py-2.5 whitespace-nowrap ${alignClass} ${numClass} ${monoClass} ${className}`}
      {...props}
    >
      {children}
    </td>
  );
}

export const DataTable = {
  Root: DataTableRoot,
  Header: DataTableHeader,
  HeadCell: DataTableHeadCell,
  Body: DataTableBody,
  Row: DataTableRow,
  Cell: DataTableCell,
};
