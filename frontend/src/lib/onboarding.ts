const STORAGE_KEY = "aegis-onboarding";

export type OnboardingKey =
  | "dashboard"
  | "canvas"
  | "canvas-tour"
  | "observability"
  | "guardrails"
  | "templates";

type OnboardingState = Partial<Record<OnboardingKey, boolean>>;

function readState(): OnboardingState {
  if (typeof window === "undefined") return {};
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEY) || "{}") as OnboardingState;
  } catch {
    return {};
  }
}

function writeState(state: OnboardingState) {
  if (typeof window === "undefined") return;
  localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
}

export function isOnboardingDismissed(key: OnboardingKey): boolean {
  return Boolean(readState()[key]);
}

export function dismissOnboarding(key: OnboardingKey) {
  writeState({ ...readState(), [key]: true });
}

export function resetOnboarding(key?: OnboardingKey) {
  if (typeof window === "undefined") return;
  if (!key) {
    localStorage.removeItem(STORAGE_KEY);
    return;
  }
  const state = readState();
  delete state[key];
  writeState(state);
}