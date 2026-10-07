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

  const pageTitleByPath: Record<string, string> = {
    '/hr/dashboard': 'Dashboard',
    '/hr/employees': 'Employees',
    '/hr/settings': 'Settings',
  };
  const pageTitle = pageTitleByPath[location.pathname] ?? 'HR Portal';

  // Close mobile drawer upon navigation
  useEffect(() => {
    setIsMobileMenuOpen(false);
  }, [location.pathname]);

  return (
    <div className="argus-app-shell portal-hr flex h-dvh bg-slate-50 text-slate-900 font-sans antialiased overflow-hidden">
      {/* Mobile Drawer Backdrop */}
      {isMobileMenuOpen && (
        <div
          className="fixed inset-0 bg-slate-900/30 backdrop-blur-xs z-40 lg:hidden transition-opacity duration-200 ease-out"
          onClick={() => setIsMobileMenuOpen(false)}
          aria-hidden="true"
        />
      )}

      {/* Sidebar - Clean Modern Enterprise Canvas (Responsive Off-Canvas on <lg) */}
      <aside
        id="hr-primary-navigation"
        className={`argus-sidebar fixed inset-y-0 left-0 z-50 w-64 bg-white border-r border-slate-200 flex flex-col transform transition-transform duration-240 ease-emil-drawer lg:translate-x-0 lg:static lg:z-20 shrink-0 ${
          isMobileMenuOpen ? 'translate-x-0 shadow-xl' : '-translate-x-full'
        }`}
      >
        <div className="h-[58px] flex items-center px-5 border-b border-slate-200 justify-between shrink-0">
          <div className="flex items-center space-x-2.5">
            <div className="w-8 h-8 rounded-xl bg-slate-900 flex items-center justify-center text-white shadow-xs">
              <ShieldCheck className="w-[17px] h-[17px] text-indigo-200" />
            </div>
            <span className="text-[15px] font-semibold text-slate-900 tracking-tight">
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
              className="lg:hidden p-2 -mr-2 rounded-lg text-slate-500 hover:text-slate-900 hover:bg-slate-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-portal-primary/30"
              aria-label="Close menu"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>
        
        <nav className="flex-1 py-2 px-3 overflow-y-auto">
          <h2 className="argus-nav-group-label">Workforce</h2>
          <div className="space-y-0.5">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = location.pathname === item.path;
            return (
              <Link
                key={item.name}
                to={item.path}
                aria-current={isActive ? 'page' : undefined}
                className={`flex items-center px-3.5 py-2 rounded-lg text-sm transition-colors duration-150 ease-out group focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-portal-primary/30 ${
                  isActive
                    ? 'bg-slate-100 text-slate-900 font-semibold border border-transparent border-l-2 border-l-portal-primary'
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
          </div>
        </nav>

        {/* Sidebar Footer Status */}
        <div className="p-4 border-t border-slate-200 bg-white shrink-0">
          <div className="flex items-center gap-3 px-3 py-2.5 rounded-xl bg-portal-surface-2 border border-portal-hairline">
            <div className="flex items-center justify-center w-8 h-8 rounded-lg bg-white border border-portal-hairline text-portal-ink-muted shrink-0">
              <Users className="w-4 h-4" aria-hidden="true" />
            </div>
            <div className="flex flex-col min-w-0">
              <span className="text-xs font-semibold text-portal-ink tracking-tight">HR workspace</span>
              <span className="text-[11px] text-portal-ink-muted font-medium">People & access</span>
            </div>
          </div>
        </div>
      </aside>

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col overflow-hidden relative z-10 min-w-0">
        {/* Header - Aligned to max-w-7xl content container */}
        <header className="argus-topbar bg-white border-b border-slate-200 flex items-center px-4 sm:px-6 lg:px-7 shrink-0">
          <div className="argus-content-frame mx-auto flex items-center justify-between gap-3">
            <div className="flex items-center space-x-2 text-sm">
              <button
                type="button"
                onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)}
                aria-controls="hr-primary-navigation"
                aria-expanded={isMobileMenuOpen}
                className="lg:hidden p-1.5 -ml-1 mr-1.5 rounded-lg text-slate-600 hover:text-slate-900 hover:bg-slate-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-portal-primary/30"
                aria-label="Toggle navigation menu"
              >
                <Menu className="w-5 h-5" />
              </button>
              <span className="text-slate-500 font-medium hidden sm:inline">Workspace</span>
              <span className="text-slate-300 hidden sm:inline">/</span>
              <span aria-hidden="true" className="text-sm font-semibold text-slate-700">
                {pageTitle}
              </span>
            </div>
            <div className="flex items-center space-x-3 sm:space-x-4">
              <div className="hidden md:flex items-center space-x-2 px-3 py-1 rounded-xl bg-slate-50 border border-slate-200 text-xs text-slate-600 font-mono">
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
          <div className="argus-content-frame mx-auto min-h-full">
            <ErrorBoundary portalTheme="hr" fallbackTitle="HR Portal View Error">
              <Outlet />
            </ErrorBoundary>
          </div>
        </main>
      </div>
    </div>
  );
}

