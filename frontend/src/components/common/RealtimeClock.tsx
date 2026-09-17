import { useState, useEffect } from 'react';

interface RealtimeClockProps {
  className?: string;
  showLiveDot?: boolean;
  showDate?: boolean;
}

export default function RealtimeClock({
  className = '',
  showLiveDot = false,
  showDate = false,
}: RealtimeClockProps) {
  const [time, setTime] = useState<Date>(() => new Date());

  useEffect(() => {
    // Tick every 1,000ms in sync with real-time clock
    const timer = setInterval(() => {
      setTime(new Date());
    }, 1000);

    return () => clearInterval(timer);
  }, []);

  const timeString = time.toLocaleTimeString([], {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });

  const dateString = time.toLocaleDateString([], {
    weekday: 'short',
    month: 'short',
    day: 'numeric',
  });

  return (
    <div className={`inline-flex items-center space-x-2 font-mono ${className}`}>
      {showLiveDot && (
        <span className="relative flex h-2 w-2 shrink-0">
          <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
          <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500" />
        </span>
      )}
      {showDate && (
        <>
          <span className="text-slate-400">{dateString}</span>
          <span className="text-slate-600">·</span>
        </>
      )}
      <span className="tabular-nums tracking-wider">{timeString}</span>
    </div>
  );
}
