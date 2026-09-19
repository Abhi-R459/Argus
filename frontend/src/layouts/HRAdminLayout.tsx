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
    <div className="portal-hr flex h-screen bg-slate-50 text-slate-900 font-sans antialiased">
      {/* Sidebar - Clean Modern Enterprise Canvas */}
      <aside className="w-64 bg-white border-r border-slate-200 flex flex-col relative z-20">
        <div className="h-16 flex items-center px-6 border-b border-slate-200 justify-between">
          <div className="flex items-center space-x-2.5">
            <div className="w-8 h-8 rounded-xl bg-slate-900 flex items-center justify-center text-white shadow-xs">
              <ShieldCheck className="w-4.5 h-4.5 text-emerald-400" />
            </div>
            <span className="text-lg font-bold text-slate-900 tracking-tight">
              Argus
            </span>
          </div>
          <span className="text-[10px] font-semibold tracking-wider px-2 py-0.5 rounded-md bg-slate-100 border border-slate-200 text-slate-600">
            HR ADMIN
          </span>
        </div>
        
        <nav className="flex-1 py-6 px-3.5 space-y-1 overflow-y-auto">
          <div className="px-3 pb-2 text-[10px] font-semibold text-slate-400 uppercase tracking-wider">
            Workforce Management
          </div>
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = location.pathname.startsWith(item.path);
            return (
              <Link
                key={item.name}
                to={item.path}
                className={`flex items-center px-3.5 py-2.5 rounded-xl text-sm transition-all duration-150 group focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-900/10 ${
                  isActive
                    ? 'bg-slate-100 text-slate-900 font-semibold border border-slate-200/80 shadow-2xs'
                    : 'text-slate-600 hover:bg-slate-50 hover:text-slate-900 font-medium border border-transparent'
                }`}
              >
                <Icon
                  className={`w-4 h-4 mr-3 transition-colors duration-150 ${
                    isActive ? 'text-slate-900' : 'text-slate-400 group-hover:text-slate-600'
                  }`}
                />
                <span>{item.name}</span>
              </Link>
            );
          })}
        </nav>

        {/* Sidebar Footer Status */}
        <div className="p-4 border-t border-slate-200 bg-white">
          <div className="flex items-center space-x-3 px-3 py-2.5 rounded-xl bg-slate-50 border border-slate-200/80">
            <div className="relative flex items-center justify-center shrink-0">
              <span className="w-2 h-2 rounded-full bg-emerald-500" />
              <span className="w-2 h-2 rounded-full bg-emerald-400/50 animate-ping absolute opacity-75" />
            </div>
            <div className="flex flex-col">
              <span className="text-xs font-semibold text-slate-800 tracking-tight">Argus Core Engine</span>
              <span className="text-[10px] text-slate-500 font-medium">Operational • Full Access</span>
            </div>
          </div>
        </div>
      </aside>

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col overflow-hidden relative z-10">
        {/* Header */}
        <header className="h-16 bg-white border-b border-slate-200 flex items-center justify-between px-8">
          <div className="flex items-center space-x-2 text-sm">
            <span className="text-slate-500 font-medium">HR Portal</span>
            <span className="text-slate-300">/</span>
            <h1 className="text-base font-semibold text-slate-900">
              {pageTitle}
            </h1>
          </div>
          <div className="flex items-center space-x-4">
            <div className="hidden md:flex items-center space-x-2 px-3 py-1 rounded-full bg-emerald-50 text-emerald-700 text-xs font-medium border border-emerald-200/60">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
              <span>Operational</span>
            </div>
            <div className="hidden md:flex items-center space-x-2 px-3 py-1 rounded-xl bg-slate-50 border border-slate-200 text-xs text-slate-600 font-mono">
              <span className="text-[10px] font-bold text-emerald-600 tracking-wider">LIVE</span>
              <span className="text-slate-300">|</span>
              <RealtimeClock showLiveDot={true} />
            </div>
            <div className="h-8 w-8 rounded-full ring-2 ring-slate-200 hover:ring-slate-300 transition-colors duration-150 flex items-center justify-center overflow-hidden">
              <UserButton afterSignOutUrl="/" appearance={{ elements: { avatarBox: "w-8 h-8" } }} />
            </div>
          </div>
        </header>

        {/* Scrollable Content */}
        <main className="flex-1 overflow-y-auto p-8 bg-slate-50">
          <div className="max-w-7xl mx-auto min-h-full">
            <ErrorBoundary portalTheme="hr" fallbackTitle="HR Portal View Error">
              <Outlet />
            </ErrorBoundary>
          </div>
        </main>
      </div>
    </div>
  );
}

