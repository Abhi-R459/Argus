import { useState } from 'react';
import { UserPlus } from 'lucide-react';
import EmployeeTable from '../../components/EmployeeTable';
import EmployeeForm from '../../components/forms/EmployeeForm';
import { Button } from '../../components/common/Button';
import PageHeader from '../../components/common/PageHeader';
import OrganizationSetup from '../../components/hr/OrganizationSetup';
import EmployeeImport from '../../components/hr/EmployeeImport';

export default function EmployeeList() {
  const [isFormOpen, setIsFormOpen] = useState(false);
  const [isImportOpen, setIsImportOpen] = useState(false);
  const [showSetup, setShowSetup] = useState(false);

  return (
    <div className="space-y-6 animate-fade-cascade">
      <PageHeader
        title="Workforce Directory"
        description="Personnel records, role assignments, and compensation history."
        portalTheme="hr"
        action={
          <div className="flex flex-wrap gap-2">
          <Button portalTheme="hr" variant="secondary" onClick={() => setShowSetup(!showSetup)} aria-expanded={showSetup}>Departments & roles</Button>
          <Button portalTheme="hr" variant="secondary" onClick={() => setIsImportOpen(true)}>Import employees</Button>
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
        }
      />

      {showSetup && <OrganizationSetup />}
      {isImportOpen && <EmployeeImport onClose={() => setIsImportOpen(false)} />}
      <EmployeeTable />

      {/* Personnel Registration Modal */}
      <EmployeeForm isOpen={isFormOpen} onClose={() => setIsFormOpen(false)} />
    </div>
  );
}
