import { useState, useEffect } from 'react';
import { createPortal } from 'react-dom';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import * as z from 'zod';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useAuth } from '@clerk/clerk-react';
import { fetchWithAuth, ApiError } from '../../lib/api';
import { fetchRoles, type RoleItem } from '../../services/auditService';
import { X, Loader2 } from 'lucide-react';

const employeeEditSchema = z.object({
  full_name: z.string().min(2, 'Name must be at least 2 characters').max(255).optional().or(z.literal('')),
  email: z.string().email('Invalid email address').optional().or(z.literal('')),
  role_id: z.coerce.number().int().positive('Role ID must be a valid number').optional().or(z.nan()),
  contact_info: z.string().max(500).optional(),
});

type EmployeeEditFormData = z.infer<typeof employeeEditSchema>;

interface EmployeeEditFormProps {
  employee: {
    employee_id: number;
    full_name: string;
    email: string;
    role_title?: string;
  };
  onClose: () => void;
}

export default function EmployeeEditForm({ employee, onClose }: EmployeeEditFormProps) {
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
    formState: { errors, isSubmitting, isDirty },
  } = useForm<EmployeeEditFormData>({
    resolver: zodResolver(employeeEditSchema),
    defaultValues: {
      full_name: employee.full_name,
      email: employee.email,
      contact_info: '', // We don't have it in the list view, so we leave it blank. Will only update if filled.
    },
  });

  const mutation = useMutation({
    mutationFn: (data: EmployeeEditFormData) => {
      // Clean up payload (remove undefined/empty strings that shouldn't be sent)
      const payload: Record<string, any> = {};
      if (data.full_name && data.full_name !== employee.full_name) payload.full_name = data.full_name;
      if (data.email && data.email !== employee.email) payload.email = data.email;
      if (data.role_id && !isNaN(data.role_id)) payload.role_id = data.role_id;
      if (data.contact_info) payload.contact_info = data.contact_info;

      if (Object.keys(payload).length === 0) {
        return Promise.resolve(null); // No changes
      }

      return fetchWithAuth(`/employees/${employee.employee_id}`, {
        method: 'PATCH',
        body: JSON.stringify(payload),
      }, getToken);
    },
    onSuccess: (res) => {
      if (res !== null) {
        queryClient.invalidateQueries({ queryKey: ['employees'] });
      }
      onClose();
    },
    onError: (error) => {
      if (error instanceof ApiError) {
        setGlobalError(error.message);
      } else {
        setGlobalError('An unexpected error occurred. Please try again.');
      }
    },
  });

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [onClose]);

  const onSubmit = (data: EmployeeEditFormData) => {
    setGlobalError(null);
    mutation.mutate(data);
  };

  return createPortal(
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-6 bg-slate-900/60 backdrop-blur-xs overflow-y-auto"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-2xl max-h-[90vh] flex flex-col overflow-hidden border border-slate-200 animate-modal-enter my-auto">
        <div className="px-6 py-4 border-b border-slate-100 flex justify-between items-center bg-slate-50/80 shrink-0">
          <div>
            <h2 className="text-lg font-bold text-slate-900">Edit Employee Profile</h2>
            <p className="text-xs text-slate-500">Updating Employee ID: #{employee.employee_id} • Modifications hashed into audit trail</p>
          </div>
          <button 
            type="button"
            onClick={onClose}
            className="btn-press-sm text-slate-400 hover:text-slate-600 bg-white hover:bg-slate-100 border border-slate-200/80 rounded-lg p-1.5 cursor-pointer shadow-2xs"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        <form onSubmit={handleSubmit(onSubmit)} className="flex flex-col flex-1 overflow-hidden">
          <div className="p-6 overflow-y-auto flex-1 space-y-5">
            {globalError && (
              <div className="p-4 rounded-lg bg-red-50 border border-red-100 text-sm text-red-600 flex items-start">
                <svg className="w-5 h-5 mr-2 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
                {globalError}
              </div>
            )}

            <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
              {/* Full Name */}
              <div className="col-span-2 md:col-span-1">
                <label className="block text-sm font-medium text-slate-700 mb-1">Full Name</label>
                <input
                  type="text"
                  {...register('full_name')}
                  className={`w-full px-3 py-2 border rounded-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/50 transition-colors ${errors.full_name ? 'border-red-300 focus:border-red-500' : 'border-slate-300 focus:border-indigo-500'}`}
                />
                {errors.full_name && <p className="mt-1 text-xs text-red-500">{errors.full_name.message}</p>}
              </div>

              {/* Email */}
              <div className="col-span-2 md:col-span-1">
                <label className="block text-sm font-medium text-slate-700 mb-1">Email Address</label>
                <input
                  type="email"
                  {...register('email')}
                  className={`w-full px-3 py-2 border rounded-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/50 transition-colors ${errors.email ? 'border-red-300 focus:border-red-500' : 'border-slate-300 focus:border-indigo-500'}`}
                />
                {errors.email && <p className="mt-1 text-xs text-red-500">{errors.email.message}</p>}
              </div>

              {/* Role ID */}
              <div className="col-span-2 md:col-span-1">
                <label className="block text-sm font-medium text-slate-700 mb-1">Update Role</label>
                <select
                  {...register('role_id')}
                  className={`w-full px-3 py-2 border rounded-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/50 transition-colors bg-white ${errors.role_id ? 'border-red-300 focus:border-red-500' : 'border-slate-300 focus:border-indigo-500'}`}
                >
                  <option value="">{isRolesLoading ? 'Loading roles...' : `Keep current: ${employee.role_title || 'Unassigned'}`}</option>
                  {roles.map((r) => (
                    <option key={r.role_id} value={r.role_id}>
                      {r.title} ({r.department_name})
                    </option>
                  ))}
                </select>
                {errors.role_id && <p className="mt-1 text-xs text-red-500">{errors.role_id.message}</p>}
              </div>

              {/* Contact Info (Encrypted payload) */}
              <div className="col-span-2">
                <label className="block text-sm font-medium text-slate-700 mb-1">Update Contact Information</label>
                <textarea
                  {...register('contact_info')}
                  rows={2}
                  className={`w-full px-3 py-2 border rounded-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/50 transition-colors ${errors.contact_info ? 'border-red-300 focus:border-red-500' : 'border-slate-300 focus:border-indigo-500'}`}
                  placeholder="Enter new contact info to overwrite..."
                />
                <p className="mt-1 text-xs flex items-center text-slate-500">
                  <svg className="w-3 h-3 mr-1 text-emerald-500" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" /></svg>
                  Encrypted at rest. Leave blank to keep existing.
                </p>
                {errors.contact_info && <p className="mt-1 text-xs text-red-500">{errors.contact_info.message}</p>}
              </div>
            </div>
          </div>

          <div className="px-6 py-4 border-t border-slate-100 bg-slate-50/80 flex justify-end space-x-3 shrink-0">
            <button
              type="button"
              onClick={onClose}
              className="btn-press px-4 py-2 text-xs font-semibold text-slate-700 bg-white border border-slate-300 rounded-lg shadow-2xs hover:bg-slate-50 cursor-pointer"
              disabled={isSubmitting}
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isSubmitting || !isDirty}
              className="btn-press inline-flex items-center px-4 py-2 text-xs font-semibold text-white bg-indigo-600 hover:bg-indigo-500 border border-transparent rounded-lg shadow-xs cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isSubmitting ? (
                <>
                  <Loader2 className="w-4 h-4 mr-2 animate-fast-spin" />
                  Saving Changes…
                </>
              ) : (
                'Save Changes'
              )}
            </button>
          </div>
        </form>
      </div>
    </div>,
    document.body
  );
}
