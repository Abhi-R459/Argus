import { useState, useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useAuth } from '@clerk/clerk-react';
import { Search, ChevronLeft, ChevronRight, Edit2, Trash2, DollarSign } from 'lucide-react';
import { fetchWithAuth } from '../lib/api';
import EmployeeEditForm from './forms/EmployeeEditForm';
import SalaryForm from './forms/SalaryForm';

interface Employee {
  employee_id: number;
  full_name: string;
  email: string;
  role_title: string;
  department_name: string;
  salary: number | null;
  date_hired: string;
  is_active: boolean;
}

interface PaginatedResponse {
  items: Employee[];
  total: number;
  page: number;
  pages: number;
}

export default function EmployeeTable() {
  const { getToken } = useAuth();
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');
  const [editingEmployee, setEditingEmployee] = useState<Employee | null>(null);
  const [salaryEmployee, setSalaryEmployee] = useState<Employee | null>(null);

  // Simple debounce
  useEffect(() => {
    const handler = setTimeout(() => {
      setDebouncedSearch(search);
      setPage(1); // Reset page on new search
    }, 400);
    return () => clearTimeout(handler);
  }, [search]);

  const limit = 10;

  const { data, isLoading, isError } = useQuery<PaginatedResponse>({
    queryKey: ['employees', page, debouncedSearch],
    queryFn: () => fetchWithAuth(`/employees?page=${page}&limit=${limit}${debouncedSearch ? `&search=${encodeURIComponent(debouncedSearch)}` : ''}`, {}, getToken),
    refetchInterval: 3000,
  });

  return (
    <div className="bg-white rounded-2xl shadow-[0_1px_3px_rgba(0,0,0,0.04),0_1px_2px_rgba(0,0,0,0.02)] border border-slate-200/90 overflow-hidden relative">
      {editingEmployee && (
        <EmployeeEditForm employee={editingEmployee} onClose={() => setEditingEmployee(null)} />
      )}
      
      {salaryEmployee && (
        <SalaryForm employee={salaryEmployee} onClose={() => setSalaryEmployee(null)} />
      )}
      
      {/* Table Header & Search */}
      <div className="p-5 border-b border-slate-200/80 flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-slate-50/60">
        <div>
          <h2 className="text-base font-bold text-slate-900 tracking-tight">Registered Personnel</h2>
          <p className="text-xs text-slate-500 mt-0.5">Encrypted PII columns masked via PostgreSQL pgcrypto</p>
        </div>
        <div className="relative w-full sm:w-80">
          <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none">
            <Search className="h-4 w-4 text-slate-400" />
          </div>
          <input
            type="text"
            className="block w-full pl-10 pr-12 py-2 border border-slate-200 rounded-xl text-sm bg-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-slate-900/10 focus:border-slate-900 transition-colors shadow-2xs"
            placeholder="Search by name or email..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
          <div className="absolute inset-y-0 right-0 pr-3 flex items-center pointer-events-none">
            {search ? (
              <button
                type="button"
                onClick={() => setSearch('')}
                className="pointer-events-auto text-xs text-slate-400 hover:text-slate-600 font-bold"
              >
                ×
              </button>
            ) : (
              <kbd className="text-[10px] font-mono text-slate-400 bg-slate-100 border border-slate-200/80 px-1.5 py-0.5 rounded shadow-2xs">
                /
              </kbd>
            )}
          </div>
        </div>
      </div>

      {/* Table Content */}
      <div className="overflow-x-auto">
        <table className="min-w-full divide-y divide-slate-200/80">
          <thead className="bg-slate-50/80">
            <tr>
              <th scope="col" className="px-6 py-3.5 text-left text-[11px] font-bold text-slate-500 uppercase tracking-wider font-mono">Employee</th>
              <th scope="col" className="px-6 py-3.5 text-left text-[11px] font-bold text-slate-500 uppercase tracking-wider font-mono">Role & Dept</th>
              <th scope="col" className="px-6 py-3.5 text-left text-[11px] font-bold text-slate-500 uppercase tracking-wider font-mono">Status</th>
              <th scope="col" className="px-6 py-3.5 text-left text-[11px] font-bold text-slate-500 uppercase tracking-wider font-mono">Hired</th>
              <th scope="col" className="relative px-6 py-3.5 text-right text-[11px] font-bold text-slate-500 uppercase tracking-wider font-mono">Actions</th>
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-slate-100">
            {isLoading ? (
              <tr><td colSpan={5} className="px-6 py-12 text-center text-slate-400 text-sm font-medium">Loading directory from PostgreSQL…</td></tr>
            ) : isError ? (
              <tr><td colSpan={5} className="px-6 py-12 text-center text-rose-500 text-sm font-medium">Failed to load employees. Check network tab.</td></tr>
            ) : data?.items.length === 0 ? (
              <tr><td colSpan={5} className="px-6 py-12 text-center text-slate-400 text-sm font-medium">No employees found matching your criteria.</td></tr>
            ) : (
              data?.items.map((emp, idx) => (
                <tr
                  key={emp.employee_id}
                  style={{ animationDelay: `${idx * 25}ms` }}
                  className="animate-fade-cascade hover:bg-slate-50/80 transition-colors duration-150 group"
                >
                  <td className="px-6 py-4 whitespace-nowrap">
                    <div className="flex items-center">
                      <div className="flex-shrink-0 h-9 w-9 rounded-xl bg-gradient-to-tr from-indigo-50 to-indigo-100/80 border border-indigo-200/80 flex items-center justify-center text-indigo-700 font-bold text-xs shadow-2xs font-mono">
                        {emp.full_name.charAt(0)}
                      </div>
                      <div className="ml-3.5">
                        <div className="text-sm font-bold text-slate-900 tracking-tight">{emp.full_name}</div>
                        <div className="text-xs text-slate-500 font-mono">{emp.email}</div>
                      </div>
                    </div>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <div className="text-sm font-semibold text-slate-800">{emp.role_title}</div>
                    <div className="text-xs text-slate-500">{emp.department_name}</div>
                  </td>
                  <td className="px-6 py-3.5 whitespace-nowrap">
                    <span className={`px-2.5 py-0.5 inline-flex items-center space-x-1.5 text-xs font-semibold rounded-full border ${
                      emp.is_active
                        ? 'bg-emerald-50 text-emerald-700 border-emerald-200/80'
                        : 'bg-slate-100 text-slate-700 border-slate-200'
                    }`}>
                      <span className={`w-1.5 h-1.5 rounded-full ${emp.is_active ? 'bg-emerald-500' : 'bg-slate-400'}`} />
                      <span>{emp.is_active ? 'Active' : 'Inactive'}</span>
                    </span>
                  </td>
                  <td className="px-6 py-3.5 whitespace-nowrap text-xs text-slate-500">
                    {new Date(emp.date_hired).toLocaleDateString()}
                  </td>
                  <td className="px-6 py-3.5 whitespace-nowrap text-right text-sm font-medium">
                    <div className="flex justify-end space-x-1.5">
                       <button
                         onClick={() => setSalaryEmployee(emp)}
                         title="Adjust Salary"
                         className="btn-press-sm text-emerald-600 hover:text-emerald-700 p-1.5 rounded-md hover:bg-emerald-50 border border-transparent hover:border-emerald-200/60"
                       >
                         <DollarSign className="w-4 h-4" />
                       </button>
                       <button
                         onClick={() => setEditingEmployee(emp)}
                         title="Edit Details"
                         className="btn-press-sm text-slate-500 hover:text-indigo-600 p-1.5 rounded-md hover:bg-indigo-50 border border-transparent hover:border-indigo-200/60"
                       >
                         <Edit2 className="w-4 h-4" />
                       </button>
                       <button
                         title="Deactivate / Manage"
                         className="btn-press-sm text-slate-400 hover:text-rose-600 p-1.5 rounded-md hover:bg-rose-50 border border-transparent hover:border-rose-200/60"
                       >
                         <Trash2 className="w-4 h-4" />
                       </button>
                    </div>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {data && data.pages > 1 && (
        <div className="bg-white px-6 py-3.5 border-t border-slate-200/80 flex items-center justify-between sm:px-6">
          <div className="hidden sm:flex-1 sm:flex sm:items-center sm:justify-between">
            <div>
              <p className="text-xs text-slate-500">
                Showing <span className="font-semibold text-slate-700">{((page - 1) * limit) + 1}</span> to <span className="font-semibold text-slate-700">{Math.min(page * limit, data.total)}</span> of <span className="font-semibold text-slate-700">{data.total}</span> records
              </p>
            </div>
            <div>
              <nav className="inline-flex rounded-lg shadow-2xs space-x-1" aria-label="Pagination">
                <button
                  onClick={() => setPage(p => Math.max(1, p - 1))}
                  disabled={page === 1}
                  className="btn-press-sm inline-flex items-center px-2.5 py-1.5 rounded-md border border-slate-200 bg-white text-xs font-semibold text-slate-600 hover:bg-slate-50 disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer"
                >
                  <ChevronLeft className="h-4 w-4 mr-1" aria-hidden="true" />
                  <span>Previous</span>
                </button>
                <button
                  onClick={() => setPage(p => Math.min(data.pages, p + 1))}
                  disabled={page === data.pages}
                  className="btn-press-sm inline-flex items-center px-2.5 py-1.5 rounded-md border border-slate-200 bg-white text-xs font-semibold text-slate-600 hover:bg-slate-50 disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer"
                >
                  <span>Next</span>
                  <ChevronRight className="h-4 w-4 ml-1" aria-hidden="true" />
                </button>
              </nav>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

