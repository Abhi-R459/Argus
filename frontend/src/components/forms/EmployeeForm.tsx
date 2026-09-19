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
      widthClass="w-full sm:w-[520px] lg:w-[580px]"
      title="Register Personnel"
      subtitle="Onboard a new employee with verified credentials, role, and initial compensation"
      headerBadge={
        <span className="text-[11px] font-medium text-emerald-700 bg-emerald-50 border border-emerald-200/80 px-2.5 py-0.5 rounded-full">
          New Profile
        </span>
      }
      footer={
        <div className="flex items-center justify-end gap-2.5">
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
            className="bg-slate-900 hover:bg-slate-800 text-white font-medium shadow-xs"
          >
            Complete Registration
          </Button>
        </div>
      }
    >
      <form id="employee-create-form" onSubmit={handleSubmit(onSubmit)} className="space-y-4">
        {globalError && (
          <div className="p-3.5 rounded-xl bg-rose-50 border border-rose-200 text-xs text-rose-700 flex items-start gap-2.5">
            <AlertCircle className="w-4 h-4 shrink-0 mt-0.5 text-rose-600" />
            <span className="font-medium">{globalError}</span>
          </div>
        )}

        <div className="space-y-4">
          {/* Full Name & Email */}
          <div className="space-y-3.5">
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1.5">
                Full legal name
              </label>
              <input
                type="text"
                {...register('full_name')}
                placeholder="e.g. Sarah Jenkins"
                className={`w-full px-3.5 py-2 bg-slate-50/60 hover:bg-slate-50 border rounded-xl text-sm text-slate-900 placeholder:text-slate-400 focus:bg-white focus:outline-none focus:ring-4 focus:ring-slate-900/5 focus:border-slate-900 transition-all shadow-2xs ${
                  errors.full_name ? 'border-rose-400 focus:border-rose-500 focus:ring-rose-500/10' : 'border-slate-200'
                }`}
              />
              {errors.full_name && (
                <p className="mt-1 text-xs text-rose-600 font-medium">{errors.full_name.message}</p>
              )}
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1.5">
                Corporate email address
              </label>
              <input
                type="email"
                {...register('email')}
                placeholder="s.jenkins@enterprise.internal"
                className={`w-full px-3.5 py-2 bg-slate-50/60 hover:bg-slate-50 border rounded-xl text-sm text-slate-900 font-mono placeholder:text-slate-400 focus:bg-white focus:outline-none focus:ring-4 focus:ring-slate-900/5 focus:border-slate-900 transition-all shadow-2xs ${
                  errors.email ? 'border-rose-400 focus:border-rose-500 focus:ring-rose-500/10' : 'border-slate-200'
                }`}
              />
              {errors.email && (
                <p className="mt-1 text-xs text-rose-600 font-medium">{errors.email.message}</p>
              )}
            </div>
          </div>

          {/* Role Selection */}
          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1.5">
              Assigned role & department
            </label>
            <select
              {...register('role_id')}
              className={`w-full px-3.5 py-2 bg-slate-50/60 hover:bg-slate-50 border rounded-xl text-sm text-slate-900 focus:bg-white focus:outline-none focus:ring-4 focus:ring-slate-900/5 focus:border-slate-900 transition-all shadow-2xs cursor-pointer ${
                errors.role_id ? 'border-rose-400 focus:border-rose-500 focus:ring-rose-500/10' : 'border-slate-200'
              }`}
            >
              <option value="">{isRolesLoading ? 'Loading roles from database...' : 'Select position…'}</option>
              {roles.map((r) => (
                <option key={r.role_id} value={r.role_id}>
                  {r.title} — {r.department_name}
                </option>
              ))}
            </select>
            {errors.role_id && (
              <p className="mt-1 text-xs text-rose-600 font-medium">{errors.role_id.message}</p>
            )}
          </div>

          {/* Compensation & Date Hired side-by-side */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5">
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1.5">
                Annual compensation (INR)
              </label>
              <div className="relative">
                <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-sm font-semibold text-slate-400">
                  ₹
                </div>
                <input
                  type="number"
                  step="1"
                  {...register('salary')}
                  placeholder="e.g. 85000"
                  className={`w-full pl-8 pr-3.5 py-2 bg-slate-50/60 hover:bg-slate-50 border rounded-xl text-sm text-slate-900 font-mono tabular-nums focus:bg-white focus:outline-none focus:ring-4 focus:ring-slate-900/5 focus:border-slate-900 transition-all shadow-2xs ${
                    errors.salary ? 'border-rose-400 focus:border-rose-500 focus:ring-rose-500/10' : 'border-slate-200'
                  }`}
                />
              </div>
              {errors.salary && (
                <p className="mt-1 text-xs text-rose-600 font-medium">{errors.salary.message}</p>
              )}
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1.5">
                Hire date
              </label>
              <input
                type="date"
                {...register('date_hired')}
                className={`w-full px-3.5 py-2 bg-slate-50/60 hover:bg-slate-50 border rounded-xl text-sm text-slate-900 font-mono focus:bg-white focus:outline-none focus:ring-4 focus:ring-slate-900/5 focus:border-slate-900 transition-all shadow-2xs ${
                  errors.date_hired ? 'border-rose-400 focus:border-rose-500 focus:ring-rose-500/10' : 'border-slate-200'
                }`}
              />
              {errors.date_hired && (
                <p className="mt-1 text-xs text-rose-600 font-medium">{errors.date_hired.message}</p>
              )}
            </div>
          </div>

          {/* National ID (Encrypted) */}
          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1.5 flex items-center justify-between">
              <span>National ID (Aadhaar / SSN)</span>
              <span className="text-[11px] text-emerald-700 font-normal flex items-center gap-1 font-sans">
                <Lock className="w-3 h-3 text-emerald-600" />
                pgcrypto encrypted
              </span>
            </label>
            <input
              type="text"
              {...register('national_id')}
              placeholder="e.g. 9876-5432-1098"
              className={`w-full px-3.5 py-2 bg-slate-50/60 hover:bg-slate-50 border rounded-xl text-sm text-slate-900 font-mono placeholder:text-slate-400 focus:bg-white focus:outline-none focus:ring-4 focus:ring-slate-900/5 focus:border-slate-900 transition-all shadow-2xs ${
                errors.national_id ? 'border-rose-400 focus:border-rose-500 focus:ring-rose-500/10' : 'border-slate-200'
              }`}
            />
            {errors.national_id && (
              <p className="mt-1 text-xs text-rose-600 font-medium">{errors.national_id.message}</p>
            )}
          </div>

          {/* Contact Info */}
          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1.5 flex items-center justify-between">
              <span>Contact & emergency information</span>
              <span className="text-[11px] text-slate-500 font-normal">Encrypted payload</span>
            </label>
            <textarea
              {...register('contact_info')}
              rows={3}
              placeholder="Residential address, contact numbers, emergency contacts..."
              className={`w-full px-3.5 py-2 bg-slate-50/60 hover:bg-slate-50 border rounded-xl text-sm text-slate-900 placeholder:text-slate-400 focus:bg-white focus:outline-none focus:ring-4 focus:ring-slate-900/5 focus:border-slate-900 transition-all shadow-2xs ${
                errors.contact_info ? 'border-rose-400 focus:border-rose-500 focus:ring-rose-500/10' : 'border-slate-200'
              }`}
            />
            <p className="mt-1.5 text-[11px] text-slate-500 flex items-center gap-1">
              <ShieldCheck className="w-3 h-3 text-emerald-600 shrink-0" />
              Payload is encrypted at rest via pgcrypto and recorded to the immutable ledger.
            </p>
            {errors.contact_info && (
              <p className="mt-1 text-xs text-rose-600 font-medium">{errors.contact_info.message}</p>
            )}
          </div>
        </div>
      </form>
    </DetailSheet>
  );
}
