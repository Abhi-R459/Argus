import { ArchiveX, Hash } from 'lucide-react';
import type { DeletedEntryEvidence as Evidence } from '../../services/auditService';
import { CopyButton } from '../common/CopyButton';

function HashValue({ label, value }: { label: string; value: string | null }) {
  if (!value) return null;
  return (
    <div className="min-w-0 rounded-lg border border-linear-hairline bg-linear-surface-2/70 p-2.5">
      <p className="text-[10px] font-semibold uppercase tracking-wide text-linear-ink-muted">{label}</p>
      <div className="mt-1 flex items-center gap-1">
        <code className="min-w-0 flex-1 truncate font-mono text-[10px] text-linear-ink" title={value}>{value}</code>
        <CopyButton text={value} label="Copy" portalTheme="auditor" />
      </div>
    </div>
  );
}

function Payload({ label, value }: { label: string; value: Record<string, unknown> | null }) {
  return (
    <div className="min-w-0 rounded-lg border border-linear-hairline bg-linear-surface-2/60 p-3">
      <p className="text-[10px] font-semibold uppercase tracking-wide text-linear-ink-muted">{label}</p>
      {value ? (
        <pre className="mt-2 max-h-48 overflow-auto whitespace-pre-wrap break-all rounded-md bg-linear-canvas p-2 font-mono text-[10px] text-linear-ink">{JSON.stringify(value, null, 2)}</pre>
      ) : (
        <p className="mt-2 text-[11px] text-linear-ink-muted">No payload was recorded for this side of the event.</p>
      )}
    </div>
  );
}

export default function DeletedEntryEvidence({ evidence }: { evidence: Evidence }) {
  return (
    <section className="overflow-hidden rounded-xl border border-status-warning/35 bg-linear-surface-1 shadow-xs" aria-labelledby="deleted-entry-evidence-title">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-status-warning/20 bg-status-warning/5 px-4 py-3">
        <div className="flex items-center gap-2">
          <ArchiveX className="h-4 w-4 text-status-warning" />
          <div>
            <h3 id="deleted-entry-evidence-title" className="text-sm font-bold text-linear-ink">Deleted audit event evidence</h3>
            <p className="text-[11px] text-linear-ink-muted">The verifier found the sequence gap; this saved copy shows the event that was removed.</p>
          </div>
        </div>
        <span className="rounded-md border border-status-warning/30 bg-status-warning/10 px-2 py-1 font-mono text-[11px] font-bold text-status-warning">
          Missing sequence #{evidence.sequence_id}
        </span>
      </div>

      <div className="space-y-3 p-4">
        <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
          <div className="rounded-lg border border-linear-hairline bg-linear-surface-2/70 p-2.5">
            <p className="text-[10px] font-semibold uppercase tracking-wide text-linear-ink-muted">Event</p>
            <p className="mt-1 text-xs font-bold text-linear-ink">{evidence.action} · {evidence.table_name}</p>
          </div>
          <div className="rounded-lg border border-linear-hairline bg-linear-surface-2/70 p-2.5">
            <p className="text-[10px] font-semibold uppercase tracking-wide text-linear-ink-muted">Row ID</p>
            <p className="mt-1 font-mono text-xs text-linear-ink">#{evidence.row_id}</p>
          </div>
          <div className="rounded-lg border border-linear-hairline bg-linear-surface-2/70 p-2.5">
            <p className="text-[10px] font-semibold uppercase tracking-wide text-linear-ink-muted">Recorded at</p>
            <p className="mt-1 text-xs text-linear-ink">{evidence.created_at ? new Date(evidence.created_at).toLocaleString() : 'Unavailable'}</p>
          </div>
          <div className="rounded-lg border border-linear-hairline bg-linear-surface-2/70 p-2.5">
            <p className="text-[10px] font-semibold uppercase tracking-wide text-linear-ink-muted">Severity</p>
            <p className="mt-1 text-xs text-linear-ink">{evidence.severity || 'Unspecified'}</p>
          </div>
        </div>

        <div className="grid gap-2 sm:grid-cols-2">
          <HashValue label="Deleted entry hash" value={evidence.entry_hash} />
          <HashValue label="Previous entry hash" value={evidence.previous_hash} />
        </div>

        <div className="grid gap-2 sm:grid-cols-2">
          <Payload label="Old payload" value={evidence.old_value} />
          <Payload label="New payload" value={evidence.new_value} />
        </div>

        <p className="flex items-center gap-1.5 text-[10px] text-linear-ink-muted">
          <Hash className="h-3 w-3" /> The event copy comes from the local recovery snapshot; the sequence-gap result comes from the verifier's chain walk.
        </p>
      </div>
    </section>
  );
}
