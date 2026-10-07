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
    } catch (err: unknown) {
      console.error('Export failed:', err);
      setStatus('error');
      setErrorMessage(err instanceof Error ? err.message : 'Failed to download evidence');
    }
  };

  return (
    <section className="bg-linear-surface-1 border border-linear-hairline rounded-2xl overflow-hidden shadow-sm flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between px-5 py-3.5 border-b border-linear-hairline shrink-0">
        <div className="flex items-center space-x-2.5">
          <div className="w-9 h-9 rounded-xl flex items-center justify-center bg-linear-surface-2 border border-linear-hairline">
            <Package className="w-4 h-4 text-linear-success" />
          </div>
          <div>
            <p className="text-xs text-linear-ink-subtle font-medium">Evidence export</p>
            <h3 className="text-sm font-semibold text-linear-ink">Package and verify a copy of the ledger</h3>
          </div>
        </div>
        <span className="flex items-center space-x-1.5 px-2.5 py-1 rounded-full text-[11px] font-bold uppercase tracking-wider border bg-linear-success/15 text-linear-success border-linear-success/30">
          <span className="w-1.5 h-1.5 rounded-full bg-linear-success" />
          <span>RFC 8032</span>
        </span>
      </div>

      {/* Content body */}
      <div className="p-5 grid grid-cols-1 lg:grid-cols-[minmax(250px,1fr)_minmax(0,1.45fr)_minmax(220px,0.8fr)] gap-5 items-center">
        <div className="space-y-3 min-w-0">
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

          <p className="text-sm text-linear-ink-subtle leading-relaxed">
            {format === 'arguspack'
              ? 'Download a .arguspack archive with a standalone verifier and detached Ed25519 signature. Verify authenticity with a public key obtained through a trusted channel.'
              : 'Download a signed JSON file containing the audit hash chain and checkpoint signatures. Verify authenticity with a public key obtained through a trusted channel.'}
          </p>
        </div>

        {/* Included in each package */}
        <div>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 text-xs">
            <div className="flex items-start gap-2.5 rounded-lg border border-linear-hairline bg-linear-surface-2 px-3 py-3 min-w-0">
              <span className="w-2 h-2 mt-1 rounded-full flex-shrink-0 bg-linear-success" />
              <div className="min-w-0">
                <span className="block text-linear-ink font-medium">Package manifest</span>
                <span className="block mt-1 font-mono text-[11px] text-linear-ink-subtle truncate">manifest.json</span>
              </div>
            </div>

            <div className="flex items-start gap-2.5 rounded-lg border border-linear-hairline bg-linear-surface-2 px-3 py-3 min-w-0">
              <span className="w-2 h-2 mt-1 rounded-full flex-shrink-0 bg-linear-success" />
              <div className="min-w-0">
                <span className="block text-linear-ink font-medium">Standalone verifier</span>
                <span className="inline-flex mt-1 text-[10px] font-semibold tracking-wide text-linear-success">ZERO DEPENDENCIES</span>
              </div>
            </div>

            <div className="flex items-start gap-2.5 rounded-lg border border-linear-hairline bg-linear-surface-2 px-3 py-3 min-w-0">
              <span className="w-2 h-2 mt-1 rounded-full flex-shrink-0 bg-linear-success" />
              <div className="min-w-0">
                <span className="block text-linear-ink font-medium">Detached signature</span>
                <span className="inline-flex mt-1 text-[10px] font-semibold tracking-wide text-linear-success">ED25519</span>
              </div>
            </div>
          </div>
        </div>

        <div className="min-w-0">
        {/* Screen Reader Live Region (F-110, F-122) */}
        <div aria-live="polite" className="sr-only">
          {status === 'loading' && `Generating ${format === 'arguspack' ? '.arguspack Bundle' : 'JSON Package'}...`}
          {status === 'success' && 'Evidence export completed and the browser download was started.'}
          {status === 'error' && `Export failed: ${errorMessage}`}
        </div>

        {/* Action Button */}
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
            <div role="alert" className="mt-2 flex items-center space-x-2 text-status-warning text-xs">
              <AlertCircle className="w-3.5 h-3.5 shrink-0" />
              <span>{errorMessage}</span>
            </div>
          )}
        </div>
      </div>

      {/* Footer */}
      <div className="border-t border-linear-hairline px-5 py-2.5 shrink-0 flex items-center gap-2 text-xs">
        <ShieldCheck className="w-3.5 h-3.5 text-linear-success" />
        <p className="text-linear-ink-subtle">Target environment</p>
        <span className="font-medium text-linear-ink">Air-gapped verifier</span>
      </div>
    </section>
  );
}
