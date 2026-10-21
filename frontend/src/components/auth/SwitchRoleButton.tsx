import { useNavigate } from 'react-router-dom';
import { useAuth } from './AuthProvider';

export default function SwitchRoleButton() {
  const { selectedRole, chooseRole } = useAuth();
  const navigate = useNavigate();
  const nextRole = selectedRole === 'hr_admin' ? 'compliance_auditor' : 'hr_admin';
  return <button type="button" onClick={() => { chooseRole(nextRole); navigate('/'); }}
    className="rounded-lg border border-current px-3 py-1.5 text-xs font-semibold opacity-75 hover:opacity-100">
    Switch to {nextRole === 'hr_admin' ? 'HR' : 'Auditor'}
  </button>;
}
