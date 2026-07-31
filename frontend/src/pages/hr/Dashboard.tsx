export default function Dashboard() {
  return (
    <div className="animate-in fade-in slide-in-from-bottom-4 duration-500">
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
        <div className="bg-white rounded-xl shadow-sm border border-slate-100 p-6 flex flex-col justify-between hover:shadow-md transition-shadow">
          <h3 className="text-sm font-medium text-slate-500">Total Employees</h3>
          <p className="text-3xl font-bold text-slate-800 mt-2">1,248</p>
          <div className="mt-4 flex items-center text-sm">
            <span className="text-emerald-500 font-medium flex items-center">
               <svg className="w-4 h-4 mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 10l7-7m0 0l7 7m-7-7v18" /></svg>
               12%
            </span>
            <span className="text-slate-400 ml-2">vs last month</span>
          </div>
        </div>
        
        <div className="bg-white rounded-xl shadow-sm border border-slate-100 p-6 flex flex-col justify-between hover:shadow-md transition-shadow">
          <h3 className="text-sm font-medium text-slate-500">Active Audits</h3>
          <p className="text-3xl font-bold text-slate-800 mt-2">4</p>
          <div className="mt-4 flex items-center text-sm">
            <span className="text-indigo-500 font-medium flex items-center">
               In Progress
            </span>
          </div>
        </div>

        <div className="bg-white rounded-xl shadow-sm border border-slate-100 p-6 flex flex-col justify-between hover:shadow-md transition-shadow">
          <h3 className="text-sm font-medium text-slate-500">Pending Approvals</h3>
          <p className="text-3xl font-bold text-slate-800 mt-2">12</p>
          <div className="mt-4 flex items-center text-sm">
            <span className="text-amber-500 font-medium flex items-center">
               Requires attention
            </span>
          </div>
        </div>
      </div>
      
      <div className="bg-white rounded-xl shadow-sm border border-slate-100 p-6 min-h-[400px]">
        <h3 className="text-lg font-semibold text-slate-800 mb-4">Recent Activity</h3>
        <div className="flex flex-col items-center justify-center h-[300px] text-slate-400 bg-slate-50 rounded-lg border border-dashed border-slate-200">
           <svg className="w-12 h-12 text-slate-300 mb-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} d="M13 10V3L4 14h7v7l9-11h-7z" /></svg>
           <p>Activity feed will appear here</p>
        </div>
      </div>
    </div>
  );
}
