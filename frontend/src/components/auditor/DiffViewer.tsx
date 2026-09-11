
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
      <p className="text-xs text-slate-600 italic py-2">No field-level diff available.</p>
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
        <span className="text-[10px] uppercase tracking-wider font-semibold text-slate-600">
          {operation === 'INSERT'
            ? 'New record'
            : operation === 'DELETE'
            ? 'Deleted record'
            : `${changedCount} field${changedCount !== 1 ? 's' : ''} changed`}
        </span>
        <div className="flex items-center space-x-3 text-[10px]">
          {oldValue !== null && (
            <span className="flex items-center space-x-1">
              <span className="w-2 h-2 rounded-sm bg-red-500/40 border border-red-500/60" />
              <span className="text-slate-600">Before</span>
            </span>
          )}
          {newValue !== null && (
            <span className="flex items-center space-x-1">
              <span className="w-2 h-2 rounded-sm bg-emerald-500/40 border border-emerald-500/60" />
              <span className="text-slate-600">After</span>
            </span>
          )}
        </div>
      </div>

      {/* Table */}
      <div className="overflow-x-auto rounded-lg border border-slate-700/40">
        <table className="min-w-full text-xs font-mono">
          <thead>
            <tr className="border-b border-slate-700/40 bg-slate-900/40">
              <th className="py-1.5 px-3 text-left text-[10px] uppercase tracking-wider text-slate-600 font-semibold w-32">
                Field
              </th>
              {oldValue !== null && (
                <th className="py-1.5 px-3 text-left text-[10px] uppercase tracking-wider text-red-500/60 font-semibold">
                  Before
                </th>
              )}
              {newValue !== null && (
                <th className="py-1.5 px-3 text-left text-[10px] uppercase tracking-wider text-emerald-500/60 font-semibold">
                  After
                </th>
              )}
            </tr>
          </thead>
          <tbody>
            {fields.map((field) => (
              <tr
                key={field.key}
                className={`border-b border-slate-800/50 last:border-0 ${
                  field.changed ? 'bg-amber-500/3' : ''
                }`}
              >
                <td className="py-1.5 px-3 text-slate-500 align-top whitespace-nowrap">
                  {field.key}
                </td>
                {oldValue !== null && (
                  <td className="py-1.5 px-3 align-top break-all">
                    <span
                      className={
                        field.changed
                          ? 'text-red-400/80 line-through decoration-red-500/40'
                          : 'text-slate-500'
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
                          ? 'text-emerald-400 font-semibold'
                          : 'text-slate-500'
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
