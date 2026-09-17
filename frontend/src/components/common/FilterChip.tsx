import { X } from 'lucide-react';

export interface FilterChipProps {
  label: string;
  value: string;
  onRemove: () => void;
  portalTheme?: 'auditor' | 'hr';
  className?: string;
}

export function FilterChip({
  label,
  value,
  onRemove,
  portalTheme = 'auditor',
  className = '',
}: FilterChipProps) {
  if (portalTheme === 'auditor') {
    return (
      <span
        className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-xs bg-linear-surface-3 border border-linear-hairline text-linear-ink ${className}`}
      >
        <span className="text-linear-ink-muted font-normal">{label}:</span>
        <span className="font-medium text-linear-ink">{value}</span>
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation();
            onRemove();
          }}
          className="ml-0.5 p-0.5 rounded hover:bg-linear-surface-4 text-linear-ink-muted hover:text-linear-ink transition-colors duration-100 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-linear-primary"
          title={`Remove ${label} filter`}
          aria-label={`Remove ${label} filter`}
        >
          <X className="w-3 h-3" />
        </button>
      </span>
    );
  }

  // HR light theme
  return (
    <span
      className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-xs bg-gray-100 border border-grafana-border text-grafana-ink ${className}`}
    >
      <span className="text-grafana-neutral font-normal">{label}:</span>
      <span className="font-medium text-grafana-ink">{value}</span>
      <button
        type="button"
        onClick={(e) => {
          e.stopPropagation();
          onRemove();
        }}
        className="ml-0.5 p-0.5 rounded hover:bg-gray-200 text-grafana-neutral hover:text-grafana-ink transition-colors duration-100 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-grafana-orange"
        title={`Remove ${label} filter`}
        aria-label={`Remove ${label} filter`}
      >
        <X className="w-3 h-3" />
      </button>
    </span>
  );
}
