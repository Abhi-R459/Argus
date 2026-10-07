import { useState } from 'react';
import { UserPlus } from 'lucide-react';
import EmployeeTable from '../../components/EmployeeTable';
import EmployeeForm from '../../components/forms/EmployeeForm';
import { Button } from '../../components/common/Button';
import PageHeader from '../../components/common/PageHeader';

export default function EmployeeList() {
  const [isFormOpen, setIsFormOpen] = useState(false);

  return (
    <div className="space-y-6 animate-fade-cascade">
      <PageHeader
        title="Workforce Directory"
        description="Personnel records, role assignments, and compensation history."
        portalTheme="hr"
        action={
          <Button
            variant="primary"
            size="md"
            portalTheme="hr"
            onClick={() => setIsFormOpen(true)}
            leftIcon={<UserPlus className="w-4 h-4" />}
          >
            Add Personnel
          </Button>
        }
      />

      {/* Workforce Table with Compound Primitives & Slide-Over Sheet */}
      <EmployeeTable />

      {/* Personnel Registration Modal */}
      <EmployeeForm isOpen={isFormOpen} onClose={() => setIsFormOpen(false)} />
    </div>
  );
}
