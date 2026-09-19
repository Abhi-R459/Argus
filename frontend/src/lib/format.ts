/**
 * Unified formatting utilities for Argus.
 * Provides module-level cached formatters for INR currency, relative time,
 * hash truncation, and employee reference formatting.
 */

const inrIntegerFormatter = new Intl.NumberFormat('en-IN', {
  style: 'currency',
  currency: 'INR',
  maximumFractionDigits: 0,
});

const inrDecimalFormatter = new Intl.NumberFormat('en-IN', {
  style: 'currency',
  currency: 'INR',
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

/**
 * Formats a number or string amount into Indian Rupee (INR) currency format (₹ XX,XX,XXX).
 */
export function formatINR(amount: number | string | null | undefined, showDecimals: boolean = false): string {
  if (amount === null || amount === undefined || amount === '') return '—';
  const num = typeof amount === 'string' ? parseFloat(amount) : amount;
  if (isNaN(num)) return '—';
  return showDecimals ? inrDecimalFormatter.format(num) : inrIntegerFormatter.format(num);
}

/**
 * Formats an ISO 8601 timestamp into a standardized relative time string.
 */
export function formatRelativeTime(isoString: string | null | undefined): string {
  if (!isoString) return '—';
  const date = new Date(isoString);
  const now = Date.now();
  const diffMs = Math.max(0, now - date.getTime());
  const seconds = Math.floor(diffMs / 1000);

  if (seconds < 5) return 'just now';
  if (seconds < 60) return `${seconds}s ago`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days < 30) return `${days}d ago`;
  return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
}

/**
 * Truncates a SHA-256 or cryptographic hash string to a human-readable snippet (e.g., "7a8f12…4b9c").
 */
export function truncateHash(hash: string | null | undefined, start: number = 6, end: number = 4): string {
  if (!hash) return '000000…0000';
  if (hash.length <= start + end + 3) return hash;
  return `${hash.slice(0, start)}…${hash.slice(-end)}`;
}

/**
 * Formats an employee ID into standard #EMP-XXXX representation.
 */
export function formatEmployeeRef(id: number | string | null | undefined): string {
  if (id === null || id === undefined || id === '') return '—';
  const clean = String(id).replace(/[^0-9]/g, '');
  const padded = clean ? clean.padStart(4, '0') : String(id);
  return `#EMP-${padded}`;
}

/**
 * Formats an ISO 8601 date to standard local date representation.
 */
export function formatDate(isoString: string | null | undefined): string {
  if (!isoString) return '—';
  const date = new Date(isoString);
  return date.toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  });
}
