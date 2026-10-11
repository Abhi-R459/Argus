
import { AlertTriangle, ShieldAlert } from 'lucide-react';

interface DiffField {
  key: string;
  oldVal: unknown;
  newVal: unknown;
  changed: boolean;
  isAnomalous?: boolean;
  changeType?: 'Added' | 'Removed' | 'Changed';
}

interface DiffViewerProps {
  oldValue: Record<string, unknown> | null;
  newValue: Record<string, unknown> | null;
  /** Operation context — drives the header label */
  operation?: 'INSERT' | 'UPDATE' | 'DELETE';
  /** Whether this row is flagged as tampered/compromised */
  isTampered?: boolean;
  /** Optional forensic error details from verification/anchor check */
  tamperDetails?: string | null;
  /** Sequence ID of the block */
  sequenceId?: number;
  /** oldValue is the original stored payload captured before a local attack. */
  forensicComparison?: boolean;
}

function renderValue(val: unknown): string {
  if (val === null || val === undefined) return '—';
  if (typeof val === 'object') return JSON.stringify(val);
  return String(val);
}

const ANOMALY_KEY_REGEX = /^(_|tamper|unauthorized|recompute|bonus|forged|fake|malicious)/i;

function isAnomalousKey(key: string): boolean {
  return (
    ANOMALY_KEY_REGEX.test(key) ||
    key.toLowerCase().includes('tamper') ||
    key.toLowerCase().includes('recompute')
  );
}

