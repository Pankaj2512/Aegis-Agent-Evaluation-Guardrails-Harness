const API_KEY_STORAGE = "aegis_api_key";
const API_KEY_AUDIT_STORAGE = "aegis_api_key_audit";
const MAX_AUDIT_ENTRIES = 20;

export type ApiKeyAuditAction = "set" | "rotate" | "clear";

export type ApiKeyAuditEntry = {
  action: ApiKeyAuditAction;
  at: string;
  keyHint: string | null;
};

function keyHint(key: string | null): string | null {
  if (!key) return null;
  const trimmed = key.trim();
  if (trimmed.length <= 4) return "••••";
  return `••••${trimmed.slice(-4)}`;
}

function readAuditLog(): ApiKeyAuditEntry[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = localStorage.getItem(API_KEY_AUDIT_STORAGE);
    if (!raw) return [];
    const parsed = JSON.parse(raw) as ApiKeyAuditEntry[];
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function appendAuditEntry(action: ApiKeyAuditAction, key: string | null): void {
  if (typeof window === "undefined") return;
  const entry: ApiKeyAuditEntry = {
    action,
    at: new Date().toISOString(),
    keyHint: keyHint(key),
  };
  const next = [entry, ...readAuditLog()].slice(0, MAX_AUDIT_ENTRIES);
  localStorage.setItem(API_KEY_AUDIT_STORAGE, JSON.stringify(next));
}

export function getApiKey(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(API_KEY_STORAGE);
}

export function setApiKey(key: string): void {
  if (typeof window === "undefined") return;
  localStorage.setItem(API_KEY_STORAGE, key);
  appendAuditEntry("set", key);
}

export function rotateApiKey(newKey: string): void {
  if (typeof window === "undefined") return;
  const trimmed = newKey.trim();
  if (!trimmed) return;
  localStorage.setItem(API_KEY_STORAGE, trimmed);
  appendAuditEntry("rotate", trimmed);
}

export function clearApiKey(): void {
  if (typeof window === "undefined") return;
  localStorage.removeItem(API_KEY_STORAGE);
  appendAuditEntry("clear", null);
}

export function getApiKeyAuditLog(): ApiKeyAuditEntry[] {
  return readAuditLog();
}

export function authHeaders(): Record<string, string> {
  const key = getApiKey();
  if (!key) return {};
  return { "X-Aegis-API-Key": key };
}