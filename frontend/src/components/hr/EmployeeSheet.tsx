import { useState, useEffect, useRef } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import * as z from 'zod';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useAuth } from '@clerk/clerk-react';
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
  CheckCircle2,
  AlertCircle,
  Clock,
  UserX,
} from 'lucide-react';
import { DetailSheet } from '../common/DetailSheet';
import { Button } from '../common/Button';
import { SegmentedControl } from '../common/SegmentedControl';
import { formatINR } from '../../lib/format';
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

  const [activeTab, setActiveTab] = useState<'overview' | 'edit' | 'salary'>(initialTab);
  const [feedbackMessage, setFeedbackMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);
  const [isDeactivateModalOpen, setIsDeactivateModalOpen] = useState(false);
  const [showDiscardConfirm, setShowDiscardConfirm] = useState(false);
  const [pendingAction, setPendingAction] = useState<
    { type: 'tab'; tab: 'overview' | 'edit' | 'salary' } | { type: 'close' } | null
  >(null);

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
    formState: { errors: salaryErrors, isSubmitting: isSalarySubmitting, isDirty: isSalaryDirty },
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

  // Cache last non-null employee so sheet content stays rendered during smooth exit transition
  const cachedEmployee = useRef<Employee | null>(employee);
  if (employee) {
    cachedEmployee.current = employee;
  }
  const currentEmployee = employee || cachedEmployee.current;

  if (!currentEmployee) return null;

  const formattedSalary = currentEmployee.salary ? formatINR(currentEmployee.salary) : 'Not Recorded';

  const handleTabChange = (nextTab: 'overview' | 'edit' | 'salary') => {
    if (nextTab === activeTab) return;
    const hasUnsavedChanges = (activeTab === 'edit' && isProfileDirty) || (activeTab === 'salary' && isSalaryDirty);
    if (hasUnsavedChanges) {
      setPendingAction({ type: 'tab', tab: nextTab });
      setShowDiscardConfirm(true);
    } else {
      setActiveTab(nextTab);
      setFeedbackMessage(null);
    }
  };

  const handleCloseRequest = () => {
    const hasUnsavedChanges = (activeTab === 'edit' && isProfileDirty) || (activeTab === 'salary' && isSalaryDirty);
    if (hasUnsavedChanges) {
      setPendingAction({ type: 'close' });
      setShowDiscardConfirm(true);
    } else {
      onClose();
    }
  };

  return (
    <DetailSheet
      isOpen={isOpen}
      onClose={handleCloseRequest}
      portalTheme="hr"
      mode="drawer"
      widthClass="w-full sm:w-[520px] lg:w-[580px]"
      title={currentEmployee.full_name}
      subtitle={`EMP-${currentEmployee.employee_id.toString().padStart(4, '0')} • ${currentEmployee.role_title}`}
      headerBadge={
        <span
          className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium border ${
            currentEmployee.is_active
              ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
              : 'bg-slate-100 text-slate-600 border-slate-200'
          }`}
        >
          <span
            className={`w-1.5 h-1.5 rounded-full ${
              currentEmployee.is_active ? 'bg-emerald-500' : 'bg-slate-400'
            }`}
          />
          {currentEmployee.is_active ? 'Active' : 'Deactivated'}
        </span>
      }
    >
      {/* Modern Segmented Tab Switcher */}
      <SegmentedControl<'overview' | 'edit' | 'salary'>
        value={activeTab}
        onChange={handleTabChange}
        options={[
          { value: 'overview', label: 'Overview', icon: <User className="w-3.5 h-3.5" /> },
          { value: 'edit', label: 'Edit Profile', icon: <Edit3 className="w-3.5 h-3.5" /> },
          { value: 'salary', label: 'Compensation', icon: <DollarSign className="w-3.5 h-3.5" /> },
        ]}
        fullWidth
        portalTheme="hr"
      />

      {/* Feedback Banner */}
      {feedbackMessage && (
        <div
          className={`p-3.5 rounded-xl border text-xs flex items-start gap-2.5 animate-in fade-in duration-150 ${
            feedbackMessage.type === 'success'
              ? 'bg-emerald-50 text-emerald-800 border-emerald-200'
              : 'bg-rose-50 text-rose-700 border-rose-200'
          }`}
        >
          {feedbackMessage.type === 'success' ? (
            <CheckCircle2 className="w-4 h-4 shrink-0 mt-0.5 text-emerald-600" />
          ) : (
            <AlertCircle className="w-4 h-4 shrink-0 mt-0.5 text-rose-600" />
          )}
          <span className="font-medium">{feedbackMessage.text}</span>
        </div>
      )}

      {/* ─── TAB 1: OVERVIEW ──────────────────────────────────────────────── */}
      {activeTab === 'overview' && (
        <div className="space-y-4">
          {/* Identity & Core Information */}
          <div className="bg-slate-50/70 rounded-2xl border border-slate-200/80 p-4 space-y-3.5">
            <h4 className="text-xs font-semibold text-slate-900 tracking-tight">
              Personnel information
            </h4>
            <div className="grid grid-cols-2 gap-3.5 text-xs">
              <div>
                <span className="text-slate-500 block text-[11px]">Full name</span>
                <span className="font-semibold text-slate-900 mt-0.5 block">{currentEmployee.full_name}</span>
              </div>
              <div>
                <span className="text-slate-500 block text-[11px]">System identifier</span>
                <span className="font-mono font-medium text-slate-900 mt-0.5 block">#{currentEmployee.employee_id}</span>
              </div>
              <div className="col-span-2">
                <span className="text-slate-500 block text-[11px]">Official corporate email</span>
                <span className="font-mono font-medium text-slate-900 flex items-center gap-1.5 mt-0.5">
                  <Mail className="w-3.5 h-3.5 text-slate-400" />
                  {currentEmployee.email}
                </span>
              </div>
              <div>
                <span className="text-slate-500 block text-[11px]">Assigned position</span>
                <span className="font-semibold text-slate-900 flex items-center gap-1 mt-0.5">
                  <Briefcase className="w-3.5 h-3.5 text-slate-400" />
                  {currentEmployee.role_title}
                </span>
              </div>
              <div>
                <span className="text-slate-500 block text-[11px]">Department</span>
                <span className="font-semibold text-slate-900 flex items-center gap-1 mt-0.5">
                  <Building2 className="w-3.5 h-3.5 text-slate-400" />
                  {currentEmployee.department_name}
                </span>
              </div>
              <div>
                <span className="text-slate-500 block text-[11px]">Date onboarded</span>
                <span className="font-mono text-slate-900 flex items-center gap-1 mt-0.5">
                  <Calendar className="w-3.5 h-3.5 text-slate-400" />
                  {new Date(currentEmployee.date_hired).toLocaleDateString()}
                </span>
              </div>
              <div>
                <span className="text-slate-500 block text-[11px]">Current compensation</span>
                <span className="font-mono font-bold text-emerald-600 mt-0.5 block text-sm">
                  {formattedSalary}
                </span>
              </div>
            </div>
          </div>

          {/* Cryptographic Shield & PII Protection */}
          <div className="bg-white rounded-2xl border border-slate-200/80 p-4 space-y-3 shadow-2xs">
            <div className="flex items-center justify-between">
              <h4 className="text-xs font-semibold text-slate-900 tracking-tight flex items-center gap-1.5">
                <ShieldCheck className="w-3.5 h-3.5 text-emerald-600" />
                PII encryption & shielding
              </h4>
              <span className="text-[10px] font-mono font-semibold text-emerald-700 bg-emerald-50 border border-emerald-200 px-2 py-0.5 rounded-full">
                pgcrypto active
              </span>
            </div>
            <div className="space-y-2 text-xs">
              <div className="flex items-center justify-between p-2.5 rounded-xl bg-slate-50 border border-slate-200/60">
                <span className="text-slate-600 font-medium flex items-center gap-1.5">
                  <Lock className="w-3 h-3 text-slate-400" />
                  National ID (Aadhaar / SSN)
                </span>
                <span className="font-mono text-xs text-slate-400 tracking-widest">
                  •••• •••• ••••
                </span>
              </div>
              <div className="flex items-center justify-between p-2.5 rounded-xl bg-slate-50 border border-slate-200/60">
                <span className="text-slate-600 font-medium flex items-center gap-1.5">
                  <Lock className="w-3 h-3 text-slate-400" />
                  Contact credentials
                </span>
                <span className="font-mono text-[11px] text-slate-500">
                  AES-256 Symmetric
                </span>
              </div>
            </div>
            <p className="text-[11px] text-slate-500 leading-relaxed">
              PII attributes are encrypted at rest using PostgreSQL <code className="font-mono text-slate-800 bg-slate-100 px-1 py-0.5 rounded">pgp_sym_encrypt</code> and shielded from unauthorized query endpoints.
            </p>
          </div>

          {/* Audit Chain Link */}
          <div className="bg-white rounded-2xl border border-slate-200/80 p-4 space-y-3 shadow-2xs">
            <div className="flex items-center justify-between">
              <h4 className="text-xs font-semibold text-slate-900 tracking-tight flex items-center gap-1.5">
                <Clock className="w-3.5 h-3.5 text-slate-700" />
                Immutable Audit Trail
              </h4>
              <span className="text-[10px] font-mono font-medium text-emerald-700 bg-emerald-50 border border-emerald-200 px-2 py-0.5 rounded-full">
                SHA-256 Chained
              </span>
            </div>
            <p className="text-xs text-slate-500 leading-relaxed">
              Every insert, profile update, or compensation adjustment on this employee is sealed into the SHA-256 tamper-evident chain by automated database triggers.
            </p>
            <div className="flex items-center justify-between p-2.5 rounded-xl bg-slate-50 border border-slate-200/60 text-xs">
              <span className="text-slate-600 font-medium">Forensic Governance</span>
              <span className="text-[11px] font-medium text-slate-600">
                Independent Auditor Monitored
              </span>
            </div>
          </div>

          {/* Quick Actions */}
          <div className="pt-2 flex items-center gap-2">
            <Button
              variant="accent"
              size="sm"
              portalTheme="hr"
              onClick={() => handleTabChange('salary')}
              className="flex-1"
            >
              Adjust Salary
            </Button>
            <Button
              variant="secondary"
              size="sm"
              portalTheme="hr"
              onClick={() => handleTabChange('edit')}
              className="flex-1"
            >
              Edit Profile
            </Button>
          </div>

          {/* Explicit Danger Zone (F-43) */}
          {currentEmployee.is_active && (
            <div className="pt-3 border-t border-slate-200/80">
              <div className="rounded-2xl border border-rose-200/80 bg-rose-50/50 p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3 shadow-2xs">
                <div>
                  <h5 className="text-xs font-semibold text-rose-950">Deactivate Workforce Personnel</h5>
                  <p className="text-[11px] text-rose-700/90 mt-0.5 leading-relaxed">
                    Revokes credentials and writes an immutable cryptographic event to the audit ledger.
                  </p>
                </div>
                <Button
                  type="button"
                  variant="danger"
                  size="sm"
                  portalTheme="hr"
                  onClick={() => setIsDeactivateModalOpen(true)}
                  disabled={deactivateMutation.isPending}
                  loading={deactivateMutation.isPending}
                  leftIcon={<UserX className="w-3.5 h-3.5" />}
                  className="shrink-0"
                >
                  Deactivate
                </Button>
              </div>
            </div>
          )}
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
          <div className="space-y-4">
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1.5">
                Full legal name
              </label>
              <input
                type="text"
                {...registerProfile('full_name')}
                placeholder="Full Name"
                className="w-full px-3.5 py-2 bg-slate-50/60 hover:bg-slate-50 border border-slate-200 rounded-xl text-sm text-slate-900 focus:bg-white focus:outline-none focus:ring-4 focus:ring-portal-primary/20 focus:border-slate-900 transition-all shadow-2xs"
              />
              {profileErrors.full_name && (
                <p className="mt-1 text-xs text-rose-600 font-medium">{profileErrors.full_name.message}</p>
              )}
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1.5">
                Corporate email address
              </label>
              <input
                type="email"
                {...registerProfile('email')}
                placeholder="workforce@example.com"
                className="w-full px-3.5 py-2 bg-slate-50/60 hover:bg-slate-50 border border-slate-200 rounded-xl text-sm text-slate-900 font-mono focus:bg-white focus:outline-none focus:ring-4 focus:ring-portal-primary/20 focus:border-slate-900 transition-all shadow-2xs"
              />
              {profileErrors.email && (
                <p className="mt-1 text-xs text-rose-600 font-medium">{profileErrors.email.message}</p>
              )}
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1.5">
                Role & department assignment
              </label>
              <select
                {...registerProfile('role_id')}
                className="w-full px-3.5 py-2 bg-slate-50/60 hover:bg-slate-50 border border-slate-200 rounded-xl text-sm text-slate-900 focus:bg-white focus:outline-none focus:ring-4 focus:ring-portal-primary/20 focus:border-slate-900 transition-all shadow-2xs cursor-pointer"
              >
                <option value="">
                  {isRolesLoading ? 'Loading roles from database…' : `Keep Current: ${currentEmployee.role_title || 'Unassigned'} (${currentEmployee.department_name || 'General'})`}
                </option>
                {roles.map((r) => (
                  <option key={r.role_id} value={r.role_id}>
                    {r.title} — {r.department_name}
                  </option>
                ))}
              </select>
              {profileErrors.role_id && (
                <p className="mt-1 text-xs text-rose-600 font-medium">{profileErrors.role_id.message}</p>
              )}
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1.5 flex items-center justify-between">
                <span>Contact information</span>
                <span className="text-[11px] text-slate-500 font-normal">Encrypted payload</span>
              </label>
              <textarea
                {...registerProfile('contact_info')}
                rows={3}
                placeholder="Enter new contact details to update encrypted payload (leave blank to retain current)..."
                className="w-full px-3.5 py-2 bg-slate-50/60 hover:bg-slate-50 border border-slate-200 rounded-xl text-sm text-slate-900 focus:bg-white focus:outline-none focus:ring-4 focus:ring-portal-primary/20 focus:border-slate-900 transition-all shadow-2xs"
              />
              <p className="mt-1.5 text-[11px] text-slate-500 flex items-center gap-1">
                <Lock className="w-3 h-3 text-emerald-600 shrink-0" />
                Payload is symmetrically encrypted via PostgreSQL pgcrypto before storage.
              </p>
              {profileErrors.contact_info && (
                <p className="mt-1 text-xs text-rose-600 font-medium">{profileErrors.contact_info.message}</p>
              )}
            </div>
          </div>

          <div className="pt-3 border-t border-slate-200 flex items-center justify-end gap-2.5">
            <Button
              variant="secondary"
              size="sm"
              portalTheme="hr"
              onClick={() => handleTabChange('overview')}
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
              className="bg-slate-900 hover:bg-slate-800 text-white font-medium shadow-xs"
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
          <div className="bg-slate-50/70 rounded-2xl border border-slate-200/80 p-4 space-y-1.5">
            <span className="text-xs font-semibold text-slate-500 tracking-tight">
              Current annual compensation
            </span>
            <div className="flex items-baseline gap-2">
              <span className="text-2xl font-bold text-slate-900 font-mono tabular-nums">
                {formattedSalary}
              </span>
              <span className="text-xs text-slate-500">per annum</span>
            </div>
            <p className="text-[11px] text-slate-500">
              Validated against role benchmarks for <span className="font-semibold text-slate-900">{currentEmployee.role_title}</span>.
            </p>
          </div>

          <div className="space-y-4">
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1.5">
                New annual compensation (INR)
              </label>
              <div className="relative">
                <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-sm font-semibold text-slate-400">
                  ₹
                </div>
                <input
                  type="number"
                  step="1"
                  {...registerSalary('amount')}
                  placeholder="e.g. 95000"
                  className="w-full pl-8 pr-3.5 py-2 bg-slate-50/60 hover:bg-slate-50 border border-slate-200 rounded-xl text-sm text-slate-900 font-mono focus:bg-white focus:outline-none focus:ring-4 focus:ring-portal-success/20 focus:border-emerald-600 transition-all tabular-nums shadow-2xs"
                />
              </div>
              {salaryErrors.amount && (
                <p className="mt-1 text-xs text-rose-600 font-medium">{salaryErrors.amount.message}</p>
              )}
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1.5">
                Effective adjustment date
              </label>
              <div className="relative">
                <input
                  type="date"
                  {...registerSalary('effective_date')}
                  className="w-full px-3.5 py-2 bg-slate-50/60 hover:bg-slate-50 border border-slate-200 rounded-xl text-sm text-slate-900 font-mono focus:bg-white focus:outline-none focus:ring-4 focus:ring-portal-success/20 focus:border-emerald-600 transition-all shadow-2xs"
                />
              </div>
              {salaryErrors.effective_date && (
                <p className="mt-1 text-xs text-rose-600 font-medium">{salaryErrors.effective_date.message}</p>
              )}
            </div>
          </div>

          <div className="p-3.5 rounded-xl bg-emerald-50/70 border border-emerald-200/80 text-xs text-slate-700 space-y-1">
            <span className="font-semibold flex items-center gap-1.5 text-emerald-800 text-[11px]">
              <ShieldCheck className="w-3.5 h-3.5 text-emerald-600" />
              Automated Checkpoint Trigger
            </span>
            <p className="text-slate-600 text-[11px] leading-relaxed">
              Recording this adjustment creates an immutable row in <code className="font-mono text-slate-900 bg-white/70 px-1 py-0.5 rounded">salary_history</code> and triggers an automatic SHA-256 block in <code className="font-mono text-slate-900 bg-white/70 px-1 py-0.5 rounded">audit_log</code>.
            </p>
          </div>

          <div className="pt-3 border-t border-slate-200 flex items-center justify-end gap-2.5">
            <Button
              variant="secondary"
              size="sm"
              portalTheme="hr"
              onClick={() => handleTabChange('overview')}
              disabled={isSalarySubmitting}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              variant="accent"
              size="sm"
              portalTheme="hr"
              disabled={isSalarySubmitting}
              loading={isSalarySubmitting}
            >
              Record Salary Adjustment
            </Button>
          </div>
        </form>
      )}

      {/* Styled Deactivation Modal (F-37) */}
      {isDeactivateModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/50 backdrop-blur-xs animate-in fade-in duration-150">
          <div className="bg-white rounded-2xl border border-slate-200 shadow-xl max-w-md w-full p-6 space-y-4 animate-modal-enter">
            <div className="flex items-center gap-3 text-rose-600">
              <div className="w-10 h-10 rounded-xl bg-rose-100 flex items-center justify-center shrink-0">
                <UserX className="w-5 h-5" />
              </div>
              <div>
                <h3 className="text-base font-semibold text-slate-900">Deactivate Personnel</h3>
                <p className="text-xs text-slate-500">Immutable ledger transaction</p>
              </div>
            </div>
            <p className="text-xs text-slate-600 leading-relaxed">
              Are you sure you want to deactivate <strong className="text-slate-900">{currentEmployee.full_name}</strong> (#{currentEmployee.employee_id})? Their active system access will be terminated immediately.
            </p>
            <div className="flex items-center justify-end gap-2.5 pt-2">
              <Button
                type="button"
                variant="secondary"
                size="sm"
                portalTheme="hr"
                onClick={() => setIsDeactivateModalOpen(false)}
                disabled={deactivateMutation.isPending}
              >
                Cancel
              </Button>
              <Button
                type="button"
                variant="danger"
                size="sm"
                portalTheme="hr"
                onClick={() => {
                  deactivateMutation.mutate();
                  setIsDeactivateModalOpen(false);
                }}
                disabled={deactivateMutation.isPending}
                loading={deactivateMutation.isPending}
              >
                Confirm Deactivation
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Discard Unsaved Changes Modal (F-40, F-124) */}
      {showDiscardConfirm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/50 backdrop-blur-xs animate-in fade-in duration-150">
          <div className="bg-white rounded-2xl border border-slate-200 shadow-xl max-w-sm w-full p-5 space-y-3 animate-modal-enter">
            <h3 className="text-sm font-semibold text-slate-900">Discard unsaved changes?</h3>
            <p className="text-xs text-slate-500 leading-relaxed">
              You have modified input fields that have not been saved. If you leave now, your changes will be lost.
            </p>
            <div className="flex items-center justify-end gap-2 pt-2">
              <Button
                type="button"
                variant="secondary"
                size="sm"
                portalTheme="hr"
                onClick={() => {
                  setShowDiscardConfirm(false);
                  setPendingAction(null);
                }}
              >
                Keep Editing
              </Button>
              <Button
                type="button"
                variant="danger"
                size="sm"
                portalTheme="hr"
                onClick={() => {
                  setShowDiscardConfirm(false);
                  resetProfile();
                  resetSalary();
                  if (pendingAction?.type === 'tab') {
                    setActiveTab(pendingAction.tab);
                    setFeedbackMessage(null);
                  } else if (pendingAction?.type === 'close') {
                    onClose();
                  }
                  setPendingAction(null);
                }}
              >
                Discard Changes
              </Button>
            </div>
          </div>
        </div>
      )}
    </DetailSheet>
  );
}