export default function DiffViewer({
  oldValue,
  newValue,
  operation,
  isTampered = false,
  tamperDetails,
  sequenceId,
  forensicComparison = false,
}: DiffViewerProps) {
  const allKeys = Array.from(
    new Set([
      ...Object.keys(oldValue ?? {}),
      ...Object.keys(newValue ?? {}),
    ])
  );

  const fields: DiffField[] = allKeys.map((key) => {
    const ov = oldValue?.[key];
    const nv = newValue?.[key];
    const anomalous = isAnomalousKey(key);
    const changed = JSON.stringify(ov) !== JSON.stringify(nv);
    return {
      key,
      oldVal: ov,
      newVal: nv,
      changed,
      isAnomalous: anomalous,
      changeType: ov === undefined ? 'Added' : nv === undefined ? 'Removed' : 'Changed',
    };
  });

  const anomalousFields = fields.filter((f) => f.isAnomalous && (!forensicComparison || f.changed));
  const displayedFields = forensicComparison ? fields.filter((field) => field.changed) : fields;
  const changedCount = fields.filter((f) => f.changed).length;
  const addedCount = fields.filter((f) => f.changed && f.changeType === 'Added').length;
  const removedCount = fields.filter((f) => f.changed && f.changeType === 'Removed').length;
  const modifiedCount = fields.filter((f) => f.changed && f.changeType === 'Changed').length;
  const showTamperAlert = isTampered || anomalousFields.length > 0;

  if (allKeys.length === 0) {
    return (
      <div className="space-y-2">
        {showTamperAlert && (
          <div className="rounded-lg border border-red-500/40 bg-linear-surface-1 p-3.5 space-y-2 shadow-sm">
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-2 text-red-400 font-bold tracking-tight">
                <ShieldAlert className="w-4 h-4 text-red-400 flex-shrink-0" />
                <span>CRYPTOGRAPHIC INTEGRITY BREACH DETECTED</span>
              </div>
              {sequenceId !== undefined && (
                <span className="text-[10px] font-mono uppercase bg-red-500/20 text-red-300 border border-red-500/40 px-2 py-0.5 rounded font-bold">
                  Block #{sequenceId}
                </span>
              )}
            </div>
            <p className="text-red-200/90 text-xs">
              {tamperDetails || 'This audit record was altered out-of-band via direct database mutation. The cryptographic verification engine flagged a discrepancy.'}
            </p>
          </div>
        )}
        <p className="text-xs text-linear-ink-muted italic py-2">No field-level diff available.</p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {/* Forensic Tamper Alert Banner */}
      {showTamperAlert && (
        <div className="rounded-lg border border-red-500/40 bg-linear-surface-1 p-3.5 space-y-2.5 shadow-sm">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-2 text-red-400 font-bold tracking-tight">
              <ShieldAlert className="w-4 h-4 text-red-400 flex-shrink-0" />
              <span>CRYPTOGRAPHIC INTEGRITY BREACH DETECTED</span>
            </div>
            {sequenceId !== undefined && (
              <span className="text-[10px] font-mono uppercase bg-red-500/20 text-red-300 border border-red-500/40 px-2 py-0.5 rounded font-bold">
                Block #{sequenceId}
              </span>
            )}
          </div>

          <p className="text-red-200/90 text-xs leading-relaxed">
            {tamperDetails ||
              (anomalousFields.length > 0
                ? 'Unauthorized out-of-band mutation detected. Malicious or injected payload attributes were inserted directly into PostgreSQL audit_log via raw SQL.'
                : 'Cryptographic hash chain or anchor store mismatch detected on this block.')}
          </p>

          {anomalousFields.length > 0 && !forensicComparison && (
            <div className="pt-2 border-t border-red-500/20">
              <div className="flex items-center space-x-1.5 text-[10px] uppercase tracking-wider font-semibold text-red-300 mb-1.5">
                <AlertTriangle className="w-3.5 h-3.5 text-amber-400" />
                <span>Malicious Injected Fields Detected in Payload:</span>
              </div>
              <div className="flex flex-wrap gap-1.5">
                {anomalousFields.map((f) => (
                  <span
                    key={f.key}
                    className="inline-flex items-center space-x-1 font-mono text-[11px] bg-red-900/40 text-red-200 border border-red-600/50 px-2 py-0.5 rounded"
                  >
                    <span className="font-semibold text-red-400">{f.key}:</span>
                    <span>{renderValue(f.newVal)}</span>
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Header */}
      <div className="flex items-center justify-between mb-1">
        <span className="text-[10px] uppercase tracking-wider font-semibold text-linear-ink-muted">
          {forensicComparison
            ? `${changedCount} payload field${changedCount === 1 ? '' : 's'} changed`
            : operation === 'INSERT'
            ? 'New record'
            : operation === 'DELETE'
            ? 'Deleted record'
            : `${changedCount} field${changedCount !== 1 ? 's' : ''} changed`}
        </span>
        <div className="flex items-center space-x-3 text-[10px]">
          {oldValue !== null && (
            <span className="flex items-center space-x-1">
              <span className="w-2 h-2 rounded-sm bg-status-warning/30 border border-status-warning/60" />
              <span className="text-linear-ink-muted">{forensicComparison ? 'Before attack' : 'Before'}</span>
            </span>
          )}
          {newValue !== null && (
            <span className="flex items-center space-x-1">
              <span className="w-2 h-2 rounded-sm bg-linear-success/30 border border-linear-success/60" />
              <span className="text-linear-ink-muted">{forensicComparison ? 'After attack' : 'After'}</span>
            </span>
          )}
        </div>
      </div>

      {!forensicComparison && operation === 'INSERT' && (
        <p className="text-[11px] text-linear-ink-muted">
          No prior row exists for this INSERT event. The before/after attack comparison appears on the exact row captured by an active local attack snapshot.
        </p>
      )}

      {forensicComparison && changedCount > 0 && (
        <p className="text-[11px] text-linear-ink-muted">
          {addedCount > 0 && `${addedCount} added`}
          {addedCount > 0 && (removedCount > 0 || modifiedCount > 0) ? ' · ' : ''}
          {removedCount > 0 && `${removedCount} removed`}
          {removedCount > 0 && modifiedCount > 0 ? ' · ' : ''}
          {modifiedCount > 0 && `${modifiedCount} existing value${modifiedCount === 1 ? '' : 's'} modified`}
          {modifiedCount === 0 && ' · No existing values were modified.'}
          {' '}Unchanged fields are omitted.
        </p>
      )}

      {/* Table */}
      {forensicComparison && changedCount === 0 ? (
        <div className="rounded-lg border border-linear-hairline bg-linear-surface-1 p-4 text-xs text-linear-ink-muted">
          The saved before-attack payload and stored payload have no field-level differences.
        </div>
      ) : <div className="overflow-x-auto rounded-lg border border-linear-hairline bg-linear-surface-1">
        <table className="min-w-full text-xs font-mono">
          <thead>
            <tr className="border-b border-linear-hairline bg-linear-surface-2/60">
              <th className="py-1.5 px-3 text-left text-[10px] uppercase tracking-wider text-linear-ink-muted font-semibold w-40">
                Field
              </th>
              {oldValue !== null && (
                <th className="py-1.5 px-3 text-left text-[10px] uppercase tracking-wider text-status-warning/80 font-semibold">
                  {forensicComparison ? 'Before attack' : 'Before'}
                </th>
              )}
              {newValue !== null && (
                <th className="py-1.5 px-3 text-left text-[10px] uppercase tracking-wider text-linear-success/80 font-semibold">
                  {forensicComparison ? 'After attack' : 'After'}
                </th>
              )}
            </tr>
          </thead>
          <tbody>
            {displayedFields.map((field) => {
              const isFieldAnomalous = field.isAnomalous;
              return (
                <tr
                  key={field.key}
                  className={`border-b border-linear-hairline/60 last:border-0 ${
                    isFieldAnomalous
                      ? 'bg-red-500/10 border-red-500/30'
                      : field.changed
                      ? 'bg-status-warning/5'
                      : ''
                  }`}
                >
                  <td className="py-2 px-3 align-top whitespace-nowrap">
                    <div className="flex items-center space-x-1.5">
                      {isFieldAnomalous && (
                        <AlertTriangle className="w-3.5 h-3.5 text-red-400 flex-shrink-0" />
                      )}
                      <span
                        className={
                          isFieldAnomalous
                            ? 'text-red-300 font-bold'
                            : 'text-linear-ink-muted'
                        }
                      >
                        {field.key}
                      </span>
                      {forensicComparison && field.changeType && (
                        <span className={`text-[9px] uppercase font-mono px-1 py-0.5 rounded border ${
                          field.changeType === 'Added'
                            ? 'text-emerald-300 bg-emerald-500/10 border-emerald-500/30'
                            : field.changeType === 'Removed'
                            ? 'text-amber-300 bg-amber-500/10 border-amber-500/30'
                            : 'text-sky-300 bg-sky-500/10 border-sky-500/30'
                        }`}>
                          {field.changeType}
                        </span>
                      )}
                      {isFieldAnomalous && (
                        <span className="text-[9px] uppercase font-mono px-1 py-0.5 rounded bg-red-500/20 text-red-300 border border-red-500/40 font-semibold ml-1">
                          Injected Field
                        </span>
                      )}
                    </div>
                  </td>
                  {oldValue !== null && (
                    <td className="py-2 px-3 align-top break-all">
                      <span
                        className={
                          isFieldAnomalous
                            ? 'text-red-400 font-medium'
                            : field.changed
                            ? 'text-status-warning/90 line-through decoration-status-warning/50'
                            : 'text-linear-ink-muted'
                        }
                      >
                        {forensicComparison && field.changeType === 'Added' ? '— (not present)' : renderValue(field.oldVal)}
                      </span>
                    </td>
                  )}
                  {newValue !== null && (
                    <td className="py-2 px-3 align-top break-all">
                      <span
                        className={
                          isFieldAnomalous
                            ? 'text-red-300 font-bold bg-red-950/40 px-1.5 py-0.5 rounded border border-red-500/40 inline-block'
                            : field.changed
                            ? 'text-linear-success font-semibold'
                            : 'text-linear-ink-muted'
                        }
                      >
                        {forensicComparison && field.changeType === 'Removed' ? '— (removed)' : renderValue(field.newVal)}
                      </span>
                    </td>
                  )}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      }
    </div>
  );
}

