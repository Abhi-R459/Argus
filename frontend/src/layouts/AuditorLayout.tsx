import { Outlet, Link, useLocation } from 'react-router-dom';
import { UserButton } from '@clerk/clerk-react';
import {
  ShieldCheck, Activity, FileSearch, LayoutDashboard, GitBranch,
  AlertTriangle, History, ShieldAlert, ArrowRight,
} from 'lucide-react';
import { useIncidentStatus } from '../services/auditService';

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

  return (
    <div className="flex h-screen bg-slate-950 text-slate-100 font-sans">
      {/* Sidebar */}
      <aside className="w-64 bg-slate-900/80 backdrop-blur-md border-r border-violet-500/10 shadow-xl flex flex-col relative z-20">
        {/* Logo */}
        <div className="h-16 flex items-center px-6 border-b border-violet-500/10">
          <ShieldCheck className="w-8 h-8 text-violet-400 mr-2 drop-shadow-[0_0_8px_rgba(139,92,246,0.6)]" />
          <span className="text-xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-violet-400 to-fuchsia-400">
            Argus
          </span>
          <span className="ml-2 text-[10px] uppercase font-bold tracking-wider px-2 py-0.5 rounded-full bg-violet-500/10 text-violet-300 border border-violet-500/20">
            AUDITOR
          </span>
        </div>

        {/* Nav */}
        <nav className="flex-1 py-6 px-4 space-y-1.5 overflow-y-auto">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = location.pathname.startsWith(item.path);
            const isRiskItem = item.name === 'Activity & Risk';
            const isChainItem = item.name === 'Audit Chain';

            return (
              <Link
                key={item.name}
                to={item.path}
                className={`flex items-center px-3 py-2.5 rounded-lg transition-all duration-200 group ${
                  isActive
                    ? 'bg-violet-500/15 text-violet-300 shadow-sm border border-violet-500/20 shadow-violet-500/5'
                    : 'text-slate-400 hover:bg-slate-800 hover:text-slate-200'
                }`}
              >
                <Icon
                  className={`w-5 h-5 mr-3 transition-colors ${
                    isActive ? 'text-violet-400' : 'text-slate-500 group-hover:text-slate-300'
                  }`}
                />
                <span className="font-medium text-sm">{item.name}</span>

                {isRiskItem && incident.unreviewedFlagsCount > 0 && (
                  <span className="ml-auto px-1.5 py-0.5 rounded-full text-[10px] font-bold bg-amber-500/20 text-amber-300 border border-amber-500/30">
                    {incident.unreviewedFlagsCount}
                  </span>
                )}

                {isChainItem && incident.isCompromised && (
                  <span className="ml-auto px-1.5 py-0.5 rounded-full text-[9px] font-extrabold uppercase tracking-wider bg-red-500/20 text-red-300 border border-red-500/40 animate-pulse">
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
        <div className="p-4 border-t border-violet-500/10">
          {incident.isCompromised ? (
            <Link
              to={`/auditor/chain${incident.tamperedSeqId ? `?seq=${incident.tamperedSeqId}` : ''}`}
              className="flex items-center space-x-2 px-3 py-2 rounded-lg bg-red-500/10 border border-red-500/30 hover:bg-red-500/20 transition-all cursor-pointer group"
              title="Click to inspect cryptographic breach in Chain Explorer"
            >
              <span className="w-2 h-2 rounded-full bg-red-400 animate-ping shadow-[0_0_6px_rgba(239,68,68,0.8)]" />
              <span className="text-xs font-semibold text-red-400 group-hover:text-red-300 truncate">
                ⚠ Compromise Detected
              </span>
            </Link>
          ) : incident.unreviewedFlagsCount > 0 ? (
            <Link
              to="/auditor/activity"
              className="flex items-center space-x-2 px-3 py-2 rounded-lg bg-amber-500/10 border border-amber-500/20 hover:bg-amber-500/20 transition-all cursor-pointer group"
              title="Click to review suspicious activity flags"
            >
              <span className="w-2 h-2 rounded-full bg-amber-400 animate-pulse shadow-[0_0_6px_rgba(245,158,11,0.8)]" />
              <span className="text-xs font-medium text-amber-400 group-hover:text-amber-300 truncate">
                {incident.unreviewedFlagsCount} Alert{incident.unreviewedFlagsCount > 1 ? 's' : ''} Pending
              </span>
            </Link>
          ) : (
            <div className="flex items-center space-x-2 px-3 py-2 rounded-lg bg-emerald-500/5 border border-emerald-500/10">
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse shadow-[0_0_6px_rgba(52,211,153,0.8)]" />
              <span className="text-xs font-medium text-emerald-400 truncate">System Monitoring Active</span>
            </div>
          )}
        </div>
      </aside>

      {/* Main Content */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Header */}
        <header className="h-16 bg-slate-900/60 backdrop-blur-md border-b border-violet-500/10 flex items-center justify-between px-8 shadow-sm">
          <div className="flex items-center space-x-3">
            <Activity className="w-4 h-4 text-violet-400" />
            <h1 className="text-base font-semibold text-slate-200 capitalize tracking-wide">
              {location.pathname.split('/').pop()?.replace('-', ' ') || 'Overview'}
            </h1>
            <span className="text-xs text-slate-500 font-mono bg-slate-800 px-2 py-0.5 rounded border border-slate-700">
              READ-ONLY
            </span>
          </div>
          <div className="flex items-center space-x-4">
            <div className="text-xs text-slate-500 font-mono hidden md:block">
              {new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
            </div>
            <div className="h-8 w-8 rounded-full ring-2 ring-violet-500/30 flex items-center justify-center overflow-hidden">
              <UserButton afterSignOutUrl="/" appearance={{ elements: { avatarBox: 'w-8 h-8' } }} />
            </div>
          </div>
        </header>

        {/* Persistent Incident Alert Banner */}
        {incident.isCompromised && (
          <div className="bg-gradient-to-r from-red-950/90 via-red-900/70 to-red-950/90 border-b border-red-500/40 px-8 py-3 flex items-center justify-between shadow-lg shadow-red-950/50 z-10">
            <div className="flex items-center space-x-3.5">
              <div className="w-8 h-8 rounded-lg bg-red-500/20 border border-red-500/40 flex items-center justify-center text-red-400 shrink-0">
                <ShieldAlert className="w-5 h-5 animate-pulse" />
              </div>
              <div>
                <div className="flex items-center space-x-2">
                  <span className="text-[11px] font-extrabold uppercase tracking-wider text-red-400 font-mono">
                    CRITICAL SECURITY ALERT
                  </span>
                  {incident.tamperedSeqId && (
                    <span className="text-[10px] font-mono font-semibold bg-red-500/25 text-red-200 px-2 py-0.5 rounded border border-red-500/40">
                      Tampered Block #{incident.tamperedSeqId}
                    </span>
                  )}
                  {incident.anchorMismatch && (
                    <span className="text-[10px] font-mono font-semibold bg-red-500/25 text-red-200 px-2 py-0.5 rounded border border-red-500/40">
                      External Anchor Mismatch
                    </span>
                  )}
                </div>
                <p className="text-xs text-red-200/90 mt-0.5 font-medium">
                  {incident.details || 'Cryptographic chain verification detected tampering or anchor discrepancy.'}
                </p>
              </div>
            </div>
            <Link
              to={`/auditor/chain${incident.tamperedSeqId ? `?seq=${incident.tamperedSeqId}` : ''}`}
              className="shrink-0 flex items-center space-x-1.5 px-3.5 py-1.5 rounded-lg bg-red-500/20 hover:bg-red-500/30 border border-red-500/40 text-red-100 text-xs font-semibold transition-all shadow-sm group hover:scale-[1.02]"
            >
              <span>Inspect Compromised Block {incident.tamperedSeqId ? `#${incident.tamperedSeqId}` : ''}</span>
              <ArrowRight className="w-3.5 h-3.5 transition-transform group-hover:translate-x-0.5" />
            </Link>
          </div>
        )}

        {/* Scrollable content */}
        <main className="flex-1 overflow-y-auto p-8 bg-slate-950">
          <div className="max-w-7xl mx-auto h-full">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  );
}
