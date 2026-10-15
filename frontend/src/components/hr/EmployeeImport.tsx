import { useEffect, useRef, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useAuth } from '../auth/AuthProvider';
import { fetchWithAuth } from '../../lib/api';
import { fetchRoles } from '../../services/auditService';
import { employeeCsvHeader, importBatchSize, previewEmployeeImport, type ImportRow } from '../../lib/employeeImport';
import { Button } from '../common/Button';
import { DetailSheet } from '../common/DetailSheet';

export default function EmployeeImport({ onClose }: { onClose: () => void }) {
  const { getToken } = useAuth();
  const cache = useQueryClient();
  const roles = useQuery({ queryKey: ['roles'], queryFn: () => fetchRoles(getToken) });
  const [source, setSource] = useState('');
  const [rows, setRows] = useState<ImportRow[]>([]);
  const [error, setError] = useState('');
  const [running, setRunning] = useState(false);
  const [started, setStarted] = useState(false);
  const [saved, setSaved] = useState(0);
  const alive = useRef(true);
  const submitting = useRef(false);
  useEffect(() => { alive.current = true; return () => { alive.current = false; }; }, []);
  const invalid = rows.filter((row) => row.errors.length).length;

  function preview() {
    setError(''); setRows([]);
    try { setRows(previewEmployeeImport(source, roles.data || [])); }
    catch (cause) { setError(cause instanceof Error ? cause.message : 'Could not read this CSV.'); }
  }
  async function importEmployees() {
    if (submitting.current || started || !rows.length || invalid) return;
    submitting.current = true; setRunning(true); setStarted(true); setError('');
    let completed = 0;
    try {
      for (let index = 0; index < rows.length && alive.current; index += importBatchSize) {
        const employees = rows.slice(index, index + importBatchSize).map((row) => row.employee!);
        const created: { employee_id: number }[] = await fetchWithAuth('/employees/batch', {
          method: 'POST', body: JSON.stringify({ employees }),
        }, getToken);
        if (created.length !== employees.length) throw new Error('The server returned an unexpected employee count.');
        completed += created.length;
        if (alive.current) setSaved(completed);
      }
    } catch (cause) {
      if (alive.current) setError(`${cause instanceof Error ? cause.message : 'Import failed.'} Import stopped. ${completed} employees confirmed saved. Check the directory before importing remaining rows; a connection interruption can hide a successful batch. No automatic retry was made.`);
    } finally {
      for (const key of ['employees', 'dashboardStats', 'audit-chain']) void cache.invalidateQueries({ queryKey: [key] });
      submitting.current = false;
      if (alive.current) setRunning(false);
    }
  }
  function template() {
    const url = URL.createObjectURL(new Blob([`${employeeCsvHeader}\n`], { type: 'text/csv;charset=utf-8' }));
    const link = document.createElement('a'); link.href = url; link.download = 'argus-employee-template.csv'; link.click(); URL.revokeObjectURL(url);
  }
  return <DetailSheet isOpen onClose={() => { if (!submitting.current) onClose(); }} mode="modal" portalTheme="hr" widthClass="w-full max-w-4xl"
    title="Import employees" subtitle="Review up to 100 employees before adding them to the workforce."
    footer={<div className="flex flex-wrap justify-between gap-3">
      <Button portalTheme="hr" variant="secondary" disabled={running} onClick={onClose}>{started ? 'Done' : 'Cancel'}</Button>
      {!started && <Button portalTheme="hr" disabled={!rows.length || !!invalid || roles.isError || roles.isFetching} onClick={() => void importEmployees()}>Confirm and add {rows.length} employees</Button>}
    </div>}>
    <div className="space-y-5 text-slate-800">
      <p className="text-sm">Create departments and job roles first. Use their exact names in the CSV. Salary is the annual amount in rupees; dates use YYYY-MM-DD. National IDs and contact information are encrypted when saved.</p>
      <p className="text-sm text-slate-600">Employees are saved in batches of 20. Each batch succeeds completely or rolls back. Earlier completed batches remain saved if a later batch fails. Every saved employee creates permanent audit history.</p>
      {!started && <>
        <Button portalTheme="hr" variant="secondary" onClick={template}>Download CSV template</Button>
        <label className="block text-sm font-medium" htmlFor="employee-import-csv">Paste employee CSV</label>
        <textarea id="employee-import-csv" className="w-full min-h-40 rounded-lg border border-slate-300 p-3 font-mono text-xs" value={source} maxLength={250_001}
          onChange={(event) => { setSource(event.target.value); setRows([]); setError(''); }} placeholder={employeeCsvHeader} spellCheck={false} />
        {roles.isError && <p role="alert">Job roles could not be loaded. <button className="underline" onClick={() => void roles.refetch()}>Retry roles</button></p>}
        <Button portalTheme="hr" onClick={preview} disabled={!source.trim() || roles.isFetching || roles.isError || !roles.data?.length}>Review employees</Button>
        {!roles.isFetching && !roles.data?.length && !roles.isError && <p role="status">Create at least one job role before importing employees.</p>}
      </>}
      {error && <p role="alert" className="rounded-lg bg-red-50 p-3 text-sm text-red-800">{error}</p>}
      {!!rows.length && <>
        <p role="status" aria-live="polite" className="text-sm font-medium">{started ? `${saved} of ${rows.length} employees saved${running ? ' — importing…' : saved === rows.length ? '. Import complete.' : '. Import stopped.'}` : `${rows.length} employees reviewed. ${invalid} rows need correction.`}</p>
        {running && <progress className="w-full" value={saved} max={rows.length} aria-label="Employees saved" />}
        <div className="overflow-auto max-h-80 rounded-lg border border-slate-200">
          <table className="w-full text-left text-xs"><caption className="sr-only">Employee import preview</caption>
            <thead className="sticky top-0 bg-slate-100"><tr>{['Row', 'Name & email', 'Department / job role', 'Annual salary', 'Validation'].map((heading) => <th key={heading} className="p-3">{heading}</th>)}</tr></thead>
            <tbody>{rows.map((row) => <tr key={row.line} className="border-t border-slate-200"><td className="p-3">{row.line}</td><td className="p-3 break-all">{row.fields[0]}<br />{row.fields[1]}</td><td className="p-3">{row.fields[3]}<br />{row.fields[2]}</td><td className="p-3">₹{row.fields[7]}</td><td className={`p-3 ${row.errors.length ? 'text-red-700' : 'text-emerald-700'}`}>{row.errors.join(' ') || (started && rows.indexOf(row) < saved ? 'Saved' : 'Ready')}</td></tr>)}</tbody>
          </table>
        </div>
      </>}
    </div>
  </DetailSheet>;
}
