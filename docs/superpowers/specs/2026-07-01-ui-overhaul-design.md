# Aegis UI overhaul — implementation spec

You are a coding agent executing a large UI/UX overhaul of the Aegis frontend. This document is your complete brief. Read it end-to-end before touching code.

## What you're building

A Vercel/Cursor-grade reskin of the Aegis app. The visual style is **glass & glow**: translucent surfaces with backdrop blur, ambient indigo/violet gradients, depth via soft shadows and selective primary-color glows on important surfaces. Motion is purposeful — five vocabulary patterns applied consistently. Component primitives migrate from hand-rolled to shadcn/ui (Radix-backed). The canvas — the product's hero surface — gets a full custom re-skin: glass chrome, animated gradient edges during runs, category-colored nodes, polished inspector.

Brand identity stays: indigo `#6366f1` primary, violet `#8b5cf6` accent. Dark mode only. The product audience is internal/the developer themselves — that means we can be opinionated and craft-driven instead of safe.

## Working agreements

You will execute this in **five sequential phases**, each ending in a shippable state. Do not skip phases. Do not reorder. The app must be visually coherent (even if some pages are mid-migration) after every commit.

- **One commit per logical group** within a phase. Commit messages: `feat(ui-overhaul): <phase>.<sub-piece> — <one-line>` with file refs in the body.
- **`cd frontend && npm run typecheck && npm run lint` must be clean after every commit.** Don't ship red.
- **Run `npm run dev` and verify in a real browser after every phase.** Visual regressions don't show up in tests.
- **Use the existing P0-P3 work as the floor, not the ceiling.** A11y patterns, validation, error copy already shipped — don't undo them while restyling.
- **No new dependencies beyond what's listed in Phase 1.** If you find yourself wanting one, stop and ask.
- **No backend changes.** Every feature in this spec is implementable with the current REST/SSE surface. If you think you need a backend change, you've misread — re-read the relevant section.
- **Do not write summary docs into the repo as you go.** Use TodoWrite to track. Final report is a single message at the end of each phase.
- **No emojis in UI copy or commit messages.** They're not part of the visual language.

### Anti-goals

- No light mode work. Tokens may include light values later but only dark gets tested and shipped now.
- No SSR/RSC migration. Pages stay client components where they are now.
- No state-management library introduction. TanStack Query stays the data layer.
- No new icon set. Lucide stays.
- No CSS-in-JS. Tailwind + CSS variables only.
- No "while I was there" refactors of business logic. If a component has bad code, restyle it; don't rewrite it.

### Final report after each phase

A single message containing:
- Commit SHAs shipped, grouped by sub-piece.
- Anything deferred and why.
- Anything that turned out to be already done.
- Visual issues you noticed but didn't fix (next-phase candidates).
- Performance numbers if relevant (bundle size delta, paint times for canvas-heavy pages).

---

# Repo context

- **Path:** `/Users/himanshu/Git/aegis`
- **Frontend root:** `frontend/`
- **Stack:** Next.js 14 (App Router) · React 18 · TypeScript · Tailwind 3.4 · React Flow 12 · TanStack Query 5 · Sonner · lucide-react
- **Backend:** FastAPI + Postgres (do not touch)
- **Test/check:** `cd frontend && npm run typecheck && npm run lint`
- **Dev server:** `cd frontend && npm run dev` (port 3000)

Existing token system lives in `frontend/src/app/globals.css` (CSS variables) + `frontend/tailwind.config.ts` (color aliases). Existing primitives live in `frontend/src/components/ui/`. Canvas lives in `frontend/src/components/canvas/`.

---

# Phase 1 — Foundation (~3-4 days)

**Goal:** install design tokens, motion system, shadcn primitives, and reusable motion components. Nothing visually significant should change yet — but everything downstream depends on this.

**Exit criteria:** every route in the app renders correctly with the new tokens applied. `<GlassCard>`, `<GlowCard>`, motion primitives, and migrated shadcn primitives are available. App still looks 95% like before — visible polish comes in Phase 2.

## 1.1 — Color tokens

Update `frontend/src/app/globals.css`. Replace the `:root` block with this complete token set. Treat any current variable not listed below as removed (sweep callers if needed).

```css
:root {
  /* Page background — slightly deeper than current */
  --bg: #08080a;
  --bg-grad-1: radial-gradient(ellipse 80% 50% at 30% -10%, rgba(99, 102, 241, 0.18), transparent 60%);
  --bg-grad-2: radial-gradient(ellipse 60% 40% at 85% 60%, rgba(139, 92, 246, 0.10), transparent 60%);

  /* Surfaces — semi-translucent, designed to sit on the ambient gradient */
  --surface: rgba(20, 20, 23, 0.72);
  --surface-elevated: rgba(28, 28, 32, 0.78);
  --surface-glass: rgba(255, 255, 255, 0.04);
  --surface-hover: rgba(255, 255, 255, 0.06);
  --surface-input: rgba(20, 20, 23, 0.85);

  /* Borders — hairlines on glass */
  --border: rgba(255, 255, 255, 0.08);
  --border-strong: rgba(255, 255, 255, 0.14);
  --border-glow: rgba(99, 102, 241, 0.32);

  /* Text */
  --fg: #fafafa;
  --fg-muted: #b4b4b8;
  --fg-subtle: #71717a;

  /* Brand — indigo primary, violet accent */
  --primary: #6366f1;
  --primary-50: #eef2ff;
  --primary-100: #e0e7ff;
  --primary-200: #c7d2fe;
  --primary-300: #a5b4fc;
  --primary-400: #818cf8;
  --primary-500: #6366f1;
  --primary-600: #4f46e5;
  --primary-700: #4338ca;
  --primary-800: #3730a3;
  --primary-900: #312e81;
  --primary-foreground: #ffffff;
  --primary-muted: rgba(99, 102, 241, 0.12);
  --primary-glow: rgba(99, 102, 241, 0.45);

  --accent: #8b5cf6;
  --accent-50: #f5f3ff;
  --accent-300: #c4b5fd;
  --accent-400: #a78bfa;
  --accent-500: #8b5cf6;
  --accent-600: #7c3aed;
  --accent-foreground: #ffffff;
  --accent-muted: rgba(139, 92, 246, 0.12);
  --accent-glow: rgba(139, 92, 246, 0.4);

  /* Status — color + glow companion */
  --destructive: #ef4444;
  --destructive-glow: rgba(239, 68, 68, 0.35);
  --success: #22c55e;
  --success-glow: rgba(34, 197, 94, 0.3);
  --warning: #f59e0b;
  --warning-glow: rgba(245, 158, 11, 0.35);

  /* Focus ring — opaque, high contrast (P0.7 already shipped this fix) */
  --ring: #818cf8;

  /* Node-category colors — used by canvas */
  --cat-trigger: #6366f1;
  --cat-logic: #06b6d4;
  --cat-llm: #8b5cf6;
  --cat-data: #10b981;
  --cat-integration: #f59e0b;
  --cat-quality: #f43f5e;
  --cat-flow: #64748b;

  /* React Flow specifics (existing) */
  --canvas-grid: #232936;
  --canvas-edge: #475569;
  --canvas-edge-active: #fbbf24;
  --canvas-edge-failed: #f43f5e;
  --canvas-connection: #6366f1;

  /* Radius scale — richer than current */
  --radius-sm: 6px;
  --radius-md: 10px;
  --radius-lg: 14px;
  --radius-xl: 20px;
  --radius-2xl: 28px;
  --radius: var(--radius-lg);  /* default for back-compat with existing classes */

  /* Elevation system — composed shadows including inset highlight */
  --elev-1: 0 1px 0 rgba(255, 255, 255, 0.04) inset, 0 1px 2px rgba(0, 0, 0, 0.4);
  --elev-2: 0 0 0 1px rgba(255, 255, 255, 0.04) inset, 0 4px 16px rgba(0, 0, 0, 0.4);
  --elev-3: 0 0 0 1px rgba(255, 255, 255, 0.05) inset, 0 12px 40px rgba(0, 0, 0, 0.5);
  --elev-glow-primary: 0 0 0 1px rgba(99, 102, 241, 0.25), 0 0 32px rgba(99, 102, 241, 0.18);
  --elev-glow-accent: 0 0 0 1px rgba(139, 92, 246, 0.22), 0 0 32px rgba(139, 92, 246, 0.18);
  --elev-glow-success: 0 0 0 1px rgba(34, 197, 94, 0.25), 0 0 24px rgba(34, 197, 94, 0.18);
  --elev-glow-destructive: 0 0 0 1px rgba(239, 68, 68, 0.3), 0 0 28px rgba(239, 68, 68, 0.2);

  /* Motion timing tokens */
  --ease-out: cubic-bezier(0.16, 1, 0.3, 1);
  --ease-in-out: cubic-bezier(0.65, 0, 0.35, 1);
  --dur-instant: 120ms;
  --dur-fast: 200ms;
  --dur-base: 320ms;
  --dur-slow: 500ms;
}
```

