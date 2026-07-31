import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import * as z from 'zod';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useAuth } from '@clerk/clerk-react';
import { fetchWithAuth, ApiError } from '../../lib/api';
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

  const onSubmit = (data: EmployeeEditFormData) => {
    setGlobalError(null);
    mutation.mutate(data);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/50 backdrop-blur-sm animate-in fade-in duration-200">
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-2xl overflow-hidden border border-slate-200 animate-in zoom-in-95 duration-200">
        <div className="px-6 py-4 border-b border-slate-100 flex justify-between items-center bg-slate-50/50">
          <div>
             <h2 className="text-xl font-semibold text-slate-800">Edit Employee</h2>
             <p className="text-sm text-slate-500">Updating ID: {employee.employee_id}</p>
          </div>
          <button 
            onClick={onClose}
            className="text-slate-400 hover:text-slate-600 transition-colors bg-white hover:bg-slate-100 rounded-full p-1"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="p-6">
          {globalError && (
            <div className="mb-6 p-4 rounded-lg bg-red-50 border border-red-100 text-sm text-red-600 flex items-start">
              <svg className="w-5 h-5 mr-2 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
              {globalError}
            </div>
          )}

          <form onSubmit={handleSubmit(onSubmit)} className="space-y-5">
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
                <label className="block text-sm font-medium text-slate-700 mb-1">Update Role ID</label>
                <input
                  type="number"
                  {...register('role_id')}
                  className={`w-full px-3 py-2 border rounded-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/50 transition-colors ${errors.role_id ? 'border-red-300 focus:border-red-500' : 'border-slate-300 focus:border-indigo-500'}`}
                  placeholder="Leave blank to keep current"
                />
                <p className="mt-1 text-xs text-slate-400">Current: {employee.role_title}</p>
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

            <div className="pt-4 mt-6 border-t border-slate-100 flex justify-end space-x-3">
              <button
                type="button"
                onClick={onClose}
                className="px-4 py-2 text-sm font-medium text-slate-700 bg-white border border-slate-300 rounded-lg shadow-sm hover:bg-slate-50 focus:outline-none focus:ring-2 focus:ring-indigo-500/50 transition-colors"
                disabled={isSubmitting}
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={isSubmitting || !isDirty}
                className="inline-flex items-center px-4 py-2 text-sm font-medium text-white bg-indigo-600 border border-transparent rounded-lg shadow-sm hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-indigo-500/50 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                {isSubmitting ? (
                  <>
                    <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                    Saving...
                  </>
                ) : (
                  'Save Changes'
                )}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
}
