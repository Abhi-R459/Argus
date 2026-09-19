import { useState } from 'react';
import { UserPlus } from 'lucide-react';
import EmployeeTable from '../../components/EmployeeTable';
import EmployeeForm from '../../components/forms/EmployeeForm';
import { Button } from '../../components/common/Button';

export default function EmployeeList() {
  const [isFormOpen, setIsFormOpen] = useState(false);

  return (
    <div className="space-y-6 animate-fade-cascade">
      {/* Header Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 pb-1">
        <div>
          <h1 className="text-xl font-bold text-slate-900 tracking-tight">
            Workforce Directory
          </h1>
          <p className="text-slate-500 text-xs mt-1">
            Institutional personnel records, role assignments, encrypted credentials, and compensation history.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <Button
            variant="primary"
            size="md"
            portalTheme="hr"
            onClick={() => setIsFormOpen(true)}
            leftIcon={<UserPlus className="w-4 h-4" />}
          >
            Add Personnel
          </Button>
        </div>
      </div>

      {/* Workforce Table with Compound Primitives & Slide-Over Sheet */}
      <EmployeeTable />

      {/* Personnel Registration Modal */}
      <EmployeeForm isOpen={isFormOpen} onClose={() => setIsFormOpen(false)} />
    </div>
  );
}
