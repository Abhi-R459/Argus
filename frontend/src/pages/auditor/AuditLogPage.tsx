import AuditLogTable from '../../components/auditor/AuditLogTable';

export default function AuditLogPage() {
  return (
    <div className="animate-in fade-in slide-in-from-bottom-4 duration-500 space-y-4">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h2 className="text-lg font-semibold text-linear-ink">Audit Log</h2>
          <p className="text-sm text-linear-ink-muted mt-0.5">
            Immutable, append-only record of every data mutation. Entries are hash-chained — any
            tampering breaks the chain.
          </p>
        </div>
      </div>
      <AuditLogTable />
    </div>
  );
}
