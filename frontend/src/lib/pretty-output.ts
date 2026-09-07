/** Pretty-print node/run output when it is JSON; pass through otherwise. */
export function formatOutput(raw: string): { text: string; isJson: boolean } {
  const trimmed = raw.trim();
  if (trimmed.startsWith("{") || trimmed.startsWith("[")) {
    try {
      return { text: JSON.stringify(JSON.parse(trimmed), null, 2), isJson: true };
    } catch {
      // fall through — looked like JSON but wasn't
    }
  }
  return { text: raw, isJson: false };
}
