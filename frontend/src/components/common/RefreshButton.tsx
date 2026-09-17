import React, { useState } from 'react';
import { RefreshCw } from 'lucide-react';

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
    // Guarantee a satisfying, smooth spin animation (min 650ms) to avoid glitchy flashes
    const minSpinTimer = new Promise((resolve) => setTimeout(resolve, 650));
    try {
      await Promise.allSettled([Promise.resolve(onRefresh()), minSpinTimer]);
    } finally {
      setIsRefreshing(false);
    }
  };

  const isDark = variant === 'dark' || variant === 'icon-dark';
  const isIconOnly = !label || variant.startsWith('icon-');

  // Styling based on portal theme and button style
  let baseStyle = '';
  if (isIconOnly) {
    if (isDark) {
      baseStyle =
        'btn-press-sm p-1.5 rounded-lg text-slate-400 hover:text-slate-200 hover:bg-slate-800/80 border border-slate-700/60 transition-colors duration-150';
    } else {
      baseStyle =
        'btn-press-sm p-1.5 rounded-lg text-slate-500 hover:text-slate-800 hover:bg-slate-100 border border-slate-200/90 transition-colors duration-150';
    }
  } else {
    if (isDark) {
      baseStyle =
        'btn-press-sm inline-flex items-center space-x-2 px-3 py-2 rounded-xl bg-slate-800/80 hover:bg-slate-800 text-slate-200 text-xs font-semibold border border-slate-700/80 shadow-xs transition-colors duration-150';
    } else {
      baseStyle =
        'btn-press inline-flex items-center px-3.5 py-2 rounded-lg border border-slate-200/90 bg-white hover:bg-slate-50 text-slate-700 text-xs font-semibold shadow-xs transition-colors duration-150';
    }
  }

  const iconSize = size === 'sm' ? 'w-3 h-3' : 'w-3.5 h-3.5';
  const activeColor = isDark ? 'text-violet-400' : 'text-indigo-600';

  return (
    <button
      type="button"
      onClick={handleClick}
      disabled={isRefreshing}
      title={title}
      className={`cursor-pointer disabled:opacity-70 select-none ${baseStyle} ${className}`}
    >
      <RefreshCw
        className={`${iconSize} shrink-0 transition-transform duration-200 ${
          isRefreshing ? `animate-fast-spin ${activeColor}` : isDark ? 'text-slate-400' : 'text-slate-500'
        } ${label && !isIconOnly ? 'mr-1.5' : ''}`}
      />
      {label && !isIconOnly && (
        <span className="truncate">{label}</span>
      )}
    </button>
  );
}
