import { useState } from 'react';
import { useAuth } from '@clerk/clerk-react';
import { downloadSignedEvidence, downloadEvidencePack } from '../../services/auditService';
import { Download, CheckCircle, AlertCircle, Package, FileJson, ShieldCheck } from 'lucide-react';

import Button from '../common/Button';
import { SegmentedControl } from '../common/SegmentedControl';

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
      <SegmentedControl<'arguspack' | 'json'>
        value={format}
        onChange={setFormat}
        options={[
          {
            value: 'arguspack',
            label: '.arguspack Bundle',
            icon: <ShieldCheck className="w-3.5 h-3.5" />,
            badge: (
              <span className="text-[10px] px-1 py-0.5 bg-linear-canvas text-linear-success rounded border border-linear-success/30 font-mono">
                Air-Gapped
              </span>
            ),
          },
          {
            value: 'json',
            label: 'Signed JSON',
            icon: <FileJson className="w-3.5 h-3.5" />,
          },
        ]}
        portalTheme="auditor"
        ariaLabel="Evidence format selection"
        className="mt-3 mb-4"
      />

      <p className="text-sm text-linear-ink-subtle mb-5 max-w-md">
        {format === 'arguspack'
          ? 'Download a turnkey .arguspack archive with embedded zero-dependency standalone verifier, detached Ed25519 signature, manifest, and canonical events.'
          : 'Download a single cryptographically signed JSON file containing the full audit trail for lightweight verification.'}
      </p>

      {/* Screen Reader Live Region (F-110, F-122) */}
      <div aria-live="polite" className="sr-only">
        {status === 'loading' && `Generating ${format === 'arguspack' ? '.arguspack Bundle' : 'JSON Package'}...`}
        {status === 'success' && 'Evidence export completed successfully and downloaded to disk.'}
        {status === 'error' && `Export failed: ${errorMessage}`}
      </div>

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
        <div role="alert" className="mt-4 flex items-center space-x-2 text-grafana-orange text-sm">
          <AlertCircle className="w-4 h-4 shrink-0" />
          <span>{errorMessage}</span>
        </div>
      )}
    </div>
  );
}
