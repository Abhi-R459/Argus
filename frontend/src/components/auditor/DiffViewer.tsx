
interface DiffField {
  key: string;
  oldVal: unknown;
  newVal: unknown;
  changed: boolean;
}

interface DiffViewerProps {
  oldValue: Record<string, unknown> | null;
  newValue: Record<string, unknown> | null;
  /** Operation context — drives the header label */
  operation?: 'INSERT' | 'UPDATE' | 'DELETE';
}

function renderValue(val: unknown): string {
  if (val === null || val === undefined) return '—';
  if (typeof val === 'object') return JSON.stringify(val);
  return String(val);
}

export default function DiffViewer({ oldValue, newValue, operation }: DiffViewerProps) {
  const allKeys = Array.from(
    new Set([
      ...Object.keys(oldValue ?? {}),
      ...Object.keys(newValue ?? {}),
    ])
  );

  if (allKeys.length === 0) {
    return (
      <p className="text-xs text-linear-ink-muted italic py-2">No field-level diff available.</p>
    );
  }

  const fields: DiffField[] = allKeys.map((key) => {
    const ov = oldValue?.[key];
    const nv = newValue?.[key];
    return {
      key,
      oldVal: ov,
      newVal: nv,
      changed: JSON.stringify(ov) !== JSON.stringify(nv),
    };
  });

  const changedCount = fields.filter((f) => f.changed).length;

  return (
    <div className="space-y-2">
      {/* Header */}
      <div className="flex items-center justify-between mb-1">
        <span className="text-[10px] uppercase tracking-wider font-semibold text-linear-ink-muted">
          {operation === 'INSERT'
            ? 'New record'
            : operation === 'DELETE'
            ? 'Deleted record'
            : `${changedCount} field${changedCount !== 1 ? 's' : ''} changed`}
        </span>
        <div className="flex items-center space-x-3 text-[10px]">
          {oldValue !== null && (
            <span className="flex items-center space-x-1">
              <span className="w-2 h-2 rounded-sm bg-grafana-orange/30 border border-grafana-orange/60" />
              <span className="text-linear-ink-muted">Before</span>
            </span>
          )}
          {newValue !== null && (
            <span className="flex items-center space-x-1">
              <span className="w-2 h-2 rounded-sm bg-linear-success/30 border border-linear-success/60" />
              <span className="text-linear-ink-muted">After</span>
            </span>
          )}
        </div>
      </div>

      {/* Table */}
      <div className="overflow-x-auto rounded-lg border border-linear-hairline bg-linear-surface-1">
        <table className="min-w-full text-xs font-mono">
          <thead>
            <tr className="border-b border-linear-hairline bg-linear-surface-2/60">
              <th className="py-1.5 px-3 text-left text-[10px] uppercase tracking-wider text-linear-ink-muted font-semibold w-32">
                Field
              </th>
              {oldValue !== null && (
                <th className="py-1.5 px-3 text-left text-[10px] uppercase tracking-wider text-grafana-orange/80 font-semibold">
                  Before
                </th>
              )}
              {newValue !== null && (
                <th className="py-1.5 px-3 text-left text-[10px] uppercase tracking-wider text-linear-success/80 font-semibold">
                  After
                </th>
              )}
            </tr>
          </thead>
          <tbody>
            {fields.map((field) => (
              <tr
                key={field.key}
                className={`border-b border-linear-hairline/60 last:border-0 ${
                  field.changed ? 'bg-grafana-orange/5' : ''
                }`}
              >
                <td className="py-1.5 px-3 text-linear-ink-muted align-top whitespace-nowrap">
                  {field.key}
                </td>
                {oldValue !== null && (
                  <td className="py-1.5 px-3 align-top break-all">
                    <span
                      className={
                        field.changed
                          ? 'text-grafana-orange/90 line-through decoration-grafana-orange/50'
                          : 'text-linear-ink-muted'
                      }
                    >
                      {renderValue(field.oldVal)}
                    </span>
                  </td>
                )}
                {newValue !== null && (
                  <td className="py-1.5 px-3 align-top break-all">
                    <span
                      className={
                        field.changed
                          ? 'text-linear-success font-semibold'
                          : 'text-linear-ink-muted'
                      }
                    >
                      {renderValue(field.newVal)}
                    </span>
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
