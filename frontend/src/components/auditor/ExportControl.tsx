import { useState } from 'react';
import { useAuth } from '@clerk/clerk-react';
import { downloadSignedEvidence, downloadEvidencePack } from '../../services/auditService';
import { Download, CheckCircle, AlertCircle, Package, FileJson, ShieldCheck } from 'lucide-react';

import Button from '../common/Button';

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
    <div className="bg-linear-surface-1 border border-linear-hairline rounded-2xl p-6 flex flex-col justify-center items-center text-center relative overflow-hidden shadow-sm">
      <div className="absolute inset-0 bg-gradient-to-br from-linear-success/5 to-transparent pointer-events-none" />
      
      <div className="bg-linear-success/10 p-3 rounded-full mb-3 border border-linear-success/20">
        {format === 'arguspack' ? (
          <Package className="w-8 h-8 text-linear-success" />
        ) : (
          <Download className="w-8 h-8 text-linear-success" />
        )}
      </div>
      
      <h3 className="text-lg font-semibold text-linear-ink">Export Cryptographic Evidence</h3>
      
      {/* Format Selector */}
      <div className="mt-3 mb-4 inline-flex p-1 bg-linear-surface-2 rounded-xl border border-linear-hairline text-xs font-medium space-x-1" role="tablist" aria-label="Evidence format selection">
        <button
          type="button"
          role="tab"
          aria-selected={format === 'arguspack'}
          onClick={() => setFormat('arguspack')}
          className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-lg transition-colors duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-linear-primary ${
            format === 'arguspack'
              ? 'bg-linear-success text-white shadow-xs font-semibold'
              : 'text-linear-ink-subtle hover:text-linear-ink'
          }`}
        >
          <ShieldCheck className="w-3.5 h-3.5" />
          <span>.arguspack Bundle</span>
          <span className="text-[10px] px-1 py-0.2 bg-linear-canvas text-linear-success rounded border border-linear-success/30">Air-Gapped</span>
        </button>

        <button
          type="button"
          role="tab"
          aria-selected={format === 'json'}
          onClick={() => setFormat('json')}
          className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-lg transition-colors duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-linear-primary ${
            format === 'json'
              ? 'bg-linear-success text-white shadow-xs font-semibold'
              : 'text-linear-ink-subtle hover:text-linear-ink'
          }`}
        >
          <FileJson className="w-3.5 h-3.5" />
          <span>Signed JSON</span>
        </button>
      </div>

      <p className="text-sm text-linear-ink-subtle mb-5 max-w-md">
        {format === 'arguspack'
          ? 'Download a turnkey .arguspack archive with embedded zero-dependency standalone verifier, detached Ed25519 signature, manifest, and canonical events.'
          : 'Download a single cryptographically signed JSON file containing the full audit trail for lightweight verification.'}
      </p>

      <Button
        type="button"
        onClick={handleExport}
        loading={status === 'loading'}
        variant={status === 'success' ? 'success' : status === 'error' ? 'danger' : 'primary'}
        size="lg"
        portalTheme="auditor"
        leftIcon={
          status === 'success' ? (
            <CheckCircle className="w-5 h-5" />
          ) : format === 'arguspack' ? (
            <Package className="w-5 h-5" />
          ) : (
            <Download className="w-5 h-5" />
          )
        }
      >
        {status === 'loading'
          ? `Generating ${format === 'arguspack' ? '.arguspack Bundle' : 'JSON Package'}...`
          : status === 'success'
          ? 'Export Complete'
          : status === 'error'
          ? 'Retry Export'
          : format === 'arguspack'
          ? 'Download .arguspack Bundle'
          : 'Download JSON Package'}
      </Button>

      {status === 'error' && (
        <div className="mt-4 flex items-center space-x-2 text-grafana-orange text-sm">
          <AlertCircle className="w-4 h-4" />
          <span>{errorMessage}</span>
        </div>
      )}
    </div>
  );
}

