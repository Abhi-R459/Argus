import { z } from 'zod';
import type { RoleItem } from '../services/auditService';

export const employeeCsvHeader = 'full_name,email,job_title,department,national_id,contact_info,date_hired,salary';
export const importLimit = 100;
export const importBatchSize = 20;
const normalize = (value: string) => value.trim().toLocaleLowerCase();

function validDate(value: string): boolean {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) return false;
  const parsed = new Date(`${value}T00:00:00Z`);
  return Number.isFinite(parsed.getTime()) && parsed.toISOString().slice(0, 10) === value;
}

const employeeRow = z.object({
  full_name: z.string().min(2).max(255), email: z.string().email().max(255),
  role_id: z.number().int().positive(), national_id: z.string().min(5).max(255),
  contact_info: z.string().min(5).max(500),
  date_hired: z.string().refine(validDate, 'Use a valid date in YYYY-MM-DD format'),
  salary: z.string().regex(/^\d+(\.\d{1,2})?$/, 'Use a positive amount with at most two decimal places')
    .refine((value) => Number(value) > 0 && Number(value) <= 9_999_999_999.99, 'Salary must be between 0.01 and 9999999999.99'),
});
export type ImportedEmployee = z.infer<typeof employeeRow>;
export type ImportRow = { line: number; fields: string[]; employee?: ImportedEmployee; errors: string[] };

// Parse quoted CSV fields without evaluating formulas or interpreting file content as HTML.
function parseCsv(source: string): string[][] {
  const rows: string[][] = [];
  let row: string[] = [], field = '', quoted = false, closed = false;
  const input = source.replace(/^\uFEFF/, '');
  for (let index = 0; index < input.length; index++) {
    const char = input[index];
    if (quoted) {
      if (char === '"' && input[index + 1] === '"') { field += '"'; index++; }
      else if (char === '"') { quoted = false; closed = true; }
      else field += char;
    } else if (char === ',' || char === '\n' || char === '\r') {
      row.push(field.trim()); field = ''; closed = false;
      if (char !== ',') {
        if (char === '\r' && input[index + 1] === '\n') index++;
        rows.push(row); row = [];
      }
    } else if (char === '"' && field === '' && !closed) quoted = true;
    else {
      if (char === '"' || (closed && char.trim())) throw new Error('Malformed CSV quotation. Put quoted fields inside double quotes and escape quotes as "".');
      if (!closed) field += char;
    }
  }
  if (quoted) throw new Error('A quoted field is missing its closing double quote.');
  if (field || row.length || closed) { row.push(field.trim()); rows.push(row); }
  return rows;
}

export function previewEmployeeImport(source: string, roles: RoleItem[]): ImportRow[] {
  if (source.length > 250_000) throw new Error('CSV is too large. Use at most 100 employees and 250,000 characters.');
  const rows = parseCsv(source);
  const header = rows.shift()?.map(normalize);
  if (!header || header.join(',') !== employeeCsvHeader) throw new Error(`The first row must be: ${employeeCsvHeader}`);
  const numbered = rows.map((fields, index) => ({ fields, line: index + 2 })).filter(({ fields }) => fields.some(Boolean));
  if (!numbered.length || numbered.length > importLimit) throw new Error('Include between 1 and 100 employees per import.');
  const emails = new Map<string, number>();
  for (const { fields } of numbered) {
    const email = normalize(fields[1] || '');
    emails.set(email, (emails.get(email) || 0) + 1);
  }
  return numbered.map(({ fields, line }) => {
    const errors: string[] = [];
    if (fields.length !== 8) errors.push('Expected eight columns. Quote values containing commas.');
    const [full_name = '', email = '', title = '', department = '', national_id = '', contact_info = '', date_hired = '', salary = ''] = fields;
    const matches = roles.filter((role) => normalize(role.title) === normalize(title) && normalize(role.department_name || '') === normalize(department));
    if (matches.length !== 1) errors.push(matches.length ? 'This job title is ambiguous in this department. Use a unique job title.' : 'Department and job title must match an existing job role. Create the role first.');
    if ((emails.get(normalize(email)) || 0) > 1) errors.push('Duplicate email in this CSV.');
    const parsed = employeeRow.safeParse({ full_name, email, role_id: matches[0]?.role_id || 0, national_id, contact_info, date_hired, salary });
    if (!parsed.success) errors.push(...parsed.error.issues.filter((issue) => issue.path[0] !== 'role_id').map((issue) => `${issue.path[0]}: ${issue.message}`));
    return { line, fields, errors, employee: parsed.success && !errors.length ? parsed.data : undefined };
  });
}
