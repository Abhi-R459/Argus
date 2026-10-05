import RiskPanel from '../../components/auditor/RiskPanel';
import ConcurrencyLab from '../../components/auditor/ConcurrencyLab';
import PageHeader from '../../components/common/PageHeader';

export default function ActivityPage() {
  return (
    <div className="space-y-6">
      <PageHeader
        title="Activity & Risk"
        description="Review suspicious activity flags and explore transaction concurrency behavior."
      />
      <RiskPanel />
      <ConcurrencyLab />
    </div>
  );
}
