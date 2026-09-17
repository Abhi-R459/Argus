import { useState, useEffect } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import * as z from 'zod';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useAuth } from '@clerk/clerk-react';
import { useNavigate } from 'react-router-dom';
import {
  User,
  DollarSign,
  Edit3,
  ShieldCheck,
  Calendar,
  Mail,
  Building2,
  Briefcase,
  Lock,
  ArrowUpRight,
  CheckCircle2,
  AlertCircle,
  Clock,
  UserX,
} from 'lucide-react';
import { DetailSheet } from '../common/DetailSheet';
import { Button } from '../common/Button';
import { fetchWithAuth, ApiError } from '../../lib/api';
import { fetchRoles, type RoleItem } from '../../services/auditService';

export interface Employee {
  employee_id: number;
  full_name: string;
  email: string;
  role_title: string;
  department_name: string;
  salary: number | null;
  date_hired: string;
  is_active: boolean;
}

export interface EmployeeSheetProps {
  employee: Employee | null;
  isOpen: boolean;
  onClose: () => void;
  initialTab?: 'overview' | 'edit' | 'salary';
  onEmployeeUpdated?: () => void;
}

// ─── Form Schemas ─────────────────────────────────────────────────────────────

const profileSchema = z.object({
  full_name: z.string().min(2, 'Name must be at least 2 characters').max(255).optional().or(z.literal('')),
  email: z.string().email('Invalid email address').optional().or(z.literal('')),
  role_id: z.coerce.number().int().positive('Please select a valid role').optional().or(z.nan()),
  contact_info: z.string().max(500).optional(),
});

type ProfileFormData = z.infer<typeof profileSchema>;

const salarySchema = z.object({
  amount: z.coerce.number().positive('Salary must be greater than 0'),
  effective_date: z.string().refine((val) => !isNaN(Date.parse(val)), {
    message: 'Invalid date format',
  }),
});

type SalaryFormData = z.infer<typeof salarySchema>;

