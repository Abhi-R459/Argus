import React from 'react';

export interface DataTableRootProps extends React.HTMLAttributes<HTMLDivElement> {
  children: React.ReactNode;
  portalTheme?: 'auditor' | 'hr';
}

export function DataTableRoot({
  children,
  className = '',
  portalTheme = 'auditor',
  ...props
}: DataTableRootProps) {
  const baseClasses =
    portalTheme === 'auditor'
      ? 'w-full overflow-hidden rounded-xl border border-linear-hairline bg-linear-surface-1 shadow-sm'
      : 'w-full overflow-hidden rounded-xl border border-grafana-border bg-white shadow-sm';

  return (
    <div className={`${baseClasses} ${className}`} {...props}>
      <div className="w-full overflow-x-auto no-scrollbar">
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
      ? 'sticky top-0 z-10 bg-linear-surface-2 border-b border-linear-hairline text-linear-ink-muted'
      : 'sticky top-0 z-10 bg-grafana-surface border-b border-grafana-border text-grafana-neutral';

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
      className={`px-3 py-2 text-[11px] font-semibold uppercase tracking-wider select-none ${alignClass} ${className}`}
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
      : 'divide-y divide-grafana-border/50';

  return (
    <tbody className={`${divideClass} ${className}`} {...props}>
      {children}
    </tbody>
  );
}

export interface DataTableRowProps extends React.HTMLAttributes<HTMLTableRowElement> {
  children: React.ReactNode;
  isSelected?: boolean;
  isTampered?: boolean;
  isFresh?: boolean;
  portalTheme?: 'auditor' | 'hr';
}

export function DataTableRow({
  children,
  className = '',
  isSelected = false,
  isTampered = false,
  isFresh = false,
  portalTheme = 'auditor',
  ...props
}: DataTableRowProps) {
  let stateClasses = '';

  if (portalTheme === 'auditor') {
    if (isTampered) {
      stateClasses = 'bg-grafana-orange/15 border-l-2 border-grafana-orange text-grafana-orange';
    } else if (isSelected) {
      stateClasses = 'bg-linear-primary/10 border-l-2 border-linear-primary';
    } else if (isFresh) {
      stateClasses = 'bg-linear-primary/15 transition-colors duration-500';
    } else {
      stateClasses = 'hover:bg-linear-surface-2/60 border-l-2 border-transparent transition-colors duration-100';
    }
  } else {
    // HR portal
    if (isTampered) {
      stateClasses = 'bg-red-50 border-l-2 border-red-500 text-red-700';
    } else if (isSelected) {
      stateClasses = 'bg-orange-50/80 border-l-2 border-grafana-orange';
    } else if (isFresh) {
      stateClasses = 'bg-blue-50/60 transition-colors duration-500';
    } else {
      stateClasses = 'hover:bg-gray-50 border-l-2 border-transparent transition-colors duration-100';
    }
  }

  return (
    <tr
      className={`group cursor-pointer text-xs h-9 ${stateClasses} ${className}`}
      {...props}
    >
      {children}
    </tr>
  );
}

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
      className={`px-3 py-2 whitespace-nowrap ${alignClass} ${numClass} ${monoClass} ${className}`}
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
