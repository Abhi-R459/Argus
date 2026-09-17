import { useState } from 'react';
import { UserPlus, Database } from 'lucide-react';
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
          <div className="flex items-center gap-2.5">
            <h1 className="text-xl font-bold text-grafana-ink tracking-tight">
              Workforce Directory
            </h1>
            <span className="hidden sm:inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-mono font-semibold bg-grafana-surface border border-grafana-border text-grafana-neutral">
              <Database className="w-3 h-3 text-grafana-neutral" />
              PostgreSQL pgcrypto
            </span>
          </div>
          <p className="text-grafana-neutral text-xs mt-1">
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

      {/* Slide-over Registration Drawer */}
      {isFormOpen && <EmployeeForm onClose={() => setIsFormOpen(false)} />}
    </div>
  );
}