export function EmployeeSheet({
  employee,
  isOpen,
  onClose,
  initialTab = 'overview',
  onEmployeeUpdated,
}: EmployeeSheetProps) {
  const { getToken } = useAuth();
  const queryClient = useQueryClient();
  const navigate = useNavigate();

  const [activeTab, setActiveTab] = useState<'overview' | 'edit' | 'salary'>(initialTab);
  const [feedbackMessage, setFeedbackMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  // Sync tab whenever initialTab or selected employee changes
  useEffect(() => {
    setActiveTab(initialTab);
    setFeedbackMessage(null);
  }, [initialTab, employee?.employee_id]);

  // Query roles for the edit dropdown
  const { data: roles = [], isLoading: isRolesLoading } = useQuery<RoleItem[]>({
    queryKey: ['roles'],
    queryFn: () => fetchRoles(() => getToken()),
    staleTime: 300000,
    enabled: isOpen,
  });

  // Profile Edit Form setup
  const {
    register: registerProfile,
    handleSubmit: handleProfileSubmit,
    reset: resetProfile,
    formState: { errors: profileErrors, isSubmitting: isProfileSubmitting, isDirty: isProfileDirty },
  } = useForm<ProfileFormData>({
    resolver: zodResolver(profileSchema),
    defaultValues: {
      full_name: employee?.full_name || '',
      email: employee?.email || '',
      role_id: undefined,
      contact_info: '',
    },
  });

  // Reset profile form when employee changes
  useEffect(() => {
    if (employee) {
      resetProfile({
        full_name: employee.full_name,
        email: employee.email,
        role_id: undefined,
        contact_info: '',
      });
    }
  }, [employee, resetProfile]);

  // Salary Adjustment Form setup
  const {
    register: registerSalary,
    handleSubmit: handleSalarySubmit,
    reset: resetSalary,
    formState: { errors: salaryErrors, isSubmitting: isSalarySubmitting },
  } = useForm<SalaryFormData>({
    resolver: zodResolver(salarySchema),
    defaultValues: {
      amount: employee?.salary ?? undefined,
      effective_date: new Date().toISOString().split('T')[0],
    },
  });

  // Reset salary form when employee changes
  useEffect(() => {
    if (employee) {
      resetSalary({
        amount: employee.salary ?? undefined,
        effective_date: new Date().toISOString().split('T')[0],
      });
    }
  }, [employee, resetSalary]);

  // ─── Mutations ──────────────────────────────────────────────────────────────

  const updateProfileMutation = useMutation({
    mutationFn: (data: ProfileFormData) => {
      if (!employee) throw new Error('No employee selected');
      const payload: Record<string, unknown> = {};
      if (data.full_name && data.full_name !== employee.full_name) payload.full_name = data.full_name;
      if (data.email && data.email !== employee.email) payload.email = data.email;
      if (data.role_id && !isNaN(data.role_id)) payload.role_id = data.role_id;
      if (data.contact_info) payload.contact_info = data.contact_info;

      if (Object.keys(payload).length === 0) {
        return Promise.resolve(null);
      }

      return fetchWithAuth(`/employees/${employee.employee_id}`, {
        method: 'PATCH',
        body: JSON.stringify(payload),
      }, getToken);
    },
    onSuccess: (res) => {
      if (res !== null) {
        queryClient.invalidateQueries({ queryKey: ['employees'] });
        queryClient.invalidateQueries({ queryKey: ['dashboardStats'] });
        onEmployeeUpdated?.();
      }
      setFeedbackMessage({
        type: 'success',
        text: 'Profile updated and cryptographically hashed into audit trail.',
      });
      setActiveTab('overview');
    },
    onError: (error) => {
      setFeedbackMessage({
        type: 'error',
        text: error instanceof ApiError ? error.message : 'Failed to update employee profile.',
      });
    },
  });

  const updateSalaryMutation = useMutation({
    mutationFn: (data: SalaryFormData) => {
      if (!employee) throw new Error('No employee selected');
      return fetchWithAuth(`/employees/${employee.employee_id}/salary`, {
        method: 'POST',
        body: JSON.stringify(data),
      }, getToken);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['employees'] });
      queryClient.invalidateQueries({ queryKey: ['dashboardStats'] });
      queryClient.invalidateQueries({ queryKey: ['audit-chain'] });
      onEmployeeUpdated?.();
      setFeedbackMessage({
        type: 'success',
        text: 'Compensation adjustment validated and recorded to immutable ledger.',
      });
      setActiveTab('overview');
    },
    onError: (error) => {
      setFeedbackMessage({
        type: 'error',
        text: error instanceof ApiError ? error.message : 'Failed to record salary update.',
      });
    },
  });

  const deactivateMutation = useMutation({
    mutationFn: () => {
      if (!employee) throw new Error('No employee selected');
      return fetchWithAuth(`/employees/${employee.employee_id}`, {
        method: 'DELETE',
      }, getToken);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['employees'] });
      queryClient.invalidateQueries({ queryKey: ['dashboardStats'] });
      onEmployeeUpdated?.();
      onClose();
    },
    onError: (error) => {
      setFeedbackMessage({
        type: 'error',
        text: error instanceof ApiError ? error.message : 'Failed to deactivate employee record.',
      });
    },
  });

  if (!employee) return null;

  const formattedSalary = employee.salary
    ? new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 }).format(
        employee.salary
      )
    : 'Not Recorded';

  return (
    <DetailSheet
      isOpen={isOpen}
      onClose={onClose}
      portalTheme="hr"
      mode="drawer"
      widthClass="w-full sm:w-[500px] lg:w-[540px]"
      title={employee.full_name}
      subtitle={`EMP-${employee.employee_id.toString().padStart(4, '0')} • ${employee.role_title}`}
      headerBadge={
        <span
          className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold border ${
            employee.is_active
              ? 'bg-linear-success/10 text-linear-success border-linear-success/20'
              : 'bg-grafana-surface text-grafana-neutral border-grafana-border'
          }`}
        >
          <span
            className={`w-1.5 h-1.5 rounded-full ${
              employee.is_active ? 'bg-linear-success' : 'bg-grafana-neutral/50'
            }`}
          />
          {employee.is_active ? 'Active' : 'Deactivated'}
        </span>
      }
    >
      {/* Tab Navigation */}
      <div className="flex border-b border-grafana-border pb-3 gap-2">
        <button
          type="button"
          onClick={() => {
            setActiveTab('overview');
            setFeedbackMessage(null);
          }}
          className={`px-3 py-1.5 text-xs font-semibold rounded-lg transition-colors duration-150 flex items-center gap-1.5 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-grafana-orange ${
            activeTab === 'overview'
              ? 'bg-black text-white shadow-2xs'
              : 'text-grafana-neutral hover:text-grafana-ink hover:bg-grafana-surface'
          }`}
        >
          <User className="w-3.5 h-3.5" />
          Overview
        </button>
        <button
          type="button"
          onClick={() => {
            setActiveTab('edit');
            setFeedbackMessage(null);
          }}
          className={`px-3 py-1.5 text-xs font-semibold rounded-lg transition-colors duration-150 flex items-center gap-1.5 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-grafana-orange ${
            activeTab === 'edit'
              ? 'bg-black text-white shadow-2xs'
              : 'text-grafana-neutral hover:text-grafana-ink hover:bg-grafana-surface'
          }`}
        >
          <Edit3 className="w-3.5 h-3.5" />
          Edit Profile
        </button>
        <button
          type="button"
          onClick={() => {
            setActiveTab('salary');
            setFeedbackMessage(null);
          }}
          className={`px-3 py-1.5 text-xs font-semibold rounded-lg transition-colors duration-150 flex items-center gap-1.5 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-grafana-orange ${
            activeTab === 'salary'
              ? 'bg-black text-white shadow-2xs'
              : 'text-grafana-neutral hover:text-grafana-ink hover:bg-grafana-surface'
          }`}
        >
          <DollarSign className="w-3.5 h-3.5" />
          Compensation
        </button>
      </div>

      {/* Feedback Banner */}
      {feedbackMessage && (
        <div
          className={`p-3 rounded-lg border text-xs flex items-start gap-2 animate-in fade-in duration-150 ${
            feedbackMessage.type === 'success'
              ? 'bg-linear-success/10 text-linear-success border-linear-success/30'
              : 'bg-grafana-orange/10 text-grafana-orange border-grafana-orange/30'
          }`}
        >
          {feedbackMessage.type === 'success' ? (
            <CheckCircle2 className="w-4 h-4 shrink-0 mt-0.5" />
          ) : (
            <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
          )}
          <span className="font-medium">{feedbackMessage.text}</span>
        </div>
      )}

      {/* ─── TAB 1: OVERVIEW ──────────────────────────────────────────────── */}
      {activeTab === 'overview' && (
        <div className="space-y-4">
          {/* Identity & Core Information */}
          <div className="bg-grafana-surface/60 rounded-xl border border-grafana-border p-4 space-y-3">
            <h4 className="text-xs font-bold text-grafana-neutral uppercase tracking-wider font-mono">
              Personnel Details
            </h4>
            <div className="grid grid-cols-2 gap-3 text-xs">
              <div>
                <span className="text-grafana-neutral block">Full Name</span>
                <span className="font-bold text-grafana-ink">{employee.full_name}</span>
              </div>
              <div>
                <span className="text-grafana-neutral block">System Identifier</span>
                <span className="font-mono font-bold text-grafana-ink">#{employee.employee_id}</span>
              </div>
              <div className="col-span-2">
                <span className="text-grafana-neutral block">Official Email</span>
                <span className="font-mono font-medium text-grafana-ink flex items-center gap-1.5 mt-0.5">
                  <Mail className="w-3.5 h-3.5 text-grafana-neutral" />
                  {employee.email}
                </span>
              </div>
              <div>
                <span className="text-grafana-neutral block">Assigned Role</span>
                <span className="font-semibold text-grafana-ink flex items-center gap-1 mt-0.5">
                  <Briefcase className="w-3.5 h-3.5 text-grafana-neutral" />
                  {employee.role_title}
                </span>
              </div>
              <div>
                <span className="text-grafana-neutral block">Department</span>
                <span className="font-semibold text-grafana-ink flex items-center gap-1 mt-0.5">
                  <Building2 className="w-3.5 h-3.5 text-grafana-neutral" />
                  {employee.department_name}
                </span>
              </div>
              <div>
                <span className="text-grafana-neutral block">Date Onboarded</span>
                <span className="font-mono text-grafana-ink flex items-center gap-1 mt-0.5">
                  <Calendar className="w-3.5 h-3.5 text-grafana-neutral" />
                  {new Date(employee.date_hired).toLocaleDateString()}
                </span>
              </div>
              <div>
                <span className="text-grafana-neutral block">Current Compensation</span>
                <span className="font-mono font-bold text-linear-success mt-0.5 block">
                  {formattedSalary}
                </span>
              </div>
            </div>
          </div>

          {/* Cryptographic Shield & PII Protection */}
          <div className="bg-white rounded-xl border border-grafana-border p-4 space-y-3">
            <div className="flex items-center justify-between">
              <h4 className="text-xs font-bold text-grafana-neutral uppercase tracking-wider font-mono flex items-center gap-1.5">
                <ShieldCheck className="w-3.5 h-3.5 text-linear-success" />
                PII Encryption & Shielding
              </h4>
              <span className="text-[10px] font-mono font-bold text-linear-success bg-linear-success/10 border border-linear-success/20 px-2 py-0.5 rounded">
                pgcrypto
              </span>
            </div>
            <div className="space-y-2 text-xs">
              <div className="flex items-center justify-between p-2.5 rounded-lg bg-grafana-surface border border-grafana-border/70">
                <span className="text-grafana-neutral font-medium flex items-center gap-1.5">
                  <Lock className="w-3 h-3 text-grafana-neutral" />
                  National ID (Aadhar/SSN)
                </span>
                <span className="font-mono text-xs text-grafana-neutral tracking-widest">
                  •••• •••• ••••
                </span>
              </div>
              <div className="flex items-center justify-between p-2.5 rounded-lg bg-grafana-surface border border-grafana-border/70">
                <span className="text-grafana-neutral font-medium flex items-center gap-1.5">
                  <Lock className="w-3 h-3 text-grafana-neutral" />
                  Contact Credentials
                </span>
                <span className="font-mono text-[11px] text-grafana-neutral">
                  Symmetric AES Encrypted
                </span>
              </div>
            </div>
            <p className="text-[11px] text-grafana-neutral leading-relaxed">
              PII attributes are encrypted at rest using PostgreSQL <code className="font-mono text-black">pgp_sym_encrypt</code> and never returned in plaintext to unauthorized endpoints.
            </p>
          </div>

          {/* Audit Chain Link */}
          <div className="bg-white rounded-xl border border-grafana-border p-4 space-y-3">
            <div className="flex items-center justify-between">
              <h4 className="text-xs font-bold text-grafana-neutral uppercase tracking-wider font-mono flex items-center gap-1.5">
                <Clock className="w-3.5 h-3.5 text-grafana-blue" />
                Forensic Audit Trail
              </h4>
              <span className="text-[10px] font-mono text-grafana-neutral bg-grafana-surface border border-grafana-border px-2 py-0.5 rounded">
                Immutable SHA-256
              </span>
            </div>
            <p className="text-xs text-grafana-neutral leading-relaxed">
              Every insert, update, or compensation adjustment on this employee is sealed into the SHA-256 tamper-evident chain by automated database triggers.
            </p>
            <Button
              variant="secondary"
              size="sm"
              portalTheme="hr"
              onClick={() => {
                onClose();
                navigate(`/auditor/time-travel?emp_id=${employee.employee_id}`);
              }}
              rightIcon={<ArrowUpRight className="w-3.5 h-3.5 text-grafana-neutral" />}
              className="w-full justify-between"
            >
              <span>Inspect Time-Travel History</span>
            </Button>
          </div>

          {/* Quick Actions */}
          <div className="pt-2 flex items-center gap-2">
            <Button
              variant="success"
              size="sm"
              portalTheme="hr"
              onClick={() => {
                setActiveTab('salary');
                setFeedbackMessage(null);
              }}
              className="flex-1"
            >
              Adjust Salary
            </Button>
            <Button
              variant="secondary"
              size="sm"
              portalTheme="hr"
              onClick={() => {
                setActiveTab('edit');
                setFeedbackMessage(null);
              }}
              className="flex-1"
            >
              Edit Profile
            </Button>
            {employee.is_active && (
              <Button
                variant="danger"
                size="icon-sm"
                portalTheme="hr"
                onClick={() => {
                  if (window.confirm(`Are you sure you want to deactivate ${employee.full_name}?`)) {
                    deactivateMutation.mutate();
                  }
                }}
                disabled={deactivateMutation.isPending}
                loading={deactivateMutation.isPending}
                title="Deactivate employee"
                aria-label={`Deactivate ${employee.full_name}`}
                leftIcon={<UserX className="w-4 h-4" />}
              />
            )}
          </div>
        </div>
      )}

      {/* ─── TAB 2: EDIT PROFILE ──────────────────────────────────────────── */}
      {activeTab === 'edit' && (
        <form
          onSubmit={handleProfileSubmit((data) => {
            setFeedbackMessage(null);
            updateProfileMutation.mutate(data);
          })}
          className="space-y-4"
        >
          <div className="space-y-3.5">
            <div>
              <label className="block text-xs font-bold text-grafana-ink uppercase tracking-wider font-mono mb-1.5">
                Full Name
              </label>
              <input
                type="text"
                {...registerProfile('full_name')}
                placeholder="Full Name"
                className="w-full px-3 py-2 border border-grafana-border rounded-lg text-sm bg-white text-grafana-ink focus:outline-none focus:ring-2 focus:ring-grafana-orange/20 focus:border-grafana-orange transition-colors"
              />
              {profileErrors.full_name && (
                <p className="mt-1 text-xs text-grafana-orange">{profileErrors.full_name.message}</p>
              )}
            </div>

            <div>
              <label className="block text-xs font-bold text-grafana-ink uppercase tracking-wider font-mono mb-1.5">
                Email Address
              </label>
              <input
                type="email"
                {...registerProfile('email')}
                placeholder="workforce@example.com"
                className="w-full px-3 py-2 border border-grafana-border rounded-lg text-sm bg-white text-grafana-ink focus:outline-none focus:ring-2 focus:ring-grafana-orange/20 focus:border-grafana-orange transition-colors font-mono"
              />
              {profileErrors.email && (
                <p className="mt-1 text-xs text-grafana-orange">{profileErrors.email.message}</p>
              )}
            </div>

            <div>
              <label className="block text-xs font-bold text-grafana-ink uppercase tracking-wider font-mono mb-1.5">
                Role & Department Assignment
              </label>
              <select
                {...registerProfile('role_id')}
                className="w-full px-3 py-2 border border-grafana-border rounded-lg text-sm bg-white text-grafana-ink focus:outline-none focus:ring-2 focus:ring-grafana-orange/20 focus:border-grafana-orange transition-colors"
              >
                <option value="">
                  {isRolesLoading ? 'Loading roles from database…' : `Keep Current: ${employee.role_title || 'Unassigned'} (${employee.department_name || 'General'})`}
                </option>
                {roles.map((r) => {
                  const minSal = Number(r.min_salary ?? r.salary_band_min ?? 0);
                  const maxSal = Number(r.max_salary ?? r.salary_band_max ?? 0);
                  const bandStr = (minSal > 0 || maxSal > 0)
                    ? ` (₹${minSal.toLocaleString('en-IN')} – ₹${maxSal.toLocaleString('en-IN')})`
                    : '';
                  return (
                    <option key={r.role_id} value={r.role_id}>
                      {r.title} — {r.department_name}{bandStr}
                    </option>
                  );
                })}
              </select>
              {profileErrors.role_id && (
                <p className="mt-1 text-xs text-grafana-orange">{profileErrors.role_id.message}</p>
              )}
            </div>

            <div>
              <label className="block text-xs font-bold text-grafana-ink uppercase tracking-wider font-mono mb-1.5">
                Contact Information (Encrypted)
              </label>
              <textarea
                {...registerProfile('contact_info')}
                rows={3}
                placeholder="Enter new contact details to update encrypted payload (leave blank to retain current)..."
                className="w-full px-3 py-2 border border-grafana-border rounded-lg text-sm bg-white text-grafana-ink focus:outline-none focus:ring-2 focus:ring-grafana-orange/20 focus:border-grafana-orange transition-colors"
              />
              <p className="mt-1 text-[11px] text-grafana-neutral flex items-center gap-1">
                <Lock className="w-3 h-3 text-linear-success" />
                Payload is symmetrically encrypted via PostgreSQL pgcrypto before storage.
              </p>
              {profileErrors.contact_info && (
                <p className="mt-1 text-xs text-grafana-orange">{profileErrors.contact_info.message}</p>
              )}
            </div>
          </div>

          <div className="pt-3 border-t border-grafana-border flex items-center justify-end gap-2">
            <Button
              variant="secondary"
              size="sm"
              portalTheme="hr"
              onClick={() => {
                setActiveTab('overview');
                setFeedbackMessage(null);
              }}
              disabled={isProfileSubmitting}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              variant="primary"
              size="sm"
              portalTheme="hr"
              disabled={isProfileSubmitting || !isProfileDirty}
              loading={isProfileSubmitting}
            >
              Save Profile Changes
            </Button>
          </div>
        </form>
      )}

      {/* ─── TAB 3: ADJUST SALARY ─────────────────────────────────────────── */}
      {activeTab === 'salary' && (
        <form
          onSubmit={handleSalarySubmit((data) => {
            setFeedbackMessage(null);
            updateSalaryMutation.mutate(data);
          })}
          className="space-y-4"
        >
          {/* Current Compensation Card */}
          <div className="bg-grafana-surface/60 rounded-xl border border-grafana-border p-4 space-y-2">
            <span className="text-xs font-bold text-grafana-neutral uppercase tracking-wider font-mono">
              Current Compensation
            </span>
            <div className="flex items-baseline gap-2">
              <span className="text-2xl font-extrabold text-grafana-ink font-mono tabular-nums">
                {formattedSalary}
              </span>
              <span className="text-xs text-grafana-neutral">per annum</span>
            </div>
            <p className="text-[11px] text-grafana-neutral">
              Validated against role range for <span className="font-semibold text-black">{employee.role_title}</span>.
            </p>
          </div>

          <div className="space-y-3.5">
            <div>
              <label className="block text-xs font-bold text-grafana-ink uppercase tracking-wider font-mono mb-1.5">
                New Annual Salary (INR)
              </label>
              <div className="relative">
                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-sm font-semibold text-grafana-neutral">
                  ₹
                </div>
                <input
                  type="number"
                  step="1"
                  {...registerSalary('amount')}
                  placeholder="e.g. 95000"
                  className="w-full pl-8 pr-3 py-2 border border-grafana-border rounded-lg text-sm bg-white text-grafana-ink font-mono focus:outline-none focus:ring-2 focus:ring-linear-success/20 focus:border-linear-success transition-colors tabular-nums"
                />
              </div>
              {salaryErrors.amount && (
                <p className="mt-1 text-xs text-grafana-orange">{salaryErrors.amount.message}</p>
              )}
            </div>

            <div>
              <label className="block text-xs font-bold text-grafana-ink uppercase tracking-wider font-mono mb-1.5">
                Effective Date
              </label>
              <div className="relative">
                <input
                  type="date"
                  {...registerSalary('effective_date')}
                  className="w-full px-3 py-2 border border-grafana-border rounded-lg text-sm bg-white text-grafana-ink font-mono focus:outline-none focus:ring-2 focus:ring-linear-success/20 focus:border-linear-success transition-colors"
                />
              </div>
              {salaryErrors.effective_date && (
                <p className="mt-1 text-xs text-grafana-orange">{salaryErrors.effective_date.message}</p>
              )}
            </div>
          </div>

          <div className="p-3.5 rounded-lg bg-linear-success/5 border border-linear-success/20 text-xs text-grafana-ink space-y-1">
            <span className="font-semibold flex items-center gap-1.5 text-linear-success font-mono uppercase tracking-wider text-[10px]">
              <ShieldCheck className="w-3.5 h-3.5" />
              Automated Checkpoint Trigger
            </span>
            <p className="text-grafana-neutral text-[11px] leading-relaxed">
              Recording this adjustment creates an entry in <code className="font-mono text-black">salary_history</code> and triggers an automatic SHA-256 block creation in <code className="font-mono text-black">audit_log</code>.
            </p>
          </div>

          <div className="pt-3 border-t border-grafana-border flex items-center justify-end gap-2">
            <Button
              variant="secondary"
              size="sm"
              portalTheme="hr"
              onClick={() => {
                setActiveTab('overview');
                setFeedbackMessage(null);
              }}
              disabled={isSalarySubmitting}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              variant="success"
              size="sm"
              portalTheme="hr"
              disabled={isSalarySubmitting}
              loading={isSalarySubmitting}
              className="bg-linear-success hover:bg-linear-success-hover text-white"
            >
              Record Salary Adjustment
            </Button>
          </div>
        </form>
      )}
    </DetailSheet>
  );
}
