import { useState, type FormEvent } from 'react';
import { useAuth } from '../auth/AuthProvider';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { fetchWithAuth } from '../../lib/api';
import { Button } from '../common/Button';
import { fetchRoles } from '../../services/auditService';

type Department = { department_id: number; name: string };

export default function OrganizationSetup() {
  const { getToken } = useAuth();
  const cache = useQueryClient();
  const [departmentName, setDepartmentName] = useState('');
  const [message, setMessage] = useState('');
  const [selectedDepartment, setSelectedDepartment] = useState('');
  const [catalogSearch, setCatalogSearch] = useState('');
  const [roleValidation, setRoleValidation] = useState('');
  const [jobTitle, setJobTitle] = useState('');
  const [salaryMinimum, setSalaryMinimum] = useState('');
  const [salaryMaximum, setSalaryMaximum] = useState('');
  const roles = useQuery({ queryKey: ['roles'], queryFn: () => fetchRoles(getToken) });
  const departments = useQuery<Department[]>({
    queryKey: ['departments'], queryFn: () => fetchWithAuth('/departments', {}, getToken),
  });
  const departmentMutation = useMutation({
    mutationFn: (): Promise<Department> => fetchWithAuth('/departments', { method: 'POST', body: JSON.stringify({ name: departmentName.trim() }) }, getToken),
    onSuccess: (department) => {
      cache.setQueryData<Department[]>(['departments'], (current) => [...(current || []).filter((item) => item.department_id !== department.department_id), department].sort((a, b) => a.name.localeCompare(b.name)));
      setSelectedDepartment(String(department.department_id)); setDepartmentName(''); setMessage('Department created and selected for the next job role.');
      void cache.invalidateQueries({ queryKey: ['departments'] });
    },
  });
  const roleMutation = useMutation({
    mutationFn: (body: Record<string, string | number>) => fetchWithAuth('/roles', { method: 'POST', body: JSON.stringify(body) }, getToken),
    onSuccess: () => { setJobTitle(''); setSalaryMinimum(''); setSalaryMaximum(''); setMessage('Job role created. You can now add employees with this role.'); void cache.invalidateQueries({ queryKey: ['roles'] }); },
  });
  function submitRole(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setMessage(''); setRoleValidation('');
    const data = new FormData(event.currentTarget);
    const title = String(data.get('title')).trim();
    const minimum = Number(data.get('salary_band_min')), maximum = Number(data.get('salary_band_max'));
    if (minimum > maximum) { setRoleValidation('Maximum salary must be greater than or equal to minimum salary.'); return; }
    if (roles.data?.some((role) => role.department_id === Number(selectedDepartment) && role.title.toLowerCase() === title.toLowerCase())) {
      setRoleValidation('This job title already exists in the selected department.'); return;
    }
    roleMutation.mutate({ title, department_id: Number(selectedDepartment),
      salary_band_min: String(data.get('salary_band_min')), salary_band_max: String(data.get('salary_band_max')) });
  }
  const field = 'mt-1 block w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900';
  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-6 space-y-5" aria-labelledby="organization-setup-title">
      <div><h2 id="organization-setup-title" className="font-semibold text-slate-900">Departments & job roles</h2>
        <p className="mt-1 text-sm text-slate-600">Set up a department, then add its job roles and annual salary bands. These roles are available in individual registration and CSV imports.</p></div>
      <form onSubmit={(event) => { event.preventDefault(); setMessage(''); departmentMutation.mutate(); }} className="flex flex-wrap items-end gap-3">
        <label className="grow text-sm text-slate-700">Department name
          <input className={field} value={departmentName} onChange={(event) => setDepartmentName(event.target.value)} required minLength={2} maxLength={255} /></label>
        <Button type="submit" disabled={departmentMutation.isPending} portalTheme="hr">Create department</Button>
      </form>
      {departmentMutation.error && <p role="alert" className="text-sm text-red-700">Department: {departmentMutation.error.message}</p>}
      {departments.isError && <p role="alert" className="text-sm text-red-700">Departments could not be loaded. <button type="button" className="underline" onClick={() => void departments.refetch()}>Retry</button></p>}
      <form onSubmit={submitRole} className="grid gap-3 sm:grid-cols-2 border-t border-slate-200 pt-5">
        <label className="text-sm text-slate-700">Job title<input name="title" className={field} value={jobTitle} onChange={(event) => setJobTitle(event.target.value)} required minLength={2} maxLength={255} /></label>
        <div className="text-sm text-slate-700"><label htmlFor="organization-department">Department</label><select id="organization-department" name="department_id" className={field} required value={selectedDepartment} onChange={(event) => setSelectedDepartment(event.target.value)} disabled={!departments.data?.length}>
          <option value="">Choose a department</option>{departments.data?.map((department) => <option key={department.department_id} value={department.department_id}>{department.name}</option>)}
        </select></div>
        <label className="text-sm text-slate-700">Minimum annual salary (₹)<input name="salary_band_min" type="number" value={salaryMinimum} onChange={(event) => setSalaryMinimum(event.target.value)} min="0" max="9999999999.99" step="0.01" className={field} required /></label>
        <label className="text-sm text-slate-700">Maximum annual salary (₹)<input name="salary_band_max" type="number" value={salaryMaximum} onChange={(event) => setSalaryMaximum(event.target.value)} min="0.01" max="9999999999.99" step="0.01" className={field} required /></label>
        <div><Button type="submit" disabled={roleMutation.isPending || !departments.data?.length} portalTheme="hr">Create job role</Button></div>
      </form>
      {message && <p role="status" className="text-sm text-emerald-700">{message}</p>}
      {roleValidation && <p role="alert" className="text-sm text-red-700">{roleValidation}</p>}
      {roleMutation.error && <p role="alert" className="text-sm text-red-700">Job role: {roleMutation.error.message}</p>}
      <div className="border-t border-slate-200 pt-5 space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-3"><h3 className="font-medium text-slate-900">Role catalogue</h3><span className="text-sm text-slate-500">{departments.data?.length || 0} departments · {roles.data?.length || 0} job roles</span></div>
        <label className="block text-sm text-slate-700">Find a department or job role<input className={field} value={catalogSearch} onChange={(event) => setCatalogSearch(event.target.value)} placeholder="Search the role catalogue" /></label>
        {roles.isPending && <p role="status" className="text-sm">Loading job roles…</p>}
        {roles.isError && <p role="alert" className="text-sm text-red-700">Job roles could not be loaded. <button type="button" className="underline" onClick={() => void roles.refetch()}>Retry job roles</button></p>}
        {!roles.isPending && !roles.isError && <div className="max-h-72 overflow-auto rounded-lg border border-slate-200"><table className="w-full text-left text-sm"><caption className="sr-only">Available job roles and salary bands</caption><thead className="bg-slate-50"><tr><th className="p-3">Department</th><th className="p-3">Job title</th><th className="p-3">Annual salary band</th></tr></thead><tbody>
          {roles.data?.filter((role) => `${role.title} ${role.department_name}`.toLowerCase().includes(catalogSearch.toLowerCase())).map((role) => <tr key={role.role_id} className="border-t border-slate-200"><td className="p-3">{role.department_name}</td><td className="p-3">{role.title}</td><td className="p-3 whitespace-nowrap">₹{Number(role.salary_band_min).toLocaleString('en-IN')} – ₹{Number(role.salary_band_max).toLocaleString('en-IN')}</td></tr>)}
          {!roles.data?.some((role) => `${role.title} ${role.department_name}`.toLowerCase().includes(catalogSearch.toLowerCase())) && <tr><td colSpan={3} className="p-3 text-slate-500">No job roles found. Create a department and job role above to get started.</td></tr>}
        </tbody></table></div>}
      </div>
    </section>
  );
}
