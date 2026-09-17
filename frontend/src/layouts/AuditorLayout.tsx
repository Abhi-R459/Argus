import { Outlet, Link, useLocation } from 'react-router-dom';
import { UserButton } from '@clerk/clerk-react';
import {
  ShieldCheck, Activity, FileSearch, LayoutDashboard, GitBranch,
  AlertTriangle, History, ShieldAlert, ArrowRight, Lock,
} from 'lucide-react';
import { useIncidentStatus } from '../services/auditService';
import RealtimeClock from '../components/common/RealtimeClock';

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
    <div className="flex h-screen bg-[#0B0F17] text-slate-100 font-sans antialiased">
      {/* Sidebar - Datadog / SentinelOne Forensic Terminal */}
      <aside className="w-64 bg-[#0F172A]/90 backdrop-blur-md border-r border-slate-800/80 shadow-[1px_0_12px_rgba(0,0,0,0.4)] flex flex-col relative z-20">
        {/* Logo */}
        <div className="h-16 flex items-center px-6 border-b border-slate-800/80 justify-between">
          <div className="flex items-center space-x-2.5">
            <div className="w-8 h-8 rounded-lg bg-violet-600 flex items-center justify-center text-white shadow-[0_0_12px_rgba(139,92,246,0.4)]">
              <ShieldCheck className="w-5 h-5" />
            </div>
            <span className="text-lg font-bold text-slate-100 tracking-tight">
              Argus
            </span>
          </div>
          <span className="text-[10px] uppercase font-bold tracking-wider px-2 py-0.5 rounded-md bg-violet-500/15 text-violet-300 border border-violet-500/30">
            AUDITOR
          </span>
        </div>

        {/* Nav */}
        <nav className="flex-1 py-6 px-3.5 space-y-1 overflow-y-auto">
          <div className="px-3 pb-2 text-[11px] font-semibold text-slate-400 uppercase tracking-wider">
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
                className={`btn-press-sm flex items-center px-3 py-2 rounded-lg text-sm font-medium transition-colors duration-150 group ${
                  isActive
                    ? 'bg-violet-600/20 text-violet-200 border border-violet-500/40 shadow-[0_0_8px_rgba(139,92,246,0.15)]'
                    : 'text-slate-400 hover:bg-slate-800/70 hover:text-slate-200 border border-transparent'
                }`}
              >
                <Icon
                  className={`w-4.5 h-4.5 mr-3 transition-colors duration-150 ${
                    isActive ? 'text-violet-400' : 'text-slate-400 group-hover:text-slate-300'
                  }`}
                />
                <span className="truncate">{item.name}</span>

                {isRiskItem && incident.unreviewedFlagsCount > 0 && (
                  <span className="ml-auto px-1.5 py-0.5 rounded-md text-[10px] font-bold bg-amber-500/20 text-amber-300 border border-amber-500/30">
                    {incident.unreviewedFlagsCount}
                  </span>
                )}

                {isChainItem && incident.isCompromised && (
                  <span className="ml-auto px-1.5 py-0.5 rounded-md text-[9px] font-extrabold uppercase tracking-wider bg-rose-500/25 text-rose-300 border border-rose-500/40 animate-pulse">
                    ALERT
                  </span>
                )}

                {isActive && (!isRiskItem || incident.unreviewedFlagsCount === 0) && (!isChainItem || !incident.isCompromised) && (
                  <span className="ml-auto w-1.5 h-1.5 rounded-full bg-violet-400 shadow-[0_0_6px_rgba(139,92,246,0.8)]" />
                )}
              </Link>
            );
          })}
        </nav>

        {/* Footer system status */}
        <div className="p-3.5 border-t border-slate-800/80">
          {incident.isCompromised ? (
            <Link
              to={`/auditor/chain${incident.tamperedSeqId ? `?seq=${incident.tamperedSeqId}` : ''}`}
              className="btn-press-sm flex items-center space-x-2.5 px-3 py-2 rounded-lg bg-rose-500/10 border border-rose-500/30 hover:bg-rose-500/20 transition-colors duration-150 group"
              title="Click to inspect cryptographic breach in Chain Explorer"
            >
              <span className="w-2 h-2 rounded-full bg-rose-500 animate-ping shadow-[0_0_8px_rgba(244,63,94,0.9)]" />
              <span className="text-xs font-semibold text-rose-400 group-hover:text-rose-300 truncate">
                ⚠ Compromise Detected
              </span>
            </Link>
          ) : incident.unreviewedFlagsCount > 0 ? (
            <Link
              to="/auditor/activity"
              className="btn-press-sm flex items-center space-x-2.5 px-3 py-2 rounded-lg bg-amber-500/10 border border-amber-500/30 hover:bg-amber-500/20 transition-colors duration-150 group"
              title="Click to review suspicious activity flags"
            >
              <span className="w-2 h-2 rounded-full bg-amber-400 animate-pulse shadow-[0_0_8px_rgba(245,158,11,0.8)]" />
              <span className="text-xs font-medium text-amber-300 group-hover:text-amber-200 truncate">
                {incident.unreviewedFlagsCount} Alert{incident.unreviewedFlagsCount > 1 ? 's' : ''} Pending
              </span>
            </Link>
          ) : (
            <div className="flex items-center space-x-2.5 px-3 py-2 rounded-lg bg-emerald-500/10 border border-emerald-500/25">
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse shadow-[0_0_8px_rgba(52,211,153,0.8)]" />
              <span className="text-xs font-medium text-emerald-300 truncate">System Monitoring Active</span>
            </div>
          )}
        </div>
      </aside>

      {/* Main Content */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Header */}
        <header className="h-16 bg-[#0F172A]/70 backdrop-blur-md border-b border-slate-800/80 flex items-center justify-between px-8 shadow-xs">
          <div className="flex items-center space-x-3">
            <Activity className="w-4 h-4 text-violet-400" />
            <h1 className="text-base font-semibold text-slate-100 tracking-wide">
              {pageTitle}
            </h1>
            <div className="flex items-center space-x-1.5 px-2.5 py-1 rounded-md bg-slate-800/80 border border-slate-700/80 text-[11px] text-slate-300 font-mono">
              <Lock className="w-3 h-3 text-violet-400" />
              <span>Pool: compliance_auditor (Read-Only)</span>
            </div>
          </div>
          <div className="flex items-center space-x-4">
            <div className="flex items-center space-x-2 px-3 py-1.5 rounded-lg bg-slate-800/60 border border-slate-700/60 text-xs text-slate-300 font-mono hidden md:flex shadow-2xs">
              <span className="text-[10px] font-bold text-emerald-400 tracking-wider">LIVE</span>
              <span className="text-slate-600">|</span>
              <RealtimeClock showLiveDot={true} />
            </div>
            <div className="h-8 w-8 rounded-full ring-2 ring-violet-500/30 flex items-center justify-center overflow-hidden">
              <UserButton afterSignOutUrl="/" appearance={{ elements: { avatarBox: 'w-8 h-8' } }} />
            </div>
          </div>
        </header>

        {/* Persistent Incident Alert Banner */}
        {incident.isCompromised && (
          <div className="bg-gradient-to-r from-rose-950/90 via-rose-900/80 to-rose-950/90 border-b border-rose-500/40 px-8 py-3 flex items-center justify-between shadow-lg shadow-rose-950/50 z-10 animate-fade-cascade">
            <div className="flex items-center space-x-3.5">
              <div className="w-8 h-8 rounded-lg bg-rose-500/20 border border-rose-500/40 flex items-center justify-center text-rose-400 shrink-0">
                <ShieldAlert className="w-5 h-5 animate-pulse" />
              </div>
              <div>
                <div className="flex items-center space-x-2">
                  <span className="text-[11px] font-extrabold uppercase tracking-wider text-rose-400 font-mono">
                    CRITICAL SECURITY ALERT
                  </span>
                  {incident.tamperedSeqId && (
                    <span className="text-[10px] font-mono font-semibold bg-rose-500/25 text-rose-200 px-2 py-0.5 rounded border border-rose-500/40">
                      Tampered Block #{incident.tamperedSeqId}
                    </span>
                  )}
                  {incident.anchorMismatch && (
                    <span className="text-[10px] font-mono font-semibold bg-rose-500/25 text-rose-200 px-2 py-0.5 rounded border border-rose-500/40">
                      External Anchor Mismatch
                    </span>
                  )}
                </div>
                <p className="text-xs text-rose-200/90 mt-0.5 font-medium">
                  {incident.details || 'Cryptographic chain verification detected tampering or anchor discrepancy.'}
                </p>
              </div>
            </div>
            <Link
              to={`/auditor/chain${incident.tamperedSeqId ? `?seq=${incident.tamperedSeqId}` : ''}`}
              className="btn-press-sm shrink-0 flex items-center space-x-1.5 px-3.5 py-1.5 rounded-lg bg-rose-500/25 hover:bg-rose-500/35 border border-rose-500/40 text-rose-100 text-xs font-semibold transition-colors duration-150 shadow-xs group"
            >
              <span>Inspect Compromised Block {incident.tamperedSeqId ? `#${incident.tamperedSeqId}` : ''}</span>
              <ArrowRight className="w-3.5 h-3.5 transition-transform duration-150 group-hover:translate-x-0.5" />
            </Link>
          </div>
        )}

        {/* Scrollable content */}
        <main className="flex-1 overflow-y-auto p-8 bg-[#0B0F17]">
          <div className="max-w-7xl mx-auto h-full">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  );
}
