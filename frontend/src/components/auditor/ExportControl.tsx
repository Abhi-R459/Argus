import { useState } from 'react';
import { useAuth } from '@clerk/clerk-react';
import { downloadSignedEvidence, downloadEvidencePack } from '../../services/auditService';
import { Download, CheckCircle, AlertCircle, Loader2, Package, FileJson, ShieldCheck } from 'lucide-react';

export default function ExportControl() {
  const { getToken } = useAuth();
  const [format, setFormat] = useState<'arguspack' | 'json'>('arguspack');
  const [status, setStatus] = useState<'idle' | 'loading' | 'success' | 'error'>('idle');
  const [errorMessage, setErrorMessage] = useState('');

  const handleExport = async () => {
    setStatus('loading');
    setErrorMessage('');
    
    try {
      if (format === 'arguspack') {
        await downloadEvidencePack(getToken);
      } else {
        await downloadSignedEvidence(getToken);
      }
      setStatus('success');
      
      // Reset success status after a few seconds
      setTimeout(() => {
        setStatus('idle');
      }, 3500);
    } catch (err: any) {
      console.error('Export failed:', err);
      setStatus('error');
      setErrorMessage(err.message || 'Failed to download evidence');
    }
  };

  return (
    <div className="bg-[#0F172A]/80 border border-slate-800/80 rounded-2xl p-6 flex flex-col justify-center items-center text-center relative overflow-hidden shadow-sm">
      <div className="absolute inset-0 bg-gradient-to-br from-emerald-600/5 to-transparent pointer-events-none" />
      
      <div className="bg-emerald-500/10 p-3 rounded-full mb-3 border border-emerald-500/20">
        {format === 'arguspack' ? (
          <Package className="w-8 h-8 text-emerald-400" />
        ) : (
          <Download className="w-8 h-8 text-emerald-400" />
        )}
      </div>
      
      <h3 className="text-lg font-semibold text-slate-100">Export Cryptographic Evidence</h3>
      
      {/* Format Selector */}
      <div className="mt-3 mb-4 inline-flex p-1 bg-[#0B0F17] rounded-xl border border-slate-800 text-xs font-medium">
        <button
          type="button"
          onClick={() => setFormat('arguspack')}
          className={`btn-press-sm flex items-center space-x-1.5 px-3 py-1.5 rounded-lg transition-colors duration-150 ${
            format === 'arguspack'
              ? 'bg-emerald-600 text-white shadow-xs'
              : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          <ShieldCheck className="w-3.5 h-3.5" />
          <span>.arguspack Bundle</span>
          <span className="text-[10px] px-1 py-0.2 bg-emerald-950/80 text-emerald-200 rounded border border-emerald-500/40">Air-Gapped</span>
        </button>

        <button
          type="button"
          onClick={() => setFormat('json')}
          className={`btn-press-sm flex items-center space-x-1.5 px-3 py-1.5 rounded-lg transition-colors duration-150 ${
            format === 'json'
              ? 'bg-emerald-600 text-white shadow-xs'
              : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          <FileJson className="w-3.5 h-3.5" />
          <span>Signed JSON</span>
        </button>
      </div>

      <p className="text-sm text-slate-400 mb-5 max-w-md">
        {format === 'arguspack'
          ? 'Download a turnkey .arguspack archive with embedded zero-dependency standalone verifier, detached Ed25519 signature, manifest, and canonical events.'
          : 'Download a single cryptographically signed JSON file containing the full audit trail for lightweight verification.'}
      </p>

      <button
        onClick={handleExport}
        disabled={status === 'loading'}
        className={`btn-press inline-flex items-center space-x-2 px-6 py-2.5 rounded-lg font-medium transition-colors duration-150 ${
          status === 'loading'
            ? 'bg-slate-800 text-slate-500 cursor-not-allowed'
            : status === 'success'
            ? 'bg-emerald-600/20 text-emerald-400 border border-emerald-500/30'
            : status === 'error'
            ? 'bg-rose-600 hover:bg-rose-500 text-white shadow-[0_0_15px_rgba(225,29,72,0.3)]'
            : 'bg-emerald-600 hover:bg-emerald-500 text-white shadow-[0_0_15px_rgba(5,150,105,0.3)]'
        }`}
      >
        {status === 'loading' ? (
          <>
            <Loader2 className="w-5 h-5 animate-fast-spin" />
            <span>Generating {format === 'arguspack' ? '.arguspack Bundle' : 'JSON Package'}...</span>
          </>
        ) : status === 'success' ? (
          <>
            <CheckCircle className="w-5 h-5" />
            <span>Export Complete</span>
          </>
        ) : (
          <>
            {format === 'arguspack' ? <Package className="w-5 h-5" /> : <Download className="w-5 h-5" />}
            <span>
              {status === 'error'
                ? 'Retry Export'
                : format === 'arguspack'
                ? 'Download .arguspack Bundle'
                : 'Download JSON Package'}
            </span>
          </>
        )}
      </button>

      {status === 'error' && (
        <div className="mt-4 flex items-center space-x-2 text-rose-400 text-sm">
          <AlertCircle className="w-4 h-4" />
          <span>{errorMessage}</span>
        </div>
      )}
    </div>
  );
}

