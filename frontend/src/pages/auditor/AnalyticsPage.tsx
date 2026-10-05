import QueryPanel from '../../components/auditor/QueryPanel';
import SecurityPosture from '../../components/auditor/SecurityPosture';
import PageHeader from '../../components/common/PageHeader';

export default function AnalyticsPage() {
  return (
    <div className="space-y-6">
      <PageHeader
        title="System Analytics"
        description="Performance metrics and security posture."
      />

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
        <SecurityPosture />
        <QueryPanel />
      </div>
    </div>
  );
}
