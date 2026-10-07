import { useState, useEffect } from 'react';
import { Outlet, Link, useLocation } from 'react-router-dom';
import { UserButton } from '@clerk/clerk-react';
import {
  ShieldCheck, Activity, FileSearch, LayoutDashboard, GitBranch,
  AlertTriangle, History, ShieldAlert, ArrowRight, Lock, Menu, X, GitCompare,
  FileCheck,
} from 'lucide-react';
import { useIncidentStatus } from '../services/auditService';
import RealtimeClock from '../components/common/RealtimeClock';
import { ErrorBoundary } from '../components/common/ErrorBoundary';

export default function AuditorLayout() {
  const location = useLocation();
  const incident = useIncidentStatus();
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);

  // Close mobile drawer upon navigation
  useEffect(() => {
    setIsMobileMenuOpen(false);
  }, [location.pathname]);

  const navGroups = [
    { label: 'Monitor', items: [
      { name: 'Overview', path: '/auditor/overview', icon: LayoutDashboard },
      { name: 'Activity & Risk', path: '/auditor/activity', icon: AlertTriangle },
      { name: 'System Analytics', path: '/auditor/analytics', icon: Activity },
    ] },
    { label: 'Investigate', items: [
      { name: 'Audit Chain', path: '/auditor/chain', icon: GitBranch },
      { name: 'Audit Log', path: '/auditor/log', icon: FileSearch },
      { name: 'Time Travel', path: '/auditor/time-travel', icon: History },
      { name: 'Counterfactual', path: '/auditor/counterfactual', icon: GitCompare },
    ] },
    { label: 'Evidence', items: [
      { name: 'Forensic Evidence', path: '/auditor/forensic-evidence', icon: FileCheck },
    ] },
  ];

  const pageTitleByPath: Record<string, string> = {
    '/auditor/overview': 'Overview',
    '/auditor/chain': 'Audit Chain',
    '/auditor/log': 'Audit Log',
    '/auditor/time-travel': 'Time Travel',
    '/auditor/counterfactual': 'Counterfactual',
    '/auditor/forensic-evidence': 'Forensic Evidence',
    '/auditor/activity': 'Activity & Risk',
    '/auditor/analytics': 'System Analytics',
  };
  const pageTitle = pageTitleByPath[location.pathname] ?? 'Auditor Portal';

  return (
    <div className="argus-app-shell portal-auditor flex h-dvh bg-linear-canvas text-linear-ink font-sans antialiased overflow-hidden">
      {/* Mobile Drawer Backdrop */}
      {isMobileMenuOpen && (
        <div
          className="fixed inset-0 bg-black/60 backdrop-blur-xs z-40 lg:hidden transition-opacity duration-200 ease-out"
          onClick={() => setIsMobileMenuOpen(false)}
          aria-hidden="true"
        />
      )}

      {/* Sidebar - Linear Terminal Style (Responsive Off-Canvas on <lg) */}
      <aside
        id="auditor-primary-navigation"
        className={`argus-sidebar fixed inset-y-0 left-0 z-50 w-64 border-r shadow-none flex flex-col transform transition-transform duration-240 ease-emil-drawer lg:translate-x-0 lg:static lg:z-20 shrink-0 ${
          isMobileMenuOpen ? 'translate-x-0 shadow-2xl' : '-translate-x-full'
        }`}
      >
        {/* Logo */}
        <div className="h-[58px] flex items-center px-5 border-b border-linear-hairline justify-between shrink-0">
          <div className="flex items-center space-x-2.5">
            <div className="w-8 h-8 rounded-lg bg-linear-surface-3 border border-linear-hairline-strong flex items-center justify-center text-linear-primary">
              <ShieldCheck className="w-[17px] h-[17px]" />
            </div>
            <span className="text-[15px] font-semibold text-linear-ink tracking-tight">
              Argus
            </span>
          </div>
          <div className="flex items-center space-x-2">
            <span className="text-[10px] uppercase font-semibold tracking-wide px-2 py-0.5 rounded-md bg-linear-surface-2 text-linear-ink-subtle border border-linear-hairline">
              AUDITOR
            </span>
            <button
              type="button"
              onClick={() => setIsMobileMenuOpen(false)}
              className="lg:hidden p-2 -mr-2 rounded-lg text-linear-ink-muted hover:text-linear-ink hover:bg-linear-surface-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-linear-primary"
              aria-label="Close menu"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Nav */}
        <nav className="flex-1 py-2 px-3 overflow-y-auto">
          {navGroups.map((group) => (
            <section key={group.label} aria-label={group.label}>
              <h2 className="argus-nav-group-label">{group.label}</h2>
              <div className="space-y-0.5">
          {group.items.map((item) => {
            const Icon = item.icon;
            const isActive = location.pathname.startsWith(item.path);
            const isRiskItem = item.name === 'Activity & Risk';
            const isChainItem = item.name === 'Audit Chain';

            return (
              <Link
                key={item.name}
                to={item.path}
                aria-current={isActive ? 'page' : undefined}
                className={`flex items-center px-3 py-2 rounded-lg text-sm font-medium transition-colors duration-150 group focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-linear-primary ${
                  isActive
                    ? 'bg-linear-surface-2 text-linear-ink border border-transparent border-l-2 border-l-linear-primary font-medium'
                    : 'text-linear-ink-muted hover:bg-linear-surface-2/60 hover:text-linear-ink border border-transparent'
                }`}
              >
                <Icon
                  className={`w-4 h-4 mr-3 transition-colors duration-150 ${
                    isActive ? 'text-linear-primary' : 'text-linear-ink-subtle group-hover:text-linear-ink'
                  }`}
                />
                <span className="truncate">{item.name}</span>

                {isRiskItem && incident.unreviewedFlagsCount > 0 && (
                  <span className="ml-auto px-1.5 py-0.5 rounded-md text-[10px] font-bold bg-status-warning/15 text-status-warning border border-status-warning/30">
                    {incident.unreviewedFlagsCount}
                  </span>
                )}

                {isChainItem && incident.isCompromised && (
                  <span className="ml-auto px-1.5 py-0.5 rounded-md text-[10px] font-bold uppercase tracking-wider bg-status-warning/20 text-status-warning border border-status-warning/40">
                    ALERT
                  </span>
                )}

                {isActive && (
                  <span className="ml-auto w-1.5 h-1.5 rounded-full bg-linear-primary" />
                )}
              </Link>
            );
          })}
              </div>
            </section>
          ))}
        </nav>

        {/* Footer system status */}
        <div className="p-3.5 border-t border-linear-hairline">
          {incident.isCompromised ? (
            <Link
              to={`/auditor/chain${incident.tamperedSeqId ? `?seq=${incident.tamperedSeqId}&inspect=true` : ''}`}
              className="flex items-center space-x-2.5 px-3 py-2 rounded-lg bg-status-warning/10 border border-status-warning/35 hover:bg-status-warning/20 transition-colors duration-150 group focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-status-warning"
              title="Click to inspect cryptographic breach in Chain Explorer"
            >
              <span className="w-2 h-2 rounded-full bg-status-warning" />
              <span className="text-xs font-semibold text-status-warning group-hover:text-status-warning-hover truncate">
                ⚠ Compromise Detected
              </span>
            </Link>
          ) : incident.unreviewedFlagsCount > 0 ? (
            <Link
              to="/auditor/activity"
              className="flex items-center space-x-2.5 px-3 py-2 rounded-lg bg-status-warning/10 border border-status-warning/30 hover:bg-status-warning/20 transition-colors duration-150 group focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-status-warning"
              title="Click to review suspicious activity flags"
            >
              <span className="w-2 h-2 rounded-full bg-status-warning" />
              <span className="text-xs font-medium text-status-warning group-hover:text-status-warning-hover truncate">
                {incident.unreviewedFlagsCount} Alert{incident.unreviewedFlagsCount > 1 ? 's' : ''} Pending
              </span>
            </Link>
          ) : incident.isUnavailable ? (
            <div className="flex items-center space-x-2.5 px-3 py-2 rounded-lg bg-status-warning/10 border border-status-warning/25" role="status">
              <span className="w-2 h-2 rounded-full bg-status-warning" />
              <span className="text-xs font-medium text-status-warning truncate">Monitoring status unavailable</span>
            </div>
          ) : (
            <div className="flex items-center space-x-2.5 px-3 py-2 rounded-lg bg-linear-surface-2 border border-linear-hairline">
              <span className="w-2 h-2 rounded-full bg-linear-success" />
              <span className="text-xs font-medium text-linear-ink-muted truncate">System Monitoring Active</span>
            </div>
          )}
        </div>
      </aside>

      {/* Main Content */}
      <div className="flex-1 flex flex-col overflow-hidden min-w-0">
        {/* Header - Aligned to max-w-7xl content container */}
        <header className="argus-topbar bg-linear-surface-1 border-b border-linear-hairline flex items-center px-4 sm:px-6 lg:px-7 shrink-0">
          <div className="argus-content-frame mx-auto flex items-center justify-between gap-3">
            <div className="flex items-center space-x-2 sm:space-x-3">
              <button
                type="button"
                onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)}
                aria-controls="auditor-primary-navigation"
                aria-expanded={isMobileMenuOpen}
                className="lg:hidden p-1.5 -ml-1 mr-1 rounded-lg text-linear-ink-subtle hover:text-linear-ink hover:bg-linear-surface-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-linear-primary"
                aria-label="Toggle navigation menu"
              >
                <Menu className="w-5 h-5" />
              </button>
              <span className="hidden sm:inline text-xs text-linear-ink-subtle">Workspace</span>
              <span className="hidden sm:inline text-linear-hairline-strong">/</span>
              <span aria-hidden="true" className="text-sm font-semibold text-linear-ink-muted tracking-wide">
                {pageTitle}
              </span>
              <div className="hidden sm:flex items-center space-x-1.5 px-2 py-1 rounded-md bg-linear-surface-2 border border-linear-hairline text-[11px] text-linear-ink-muted">
                <Lock className="w-3 h-3 text-linear-primary" />
                <span>Pool: compliance_auditor (Read-Only)</span>
              </div>
            </div>
            <div className="flex items-center space-x-3 sm:space-x-4">
              <div className="hidden md:flex items-center space-x-2 px-2.5 py-1.5 rounded-lg text-xs text-linear-ink-subtle">
                <span className="w-1.5 h-1.5 rounded-full bg-linear-success" aria-hidden="true" />
                <RealtimeClock showLiveDot={false} />
              </div>
              <div className="h-8 w-8 rounded-full ring-2 ring-linear-hairline-strong flex items-center justify-center overflow-hidden">
                <UserButton afterSignOutUrl="/" appearance={{ elements: { avatarBox: 'w-8 h-8' } }} />
              </div>
            </div>
          </div>
        </header>

        {/* Persistent Incident Alert Banner */}
        {incident.isCompromised && (
          <div className="border-b border-rose-500/40 bg-rose-950/35 px-4 sm:px-6 lg:px-7 py-3 z-10 shrink-0">
            <div className="argus-content-frame mx-auto flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
              <div className="flex items-center space-x-3.5">
                <div className="w-8 h-8 rounded-lg bg-rose-500/10 border border-rose-400/30 flex items-center justify-center text-rose-300 shrink-0">
                  <ShieldAlert className="w-5 h-5" />
                </div>
                <div>
                  <div className="flex items-center space-x-2">
                      <span className="text-xs font-semibold text-rose-200">
                      CRITICAL SECURITY ALERT
                    </span>
                    {incident.tamperedSeqId && (
                        <span className="text-xs font-mono font-medium bg-rose-500/15 text-rose-100 px-2 py-0.5 rounded border border-rose-400/30">
                        Tampered Block #{incident.tamperedSeqId}
                      </span>
                    )}
                    {incident.anchorMismatch && (
                        <span className="text-xs font-mono font-medium bg-rose-500/15 text-rose-100 px-2 py-0.5 rounded border border-rose-400/30">
                        Anchor Record Mismatch
                      </span>
                    )}
                  </div>
                  <p className="text-sm text-rose-100 mt-1">
                    {incident.details || 'Cryptographic chain verification detected tampering or anchor discrepancy.'}
                  </p>
                </div>
              </div>
              <Link
                to={`/auditor/chain${incident.tamperedSeqId ? `?seq=${incident.tamperedSeqId}&inspect=true` : ''}`}
                className="shrink-0 flex items-center space-x-1.5 px-3 py-2 rounded-lg bg-rose-600 hover:bg-rose-500 border border-rose-500 text-white text-sm font-medium transition-colors duration-150 group focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white"
              >
                <span>Inspect Compromised Block {incident.tamperedSeqId ? `#${incident.tamperedSeqId}` : ''}</span>
                <ArrowRight className="w-3.5 h-3.5 transition-transform duration-150 group-hover:translate-x-0.5" />
              </Link>
            </div>
          </div>
        )}

        {/* Scrollable content */}
        <main className="flex-1 overflow-y-auto p-4 sm:p-6 lg:p-8 bg-linear-canvas">
          <div className="argus-content-frame mx-auto min-h-full">
            <ErrorBoundary portalTheme="auditor" fallbackTitle="Auditor Portal View Error">
              <Outlet />
            </ErrorBoundary>
          </div>
        </main>
      </div>
    </div>
  );
}
