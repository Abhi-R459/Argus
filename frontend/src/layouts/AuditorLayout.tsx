import { Outlet, Link, useLocation } from 'react-router-dom';
import { UserButton } from '@clerk/clerk-react';
import {
  ShieldCheck, Activity, FileSearch, LayoutDashboard, GitBranch,
  AlertTriangle, History, ShieldAlert, ArrowRight, Lock,
} from 'lucide-react';
import { useIncidentStatus } from '../services/auditService';
import RealtimeClock from '../components/common/RealtimeClock';
import { ErrorBoundary } from '../components/common/ErrorBoundary';

export default function AuditorLayout() {
  const location = useLocation();
  const incident = useIncidentStatus();

  const navItems = [
    { name: 'Overview', path: '/auditor/overview', icon: LayoutDashboard },
    { name: 'Audit Chain', path: '/auditor/chain', icon: GitBranch },
    { name: 'Audit Log', path: '/auditor/log', icon: FileSearch },
    { name: 'Time Travel', path: '/auditor/time-travel', icon: History },
    { name: 'Activity & Risk', path: '/auditor/activity', icon: AlertTriangle },
    { name: 'System Analytics', path: '/auditor/analytics', icon: Activity },
  ];

  const currentPath = location.pathname.split('/').pop()?.replace('-', ' ') || 'Overview';
  const pageTitle = currentPath.charAt(0).toUpperCase() + currentPath.slice(1);

  return (
    <div className="portal-auditor flex h-screen bg-linear-canvas text-linear-ink font-sans antialiased">
      {/* Sidebar - Linear Terminal Style */}
      <aside className="w-64 bg-linear-surface-1 border-r border-linear-hairline shadow-sm flex flex-col relative z-20">
        {/* Logo */}
        <div className="h-16 flex items-center px-6 border-b border-linear-hairline justify-between">
          <div className="flex items-center space-x-2.5">
            <div className="w-8 h-8 rounded-lg bg-linear-primary flex items-center justify-center text-white shadow-xs">
              <ShieldCheck className="w-5 h-5" />
            </div>
            <span className="text-lg font-bold text-linear-ink tracking-tight">
              Argus
            </span>
          </div>
          <span className="text-[10px] uppercase font-bold tracking-wider px-2 py-0.5 rounded-md bg-linear-primary/15 text-linear-primary border border-linear-primary/30">
            AUDITOR
          </span>
        </div>

        {/* Nav */}
        <nav className="flex-1 py-6 px-3.5 space-y-1 overflow-y-auto">
          <div className="px-3 pb-2 text-[11px] font-semibold text-linear-ink-subtle uppercase tracking-wider">
            Forensic Telemetry
          </div>
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = location.pathname.startsWith(item.path);
            const isRiskItem = item.name === 'Activity & Risk';
            const isChainItem = item.name === 'Audit Chain';

            return (
              <Link
                key={item.name}
                to={item.path}
                className={`flex items-center px-3 py-2 rounded-lg text-sm font-medium transition-colors duration-150 group focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-linear-primary ${
                  isActive
                    ? 'bg-linear-surface-2 text-linear-ink border border-linear-hairline-strong shadow-xs font-medium'
                    : 'text-linear-ink-muted hover:bg-linear-surface-2/60 hover:text-linear-ink border border-transparent'
                }`}
              >
                <Icon
                  className={`w-4.5 h-4.5 mr-3 transition-colors duration-150 ${
                    isActive ? 'text-linear-primary' : 'text-linear-ink-subtle group-hover:text-linear-ink'
                  }`}
                />
                <span className="truncate">{item.name}</span>

                {isRiskItem && incident.unreviewedFlagsCount > 0 && (
                  <span className="ml-auto px-1.5 py-0.5 rounded-md text-[10px] font-bold bg-grafana-orange/15 text-grafana-orange border border-grafana-orange/30">
                    {incident.unreviewedFlagsCount}
                  </span>
                )}

                {isChainItem && incident.isCompromised && (
                  <span className="ml-auto px-1.5 py-0.5 rounded-md text-[9px] font-extrabold uppercase tracking-wider bg-grafana-orange/20 text-grafana-orange border border-grafana-orange/40 animate-pulse">
                    ALERT
                  </span>
                )}

                {isActive && (
                  <span className="ml-auto w-1.5 h-1.5 rounded-full bg-linear-primary" />
                )}
              </Link>
            );
          })}
        </nav>

        {/* Footer system status */}
        <div className="p-3.5 border-t border-linear-hairline">
          {incident.isCompromised ? (
            <Link
              to={`/auditor/chain${incident.tamperedSeqId ? `?seq=${incident.tamperedSeqId}` : ''}`}
              className="flex items-center space-x-2.5 px-3 py-2 rounded-lg bg-grafana-orange/10 border border-grafana-orange/35 hover:bg-grafana-orange/20 transition-colors duration-150 group focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-grafana-orange"
              title="Click to inspect cryptographic breach in Chain Explorer"
            >
              <span className="w-2 h-2 rounded-full bg-grafana-orange" />
              <span className="text-xs font-semibold text-grafana-orange group-hover:text-grafana-orange-hover truncate">
                ⚠ Compromise Detected
              </span>
            </Link>
          ) : incident.unreviewedFlagsCount > 0 ? (
            <Link
              to="/auditor/activity"
              className="flex items-center space-x-2.5 px-3 py-2 rounded-lg bg-grafana-orange/10 border border-grafana-orange/30 hover:bg-grafana-orange/20 transition-colors duration-150 group focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-grafana-orange"
              title="Click to review suspicious activity flags"
            >
              <span className="w-2 h-2 rounded-full bg-grafana-orange" />
              <span className="text-xs font-medium text-grafana-orange group-hover:text-grafana-orange-hover truncate">
                {incident.unreviewedFlagsCount} Alert{incident.unreviewedFlagsCount > 1 ? 's' : ''} Pending
              </span>
            </Link>
          ) : (
            <div className="flex items-center space-x-2.5 px-3 py-2 rounded-lg bg-linear-surface-2 border border-linear-hairline">
              <span className="w-2 h-2 rounded-full bg-linear-success" />
              <span className="text-xs font-medium text-linear-ink-muted truncate">System Monitoring Active</span>
            </div>
          )}
        </div>
      </aside>

      {/* Main Content */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Header */}
        <header className="h-16 bg-linear-surface-1/90 backdrop-blur-md border-b border-linear-hairline flex items-center justify-between px-8 shadow-xs">
          <div className="flex items-center space-x-3">
            <Activity className="w-4 h-4 text-linear-primary" />
            <h1 className="text-base font-semibold text-linear-ink tracking-wide">
              {pageTitle}
            </h1>
            <div className="flex items-center space-x-1.5 px-2.5 py-1 rounded-md bg-linear-surface-2 border border-linear-hairline text-[11px] text-linear-ink-muted font-mono">
              <Lock className="w-3 h-3 text-linear-primary" />
              <span>Pool: compliance_auditor (Read-Only)</span>
            </div>
          </div>
          <div className="flex items-center space-x-4">
            <div className="flex items-center space-x-2 px-3 py-1.5 rounded-lg bg-linear-surface-2 border border-linear-hairline text-xs text-linear-ink-muted font-mono hidden md:flex shadow-2xs">
              <span className="text-[10px] font-bold text-linear-success tracking-wider">LIVE</span>
              <span className="text-linear-hairline-strong">|</span>
              <RealtimeClock showLiveDot={true} />
            </div>
            <div className="h-8 w-8 rounded-full ring-2 ring-linear-hairline-strong flex items-center justify-center overflow-hidden">
              <UserButton afterSignOutUrl="/" appearance={{ elements: { avatarBox: 'w-8 h-8' } }} />
            </div>
          </div>
        </header>

        {/* Persistent Incident Alert Banner */}
        {incident.isCompromised && (
          <div className="bg-gradient-to-r from-grafana-orange/20 via-grafana-orange/15 to-grafana-orange/20 border-b border-grafana-orange/40 px-8 py-3 flex items-center justify-between shadow-lg shadow-black/50 z-10 animate-fade-cascade">
            <div className="flex items-center space-x-3.5">
              <div className="w-8 h-8 rounded-lg bg-grafana-orange/20 border border-grafana-orange/40 flex items-center justify-center text-grafana-orange shrink-0">
                <ShieldAlert className="w-5 h-5 animate-pulse" />
              </div>
              <div>
                <div className="flex items-center space-x-2">
                  <span className="text-[11px] font-extrabold uppercase tracking-wider text-grafana-orange font-mono">
                    CRITICAL SECURITY ALERT
                  </span>
                  {incident.tamperedSeqId && (
                    <span className="text-[10px] font-mono font-semibold bg-grafana-orange/25 text-white px-2 py-0.5 rounded border border-grafana-orange/40">
                      Tampered Block #{incident.tamperedSeqId}
                    </span>
                  )}
                  {incident.anchorMismatch && (
                    <span className="text-[10px] font-mono font-semibold bg-grafana-orange/25 text-white px-2 py-0.5 rounded border border-grafana-orange/40">
                      External Anchor Mismatch
                    </span>
                  )}
                </div>
                <p className="text-xs text-linear-ink mt-0.5 font-medium">
                  {incident.details || 'Cryptographic chain verification detected tampering or anchor discrepancy.'}
                </p>
              </div>
            </div>
            <Link
              to={`/auditor/chain${incident.tamperedSeqId ? `?seq=${incident.tamperedSeqId}` : ''}`}
              className="shrink-0 flex items-center space-x-1.5 px-3.5 py-1.5 rounded-lg bg-grafana-orange hover:bg-grafana-orange-hover border border-grafana-orange text-white text-xs font-semibold transition-colors duration-150 shadow-xs group focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white"
            >
              <span>Inspect Compromised Block {incident.tamperedSeqId ? `#${incident.tamperedSeqId}` : ''}</span>
              <ArrowRight className="w-3.5 h-3.5 transition-transform duration-150 group-hover:translate-x-0.5" />
            </Link>
          </div>
        )}

        {/* Scrollable content */}
        <main className="flex-1 overflow-y-auto p-8 bg-linear-canvas">
          <div className="max-w-7xl mx-auto min-h-full">
            <ErrorBoundary portalTheme="auditor" fallbackTitle="Auditor Portal View Error">
              <Outlet />
            </ErrorBoundary>
          </div>
        </main>
      </div>
    </div>
  );
}
