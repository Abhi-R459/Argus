import { Outlet, Link, useLocation } from 'react-router-dom';
import { UserButton } from '@clerk/clerk-react';
import { LayoutDashboard, Users, Settings, ShieldCheck } from 'lucide-react';
import RealtimeClock from '../components/common/RealtimeClock';
import { ErrorBoundary } from '../components/common/ErrorBoundary';

export default function HRAdminLayout() {
  const location = useLocation();

  const navItems = [
    { name: 'Dashboard', path: '/hr/dashboard', icon: LayoutDashboard },
    { name: 'Employees', path: '/hr/employees', icon: Users },
    { name: 'Settings', path: '/hr/settings', icon: Settings },
  ];

  const currentPath = location.pathname.split('/').pop() || 'Dashboard';
  const pageTitle = currentPath.charAt(0).toUpperCase() + currentPath.slice(1);

  return (
    <div className="portal-hr flex h-screen bg-grafana-surface text-black font-sans antialiased">
      {/* Sidebar - Grafana High-Clarity Enterprise Canvas */}
      <aside className="w-64 bg-white border-r border-grafana-border shadow-xs flex flex-col relative z-20">
        <div className="h-16 flex items-center px-6 border-b border-grafana-border justify-between">
          <div className="flex items-center space-x-2.5">
            <div className="w-8 h-8 rounded-xl bg-grafana-orange flex items-center justify-center text-white shadow-2xs">
              <ShieldCheck className="w-5 h-5" />
            </div>
            <span className="text-lg font-bold text-black tracking-tight">
              Argus
            </span>
          </div>
          <span className="text-[10px] font-mono font-bold tracking-wider px-2 py-0.5 rounded-md bg-grafana-surface border border-grafana-border text-grafana-neutral shadow-2xs">
            HR ADMIN
          </span>
        </div>
        
        <nav className="flex-1 py-6 px-3.5 space-y-1.5 overflow-y-auto">
          <div className="px-3 pb-2 text-[10px] font-bold text-grafana-neutral uppercase tracking-widest font-mono">
            Workforce Management
          </div>
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = location.pathname.startsWith(item.path);
            return (
              <Link
                key={item.name}
                to={item.path}
                className={`flex items-center px-3 py-2.5 rounded-xl text-sm font-medium transition-colors duration-150 group focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-grafana-orange ${
                  isActive
                    ? 'bg-black text-white shadow-xs font-semibold'
                    : 'text-grafana-neutral hover:bg-grafana-surface hover:text-black border border-transparent'
                }`}
              >
                <Icon
                  className={`w-4.5 h-4.5 mr-3 transition-colors duration-150 ${
                    isActive ? 'text-grafana-orange' : 'text-grafana-neutral group-hover:text-black'
                  }`}
                />
                <span>{item.name}</span>
              </Link>
            );
          })}
        </nav>

        {/* Sidebar Footer Status */}
        <div className="p-4 border-t border-grafana-border bg-grafana-surface/60">
          <div className="flex items-center space-x-3 px-3 py-2.5 rounded-xl bg-white border border-grafana-border shadow-2xs">
            <div className="relative flex items-center justify-center shrink-0">
              <span className="w-2.5 h-2.5 rounded-full bg-linear-success" />
              <span className="w-2.5 h-2.5 rounded-full bg-linear-success/50 animate-ping absolute opacity-75" />
            </div>
            <div className="flex flex-col">
              <span className="text-xs font-bold text-black tracking-tight">PostgreSQL Live Pool</span>
              <span className="text-[10px] text-grafana-neutral font-mono">role: hr_admin (R/W)</span>
            </div>
          </div>
        </div>
      </aside>

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col overflow-hidden relative z-10">
        {/* Header */}
        <header className="h-16 bg-white/90 backdrop-blur-md border-b border-grafana-border flex items-center justify-between px-8 shadow-xs">
          <div className="flex items-center space-x-2 text-sm">
            <span className="text-grafana-neutral font-medium">HR Portal</span>
            <span className="text-grafana-neutral/50">/</span>
            <h1 className="text-base font-semibold text-black">
              {pageTitle}
            </h1>
          </div>
          <div className="flex items-center space-x-4">
            <div className="hidden md:flex items-center space-x-2 px-3 py-1 rounded-full bg-emerald-50 text-emerald-800 text-xs font-semibold border border-emerald-200/80 shadow-2xs">
              <span className="w-1.5 h-1.5 rounded-full bg-linear-success animate-pulse" />
              <span>Dual-Layer RBAC Active</span>
            </div>
            <div className="hidden md:flex items-center space-x-2 px-3 py-1 rounded-lg bg-grafana-surface border border-grafana-border text-xs text-grafana-neutral font-mono shadow-2xs">
              <span className="text-[10px] font-bold text-linear-success tracking-wider">LIVE</span>
              <span className="text-grafana-border">|</span>
              <RealtimeClock showLiveDot={true} />
            </div>
            <div className="h-8 w-8 rounded-full ring-2 ring-grafana-border hover:ring-grafana-orange transition-colors duration-150 flex items-center justify-center overflow-hidden">
              <UserButton afterSignOutUrl="/" appearance={{ elements: { avatarBox: "w-8 h-8" } }} />
            </div>
          </div>
        </header>

        {/* Scrollable Content */}
        <main className="flex-1 overflow-y-auto p-8 bg-grafana-surface">
          <div className="max-w-7xl mx-auto h-full">
            <ErrorBoundary portalTheme="hr" fallbackTitle="HR Portal View Error">
              <Outlet />
            </ErrorBoundary>
          </div>
        </main>
      </div>
    </div>
  );
}

