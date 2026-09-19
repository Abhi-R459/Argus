import { useState } from 'react';
import { Copy, Check } from 'lucide-react';

export interface CopyButtonProps {
  text: string;
  label?: string;
  copiedLabel?: string;
  portalTheme?: 'auditor' | 'hr';
  size?: 'xs' | 'sm' | 'md';
  className?: string;
  title?: string;
}

export function CopyButton({
  text,
  label,
  copiedLabel = 'Copied',
  portalTheme = 'auditor',
  size = 'xs',
  className = '',
  title = 'Copy to clipboard',
}: CopyButtonProps) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async (e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 1600);
    } catch {
      // Fallback
      setCopied(false);
    }
  };

  const isAuditor = portalTheme === 'auditor';

  const sizeClasses =
    size === 'xs'
      ? 'px-1.5 py-0.5 text-[11px] gap-1'
      : size === 'md'
      ? 'px-3 py-1.5 text-xs gap-1.5'
      : 'px-2 py-1 text-xs gap-1';

  const iconSize = size === 'xs' ? 'w-3 h-3' : 'w-3.5 h-3.5';

  const themeClasses = isAuditor
    ? 'text-linear-primary hover:text-white hover:bg-linear-surface-3 border border-transparent hover:border-linear-hairline focus-visible:ring-linear-primary'
    : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100 border border-slate-200/60 focus-visible:ring-slate-400';

  return (
    <button
      type="button"
      onClick={handleCopy}
      title={copied ? copiedLabel : title}
      aria-label={copied ? copiedLabel : title}
      className={`inline-flex items-center justify-center font-mono rounded-md transition-colors duration-150 focus-visible:outline-none focus-visible:ring-2 ${sizeClasses} ${themeClasses} ${className}`}
    >
      {copied ? (
        <>
          <Check className={`${iconSize} text-emerald-500`} />
          {copiedLabel && <span className="text-emerald-500 font-sans text-[11px]">{copiedLabel}</span>}
        </>
      ) : (
        <>
          <Copy className={iconSize} />
          {label && <span>{label}</span>}
        </>
      )}
    </button>
  );
}
