import { useState, useEffect } from 'react';
import { createPortal } from 'react-dom';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import * as z from 'zod';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useAuth } from '@clerk/clerk-react';
import { fetchWithAuth, ApiError } from '../../lib/api';
import { X, DollarSign } from 'lucide-react';
import { Button } from '../common/Button';

const salarySchema = z.object({
  amount: z.coerce.number().positive('Salary must be greater than 0'),
  effective_date: z.string().refine((val) => !isNaN(Date.parse(val)), {
    message: 'Invalid date format',
  }),
});

type SalaryFormData = z.infer<typeof salarySchema>;

interface SalaryFormProps {
  employee: {
    employee_id: number;
    full_name: string;
    salary: number | null;
  };
  onClose: () => void;
}

export default function SalaryForm({ employee, onClose }: SalaryFormProps) {
  const { getToken } = useAuth();
  const queryClient = useQueryClient();
  const [globalError, setGlobalError] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<SalaryFormData>({
    resolver: zodResolver(salarySchema),
    defaultValues: {
      amount: employee.salary ? employee.salary : undefined,
      effective_date: new Date().toISOString().split('T')[0],
    },
  });

  const mutation = useMutation({
    mutationFn: (data: SalaryFormData) =>
      fetchWithAuth(`/employees/${employee.employee_id}/salary`, {
        method: 'POST',
        body: JSON.stringify(data),
      }, getToken),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['employees'] });
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

  const onSubmit = (data: SalaryFormData) => {
    setGlobalError(null);
    mutation.mutate(data);
  };

  return createPortal(
    <div
      className="portal-hr fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-6 bg-black/60 backdrop-blur-xs overflow-y-auto"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="bg-white rounded-xl shadow-2xl w-full max-w-md max-h-[90vh] flex flex-col overflow-hidden border border-grafana-border animate-modal-enter my-auto">
        <div className="px-6 py-4 border-b border-grafana-border flex justify-between items-center bg-grafana-surface shrink-0">
          <div className="flex items-center">
            <div className="bg-linear-success/10 text-linear-success border border-linear-success/20 p-2 rounded-lg mr-3 shadow-2xs">
              <DollarSign className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-base font-bold text-grafana-ink">Update Salary Record</h2>
              <p className="text-xs text-grafana-neutral">{employee.full_name} • Triggers DB validation</p>
            </div>
          </div>
          <Button 
            variant="secondary"
            size="icon-sm"
            portalTheme="hr"
            onClick={onClose}
            title="Close dialog"
            aria-label="Close dialog"
            leftIcon={<X className="w-4 h-4" />}
          />
        </div>

        <form onSubmit={handleSubmit(onSubmit)} className="flex flex-col flex-1 overflow-hidden">
          <div className="p-6 overflow-y-auto flex-1 space-y-5">
            {globalError && (
              <div className="p-4 rounded-lg bg-grafana-orange/10 border border-grafana-orange/30 text-sm text-grafana-orange flex items-start">
                <svg className="w-5 h-5 mr-2 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
                {globalError}
              </div>
            )}

            <div>
              <label className="block text-sm font-medium text-grafana-ink mb-1">New Salary Amount</label>
              <div className="relative">
                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                  <span className="text-grafana-neutral sm:text-sm">₹</span>
                </div>
                <input
                  type="number"
                  step="0.01"
                  {...register('amount')}
                  className={`w-full pl-7 pr-3 py-2 border rounded-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-grafana-orange/20 transition-colors ${errors.amount ? 'border-grafana-orange focus:border-grafana-orange' : 'border-grafana-border focus:border-grafana-orange text-grafana-ink placeholder-grafana-neutral/50'}`}
                  placeholder="0.00"
                />
              </div>
              {errors.amount && <p className="mt-1 text-xs text-grafana-orange">{errors.amount.message}</p>}
            </div>

            <div>
              <label className="block text-sm font-medium text-grafana-ink mb-1">Effective Date</label>
              <input
                type="date"
                {...register('effective_date')}
                className={`w-full px-3 py-2 border rounded-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-grafana-orange/20 transition-colors ${errors.effective_date ? 'border-grafana-orange focus:border-grafana-orange' : 'border-grafana-border focus:border-grafana-orange text-grafana-ink placeholder-grafana-neutral/50'}`}
              />
              {errors.effective_date && <p className="mt-1 text-xs text-grafana-orange">{errors.effective_date.message}</p>}
            </div>
          </div>

          <div className="px-6 py-4 border-t border-grafana-border bg-grafana-surface flex justify-end space-x-3 shrink-0">
            <Button
              variant="secondary"
              size="md"
              portalTheme="hr"
              onClick={onClose}
              disabled={isSubmitting}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              variant="primary"
              size="md"
              portalTheme="hr"
              disabled={isSubmitting}
              loading={isSubmitting}
            >
              Add Salary Record
            </Button>
          </div>
        </form>
      </div>
    </div>,
    document.body
  );
}
