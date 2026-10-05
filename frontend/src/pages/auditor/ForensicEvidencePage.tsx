import React, { useState } from 'react';
import { useAuth } from '@clerk/clerk-react';
import {
  ShieldCheck,
  Download,
  Search,
  Layers,
  FileCheck,
  AlertCircle,
  Copy,
  CheckCircle2,
  Terminal,
  Sparkles,
} from 'lucide-react';
import {
  getMerkleProof,
  downloadCapsule,
  MerkleProof,
} from '../../services/auditService';
import PageHeader from '../../components/common/PageHeader';

export default function ForensicEvidencePage() {
  const { getToken } = useAuth();

  const [sequenceId, setSequenceId] = useState<number>(1);
  const [isLoadingProof, setIsLoadingProof] = useState<boolean>(false);
  const [isDownloading, setIsDownloading] = useState<boolean>(false);
  const [proof, setProof] = useState<MerkleProof | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [copiedField, setCopiedField] = useState<string | null>(null);

  const handleFetchProof = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!sequenceId || sequenceId <= 0) {
      setError('Please provide a valid sequence ID (greater than 0).');
      return;
    }

    setError(null);
    setIsLoadingProof(true);

    try {
      const data = await getMerkleProof(Number(sequenceId), getToken);
      setProof(data);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      setError(msg || 'Failed to generate Merkle proof for this sequence ID.');
      setProof(null);
    } finally {
      setIsLoadingProof(false);
    }
  };

  const handleDownloadCapsule = async () => {
    if (!sequenceId) return;
    setIsDownloading(true);
    setError(null);

    try {
      await downloadCapsule(Number(sequenceId), getToken);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      setError(msg || 'Failed to download forensic evidence capsule.');
    } finally {
      setIsDownloading(false);
    }
  };

  const copyToClipboard = (text: string, label: string) => {
    navigator.clipboard.writeText(text);
    setCopiedField(label);
    setTimeout(() => setCopiedField(null), 2000);
  };

  return (
    <div className="space-y-6 max-w-7xl mx-auto pb-12">
      <PageHeader
        icon={<ShieldCheck className="h-5 w-5" />}
        title="Forensic Evidence & Selective Merkle Capsules"
        description="Prove one record’s inclusion in a signed checkpoint without disclosing sibling records."
        eyebrow="Selective evidence · RFC 6962"
      />

      {/* Lookup Card */}
      <div className="p-5 rounded-xl border border-linear-hairline bg-linear-surface-1 shadow-xs space-y-4">
        <form onSubmit={handleFetchProof} className="flex flex-col sm:flex-row gap-3 items-end">
          <div className="w-full sm:w-80">
            <label className="block text-xs font-semibold text-linear-ink-subtle uppercase tracking-wider mb-1.5">
              Audit Event Sequence ID
            </label>
            <div className="relative">
              <Search className="w-4 h-4 text-linear-ink-muted absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" />
              <input
                type="number"
                min="1"
                value={sequenceId || ''}
                onChange={(e) => setSequenceId(parseInt(e.target.value, 10) || 0)}
                placeholder="e.g. 42"
                className="w-full bg-linear-surface-2 border border-linear-hairline rounded-lg pl-9 pr-3 py-2 text-sm text-linear-ink placeholder-linear-ink-subtle focus:outline-hidden focus:border-linear-primary focus:ring-1 focus:ring-linear-primary/30 font-mono h-[38px] transition-colors"
              />
            </div>
          </div>

          <button
            type="submit"
            disabled={isLoadingProof || !sequenceId}
            className="flex items-center justify-center gap-2 px-4 py-2 bg-linear-primary hover:bg-linear-primary-hover active:bg-linear-primary-focus text-white rounded-lg text-sm font-medium transition-colors shadow-xs disabled:opacity-50 h-[38px] btn-press shrink-0"
          >
            {isLoadingProof ? (
              <>
                <div className="w-4 h-4 border-2 border-white/20 border-t-white rounded-full animate-fast-spin" />
                <span>Computing Proof...</span>
              </>
            ) : (
              <>
                <Sparkles className="w-4 h-4 text-linear-primary" />
                <span>Generate Merkle Proof</span>
              </>
            )}
          </button>

          <button
            type="button"
            onClick={handleDownloadCapsule}
            disabled={isDownloading || !sequenceId}
            className="flex items-center justify-center gap-2 px-4 py-2 bg-linear-surface-2 hover:bg-linear-surface-3 active:bg-linear-surface-4 border border-linear-hairline text-linear-ink rounded-lg text-sm font-medium transition-colors shadow-2xs disabled:opacity-50 h-[38px] btn-press shrink-0"
          >
            {isDownloading ? (
              <>
                <div className="w-4 h-4 border-2 border-white/20 border-t-white rounded-full animate-fast-spin" />
                <span>Bundling...</span>
              </>
            ) : (
              <>
                <Download className="w-4 h-4" />
                <span>Download .arguscap</span>
              </>
            )}
          </button>
        </form>

        {error && (
          <div className="flex items-start gap-2.5 p-3 rounded-lg bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs">
            <AlertCircle className="w-4 h-4 text-rose-400 shrink-0 mt-0.5" />
            <p>{error}</p>
          </div>
        )}
      </div>

      {/* Proof Results */}
      {proof && (
        <div className="space-y-6">
          {/* Metadata Card */}
          <div className="p-6 rounded-xl border border-linear-hairline bg-linear-surface-1 shadow-xs space-y-5">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-linear-hairline pb-4">
              <div className="flex items-center gap-2">
                <FileCheck className="w-5 h-5 text-emerald-400" />
                <h3 className="font-semibold text-linear-ink text-sm sm:text-base">
                  Selective Merkle Inclusion Proof (Sequence #{proof.sequence_id})
                </h3>
              </div>
              <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-emerald-500/15 text-emerald-400 border border-emerald-500/30 w-fit">
                <CheckCircle2 className="w-3.5 h-3.5" />
                RFC 6962 COMPLIANT
              </span>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
              <div className="p-3.5 rounded-lg border border-linear-hairline bg-linear-surface-2 space-y-1">
                <div className="text-[11px] font-medium text-linear-ink-muted uppercase tracking-wider">
                  Checkpoint Enclosing
                </div>
                <div className="text-base font-bold text-linear-ink">
                  Checkpoint #{proof.checkpoint_id}
                </div>
                <div className="text-[11px] text-linear-ink-subtle">
                  Interval Leaf Size: {proof.tree_size} records
                </div>
              </div>

              <div className="p-3.5 rounded-lg border border-linear-hairline bg-linear-surface-2 space-y-1">
                <div className="text-[11px] font-medium text-linear-ink-muted uppercase tracking-wider">
                  Audit Path Depth
                </div>
                <div className="text-base font-bold text-emerald-400">
                  {proof.audit_path_depth} Level{proof.audit_path_depth !== 1 ? 's' : ''}
                </div>
                <div className="text-[11px] text-linear-ink-subtle">
                  Logarithmic: O(log₂ K) complexity
                </div>
              </div>

              <div className="p-3.5 rounded-lg border border-linear-hairline bg-linear-surface-2 space-y-1">
                <div className="text-[11px] font-medium text-linear-ink-muted uppercase tracking-wider">
                  Leaf Position
                </div>
                <div className="text-base font-bold text-linear-ink">
                  Index #{proof.leaf_index}
                </div>
                <div className="text-[11px] text-linear-ink-subtle">
                  Domain prefix: 0x00
                </div>
              </div>

              <div className="p-3.5 rounded-lg border border-linear-hairline bg-linear-surface-2 space-y-1">
                <div className="text-[11px] font-medium text-linear-ink-muted uppercase tracking-wider">
                  Capsule Format
                </div>
                <div className="text-base font-bold text-blue-400">
                  .arguscap
                </div>
                <div className="text-[11px] text-linear-ink-subtle">
                  Zero-disclosure evidence
                </div>
              </div>
            </div>

            {/* Cryptographic Hashes */}
            <div className="space-y-3 pt-2">
              <div className="p-3 rounded-lg bg-linear-surface-2 border border-linear-hairline space-y-1.5">
                <div className="flex items-center justify-between text-xs">
                  <span className="font-semibold text-linear-ink">Merkle Root Hash</span>
                  <button
                    onClick={() => copyToClipboard(proof.merkle_root, 'root')}
                    className="flex items-center gap-1 text-[11px] text-linear-primary hover:underline"
                  >
                    {copiedField === 'root' ? <CheckCircle2 className="w-3.5 h-3.5" /> : <Copy className="w-3.5 h-3.5" />}
                    {copiedField === 'root' ? 'Copied' : 'Copy Root'}
                  </button>
                </div>
                <div className="font-mono text-xs text-linear-ink-subtle break-all select-all">
                  {proof.merkle_root}
                </div>
              </div>

              <div className="p-3 rounded-lg bg-linear-surface-2 border border-linear-hairline space-y-1.5">
                <div className="flex items-center justify-between text-xs">
                  <span className="font-semibold text-linear-ink">Leaf Hash (SHA-256(0x00 || canonical_row))</span>
                  <button
                    onClick={() => copyToClipboard(proof.leaf_hash, 'leaf')}
                    className="flex items-center gap-1 text-[11px] text-linear-primary hover:underline"
                  >
                    {copiedField === 'leaf' ? <CheckCircle2 className="w-3.5 h-3.5" /> : <Copy className="w-3.5 h-3.5" />}
                    {copiedField === 'leaf' ? 'Copied' : 'Copy Leaf'}
                  </button>
                </div>
                <div className="font-mono text-xs text-linear-ink-subtle break-all select-all">
                  {proof.leaf_hash}
                </div>
              </div>
            </div>
          </div>

          {/* Audit Path Traversal Graph */}
          <div className="p-6 rounded-xl border border-linear-hairline bg-linear-surface-1 shadow-xs space-y-4">
            <div className="flex items-center gap-2">
              <Layers className="w-5 h-5 text-linear-primary" />
              <h3 className="font-semibold text-linear-ink text-sm sm:text-base">
                Merkle Inclusion Audit Path ({proof.audit_path.length} steps)
              </h3>
            </div>
            <p className="text-xs text-linear-ink-subtle">
              An independent third party can traverse these sibling hashes bottom-up using RFC 6962 parent hashing (0x01 || left || right) to independently arrive at the Ed25519-signed checkpoint Merkle root.
            </p>

            <div className="space-y-2.5 pt-1">
              {proof.audit_path.map((step, idx) => (
                <div
                  key={idx}
                  className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 p-3 rounded-lg border border-linear-hairline bg-linear-surface-2 text-xs"
                >
                  <div className="flex items-center gap-2 font-mono">
                    <span className="px-2 py-0.5 rounded bg-linear-primary/10 text-linear-primary font-bold text-[11px]">
                      Level {step.level}
                    </span>
                    <span className="text-linear-ink-muted">
                      Sibling Direction: <strong className="text-linear-ink uppercase">{step.direction}</strong>
                    </span>
                  </div>

                  <div className="flex items-center gap-2 font-mono text-[11px] text-linear-ink-subtle select-all">
                    <span>{step.sibling_hash}</span>
                    <button
                      onClick={() => copyToClipboard(step.sibling_hash, `step-${idx}`)}
                      className="p-1 hover:text-linear-primary"
                      title="Copy sibling hash"
                    >
                      {copiedField === `step-${idx}` ? (
                        <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                      ) : (
                        <Copy className="w-3.5 h-3.5" />
                      )}
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Verification Callout */}
          <div className="p-5 rounded-xl border border-blue-500/30 bg-blue-500/5 space-y-3">
            <div className="flex items-center gap-2 text-blue-400 font-semibold text-sm">
              <Terminal className="w-4 h-4" />
              Air-Gapped Standalone Verification Instructions
            </div>
            <p className="text-xs text-linear-ink-subtle">
              Every <code className="text-blue-300">.arguscap</code> archive is completely self-contained with its own embedded zero-dependency verifier script. It requires only standard Python 3.10+ (no pip install required):
            </p>
            <div className="p-3 rounded-lg bg-black/60 border border-white/10 font-mono text-xs text-emerald-400 flex items-center justify-between">
              <span>python verify_capsule.py proof_seq{proof.sequence_id}.arguscap</span>
              <button
                onClick={() =>
                  copyToClipboard(
                    `python verify_capsule.py proof_seq${proof.sequence_id}.arguscap`,
                    'cli',
                  )
                }
                className="text-white/60 hover:text-white"
                title="Copy command"
              >
                {copiedField === 'cli' ? <CheckCircle2 className="w-4 h-4 text-emerald-400" /> : <Copy className="w-4 h-4" />}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
