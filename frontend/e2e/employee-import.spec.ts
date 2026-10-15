import { expect, test } from '@playwright/test';
import { mockArgusApi } from './fixtures/argus-api';
import { employeeCsvHeader, previewEmployeeImport } from '../src/lib/employeeImport';
import type { RoleItem } from '../src/services/auditService';

const roles = [{ role_id: 1, title: 'Engineer', department_name: 'Engineering' }] as RoleItem[];
const row = (index: number) => `QA Employee ${index},qa${index}@example.com,Engineer,Engineering,QA-ID-${index},Fictional contact,2024-01-01,500000`;
const csv = (count: number) => [employeeCsvHeader, ...Array.from({ length: count }, (_, index) => row(index + 1))].join('\n');

test('CSV accepts BOM, CRLF, escaped quotes, commas and multiline fields', () => {
  const input = `\uFEFF${employeeCsvHeader}\r\n"QA, ""One""",qa@example.com,Engineer,Engineering,QA-ID-1,"Fictional\r\ncontact",2024-02-29,500000.25\r\n`;
  const preview = previewEmployeeImport(input, roles);
  expect(preview).toHaveLength(1);
  expect(preview[0].errors).toEqual([]);
  expect(preview[0].employee?.full_name).toBe('QA, "One"');
  expect(preview[0].employee?.contact_info).toBe('Fictional\r\ncontact');
});

test('CSV rejects invalid dates, duplicate emails, unknown roles and ambiguous roles', () => {
  const duplicate = `${employeeCsvHeader}\n${row(1)}\n${row(1).replace('2024-01-01', '2024-02-30')}`;
  const preview = previewEmployeeImport(duplicate, roles);
  expect(preview.every((item) => item.errors.some((error) => error.includes('Duplicate email')))).toBe(true);
  expect(preview[1].errors.join(' ')).toContain('valid date');
  expect(previewEmployeeImport(csv(1), [])[0].errors.join(' ')).toContain('existing job role');
  expect(previewEmployeeImport(csv(1), [...roles, ...roles])[0].errors.join(' ')).toContain('ambiguous');
  expect(() => previewEmployeeImport(csv(101), roles)).toThrow('1 and 100');
  expect(() => previewEmployeeImport(`${employeeCsvHeader}\n"unfinished`, roles)).toThrow('closing double quote');
});

test.describe('HR employee import workflow', () => {
  test.beforeEach(async ({ page }) => {
    await page.addInitScript(() => { (window as Window & { __E2E_ROLE__?: string }).__E2E_ROLE__ = 'hr_admin'; });
    await mockArgusApi(page);
  });
  test('reviews before writing and splits 21 employees into bounded batches', async ({ page }) => {
    const sizes: number[] = [];
    await page.route('**/api/employees/batch', async (route) => {
      const employees = route.request().postDataJSON().employees;
      sizes.push(employees.length);
      await route.fulfill({ status: 201, contentType: 'application/json', body: JSON.stringify(employees.map((_: unknown, index: number) => ({ employee_id: index + 1 }))) });
    });
    await page.goto('/hr/employees');
    await page.getByRole('button', { name: 'Import employees', exact: true }).click();
    await page.getByLabel('Paste employee CSV').fill(csv(21));
    await page.getByRole('button', { name: 'Review employees', exact: true }).click();
    await expect(page.getByRole('status').filter({ hasText: '21 employees reviewed. 0 rows need correction.' })).toBeVisible();
    expect(sizes).toEqual([]);
    await page.getByRole('button', { name: 'Confirm and add 21 employees' }).click();
    await expect(page.getByRole('status').filter({ hasText: '21 of 21 employees saved. Import complete.' })).toBeVisible();
    expect(sizes).toEqual([20, 1]);
  });
  test('invalid rows block submission and edits invalidate the preview', async ({ page }) => {
    await page.goto('/hr/employees');
    await page.getByRole('button', { name: 'Import employees', exact: true }).click();
    await page.getByLabel('Paste employee CSV').fill(csv(1).replace('Engineer,', 'Missing,'));
    await page.getByRole('button', { name: 'Review employees', exact: true }).click();
    await expect(page.getByRole('button', { name: 'Confirm and add 1 employees' })).toBeDisabled();
    await expect(page.getByText(/Department and job title must match/)).toBeVisible();
    await page.getByLabel('Paste employee CSV').fill(csv(1));
    await expect(page.getByRole('button', { name: 'Confirm and add 0 employees' })).toBeDisabled();
  });
  test('a failed later batch preserves the completed count and is never retried automatically', async ({ page }) => {
    let calls = 0;
    await page.route('**/api/employees/batch', async (route) => {
      calls++;
      const body = route.request().postDataJSON().employees;
      await route.fulfill({ status: calls === 1 ? 201 : 409, contentType: 'application/json', body: JSON.stringify(calls === 1 ? body.map(() => ({ employee_id: 1 })) : { detail: 'Duplicate email. No employees were added from this batch.' }) });
    });
    await page.goto('/hr/employees');
    await page.getByRole('button', { name: 'Import employees', exact: true }).click();
    await page.getByLabel('Paste employee CSV').fill(csv(21));
    await page.getByRole('button', { name: 'Review employees', exact: true }).click();
    await page.getByRole('button', { name: 'Confirm and add 21 employees' }).click();
    await expect(page.getByRole('alert')).toContainText('20 employees confirmed saved');
    await expect(page.getByRole('status').filter({ hasText: '20 of 21 employees saved. Import stopped.' })).toBeVisible();
    expect(calls).toBe(2);
    await expect(page.getByRole('button', { name: /Confirm and add/ })).toHaveCount(0);
  });
  test('organisation setup is available inside the directory and the catalogue is searchable', async ({ page }) => {
    await page.goto('/hr/employees');
    await page.getByRole('button', { name: 'Departments & roles', exact: true }).click();
    await page.getByLabel('Find a department or job role').fill('Finance');
    await expect(page.getByRole('table', { name: 'Available job roles and salary bands' }).getByText('Analyst', { exact: true })).toBeVisible();
    await expect(page.getByRole('table', { name: 'Available job roles and salary bands' }).getByText('Engineer', { exact: true })).toHaveCount(0);
  });
});
