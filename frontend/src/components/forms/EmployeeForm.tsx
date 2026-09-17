import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import * as z from 'zod';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useAuth } from '@clerk/clerk-react';
import { fetchWithAuth, ApiError } from '../../lib/api';
import { fetchRoles, type RoleItem } from '../../services/auditService';
import { Lock, ShieldCheck, AlertCircle } from 'lucide-react';
import { DetailSheet } from '../common/DetailSheet';
import { Button } from '../common/Button';

const employeeSchema = z.object({
  full_name: z.string().min(2, 'Name must be at least 2 characters').max(255),
  email: z.string().email('Invalid email address'),
  role_id: z.coerce.number().int().positive('Please select a valid role'),
  national_id: z.string().min(5, 'National ID is required').max(255),
  contact_info: z.string().min(5, 'Contact info is required').max(500),
  date_hired: z.string().refine((val) => !isNaN(Date.parse(val)), {
    message: 'Invalid date format',
  }),
  salary: z.coerce.number().positive('Salary must be greater than 0'),
});

type EmployeeFormData = z.infer<typeof employeeSchema>;

export interface EmployeeFormProps {
  onClose: () => void;
}

export default function EmployeeForm({ onClose }: EmployeeFormProps) {
  const { getToken } = useAuth();
  const queryClient = useQueryClient();
  const [globalError, setGlobalError] = useState<string | null>(null);

  const { data: roles = [], isLoading: isRolesLoading } = useQuery<RoleItem[]>({
    queryKey: ['roles'],
    queryFn: () => fetchRoles(() => getToken()),
    staleTime: 300000,
    refetchInterval: false,
  });

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<EmployeeFormData>({
    resolver: zodResolver(employeeSchema),
    defaultValues: {
      date_hired: new Date().toISOString().split('T')[0],
    },
  });

  const mutation = useMutation({
    mutationFn: (data: EmployeeFormData) =>
      fetchWithAuth(
        '/employees',
        {
          method: 'POST',
          body: JSON.stringify(data),
        },
        getToken
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['employees'] });
      queryClient.invalidateQueries({ queryKey: ['dashboardStats'] });
      queryClient.invalidateQueries({ queryKey: ['audit-chain'] });
      onClose();
    },
    onError: (error) => {
      if (error instanceof ApiError) {
        setGlobalError(error.message);
      } else {
        setGlobalError('An unexpected error occurred while adding the employee.');
      }
    },
  });

  const onSubmit = (data: EmployeeFormData) => {
    setGlobalError(null);
    mutation.mutate(data);
  };

  return (
    <DetailSheet
      isOpen={true}
      onClose={onClose}
      portalTheme="hr"
      mode="drawer"
      widthClass="w-full sm:w-[500px] lg:w-[560px]"
      title="Register Personnel"
      subtitle="Atomic workforce onboarding with PostgreSQL trigger chain sealing"
      headerBadge={
        <span className="text-[10px] font-mono font-bold text-linear-success bg-linear-success/10 border border-linear-success/20 px-2 py-0.5 rounded">
          INSERT
        </span>
      }
      footer={
        <div className="flex items-center justify-end gap-2">
          <Button
            variant="secondary"
            size="sm"
            portalTheme="hr"
            onClick={onClose}
            disabled={isSubmitting}
          >
            Cancel
          </Button>
          <Button
            type="submit"
            form="employee-create-form"
            variant="primary"
            size="sm"
            portalTheme="hr"
            disabled={isSubmitting}
            loading={isSubmitting}
          >
            Complete Registration
          </Button>
        </div>
      }
    >
      <form id="employee-create-form" onSubmit={handleSubmit(onSubmit)} className="space-y-4">
        {globalError && (
          <div className="p-3 rounded-lg bg-grafana-orange/10 border border-grafana-orange/30 text-xs text-grafana-orange flex items-start gap-2">
            <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
            <span className="font-medium">{globalError}</span>
          </div>
        )}

        <div className="space-y-3.5">
          {/* Full Name */}
          <div>
            <label className="block text-xs font-bold text-grafana-ink uppercase tracking-wider font-mono mb-1.5">
              Full Legal Name
            </label>
            <input
              type="text"
              {...register('full_name')}
              placeholder="e.g. Sarah Jenkins"
              className={`w-full px-3 py-2 border rounded-lg text-sm bg-white text-grafana-ink focus:outline-none focus:ring-2 focus:ring-grafana-orange/20 transition-colors ${
                errors.full_name ? 'border-grafana-orange' : 'border-grafana-border focus:border-grafana-orange'
              }`}
            />
            {errors.full_name && (
              <p className="mt-1 text-xs text-grafana-orange">{errors.full_name.message}</p>
            )}
          </div>

          {/* Email */}
          <div>
            <label className="block text-xs font-bold text-grafana-ink uppercase tracking-wider font-mono mb-1.5">
              Corporate Email Address
            </label>
            <input
              type="email"
              {...register('email')}
              placeholder="s.jenkins@enterprise.internal"
              className={`w-full px-3 py-2 border rounded-lg text-sm bg-white text-grafana-ink font-mono focus:outline-none focus:ring-2 focus:ring-grafana-orange/20 transition-colors ${
                errors.email ? 'border-grafana-orange' : 'border-grafana-border focus:border-grafana-orange'
              }`}
            />
            {errors.email && (
              <p className="mt-1 text-xs text-grafana-orange">{errors.email.message}</p>
            )}
          </div>

          {/* Role */}
          <div>
            <label className="block text-xs font-bold text-grafana-ink uppercase tracking-wider font-mono mb-1.5">
              Assigned Position & Department
            </label>
            <select
              {...register('role_id')}
              className={`w-full px-3 py-2 border rounded-lg text-sm bg-white text-grafana-ink focus:outline-none focus:ring-2 focus:ring-grafana-orange/20 transition-colors ${
                errors.role_id ? 'border-grafana-orange' : 'border-grafana-border focus:border-grafana-orange'
              }`}
            >
              <option value="">{isRolesLoading ? 'Loading roles...' : 'Select assigned role…'}</option>
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
            {errors.role_id && (
              <p className="mt-1 text-xs text-grafana-orange">{errors.role_id.message}</p>
            )}
          </div>

          {/* Salary */}
          <div>
            <label className="block text-xs font-bold text-grafana-ink uppercase tracking-wider font-mono mb-1.5">
              Base Compensation (Annual INR)
            </label>
            <div className="relative">
              <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-sm font-semibold text-grafana-neutral">
                ₹
              </div>
              <input
                type="number"
                step="1"
                {...register('salary')}
                placeholder="e.g. 85000"
                className={`w-full pl-8 pr-3 py-2 border rounded-lg text-sm bg-white text-grafana-ink font-mono tabular-nums focus:outline-none focus:ring-2 focus:ring-grafana-orange/20 transition-colors ${
                  errors.salary ? 'border-grafana-orange' : 'border-grafana-border focus:border-grafana-orange'
                }`}
              />
            </div>
            {errors.salary && (
              <p className="mt-1 text-xs text-grafana-orange">{errors.salary.message}</p>
            )}
          </div>

          {/* National ID */}
          <div>
            <label className="block text-xs font-bold text-grafana-ink uppercase tracking-wider font-mono mb-1.5">
              National Identification (Aadhar / SSN)
            </label>
            <input
              type="text"
              {...register('national_id')}
              placeholder="e.g. 9876-5432-1098"
              className={`w-full px-3 py-2 border rounded-lg text-sm bg-white text-grafana-ink font-mono focus:outline-none focus:ring-2 focus:ring-grafana-orange/20 transition-colors ${
                errors.national_id ? 'border-grafana-orange' : 'border-grafana-border focus:border-grafana-orange'
              }`}
            />
            <p className="mt-1 text-[11px] text-grafana-neutral flex items-center gap-1">
              <Lock className="w-3 h-3 text-linear-success" />
              Symmetrically encrypted with PostgreSQL pgcrypto before commit.
            </p>
            {errors.national_id && (
              <p className="mt-1 text-xs text-grafana-orange">{errors.national_id.message}</p>
            )}
          </div>

          {/* Date Hired */}
          <div>
            <label className="block text-xs font-bold text-grafana-ink uppercase tracking-wider font-mono mb-1.5">
              Hire Date
            </label>
            <input
              type="date"
              {...register('date_hired')}
              className={`w-full px-3 py-2 border rounded-lg text-sm bg-white text-grafana-ink font-mono focus:outline-none focus:ring-2 focus:ring-grafana-orange/20 transition-colors ${
                errors.date_hired ? 'border-grafana-orange' : 'border-grafana-border focus:border-grafana-orange'
              }`}
            />
            {errors.date_hired && (
              <p className="mt-1 text-xs text-grafana-orange">{errors.date_hired.message}</p>
            )}
          </div>

          {/* Contact Info */}
          <div>
            <label className="block text-xs font-bold text-grafana-ink uppercase tracking-wider font-mono mb-1.5">
              Contact & Emergency Information
            </label>
            <textarea
              {...register('contact_info')}
              rows={3}
              placeholder="Residential address, phone, emergency contacts..."
              className={`w-full px-3 py-2 border rounded-lg text-sm bg-white text-grafana-ink focus:outline-none focus:ring-2 focus:ring-grafana-orange/20 transition-colors ${
                errors.contact_info ? 'border-grafana-orange' : 'border-grafana-border focus:border-grafana-orange'
              }`}
            />
            <p className="mt-1 text-[11px] text-grafana-neutral flex items-center gap-1">
              <ShieldCheck className="w-3 h-3 text-linear-success" />
              Stored in encrypted BYTEA column; never logged in plaintext.
            </p>
            {errors.contact_info && (
              <p className="mt-1 text-xs text-grafana-orange">{errors.contact_info.message}</p>
            )}
          </div>
        </div>
      </form>
    </DetailSheet>
  );
}
