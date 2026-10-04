import React, { useState } from 'react';
import { RefreshCw } from 'lucide-react';
import { Button, ButtonSize } from './Button';

export type RefreshButtonVariant = 'light' | 'dark' | 'icon-light' | 'icon-dark';

interface RefreshButtonProps {
  onRefresh: () => Promise<unknown> | void;
  label?: string;
  variant?: RefreshButtonVariant;
  className?: string;
  title?: string;
  size?: 'sm' | 'md';
}

export default function RefreshButton({
  onRefresh,
  label,
  variant = 'light',
  className = '',
  title = 'Refresh',
  size = 'md',
}: RefreshButtonProps) {
  const [isRefreshing, setIsRefreshing] = useState(false);

  const handleClick = async (e: React.MouseEvent<HTMLButtonElement>) => {
    e.preventDefault();
    if (isRefreshing) return;

    setIsRefreshing(true);
    // Guarantee a satisfying, snappy spin animation (min 250ms) to avoid glitchy flashes
    const minSpinTimer = new Promise((resolve) => setTimeout(resolve, 250));
    try {
      await Promise.allSettled([Promise.resolve(onRefresh()), minSpinTimer]);
    } finally {
      setIsRefreshing(false);
    }
  };

  const isDark = variant === 'dark' || variant === 'icon-dark';
  const isIconOnly = !label || variant.startsWith('icon-');
  const portalTheme = isDark ? 'auditor' : 'hr';

  const buttonSize: ButtonSize = isIconOnly
    ? size === 'sm'
      ? 'icon-xs'
      : 'icon-sm'
    : size === 'sm'
    ? 'sm'
    : 'md';

  const iconSize = size === 'sm' ? 'w-3 h-3' : 'w-3.5 h-3.5';
  const activeColor = isDark ? 'text-linear-primary' : 'text-grafana-orange';

  return (
    <Button
      variant="secondary"
      size={buttonSize}
      portalTheme={portalTheme}
      onClick={handleClick}
      disabled={isRefreshing}
      title={title}
      aria-label={label ? `${label} (${title})` : title}
      className={className}
      leftIcon={
        <RefreshCw
          className={`${iconSize} shrink-0 transition-transform duration-200 ${
            isRefreshing
              ? `animate-fast-spin ${activeColor}`
              : isDark
              ? 'text-linear-ink-muted'
              : 'text-grafana-neutral'
          }`}
        />
      }
    >
      {label && !isIconOnly ? label : undefined}
    </Button>
  );
}

