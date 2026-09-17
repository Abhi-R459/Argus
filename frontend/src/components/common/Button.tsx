import React from 'react';
import { Loader2 } from 'lucide-react';

export type ButtonVariant =
  | 'primary'
  | 'secondary'
  | 'ghost'
  | 'danger'
  | 'success'
  | 'outline'
  | 'link';

export type ButtonSize =
  | 'xs'
  | 'sm'
  | 'md'
  | 'lg'
  | 'icon-xs'
  | 'icon-sm'
  | 'icon-md'
  | 'icon-lg';

export type PortalTheme = 'auditor' | 'hr';

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  portalTheme?: PortalTheme;
  loading?: boolean;
  leftIcon?: React.ReactNode;
  rightIcon?: React.ReactNode;
}

const VARIANT_MAP: Record<PortalTheme, Record<ButtonVariant, string>> = {
  auditor: {
    primary:
      'bg-linear-primary hover:bg-linear-primary-hover active:bg-linear-primary-focus text-white border border-transparent shadow-xs',
    secondary:
      'bg-linear-surface-1 hover:bg-linear-surface-2 active:bg-linear-surface-3 border border-linear-hairline text-linear-ink shadow-2xs',
    ghost:
      'bg-transparent hover:bg-linear-surface-2 active:bg-linear-surface-3 text-linear-ink-muted hover:text-linear-ink border border-transparent',
    danger:
      'bg-rose-500/15 hover:bg-rose-500/25 active:bg-rose-500/35 border border-rose-500/30 text-rose-400',
    success:
      'bg-linear-success/15 hover:bg-linear-success/25 active:bg-linear-success/35 border border-linear-success/30 text-linear-success',
    outline:
      'bg-transparent hover:bg-linear-surface-1 active:bg-linear-surface-2 border border-linear-hairline text-linear-ink',
    link: 'bg-transparent text-linear-primary hover:text-linear-primary-hover underline-offset-2 hover:underline p-0 h-auto border-0 shadow-none',
  },
  hr: {
    primary:
      'bg-grafana-orange hover:bg-grafana-orange-hover active:bg-grafana-orange-pressed text-white border border-transparent shadow-xs',
    secondary:
      'bg-white hover:bg-grafana-surface active:bg-gray-100 border border-grafana-border text-grafana-ink shadow-2xs',
    ghost:
      'bg-transparent hover:bg-grafana-surface active:bg-gray-100 text-grafana-neutral hover:text-grafana-ink border border-transparent',
    danger:
      'bg-rose-50 hover:bg-rose-100 active:bg-rose-200 border border-rose-200 text-rose-700',
    success:
      'bg-emerald-50 hover:bg-emerald-100 active:bg-emerald-200 border border-emerald-200 text-emerald-700',
    outline:
      'bg-transparent hover:bg-grafana-surface active:bg-gray-100 border border-grafana-border text-grafana-ink',
    link: 'bg-transparent text-grafana-blue hover:text-grafana-blue/80 underline-offset-2 hover:underline p-0 h-auto border-0 shadow-none',
  },
};

const SIZE_MAP: Record<ButtonSize, string> = {
  xs: 'h-6 px-2 text-[11px] font-medium rounded-md gap-1',
  sm: 'h-7 px-2.5 text-xs font-medium rounded-lg gap-1.5',
  md: 'h-8 px-3.5 text-xs font-semibold rounded-lg gap-2',
  lg: 'h-9.5 px-4 text-sm font-semibold rounded-lg gap-2',
  'icon-xs': 'h-6 w-6 p-0 rounded-md shrink-0 justify-center',
  'icon-sm': 'h-7 w-7 p-0 rounded-lg shrink-0 justify-center',
  'icon-md': 'h-8 w-8 p-0 rounded-lg shrink-0 justify-center',
  'icon-lg': 'h-9.5 w-9.5 p-0 rounded-lg shrink-0 justify-center',
};

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  (
    {
      children,
      className = '',
      variant = 'secondary',
      size = 'md',
      portalTheme = 'auditor',
      loading = false,
      leftIcon,
      rightIcon,
      type = 'button',
      disabled = false,
      ...props
    },
    ref
  ) => {
    const isIconOnly = size.startsWith('icon-');
    const isLink = variant === 'link';

    // Press physics: scale only on medium/large solid action buttons
    const pressClass = isLink
      ? 'btn-press-subtle'
      : size === 'md' || size === 'lg'
      ? 'btn-press'
      : 'btn-press-sm';

    // Focus ring styling per portal theme
    const focusClass =
      portalTheme === 'auditor'
        ? 'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-linear-primary focus-visible:ring-offset-1 focus-visible:ring-offset-linear-canvas'
        : 'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-grafana-orange focus-visible:ring-offset-1 focus-visible:ring-offset-white';

    const disabledClass =
      'disabled:opacity-40 disabled:pointer-events-none disabled:cursor-not-allowed select-none';

    const baseClass = isLink
      ? 'inline-flex items-center cursor-pointer transition-colors'
      : `inline-flex items-center justify-center font-sans tracking-tight transition-all duration-150 cursor-pointer ${pressClass}`;

    const variantClass = VARIANT_MAP[portalTheme][variant] || VARIANT_MAP.auditor.secondary;
    const sizeClass = isLink ? '' : SIZE_MAP[size] || SIZE_MAP.md;

    const spinnerSize =
      size === 'xs' || size === 'icon-xs'
        ? 'w-3 h-3'
        : size === 'lg' || size === 'icon-lg'
        ? 'w-4 h-4'
        : 'w-3.5 h-3.5';

    return (
      <button
        ref={ref}
        type={type}
        disabled={disabled || loading}
        aria-busy={loading ? true : undefined}
        className={`${baseClass} ${variantClass} ${sizeClass} ${focusClass} ${disabledClass} ${className}`.trim()}
        {...props}
      >
        {loading ? (
          <>
            <Loader2 className={`${spinnerSize} animate-fast-spin shrink-0`} />
            {!isIconOnly && children && <span className="truncate">{children}</span>}
          </>
        ) : (
          <>
            {leftIcon && <span className="shrink-0 flex items-center">{leftIcon}</span>}
            {children && (!isIconOnly ? <span className="truncate">{children}</span> : children)}
            {rightIcon && <span className="shrink-0 flex items-center">{rightIcon}</span>}
          </>
        )}
      </button>
    );
  }
);

Button.displayName = 'Button';

export default Button;
