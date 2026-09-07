export function traceUrl(traceId: string, uiBaseUrl?: string | null): string | null {
  if (!uiBaseUrl) return null;
  if (uiBaseUrl.includes("{trace_id}")) {
    return uiBaseUrl.replace("{trace_id}", traceId);
  }
  return `${uiBaseUrl.replace(/\/$/, "")}/trace/${traceId}`;
}