Then update the page-level ambient gradient in the `body` selector to use `var(--bg-grad-1), var(--bg-grad-2)` instead of the inline gradients currently there.

**Verify:** every page still renders. `text-muted` (existing class at globals.css:81-83) must keep working — it references `--muted`, which is renamed to `--fg-muted`. Find every usage of `--muted` and migrate to `--fg-muted` (search both `var(--muted)` and the `muted` Tailwind alias in `tailwind.config.ts`).

## 1.2 — Tailwind config update

Update `frontend/tailwind.config.ts`:

```ts
import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        // Surfaces
        bg: "var(--bg)",
        background: "var(--bg)",              // keep alias for back-compat
        foreground: "var(--fg)",
        muted: {
          DEFAULT: "var(--fg-muted)",
          foreground: "var(--fg-muted)",
        },
        subtle: "var(--fg-subtle)",
        surface: {
          DEFAULT: "var(--surface)",
          elevated: "var(--surface-elevated)",
          glass: "var(--surface-glass)",
          hover: "var(--surface-hover)",
          input: "var(--surface-input)",
        },
        border: {
          DEFAULT: "var(--border)",
          strong: "var(--border-strong)",
          glow: "var(--border-glow)",
        },
        // Brand
        primary: {
          DEFAULT: "var(--primary)",
          foreground: "var(--primary-foreground)",
          muted: "var(--primary-muted)",
          glow: "var(--primary-glow)",
          50: "var(--primary-50)", 100: "var(--primary-100)",
          200: "var(--primary-200)", 300: "var(--primary-300)",
          400: "var(--primary-400)", 500: "var(--primary-500)",
          600: "var(--primary-600)", 700: "var(--primary-700)",
          800: "var(--primary-800)", 900: "var(--primary-900)",
        },
        accent: {
          DEFAULT: "var(--accent)",
          foreground: "var(--accent-foreground)",
          muted: "var(--accent-muted)",
          glow: "var(--accent-glow)",
          300: "var(--accent-300)", 400: "var(--accent-400)",
          500: "var(--accent-500)", 600: "var(--accent-600)",
        },
        // Status
        destructive: { DEFAULT: "var(--destructive)", glow: "var(--destructive-glow)" },
        success: { DEFAULT: "var(--success)", glow: "var(--success-glow)" },
        warning: { DEFAULT: "var(--warning)", glow: "var(--warning-glow)" },
        ring: "var(--ring)",
        // Categories
        cat: {
          trigger: "var(--cat-trigger)",
          logic: "var(--cat-logic)",
          llm: "var(--cat-llm)",
          data: "var(--cat-data)",
          integration: "var(--cat-integration)",
          quality: "var(--cat-quality)",
          flow: "var(--cat-flow)",
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
        "glow-success": "var(--elev-glow-success)",
        "glow-destructive": "var(--elev-glow-destructive)",
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
          "0%, 100%": { boxShadow: "var(--elev-glow-primary)" },
          "50%": { boxShadow: "0 0 0 1px rgba(99,102,241,0.35), 0 0 48px rgba(99,102,241,0.3)" },
        },
        "edge-flow": {
          "0%": { strokeDashoffset: "20" },
          "100%": { strokeDashoffset: "0" },
        },
      },
      animation: {
        "fade-in": "fade-in 320ms var(--ease-out) forwards",
        "stagger-fade": "stagger-fade 400ms var(--ease-out) forwards",
        "glow-pulse": "glow-pulse 1.6s var(--ease-in-out) infinite",
        "edge-flow": "edge-flow 1.5s linear infinite",
      },
      backdropBlur: {
        xs: "2px",
      },
    },
  },
  plugins: [],
};
export default config;
```

## 1.3 — Geist font integration

In `frontend/src/app/layout.tsx`, replace the current font setup with:

```tsx
import { GeistSans } from "geist/font/sans";
import { GeistMono } from "geist/font/mono";
// ...
<html lang="en" className={`${GeistSans.variable} ${GeistMono.variable}`}>
```

Install: `cd frontend && npm install geist`.

Verify the font is actually rendering by opening Chrome DevTools → Computed → font-family on body. Should read `Geist`.

## 1.4 — Type ramp utility classes

Add to `globals.css` under `@layer components`:

```css
.text-display {
  @apply text-[32px] leading-[40px] font-semibold tracking-tight text-foreground;
  letter-spacing: -0.02em;
}
.text-title {
  @apply text-2xl font-semibold tracking-tight text-foreground;
  letter-spacing: -0.015em;
}
.text-heading {
  @apply text-lg font-semibold text-foreground;
  letter-spacing: -0.01em;
}
.text-body-lg {
  @apply text-base text-foreground;
}
.text-body {
  @apply text-sm text-foreground;
}
.text-caption {
  @apply text-xs text-muted;
}
.text-micro {
  @apply text-[11px] font-medium uppercase tracking-[0.06em] text-muted;
}
.text-gradient-primary {
  background: linear-gradient(135deg, var(--primary-300) 0%, var(--accent-300) 100%);
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
}
```

Existing `.text-subtitle`, `.text-caption` may conflict — replace usages with the new ramp before deleting the old classes. Search `frontend/src` for each existing class.

## 1.5 — Install Framer Motion

```bash
cd frontend && npm install framer-motion
```

Build motion primitives at `frontend/src/components/motion/`:

