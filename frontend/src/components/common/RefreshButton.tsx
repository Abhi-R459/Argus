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
  const [refreshFailed, setRefreshFailed] = useState(false);

  const handleClick = async (e: React.MouseEvent<HTMLButtonElement>) => {
    e.preventDefault();
    if (isRefreshing) return;

    setIsRefreshing(true);
    setRefreshFailed(false);
    // Guarantee a satisfying, snappy spin animation (min 250ms) to avoid glitchy flashes
    const minSpinTimer = new Promise((resolve) => setTimeout(resolve, 250));
    const refreshPromise = Promise.resolve()
      .then(onRefresh)
      .then((result) => {
        if (result && typeof result === 'object' && 'isError' in result && result.isError) {
          throw new Error('The refresh request did not complete successfully.');
        }
      });
    const [refreshOutcome] = await Promise.allSettled([refreshPromise, minSpinTimer]);
    setRefreshFailed(refreshOutcome.status === 'rejected');
    setIsRefreshing(false);
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
  const activeColor = isDark ? 'text-linear-primary' : 'text-status-warning';

  return (
    <>
      <Button
        variant="secondary"
        size={buttonSize}
        portalTheme={portalTheme}
        onClick={handleClick}
        disabled={isRefreshing}
        title={refreshFailed ? `${title} failed. Try again.` : title}
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
      {refreshFailed && (
        <span className="text-xs font-medium text-status-warning" role="status" aria-live="polite">
          {title} failed. Try again.
        </span>
      )}
    </>
  );
}

