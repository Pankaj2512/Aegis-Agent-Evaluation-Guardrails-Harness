export type Theme = "dark" | "light";

export const THEME_STORAGE_KEY = "aegis-theme";

export function getStoredTheme(): Theme {
  if (typeof window === "undefined") return "dark";
  try {
    const raw = localStorage.getItem(THEME_STORAGE_KEY);
    if (raw === "light" || raw === "dark") return raw;
  } catch {
    /* ignore */
  }
  return "dark";
}

/** Apply theme class + color-scheme on <html>. Safe on server (no-op). */
export function applyTheme(theme: Theme): void {
  if (typeof document === "undefined") return;
  const root = document.documentElement;
  root.classList.toggle("light", theme === "light");
  root.classList.toggle("dark", theme === "dark");
  root.style.colorScheme = theme;
  // Keep mobile browser chrome roughly in sync. Update every theme-color meta
  // and drop any media attribute so the OS scheme can't override our choice.
  const content = theme === "light" ? "#e9e5de" : "#10110f";
  const metas = document.querySelectorAll('meta[name="theme-color"]');
  metas.forEach((meta) => {
    meta.setAttribute("content", content);
    meta.removeAttribute("media");
  });
}

export function persistTheme(theme: Theme): void {
  try {
    localStorage.setItem(THEME_STORAGE_KEY, theme);
  } catch {
    /* ignore */
  }
}
