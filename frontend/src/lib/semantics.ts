/**
 * Shared semantic tokens, badge styles, and status mappings for Argus.
 * Unifies action badges, severity dots/chips across HR Admin and Compliance Auditor portals.
 */

export type SemanticTheme = 'auditor' | 'hr';
export type AuditAction = 'INSERT' | 'UPDATE' | 'DELETE' | string;
export type AuditSeverity = 'low' | 'medium' | 'high' | 'critical' | string;

export interface SemanticBadgeStyle {
  bg: string;
  text: string;
  border: string;
  dotBg: string;
  combined: string;
}

/**
 * Returns unified Tailwind classes for action pills (INSERT, UPDATE, DELETE, COMPENSATION).
 */
export function getActionSemantic(
  action: string,
  tableName?: string,
  portalTheme: SemanticTheme = 'auditor'
): { label: string; className: string; dotClassName: string } {
  const normAction = (action || '').toUpperCase();
  const isSalary =
    (tableName || '').toLowerCase().includes('salary') ||
    normAction === 'COMPENSATION' ||
    normAction.includes('SALARY');

  if (portalTheme === 'hr') {
    if (isSalary) {
      return {
        label: 'Compensation',
        className: 'bg-purple-50 text-purple-700 border-purple-200/80 font-semibold',
        dotClassName: 'bg-purple-500',
      };
    }
    switch (normAction) {
      case 'INSERT':
        return {
          label: 'New Hire',
          className: 'bg-emerald-50 text-emerald-700 border-emerald-200/80 font-semibold',
          dotClassName: 'bg-emerald-600',
        };
      case 'UPDATE':
        return {
          label: 'Profile Update',
          className: 'bg-blue-50 text-blue-700 border-blue-200/80 font-semibold',
          dotClassName: 'bg-blue-600',
        };
      case 'DELETE':
        return {
          label: 'Deactivation',
          className: 'bg-rose-50 text-rose-700 border-rose-200/80 font-semibold',
          dotClassName: 'bg-rose-600',
        };
      default:
        return {
          label: normAction,
          className: 'bg-slate-100 text-slate-700 border-slate-200/80 font-semibold',
          dotClassName: 'bg-slate-500',
        };
    }
  }

  // Auditor portal (dark / linear terminal)
  if (isSalary) {
    return {
      label: normAction,
      className: 'bg-purple-500/15 text-purple-300 border-purple-500/30',
      dotClassName: 'bg-purple-400',
    };
  }
  switch (normAction) {
    case 'INSERT':
      return {
        label: 'INSERT',
        className: 'bg-linear-success/15 text-linear-success border-linear-success/30',
        dotClassName: 'bg-linear-success',
      };
    case 'UPDATE':
      return {
        label: 'UPDATE',
        className: 'bg-linear-primary/15 text-linear-primary border-linear-primary/30',
        dotClassName: 'bg-linear-primary',
      };
    case 'DELETE':
      return {
        label: 'DELETE',
        className: 'bg-grafana-orange/15 text-grafana-orange border-grafana-orange/30',
        dotClassName: 'bg-grafana-orange',
      };
    default:
      return {
        label: normAction,
        className: 'bg-linear-surface-2 text-linear-ink border-linear-hairline',
        dotClassName: 'bg-linear-ink-subtle',
      };
  }
}

/**
 * Returns color classes for severity dots (WCAG AA compliant).
 */
export function getSeverityDotClass(severity: string): string {
  const norm = (severity || 'low').toLowerCase();
  switch (norm) {
    case 'critical':
      return 'bg-grafana-orange';
    case 'high':
      return 'bg-orange-400';
    case 'medium':
      return 'bg-amber-400';
    case 'low':
    default:
      return 'bg-linear-ink-subtle';
  }
}

/**
 * Returns color classes for severity chips/badges (WCAG AA compliant).
 */
export function getSeverityChipClass(
  severity: string,
  portalTheme: SemanticTheme = 'auditor'
): string {
  const norm = (severity || 'low').toLowerCase();
  if (portalTheme === 'hr') {
    switch (norm) {
      case 'critical':
        return 'bg-rose-50 text-rose-700 border-rose-200/80';
      case 'high':
        return 'bg-orange-50 text-orange-700 border-orange-200/80';
      case 'medium':
        return 'bg-amber-50 text-amber-800 border-amber-200/80';
      case 'low':
      default:
        return 'bg-slate-100 text-slate-700 border-slate-200/80';
    }
  }

  // Auditor portal
  switch (norm) {
    case 'critical':
      return 'bg-grafana-orange/20 text-grafana-orange border-grafana-orange/40 font-semibold';
    case 'high':
      return 'bg-orange-500/15 text-orange-300 border-orange-500/30';
    case 'medium':
      return 'bg-amber-500/15 text-amber-300 border-amber-500/30';
    case 'low':
    default:
      return 'bg-linear-surface-2 text-linear-ink-muted border-linear-hairline';
  }
}
