import { useState, type FormEvent } from 'react';
import { useAuth } from '../auth/AuthProvider';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { fetchWithAuth } from '../../lib/api';
import { Button } from '../common/Button';

type Department = { department_id: number; name: string };

export default function OrganizationSetup() {
  const { getToken } = useAuth();
  const cache = useQueryClient();
  const [departmentName, setDepartmentName] = useState('');
  const [message, setMessage] = useState('');
  const departments = useQuery<Department[]>({
    queryKey: ['departments'], queryFn: () => fetchWithAuth('/departments', {}, getToken),
  });
  const departmentMutation = useMutation({
    mutationFn: () => fetchWithAuth('/departments', { method: 'POST', body: JSON.stringify({ name: departmentName.trim() }) }, getToken),
    onSuccess: () => { setDepartmentName(''); setMessage('Department created.'); void cache.invalidateQueries({ queryKey: ['departments'] }); },
  });
  const roleMutation = useMutation({
    mutationFn: (body: Record<string, string | number>) => fetchWithAuth('/roles', { method: 'POST', body: JSON.stringify(body) }, getToken),
    onSuccess: () => { setMessage('Job role created. You can now add employees with this role.'); void cache.invalidateQueries({ queryKey: ['roles'] }); },
  });
  function submitRole(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setMessage('');
    const data = new FormData(event.currentTarget);
    roleMutation.mutate({ title: String(data.get('title')), department_id: Number(data.get('department_id')),
      salary_band_min: String(data.get('salary_band_min')), salary_band_max: String(data.get('salary_band_max')) });
  }
  const field = 'mt-1 block w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900';
  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-6 space-y-5" aria-labelledby="organization-setup-title">
      <div><h2 id="organization-setup-title" className="font-semibold text-slate-900">Departments & job roles</h2>
        <p className="mt-1 text-sm text-slate-600">Create your organization’s departments and job roles before adding employees.</p></div>
      <form onSubmit={(event) => { event.preventDefault(); setMessage(''); departmentMutation.mutate(); }} className="flex flex-wrap items-end gap-3">
        <label className="grow text-sm text-slate-700">Department name
          <input className={field} value={departmentName} onChange={(event) => setDepartmentName(event.target.value)} required minLength={2} maxLength={255} /></label>
        <Button type="submit" disabled={departmentMutation.isPending} portalTheme="hr">Create department</Button>
      </form>
      {departments.isError && <p role="alert" className="text-sm text-red-700">Departments could not be loaded. <button type="button" className="underline" onClick={() => void departments.refetch()}>Retry</button></p>}
      <form onSubmit={submitRole} className="grid gap-3 sm:grid-cols-2">
        <label className="text-sm text-slate-700">Job title<input name="title" className={field} required minLength={2} maxLength={255} /></label>
        <div className="text-sm text-slate-700"><label htmlFor="organization-department">Department</label><select id="organization-department" name="department_id" className={field} required disabled={!departments.data?.length}>
          <option value="">Choose a department</option>{departments.data?.map((department) => <option key={department.department_id} value={department.department_id}>{department.name}</option>)}
        </select></div>
        <label className="text-sm text-slate-700">Minimum annual salary (₹)<input name="salary_band_min" type="number" min="0" max="9999999999.99" step="0.01" className={field} required /></label>
        <label className="text-sm text-slate-700">Maximum annual salary (₹)<input name="salary_band_max" type="number" min="0.01" max="9999999999.99" step="0.01" className={field} required /></label>
        <div><Button type="submit" disabled={roleMutation.isPending || !departments.data?.length} portalTheme="hr">Create job role</Button></div>
      </form>
      {message && <p role="status" className="text-sm text-emerald-700">{message}</p>}
      {(departmentMutation.error || roleMutation.error) && <p role="alert" className="text-sm text-red-700">{(departmentMutation.error || roleMutation.error)?.message}</p>}
    </section>
  );
}
