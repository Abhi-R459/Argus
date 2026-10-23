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

interface UndoPreview {
  action_id: number;
  employee_id: number;
  employee_name: string;
  action_type: string;
  created_at: string;
  changes: { field: string; label: string; current: string; restored: string }[];
  can_undo: boolean;
  blocked_reason: string | null;
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
  const [selectedAction, setSelectedAction] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const actions = useQuery<UndoAction[]>({
    queryKey: ['hrUndoActions'],
    queryFn: () => fetchWithAuth('/hr-undo', {}, getToken),
  });
  const preview = useQuery<UndoPreview>({
    queryKey: ['hrUndoPreview', selectedAction],
    queryFn: () => fetchWithAuth(`/hr-undo/${selectedAction}/preview`, {}, getToken),
    enabled: selectedAction !== null,
  });
  async function undo(actionId: number) {
    setError(null);
    setPending(actionId);
    try {
      await fetchWithAuth(`/hr-undo/${actionId}/undo`, { method: 'POST' }, getToken);
      setSelectedAction(null);
      await queryClient.invalidateQueries();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'The change could not be restored.');
      await queryClient.invalidateQueries({ queryKey: ['hrUndoPreview', actionId] });
    } finally {
      setPending(null);
    }
  }
  return <main className="mx-auto max-w-5xl p-6 text-slate-900">
    <h1 className="text-2xl font-semibold">Undo HR changes</h1>
    <p className="mt-2 text-sm text-slate-600">Restore a supported recent employee change. The original audit event stays in the history, and the restoration creates another event.</p>
    <p className="mt-2 text-sm text-slate-600">Salary changes and changes without an eligible undo receipt require a normal corrective action. Review each eligible change before restoring it.</p>
    {error && <p role="alert" className="mt-4 rounded-lg bg-red-50 p-3 text-sm text-red-800">{error}</p>}
    {actions.isLoading && <p className="mt-6" role="status">Loading changes…</p>}
    {actions.isError && <p className="mt-6" role="alert">Could not load changes. Please try again.</p>}
    {actions.data && <div className="mt-6 overflow-hidden rounded-xl border border-slate-200 bg-white">
      {actions.data.length === 0 && <p className="p-5 text-sm text-slate-500">No eligible changes have been recorded yet.</p>}
      {actions.data.map(action => <div key={action.action_id} className="border-b border-slate-100 p-4 last:border-b-0">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="font-medium">{labels[action.action_type] ?? action.action_type} · Employee #{action.employee_id}</p>
            <p className="text-xs text-slate-500">{new Date(action.created_at).toLocaleString()}</p>
          </div>
          {action.undone_at
            ? <span className="text-sm text-slate-500">Undone</span>
            : <button type="button" disabled={pending !== null} onClick={() => {
                setError(null);
                setSelectedAction(selectedAction === action.action_id ? null : action.action_id);
              }}
                aria-expanded={selectedAction === action.action_id}
                className="rounded-lg border border-slate-300 px-3 py-2 text-sm font-medium hover:bg-slate-50 disabled:opacity-50">
                {selectedAction === action.action_id ? 'Close review' : 'Review change'}
              </button>}
        </div>
        {selectedAction === action.action_id && !action.undone_at && <section aria-label={`Undo review for employee ${action.employee_id}`} className="mt-4 rounded-xl border border-blue-200 bg-blue-50/50 p-4">
          {preview.isLoading && <p role="status" className="text-sm text-slate-600">Loading the proposed restoration…</p>}
          {preview.isError && <p role="alert" className="text-sm text-red-700">Could not review this change. Please close and try again.</p>}
          {preview.data && <>
            <h2 className="text-base font-semibold">Review restoration for {preview.data.employee_name} <span className="font-normal text-slate-500">(#{preview.data.employee_id})</span></h2>
            <p className="mt-1 text-sm text-slate-600">The values in “After undo” are what Argus will restore. The original audit event remains, and the restoration creates a new event.</p>
            {preview.data.changes.length > 0 ? <div className="mt-4 overflow-x-auto rounded-lg border border-slate-200 bg-white">
              <table className="w-full min-w-[520px] text-left text-sm">
                <thead className="bg-slate-50 text-xs font-semibold uppercase tracking-wide text-slate-500"><tr><th className="px-3 py-2">Field</th><th className="px-3 py-2">Current</th><th className="px-3 py-2">After undo</th></tr></thead>
                <tbody>{preview.data.changes.map(change => <tr key={change.field} className="border-t border-slate-100 align-top">
                  <th scope="row" className="px-3 py-3 font-medium text-slate-800">{change.label}</th>
                  <td className="max-w-xs break-words px-3 py-3 text-slate-700">{change.current || 'Empty'}</td>
                  <td className="max-w-xs break-words px-3 py-3 font-medium text-slate-900">{change.restored || 'Empty'}</td>
                </tr>)}</tbody>
              </table>
            </div> : <p className="mt-4 text-sm text-slate-600">No employee field values would change.</p>}
            {preview.data.blocked_reason && <p role="alert" className="mt-4 rounded-lg bg-amber-50 p-3 text-sm text-amber-900">{preview.data.blocked_reason}</p>}
            <div className="mt-4 flex flex-wrap justify-end gap-2">
              <button type="button" onClick={() => setSelectedAction(null)} className="rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-medium hover:bg-slate-50">Cancel</button>
              <button type="button" disabled={!preview.data.can_undo || preview.data.changes.length === 0 || pending !== null}
                onClick={() => void undo(action.action_id)}
                className="rounded-lg bg-blue-700 px-4 py-2 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-blue-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-600 focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:bg-slate-500 disabled:text-white disabled:opacity-100">
                {pending === action.action_id ? 'Restoring…' : 'Confirm undo'}
              </button>
            </div>
          </>}
        </section>}
      </div>)}
    </div>}
  </main>;
}
