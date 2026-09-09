import { Outlet, Link, useLocation } from 'react-router-dom';
import { UserButton } from '@clerk/clerk-react';
import { LayoutDashboard, Users, FileText, Settings, ShieldCheck } from 'lucide-react';

export default function HRAdminLayout() {
  const location = useLocation();

  const navItems = [
    { name: 'Dashboard', path: '/hr/dashboard', icon: LayoutDashboard },
    { name: 'Employees', path: '/hr/employees', icon: Users },
    { name: 'Audit Logs', path: '/hr/audits', icon: FileText },
    { name: 'Settings', path: '/hr/settings', icon: Settings },
  ];

  return (
    <div className="flex h-screen bg-slate-50 text-slate-900 font-sans">
      {/* Sidebar - Glassmorphism style */}
      <aside className="w-64 bg-white/70 backdrop-blur-md border-r border-slate-200/60 shadow-sm flex flex-col transition-all duration-300 relative z-20">
        <div className="h-16 flex items-center px-6 border-b border-slate-200/50">
          <ShieldCheck className="w-8 h-8 text-indigo-600 mr-2" />
          <span className="text-xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-indigo-600 to-violet-600">
            Argus
          </span>
          <span className="ml-2 text-[10px] uppercase font-bold tracking-wider px-2 py-0.5 rounded-full bg-slate-100 text-slate-500 border border-slate-200 shadow-sm">
            HR
          </span>
        </div>
        
        <nav className="flex-1 py-6 px-4 space-y-1.5 overflow-y-auto">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = location.pathname.startsWith(item.path);
            return (
              <Link
                key={item.name}
                to={item.path}
                className={`flex items-center px-3 py-2.5 rounded-lg transition-all duration-200 group ${
                  isActive
                    ? 'bg-indigo-50/80 text-indigo-700 shadow-sm border border-indigo-100/50'
                    : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900'
                }`}
              >
                <Icon className={`w-5 h-5 mr-3 transition-colors ${isActive ? 'text-indigo-600' : 'text-slate-400 group-hover:text-slate-600'}`} />
                <span className="font-medium text-sm">{item.name}</span>
              </Link>
            );
          })}
        </nav>
      </aside>

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col overflow-hidden relative z-10">
        {/* Header */}
        <header className="h-16 bg-white/70 backdrop-blur-md border-b border-slate-200/60 flex items-center justify-between px-8 shadow-sm">
          <div className="flex items-center">
             <h1 className="text-xl font-semibold text-slate-800 capitalize">
                {location.pathname.split('/').pop() || 'Dashboard'}
             </h1>
          </div>
          <div className="flex items-center space-x-4">
             <div className="h-8 w-8 rounded-full ring-2 ring-indigo-100 flex items-center justify-center overflow-hidden">
                <UserButton afterSignOutUrl="/" appearance={{ elements: { avatarBox: "w-8 h-8" } }} />
             </div>
          </div>
        </header>

        {/* Scrollable Content */}
        <main className="flex-1 overflow-y-auto p-8 bg-slate-50/50">
           <div className="max-w-7xl mx-auto h-full">
              <Outlet />
           </div>
        </main>
      </div>
    </div>
  );
}
