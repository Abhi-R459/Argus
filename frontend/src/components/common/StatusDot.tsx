export type StatusDotVariant = 'success' | 'warning' | 'error' | 'info' | 'idle' | 'primary';

export interface StatusDotProps {
  variant?: StatusDotVariant;
  pulse?: boolean;
  size?: 'xs' | 'sm' | 'md';
  className?: string;
}

const COLOR_MAP: Record<StatusDotVariant, { bg: string; pulseBg: string }> = {
  success: { bg: 'bg-emerald-500', pulseBg: 'bg-emerald-400' },
  warning: { bg: 'bg-amber-500', pulseBg: 'bg-amber-400' },
  error: { bg: 'bg-status-warning', pulseBg: 'bg-status-warning' },
  info: { bg: 'bg-sky-500', pulseBg: 'bg-sky-400' },
  primary: { bg: 'bg-linear-primary', pulseBg: 'bg-linear-primary' },
  idle: { bg: 'bg-linear-ink-subtle', pulseBg: 'bg-linear-ink-subtle' },
};

const SIZE_MAP = {
  xs: 'w-1.5 h-1.5',
  sm: 'w-2 h-2',
  md: 'w-2.5 h-2.5',
};

export function StatusDot({
  variant = 'success',
  pulse = false,
  size = 'sm',
  className = '',
}: StatusDotProps) {
  const { bg, pulseBg } = COLOR_MAP[variant] || COLOR_MAP.idle;
  const sizeClass = SIZE_MAP[size] || SIZE_MAP.sm;

  return (
    <span className={`relative inline-flex items-center justify-center shrink-0 ${sizeClass} ${className}`}>
      {pulse && (
        <span
          className={`absolute inline-flex h-full w-full rounded-full opacity-75 animate-ping ${pulseBg}`}
        />
      )}
      <span className={`relative inline-flex rounded-full ${sizeClass} ${bg}`} />
    </span>
  );
}
