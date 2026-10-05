import AuditLogTable from '../../components/auditor/AuditLogTable';
import PageHeader from '../../components/common/PageHeader';

export default function AuditLogPage() {
  return (
    <div className="animate-fade-cascade space-y-4">
      <PageHeader
        title="Audit Log"
        description="Append-only history of data changes, linked by the audit hash chain."
      />
      <AuditLogTable />
    </div>
  );
}
