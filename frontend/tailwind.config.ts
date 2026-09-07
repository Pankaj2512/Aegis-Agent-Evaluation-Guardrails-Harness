import type { Config } from "tailwindcss";
// v3 counterpart of tw-animate-css: supplies animate-in/out, fade-*, zoom-*,
// slide-in-from-* used by the Radix overlay primitives.
import tailwindcssAnimate from "tailwindcss-animate";

/**
 * Token colors are CSS vars (hex), which Tailwind cannot alpha-compose —
 * `bg-destructive/20` would silently compile to nothing. Emitting color-mix()
 * makes every /NN opacity modifier work against the runtime theme value.
 */
type WithAlphaParams = { opacityValue?: string };
const varColor = (variable: string) =>
  // Function colors work at runtime but aren't in Tailwind's TS types.
  (({ opacityValue }: WithAlphaParams = {}) =>
    opacityValue === undefined || opacityValue === "1"
      ? `var(${variable})`
      : `color-mix(in srgb, var(${variable}) calc(${opacityValue} * 100%), transparent)`) as unknown as string;


const config: Config = {
  // Theme is class-driven (boot script sets .dark/.light on <html>);
  // media-strategy dark: variants would track the OS instead of the app.
  darkMode: "class",
  content: [
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        bg: varColor("--bg"),
        background: varColor("--bg"),
        foreground: varColor("--fg"),
        muted: {
          DEFAULT: varColor("--fg-muted"),
          foreground: varColor("--fg-muted"),
        },
        subtle: varColor("--fg-subtle"),
        surface: {
          DEFAULT: varColor("--surface"),
          elevated: varColor("--surface-elevated"),
          overlay: varColor("--surface-overlay"),
          glass: varColor("--surface-glass"),
          hover: varColor("--surface-hover"),
          input: varColor("--surface-input"),
        },
        border: {
          DEFAULT: varColor("--border"),
          mid: varColor("--border-mid"),
          strong: varColor("--border-strong"),
        },
        primary: {
          DEFAULT: varColor("--primary"),
          foreground: varColor("--primary-foreground"),
          muted: varColor("--primary-muted"),
          glow: varColor("--primary-glow"),
          50: varColor("--primary-50"),
          100: varColor("--primary-100"),
          200: varColor("--primary-200"),
          300: varColor("--primary-300"),
          400: varColor("--primary-400"),
          500: varColor("--primary-500"),
          600: varColor("--primary-600"),
          700: varColor("--primary-700"),
          800: varColor("--primary-800"),
          900: varColor("--primary-900"),
        },
        accent: {
          DEFAULT: varColor("--accent"),
          foreground: varColor("--accent-foreground"),
          muted: varColor("--accent-muted"),
          glow: varColor("--accent-glow"),
          300: varColor("--accent-300"),
          400: varColor("--accent-400"),
          500: varColor("--accent-500"),
          600: varColor("--accent-600"),
        },
        active: {
          DEFAULT: varColor("--active"),
          glow: varColor("--active-glow"),
        },
        destructive: {
          DEFAULT: varColor("--destructive"),
          foreground: varColor("--destructive-foreground"),
          glow: varColor("--destructive-glow"),
        },
        success: {
          DEFAULT: varColor("--success"),
          glow: varColor("--success-glow"),
        },
        warning: {
          DEFAULT: varColor("--warning"),
          glow: varColor("--warning-glow"),
        },
        ring: varColor("--ring"),
        cat: {
          trigger: varColor("--cat-trigger"),
          logic: varColor("--cat-logic"),
          llm: varColor("--cat-llm"),
          data: varColor("--cat-data"),
          integration: varColor("--cat-integration"),
          quality: varColor("--cat-quality"),
          flow: varColor("--cat-flow"),
        },
      },
      borderRadius: {
        sm: "var(--radius-sm)",
        md: "var(--radius-md)",
        lg: "var(--radius-lg)",
        xl: "var(--radius-xl)",
        "2xl": "var(--radius-2xl)",
      },
      boxShadow: {
        "elev-1": "var(--elev-1)",
        "elev-2": "var(--elev-2)",
        "elev-3": "var(--elev-3)",
        "glow-primary": "var(--elev-glow-primary)",
        "glow-accent": "var(--elev-glow-accent)",
        "glow-active": "var(--elev-glow-active)",
        "glow-success": "var(--elev-glow-success)",
        "glow-destructive": "var(--elev-glow-destructive)",
        "glow-warning": "var(--elev-glow-warning)",
      },
      fontSize: {
        "2xs": ["10px", "14px"],
      },
      fontFamily: {
        sans: ["var(--font-geist-sans)", "system-ui", "sans-serif"],
        mono: ["var(--font-geist-mono)", "ui-monospace", "monospace"],
      },
      transitionTimingFunction: {
        "out-soft": "var(--ease-out)",
        "in-out-soft": "var(--ease-in-out)",
      },
      transitionDuration: {
        instant: "120ms",
        fast: "200ms",
        base: "320ms",
        slow: "500ms",
        // Motion contract tokens (mirror --dur-* in globals.css): duration-1/2/3
        1: "var(--dur-1)",
        2: "var(--dur-2)",
        3: "var(--dur-3)",
      },
      keyframes: {
        "fade-in": {
          "0%": { opacity: "0", transform: "translateY(4px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        "stagger-fade": {
          "0%": { opacity: "0", transform: "translateY(8px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        "glow-pulse": {
          "0%, 100%": { boxShadow: "0 0 0 1px var(--border-strong)" },
          "50%": { boxShadow: "0 0 0 1px color-mix(in srgb, var(--fg) 36%, transparent)" },
        },
        "glow-pulse-warning": {
          "0%, 100%": { boxShadow: "0 0 0 1px color-mix(in srgb, var(--warning) 42%, transparent)" },
          "50%": { boxShadow: "0 0 0 1px color-mix(in srgb, var(--warning) 72%, transparent)" },
        },
        "edge-flow": {
          "0%": { strokeDashoffset: "20" },
          "100%": { strokeDashoffset: "0" },
        },
        "edge-settle": {
          "0%": { strokeOpacity: "0.9", strokeWidth: "4" },
          "100%": { strokeOpacity: "0", strokeWidth: "2" },
        },
        "panel-in": {
          "0%": { opacity: "0", transform: "translateX(16px)" },
          "100%": { opacity: "1", transform: "translateX(0)" },
        },
      },
      animation: {
        "fade-in": "fade-in 320ms var(--ease-out) forwards",
        "stagger-fade": "stagger-fade 400ms var(--ease-out) forwards",
        "glow-pulse": "glow-pulse 1.6s var(--ease-in-out) infinite",
        "glow-pulse-warning": "glow-pulse-warning 1.6s var(--ease-in-out) infinite",
        "edge-flow": "edge-flow 1.5s linear infinite",
        "edge-settle": "edge-settle 0.7s var(--ease-out) forwards",
        "panel-in": "panel-in 220ms var(--ease-out)",
      },
      backdropBlur: {
        xs: "2px",
      },
    },
  },
  plugins: [tailwindcssAnimate],
};
export default config;
