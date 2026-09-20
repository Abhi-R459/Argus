import { useState, useEffect } from 'react';
import { Outlet, Link, useLocation } from 'react-router-dom';
import { UserButton } from '@clerk/clerk-react';
import { LayoutDashboard, Users, Settings, ShieldCheck, Menu, X } from 'lucide-react';
import RealtimeClock from '../components/common/RealtimeClock';
import { ErrorBoundary } from '../components/common/ErrorBoundary';

export default function HRAdminLayout() {
  const location = useLocation();
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);

  const navItems = [
    { name: 'Dashboard', path: '/hr/dashboard', icon: LayoutDashboard },
    { name: 'Employees', path: '/hr/employees', icon: Users },
    { name: 'Settings', path: '/hr/settings', icon: Settings },
  ];

  const currentPath = location.pathname.split('/').pop() || 'Dashboard';
  const pageTitle = currentPath.charAt(0).toUpperCase() + currentPath.slice(1);

  // Close mobile drawer upon navigation
  useEffect(() => {
    setIsMobileMenuOpen(false);
  }, [location.pathname]);

  return (
    <div className="portal-hr flex h-dvh bg-slate-50 text-slate-900 font-sans antialiased overflow-hidden">
      {/* Mobile Drawer Backdrop */}
      {isMobileMenuOpen && (
        <div
          className="fixed inset-0 bg-slate-900/30 backdrop-blur-xs z-40 lg:hidden transition-opacity"
          onClick={() => setIsMobileMenuOpen(false)}
          aria-hidden="true"
        />
      )}

      {/* Sidebar - Clean Modern Enterprise Canvas (Responsive Off-Canvas on <lg) */}
      <aside
        className={`fixed inset-y-0 left-0 z-50 w-64 bg-white border-r border-slate-200 flex flex-col transform transition-transform duration-200 ease-in-out lg:translate-x-0 lg:static lg:z-20 shrink-0 ${
          isMobileMenuOpen ? 'translate-x-0 shadow-xl' : '-translate-x-full'
        }`}
      >
        <div className="h-16 flex items-center px-6 border-b border-slate-200 justify-between shrink-0">
          <div className="flex items-center space-x-2.5">
            <div className="w-8 h-8 rounded-xl bg-slate-900 flex items-center justify-center text-white shadow-xs">
              <ShieldCheck className="w-5 h-5 text-emerald-400" />
            </div>
            <span className="text-lg font-bold text-slate-900 tracking-tight">
              Argus
            </span>
          </div>
          <div className="flex items-center space-x-2">
            <span className="text-[10px] font-semibold tracking-wider px-2 py-0.5 rounded-md bg-slate-100 border border-slate-200 text-slate-600">
              HR ADMIN
            </span>
            <button
              type="button"
              onClick={() => setIsMobileMenuOpen(false)}
              className="lg:hidden p-1 rounded-md text-slate-400 hover:text-slate-700 hover:bg-slate-100"
              aria-label="Close menu"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
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
        <div className="p-4 border-t border-slate-200 bg-white shrink-0">
          <div className="flex items-center space-x-3 px-3 py-2.5 rounded-xl bg-slate-50 border border-slate-200/80">
            <div className="flex items-center justify-center shrink-0">
              <span className="w-2 h-2 rounded-full bg-emerald-500" />
            </div>
            <div className="flex flex-col">
              <span className="text-xs font-semibold text-slate-800 tracking-tight">Argus Core Engine</span>
              <span className="text-[10px] text-slate-500 font-medium">Operational • Full Access</span>
            </div>
          </div>
        </div>
      </aside>

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col overflow-hidden relative z-10 min-w-0">
        {/* Header - Aligned to max-w-7xl content container */}
        <header className="h-16 bg-white border-b border-slate-200 flex items-center px-4 sm:px-6 lg:px-8 shrink-0">
          <div className="max-w-7xl mx-auto w-full flex items-center justify-between">
            <div className="flex items-center space-x-2 text-sm">
              <button
                type="button"
                onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)}
                className="lg:hidden p-1.5 -ml-1 mr-1.5 rounded-lg text-slate-600 hover:text-slate-900 hover:bg-slate-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-900/10"
                aria-label="Toggle navigation menu"
              >
                <Menu className="w-5 h-5" />
              </button>
              <span className="text-slate-500 font-medium hidden sm:inline">HR Portal</span>
              <span className="text-slate-300 hidden sm:inline">/</span>
              <h1 className="text-base font-semibold text-slate-900">
                {pageTitle}
              </h1>
            </div>
            <div className="flex items-center space-x-3 sm:space-x-4">
              <div className="hidden sm:flex items-center space-x-2 px-3 py-1 rounded-full bg-emerald-50 text-emerald-700 text-xs font-medium border border-emerald-200/60">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-600" />
                <span>Operational</span>
              </div>
              <div className="hidden md:flex items-center space-x-2 px-3 py-1 rounded-xl bg-slate-50 border border-slate-200 text-xs text-slate-600 font-mono">
                <span className="text-[10px] font-bold text-emerald-600 tracking-wider">LIVE</span>
                <span className="text-slate-300">|</span>
                <RealtimeClock showLiveDot={false} />
              </div>
              <div className="h-8 w-8 rounded-full ring-2 ring-slate-200 hover:ring-slate-300 transition-colors duration-150 flex items-center justify-center overflow-hidden">
                <UserButton afterSignOutUrl="/" appearance={{ elements: { avatarBox: "w-8 h-8" } }} />
              </div>
            </div>
          </div>
        </header>

        {/* Scrollable Content */}
        <main className="flex-1 overflow-y-auto p-4 sm:p-6 lg:p-8 bg-slate-50">
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