- **`PageEnter.tsx`** — wraps page content, applies fade+lift on mount. Honors `useReducedMotion()`.
- **`StaggerList.tsx`** — wraps children, each direct child gets `motion.div` with staggered delay (40ms, max 8 items, rest snap in instantly).
- **`HoverLift.tsx`** — wraps a card-like child, applies y: -1px and shadow-elev-2 on hover.
- **`NumberTween.tsx`** — takes a `value: number`, tweens the displayed number when value changes (200ms ease-out). Round to integer or one-decimal based on prop.
- **`useGlowPulse.ts`** — hook that returns className `"animate-glow-pulse"` unless `useReducedMotion()` is true (returns ""). Used by canvas active node + live status dots.

Each primitive is small (<60 lines). Export from `frontend/src/components/motion/index.ts`.

## 1.6 — shadcn/ui setup

```bash
cd frontend && npx shadcn@latest init
```

When prompted: TypeScript yes, Style "New York", Base color "Zinc", CSS variables yes. **Crucially, after init, edit `components.json` to point CSS variables to OUR existing tokens** — don't let shadcn overwrite `globals.css`. Specifically:

- shadcn's `--background` → already covered by our `--bg`
- shadcn's `--foreground` → our `--fg`
- shadcn's `--primary` → our `--primary`
- shadcn's `--border` → our `--border`
- shadcn's `--ring` → our `--ring`
- shadcn's `--card` → our `--surface`
- shadcn's `--popover` → our `--surface-elevated`

If shadcn's init overwrote any of our tokens, revert that block from git and add only the alias mappings shadcn needs.

Install these shadcn components, in order:

```bash
npx shadcn@latest add dialog
npx shadcn@latest add popover
npx shadcn@latest add tooltip
npx shadcn@latest add select
npx shadcn@latest add tabs
npx shadcn@latest add dropdown-menu
npx shadcn@latest add sheet
npx shadcn@latest add command
npx shadcn@latest add switch
```

Each lands in `frontend/src/components/ui/`. **Do not delete the existing hand-rolled versions yet.** Migrate callers one by one in later sub-tasks to avoid breaking the app.

After adding, restyle each shadcn component to use our glass aesthetic:

- **Dialog**: content gets `bg-surface-elevated backdrop-blur-xl border-border shadow-elev-3 rounded-xl`. Overlay gets `bg-bg/40 backdrop-blur-xs`.
- **Popover / DropdownMenu**: same surface treatment as Dialog content but with `rounded-lg` and `shadow-elev-2`.
- **Tooltip**: `bg-surface-elevated backdrop-blur-md border-border shadow-elev-1 text-xs px-2.5 py-1.5 rounded-md`.
- **Sheet**: slide-from-right by default. Content uses `bg-surface-elevated backdrop-blur-xl`.
- **Command**: input gets ghost styling, list items hover-state uses `bg-surface-hover`.

## 1.7 — Migrate primitive callers

For each migrated primitive, replace usages of the hand-rolled version. Use these search-and-replace passes:

- `Dialog` from `@/components/ui/dialog` (old) → shadcn `Dialog`. The old one had a slightly different API; adapter shim is fine for one commit, then sweep callers and remove shim.
- Same for `Tooltip`, `Select`, `Popover`.
- The hand-rolled `CommandPalette` at `frontend/src/components/layout/CommandPalette.tsx` gets replaced by a new component using shadcn's `Command`. Preserve current keyboard bindings (Cmd+K), existing actions list, and the `isEditableTarget` guard.

Old files only get deleted when zero callers remain. Run `grep -rn` for each old import path before deleting.

## 1.8 — `<GlassCard>` and `<GlowCard>` primitives

Add to `frontend/src/components/ui/glass-card.tsx`:

```tsx
// GlassCard — the default surface for most content
// Renders: bg-surface backdrop-blur-md border-border shadow-elev-1 rounded-xl

// GlowCard — used for the "important" surface on a page (max 1 per page)
// Renders: bg-surface backdrop-blur-md border-border-glow shadow-glow-primary rounded-xl
// Optional prop: variant = "primary" | "accent" | "success" | "destructive" — swaps the glow color
```

Both accept all standard HTML props + className for caller extensions. Both honor `useReducedMotion()` for any internal hover transitions.

## 1.9 — Phase 1 exit verification

Run through this checklist before marking Phase 1 done:

- [ ] `npm run typecheck && npm run lint` clean
- [ ] `npm run dev`, click through every route in the app; nothing 404s, nothing throws
- [ ] Open DevTools → Computed → confirm `--bg: #08080a` is set on `html`
- [ ] Open DevTools → Network → confirm Geist font loads (not falling back to system)
- [ ] Open a dialog (any page that has one) — confirm shadcn version renders with backdrop blur
- [ ] Open the command palette (Cmd+K) — confirm it still works
- [ ] No console errors

Commit per sub-piece. Phase 1 likely has 8-10 commits.

---

# Phase 2 — Dashboard redesign (~3-4 days)

**Goal:** the dashboard becomes the proof surface. After this phase, the rest of the app should visibly look like the "before" state by comparison.

**Files in scope:**
- `frontend/src/app/page.tsx`
- `frontend/src/components/dashboard/DashboardView.tsx`
- Any sub-components in `frontend/src/components/dashboard/`

**Files you may CREATE:**
- `frontend/src/components/dashboard/HeroGreeting.tsx`
- `frontend/src/components/dashboard/StatCard.tsx` (replaces existing if any)
- `frontend/src/components/dashboard/Sparkline.tsx`
- `frontend/src/components/dashboard/WorkflowCard.tsx`
- `frontend/src/components/dashboard/RecentRunRow.tsx`
- `frontend/src/components/dashboard/LiveDot.tsx`

## 2.1 — Hero greeting

A single horizontal block at the top of the dashboard. Contains:

- Personalized greeting using `text-display`. Format: `"Good morning, {name}"` / `"Good afternoon"` / `"Good evening"` based on local time. Name comes from auth context if available; if not, falls back to `"Good evening"` with no name. The name itself gets `.text-gradient-primary`.
- Single line of secondary info using `text-caption`: `"234 runs · 91% pass rate · last 7 days"`. Pull from existing observability summary API; compute from `summary.run_count`, `summary.eval_passed_count / summary.eval_count`. If data isn't there yet (first-time user), show: `"No runs yet — create your first workflow to get started"`.
- Two primary actions, side-by-side on desktop, stacked on mobile:
  - `[+ New workflow]` — `Button` variant default, leads to `/workflows/new`
  - `[Open last canvas →]` — `Button` variant outline, leads to `/workflows/{last-edited-workflow-id}/edit`. If no recent workflow, hide this button.

The hero has no background card — it sits directly on the page's ambient gradient. Just spacing and typography.

Animate with `<PageEnter>` wrapper. Greeting fades+lifts on mount.

## 2.2 — Stat cards row

Four cards in a row at desktop (1280px+), 2x2 grid on tablet, stacked on mobile.

