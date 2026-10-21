export type WorkspaceRole = 'hr_admin' | 'compliance_auditor';

const key = 'argus:workspace-role';

export function readWorkspaceRole(): WorkspaceRole | null {
  const value = sessionStorage.getItem(key);
  return value === 'hr_admin' || value === 'compliance_auditor' ? value : null;
}

export function writeWorkspaceRole(role: WorkspaceRole | null): void {
  if (role) sessionStorage.setItem(key, role);
  else sessionStorage.removeItem(key);
}
