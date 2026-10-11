import { KeyRound, ShieldAlert, ShieldCheck } from 'lucide-react';
import type { CheckpointSignatureEvidence as Evidence } from '../../services/auditService';
import { CopyButton } from '../common/CopyButton';

interface CheckpointSignatureEvidenceProps {
  evidence: Evidence;
}

function CheckStatus({ status }: { status: 'pass' | 'fail' | 'unknown' }) {
  const label = status === 'pass' ? 'Verified' : status === 'fail' ? 'Failed' : 'Unverified';
  const color = status === 'pass'
    ? 'text-linear-success border-linear-success/30 bg-linear-success/10'
    : status === 'fail'
      ? 'text-status-warning border-status-warning/30 bg-status-warning/10'
      : 'text-linear-ink-muted border-linear-hairline bg-linear-surface-2';

  return <span className={`inline-flex rounded-full border px-2 py-0.5 text-[10px] font-bold uppercase ${color}`}>{label}</span>;
}

function EvidenceValue({ label, value }: { label: string; value: string | null }) {
  return (
    <div className="min-w-0 rounded-lg border border-linear-hairline bg-linear-surface-2/70 p-2.5">
      <p className="text-[10px] font-semibold uppercase tracking-wide text-linear-ink-muted">{label}</p>
      <p className="mt-1 break-all font-mono text-[11px] text-linear-ink">{value || 'Unavailable'}</p>
    </div>
  );
}

function SignatureValue({
  label,
  signature,
  status,
}: {
  label: string;
  signature: string | null;
  status: 'pass' | 'fail' | 'unknown';
}) {
  if (!signature) {
    return (
      <div className="rounded-lg border border-linear-hairline bg-linear-surface-2/70 p-3">
        <div className="flex items-center justify-between gap-2">
          <p className="text-xs font-semibold text-linear-ink">{label}</p>
          <CheckStatus status="unknown" />
        </div>
        <p className="mt-2 text-[11px] text-linear-ink-muted">No trusted pre-attack signature was saved for comparison.</p>
      </div>
    );
  }

  const preview = signature.length > 56
    ? `${signature.slice(0, 32)}…${signature.slice(-16)}`
    : signature;

  return (
    <div className="min-w-0 rounded-lg border border-linear-hairline bg-linear-surface-2/70 p-3">
      <div className="flex items-center justify-between gap-2">
        <p className="text-xs font-semibold text-linear-ink">{label}</p>
        <CheckStatus status={status} />
      </div>
      <div className="mt-2 flex items-center gap-1 rounded-md border border-linear-hairline bg-linear-canvas px-2 py-1.5">
        <code className="min-w-0 flex-1 truncate font-mono text-[10px] text-linear-ink" title={signature}>{preview}</code>
        <CopyButton text={signature} label="Copy full signature" portalTheme="auditor" />
      </div>
      <details className="mt-2">
        <summary className="cursor-pointer text-[10px] text-linear-primary">View full signature</summary>
        <code className="mt-1 block break-all rounded-md bg-linear-canvas p-2 font-mono text-[10px] text-linear-ink">{signature}</code>
      </details>
    </div>
  );
}

export default function CheckpointSignatureEvidence({ evidence }: CheckpointSignatureEvidenceProps) {
  const changedBytes = evidence.signature_before_hex
    ? Array.from({ length: Math.min(evidence.signature_before_hex.length, evidence.signature_after_hex.length) / 2 }, (_, index) =>
        evidence.signature_before_hex!.slice(index * 2, index * 2 + 2) !== evidence.signature_after_hex.slice(index * 2, index * 2 + 2)
      ).filter(Boolean).length
    : null;
  const checkpointHashChanged = Boolean(
    evidence.checkpoint_hash_before && evidence.checkpoint_hash_before !== evidence.checkpoint_hash,
  );
  const signatureChangeSummary = changedBytes === null
    ? 'Signature baseline unavailable'
    : changedBytes === 0 && checkpointHashChanged
      ? 'Signature unchanged; signed checkpoint hash was rewritten'
      : `${changedBytes} of 64 signature bytes changed`;

  return (
    <section className="overflow-hidden rounded-xl border border-status-warning/35 bg-linear-surface-1 shadow-xs" aria-labelledby="checkpoint-signature-evidence-title">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-status-warning/20 bg-status-warning/5 px-4 py-3">
        <div className="flex items-center gap-2">
          <ShieldAlert className="h-4 w-4 text-status-warning" />
          <div>
            <h3 id="checkpoint-signature-evidence-title" className="text-sm font-bold text-linear-ink">Checkpoint signature evidence</h3>
            <p className="text-[11px] text-linear-ink-muted">Stored signature does not verify against the trusted public key.</p>
          </div>
        </div>
        <span className="rounded-md border border-status-warning/30 bg-status-warning/10 px-2 py-1 font-mono text-[11px] font-bold text-status-warning">
          Checkpoint #{evidence.checkpoint_id} · Seq #{evidence.sequence_id}
        </span>
      </div>

      <div className="space-y-3 p-4">
        <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-3">
          <EvidenceValue label="Checkpoint hash before attack" value={evidence.checkpoint_hash_before} />
          <EvidenceValue label="Checkpoint hash currently stored" value={evidence.checkpoint_hash} />
          <EvidenceValue label="Merkle root before attack" value={evidence.merkle_root_before} />
          <EvidenceValue label="Merkle root currently stored" value={evidence.merkle_root} />
          <EvidenceValue label="Key ID" value={evidence.key_id} />
          <EvidenceValue label="Trusted public key fingerprint · SHA-256" value={evidence.public_key_fingerprint} />
          <EvidenceValue label="Checkpoint created" value={evidence.created_at ? new Date(evidence.created_at).toLocaleString() : null} />
        </div>

        <div className="grid gap-2 sm:grid-cols-2">
          <SignatureValue
            label="Saved pre-attack signature"
            signature={evidence.signature_before_hex}
            status={evidence.signature_before_status}
          />
          <SignatureValue
            label="Signature currently stored in database"
            signature={evidence.signature_after_hex}
            status={evidence.signature_after_status}
          />
        </div>

        <div className="flex flex-wrap items-center gap-x-4 gap-y-2 rounded-lg border border-linear-hairline bg-linear-surface-2/50 px-3 py-2 text-[11px]">
          <span className="inline-flex items-center gap-1.5 text-linear-ink">
            <KeyRound className="h-3.5 w-3.5 text-linear-primary" />
            {signatureChangeSummary}
          </span>
          <span className="inline-flex items-center gap-1.5"><ShieldCheck className="h-3.5 w-3.5 text-linear-primary" /> Hash chain <CheckStatus status={evidence.hash_chain_status} /></span>
          <span className="inline-flex items-center gap-1.5"><ShieldCheck className="h-3.5 w-3.5 text-linear-primary" /> Anchor <CheckStatus status={evidence.anchor_status} /></span>
          {evidence.before_source?.startsWith('recovery_snapshot:') && (
            <span className="text-linear-ink-muted">Original checkpoint evidence loaded from the saved pre-attack snapshot and verified with the trusted public key.</span>
          )}
        </div>
      </div>
    </section>
  );
}