| Card | Content | Treatment |
|---|---|---|
| Total runs | `<NumberTween>` for the number, trend pill below: `"↗ +12% vs prior 7d"` (color from sign — success green / destructive red / muted neutral) | `<GlassCard>` |
| Pass rate | Big number with `%`. `<NumberTween>`. Subtle inline trend chevron. Number itself uses `.text-gradient-primary` ONLY if pass rate ≥ 80%; below 80% use `text-foreground` (don't celebrate bad numbers). | `<GlowCard variant="primary">` — this is the showpiece card |
| Avg latency | Number in ms or s (format intelligently: <1000ms shows "987ms", ≥1000ms shows "1.2s"). Below: 14-day sparkline using `<Sparkline>`. | `<GlassCard>` |
| Last run | Relative time ("2m ago"). Below: `<LiveDot />` if SSE is connected, else hidden. | `<GlassCard>` |

Each card:
- Padding: `p-5`
- Top row: `<eyebrow>` micro-label (e.g. "TOTAL RUNS")
- Middle: the big number (text-display)
- Bottom row: trend / sparkline / live state

Card width: `flex-1` within a `<StaggerList>` row. Stagger animates the cards in over 160ms total (40ms × 4 cards).

## 2.3 — Sparkline component

`frontend/src/components/dashboard/Sparkline.tsx`. SVG-based, ~24px tall, fills width of its container.

Props:
```ts
type SparklineProps = {
  data: number[];        // 14 data points, oldest first
  color?: string;        // defaults to var(--primary)
  height?: number;       // defaults to 24
  drawOnMount?: boolean; // if true, animates stroke-dashoffset on first render
};
```

Renders:
- A `<polyline>` for the trend line at `stroke-width: 1.5`, full opacity color.
- A `<polygon>` area fill below the line, fillstyle `linear-gradient(180deg, color/0.3 0%, color/0 100%)` via `<linearGradient>` in SVG `<defs>`.
- If `drawOnMount`, the polyline starts with `stroke-dashoffset = perimeter` and animates to 0 over 600ms ease-out.

Data source for the latency sparkline: aggregate `observability_rollups` per-day for 14 days on the frontend. The existing `/api/observability/summary` likely doesn't include 14-day rollups; instead use `/api/observability/quality` or the `runs` endpoint and aggregate. **If the data isn't available without a backend change, render an empty state instead and note it in the phase report — don't fake the data.**

## 2.4 — `<LiveDot>` component

A pulsing dot that signals "SSE is connected". Renders an 8px circle with `bg-success` and `useGlowPulse()`. When disconnected, dot becomes muted and stops pulsing. Subscribes to the existing `ObservabilityStreamProvider`.

## 2.5 — Two-column layout below stats

```
┌────────────────────────────┬─────────────────────────────────┐
│  WORKFLOWS         [+ New] │  RECENT RUNS              ●live │
│                            │                                  │
│  [search input]            │  Run row                         │
│                            │  Run row                         │
│  ─ Workflow card           │  Run row                         │
│  ─ Workflow card           │  Run row                         │
│  ─ Workflow card           │  ...                             │
│                            │                                  │
│  → View all                │  → View all 234 runs             │
└────────────────────────────┴─────────────────────────────────┘
```

Columns are 50/50 on desktop. On tablet (768-1024px), the columns stay side-by-side but with narrower padding. On mobile, columns stack with Recent Runs ON TOP (it's the more time-sensitive surface).

### Workflows column

- Header: `<eyebrow>` "WORKFLOWS" left, `+ New` button right (icon-only on mobile, label+icon on desktop).
- Search input below header: full-width `Input` with magnifying-glass icon prefix, placeholder `"Search by name or description"`.
- Workflow cards in a `<StaggerList>`, max 6 cards rendered. Each card is a `<WorkflowCard>`.
- "→ View all" link below if `total > 6`, hidden otherwise.

### Recent Runs column

- Header: `<eyebrow>` "RECENT RUNS" left, `<LiveDot />` right.
- Run rows in a `<StaggerList>`, max 8 rows rendered. Each is a `<RecentRunRow>`.
- "→ View all 234 runs" link with `pluralize()` (already exists from P1.12).

## 2.6 — `<WorkflowCard>`

Renders a single workflow as a clickable card. Anatomy:

```
┌─ accent bar (2px, indigo→violet gradient, slides in on hover) ─┐
│  Workflow name                          ⋮ (hover-only menu)    │
│  Optional one-line description                                  │
│                                                                  │
│  ● Last run: 2m ago     5 runs this week                        │
└──────────────────────────────────────────────────────────────────┘
```

- Outer: `<GlassCard>` extended with `<HoverLift>` motion. Cursor pointer.
- The accent bar at top is `h-0.5` and starts at `w-0`, animates to `w-full` on hover with 160ms transition. Use a `::before` pseudo-element on the card with a gradient `from-primary-500 to-accent-500`.
- Header row: name in `text-body-lg font-semibold`, right side has a 3-dot button (only visible on hover, renders a DropdownMenu with Edit / Duplicate / Delete).
- Footer row: status dot (color from last run status — success/destructive/warning) + relative time + a separator + run count this week.
- Whole card is a `Link` to `/workflows/{id}/edit`.

Empty state for the column (zero workflows): glass card with a `+ Create your first workflow` button, helpful copy. Use `<EmptyState>` primitive.

## 2.7 — `<RecentRunRow>`

A single row, not a card. Anatomy:

```
●   Workflow name                       1.2s    2m ago
```

- Status icon (the leftmost dot) — colored per status with `useGlowPulse()` if status is "running".
- Workflow name in `text-body`, truncate with ellipsis.
- Duration in `text-caption font-mono` (mono number alignment).
- Relative time in `text-caption`.
- Row is `<Link>` to `/runs/{id}`. Hover: row background → `bg-surface-hover`, no lift, 120ms.

New runs entering the list use Framer's `<AnimatePresence>` + `layout` so the list shifts smoothly when a run finishes or a new one starts.

## 2.8 — Hooking up live data

The dashboard subscribes to the observability SSE stream via `ObservabilityStreamProvider`. On each event:

- `run_started`: prepend a new `<RecentRunRow>` with status "running".
- `run_completed` / `run_failed` / `run_cancelled`: update the matching row's status; trigger the brief flash animation (350ms green/red border-flash) on the affected row.
- `summary_update` (if it exists, otherwise ignore): re-fetch stats via `useQuery` invalidation.

Don't add new SSE event types backend-side. If the existing stream gives enough for partial updates and TanStack Query refetches handle the rest, ship that.

## 2.9 — Mobile dashboard

At < 768px:
- Hero greeting: name stays gradient. Actions stack vertically.
- Stat cards: 2x2 grid. Sparkline card hides the sparkline (just shows the number).
- Two-column area becomes single column, Recent Runs first.
- All cards become full width.

## 2.10 — Phase 2 exit verification

- [ ] Open `/` in dev — looks like the new design, not the old one.
- [ ] Resize to 375px — layout collapses cleanly.
- [ ] Tab through the page — every interactive element has a visible focus ring (P0.7 should already make this work; verify).
- [ ] Open VoiceOver and confirm the live dot and run status changes are announced (aria-live region from P0.8 should still work — but verify on the dashboard).
- [ ] Trigger a workflow run from another page; come back to dashboard and watch the SSE update populate the Recent Runs column without a refresh.
- [ ] Toggle reduced motion in OS settings: stagger entries become snap, glow pulse stops, hover lift stays (it's <120ms).
- [ ] No console errors.

---

# Phase 3 — Canvas re-skin (~5-7 days)

**Goal:** the product's hero surface goes from "React Flow demo" to "custom-built premium tool." Split into four sub-pieces. Land them in this order.

**Files in scope:**
- `frontend/src/components/canvas/*` (entire directory)
- `frontend/src/components/canvas/nodes/*` (custom node components)
- `frontend/src/app/workflows/[id]/edit/` (the canvas route)

## 3.a — Chrome (1 day)

The frame around the canvas surface: header, sidebar wrapper, inspector wrapper, FAB.

### 3.a.i — Floating glass header

Currently `WorkflowCanvas.tsx` has a top toolbar flush with the canvas. Restyle to be a floating bar.

- Position: `absolute top-3 left-3 right-3 z-20`. Sits 12px from each edge of the canvas area (NOT the viewport — the canvas wrapper).
- Background: `bg-surface-elevated backdrop-blur-xl border border-border rounded-xl shadow-elev-2`.
- Padding: `px-4 py-2.5`.
- Contents (left-to-right):
  - `<` icon-button back to `/workflows` (use `Button` variant ghost + size icon).
  - Workflow name (editable inline; tap to edit, blur saves). If dirty, append a 6px filled circle (P1.7 already ships this; keep it).
  - Spacer.
  - `Versions` button (DropdownMenu → version list).
  - `Save` button (variant outline).
  - `Run` button (variant default, shadcn Button styled with `shadow-glow-primary` while idle).
- When running: the `Run` button transforms via Framer `layout` into a `Cancel` button. Same width — only label and color change.

### 3.a.ii — Sidebar + Inspector wrappers

Currently the left sidebar and right inspector are flush with the canvas edges. New treatment:

- Both panels become `<GlassCard>`-style: `bg-surface backdrop-blur-md border-border shadow-elev-1 rounded-xl`.
- Both inset 12px from their respective edges and 12px from the bottom. The floating header above sits 12px from top.
- Width: sidebar 280px (current), inspector 360px (slightly wider than current).
- On hover near the sidebar/inspector edge, the cursor shows a resize affordance, but actual resize is out of scope for this phase.

### 3.a.iii — Canvas background

Replace the React Flow `<Background>` component variant with `BackgroundVariant.Dots`, `gap={24} size={1} color={var(--canvas-grid)}`.

Then add a CSS layer behind the React Flow canvas (or as a pseudo-element on its container):

```css
.canvas-bg::before {
  content: "";
  position: absolute;
  inset: 0;
  background:
    radial-gradient(ellipse 50% 40% at 25% 15%, rgba(99, 102, 241, 0.08), transparent 60%),
    radial-gradient(ellipse 40% 30% at 80% 75%, rgba(139, 92, 246, 0.06), transparent 60%);
  pointer-events: none;
  z-index: 0;
}
```

The React Flow canvas sits at `z-index: 1` over this. Result: subtle indigo + violet ambient over the dot grid.

### 3.a.iv — Floating Run FAB

When nothing is selected AND the canvas has nodes, render a Floating Action Button at `absolute bottom-6 right-6 z-30`:

- Size: 56×56px, fully rounded.
- Style: `bg-primary-500 shadow-glow-primary text-primary-foreground`.
- Icon: `Play` from lucide.
- On hover: scale 1.05, shadow intensifies (use Framer `whileHover`).
- On click: same handler as the Run button in the header.

When a node IS selected: FAB animates out (Framer `<AnimatePresence>` with scale 0 + fade), the inspector content scales in. They're alternates — only one visible at a time, with motion linking them.

## 3.b — Nodes (2-3 days)

The biggest visual lift in the canvas. Build a `<BaseNode>` shell and category-specific shells over it.

### 3.b.i — Category mapping

In `frontend/src/lib/node-registry.ts` (existing), augment each node type with a `category` field:

| Node types | Category |
|---|---|
| `trigger` (all subtypes: manual / schedule / webhook) | `trigger` |
| `if`, `switch`, `router`, `classifier_router` | `logic` |
| `agent`, `classifier` | `llm` |
| `kb_retrieve`, `memory_store`, `memory_retrieve`, `json_parse` | `data` |
| `integration_slack`, `integration_discord`, `integration_email`, `integration_postgres`, `http_request` | `integration` |
| `evaluation`, `guardrail` | `quality` |
| `join`, `delay`, `sub_workflow`, `human_approval`, `end` | `flow` |
| `code` | `data` (debatable; code is closer to data manipulation than logic) |

The category drives:
- Accent bar color on the node
- Icon background tint
- Edge color on the source side of the connection
- The "filter by category" pills in the node palette (Phase 4)

### 3.b.ii — `<BaseNode>` shell

`frontend/src/components/canvas/nodes/BaseNode.tsx` already exists. Rewrite to this anatomy:

```
┌─ accent bar (2px, color = var(--cat-{category})) ────┐
│                                                       │
│  ⊙ icon  Agent                              ⋮         │  ← header row, 32px tall
│                                                       │
│  Classify the user message                            │  ← user-provided label, text-body
│                                                       │
│  [optional: inline elapsed timer when running]        │
│                                                       │
└───────────────────────────────────────────────────────┘
   ●           ●        ← React Flow handles
```

Sizes:
- Width: 240px (fixed; React Flow nodes need fixed width for layout consistency).
- Min height: 88px, grows with content.
- Padding: `p-3.5`.
- Outer container: `<motion.div>` for state animations. Class: `relative rounded-lg bg-surface backdrop-blur-md border border-border shadow-elev-1 overflow-hidden`.

State variants (mutually exclusive except where noted):

```ts
type NodeState =
  | "idle"
  | "hover"             // controlled by React Flow's onMouseEnter/Leave
  | "selected"          // controlled by isSelected prop from React Flow
  | "running"           // from the run stream
  | "completed"         // brief, then transitions back to idle
  | "failed"
  | "awaiting_approval";
```

Per-state styling:

| State | Border | Shadow | Extra |
|---|---|---|---|
| idle | `border-border` | `shadow-elev-1` | accent bar stays subtle |
| hover | `border-border-strong` | `shadow-elev-2` | accent bar saturates |
| selected | `border-primary/40` | `shadow-glow-primary` | accent bar has gradient (indigo→violet) |
| running | `border-warning/40` | `useGlowPulse()` returns `animate-glow-pulse` (animates a warning-colored glow via a custom keyframe — define `glow-pulse-warning` if needed) | inline elapsed-seconds counter shows |
| completed | brief 400ms flash: `border-success`, `shadow-glow-success` | then springs back to idle | optional output preview on hover |
| failed | `border-destructive/50` | `shadow-glow-destructive` | tooltip on hover shows error text |
| awaiting_approval | `border-warning border-dashed` | `shadow-glow-warning` (define if needed) | pulsing animation |

Layered effects:
- The accent bar at top is a `div` with `h-0.5 bg-cat-{category}`. On selected, its background becomes `bg-gradient-to-r from-cat-{category} to-accent-500`.
- The icon background uses `bg-cat-{category}/12` (12% opacity). Icon color is the full category color.
- The label is editable in-place by double-click. Single click selects the node. Use a controlled `<input>` that styles like the label until focused.

Handles (the connection dots on the sides):
- 10×10px circles, `bg-surface-elevated border border-border`. Inside, a 4px dot of category color.
- On hover (node OR handle): handle scales to 14×14, opacity 1, primary-color glow appears.
- When user is dragging a connection: nearby handles pulse to signal "drop target". Use Framer `useTransform` on React Flow's `onConnectStart` state.

### 3.b.iii — Category-specific node components

Create one file per category in `frontend/src/components/canvas/nodes/`:

- `TriggerNode.tsx`
- `LogicNode.tsx`
- `LLMNode.tsx`
- `DataNode.tsx`
- `IntegrationNode.tsx`
- `QualityNode.tsx`
- `FlowNode.tsx`

Each is thin (~30 lines): imports `<BaseNode>`, passes its `category`, picks the right Lucide icon based on the node subtype, optionally renders a category-specific footer slot (e.g. LLMNode shows model name in micro text at bottom).

Register them in the React Flow `<ReactFlow nodeTypes={...}>` prop. Map every existing `node_type` string to the right category component.

### 3.b.iv — Node hover-menu

The `⋮` icon in the header row (visible only on hover) renders a `DropdownMenu` with:
- Duplicate node
- Copy node JSON
- Delete node (uses existing P0.1 confirm dialog when needed)

## 3.c — Edges (1-2 days)

### 3.c.i — Custom edge component

Create `frontend/src/components/canvas/edges/GradientEdge.tsx`. React Flow's `EdgeProps` give you `sourceX`, `sourceY`, `targetX`, `targetY`, source/target node IDs.

For each edge, determine the source node category (look up in the React Flow store) and pick the matching `--cat-*` color.

Render:
- Use `getBezierPath()` from `@xyflow/react` for the curve.
- The path itself: `<path>` with `stroke={categoryColor}`, `stroke-width: 1.5`, `stroke-linecap: round`, `fill: none`.
- A second `<path>` overlaying the first, used for the animation effect — this one has `stroke-dasharray="4 4"` and animates `stroke-dashoffset`. Only renders when the edge is "active" (see below).
- Hover state: full opacity + soft bloom (add a third path underneath as a wider, blurred version of the same color).

### 3.c.ii — Active-during-run animation

Subscribe to the run stream. When a node enters the "running" state, mark all incoming edges (edges where this node is the target) AND the outgoing edges as "active". Active edges get:
- The dashed overlay path becomes visible and animates (`animation: edge-flow 1.5s linear infinite`).
- The stroke becomes a `<linearGradient>` from source-category-color to target-category-color.

Performance guardrail: if the workflow has > 80 edges, skip the dashed animation entirely. Static gradient stroke only. Compute this once per render of the canvas, not per-edge.

When the run finishes: active edges revert to idle styling. If any node on the edge's path failed, that edge becomes `--canvas-edge-failed` (existing token).

### 3.c.iii — Connection preview

While the user is dragging from a handle to create a new connection, the preview line (React Flow's `connectionLineComponent` prop) renders:
- Animated gradient (indigo to violet)
- Soft glow underneath
- Tiny arrow at the cursor end

Register this as `connectionLineComponent={CustomConnectionLine}`.

## 3.d — Inspector (1-2 days)

The right-side panel.

### 3.d.i — Layout

`<GlassCard>` with `bg-surface backdrop-blur-md`, full height inside its inset wrapper. Internal scroll.

Top section (fixed, doesn't scroll):

```
┌──────────────────────────────────┐
│  ⊙ Agent · Classify message      │  ← icon (category color) + category label · editable name
│  ─────────────                    │
└──────────────────────────────────┘
```

Scrollable body: collapsible sections via shadcn's Accordion (single-collapsible mode by default). Each section is a `<details>`-like primitive with smooth open/close animation via Framer `layout`.

Section structure per node category:

| Node category | Always-open section | Collapsed sections |
|---|---|---|
| LLM | "Essentials" (instruction, model) | "Output processing", "Eval & guardrails", "Testing" |
| Trigger | "Trigger" (type, schedule cron or webhook URL) | "Advanced" |
| Logic | "Routing" (rules) | "Default branch", "Testing" |
| Data | "Configuration" (KB / memory namespace / parse rules) | "Output mapping" |
| Integration | "Connection" (credential select, target) | "Payload", "Retry & timeout" |
| Quality | "Rules" (LLM / Presidio / regex) | "Threshold & fail behavior", "Test sample" |
| Flow | "Configuration" | (none, usually) |

Existing P2.1 work introduced collapsible sections in `NodeInspector.tsx`. Carry that forward — just apply the new visual treatment.

### 3.d.ii — Switching nodes

When user clicks a different node:
- Use Framer's `<AnimatePresence mode="wait">` to crossfade the inspector body.
- Use `<motion.div layout>` so any height changes ease (200ms `ease-out`).
- The identity header at top transitions: icon color changes, category label slides up + new one slides in, name field re-populates.

### 3.d.iii — Danger zone

At the bottom of the inspector, visually separated by `border-t border-border pt-4 mt-6`:
- A single `Delete node` button, variant ghost (muted text). On hover: turns destructive color.
- Click triggers the existing P0.1 confirm dialog.
- Above the button, in `text-micro`: "Danger zone".

### 3.d.iv — Empty state

When no node is selected:

```
   No selection

   Click a node on the canvas to configure it,
   or drag a new node from the sidebar.

   ─ Quick tips ─
   Cmd+K       Search nodes
   Cmd+S       Save workflow
   Cmd+/       Keyboard shortcuts
```

Centered, muted. Style: `<div class="flex flex-col items-center justify-center p-8 text-center">`. The `Cmd+K`/`Cmd+S`/`Cmd+/` use shadcn-style `<kbd>` styling.

## 3.e — Sidebar (node palette) restyle

In the same phase, restyle the existing node palette to use the new visuals:

- Category pills at the top (horizontal scroll on narrow widths): filter nodes by category. Pills are `Badge`-like, glass background, active state uses category color.
- Node list items: each item shows the icon (in its category color), node type name, one-line description. Hover: `bg-surface-hover`. Drag: ghost preview matches the eventual node card visual.
- Search input at top: shadcn `Input` with prefix icon.

Use `<StaggerList>` for items when the category filter changes.

## 3.f — Phase 3 exit verification

- [ ] Open any workflow's canvas. Look at the floating header, glass panels, ambient bg. Take a screenshot — does it look like a custom tool, not a demo?
- [ ] Drag a new node onto the canvas. Watch the entrance animation.
- [ ] Connect two nodes. Watch the connection preview line.
- [ ] Click a node. Inspector switches with crossfade. Click another. Inspector animates.
- [ ] Run the workflow. Active edges should flow (gradient + animated dashes if <80 edges; static gradient otherwise). Active node should glow-pulse. Completed nodes should flash green.
- [ ] Test on a workflow with 50+ nodes — no jank, no React Flow rendering issues.
- [ ] Toggle reduced motion: glow-pulse stops, edge-flow stops, hover-lift stays.
- [ ] Open the canvas at 375px: P2.14 mobile fallback should still trigger and show the "use desktop" message.
- [ ] `npm run typecheck && npm run lint` clean.

---

# Phase 4 — Extend outward (~5-7 days)

**Goal:** every other page reaches the dashboard/canvas bar. No new patterns invented here — extend existing ones.

Order (most-used first):

## 4.1 — `/runs/[id]` (run detail) — 1-2 days

- Header: workflow name + run status badge with glow per status + timestamp + duration. Status badge gets glow-pulse if status === "running".
- Body split into two columns on desktop:
  - Left: timeline of node executions. Each node is a glass card with collapsed-by-default expansion that reveals output, latency, eval scores. Order: vertical timeline with connecting line. Status icon on the left rail.
  - Right: sticky panel with eval scores chart (sparkline-style or radar) + guardrail events (using new color coding) + final output card.
- Final output gets `<GlowCard>` treatment if eval passed, plain `<GlassCard>` otherwise.
- Approval action (if status === awaiting_approval): prominent `<GlowCard variant="warning">` at top with Approve / Reject buttons.

## 4.2 — `/observability` — 1-2 days

- Hero stat strip identical pattern to dashboard's stat cards row.
- Sparkline strip across full width below stats: one sparkline per metric (run count, pass rate, latency p50, latency p95). Aligned vertically so users can compare.
- Live indicator on the page header.
- Runs list at the bottom uses the same `<RecentRunRow>` pattern from the dashboard, but with full filtering (existing — restyle).
- Empty state when no data: `<EmptyState variant="info">` (P3.8 already shipped) with CTA to docs.

## 4.3 — `/settings` — 1 day

- Tabs along the top (use shadcn `Tabs`): General, Credentials, Eval Presets, Integrations, API Keys.
- Each tab content area is wrapped in `<GlassCard>`.
- Form fields use shadcn `Input`, `Select`, `Switch` (replace toggles).
- Credentials list: each credential is a row in a glass-bordered list. Add `<Sheet>` (shadcn) for the edit drawer — opens from the right.
- Delete confirms use the existing P0.4 named-resource dialogs.

## 4.4 — `/templates` — half day

- Gallery: 3-column grid of template cards (responsive: 2 on tablet, 1 on mobile).
- Each template card: `<GlassCard>` with `<HoverLift>`. Top half is a placeholder gradient image (use a deterministic hash of the template name to pick from a small palette of gradients). Bottom half: name + description + node count + "Use template" button.
- Skeleton load uses the same card structure (already shipped per P2.7).

## 4.5 — `/guardrails` — half day

- Playground card: glass surface, split into two sub-panels.
- Left: editor for guardrail config (shadcn Textarea + Select for type).
- Right: result panel — pass/fail badge with status glow, redacted output (mono font), latency.
- Above the playground: a strip of preset examples (chips/badges) the user can click to load.
- "How to use" collapsed section (P3.7 already shipped, restyle).

## 4.6 — `/workflows` (list page) — half day

- Search + filter bar at top.
- Grid of workflow cards using the same `<WorkflowCard>` from the dashboard (extract to a shared component).

## 4.7 — Layout chrome (`AppNav`, mobile nav) — half day

- `AppNav.tsx`: restyle as floating glass bar at top (similar to canvas header), with the page nav + user menu.
- Active route indicator: a subtle gradient line below the nav item (use `<motion.div layout>` keyed by pathname for the line to slide between items).
- Mobile nav (`MobileNav.tsx`): bottom-sheet style using shadcn `Sheet`, slides up from the bottom on tap.

## 4.8 — Phase 4 exit verification

Click through every route. No page should still look like the "before" version. Run a workflow end-to-end and watch it propagate: dashboard live update → canvas execution viz → run detail timeline. The whole flow should feel coherent.

- [ ] No hand-rolled CSS class `.interactive-card` remains in any component (search and remove).
- [ ] All P0–P3 work from the previous fix pass is still intact (focus rings visible, aria-labels present, validation working, confirm dialogs firing).
- [ ] `npm run typecheck && npm run lint` clean.

---

# Phase 5 — Polish & microinteractions (~2-3 days)

**Goal:** the difference between "good" and "premium." Small details, but they compound.

## 5.1 — Sonner toast restyle

Configure Sonner with our tokens. Each variant gets its glow:

- success → `shadow-glow-success`, success-color border on the left edge
- error → `shadow-glow-destructive`, destructive border
- info → glass surface, no glow
- loading → spinner uses primary color

Transition: spring entry (Framer-like — but Sonner has its own; use the closest stiff/damping combo). Out: fade + slide.

## 5.2 — Button press scale

Add `active:scale-[0.98] transition-transform duration-fast` to the base button styles. Honors reduced motion automatically since duration goes to instant.

## 5.3 — Focus ring animation

Replace hard ring with: on focus, a `box-shadow` transition from `0 0 0 0 var(--ring)` to `0 0 0 3px var(--primary-glow)` over 160ms. Apply via a base class added to `globals.css` `@layer base`:

```css
:focus-visible {
  outline: none;
  box-shadow: 0 0 0 2px var(--bg), 0 0 0 4px var(--primary-glow);
  transition: box-shadow 160ms var(--ease-out);
}
```

## 5.4 — Number tweens everywhere they fit

Audit all places displaying a numeric value that can change live (dashboard stats, observability metrics, run detail latency). Wrap each in `<NumberTween>` if not already.

## 5.5 — Command palette polish

- Add recent items (persist last 5 selected actions in localStorage).
- Add fuzzy search via shadcn's Command (uses cmdk under the hood — already fuzzy).
- Group actions: Workflows, Recent runs, Settings, Help.
- Empty state copy: "No matches. Try a different search."

## 5.6 — Hover affordances audit

Click through every page. Anything that's interactive but doesn't show hover state — fix it. Anything that looks interactive but isn't — make it look passive (no cursor pointer, no hover).

## 5.7 — Screen reader final pass

Walk through with VoiceOver:
- Dashboard live updates announce correctly.
- Canvas node state changes announce.
- Run detail status changes announce (P0.8 — verify).
- Modal focus traps work (shadcn Dialog handles this; verify).
- Form errors announce (P0.9 inline errors — verify).

## 5.8 — Reduced motion final pass

Toggle the OS setting and verify ALL of:
- Page enters: stagger becomes instant
- Stat cards: no stagger
- Sparkline: no draw animation
- Canvas active node: no glow pulse (becomes static glow)
- Canvas edges during runs: no edge flow animation
- Inspector switching: no layout animation (just snap)
- Hover lift: still works (it's <120ms, doesn't count as "motion" per WCAG)
- Button press: still works

## 5.9 — Mobile final pass

At 375px on every route:
- Dashboard: stat cards stack 2x2; columns become single column.
- Canvas: shows the mobile fallback (P2.14).
- Run detail: timeline + right panel stack.
- Settings: tabs become a `<Select>` or horizontal scrollable.
- Modals: full-width with safe margins.

## 5.10 — Screenshot session

Open the dev server. Take screenshots of:
- Dashboard (with data)
- Dashboard (empty state)
- Canvas (mid-edit)
- Canvas (running, with active edges + glowing node)
- Run detail (passed with evals)
- Run detail (awaiting approval)
- Observability dashboard
- Settings credentials list
- Command palette open

Look at each screenshot. Anything that looks off in the screenshot, fix. Anything that looks great, note it.

## 5.11 — Phase 5 exit verification

- [ ] Record a 60-second screen capture of using the product end-to-end. Watch it back. Does it look intentional from start to finish?
- [ ] `npm run typecheck && npm run lint` clean.
- [ ] Bundle size delta from start-of-overhaul to end-of-Phase-5 ≤ 150KB gzipped. If over, audit framer-motion imports and tree-shake.

---

# Reference: file map

After all five phases, these files SHOULD exist (relative to `frontend/`):

```
src/app/globals.css                       ← updated tokens (Phase 1)
tailwind.config.ts                        ← updated config (Phase 1)
src/app/layout.tsx                        ← Geist font + page-level chrome (Phase 1)

src/components/motion/
  PageEnter.tsx
  StaggerList.tsx
  HoverLift.tsx
  NumberTween.tsx
  useGlowPulse.ts
  index.ts

src/components/ui/
  glass-card.tsx                          ← new
  glow-card.tsx                           ← new
  button.tsx                              ← restyled, kept
  card.tsx, input.tsx, textarea.tsx, etc. ← restyled, kept
  badge.tsx, alert.tsx, ...               ← restyled, kept
  dialog.tsx                              ← shadcn-replaced
  popover.tsx                             ← shadcn-new
  tooltip.tsx                             ← shadcn-replaced
  select.tsx                              ← shadcn-replaced
  tabs.tsx                                ← shadcn-new
  dropdown-menu.tsx                       ← shadcn-new
  sheet.tsx                               ← shadcn-new
  command.tsx                             ← shadcn-new
  switch.tsx                              ← shadcn-new

src/components/dashboard/
  HeroGreeting.tsx                        ← new
  StatCard.tsx                            ← new or restyled
  Sparkline.tsx                           ← new
  WorkflowCard.tsx                        ← new (also reused in /workflows list)
  RecentRunRow.tsx                        ← new
  LiveDot.tsx                             ← new
  DashboardView.tsx                       ← rewritten

src/components/canvas/
  WorkflowCanvas.tsx                      ← rewritten chrome
  CanvasSidebar.tsx                       ← restyled
  NodeInspector.tsx                       ← restyled, sections kept
  EdgeInspector.tsx                       ← restyled
  NodePalette.tsx                         ← restyled with category pills
  VersionHistory.tsx                      ← restyled
  edges/
    GradientEdge.tsx                      ← new
    ConnectionLine.tsx                    ← new
  nodes/
    BaseNode.tsx                          ← rewritten
    TriggerNode.tsx                       ← new
    LogicNode.tsx                         ← new
    LLMNode.tsx                           ← new
    DataNode.tsx                          ← new
    IntegrationNode.tsx                   ← new
    QualityNode.tsx                       ← new
    FlowNode.tsx                          ← new

src/components/layout/
  AppNav.tsx                              ← restyled
  MobileNav.tsx                           ← restyled with Sheet
  CommandPalette.tsx                      ← rewritten with shadcn Command
```

# Reference: token-to-style cheatsheet

When restyling any component, use this as your reference:

**Cards / panels** (most surfaces):
```
className="bg-surface backdrop-blur-md border border-border rounded-xl shadow-elev-1"
```

**Cards that need to feel important** (one per page):
```
className="bg-surface backdrop-blur-md border border-border-glow rounded-xl shadow-glow-primary"
```

**Modals / popovers**:
```
className="bg-surface-elevated backdrop-blur-xl border border-border rounded-xl shadow-elev-3"
```

**Inputs**:
```
className="bg-surface-input border border-border rounded-md px-3 h-10 focus-visible:border-border-strong"
```

**Buttons (primary)**:
```
className="bg-primary text-primary-foreground hover:bg-primary-600 rounded-md h-9 px-4 active:scale-[0.98]"
```

**Buttons (outline)**:
```
className="border border-border bg-transparent hover:bg-surface-hover rounded-md h-9 px-4"
```

**Buttons (ghost)**:
```
className="text-muted hover:bg-surface-hover hover:text-foreground rounded-md h-9 px-4"
```

**Status badges** (with text + icon, per P1.14):
```
<Badge className="bg-success/12 text-success border-success/20"><CheckCircle2 /> Passed</Badge>
<Badge className="bg-destructive/12 text-destructive border-destructive/20"><XCircle /> Failed</Badge>
<Badge className="bg-warning/12 text-warning border-warning/20"><AlertTriangle /> Warning</Badge>
```

# Reference: copy guidelines

- **Verb-noun for actions:** "Delete workflow", not "Confirm". "Save changes", not "Save". (P1.11 already enforces this in `ConfirmDialog`.)
- **Sentence case** for buttons, titles, copy. Not Title Case.
- **No emoji in UI strings.**
- **Empty states tell users what to do**, not just what's missing. "No runs yet — run your first workflow to see them here." not "No data."
- **Errors say what failed AND what to try.** P0.11 already enforces this for boundaries; extend to inline form errors.
- **Relative times by default, absolute on hover** ("2m ago" with tooltip "Jun 30, 2026 at 4:23 PM"). Existing `format-date.ts` already supports this.

# What you DO NOT need to ask about

These decisions are made. Don't waste a turn confirming:

- Glass aesthetic (translucent surfaces, backdrop blur, ambient gradients) — committed.
- Indigo + violet brand identity — kept.
- Dark mode only — light mode is out of scope.
- shadcn/ui as primitives + Framer Motion for animations — chosen.
- Geist font — chosen.
- 7-category color system on canvas nodes — committed.
- Hero-first phase order (foundation → dashboard → canvas → rest → polish) — committed.
- Floating header + glass panels with edge insets on canvas — committed.

# What you SHOULD ask about

Stop and ask the user before:
- Adding any dependency not listed in this spec.
- Making any backend change (REST endpoint, SSE event type, schema).
- Removing a feature that exists today, even if you think it's not needed.
- Changing a category-to-node mapping in 3.b.i if a node type doesn't fit any category cleanly.
- Skipping any sub-piece you think is "not worth it" — surface the tradeoff, let the user decide.

# How to handle scope drift mid-phase

If you discover a piece of work that's bigger than the spec implied (e.g., the sparkline needs backend data that doesn't exist), do NOT silently expand scope. Stop, write a short message:

```
[scope flag: <phase> <sub-piece>]
Hit an issue: <one-paragraph description>.
Options:
  A: <smallest possible workaround>
  B: <slightly bigger fix>
  C: <full fix>
Recommend: <one of the above + why>
```

Wait for user response. Don't ship a "creative interpretation" of the spec.

# Done condition

Five phases shipped. Spec items above either implemented, intentionally deferred (with reason), or already done. Final report message contains:
- All commits grouped by phase.
- Deferrals.
- Bundle size delta.
- A short paragraph: "If I had one more day, I'd polish X" — your call on what.

Now go.
