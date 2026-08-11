import QueryPanel from '../../components/auditor/QueryPanel';
import SecurityPosture from '../../components/auditor/SecurityPosture';

export default function AnalyticsPage() {
  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-semibold text-slate-200">System Analytics</h2>
        <p className="text-sm text-slate-500 mt-0.5">
          Performance metrics and security posture overview.
        </p>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
        <SecurityPosture />
        <QueryPanel />
      </div>
    </div>
  );
}
