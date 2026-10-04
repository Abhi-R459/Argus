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
    <div className="bg-linear-surface-1 border border-linear-hairline rounded-2xl overflow-hidden shadow-sm h-full flex flex-col justify-between relative">
      <div className="absolute inset-0 bg-gradient-to-br from-linear-success/5 to-transparent pointer-events-none" />

      {/* Header */}
      <div className="flex items-center justify-between px-5 py-4 border-b border-linear-hairline shrink-0">
        <div className="flex items-center space-x-2.5">
          <div className="w-9 h-9 rounded-xl flex items-center justify-center bg-linear-surface-2 border border-linear-hairline">
            <Package className="w-4 h-4 text-linear-success" />
          </div>
          <div>
            <p className="text-[10px] text-linear-ink-subtle uppercase tracking-wider font-semibold">Evidence Export</p>
            <h3 className="text-sm font-semibold text-linear-ink">Standalone Bundle</h3>
          </div>
        </div>
        <span className="flex items-center space-x-1.5 px-2.5 py-1 rounded-full text-[11px] font-bold uppercase tracking-wider border bg-linear-success/15 text-linear-success border-linear-success/30">
          <span className="w-1.5 h-1.5 rounded-full bg-linear-success" />
          <span>RFC 8032</span>
        </span>
      </div>

      {/* Content body */}
      <div className="p-5 flex-1 flex flex-col justify-between space-y-3.5">
        <div className="space-y-3">
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
            className="w-full"
          />

          <p className="text-xs text-linear-ink-subtle leading-relaxed">
            {format === 'arguspack'
              ? 'Download a turnkey .arguspack archive with embedded zero-dependency standalone verifier, detached Ed25519 signature, manifest, and canonical events.'
              : 'Download a single cryptographically signed JSON file containing the full audit hash chain and checkpoint signatures for lightweight verification.'}
          </p>

          {/* Manifest Specification Box */}
          <div className="space-y-1.5 bg-linear-surface-2 p-2.5 rounded-xl border border-linear-hairline text-[11px]">
            <div className="flex items-center justify-between py-1 px-1.5 rounded hover:bg-linear-surface-1 transition-colors">
              <div className="flex items-center space-x-2 truncate pr-2">
                <span className="w-1.5 h-1.5 rounded-full flex-shrink-0 bg-linear-success" />
                <span className="font-mono text-linear-ink truncate">Package Manifest</span>
              </div>
              <span className="font-mono text-[10px] text-linear-ink-subtle">manifest.json</span>
            </div>

            <div className="flex items-center justify-between py-1 px-1.5 rounded hover:bg-linear-surface-1 transition-colors">
              <div className="flex items-center space-x-2 truncate pr-2">
                <span className="w-1.5 h-1.5 rounded-full flex-shrink-0 bg-linear-success" />
                <span className="font-mono text-linear-ink truncate">Standalone Verifier</span>
              </div>
              <span className="text-[9px] font-bold px-1.5 py-0.5 rounded border uppercase bg-linear-success/10 text-linear-success border-linear-success/30">
                ZERO-DEP
              </span>
            </div>

            <div className="flex items-center justify-between py-1 px-1.5 rounded hover:bg-linear-surface-1 transition-colors">
              <div className="flex items-center space-x-2 truncate pr-2">
                <span className="w-1.5 h-1.5 rounded-full flex-shrink-0 bg-linear-success" />
                <span className="font-mono text-linear-ink truncate">Detached Signature</span>
              </div>
              <span className="text-[9px] font-bold px-1.5 py-0.5 rounded border uppercase bg-linear-success/10 text-linear-success border-linear-success/30">
                ED25519
              </span>
            </div>
          </div>
        </div>

        {/* Screen Reader Live Region (F-110, F-122) */}
        <div aria-live="polite" className="sr-only">
          {status === 'loading' && `Generating ${format === 'arguspack' ? '.arguspack Bundle' : 'JSON Package'}...`}
          {status === 'success' && 'Evidence export completed successfully and downloaded to disk.'}
          {status === 'error' && `Export failed: ${errorMessage}`}
        </div>

        {/* Action Button */}
        <div>
          <Button
            type="button"
            onClick={handleExport}
            loading={status === 'loading'}
            variant={status === 'success' ? 'success' : status === 'error' ? 'danger' : 'primary'}
            size="md"
            portalTheme="auditor"
            className="w-full justify-center"
            leftIcon={
              status === 'success' ? (
                <CheckCircle className="w-4 h-4" />
              ) : format === 'arguspack' ? (
                <Package className="w-4 h-4" />
              ) : (
                <Download className="w-4 h-4" />
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
            <div role="alert" className="mt-2 flex items-center space-x-2 text-grafana-orange text-xs">
              <AlertCircle className="w-3.5 h-3.5 shrink-0" />
              <span>{errorMessage}</span>
            </div>
          )}
        </div>
      </div>

      {/* Footer */}
      <div className="border-t border-linear-hairline px-5 py-3 shrink-0">
        <div className="flex items-center justify-between">
          <p className="text-xs text-linear-ink-subtle">Target Environment</p>
          <span className="font-mono text-xs text-linear-ink">Air-Gapped Verifier</span>
        </div>
      </div>
    </div>
  );
}
