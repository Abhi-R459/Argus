import { Outlet, Link, useLocation } from 'react-router-dom';
import { UserButton } from '@clerk/clerk-react';
import { LayoutDashboard, Users, Settings, ShieldCheck } from 'lucide-react';
import RealtimeClock from '../components/common/RealtimeClock';

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
    <div className="flex h-screen bg-[#F8FAFC] text-slate-900 font-sans antialiased">
      {/* Sidebar - Stripe/Linear Style High-Clarity Canvas */}
      <aside className="w-64 bg-white border-r border-slate-200/90 shadow-[1px_0_4px_rgba(0,0,0,0.02)] flex flex-col relative z-20">
        <div className="h-16 flex items-center px-6 border-b border-slate-200/80 justify-between">
          <div className="flex items-center space-x-2.5">
            <div className="w-8 h-8 rounded-xl bg-gradient-to-tr from-indigo-600 to-indigo-500 flex items-center justify-center text-white shadow-[0_2px_8px_rgba(79,70,229,0.35)]">
              <ShieldCheck className="w-5 h-5" />
            </div>
            <span className="text-lg font-extrabold text-slate-900 tracking-tight">
              Argus
            </span>
          </div>
          <span className="text-[10px] font-mono font-bold tracking-wider px-2 py-0.5 rounded-md bg-slate-900 text-white shadow-2xs">
            HR ADMIN
          </span>
        </div>
        
        <nav className="flex-1 py-6 px-3.5 space-y-1.5 overflow-y-auto">
          <div className="px-3 pb-2 text-[10px] font-bold text-slate-400 uppercase tracking-widest font-mono">
            Workforce Management
          </div>
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = location.pathname.startsWith(item.path);
            return (
              <Link
                key={item.name}
                to={item.path}
                className={`btn-press-sm flex items-center px-3 py-2.5 rounded-xl text-sm font-medium transition-colors duration-150 group ${
                  isActive
                    ? 'bg-slate-900 text-white shadow-xs font-semibold'
                    : 'text-slate-600 hover:bg-slate-100/80 hover:text-slate-900 border border-transparent'
                }`}
              >
                <Icon
                  className={`w-4.5 h-4.5 mr-3 transition-colors duration-150 ${
                    isActive ? 'text-indigo-400' : 'text-slate-400 group-hover:text-slate-700'
                  }`}
                />
                <span>{item.name}</span>
              </Link>
            );
          })}
        </nav>

        {/* Sidebar Footer Status */}
        <div className="p-4 border-t border-slate-200/80 bg-slate-50/60">
          <div className="flex items-center space-x-3 px-3 py-2.5 rounded-xl bg-white border border-slate-200/90 shadow-2xs">
            <div className="relative flex items-center justify-center shrink-0">
              <span className="w-2.5 h-2.5 rounded-full bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.6)]" />
              <span className="w-2.5 h-2.5 rounded-full bg-emerald-400 animate-ping absolute opacity-75" />
            </div>
            <div className="flex flex-col">
              <span className="text-xs font-bold text-slate-900 tracking-tight">PostgreSQL Live Pool</span>
              <span className="text-[10px] text-slate-500 font-mono">role: hr_admin (R/W)</span>
            </div>
          </div>
        </div>
      </aside>

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col overflow-hidden relative z-10">
        {/* Header */}
        <header className="h-16 bg-white/80 backdrop-blur-md border-b border-slate-200/80 flex items-center justify-between px-8 shadow-xs">
          <div className="flex items-center space-x-2 text-sm">
            <span className="text-slate-400 font-medium">HR Portal</span>
            <span className="text-slate-300">/</span>
            <h1 className="text-base font-semibold text-slate-900">
              {pageTitle}
            </h1>
          </div>
          <div className="flex items-center space-x-4">
            <div className="hidden md:flex items-center space-x-2 px-3 py-1 rounded-full bg-emerald-50 text-emerald-700 text-xs font-semibold border border-emerald-200/80 shadow-2xs">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
              <span>Dual-Layer RBAC Active</span>
            </div>
            <div className="hidden md:flex items-center space-x-2 px-3 py-1 rounded-lg bg-slate-100 border border-slate-200 text-xs text-slate-600 font-mono shadow-2xs">
              <span className="text-[10px] font-bold text-emerald-600 tracking-wider">LIVE</span>
              <span className="text-slate-300">|</span>
              <RealtimeClock showLiveDot={true} />
            </div>
            <div className="h-8 w-8 rounded-full ring-2 ring-slate-200 hover:ring-indigo-500 transition-colors duration-150 flex items-center justify-center overflow-hidden">
              <UserButton afterSignOutUrl="/" appearance={{ elements: { avatarBox: "w-8 h-8" } }} />
            </div>
          </div>
        </header>

        {/* Scrollable Content */}
        <main className="flex-1 overflow-y-auto p-8 bg-[#F8FAFC]">
          <div className="max-w-7xl mx-auto h-full">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  );
}

