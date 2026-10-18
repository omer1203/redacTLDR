/** The API writes `datetime.utcnow()` without an offset; read such values as UTC, not local time. */
export function formatUtc(value: string | null | undefined): string {
  if (!value) {
    return "—";
  }
  const hasZone = /[zZ]|[+-]\d{2}:?\d{2}$/.test(value);
  const timestamp = Date.parse(hasZone ? value : `${value}Z`);
  return Number.isNaN(timestamp) ? value : new Date(timestamp).toLocaleString();
}

export function formatBytes(bytes: number | null | undefined): string {
  if (bytes == null) {
    return "—";
  }
  if (bytes < 1024) {
    return `${bytes} B`;
  }
  if (bytes < 1024 * 1024) {
    return `${Math.round(bytes / 1024)} KB`;
  }
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}
