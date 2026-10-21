import { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useAuth } from '../../components/auth/AuthProvider';
import { fetchWithAuth } from '../../lib/api';

interface UndoAction {
  action_id: number;
  employee_id: number;
  action_type: string;
  created_at: string;
  undone_at: string | null;
}

const labels: Record<string, string> = {
  employee_created: 'Employee added',
  profile_updated: 'Profile changed',
  employee_deactivated: 'Employee deactivated',
};

export default function UndoHistory() {
  const { getToken } = useAuth();
  const queryClient = useQueryClient();
  const [pending, setPending] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const actions = useQuery<UndoAction[]>({
    queryKey: ['hrUndoActions'],
    queryFn: () => fetchWithAuth('/hr-undo', {}, getToken),
  });
  async function undo(action: UndoAction) {
    if (!window.confirm('Restore the employee state from before this change? A new audit event will record the restoration.')) return;
    setError(null);
    setPending(action.action_id);
    try {
      await fetchWithAuth('/hr-undo/' + action.action_id + '/undo', { method: 'POST' }, getToken);
      await queryClient.invalidateQueries();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'The change could not be restored.');
    } finally {
      setPending(null);
    }
  }
  return <main className="mx-auto max-w-5xl p-6 text-slate-900">
    <h1 className="text-2xl font-semibold">Undo HR changes</h1>
    <p className="mt-2 text-sm text-slate-600">Restore a supported recent employee change. The original audit event stays in the history, and the restoration creates another event.</p>
    <p className="mt-2 text-sm text-slate-600">Salary changes, departments, job roles, and older changes require review and a normal corrective action.</p>
    {error && <p role="alert" className="mt-4 rounded-lg bg-red-50 p-3 text-sm text-red-800">{error}</p>}
    {actions.isLoading && <p className="mt-6" role="status">Loading changes…</p>}
    {actions.isError && <p className="mt-6" role="alert">Could not load changes. Please try again.</p>}
    {actions.data && <div className="mt-6 overflow-hidden rounded-xl border border-slate-200 bg-white">
      {actions.data.length === 0 && <p className="p-5 text-sm text-slate-500">No eligible changes have been recorded yet.</p>}
      {actions.data.map(action => <div key={action.action_id} className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 p-4 last:border-b-0">
        <div>
          <p className="font-medium">{labels[action.action_type] ?? action.action_type} · Employee #{action.employee_id}</p>
          <p className="text-xs text-slate-500">{new Date(action.created_at).toLocaleString()}</p>
        </div>
        {action.undone_at
          ? <span className="text-sm text-slate-500">Undone</span>
          : <button type="button" disabled={pending !== null} onClick={() => void undo(action)}
              className="rounded-lg border border-slate-300 px-3 py-2 text-sm font-medium hover:bg-slate-50 disabled:opacity-50">
              {pending === action.action_id ? 'Restoring…' : 'Review and undo'}
            </button>}
      </div>)}
    </div>}
  </main>;
}
