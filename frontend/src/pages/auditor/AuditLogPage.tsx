import AuditLogTable from '../../components/auditor/AuditLogTable';

export default function AuditLogPage() {
  return (
    <div className="animate-in fade-in slide-in-from-bottom-4 duration-500 space-y-4">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h2 className="text-lg font-semibold text-slate-200">Audit Log</h2>
          <p className="text-sm text-slate-500 mt-0.5">
            Immutable, append-only record of every data mutation. Entries are hash-chained — any
            tampering breaks the chain.
          </p>
        </div>
        <div className="flex-shrink-0 w-full sm:w-auto">
          {/* We can use the ExportControl component here, but the current component is a large card.
              Let's adjust it to be a small button, or we can use the card version. Let's see what works best. */}
        </div>
      </div>
      <AuditLogTable />
    </div>
  );
}
