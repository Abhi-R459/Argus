import RiskPanel from '../../components/auditor/RiskPanel';
import ConcurrencyLab from '../../components/auditor/ConcurrencyLab';

export default function ActivityPage() {
  return (
    <div className="space-y-4">
      <RiskPanel />
      <ConcurrencyLab />
    </div>
  );
}
