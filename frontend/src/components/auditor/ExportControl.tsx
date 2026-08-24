import { useState } from 'react';
import { useAuth } from '@clerk/clerk-react';
import { downloadSignedEvidence } from '../../services/auditService';
import { Download, CheckCircle, AlertCircle, Loader2 } from 'lucide-react';

export default function ExportControl() {
  const { getToken } = useAuth();
  const [status, setStatus] = useState<'idle' | 'loading' | 'success' | 'error'>('idle');
  const [errorMessage, setErrorMessage] = useState('');

  const handleExport = async () => {
    setStatus('loading');
    setErrorMessage('');
    
    try {
      await downloadSignedEvidence(getToken);
      setStatus('success');
      
      // Reset success status after a few seconds
      setTimeout(() => {
        setStatus('idle');
      }, 3000);
    } catch (err: any) {
      console.error('Export failed:', err);
      setStatus('error');
      setErrorMessage(err.message || 'Failed to download evidence');
    }
  };

  return (
    <div className="bg-slate-900/50 border border-slate-700/50 rounded-2xl p-6 flex flex-col justify-center items-center text-center relative overflow-hidden">
      <div className="absolute inset-0 bg-gradient-to-br from-emerald-600/5 to-transparent pointer-events-none" />
      
      <div className="bg-emerald-500/10 p-3 rounded-full mb-4">
        <Download className="w-8 h-8 text-emerald-400" />
      </div>
      
      <h3 className="text-lg font-semibold text-slate-200">Export Signed Evidence</h3>
      <p className="text-sm text-slate-400 mt-2 mb-6 max-w-sm">
        Download a cryptographically signed JSON file containing the full audit trail for external verification or offline archiving.
      </p>

      <button
        onClick={handleExport}
        disabled={status === 'loading'}
        className={`inline-flex items-center space-x-2 px-6 py-2.5 rounded-lg font-medium transition-all ${
          status === 'loading'
            ? 'bg-slate-800 text-slate-400 cursor-not-allowed'
            : status === 'success'
            ? 'bg-emerald-600/20 text-emerald-400 border border-emerald-500/30'
            : status === 'error'
            ? 'bg-red-600 hover:bg-red-500 text-white shadow-[0_0_15px_rgba(220,38,38,0.3)]'
            : 'bg-emerald-600 hover:bg-emerald-500 text-white shadow-[0_0_15px_rgba(5,150,105,0.3)] hover:shadow-[0_0_20px_rgba(5,150,105,0.5)]'
        }`}
      >
        {status === 'loading' ? (
          <>
            <Loader2 className="w-5 h-5 animate-spin" />
            <span>Generating Package...</span>
          </>
        ) : status === 'success' ? (
          <>
            <CheckCircle className="w-5 h-5" />
            <span>Export Complete</span>
          </>
        ) : (
          <>
            <Download className="w-5 h-5" />
            <span>{status === 'error' ? 'Retry Export' : 'Download JSON Package'}</span>
          </>
        )}
      </button>

      {status === 'error' && (
        <div className="mt-4 flex items-center space-x-2 text-red-400 text-sm">
          <AlertCircle className="w-4 h-4" />
          <span>{errorMessage}</span>
        </div>
      )}
    </div>
  );
}
