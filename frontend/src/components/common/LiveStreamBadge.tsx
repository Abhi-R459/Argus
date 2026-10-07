import { useState, useEffect } from 'react';
import { Pause, Play } from 'lucide-react';

export interface LiveStreamBadgeProps {
  isStreaming: boolean;
  onToggleStream: () => void;
  lastFetchedAt?: Date | number;
  portalTheme?: 'auditor' | 'hr';
  className?: string;
}

export function LiveStreamBadge({
  isStreaming,
  onToggleStream,
  lastFetchedAt,
  portalTheme = 'auditor',
  className = '',
}: LiveStreamBadgeProps) {
  const [secondsAgo, setSecondsAgo] = useState(0);

  useEffect(() => {
    if (!lastFetchedAt) return;

    const updateSeconds = () => {
      const fetchTime = typeof lastFetchedAt === 'number' ? lastFetchedAt : lastFetchedAt.getTime();
      const diff = Math.max(0, Math.floor((Date.now() - fetchTime) / 1000));
      setSecondsAgo(diff);
    };

    updateSeconds();
    const interval = setInterval(updateSeconds, 1000);
    return () => clearInterval(interval);
  }, [lastFetchedAt]);

  const isAuditor = portalTheme === 'auditor';

  const containerClasses = isAuditor
    ? 'bg-linear-surface-2 border border-linear-hairline text-linear-ink'
    : 'bg-white border border-slate-200 text-slate-900';

  const buttonHoverClasses = isAuditor
    ? 'hover:bg-linear-surface-3 text-linear-ink-muted hover:text-linear-ink'
    : 'hover:bg-slate-100 text-slate-500 hover:text-slate-900';

  return (
    <div
      className={`inline-flex items-center gap-2 px-2.5 py-1 rounded-lg text-xs font-medium shadow-xs ${containerClasses} ${className}`}
    >
      {isStreaming ? (
        <span className="flex items-center gap-1.5">
          <span className="relative flex h-2 w-2">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-linear-success opacity-75" />
            <span className="relative inline-flex rounded-full h-2 w-2 bg-linear-success" />
          </span>
          <span className="text-[11px] font-semibold text-linear-success uppercase tracking-wider">
            Streaming
          </span>
          <span className="text-[10px] text-linear-ink-muted tabular-nums">
            ({secondsAgo}s ago)
          </span>
        </span>
      ) : (
        <span className="flex items-center gap-1.5">
          <span className="inline-flex rounded-full h-2 w-2 bg-status-warning" />
          <span className="text-[11px] font-semibold text-status-warning uppercase tracking-wider">
            Paused
          </span>
        </span>
      )}

      <button
        type="button"
        onClick={onToggleStream}
        className={`ml-1 p-1 rounded transition-colors duration-100 focus-visible:outline-none focus-visible:ring-1 ${
          portalTheme === 'auditor' ? 'focus-visible:ring-linear-primary' : 'focus-visible:ring-status-warning'
        } ${buttonHoverClasses}`}
        title={isStreaming ? 'Pause live stream (p)' : 'Resume live stream (p)'}
        aria-label={isStreaming ? 'Pause live stream' : 'Resume live stream'}
      >
        {isStreaming ? (
          <Pause className="w-3 h-3" />
        ) : (
          <Play className="w-3 h-3" />
        )}
      </button>
    </div>
  );
}
