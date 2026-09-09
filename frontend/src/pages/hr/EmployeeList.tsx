import { useState } from 'react';
import EmployeeTable from '../../components/EmployeeTable';
import EmployeeForm from '../../components/forms/EmployeeForm';

export default function EmployeeList() {
  const [isFormOpen, setIsFormOpen] = useState(false);

  return (
    <div className="animate-in fade-in slide-in-from-bottom-4 duration-500 space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight">Employees</h1>
          <p className="text-slate-500 mt-1">Manage your workforce, roles, and salary history.</p>
        </div>
        <button 
          onClick={() => setIsFormOpen(true)}
          className="bg-indigo-600 hover:bg-indigo-700 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors shadow-sm ring-1 ring-indigo-600 ring-offset-2 ring-offset-slate-50 focus:outline-none focus:ring-2"
        >
          + Add Employee
        </button>
      </div>

      <EmployeeTable />

      {isFormOpen && <EmployeeForm onClose={() => setIsFormOpen(false)} />}
    </div>
  );
}
