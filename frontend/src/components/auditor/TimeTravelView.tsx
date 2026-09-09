import { useState } from 'react';
import { useAuth } from '@clerk/clerk-react';
import { useQuery } from '@tanstack/react-query';
import { History, Search, CalendarClock, User, CheckCircle2, XCircle } from 'lucide-react';
import { fetchTimeTravelState } from '../../services/auditService';

export default function TimeTravelView() {
  const { getToken } = useAuth();
  
  const [employeeIdInput, setEmployeeIdInput] = useState('');
  const [dateInput, setDateInput] = useState('');
  const [timeInput, setTimeInput] = useState('');
  
  const [queryParams, setQueryParams] = useState<{ id: number; timestamp: string } | null>(null);

  const { data: record, isLoading, isError, error } = useQuery({
    queryKey: ['timeTravel', queryParams?.id, queryParams?.timestamp],
    queryFn: async () => {
      if (!queryParams) return null;
      return fetchTimeTravelState(queryParams.id, queryParams.timestamp, getToken);
    },
    enabled: !!queryParams,
    retry: false
  });

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (!employeeIdInput || !dateInput || !timeInput) return;
    
    const timestamp = `${dateInput}T${timeInput}:00Z`; // Combine to ISO UTC
    setQueryParams({
      id: parseInt(employeeIdInput, 10),
      timestamp
    });
  };

  return (
    <div className="space-y-6">
      {/* Header & Controls */}
      <div className="bg-slate-900/50 backdrop-blur-sm border border-violet-500/10 rounded-xl p-6 shadow-xl relative overflow-hidden">
        <div className="absolute top-0 right-0 p-8 opacity-5">
          <History className="w-32 h-32" />
        </div>
        
        <h2 className="text-xl font-bold text-white mb-2 flex items-center">
          <History className="w-5 h-5 mr-2 text-violet-400" />
          Time-Travel Reconstruction
        </h2>
        <p className="text-sm text-slate-400 mb-6 max-w-2xl">
          Query the composite index to deterministically reconstruct the exact state of an employee record at any given microsecond in the past using the cryptographic audit log.
        </p>

        <form onSubmit={handleSearch} className="flex flex-col md:flex-row gap-4 max-w-4xl relative z-10">
          <div className="flex-1">
            <label className="block text-xs font-medium text-slate-400 mb-1">Employee ID</label>
            <div className="relative">
              <User className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
              <input
                type="number"
                required
                min="1"
                placeholder="e.g. 13"
                value={employeeIdInput}
                onChange={(e) => setEmployeeIdInput(e.target.value)}
                className="w-full bg-slate-950/50 border border-slate-800 rounded-lg py-2 pl-10 pr-4 text-sm text-slate-200 focus:outline-none focus:border-violet-500/50 focus:ring-1 focus:ring-violet-500/50"
              />
            </div>
          </div>
          
          <div className="flex-1">
            <label className="block text-xs font-medium text-slate-400 mb-1">Target Date (UTC)</label>
            <input
              type="date"
              required
              value={dateInput}
              onChange={(e) => setDateInput(e.target.value)}
              className="w-full bg-slate-950/50 border border-slate-800 rounded-lg py-2 px-4 text-sm text-slate-200 focus:outline-none focus:border-violet-500/50 focus:ring-1 focus:ring-violet-500/50"
            />
          </div>
          
          <div className="flex-1">
            <label className="block text-xs font-medium text-slate-400 mb-1">Target Time (UTC)</label>
            <input
              type="time"
              required
              value={timeInput}
              onChange={(e) => setTimeInput(e.target.value)}
              className="w-full bg-slate-950/50 border border-slate-800 rounded-lg py-2 px-4 text-sm text-slate-200 focus:outline-none focus:border-violet-500/50 focus:ring-1 focus:ring-violet-500/50"
            />
          </div>

          <div className="flex items-end">
            <button
              type="submit"
              disabled={isLoading}
              className="h-[38px] px-6 bg-violet-600 hover:bg-violet-500 text-white text-sm font-medium rounded-lg transition-colors flex items-center shadow-lg shadow-violet-900/20 disabled:opacity-50"
            >
              {isLoading ? (
                <div className="w-4 h-4 border-2 border-white/20 border-t-white rounded-full animate-spin mr-2" />
              ) : (
                <Search className="w-4 h-4 mr-2" />
              )}
              Reconstruct
            </button>
          </div>
        </form>
      </div>

      {/* Results Area */}
      {isError && (
        <div className="bg-red-500/10 border border-red-500/20 rounded-xl p-4 flex items-start text-red-400 animate-in fade-in">
          <XCircle className="w-5 h-5 mr-3 mt-0.5 shrink-0" />
          <div>
            <h3 className="font-medium">Reconstruction Failed</h3>
            <p className="text-sm opacity-80 mt-1">
              {error instanceof Error ? error.message : 'The requested record could not be reconstructed for the given timestamp.'}
            </p>
          </div>
        </div>
      )}

      {record && !isLoading && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 animate-in slide-in-from-bottom-4">
          
          {/* Formatted View */}
          <div className="lg:col-span-2 bg-slate-900/50 backdrop-blur-sm border border-violet-500/10 rounded-xl shadow-xl overflow-hidden">
            <div className="bg-slate-800/30 px-6 py-4 border-b border-slate-800/50 flex justify-between items-center">
              <h3 className="font-semibold text-slate-200 flex items-center">
                <CheckCircle2 className="w-4 h-4 mr-2 text-emerald-400" />
                State Reconstructed Successfully
              </h3>
              <div className="flex items-center text-xs font-mono text-violet-300 bg-violet-500/10 px-3 py-1 rounded-full border border-violet-500/20">
                <CalendarClock className="w-3 h-3 mr-2" />
                AS OF {new Date(record.as_of).toLocaleString()}
              </div>
            </div>
            
            <div className="p-6">
              <div className="grid grid-cols-2 gap-x-12 gap-y-6">
                <div>
                  <div className="text-xs font-medium text-slate-500 mb-1 uppercase tracking-wider">Employee ID</div>
                  <div className="text-lg font-mono text-slate-200">{record.employee_id}</div>
                </div>
                <div>
                  <div className="text-xs font-medium text-slate-500 mb-1 uppercase tracking-wider">Status</div>
                  <div>
                    {record.is_active ? (
                      <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                        Active
                      </span>
                    ) : (
                      <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-red-500/10 text-red-400 border border-red-500/20">
                        Inactive
                      </span>
                    )}
                  </div>
                </div>
                
                <div>
                  <div className="text-xs font-medium text-slate-500 mb-1 uppercase tracking-wider">Full Name</div>
                  <div className="text-base text-slate-200 font-medium">{record.full_name}</div>
                </div>
                <div>
                  <div className="text-xs font-medium text-slate-500 mb-1 uppercase tracking-wider">Email</div>
                  <div className="text-base text-slate-300">{record.email}</div>
                </div>

                <div>
                  <div className="text-xs font-medium text-slate-500 mb-1 uppercase tracking-wider">Role & Dept</div>
                  <div className="text-base text-slate-200">{record.role_title}</div>
                  <div className="text-sm text-slate-400">{record.department_name}</div>
                </div>
                <div>
                  <div className="text-xs font-medium text-slate-500 mb-1 uppercase tracking-wider">Compensation</div>
                  <div className="text-base font-mono text-slate-200">
                    {new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR' }).format(record.salary)}
                  </div>
                </div>

                <div className="col-span-2">
                  <div className="text-xs font-medium text-slate-500 mb-1 uppercase tracking-wider">Date Hired</div>
                  <div className="text-base text-slate-300">{new Date(record.date_hired).toLocaleDateString()}</div>
                </div>
              </div>
            </div>
          </div>

          {/* Raw JSON View */}
          <div className="bg-slate-950 border border-slate-800 rounded-xl shadow-xl overflow-hidden flex flex-col">
            <div className="bg-slate-900 px-4 py-3 border-b border-slate-800 flex items-center justify-between">
              <span className="text-xs font-mono text-slate-400">raw_state.json</span>
              <span className="text-[10px] uppercase font-bold tracking-wider px-2 py-0.5 rounded bg-violet-500/10 text-violet-400">
                O(log N) RECONSTRUCT
              </span>
            </div>
            <div className="p-4 flex-1 overflow-auto">
              <pre className="text-[11px] font-mono text-slate-300 leading-relaxed">
                {JSON.stringify(record, null, 2)}
              </pre>
            </div>
          </div>

        </div>
      )}
      
      {!record && !isLoading && !isError && (
        <div className="h-48 border-2 border-dashed border-slate-800 rounded-xl flex items-center justify-center text-slate-500">
          Enter an Employee ID and target time to view their historical state.
        </div>
      )}
    </div>
  );
}
