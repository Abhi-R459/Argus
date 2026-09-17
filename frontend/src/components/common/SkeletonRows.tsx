export interface SkeletonRowsProps {
  rowCount?: number;
  columnCount?: number;
  portalTheme?: 'auditor' | 'hr';
}

export function SkeletonRows({
  rowCount = 5,
  columnCount = 6,
  portalTheme = 'auditor',
}: SkeletonRowsProps) {
  const isAuditor = portalTheme === 'auditor';

  const pulseBg = isAuditor
    ? 'bg-linear-surface-3/80'
    : 'bg-gray-200/80';

  const divideClass = isAuditor
    ? 'divide-y divide-linear-hairline/40'
    : 'divide-y divide-grafana-border/50';

  return (
    <tbody className={divideClass}>
      {Array.from({ length: rowCount }).map((_, rIdx) => (
        <tr key={`skeleton-row-${rIdx}`} className="h-9 animate-pulse">
          {Array.from({ length: columnCount }).map((_, cIdx) => (
            <td key={`skeleton-cell-${cIdx}`} className="px-3 py-2">
              <div
                className={`h-3.5 rounded ${pulseBg}`}
                style={{
                  width: `${60 + ((rIdx + cIdx) * 17) % 35}%`,
                }}
              />
            </td>
          ))}
        </tr>
      ))}
    </tbody>
  );
}
