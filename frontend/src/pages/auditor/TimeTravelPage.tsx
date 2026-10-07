import TimeTravelView from '../../components/auditor/TimeTravelView';
import PageHeader from '../../components/common/PageHeader';

export default function TimeTravelPage() {
  return (
    <div className="space-y-6">
      <PageHeader
        title="Time Travel"
        description="Reconstruct employee state at a point in the audit history."
      />
      <TimeTravelView />
    </div>
  );
}
