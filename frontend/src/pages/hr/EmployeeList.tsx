import { useState } from 'react';
import { UserPlus } from 'lucide-react';
import EmployeeTable from '../../components/EmployeeTable';
import EmployeeForm from '../../components/forms/EmployeeForm';

export default function EmployeeList() {
  const [isFormOpen, setIsFormOpen] = useState(false);

  return (
    <div className="space-y-6 animate-fade-cascade">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight">Workforce Directory</h1>
          <p className="text-slate-500 text-sm mt-1">Manage verified employees, role assignments, and salary history.</p>
        </div>
        <button 
          onClick={() => setIsFormOpen(true)}
          className="btn-press inline-flex items-center space-x-2 bg-slate-900 hover:bg-slate-800 text-white px-4 py-2.5 rounded-xl text-sm font-semibold shadow-xs transition-colors duration-150 cursor-pointer"
        >
          <UserPlus className="w-4 h-4" />
          <span>Add Employee</span>
        </button>
      </div>

      <EmployeeTable />

      {isFormOpen && <EmployeeForm onClose={() => setIsFormOpen(false)} />}
    </div>
  );
}

