# Aegis UI Overhaul Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reskin Aegis to Vercel/Cursor-grade with glass surfaces, ambient gradients, selective primary-color glows, and Framer Motion micro-interactions — across foundation, dashboard, canvas internals, the remaining pages, and a polish pass.

**Architecture:** Five sequential phases, each ending in a shippable state. Phase 1 lays tokens, motion primitives, and shadcn migration (mostly invisible). Phase 2 redesigns the dashboard as the proof surface. Phase 3 rebuilds the canvas chrome, custom node cards, animated gradient edges, and inspector polish. Phase 4 carries the patterns into runs, observability, settings, templates, guardrails, and workflow listings. Phase 5 is microinteractions, screen-reader audit, reduced-motion verification, and a screenshot session. No backend changes.

**Tech Stack:** Next.js 14 (App Router) · React 18 · TypeScript · Tailwind 3.4 (extended) · CSS variables · Framer Motion (new) · shadcn/ui (new, Radix under the hood) · cmdk (via shadcn Command) · Geist font (new) · React Flow 12 (theme + custom node/edge components) · TanStack Query 5 (unchanged) · Sonner (kept, restyled) · lucide-react.

**Spec:** `docs/superpowers/specs/2026-07-01-ui-overhaul-design.md` is the source of truth for design decisions. This plan implements that spec.

**Working agreements:**

- `cd frontend && npm run typecheck && npm run lint` must be clean after every commit.
- One commit per task. Commit messages: `feat(ui-overhaul): <phase>.<task> — <one-line>`.
- After every phase, run `npm run dev` and click through every route in a real browser before marking the phase done.
- No backend changes. Ever.
- No new dependencies beyond the ones in Task 1.1 (`framer-motion`, `geist`, shadcn-installed Radix packages, `cmdk`).
- Existing P0–P3 a11y/validation/error-copy work stays intact — restyle, don't undo.
- No emojis in UI copy or commit messages.

**Phase review gates:**

- End of Phase 1 (Task 1.x): app looks 95% like before but tokens, motion primitives, and shadcn primitives are in place. Foundation review.
- End of Phase 2 (Task 2.x): dashboard looks reskinned, rest of app looks worse by comparison.
- End of Phase 3 (Task 3.x): canvas feels custom-built.
- End of Phase 4 (Task 4.x): every page reaches the bar.
- End of Phase 5 (Task 5.x): polish complete, screenshot-ready.

---

# File Structure

## Created files

```
frontend/src/components/motion/
  PageEnter.tsx
  StaggerList.tsx
  HoverLift.tsx
  NumberTween.tsx
  use-glow-pulse.ts
  use-reduced-motion-strict.ts
  index.ts

frontend/src/components/ui/
  glass-card.tsx
  glow-card.tsx
  (shadcn-added: popover.tsx, tabs.tsx, dropdown-menu.tsx, sheet.tsx, command.tsx, switch.tsx)
  (shadcn-replaced: dialog.tsx, tooltip.tsx, select.tsx)

frontend/src/components/dashboard/
  HeroGreeting.tsx
  StatCard.tsx
  Sparkline.tsx
  WorkflowCard.tsx
  RecentRunRow.tsx
  LiveDot.tsx
  TrendPill.tsx

frontend/src/components/canvas/edges/
  GradientEdge.tsx
  ConnectionLine.tsx

frontend/src/components/canvas/nodes/
  TriggerNode.tsx
  LogicNode.tsx
  LLMNode.tsx
  DataNode.tsx
  IntegrationNode.tsx
  QualityNode.tsx
  FlowNode.tsx
  category.ts
```

## Modified files

```
frontend/src/app/globals.css            — full token rewrite (Task 1.2)
frontend/tailwind.config.ts             — full config rewrite (Task 1.3)
frontend/src/app/layout.tsx             — Geist font wiring (Task 1.4)
frontend/package.json                   — dependency adds (Task 1.1)

frontend/src/components/ui/button.tsx           — restyle (Task 1.13)
frontend/src/components/ui/input.tsx            — restyle (Task 1.13)
frontend/src/components/ui/textarea.tsx         — restyle (Task 1.13)
frontend/src/components/ui/badge.tsx            — restyle (Task 1.13)
frontend/src/components/ui/card.tsx             — restyle (Task 1.13)
frontend/src/components/ui/alert.tsx            — restyle (Task 1.13)
frontend/src/components/ui/empty-state.tsx      — restyle (Task 1.13)

frontend/src/components/dashboard/DashboardView.tsx   — rewrite (Tasks 2.x)

frontend/src/components/canvas/WorkflowCanvas.tsx     — chrome (Task 3.1)
frontend/src/components/canvas/CanvasSidebar.tsx      — restyle (Task 3.10)
frontend/src/components/canvas/NodeInspector.tsx      — restyle (Tasks 3.8, 3.9)
frontend/src/components/canvas/EdgeInspector.tsx      — restyle (Task 3.1)
frontend/src/components/canvas/NodePalette.tsx        — restyle (Task 3.10)
frontend/src/components/canvas/nodes/BaseNode.tsx     — rewrite (Task 3.4)
frontend/src/lib/node-registry.ts                     — augment with category (Task 3.3)

frontend/src/app/runs/[id]/page.tsx                   — restyle (Task 4.1)
frontend/src/components/runs/RunDetailView.tsx        — restyle (Task 4.1)
frontend/src/app/observability/page.tsx               — restyle (Task 4.2)
frontend/src/app/settings/page.tsx                    — restyle (Task 4.3)
frontend/src/app/templates/page.tsx                   — restyle (Task 4.4)
frontend/src/app/guardrails/page.tsx                  — restyle (Task 4.5)
frontend/src/components/guardrails/GuardrailPlayground.tsx — restyle (Task 4.5)
frontend/src/app/workflows/page.tsx                   — restyle (Task 4.6)
frontend/src/components/layout/AppNav.tsx             — restyle (Task 4.7)
frontend/src/components/layout/MobileNav.tsx          — restyle with Sheet (Task 4.7)
frontend/src/components/layout/CommandPalette.tsx     — rewrite with shadcn Command (Task 1.12)
```

## Deleted files

```
frontend/src/components/ui/dialog.tsx          — replaced by shadcn (after callers migrated)
frontend/src/components/ui/tooltip.tsx         — replaced by shadcn
frontend/src/components/ui/select.tsx          — replaced by shadcn
(Old hand-rolled CommandPalette logic absorbed into the rewritten file)
```

---

# Phase 1 — Foundation

Goal: tokens, fonts, motion primitives, shadcn migration. No visible product changes.

## Task 1.1: Add dependencies

**Files:**
- Modify: `frontend/package.json`

- [ ] **Step 1: Install Framer Motion**

```bash
cd frontend && npm install framer-motion
```

Expected: `framer-motion` added under `dependencies`. Version 11+ is fine.

- [ ] **Step 2: Install Geist font package**

```bash
cd frontend && npm install geist
```

Expected: `geist` added under `dependencies`.

- [ ] **Step 3: Init shadcn/ui**

```bash
cd frontend && npx shadcn@latest init
```

Prompts to answer:
- "Would you like to use TypeScript?" → yes
- "Which style would you like to use?" → New York
- "Which color would you like to use as base color?" → Zinc
- "Where is your global CSS file?" → `src/app/globals.css`
- "Would you like to use CSS variables for colors?" → yes
- "Where is your tailwind.config.js?" → `tailwind.config.ts`
- "Configure the import alias for components?" → `@/components`
- "Configure the import alias for utils?" → `@/lib/utils`
- "Are you using React Server Components?" → yes (Next App Router)

This creates `components.json`. It will also try to overwrite `globals.css` with shadcn's defaults — that's expected and we'll fix it in Task 1.2.

- [ ] **Step 4: Verify install**

```bash
cd frontend && npm run typecheck
```

Expected: PASS (shadcn init may have added unused imports — clean if so).

- [ ] **Step 5: Commit**

```bash
cd frontend && git add package.json package-lock.json components.json src/app/globals.css 2>/dev/null
cd .. && git commit -m "feat(ui-overhaul): 1.1 — install framer-motion, geist, shadcn"
```

## Task 1.2: Replace globals.css with new token set

**Files:**
- Modify: `frontend/src/app/globals.css`

- [ ] **Step 1: Read current globals.css to preserve component-layer classes**

```bash
cat frontend/src/app/globals.css
```

Note the `@layer components` block (panel, page-container, skip-link, sr-only, interactive-card, skeleton, nav-link, tab-trigger, sidebar-tab, eyebrow, text-display, text-title, etc.) and the React Flow customizations at the bottom (`.canvas-flow ...`), the `@media (pointer: coarse)` and `@media (prefers-reduced-motion: reduce)` blocks.

These all need to be preserved; only the `:root` token block at top changes substantially.

- [ ] **Step 2: Write the new globals.css**

Replace the file contents with:

```css
@tailwind base;
@tailwind components;
@tailwind utilities;

:root {
  --bg: #08080a;
  --bg-grad-1: radial-gradient(ellipse 80% 50% at 30% -10%, rgba(99, 102, 241, 0.18), transparent 60%);
  --bg-grad-2: radial-gradient(ellipse 60% 40% at 85% 60%, rgba(139, 92, 246, 0.10), transparent 60%);

  --surface: rgba(20, 20, 23, 0.72);
  --surface-elevated: rgba(28, 28, 32, 0.78);
  --surface-glass: rgba(255, 255, 255, 0.04);
  --surface-hover: rgba(255, 255, 255, 0.06);
  --surface-input: rgba(20, 20, 23, 0.85);

  --border: rgba(255, 255, 255, 0.08);
  --border-strong: rgba(255, 255, 255, 0.14);
  --border-glow: rgba(99, 102, 241, 0.32);

  --fg: #fafafa;
  --fg-muted: #b4b4b8;
  --fg-subtle: #71717a;

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

  --destructive: #ef4444;
  --destructive-glow: rgba(239, 68, 68, 0.35);
  --success: #22c55e;
  --success-glow: rgba(34, 197, 94, 0.3);
  --warning: #f59e0b;
  --warning-glow: rgba(245, 158, 11, 0.35);

  --ring: #818cf8;

  --cat-trigger: #6366f1;
  --cat-logic: #06b6d4;
  --cat-llm: #8b5cf6;
  --cat-data: #10b981;
  --cat-integration: #f59e0b;
  --cat-quality: #f43f5e;
  --cat-flow: #64748b;

  --canvas-grid: #232936;
  --canvas-edge: #475569;
  --canvas-edge-active: #fbbf24;
  --canvas-edge-failed: #f43f5e;
  --canvas-connection: #6366f1;

  --radius-sm: 6px;
  --radius-md: 10px;
  --radius-lg: 14px;
  --radius-xl: 20px;
  --radius-2xl: 28px;
  --radius: var(--radius-lg);

  --elev-1: 0 1px 0 rgba(255, 255, 255, 0.04) inset, 0 1px 2px rgba(0, 0, 0, 0.4);
  --elev-2: 0 0 0 1px rgba(255, 255, 255, 0.04) inset, 0 4px 16px rgba(0, 0, 0, 0.4);
  --elev-3: 0 0 0 1px rgba(255, 255, 255, 0.05) inset, 0 12px 40px rgba(0, 0, 0, 0.5);
  --elev-glow-primary: 0 0 0 1px rgba(99, 102, 241, 0.25), 0 0 32px rgba(99, 102, 241, 0.18);
  --elev-glow-accent: 0 0 0 1px rgba(139, 92, 246, 0.22), 0 0 32px rgba(139, 92, 246, 0.18);
  --elev-glow-success: 0 0 0 1px rgba(34, 197, 94, 0.25), 0 0 24px rgba(34, 197, 94, 0.18);
  --elev-glow-destructive: 0 0 0 1px rgba(239, 68, 68, 0.3), 0 0 28px rgba(239, 68, 68, 0.2);
  --elev-glow-warning: 0 0 0 1px rgba(245, 158, 11, 0.3), 0 0 24px rgba(245, 158, 11, 0.2);

  --ease-out: cubic-bezier(0.16, 1, 0.3, 1);
  --ease-in-out: cubic-bezier(0.65, 0, 0.35, 1);
  --dur-instant: 120ms;
  --dur-fast: 200ms;
  --dur-base: 320ms;
  --dur-slow: 500ms;
}

@layer base {
  * {
    @apply border-border;
  }

  body {
    @apply bg-bg text-foreground antialiased;
    font-feature-settings: "rlig" 1, "calt" 1;
    background-image: var(--bg-grad-1), var(--bg-grad-2);
    background-attachment: fixed;
  }
}

@layer components {
  .app-shell {
    @apply min-h-screen;
  }

  .panel {
    @apply rounded-lg border border-border bg-surface-elevated;
    box-shadow: var(--elev-1);
  }

  .page-container {
    @apply mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8 lg:py-10;
  }

  .skip-link {
    @apply sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-50 focus:rounded-lg focus:border focus:border-border focus:bg-surface-elevated focus:px-4 focus:py-2 focus:text-sm focus:font-medium focus:text-foreground focus:shadow-lg;
  }

  .sr-only {
    @apply absolute h-px w-px overflow-hidden whitespace-nowrap border-0 p-0;
    clip: rect(0, 0, 0, 0);
    clip-path: inset(50%);
  }

  .not-sr-only {
    @apply static h-auto w-auto overflow-visible whitespace-normal p-0;
    clip: auto;
    clip-path: none;
  }

  .section-heading {
    @apply text-base font-semibold tracking-tight text-foreground;
  }

  .text-muted {
    color: var(--fg-muted);
  }

  .text-subtle {
    color: var(--fg-subtle);
  }

  .interactive-card {
    @apply rounded-lg border border-border bg-surface-elevated transition-all duration-200;
    box-shadow: var(--elev-1);
  }

  .interactive-card:hover {
    @apply border-border-strong bg-surface-hover;
    box-shadow: var(--elev-2);
  }

  .skeleton {
    @apply animate-pulse rounded-md bg-surface-hover;
  }

  .nav-link {
    @apply rounded-md px-3 py-1.5 text-sm font-medium text-muted transition-colors;
  }

  .nav-link:hover {
    @apply text-foreground;
  }

  .nav-link-active {
    @apply bg-surface-hover text-foreground;
  }

  .nav-link:focus-visible,
  .sidebar-tab:focus-visible,
  .tab-trigger:focus-visible,
  .focus-ring:focus-visible {
    outline: none;
    box-shadow: 0 0 0 2px var(--bg), 0 0 0 4px var(--ring);
  }

  .section-block {
    animation: fade-in 0.35s ease-out forwards;
    opacity: 0;
  }

  .tab-trigger {
    @apply flex flex-1 items-center justify-center gap-2 border-b-2 border-transparent px-3 py-3 text-xs font-medium text-muted transition sm:px-4 sm:text-sm;
  }

  .tab-trigger:hover {
    @apply text-foreground;
  }

  .tab-trigger-active {
    @apply border-primary text-foreground;
  }

  .sidebar-tab {
    @apply flex min-w-0 flex-1 flex-col items-center gap-1 px-1.5 py-3 text-[10px] font-semibold uppercase tracking-wider transition sm:px-2;
  }

  .sidebar-tab-active {
    @apply border-b-2 border-primary text-foreground;
  }

  .eyebrow {
    @apply text-sm font-medium text-primary;
  }

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

  .inspector-empty {
    @apply rounded-lg border border-dashed border-border bg-surface p-8 text-center;
  }

  .form-hint {
    @apply text-xs leading-relaxed text-muted;
  }

  .stagger-item {
    animation: stagger-fade 0.4s ease-out forwards;
    opacity: 0;
  }

  @keyframes fade-in {
    from { opacity: 0; transform: translateY(4px); }
    to { opacity: 1; transform: translateY(0); }
  }
  @keyframes stagger-fade {
    from { opacity: 0; transform: translateY(8px); }
    to { opacity: 1; transform: translateY(0); }
  }
  @keyframes glow-pulse {
    0%, 100% { box-shadow: var(--elev-glow-primary); }
    50% { box-shadow: 0 0 0 1px rgba(99,102,241,0.35), 0 0 48px rgba(99,102,241,0.3); }
  }
  @keyframes glow-pulse-warning {
    0%, 100% { box-shadow: var(--elev-glow-warning); }
    50% { box-shadow: 0 0 0 1px rgba(245,158,11,0.4), 0 0 36px rgba(245,158,11,0.32); }
  }
  @keyframes edge-flow {
    0% { stroke-dashoffset: 20; }
    100% { stroke-dashoffset: 0; }
  }
}

.canvas-flow .react-flow__edge-path {
  stroke-linecap: round;
}

.canvas-flow .react-flow__handle {
  transition: border-color 0.15s ease, transform 0.15s ease;
}

.canvas-flow .react-flow__handle:hover {
  transform: scale(1.12);
}

.canvas-flow .react-flow__controls-button {
  background: var(--surface-elevated) !important;
  border-color: var(--border) !important;
  color: var(--fg-muted) !important;
  border-radius: 8px !important;
}

.canvas-flow .react-flow__controls-button:hover {
  background: var(--surface-hover) !important;
  color: var(--fg) !important;
}

.canvas-flow .react-flow__attribution {
  display: none;
}

@media (pointer: coarse) {
  .hover-reveal {
    opacity: 1 !important;
  }
}

@media (prefers-reduced-motion: reduce) {
  *,
  *::before,
  *::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
    scroll-behavior: auto !important;
  }
  body { background-attachment: scroll; }
  .stagger-item, .section-block { opacity: 1; animation: none; }
  .animate-pulse, .animate-spin, .animate-fade-in,
  .animate-glow-pulse, .animate-glow-pulse-warning, .animate-edge-flow {
    animation: none !important;
  }
}
```

Note the `--muted` → `--fg-muted` rename. The `.text-muted` class still works because we updated it. Existing Tailwind alias `muted` will continue to map via the next task.

- [ ] **Step 3: Commit**

```bash
cd /Users/himanshu/Git/aegis && git add frontend/src/app/globals.css && git commit -m "feat(ui-overhaul): 1.2 — replace globals.css with new token system"
```

## Task 1.3: Update tailwind.config.ts

**Files:**
- Modify: `frontend/tailwind.config.ts`

- [ ] **Step 1: Replace tailwind.config.ts**

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
        bg: "var(--bg)",
        background: "var(--bg)",
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
        primary: {
          DEFAULT: "var(--primary)",
          foreground: "var(--primary-foreground)",
          muted: "var(--primary-muted)",
          glow: "var(--primary-glow)",
          50: "var(--primary-50)",
          100: "var(--primary-100)",
          200: "var(--primary-200)",
          300: "var(--primary-300)",
          400: "var(--primary-400)",
          500: "var(--primary-500)",
          600: "var(--primary-600)",
          700: "var(--primary-700)",
          800: "var(--primary-800)",
          900: "var(--primary-900)",
        },
        accent: {
          DEFAULT: "var(--accent)",
          foreground: "var(--accent-foreground)",
          muted: "var(--accent-muted)",
          glow: "var(--accent-glow)",
          300: "var(--accent-300)",
          400: "var(--accent-400)",
          500: "var(--accent-500)",
          600: "var(--accent-600)",
        },
        destructive: {
          DEFAULT: "var(--destructive)",
          glow: "var(--destructive-glow)",
        },
        success: {
          DEFAULT: "var(--success)",
          glow: "var(--success-glow)",
        },
        warning: {
          DEFAULT: "var(--warning)",
          glow: "var(--warning-glow)",
        },
        ring: "var(--ring)",
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
        "glow-warning": "var(--elev-glow-warning)",
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
        "glow-pulse-warning": {
          "0%, 100%": { boxShadow: "var(--elev-glow-warning)" },
          "50%": { boxShadow: "0 0 0 1px rgba(245,158,11,0.4), 0 0 36px rgba(245,158,11,0.32)" },
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
        "glow-pulse-warning": "glow-pulse-warning 1.6s var(--ease-in-out) infinite",
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

- [ ] **Step 2: Typecheck**

```bash
cd frontend && npm run typecheck
```

Expected: PASS. If any TypeScript error mentions a removed token, ignore — Tailwind classes are strings, not typed, so failures will show up at lint time or as missing styles in the browser.

- [ ] **Step 3: Build to verify Tailwind config**

```bash
cd frontend && npm run lint
```

Expected: PASS.

- [ ] **Step 4: Commit**

```bash
cd /Users/himanshu/Git/aegis && git add frontend/tailwind.config.ts && git commit -m "feat(ui-overhaul): 1.3 — extend tailwind config with new tokens"
```

## Task 1.4: Wire Geist fonts in layout

**Files:**
- Modify: `frontend/src/app/layout.tsx`

- [ ] **Step 1: Read the current layout**

```bash
cat frontend/src/app/layout.tsx
```

- [ ] **Step 2: Edit imports and html className**

At the top, replace the current font imports (whatever they are) with:

```tsx
import { GeistSans } from "geist/font/sans";
import { GeistMono } from "geist/font/mono";
```

In the `<html>` element, update className so it includes both font variables. Example:

```tsx
<html lang="en" className={`${GeistSans.variable} ${GeistMono.variable}`}>
```

If the existing layout uses a different className or pattern, preserve any other classes that were there — just add the Geist variables.

- [ ] **Step 3: Run dev server and verify**

```bash
cd frontend && npm run dev
```

Open `http://localhost:3000`. Open DevTools → Computed on `body` → `font-family` should include `Geist`. Stop the server.

- [ ] **Step 4: Commit**

```bash
cd /Users/himanshu/Git/aegis && git add frontend/src/app/layout.tsx && git commit -m "feat(ui-overhaul): 1.4 — wire Geist Sans + Mono via next/font"
```

## Task 1.5: Sweep `--muted` → `--fg-muted`

**Files:**
- Modify: any file referencing `var(--muted)` in CSS

- [ ] **Step 1: Find direct CSS variable references**

```bash
cd frontend && grep -rn "var(--muted)" src/
```

Expected: zero or a small number of hits.

- [ ] **Step 2: Update each match**

For each match, replace `var(--muted)` with `var(--fg-muted)`. The Tailwind `muted` alias still resolves through `tailwind.config.ts` to `--fg-muted`, so `text-muted`/`bg-muted` class usages do NOT need changes — only direct `var(--muted)` references do.

- [ ] **Step 3: Verify clean**

```bash
cd frontend && grep -rn "var(--muted)" src/ || echo "clean"
```

Expected: `clean`.

- [ ] **Step 4: Run dev server, smoke-test a few pages**

Open `/`, `/workflows`, `/runs`, `/settings`. Muted text should still render.

- [ ] **Step 5: Commit**

```bash
cd /Users/himanshu/Git/aegis && git add -A frontend/src && git commit -m "feat(ui-overhaul): 1.5 — rename --muted to --fg-muted in CSS"
```

## Task 1.6: Build motion primitive — `useReducedMotion` strict hook

**Files:**
- Create: `frontend/src/components/motion/use-reduced-motion-strict.ts`

- [ ] **Step 1: Create the hook**

```ts
"use client";
import { useReducedMotion } from "framer-motion";

/**
 * Strict reduced-motion: returns true if the user has prefers-reduced-motion: reduce.
 * Components should disable looping or large motion when this is true.
 * Sub-120ms transitions (hover, button press) may still run — those don't trigger this gate.
 */
export function useReducedMotionStrict(): boolean {
  const prefers = useReducedMotion();
  return prefers === true;
}
```

- [ ] **Step 2: Typecheck**

```bash
cd frontend && npm run typecheck
```

Expected: PASS.

- [ ] **Step 3: Commit**

```bash
cd /Users/himanshu/Git/aegis && git add frontend/src/components/motion/use-reduced-motion-strict.ts && git commit -m "feat(ui-overhaul): 1.6 — add useReducedMotionStrict hook"
```

## Task 1.7: Build motion primitive — `<PageEnter>`

**Files:**
- Create: `frontend/src/components/motion/PageEnter.tsx`

- [ ] **Step 1: Create the component**

```tsx
"use client";
import { motion } from "framer-motion";
import { ReactNode } from "react";
import { useReducedMotionStrict } from "./use-reduced-motion-strict";

type Props = {
  children: ReactNode;
  className?: string;
  delay?: number;
};

export function PageEnter({ children, className, delay = 0 }: Props) {
  const reduce = useReducedMotionStrict();
  if (reduce) {
    return <div className={className}>{children}</div>;
  }
  return (
    <motion.div
      className={className}
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.32, ease: [0.16, 1, 0.3, 1], delay }}
    >
      {children}
    </motion.div>
  );
}
```

- [ ] **Step 2: Typecheck**

```bash
cd frontend && npm run typecheck
```

Expected: PASS.

- [ ] **Step 3: Commit**

```bash
cd /Users/himanshu/Git/aegis && git add frontend/src/components/motion/PageEnter.tsx && git commit -m "feat(ui-overhaul): 1.7 — add PageEnter motion primitive"
```

## Task 1.8: Build motion primitive — `<StaggerList>`

**Files:**
- Create: `frontend/src/components/motion/StaggerList.tsx`

- [ ] **Step 1: Create the component**

```tsx
"use client";
import { motion } from "framer-motion";
import { Children, ReactNode } from "react";
import { useReducedMotionStrict } from "./use-reduced-motion-strict";

type Props = {
  children: ReactNode;
  className?: string;
  itemClassName?: string;
  /** Max items to stagger; remaining items snap in instantly. Defaults to 8. */
  max?: number;
};

export function StaggerList({ children, className, itemClassName, max = 8 }: Props) {
  const reduce = useReducedMotionStrict();
  const items = Children.toArray(children);
  if (reduce) {
    return <div className={className}>{items.map((c, i) => <div key={i} className={itemClassName}>{c}</div>)}</div>;
  }
  return (
    <div className={className}>
      {items.map((child, i) => {
        const delay = Math.min(i, max) * 0.04;
        return (
          <motion.div
            key={i}
            className={itemClassName}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4, ease: [0.16, 1, 0.3, 1], delay }}
          >
            {child}
          </motion.div>
        );
      })}
    </div>
  );
}
```

- [ ] **Step 2: Typecheck**

```bash
cd frontend && npm run typecheck
```

Expected: PASS.

- [ ] **Step 3: Commit**

```bash
cd /Users/himanshu/Git/aegis && git add frontend/src/components/motion/StaggerList.tsx && git commit -m "feat(ui-overhaul): 1.8 — add StaggerList motion primitive"
```

## Task 1.9: Build motion primitives — `<HoverLift>`, `<NumberTween>`, `useGlowPulse`

**Files:**
- Create: `frontend/src/components/motion/HoverLift.tsx`
- Create: `frontend/src/components/motion/NumberTween.tsx`
- Create: `frontend/src/components/motion/use-glow-pulse.ts`
- Create: `frontend/src/components/motion/index.ts`

- [ ] **Step 1: Create HoverLift**

```tsx
// frontend/src/components/motion/HoverLift.tsx
"use client";
import { motion, type HTMLMotionProps } from "framer-motion";
import { ReactNode } from "react";

type Props = HTMLMotionProps<"div"> & { children: ReactNode };

/**
 * Hover-lift wrapper. Always active (hover transitions are <120ms — exempt from reduced-motion).
 * Lifts 1px and intensifies shadow on hover.
 */
export function HoverLift({ children, className, ...rest }: Props) {
  return (
    <motion.div
      className={className}
      whileHover={{ y: -1, transition: { duration: 0.12, ease: [0.16, 1, 0.3, 1] } }}
      {...rest}
    >
      {children}
    </motion.div>
  );
}
```

- [ ] **Step 2: Create NumberTween**

```tsx
// frontend/src/components/motion/NumberTween.tsx
"use client";
import { useEffect, useRef, useState } from "react";
import { useReducedMotionStrict } from "./use-reduced-motion-strict";

type Props = {
  value: number;
  /** Decimal places to display. Defaults to 0. */
  precision?: number;
  /** Append a suffix like "%" or "ms". */
  suffix?: string;
  /** Duration in ms. Defaults to 320. */
  duration?: number;
  className?: string;
};

export function NumberTween({ value, precision = 0, suffix = "", duration = 320, className }: Props) {
  const reduce = useReducedMotionStrict();
  const [display, setDisplay] = useState(value);
  const fromRef = useRef(value);
  const startTimeRef = useRef<number | null>(null);

  useEffect(() => {
    if (reduce) {
      setDisplay(value);
      return;
    }
    const from = fromRef.current;
    const to = value;
    if (from === to) return;
    startTimeRef.current = null;
    let raf = 0;
    const tick = (t: number) => {
      if (startTimeRef.current === null) startTimeRef.current = t;
      const elapsed = t - startTimeRef.current;
      const progress = Math.min(elapsed / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 3); // easeOutCubic
      setDisplay(from + (to - from) * eased);
      if (progress < 1) {
        raf = requestAnimationFrame(tick);
      } else {
        fromRef.current = to;
      }
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [value, duration, reduce]);

  return <span className={className}>{display.toFixed(precision)}{suffix}</span>;
}
```

- [ ] **Step 3: Create useGlowPulse hook**

```ts
// frontend/src/components/motion/use-glow-pulse.ts
"use client";
import { useReducedMotionStrict } from "./use-reduced-motion-strict";

type Variant = "primary" | "warning";

/**
 * Returns the className for an animated glow pulse, or empty string when
 * reduced motion is on. Use on canvas active nodes, live status dots, etc.
 */
export function useGlowPulse(variant: Variant = "primary"): string {
  const reduce = useReducedMotionStrict();
  if (reduce) return "";
  return variant === "warning" ? "animate-glow-pulse-warning" : "animate-glow-pulse";
}
```

- [ ] **Step 4: Create barrel index**

```ts
// frontend/src/components/motion/index.ts
export { PageEnter } from "./PageEnter";
export { StaggerList } from "./StaggerList";
export { HoverLift } from "./HoverLift";
export { NumberTween } from "./NumberTween";
export { useGlowPulse } from "./use-glow-pulse";
export { useReducedMotionStrict } from "./use-reduced-motion-strict";
```

- [ ] **Step 5: Typecheck**

```bash
cd frontend && npm run typecheck
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
cd /Users/himanshu/Git/aegis && git add frontend/src/components/motion/ && git commit -m "feat(ui-overhaul): 1.9 — add HoverLift, NumberTween, useGlowPulse, barrel"
```

## Task 1.10: Build `<GlassCard>` and `<GlowCard>` primitives

**Files:**
- Create: `frontend/src/components/ui/glass-card.tsx`
- Create: `frontend/src/components/ui/glow-card.tsx`

- [ ] **Step 1: Create GlassCard**

```tsx
// frontend/src/components/ui/glass-card.tsx
import { forwardRef, HTMLAttributes } from "react";
import { cn } from "@/lib/utils";

export const GlassCard = forwardRef<HTMLDivElement, HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div
      ref={ref}
      className={cn(
        "bg-surface backdrop-blur-md border border-border rounded-xl shadow-elev-1",
        className
      )}
      {...props}
    />
  )
);
GlassCard.displayName = "GlassCard";
```

- [ ] **Step 2: Create GlowCard**

```tsx
// frontend/src/components/ui/glow-card.tsx
import { forwardRef, HTMLAttributes } from "react";
import { cn } from "@/lib/utils";

type Variant = "primary" | "accent" | "success" | "destructive" | "warning";

type Props = HTMLAttributes<HTMLDivElement> & {
  variant?: Variant;
};

const VARIANT_SHADOW: Record<Variant, string> = {
  primary: "shadow-glow-primary",
  accent: "shadow-glow-accent",
  success: "shadow-glow-success",
  destructive: "shadow-glow-destructive",
  warning: "shadow-glow-warning",
};

export const GlowCard = forwardRef<HTMLDivElement, Props>(
  ({ className, variant = "primary", ...props }, ref) => (
    <div
      ref={ref}
      className={cn(
        "bg-surface backdrop-blur-md border border-border-glow rounded-xl",
        VARIANT_SHADOW[variant],
        className
      )}
      {...props}
    />
  )
);
GlowCard.displayName = "GlowCard";
```

- [ ] **Step 3: Typecheck**

```bash
cd frontend && npm run typecheck
```

Expected: PASS.

- [ ] **Step 4: Commit**

```bash
cd /Users/himanshu/Git/aegis && git add frontend/src/components/ui/glass-card.tsx frontend/src/components/ui/glow-card.tsx && git commit -m "feat(ui-overhaul): 1.10 — add GlassCard and GlowCard primitives"
```

## Task 1.11: Add shadcn primitives

**Files:**
- Created by shadcn CLI: `frontend/src/components/ui/popover.tsx`, `tabs.tsx`, `dropdown-menu.tsx`, `sheet.tsx`, `command.tsx`, `switch.tsx`. Also `dialog.tsx`, `tooltip.tsx`, `select.tsx` (replacing existing hand-rolled).

- [ ] **Step 1: Add Dialog (shadcn will overwrite the existing hand-rolled dialog.tsx)**

```bash
cd frontend && npx shadcn@latest add dialog
```

If prompted "File exists, overwrite?" → yes. The hand-rolled API may differ from shadcn's; we'll fix callers in Task 1.13.

- [ ] **Step 2: Add Popover**

```bash
cd frontend && npx shadcn@latest add popover
```

- [ ] **Step 3: Add Tooltip (overwrites existing)**

```bash
cd frontend && npx shadcn@latest add tooltip
```

- [ ] **Step 4: Add Select (overwrites existing)**

```bash
cd frontend && npx shadcn@latest add select
```

- [ ] **Step 5: Add remaining: Tabs, DropdownMenu, Sheet, Command, Switch**

```bash
cd frontend && npx shadcn@latest add tabs
cd frontend && npx shadcn@latest add dropdown-menu
cd frontend && npx shadcn@latest add sheet
cd frontend && npx shadcn@latest add command
cd frontend && npx shadcn@latest add switch
```

- [ ] **Step 6: Typecheck (may FAIL — that's expected)**

```bash
cd frontend && npm run typecheck
```

Failures here are likely from callers of the old hand-rolled Dialog/Tooltip/Select APIs. Note the list. Task 1.13 fixes them.

- [ ] **Step 7: Commit shadcn additions**

```bash
cd /Users/himanshu/Git/aegis && git add frontend/src/components/ui/ frontend/components.json frontend/package.json frontend/package-lock.json && git commit -m "feat(ui-overhaul): 1.11 — add shadcn primitives (dialog, popover, tooltip, select, tabs, dropdown-menu, sheet, command, switch)"
```

## Task 1.12: Apply glass theming to shadcn primitives

**Files:**
- Modify: `frontend/src/components/ui/dialog.tsx`
- Modify: `frontend/src/components/ui/popover.tsx`
- Modify: `frontend/src/components/ui/tooltip.tsx`
- Modify: `frontend/src/components/ui/dropdown-menu.tsx`
- Modify: `frontend/src/components/ui/sheet.tsx`
- Modify: `frontend/src/components/ui/select.tsx`
- Modify: `frontend/src/components/ui/command.tsx`

- [ ] **Step 1: Restyle Dialog**

Find the `DialogContent` className. Replace its surface classes with:

```
"bg-surface-elevated backdrop-blur-xl border border-border rounded-xl shadow-elev-3 max-w-[min(32rem,calc(100vw-2rem))]"
```

Find the `DialogOverlay` className. Replace with:

```
"fixed inset-0 z-50 bg-bg/40 backdrop-blur-xs data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0"
```

- [ ] **Step 2: Restyle Popover, Tooltip, DropdownMenu**

For each `*Content` component, set surface to:

```
"bg-surface-elevated backdrop-blur-md border border-border rounded-lg shadow-elev-2"
```

Tooltip uses smaller padding: `"px-2.5 py-1.5 text-xs"`. Keep that.

- [ ] **Step 3: Restyle Sheet**

`SheetContent` surface: `"bg-surface-elevated backdrop-blur-xl border-l border-border shadow-elev-3"` (the `border-l` is for the default right-side variant).

- [ ] **Step 4: Restyle Select**

`SelectTrigger` background: `"bg-surface-input border-border rounded-md h-10"`.
`SelectContent`: `"bg-surface-elevated backdrop-blur-md border border-border rounded-lg shadow-elev-2"`.

- [ ] **Step 5: Restyle Command**

`Command` surface: `"bg-surface-elevated backdrop-blur-xl border border-border rounded-xl"`.
`CommandInput` wrapper: ensure it has a search icon prefix slot (shadcn uses lucide `Search`).
`CommandItem` hover/selected state: `"data-[selected=true]:bg-surface-hover"`.

- [ ] **Step 6: Typecheck**

```bash
cd frontend && npm run typecheck
```

Failures still expected from old-API callers (Task 1.13).

- [ ] **Step 7: Commit**

```bash
cd /Users/himanshu/Git/aegis && git add frontend/src/components/ui/ && git commit -m "feat(ui-overhaul): 1.12 — apply glass theme to shadcn primitives"
```

## Task 1.13: Migrate callers of old Dialog/Tooltip/Select to shadcn API

**Files:**
- Modify: every file that previously imported from `@/components/ui/dialog` / `@/components/ui/tooltip` / `@/components/ui/select` if the old hand-rolled API differs from shadcn's.

- [ ] **Step 1: Find dialog callers**

```bash
cd frontend && grep -rn "from \"@/components/ui/dialog\"" src/
```

shadcn's Dialog API uses `<Dialog>`, `<DialogContent>`, `<DialogHeader>`, `<DialogTitle>`, `<DialogDescription>`, `<DialogFooter>`, `<DialogTrigger>`. For each caller:

  1. Check the existing usage.
  2. If it imports `Dialog` only (controlled via `open`/`onOpenChange`), it almost certainly still works — shadcn keeps that API.
  3. If it uses props like `title` or `description` as direct props on `<Dialog>`, refactor to use `<DialogHeader>`/`<DialogTitle>`/`<DialogDescription>` subcomponents.
  4. Children placement may change — wrap content in `<DialogContent>` if it wasn't already.

- [ ] **Step 2: Update each caller**

Migrate one caller at a time, running `npm run typecheck` after each to catch regressions.

- [ ] **Step 3: Find tooltip callers**

```bash
cd frontend && grep -rn "from \"@/components/ui/tooltip\"" src/
```

shadcn's Tooltip needs `<TooltipProvider>` somewhere up the tree (usually at the root layout). For each caller:
- Wrap with `<TooltipProvider>` if not already wrapped globally.
- Use `<Tooltip>` `<TooltipTrigger asChild>` `<children/>` `</TooltipTrigger>` `<TooltipContent>` text `</TooltipContent>` `</Tooltip>`.

Add `<TooltipProvider>` to `frontend/src/app/layout.tsx` at the same level as ErrorBoundary, so it covers the whole app.

- [ ] **Step 4: Find select callers**

```bash
cd frontend && grep -rn "from \"@/components/ui/select\"" src/
```

shadcn's Select API uses `<Select>` (with `value`/`onValueChange`), `<SelectTrigger>` (the visible button), `<SelectValue>` (placeholder/display), `<SelectContent>` (the dropdown), `<SelectItem value="...">` (each option). Migrate each caller accordingly.

- [ ] **Step 5: Typecheck and lint**

```bash
cd frontend && npm run typecheck && npm run lint
```

Expected: PASS. If still failing, repeat step 2 until clean.

- [ ] **Step 6: Run dev and smoke-test**

```bash
cd frontend && npm run dev
```

Open any page with a dialog (e.g. settings credentials delete confirmation), open any page with tooltips (run details), open any page with a select (workflow filters). Verify each renders and works. Stop server.

- [ ] **Step 7: Commit**

```bash
cd /Users/himanshu/Git/aegis && git add -A frontend/src && git commit -m "feat(ui-overhaul): 1.13 — migrate dialog/tooltip/select callers to shadcn API"
```

## Task 1.14: Rewrite CommandPalette with shadcn Command

**Files:**
- Modify: `frontend/src/components/layout/CommandPalette.tsx`

- [ ] **Step 1: Read existing CommandPalette to extract its actions list and keyboard binding**

```bash
cat frontend/src/components/layout/CommandPalette.tsx
```

Note: the list of actions (navigate to workflows, new workflow, settings, etc.), the Cmd+K binding, any `isEditableTarget` guard, and the localStorage usage if any.

- [ ] **Step 2: Rewrite using shadcn Command**

```tsx
// frontend/src/components/layout/CommandPalette.tsx
"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Search, Plus, Settings, Layers, BarChart3, Shield, FileText } from "lucide-react";
import {
  Command,
  CommandDialog,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command";
import { isEditableTarget } from "@/lib/shortcuts";

const RECENTS_KEY = "aegis:command-recents";
const MAX_RECENTS = 5;

type Action = {
  id: string;
  label: string;
  group: "Navigate" | "Create" | "Help";
  icon: React.ComponentType<{ className?: string }>;
  perform: (router: ReturnType<typeof useRouter>) => void;
};

const ACTIONS: Action[] = [
  { id: "nav:workflows", label: "Workflows", group: "Navigate", icon: Layers,
    perform: (r) => r.push("/workflows") },
  { id: "nav:runs", label: "Runs", group: "Navigate", icon: FileText,
    perform: (r) => r.push("/runs") },
  { id: "nav:observability", label: "Observability", group: "Navigate", icon: BarChart3,
    perform: (r) => r.push("/observability") },
  { id: "nav:templates", label: "Templates", group: "Navigate", icon: Layers,
    perform: (r) => r.push("/templates") },
  { id: "nav:guardrails", label: "Guardrails", group: "Navigate", icon: Shield,
    perform: (r) => r.push("/guardrails") },
  { id: "nav:settings", label: "Settings", group: "Navigate", icon: Settings,
    perform: (r) => r.push("/settings") },
  { id: "create:workflow", label: "New workflow", group: "Create", icon: Plus,
    perform: (r) => r.push("/workflows/new") },
];

export function CommandPalette() {
  const [open, setOpen] = useState(false);
  const [recents, setRecents] = useState<string[]>([]);
  const router = useRouter();

  useEffect(() => {
    try {
      const raw = localStorage.getItem(RECENTS_KEY);
      if (raw) setRecents(JSON.parse(raw) as string[]);
    } catch {}
  }, []);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        if (isEditableTarget(e.target)) return;
        e.preventDefault();
        setOpen((o) => !o);
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, []);

  const recordRecent = (id: string) => {
    const next = [id, ...recents.filter((r) => r !== id)].slice(0, MAX_RECENTS);
    setRecents(next);
    try { localStorage.setItem(RECENTS_KEY, JSON.stringify(next)); } catch {}
  };

  const run = (action: Action) => {
    recordRecent(action.id);
    setOpen(false);
    action.perform(router);
  };

  const groupBy = (items: Action[]) => {
    const map = new Map<string, Action[]>();
    for (const a of items) {
      const arr = map.get(a.group) ?? [];
      arr.push(a);
      map.set(a.group, arr);
    }
    return Array.from(map.entries());
  };

  const recentActions = recents
    .map((id) => ACTIONS.find((a) => a.id === id))
    .filter((a): a is Action => !!a);

  return (
    <CommandDialog open={open} onOpenChange={setOpen}>
      <CommandInput placeholder="Search actions, workflows, settings..." />
      <CommandList>
        <CommandEmpty>No matches. Try a different search.</CommandEmpty>
        {recentActions.length > 0 && (
          <CommandGroup heading="Recent">
            {recentActions.map((a) => (
              <CommandItem key={a.id} onSelect={() => run(a)}>
                <a.icon className="mr-2 h-4 w-4" />
                {a.label}
              </CommandItem>
            ))}
          </CommandGroup>
        )}
        {groupBy(ACTIONS).map(([group, items]) => (
          <CommandGroup key={group} heading={group}>
            {items.map((a) => (
              <CommandItem key={a.id} onSelect={() => run(a)}>
                <a.icon className="mr-2 h-4 w-4" />
                {a.label}
              </CommandItem>
            ))}
          </CommandGroup>
        ))}
      </CommandList>
    </CommandDialog>
  );
}
```

- [ ] **Step 3: Wire CommandPalette in the layout**

Open `frontend/src/components/layout/AppShell.tsx`. Confirm `<CommandPalette />` is rendered once at the layout level. If the API changed (open/setOpen props are now internal), remove any old `open`/`onOpenChange` props from AppShell and any related state — Cmd+K binding is now self-contained.

- [ ] **Step 4: Typecheck**

```bash
cd frontend && npm run typecheck
```

Expected: PASS.

- [ ] **Step 5: Smoke test in dev**

```bash
cd frontend && npm run dev
```

Press Cmd+K. The palette opens. Try fuzzy search ("wo" should match Workflows). Pick an action. Confirm it navigates. Reopen — your last action is in the "Recent" group. Stop server.

- [ ] **Step 6: Commit**

```bash
cd /Users/himanshu/Git/aegis && git add frontend/src/components/layout/CommandPalette.tsx frontend/src/components/layout/AppShell.tsx && git commit -m "feat(ui-overhaul): 1.14 — rewrite CommandPalette with shadcn Command + recents"
```

## Task 1.15: Restyle existing primitives (Button, Input, Textarea, Badge, Card, Alert, EmptyState)

**Files:**
- Modify: `frontend/src/components/ui/button.tsx`
- Modify: `frontend/src/components/ui/input.tsx`
- Modify: `frontend/src/components/ui/textarea.tsx`
- Modify: `frontend/src/components/ui/badge.tsx`
- Modify: `frontend/src/components/ui/card.tsx`
- Modify: `frontend/src/components/ui/alert.tsx`
- Modify: `frontend/src/components/ui/empty-state.tsx`

- [ ] **Step 1: Update Button variants**

Open `button.tsx`. In the `cva` block, update variants to:

```tsx
variants: {
  variant: {
    default: "bg-primary text-primary-foreground hover:bg-primary-600 shadow-elev-1 active:scale-[0.98] transition-transform duration-fast",
    outline: "border border-border bg-transparent text-foreground hover:bg-surface-hover active:scale-[0.98] transition-transform duration-fast",
    ghost: "text-muted hover:bg-surface-hover hover:text-foreground active:scale-[0.98] transition-transform duration-fast",
    destructive: "bg-destructive text-white hover:bg-destructive/90 shadow-elev-1 active:scale-[0.98] transition-transform duration-fast",
  },
  size: {
    default: "h-9 px-4",
    sm: "h-8 px-3 text-xs rounded-md",
    lg: "h-10 px-5",
    icon: "h-9 w-9",
    "icon-lg": "h-11 w-11",
  },
},
```

- [ ] **Step 2: Update Input**

Open `input.tsx`. Set className base to:

```
"flex h-10 w-full rounded-md border border-border bg-surface-input px-3 text-sm placeholder:text-muted focus-visible:border-border-strong focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-bg disabled:cursor-not-allowed disabled:opacity-50"
```

- [ ] **Step 3: Update Textarea**

Same surface treatment as Input. Min height `min-h-[80px]`.

- [ ] **Step 4: Update Badge**

Base className:

```
"inline-flex items-center gap-1 rounded-md border px-2.5 py-1 text-xs font-medium"
```

Variants — keep existing variant set if present, but ensure each variant produces foreground + glow-tinted border:

```tsx
default: "bg-surface text-foreground border-border",
primary: "bg-primary-muted text-primary-300 border-primary/20",
success: "bg-success/12 text-success border-success/20",
warning: "bg-warning/12 text-warning border-warning/20",
destructive: "bg-destructive/12 text-destructive border-destructive/20",
```

- [ ] **Step 5: Update Card**

Card surface:

```
"rounded-xl border border-border bg-surface backdrop-blur-md shadow-elev-1"
```

Remove `overflow-hidden` if present (let callers control overflow).

CardHeader: `"px-5 py-4 border-b border-border"`.
CardContent: `"px-5 py-4"`.

- [ ] **Step 6: Update Alert**

Alert surface:

```
"relative w-full rounded-lg border p-4 backdrop-blur-md"
```

Variants: tint the surface and border per status, same color logic as Badge.

- [ ] **Step 7: Update EmptyState**

If a `variant` prop already exists (from P3.8), keep it. Update surface to:

```
"flex flex-col items-center justify-center rounded-xl border border-border bg-surface backdrop-blur-md p-12 text-center shadow-elev-1"
```

- [ ] **Step 8: Typecheck and lint**

```bash
cd frontend && npm run typecheck && npm run lint
```

Expected: PASS.

- [ ] **Step 9: Smoke test in dev**

Open `/`, `/workflows`, `/runs`, `/settings`. Each should render. Buttons should still look like buttons. Inputs should have the new translucent dark fill. Nothing should crash.

- [ ] **Step 10: Commit**

```bash
cd /Users/himanshu/Git/aegis && git add frontend/src/components/ui/ && git commit -m "feat(ui-overhaul): 1.15 — restyle Button, Input, Textarea, Badge, Card, Alert, EmptyState"
```

## Task 1.16: Phase 1 exit verification

**Files:** none (verification only).

- [ ] **Step 1: Clean typecheck and lint**

```bash
cd frontend && npm run typecheck && npm run lint
```

Expected: PASS.

- [ ] **Step 2: Click through every route in dev**

```bash
cd frontend && npm run dev
```

Visit each:
- `/`
- `/workflows`
- `/workflows/new`
- `/workflows/[any-id]/edit`
- `/runs`
- `/runs/[any-id]`
- `/observability`
- `/templates`
- `/settings`
- `/guardrails`

For each: no console errors, page renders, focus rings visible when tabbing, dialogs/tooltips/selects work.

- [ ] **Step 3: Verify font and tokens**

DevTools → Computed on body: `font-family` includes `Geist`. On html: `--bg: #08080a`, `--fg-muted: #b4b4b8`.

- [ ] **Step 4: Verify shadcn Dialog backdrop blur**

Open any dialog (settings credentials delete). Confirm the overlay has visible backdrop blur.

- [ ] **Step 5: Verify Cmd+K**

Press Cmd+K. Palette opens. Type a query, select an action. Confirm navigation works and the action appears under "Recent" next time.

- [ ] **Step 6: Phase 1 commit marker (optional)**

If you'd like a marker commit on `main` denoting Phase 1 done, write a short empty commit:

```bash
cd /Users/himanshu/Git/aegis && git commit --allow-empty -m "milestone(ui-overhaul): phase 1 — foundation complete"
```

---

# Phase 2 — Dashboard redesign

Goal: proof surface. After this phase, the dashboard looks reskinned; the rest of the app looks worse by comparison.

## Task 2.1: Build `<LiveDot>`

**Files:**
- Create: `frontend/src/components/dashboard/LiveDot.tsx`

- [ ] **Step 1: Create component**

```tsx
// frontend/src/components/dashboard/LiveDot.tsx
"use client";
import { cn } from "@/lib/utils";
import { useGlowPulse } from "@/components/motion";

type Props = {
  connected: boolean;
  className?: string;
};

export function LiveDot({ connected, className }: Props) {
  const pulse = useGlowPulse("primary");
  return (
    <span
      className={cn(
        "inline-block h-2 w-2 rounded-full",
        connected ? `bg-success ${pulse}` : "bg-muted",
        className
      )}
      aria-label={connected ? "Live updates connected" : "Live updates disconnected"}
    />
  );
}
```

- [ ] **Step 2: Typecheck**

```bash
cd frontend && npm run typecheck
```

Expected: PASS.

- [ ] **Step 3: Commit**

```bash
cd /Users/himanshu/Git/aegis && git add frontend/src/components/dashboard/LiveDot.tsx && git commit -m "feat(ui-overhaul): 2.1 — add LiveDot component"
```

## Task 2.2: Build `<TrendPill>`

**Files:**
- Create: `frontend/src/components/dashboard/TrendPill.tsx`

- [ ] **Step 1: Create component**

```tsx
// frontend/src/components/dashboard/TrendPill.tsx
import { ArrowUpRight, ArrowDownRight, Minus } from "lucide-react";
import { cn } from "@/lib/utils";

type Props = {
  /** Signed percentage change, e.g. 12 or -8.5. Use 0 for neutral. */
  deltaPercent: number;
  /** Label for the comparison window, e.g. "vs prior 7d". */
  comparisonLabel?: string;
  className?: string;
};

export function TrendPill({ deltaPercent, comparisonLabel = "vs prior 7d", className }: Props) {
  const direction = deltaPercent > 0 ? "up" : deltaPercent < 0 ? "down" : "flat";
  const Icon = direction === "up" ? ArrowUpRight : direction === "down" ? ArrowDownRight : Minus;
  const tone =
    direction === "up" ? "text-success" :
    direction === "down" ? "text-destructive" :
    "text-muted";
  const sign = deltaPercent > 0 ? "+" : "";
  return (
    <span className={cn("inline-flex items-center gap-1 text-xs", tone, className)}>
      <Icon className="h-3 w-3" />
      {sign}{deltaPercent.toFixed(0)}% <span className="text-muted">{comparisonLabel}</span>
    </span>
  );
}
```

- [ ] **Step 2: Typecheck and commit**

```bash
cd frontend && npm run typecheck
cd /Users/himanshu/Git/aegis && git add frontend/src/components/dashboard/TrendPill.tsx && git commit -m "feat(ui-overhaul): 2.2 — add TrendPill component"
```

## Task 2.3: Build `<Sparkline>`

**Files:**
- Create: `frontend/src/components/dashboard/Sparkline.tsx`

- [ ] **Step 1: Create component**

```tsx
// frontend/src/components/dashboard/Sparkline.tsx
"use client";
import { useId, useEffect, useState } from "react";
import { useReducedMotionStrict } from "@/components/motion";

type Props = {
  data: number[];
  color?: string;
  height?: number;
  /** Animates the stroke drawing on first mount. Defaults to true. */
  drawOnMount?: boolean;
};

/**
 * Compact area sparkline. Renders inline (no width attribute — fills container).
 * Width-based aspect via SVG viewBox; the polyline scales fluidly.
 */
export function Sparkline({ data, color = "var(--primary)", height = 24, drawOnMount = true }: Props) {
  const id = useId();
  const reduce = useReducedMotionStrict();
  const [drawn, setDrawn] = useState(!drawOnMount || reduce);

  useEffect(() => {
    if (!drawOnMount || reduce) return;
    const t = setTimeout(() => setDrawn(true), 16);
    return () => clearTimeout(t);
  }, [drawOnMount, reduce]);

  if (!data || data.length < 2) {
    return <div className="h-6 text-xs text-muted">No trend data</div>;
  }

  const max = Math.max(...data);
  const min = Math.min(...data);
  const range = max - min || 1;
  const w = 100;
  const h = height;
  const stepX = w / (data.length - 1);
  const points = data.map((v, i) => {
    const x = i * stepX;
    const y = h - ((v - min) / range) * h;
    return `${x.toFixed(2)},${y.toFixed(2)}`;
  });
  const polyline = points.join(" ");
  const area = `0,${h} ${polyline} ${w},${h}`;

  return (
    <svg
      viewBox={`0 0 ${w} ${h}`}
      preserveAspectRatio="none"
      className="w-full"
      style={{ height }}
      aria-hidden
    >
      <defs>
        <linearGradient id={`spark-fill-${id}`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity="0.3" />
          <stop offset="100%" stopColor={color} stopOpacity="0" />
        </linearGradient>
      </defs>
      <polygon points={area} fill={`url(#spark-fill-${id})`} />
      <polyline
        points={polyline}
        fill="none"
        stroke={color}
        strokeWidth="1.5"
        strokeLinejoin="round"
        strokeLinecap="round"
        style={{
          strokeDasharray: drawn ? "none" : "1000",
          strokeDashoffset: drawn ? 0 : 1000,
          transition: "stroke-dashoffset 600ms var(--ease-out)",
        }}
      />
    </svg>
  );
}
```

- [ ] **Step 2: Typecheck and commit**

```bash
cd frontend && npm run typecheck
cd /Users/himanshu/Git/aegis && git add frontend/src/components/dashboard/Sparkline.tsx && git commit -m "feat(ui-overhaul): 2.3 — add Sparkline component"
```

## Task 2.4: Build `<StatCard>`

**Files:**
- Create: `frontend/src/components/dashboard/StatCard.tsx`

- [ ] **Step 1: Create component**

```tsx
// frontend/src/components/dashboard/StatCard.tsx
import { ReactNode } from "react";
import { GlassCard } from "@/components/ui/glass-card";
import { GlowCard } from "@/components/ui/glow-card";
import { cn } from "@/lib/utils";

type Props = {
  eyebrow: string;
  value: ReactNode;
  footer?: ReactNode;
  variant?: "default" | "highlight";
  className?: string;
};

export function StatCard({ eyebrow, value, footer, variant = "default", className }: Props) {
  const inner = (
    <div className="flex flex-col gap-2">
      <div className="text-micro">{eyebrow}</div>
      <div className="text-display">{value}</div>
      {footer && <div>{footer}</div>}
    </div>
  );
  return variant === "highlight"
    ? <GlowCard variant="primary" className={cn("p-5", className)}>{inner}</GlowCard>
    : <GlassCard className={cn("p-5", className)}>{inner}</GlassCard>;
}
```

- [ ] **Step 2: Typecheck and commit**

```bash
cd frontend && npm run typecheck
cd /Users/himanshu/Git/aegis && git add frontend/src/components/dashboard/StatCard.tsx && git commit -m "feat(ui-overhaul): 2.4 — add StatCard component"
```

## Task 2.5: Build `<HeroGreeting>`

**Files:**
- Create: `frontend/src/components/dashboard/HeroGreeting.tsx`

- [ ] **Step 1: Create component**

```tsx
// frontend/src/components/dashboard/HeroGreeting.tsx
"use client";
import Link from "next/link";
import { Plus, ArrowRight } from "lucide-react";
import { Button } from "@/components/ui/button";

type Props = {
  /** User's display name, or null/undefined for a nameless greeting. */
  name?: string | null;
  /** Optional secondary info line. */
  meta?: string;
  /** Last-edited workflow id, used to power the "Open last canvas" CTA. Hide CTA if absent. */
  lastWorkflowId?: string | null;
};

function partOfDay(d = new Date()): "morning" | "afternoon" | "evening" {
  const h = d.getHours();
  if (h < 12) return "morning";
  if (h < 18) return "afternoon";
  return "evening";
}

export function HeroGreeting({ name, meta, lastWorkflowId }: Props) {
  const part = partOfDay();
  return (
    <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
      <div className="flex flex-col gap-2">
        <h1 className="text-display">
          Good {part}{name ? ", " : ""}
          {name && <span className="text-gradient-primary">{name}</span>}
        </h1>
        {meta && <p className="text-caption">{meta}</p>}
      </div>
      <div className="flex flex-col gap-2 sm:flex-row">
        <Button asChild variant="default">
          <Link href="/workflows/new"><Plus className="mr-2 h-4 w-4" />New workflow</Link>
        </Button>
        {lastWorkflowId && (
          <Button asChild variant="outline">
            <Link href={`/workflows/${lastWorkflowId}/edit`}>
              Open last canvas <ArrowRight className="ml-2 h-4 w-4" />
            </Link>
          </Button>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Typecheck and commit**

```bash
cd frontend && npm run typecheck
cd /Users/himanshu/Git/aegis && git add frontend/src/components/dashboard/HeroGreeting.tsx && git commit -m "feat(ui-overhaul): 2.5 — add HeroGreeting component"
```

## Task 2.6: Build `<WorkflowCard>`

**Files:**
- Create: `frontend/src/components/dashboard/WorkflowCard.tsx`

- [ ] **Step 1: Create component**

```tsx
// frontend/src/components/dashboard/WorkflowCard.tsx
"use client";
import Link from "next/link";
import { GlassCard } from "@/components/ui/glass-card";
import { HoverLift } from "@/components/motion";
import { formatRelativeTime } from "@/lib/format-date";
import { pluralize } from "@/lib/pluralize";

type Workflow = {
  id: string;
  name: string;
  description?: string | null;
  last_run_at?: string | null;
  last_run_status?: "completed" | "failed" | "running" | "cancelled" | "pending" | null;
  runs_this_week?: number;
};

type Props = {
  workflow: Workflow;
};

const DOT_BY_STATUS: Record<string, string> = {
  completed: "bg-success",
  failed: "bg-destructive",
  running: "bg-warning",
  cancelled: "bg-muted",
  pending: "bg-muted",
};

export function WorkflowCard({ workflow }: Props) {
  const dot = workflow.last_run_status ? DOT_BY_STATUS[workflow.last_run_status] ?? "bg-muted" : "bg-muted";
  return (
    <Link href={`/workflows/${workflow.id}/edit`} className="block group">
      <HoverLift>
        <GlassCard className="relative overflow-hidden p-4">
          <span
            className="absolute left-0 top-0 h-0.5 w-0 bg-gradient-to-r from-primary-500 to-accent-500 transition-all duration-fast group-hover:w-full"
            aria-hidden
          />
          <div className="flex items-start justify-between gap-2">
            <h3 className="text-body-lg font-semibold truncate">{workflow.name}</h3>
          </div>
          {workflow.description && (
            <p className="text-caption mt-1 line-clamp-1">{workflow.description}</p>
          )}
          <div className="mt-3 flex items-center gap-3 text-caption">
            <span className="inline-flex items-center gap-1.5">
              <span className={`h-1.5 w-1.5 rounded-full ${dot}`} />
              {workflow.last_run_at ? `Last run: ${formatRelativeTime(workflow.last_run_at)}` : "No runs yet"}
            </span>
            {workflow.runs_this_week !== undefined && (
              <>
                <span className="text-subtle">•</span>
                <span>{pluralize(workflow.runs_this_week, "run")} this week</span>
              </>
            )}
          </div>
        </GlassCard>
      </HoverLift>
    </Link>
  );
}
```

If `pluralize` isn't in `frontend/src/lib/pluralize.ts` yet (P1.12 shipped a `format.ts` or similar — check), create it now with the implementation from the spec:

```ts
// frontend/src/lib/pluralize.ts (only if missing)
export const pluralize = (n: number, singular: string, plural = singular + "s") =>
  `${n} ${n === 1 ? singular : plural}`;
```

- [ ] **Step 2: Verify pluralize exists or create it**

```bash
cd frontend && grep -rn "export.*pluralize" src/lib/
```

If empty, create the file above.

- [ ] **Step 3: Typecheck and commit**

```bash
cd frontend && npm run typecheck
cd /Users/himanshu/Git/aegis && git add frontend/src/components/dashboard/WorkflowCard.tsx frontend/src/lib/pluralize.ts 2>/dev/null
cd /Users/himanshu/Git/aegis && git commit -m "feat(ui-overhaul): 2.6 — add WorkflowCard component"
```

## Task 2.7: Build `<RecentRunRow>`

**Files:**
- Create: `frontend/src/components/dashboard/RecentRunRow.tsx`

- [ ] **Step 1: Create component**

```tsx
// frontend/src/components/dashboard/RecentRunRow.tsx
"use client";
import Link from "next/link";
import { motion } from "framer-motion";
import { useGlowPulse } from "@/components/motion";
import { formatRelativeTime } from "@/lib/format-date";

type Run = {
  id: string;
  workflow_name: string | null;
  status: "completed" | "failed" | "running" | "cancelled" | "pending" | "awaiting_approval";
  duration_ms?: number | null;
  created_at: string;
};

const COLOR_BY_STATUS: Record<Run["status"], string> = {
  completed: "bg-success",
  failed: "bg-destructive",
  running: "bg-warning",
  cancelled: "bg-muted",
  pending: "bg-muted",
  awaiting_approval: "bg-warning",
};

function formatDuration(ms?: number | null): string {
  if (!ms && ms !== 0) return "—";
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

export function RecentRunRow({ run }: { run: Run }) {
  const pulse = useGlowPulse("primary");
  const dotClass =
    run.status === "running"
      ? `${COLOR_BY_STATUS.running} ${pulse}`
      : COLOR_BY_STATUS[run.status];
  return (
    <motion.div layout="position">
      <Link
        href={`/runs/${run.id}`}
        className="flex items-center gap-3 rounded-md px-3 py-2 hover:bg-surface-hover transition-colors duration-instant"
      >
        <span className={`inline-block h-2 w-2 rounded-full ${dotClass}`} />
        <span className="text-body truncate flex-1">{run.workflow_name ?? "Unnamed"}</span>
        <span className="text-caption font-mono">{formatDuration(run.duration_ms)}</span>
        <span className="text-caption">{formatRelativeTime(run.created_at)}</span>
      </Link>
    </motion.div>
  );
}
```

- [ ] **Step 2: Typecheck and commit**

```bash
cd frontend && npm run typecheck
cd /Users/himanshu/Git/aegis && git add frontend/src/components/dashboard/RecentRunRow.tsx && git commit -m "feat(ui-overhaul): 2.7 — add RecentRunRow component"
```

## Task 2.8: Rewrite DashboardView

**Files:**
- Modify: `frontend/src/components/dashboard/DashboardView.tsx`

- [ ] **Step 1: Read existing DashboardView**

```bash
cat frontend/src/components/dashboard/DashboardView.tsx | head -80
```

Note the data sources (which `useQuery` calls), the SSE provider usage, and any current sub-components.

- [ ] **Step 2: Rewrite DashboardView using new components**

Goal layout:

```
<PageEnter>
  <HeroGreeting ... />
  <StaggerList className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mt-8">
    <StatCard eyebrow="TOTAL RUNS" value={<NumberTween value={totalRuns} />} footer={<TrendPill deltaPercent={runsDelta} />} />
    <StatCard variant="highlight" eyebrow="PASS RATE" value={passRateNode} footer={<TrendPill deltaPercent={passRateDelta} />} />
    <StatCard eyebrow="AVG LATENCY" value={<NumberTween value={avgLatency} suffix="ms" />} footer={<Sparkline data={sparkData} />} />
    <StatCard eyebrow="LAST RUN" value={<RelativeTimeLabel ts={lastRunAt} />} footer={<LiveDot connected={sseConnected} />} />
  </StaggerList>
  <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mt-8">
    <WorkflowsColumn />
    <RecentRunsColumn />
  </div>
</PageEnter>
```

Implementation notes:
- Reuse the existing `useQuery` calls for workflows and observability summary. Don't refetch or add new ones.
- `totalRuns`, `passRate`, `avgLatency`, `lastRunAt` come from observability summary. If a field isn't present in the API response, compute from existing fields or omit (don't fake it).
- `runsDelta` / `passRateDelta`: compute (`current - prior) / prior * 100`. If no prior, pass 0 and let TrendPill show neutral.
- `sparkData`: aggregate from existing hourly rollups for 14 days. If `/api/observability/summary` doesn't expose 14d trend, **skip the sparkline and render a small caption** ("No 14d trend") in its place — note this in the phase report. Don't add a backend endpoint.
- `passRateNode`: if passRate >= 80, wrap the number in `<span className="text-gradient-primary">`. Otherwise plain.
- The "Recent Runs" SSE wiring should subscribe to the existing `ObservabilityStreamProvider` (or whatever it's called) and prepend rows on `run_started`, update on `run_completed`/etc. The whole list uses `<motion.div layout>` so order changes animate.

The `WorkflowsColumn` and `RecentRunsColumn` should be local components inside DashboardView (file is fine to be ~250 lines for this). Each renders:

WorkflowsColumn:
- Header row: eyebrow "WORKFLOWS" + a small `+ New` Button.
- Search Input.
- `<StaggerList>` of `<WorkflowCard>` filtered by search query (case-insensitive name/description match), max 6.
- "View all N workflows →" Link below if `total > 6`.

RecentRunsColumn:
- Header row: eyebrow "RECENT RUNS" + `<LiveDot connected={sseConnected} />`.
- `<StaggerList>` of `<RecentRunRow>`, max 8.
- "View all N runs →" Link.

- [ ] **Step 3: Typecheck**

```bash
cd frontend && npm run typecheck
```

Expected: PASS. If failing, fix imports and types.

- [ ] **Step 4: Smoke test in dev**

```bash
cd frontend && npm run dev
```

Open `/`. Confirm:
- Greeting at top with gradient name.
- Four stat cards (one with glow, others plain).
- Two columns with workflows and recent runs.
- Search filters workflow cards in real time.
- Live dot pulses if SSE provider is connected.

Trigger a run from another tab/window and watch the Recent Runs column add a row at the top.

- [ ] **Step 5: Mobile check**

DevTools → toggle device → 375px. Confirm stat cards become 2x2 grid; columns stack with Recent Runs on top.

- [ ] **Step 6: Commit**

```bash
cd /Users/himanshu/Git/aegis && git add frontend/src/components/dashboard/DashboardView.tsx && git commit -m "feat(ui-overhaul): 2.8 — rewrite DashboardView with new components and layout"
```

## Task 2.9: Phase 2 exit verification

**Files:** none.

- [ ] **Step 1: Lint and typecheck clean**

```bash
cd frontend && npm run typecheck && npm run lint
```

- [ ] **Step 2: Reduced motion check**

DevTools → emulate prefers-reduced-motion: reduce. Reload `/`. Confirm: stagger entrance becomes instant, glow pulse on LiveDot stops, but Hover lift (mouse over a workflow card) still works.

- [ ] **Step 3: Tab through page**

Tab the keyboard. Every interactive element shows the focus ring (P0.7 ring shouldn't have been broken — verify).

- [ ] **Step 4: Screen reader spot check**

VoiceOver: open `/runs/{some-running-run-id}`. Status change should still announce via the aria-live region (P0.8). It hasn't been touched in Phase 2 — just confirm it didn't regress.

- [ ] **Step 5: Phase 2 marker commit**

```bash
cd /Users/himanshu/Git/aegis && git commit --allow-empty -m "milestone(ui-overhaul): phase 2 — dashboard complete"
```

---

# Phase 3 — Canvas re-skin

Goal: canvas becomes the showpiece. Split into chrome (3.1), category mapping (3.2-3.3), BaseNode (3.4), category nodes (3.5), edges (3.6-3.7), inspector (3.8-3.9), node palette (3.10).

## Task 3.1: Canvas chrome — floating header

**Files:**
- Modify: `frontend/src/components/canvas/WorkflowCanvas.tsx`

- [ ] **Step 1: Find the current header rendering**

```bash
grep -n "Save\|Run\|Workflow name" frontend/src/components/canvas/WorkflowCanvas.tsx | head -20
```

- [ ] **Step 2: Refactor header to floating glass bar**

In `WorkflowCanvas.tsx`, locate the JSX block that renders the top toolbar. Replace its container className with a floating bar:

```tsx
<div className="absolute top-3 left-3 right-3 z-20 flex items-center gap-2 bg-surface-elevated backdrop-blur-xl border border-border rounded-xl shadow-elev-2 px-4 py-2.5">
  {/* left: back, workflow name (editable), dirty dot */}
  {/* spacer */}
  {/* right: Versions DropdownMenu, Save button, Run/Cancel button */}
</div>
```

Keep all existing handlers (save, run, etc.). Convert Versions button to use shadcn `DropdownMenu`. Convert Save button to `variant="outline"`. Convert Run button to `variant="default"` with `className="shadow-glow-primary"`.

When running, the Run button transforms to Cancel. Use Framer `<motion.div layout>` wrapper around the Run/Cancel button:

```tsx
<motion.div layout>
  {isRunning
    ? <Button variant="destructive" onClick={handleStop}>Cancel</Button>
    : <Button onClick={handleRun} className="shadow-glow-primary">Run</Button>}
</motion.div>
```

- [ ] **Step 3: Add canvas-bg pseudo-element**

In the canvas wrapper element (the div that contains `<ReactFlow>`), add className `relative canvas-bg`. Add a CSS rule in globals.css (already there if you followed Task 1.2's full template — verify the rule exists; if not, add):

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

If this rule was not added in Task 1.2, add it now under `@layer components`.

- [ ] **Step 4: Inset sidebar and inspector wrappers**

The Sidebar (left) and Inspector (right) panel wrappers should become floating glass cards with 12px insets from their edges. Find their wrapper divs in WorkflowCanvas.tsx and update:

Sidebar wrapper:
```tsx
<div className="absolute top-16 left-3 bottom-3 z-10 w-[280px] bg-surface backdrop-blur-md border border-border rounded-xl shadow-elev-1 overflow-hidden">
```

Inspector wrapper:
```tsx
<div className="absolute top-16 right-3 bottom-3 z-10 w-[360px] bg-surface backdrop-blur-md border border-border rounded-xl shadow-elev-1 overflow-hidden">
```

(`top-16` accommodates the floating header with margin.)

- [ ] **Step 5: Add floating Run FAB**

Below the canvas wrapper, conditionally render a FAB at bottom-right:

```tsx
{!selectedNodeId && nodes.length > 0 && (
  <motion.button
    layout
    onClick={handleRun}
    disabled={isRunning}
    className="absolute bottom-6 right-6 z-30 h-14 w-14 rounded-full bg-primary text-primary-foreground shadow-glow-primary flex items-center justify-center hover:scale-105 transition-transform duration-fast"
    aria-label="Run workflow"
  >
    <Play className="h-5 w-5" />
  </motion.button>
)}
```

The FAB animates in/out via `<AnimatePresence>` when selection changes — wrap in `<AnimatePresence>` and add `initial={{ scale: 0, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} exit={{ scale: 0, opacity: 0 }}`.

- [ ] **Step 6: Typecheck and dev-test**

```bash
cd frontend && npm run typecheck && npm run dev
```

Open any workflow's canvas. Verify floating header, glass sidebar + inspector with insets, ambient gradient over the dot grid, and the FAB at bottom-right.

- [ ] **Step 7: Commit**

```bash
cd /Users/himanshu/Git/aegis && git add frontend/src/components/canvas/WorkflowCanvas.tsx frontend/src/app/globals.css && git commit -m "feat(ui-overhaul): 3.1 — canvas chrome (floating header, glass panels, ambient bg, FAB)"
```

## Task 3.2: Define `NodeCategory` type and color map

**Files:**
- Create: `frontend/src/components/canvas/nodes/category.ts`

- [ ] **Step 1: Create category module**

```ts
// frontend/src/components/canvas/nodes/category.ts
export type NodeCategory =
  | "trigger" | "logic" | "llm" | "data" | "integration" | "quality" | "flow";

export const CATEGORY_LABEL: Record<NodeCategory, string> = {
  trigger: "Trigger",
  logic: "Logic",
  llm: "LLM",
  data: "Data",
  integration: "Integration",
  quality: "Quality",
  flow: "Flow control",
};

export const CATEGORY_COLOR_VAR: Record<NodeCategory, string> = {
  trigger: "var(--cat-trigger)",
  logic: "var(--cat-logic)",
  llm: "var(--cat-llm)",
  data: "var(--cat-data)",
  integration: "var(--cat-integration)",
  quality: "var(--cat-quality)",
  flow: "var(--cat-flow)",
};

/** Map a node-type string from the registry to a category. */
export function categorize(nodeType: string): NodeCategory {
  if (nodeType.startsWith("trigger") || nodeType === "trigger") return "trigger";
  if (["if", "switch", "router", "classifier_router"].includes(nodeType)) return "logic";
  if (["agent", "classifier"].includes(nodeType)) return "llm";
  if (["kb_retrieve", "memory_store", "memory_retrieve", "json_parse", "code"].includes(nodeType)) return "data";
  if (nodeType.startsWith("integration_") || nodeType === "http_request") return "integration";
  if (["evaluation", "guardrail"].includes(nodeType)) return "quality";
  if (["join", "delay", "sub_workflow", "human_approval", "end"].includes(nodeType)) return "flow";
  return "flow"; // default fallback
}
```

- [ ] **Step 2: Typecheck and commit**

```bash
cd frontend && npm run typecheck
cd /Users/himanshu/Git/aegis && git add frontend/src/components/canvas/nodes/category.ts && git commit -m "feat(ui-overhaul): 3.2 — add NodeCategory module"
```

## Task 3.3: Verify node-registry has needed fields

**Files:**
- Modify: `frontend/src/lib/node-registry.ts` (only if needed)

- [ ] **Step 1: Read node-registry**

```bash
cat frontend/src/lib/node-registry.ts | head -80
```

The `categorize()` function in 3.2 maps from node-type strings. As long as those strings are stable and exhaustive, no change is needed here.

- [ ] **Step 2: Add a category resolver export (optional convenience)**

If the registry already exports a `getNodeMeta(nodeType)` function, add a category field to its return shape (or wrap callers):

If unsure, **do nothing here** — `categorize(nodeType)` from category.ts can be called directly from BaseNode. Skip step 3.

- [ ] **Step 3: Commit (if changed)**

If you modified node-registry.ts:

```bash
cd /Users/himanshu/Git/aegis && git add frontend/src/lib/node-registry.ts && git commit -m "feat(ui-overhaul): 3.3 — expose category from node registry"
```

Otherwise skip the commit.

## Task 3.4: Rewrite `<BaseNode>`

**Files:**
- Modify: `frontend/src/components/canvas/nodes/BaseNode.tsx`

- [ ] **Step 1: Read existing BaseNode**

```bash
cat frontend/src/components/canvas/nodes/BaseNode.tsx
```

Note the props it receives from React Flow and any external state hooks (e.g. node-state from run stream).

- [ ] **Step 2: Rewrite BaseNode**

```tsx
// frontend/src/components/canvas/nodes/BaseNode.tsx
"use client";
import { ReactNode, useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Handle, Position, type NodeProps } from "@xyflow/react";
import { cn } from "@/lib/utils";
import { categorize, type NodeCategory } from "./category";
import { useGlowPulse } from "@/components/motion";

export type NodeRuntimeState =
  | "idle" | "selected" | "running" | "completed" | "failed" | "awaiting_approval";

type BaseNodeData = {
  label?: string;
  nodeType: string;
  description?: string;
  /** Optional override of derived category. */
  category?: NodeCategory;
  /** Runtime state from the run stream. */
  runtimeState?: NodeRuntimeState;
  /** Optional error message (failed state) */
  errorMessage?: string;
  /** Optional ms elapsed timer (running state) */
  startedAt?: number;
};

type Props = NodeProps<BaseNodeData> & {
  icon: ReactNode;
  /** Optional category-specific footer slot (e.g. model name for LLM nodes). */
  footer?: ReactNode;
};

const BORDER_BY_STATE: Record<NodeRuntimeState, string> = {
  idle: "border-border",
  selected: "border-primary/40",
  running: "border-warning/40",
  completed: "border-success",
  failed: "border-destructive/50",
  awaiting_approval: "border-warning border-dashed",
};

const SHADOW_BY_STATE: Record<NodeRuntimeState, string> = {
  idle: "shadow-elev-1",
  selected: "shadow-glow-primary",
  running: "shadow-glow-warning",
  completed: "shadow-glow-success",
  failed: "shadow-glow-destructive",
  awaiting_approval: "shadow-glow-warning",
};

export function BaseNode({ data, selected, icon, footer }: Props) {
  const cat: NodeCategory = data.category ?? categorize(data.nodeType);
  const runtimeState: NodeRuntimeState = selected ? "selected" : data.runtimeState ?? "idle";
  const pulse = useGlowPulse(runtimeState === "running" ? "warning" : "primary");
  const animate = runtimeState === "running" ? pulse : "";

  // Elapsed timer for running state
  const [elapsedSec, setElapsedSec] = useState(0);
  useEffect(() => {
    if (runtimeState !== "running" || !data.startedAt) return;
    const tick = () => setElapsedSec(Math.floor((Date.now() - data.startedAt!) / 1000));
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, [runtimeState, data.startedAt]);

  return (
    <motion.div
      layout="size"
      className={cn(
        "relative w-[240px] min-h-[88px] rounded-lg bg-surface backdrop-blur-md border overflow-hidden",
        BORDER_BY_STATE[runtimeState],
        SHADOW_BY_STATE[runtimeState],
        animate,
      )}
    >
      {/* Accent bar */}
      <span
        className="absolute left-0 top-0 right-0 h-0.5"
        style={{
          background: runtimeState === "selected"
            ? `linear-gradient(90deg, ${CSSVar("cat-" + cat)}, var(--accent-500))`
            : CSSVar("cat-" + cat),
        }}
        aria-hidden
      />

      <div className="p-3.5">
        <div className="flex items-center justify-between gap-2">
          <div
            className="flex h-6 w-6 items-center justify-center rounded-md"
            style={{ background: `color-mix(in srgb, ${CSSVar("cat-" + cat)} 12%, transparent)`, color: CSSVar("cat-" + cat) }}
          >
            {icon}
          </div>
          <span className="text-micro" style={{ color: CSSVar("cat-" + cat) }}>
            {data.nodeType}
          </span>
        </div>
        <div className="mt-2 text-body line-clamp-2">{data.label || "Untitled"}</div>
        {runtimeState === "running" && (
          <div className="mt-2 text-caption font-mono">{elapsedSec}s</div>
        )}
        {footer && <div className="mt-2">{footer}</div>}
      </div>

      {/* Error tooltip on failed */}
      <AnimatePresence>
        {runtimeState === "failed" && data.errorMessage && (
          <motion.div
            initial={{ opacity: 0, y: 4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 4 }}
            className="pointer-events-none absolute -bottom-2 left-2 right-2 translate-y-full rounded-md bg-surface-elevated backdrop-blur-md border border-destructive/40 p-2 text-caption shadow-elev-2"
          >
            {data.errorMessage}
          </motion.div>
        )}
      </AnimatePresence>

      <Handle type="target" position={Position.Left} className="!h-2.5 !w-2.5 !border-border !bg-surface-elevated" style={{ borderColor: CSSVar("cat-" + cat) }} />
      <Handle type="source" position={Position.Right} className="!h-2.5 !w-2.5 !border-border !bg-surface-elevated" style={{ borderColor: CSSVar("cat-" + cat) }} />
    </motion.div>
  );
}

/** Tiny helper to reference CSS variables in inline styles. */
function CSSVar(name: string): string {
  return `var(--${name})`;
}
```

- [ ] **Step 3: Typecheck and commit**

```bash
cd frontend && npm run typecheck
cd /Users/himanshu/Git/aegis && git add frontend/src/components/canvas/nodes/BaseNode.tsx && git commit -m "feat(ui-overhaul): 3.4 — rewrite BaseNode with state variants and animations"
```

## Task 3.5: Create category-specific node components

**Files:**
- Create: `frontend/src/components/canvas/nodes/TriggerNode.tsx`, `LogicNode.tsx`, `LLMNode.tsx`, `DataNode.tsx`, `IntegrationNode.tsx`, `QualityNode.tsx`, `FlowNode.tsx`

- [ ] **Step 1: Create TriggerNode**

```tsx
// frontend/src/components/canvas/nodes/TriggerNode.tsx
"use client";
import { type NodeProps } from "@xyflow/react";
import { Zap } from "lucide-react";
import { BaseNode } from "./BaseNode";

export function TriggerNode(props: NodeProps) {
  return <BaseNode {...props} icon={<Zap className="h-3.5 w-3.5" />} />;
}
```

- [ ] **Step 2: Create LogicNode, LLMNode, DataNode, IntegrationNode, QualityNode, FlowNode**

Use these icons (Lucide):
- LogicNode: `GitBranch`
- LLMNode: `Sparkles` (with footer showing model name if `data.config?.model` present)
- DataNode: `Database`
- IntegrationNode: `Plug` (or branch on data.nodeType for slack/discord/email icons later)
- QualityNode: `Shield`
- FlowNode: `Workflow`

Each file is ~12 lines (the TriggerNode template). For LLMNode, add a footer:

```tsx
// LLMNode footer example
const model = (props.data as any).config?.model;
const footer = model ? <span className="text-micro">{model}</span> : null;
return <BaseNode {...props} icon={<Sparkles className="h-3.5 w-3.5" />} footer={footer} />;
```

- [ ] **Step 3: Wire nodeTypes in WorkflowCanvas**

In `WorkflowCanvas.tsx`, find the `<ReactFlow>` element. Update its `nodeTypes` prop:

```tsx
import { TriggerNode } from "@/components/canvas/nodes/TriggerNode";
import { LogicNode } from "@/components/canvas/nodes/LogicNode";
import { LLMNode } from "@/components/canvas/nodes/LLMNode";
import { DataNode } from "@/components/canvas/nodes/DataNode";
import { IntegrationNode } from "@/components/canvas/nodes/IntegrationNode";
import { QualityNode } from "@/components/canvas/nodes/QualityNode";
import { FlowNode } from "@/components/canvas/nodes/FlowNode";

const nodeTypes = {
  trigger: TriggerNode,
  agent: LLMNode,
  classifier: LLMNode,
  if: LogicNode,
  switch: LogicNode,
  router: LogicNode,
  classifier_router: LogicNode,
  kb_retrieve: DataNode,
  memory_store: DataNode,
  memory_retrieve: DataNode,
  json_parse: DataNode,
  code: DataNode,
  integration_slack: IntegrationNode,
  integration_discord: IntegrationNode,
  integration_email: IntegrationNode,
  integration_postgres: IntegrationNode,
  http_request: IntegrationNode,
  evaluation: QualityNode,
  guardrail: QualityNode,
  join: FlowNode,
  delay: FlowNode,
  sub_workflow: FlowNode,
  human_approval: FlowNode,
  end: FlowNode,
};
```

Use `useMemo` to memoize this map (React Flow requires stable references).

- [ ] **Step 4: Typecheck and dev-test**

```bash
cd frontend && npm run typecheck && npm run dev
```

Open a workflow. Each node should now render with category-colored accent bar and icon background. Confirm at least 3 categories visually distinct.

- [ ] **Step 5: Commit**

```bash
cd /Users/himanshu/Git/aegis && git add frontend/src/components/canvas/nodes/ frontend/src/components/canvas/WorkflowCanvas.tsx && git commit -m "feat(ui-overhaul): 3.5 — add category-specific node components and wire nodeTypes"
```

## Task 3.6: Build `<GradientEdge>` component

**Files:**
- Create: `frontend/src/components/canvas/edges/GradientEdge.tsx`

- [ ] **Step 1: Create GradientEdge**

```tsx
// frontend/src/components/canvas/edges/GradientEdge.tsx
"use client";
import { useId } from "react";
import { BaseEdge, getBezierPath, type EdgeProps } from "@xyflow/react";
import { categorize, CATEGORY_COLOR_VAR } from "../nodes/category";

type EdgeData = {
  active?: boolean;          // edge is on the running path
  failed?: boolean;          // edge is on a failed path
  sourceNodeType?: string;   // for category color lookup
  targetNodeType?: string;
};

export function GradientEdge({
  id,
  sourceX, sourceY, targetX, targetY,
  sourcePosition, targetPosition,
  data,
  selected,
}: EdgeProps<EdgeData>) {
  const gradId = useId();
  const [path] = getBezierPath({ sourceX, sourceY, sourcePosition, targetX, targetY, targetPosition });

  const sCat = data?.sourceNodeType ? categorize(data.sourceNodeType) : "flow";
  const tCat = data?.targetNodeType ? categorize(data.targetNodeType) : "flow";
  const sColor = CATEGORY_COLOR_VAR[sCat];
  const tColor = CATEGORY_COLOR_VAR[tCat];

  const active = !!data?.active;
  const failed = !!data?.failed;

  return (
    <>
      <defs>
        <linearGradient id={gradId} gradientUnits="userSpaceOnUse" x1={sourceX} y1={sourceY} x2={targetX} y2={targetY}>
          <stop offset="0%" stopColor={sColor} />
          <stop offset="100%" stopColor={tColor} />
        </linearGradient>
      </defs>

      {selected && (
        <BaseEdge id={`${id}-bloom`} path={path} style={{ stroke: sColor, strokeWidth: 6, opacity: 0.18, filter: "blur(4px)" }} />
      )}

      <BaseEdge
        id={id}
        path={path}
        style={{
          stroke: failed ? "var(--canvas-edge-failed)" : `url(#${gradId})`,
          strokeWidth: 1.5,
          opacity: active ? 1 : 0.55,
          strokeLinecap: "round",
          fill: "none",
        }}
      />

      {active && !failed && (
        <BaseEdge
          id={`${id}-flow`}
          path={path}
          className="animate-edge-flow"
          style={{
            stroke: `url(#${gradId})`,
            strokeWidth: 1.5,
            strokeDasharray: "4 4",
            fill: "none",
          }}
        />
      )}
    </>
  );
}
```

- [ ] **Step 2: Wire in WorkflowCanvas**

In `WorkflowCanvas.tsx`:

```tsx
import { GradientEdge } from "@/components/canvas/edges/GradientEdge";

const edgeTypes = { default: GradientEdge };
```

Pass `edgeTypes={edgeTypes}` to `<ReactFlow>`. Memoize.

- [ ] **Step 3: Wire sourceNodeType/targetNodeType into edge data**

When edges are created/loaded in WorkflowCanvas, decorate each edge with `data: { sourceNodeType, targetNodeType }` by looking up the node types from the nodes array.

```tsx
const decoratedEdges = useMemo(() => edges.map(e => {
  const src = nodes.find(n => n.id === e.source);
  const tgt = nodes.find(n => n.id === e.target);
  return { ...e, data: { ...e.data, sourceNodeType: src?.type, targetNodeType: tgt?.type } };
}), [edges, nodes]);
```

Pass `decoratedEdges` to `<ReactFlow edges={...}>`.

- [ ] **Step 4: Typecheck and dev-test**

```bash
cd frontend && npm run typecheck && npm run dev
```

Open a workflow with connected nodes. Edges should now be gradient-colored, source-to-target.

- [ ] **Step 5: Commit**

```bash
cd /Users/himanshu/Git/aegis && git add frontend/src/components/canvas/edges/GradientEdge.tsx frontend/src/components/canvas/WorkflowCanvas.tsx && git commit -m "feat(ui-overhaul): 3.6 — add GradientEdge with category-colored gradients"
```

## Task 3.7: Activate edges during runs + connection preview

**Files:**
- Modify: `frontend/src/components/canvas/WorkflowCanvas.tsx`
- Create: `frontend/src/components/canvas/edges/ConnectionLine.tsx`

- [ ] **Step 1: Create ConnectionLine**

```tsx
// frontend/src/components/canvas/edges/ConnectionLine.tsx
"use client";
import { type ConnectionLineComponentProps } from "@xyflow/react";

export function ConnectionLine({ fromX, fromY, toX, toY }: ConnectionLineComponentProps) {
  const id = "conn-preview";
  return (
    <g>
      <defs>
        <linearGradient id={id} gradientUnits="userSpaceOnUse" x1={fromX} y1={fromY} x2={toX} y2={toY}>
          <stop offset="0%" stopColor="var(--primary-500)" />
          <stop offset="100%" stopColor="var(--accent-500)" />
        </linearGradient>
      </defs>
      <path
        d={`M ${fromX} ${fromY} C ${fromX + 50} ${fromY}, ${toX - 50} ${toY}, ${toX} ${toY}`}
        stroke={`url(#${id})`}
        strokeWidth={1.5}
        strokeLinecap="round"
        fill="none"
        style={{ filter: "drop-shadow(0 0 8px rgba(99,102,241,0.6))" }}
      />
    </g>
  );
}
```

- [ ] **Step 2: Wire ConnectionLine + edge activation**

In WorkflowCanvas.tsx, add to `<ReactFlow>`:

```tsx
<ReactFlow
  ...
  connectionLineComponent={ConnectionLine}
>
```

For edge activation during runs:

When the run stream emits `node_started` for a node, mark all edges where `e.target === nodeId` as `active`. When `node_completed`, mark all edges where `e.source === nodeId` AND target is the next running node as active. When run finishes (run_completed/failed/cancelled), reset all `active` flags.

Implementation: keep a `Set<string>` of active edge IDs in state. Compute from the run event stream. Decorate edges in `decoratedEdges` with `data.active = activeEdgeIds.has(e.id)`.

**Performance guardrail:** if `edges.length > 80`, skip the dashed `<BaseEdge>` overlay in GradientEdge by clamping `active` to false in the decoration step:

```tsx
const skipAnim = edges.length > 80;
const decoratedEdges = useMemo(() => edges.map(e => ({
  ...e,
  data: { ...e.data, sourceNodeType: ..., targetNodeType: ..., active: !skipAnim && activeEdgeIds.has(e.id), failed: failedEdgeIds.has(e.id) },
})), [edges, activeEdgeIds, failedEdgeIds, skipAnim]);
```

- [ ] **Step 3: Typecheck and dev-test**

```bash
cd frontend && npm run typecheck && npm run dev
```

Open a workflow. Drag from a node handle. The connection preview should show a gradient line with glow. Run the workflow — connected edges should flow.

- [ ] **Step 4: Commit**

```bash
cd /Users/himanshu/Git/aegis && git add frontend/src/components/canvas/edges/ConnectionLine.tsx frontend/src/components/canvas/WorkflowCanvas.tsx && git commit -m "feat(ui-overhaul): 3.7 — wire connection preview and edge run-activation"
```

## Task 3.8: Restyle Inspector identity header

**Files:**
- Modify: `frontend/src/components/canvas/NodeInspector.tsx`

- [ ] **Step 1: Read inspector**

```bash
head -120 frontend/src/components/canvas/NodeInspector.tsx
```

- [ ] **Step 2: Update the inspector top "identity" section**

Find where the inspector renders the selected node's type / label. Replace with:

```tsx
<div className="flex items-center gap-3 px-5 py-4 border-b border-border">
  <div
    className="flex h-9 w-9 items-center justify-center rounded-lg"
    style={{ background: `color-mix(in srgb, ${CATEGORY_COLOR_VAR[cat]} 12%, transparent)`, color: CATEGORY_COLOR_VAR[cat] }}
  >
    {/* category icon — pick a default based on cat, or pass through node-specific icon */}
    <CategoryIcon category={cat} />
  </div>
  <div className="flex flex-col">
    <span className="text-micro" style={{ color: CATEGORY_COLOR_VAR[cat] }}>{CATEGORY_LABEL[cat]}</span>
    {/* Editable name input — already inline-editable in existing inspector; just restyle */}
    <Input className="text-body-lg h-7 px-1 bg-transparent border-transparent focus-visible:border-border" value={...} onChange={...} />
  </div>
</div>
```

Add a tiny `CategoryIcon` helper at the top of the file:

```tsx
import { Zap, GitBranch, Sparkles, Database, Plug, Shield, Workflow } from "lucide-react";

const ICON_BY_CAT = {
  trigger: Zap, logic: GitBranch, llm: Sparkles,
  data: Database, integration: Plug, quality: Shield, flow: Workflow,
};

function CategoryIcon({ category }: { category: NodeCategory }) {
  const Icon = ICON_BY_CAT[category];
  return <Icon className="h-4 w-4" />;
}
```

- [ ] **Step 3: Typecheck and dev-test**

```bash
cd frontend && npm run typecheck && npm run dev
```

Open a workflow. Click a node. Inspector identity header shows category color + label.

- [ ] **Step 4: Commit**

```bash
cd /Users/himanshu/Git/aegis && git add frontend/src/components/canvas/NodeInspector.tsx && git commit -m "feat(ui-overhaul): 3.8 — restyle inspector identity header with category color"
```

## Task 3.9: Add Framer layout animation on inspector node-switch

**Files:**
- Modify: `frontend/src/components/canvas/NodeInspector.tsx`

- [ ] **Step 1: Wrap inspector body in motion + AnimatePresence**

Find the body content (the scrollable area below the identity header). Wrap with:

```tsx
<AnimatePresence mode="wait">
  <motion.div
    key={selectedNodeId ?? "empty"}
    initial={{ opacity: 0, y: 4 }}
    animate={{ opacity: 1, y: 0 }}
    exit={{ opacity: 0, y: -4 }}
    transition={{ duration: 0.2, ease: [0.16, 1, 0.3, 1] }}
  >
    {/* existing body */}
  </motion.div>
</AnimatePresence>
```

Also apply `<motion.div layout>` to the outermost wrapper of each collapsible section so height changes ease on expand/collapse.

- [ ] **Step 2: Restyle danger zone**

At the bottom of the inspector, find the Delete button. Wrap with:

```tsx
<div className="border-t border-border pt-4 mt-6 px-5 pb-5">
  <div className="text-micro mb-2">Danger zone</div>
  <Button variant="ghost" className="text-muted hover:text-destructive hover:bg-destructive/10" onClick={handleDelete}>
    Delete node
  </Button>
</div>
```

- [ ] **Step 3: Replace empty state**

When `!selectedNodeId`, render:

```tsx
<div className="flex flex-col items-center justify-center p-8 text-center gap-4">
  <h3 className="text-heading">No selection</h3>
  <p className="text-caption max-w-[260px]">
    Click a node on the canvas to configure it, or drag a new node from the sidebar.
  </p>
  <div className="grid grid-cols-2 gap-2 text-caption mt-4">
    <kbd className="rounded border border-border px-2 py-0.5 font-mono text-[11px]">⌘K</kbd>
    <span className="text-left">Search nodes</span>
    <kbd className="rounded border border-border px-2 py-0.5 font-mono text-[11px]">⌘S</kbd>
    <span className="text-left">Save workflow</span>
    <kbd className="rounded border border-border px-2 py-0.5 font-mono text-[11px]">⌘/</kbd>
    <span className="text-left">Keyboard shortcuts</span>
  </div>
</div>
```

- [ ] **Step 4: Typecheck and dev-test**

```bash
cd frontend && npm run typecheck && npm run dev
```

Click between nodes — inspector should crossfade. Click empty area — empty state should appear.

- [ ] **Step 5: Commit**

```bash
cd /Users/himanshu/Git/aegis && git add frontend/src/components/canvas/NodeInspector.tsx && git commit -m "feat(ui-overhaul): 3.9 — animate inspector node-switch, restyle empty + danger zone"
```

## Task 3.10: Restyle NodePalette + CanvasSidebar

**Files:**
- Modify: `frontend/src/components/canvas/NodePalette.tsx`
- Modify: `frontend/src/components/canvas/CanvasSidebar.tsx`

- [ ] **Step 1: Add category filter pills**

In NodePalette.tsx, at the top, render filter pills (a horizontal scrollable row of badges, one per category):

```tsx
import { CATEGORY_LABEL, type NodeCategory } from "./nodes/category";

const ALL_CATS: NodeCategory[] = ["trigger", "logic", "llm", "data", "integration", "quality", "flow"];

// state for active filter
const [activeCat, setActiveCat] = useState<NodeCategory | "all">("all");

// pill row
<div className="flex gap-2 overflow-x-auto px-4 py-3 border-b border-border scrollbar-thin">
  <button onClick={() => setActiveCat("all")} className={cn(pillClasses, activeCat === "all" && pillActive)}>
    All
  </button>
  {ALL_CATS.map(c => (
    <button key={c} onClick={() => setActiveCat(c)} className={cn(pillClasses, activeCat === c && pillActiveCat(c))}>
      {CATEGORY_LABEL[c]}
    </button>
  ))}
</div>

// Filter the node list by activeCat
const filteredNodes = activeCat === "all" ? allNodes : allNodes.filter(n => categorize(n.nodeType) === activeCat);
```

Define `pillClasses`, `pillActive`, and `pillActiveCat`:

```tsx
const pillClasses = "shrink-0 rounded-full border border-border bg-surface px-3 py-1 text-xs text-muted hover:bg-surface-hover transition-colors";
const pillActive = "border-border-strong text-foreground bg-surface-hover";
function pillActiveCat(cat: NodeCategory) {
  return `border-current text-foreground`;
  // inline style: { background: `color-mix(in srgb, ${CATEGORY_COLOR_VAR[cat]} 14%, transparent)`, color: CATEGORY_COLOR_VAR[cat] }
}
```

Apply the inline style for the active-cat pill in the JSX.

- [ ] **Step 2: Restyle node list items**

Each item in the palette gets:
- Category-colored icon background (same pattern as in BaseNode).
- Hover state: `bg-surface-hover`.
- Use `<StaggerList>` wrapping the filtered list when activeCat changes (re-mount via key).

- [ ] **Step 3: Add search input at top of palette**

Already present? If so, restyle to shadcn `Input` with prefix `Search` icon (`<div class="relative"><Search class="absolute left-3 ..."/><Input class="pl-9" .../></div>`).

- [ ] **Step 4: CanvasSidebar: Tab persistence**

In `CanvasSidebar.tsx`, ensure tabs (Nodes / Data) stay mounted via `hidden` class (P2.2 was already shipped — verify; if not, fix here).

- [ ] **Step 5: Typecheck and dev-test**

```bash
cd frontend && npm run typecheck && npm run dev
```

Open a workflow. The sidebar palette shows pills at top, filter by clicking. Drag a node — it appears on canvas with full new styling.

- [ ] **Step 6: Commit**

```bash
cd /Users/himanshu/Git/aegis && git add frontend/src/components/canvas/NodePalette.tsx frontend/src/components/canvas/CanvasSidebar.tsx && git commit -m "feat(ui-overhaul): 3.10 — restyle NodePalette with category pills and CanvasSidebar"
```

## Task 3.11: Phase 3 exit verification

**Files:** none.

- [ ] **Step 1: Lint and typecheck**

```bash
cd frontend && npm run typecheck && npm run lint
```

Expected: PASS.

- [ ] **Step 2: Open a workflow with ≥ 5 nodes and run it**

Verify all of:
- Floating header, glass panels with insets, ambient bg.
- Each node shows category-colored accent + icon background.
- Click a node → glow ring + inspector crossfade.
- Run workflow → active node glow-pulses (warning color), edges show gradient + flowing dashes.
- Completed nodes briefly flash green via the BaseNode state transition.
- Failed node (force a failure if possible) shows destructive ring + error tooltip.

- [ ] **Step 3: Test with a large workflow (>80 edges) if available, OR fabricate via duplicating nodes**

Verify: dashed-flow animation is suppressed (gradient stroke only). No frame drops.

- [ ] **Step 4: Reduced motion**

DevTools → reduced motion. Re-open canvas. Glow-pulse stops. Edge-flow stops. Inspector crossfade snaps. Hover lift still works.

- [ ] **Step 5: Mobile fallback**

Resize to 375px. P2.14 "canvas requires larger screen" message should still appear.

- [ ] **Step 6: Phase 3 marker commit**

```bash
cd /Users/himanshu/Git/aegis && git commit --allow-empty -m "milestone(ui-overhaul): phase 3 — canvas re-skin complete"
```

---

# Phase 4 — Extend outward

Goal: every remaining page reaches the bar set by dashboard + canvas.

## Task 4.1: /runs/[id] (run detail) restyle

**Files:**
- Modify: `frontend/src/app/runs/[id]/page.tsx`
- Modify: `frontend/src/components/runs/RunDetailView.tsx`

- [ ] **Step 1: Restyle header**

In `RunDetailView.tsx`, the page header section: replace with:

```tsx
<div className="mb-6 flex items-start justify-between">
  <div>
    <h1 className="text-title">{workflow_name}</h1>
    <div className="mt-1 flex items-center gap-3 text-caption">
      <Badge variant={statusBadgeVariant(run.status)}>{statusLabel(run.status)}</Badge>
      <span>{formatRelativeTime(run.created_at)}</span>
      <span>•</span>
      <span>{durationLabel(run)}</span>
    </div>
  </div>
  <div className="flex gap-2">
    {/* Re-run button if available, Export, etc. */}
  </div>
</div>
```

If `run.status === "running"`, wrap the Badge in a span with `useGlowPulse()` className.

- [ ] **Step 2: Two-column layout**

Below header:

```tsx
<div className="grid grid-cols-1 lg:grid-cols-[1fr_360px] gap-6">
  <div className="space-y-4">
    {/* Timeline of node executions */}
    {nodeResults.map(nr => <NodeResultCard key={nr.node_id} nodeResult={nr} />)}
  </div>
  <aside className="lg:sticky lg:top-6 space-y-4">
    {/* Eval scores chart, guardrail panel, final output */}
    {evalScores && <EvalScoresChart scores={evalScores} />}
    {guardrailEvents.length > 0 && <GuardrailEventsPanel events={guardrailEvents} />}
    {run.final_output && (
      run.eval_passed
        ? <GlowCard variant="primary" className="p-4"><h3 className="text-heading mb-2">Final output</h3><pre className="text-body whitespace-pre-wrap font-mono">{run.final_output}</pre></GlowCard>
        : <GlassCard className="p-4"><h3 className="text-heading mb-2">Final output</h3><pre className="text-body whitespace-pre-wrap font-mono">{run.final_output}</pre></GlassCard>
    )}
  </aside>
</div>
```

NodeResultCard: render each node result as a `<GlassCard>` with a left rail showing the timeline dot (category-colored), expandable to show output. Use the existing component or restyle in place.

- [ ] **Step 3: Approval prompt**

If `run.status === "awaiting_approval"`, render at the very top (above the header):

```tsx
<GlowCard variant="warning" className="mb-6 p-4">
  <h2 className="text-heading mb-2">Approval required</h2>
  <p className="text-caption mb-3">{approvalContext}</p>
  <div className="flex gap-2">
    <Button variant="default" onClick={handleApprove}>Approve</Button>
    <Button variant="outline" onClick={handleReject}>Reject</Button>
  </div>
</GlowCard>
```

- [ ] **Step 4: Typecheck and dev-test**

```bash
cd frontend && npm run typecheck && npm run dev
```

Navigate to a run. Verify layout and visuals.

- [ ] **Step 5: Commit**

```bash
cd /Users/himanshu/Git/aegis && git add frontend/src/app/runs/[id]/page.tsx frontend/src/components/runs/RunDetailView.tsx && git commit -m "feat(ui-overhaul): 4.1 — restyle run detail with two-column timeline and quality panel"
```

## Task 4.2: /observability restyle

**Files:**
- Modify: `frontend/src/app/observability/page.tsx`

- [ ] **Step 1: Restyle hero strip**

Use the same 4-card stat strip pattern from the dashboard. Below it, render a horizontal strip of small sparklines:

```tsx
<div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
  <StatCard ... />
  ...
</div>
<GlassCard className="mt-4 p-4">
  <div className="text-micro mb-2">14-DAY TRENDS</div>
  <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
    <div><div className="text-caption mb-1">Runs/day</div><Sparkline data={runsTrend} /></div>
    <div><div className="text-caption mb-1">Pass rate</div><Sparkline data={passTrend} color="var(--success)" /></div>
    <div><div className="text-caption mb-1">Latency p50</div><Sparkline data={p50Trend} /></div>
    <div><div className="text-caption mb-1">Latency p95</div><Sparkline data={p95Trend} color="var(--warning)" /></div>
  </div>
</GlassCard>
```

If trend data is unavailable, fall back to an info copy. Same rule as Task 2.8.

- [ ] **Step 2: Runs list at bottom**

Reuse `<RecentRunRow>` from dashboard. Existing filtering UI: restyle filter chips/buttons. Add the "showing N of M" caption above the list (P2.8 already shipped — verify).

- [ ] **Step 3: Empty state**

If no data: `<EmptyState variant="info" title="No telemetry yet" description="Run a workflow to see runs and quality metrics here." />`.

- [ ] **Step 4: Typecheck and dev-test, commit**

```bash
cd frontend && npm run typecheck
cd /Users/himanshu/Git/aegis && git add frontend/src/app/observability/page.tsx && git commit -m "feat(ui-overhaul): 4.2 — restyle observability with stat strip + sparkline trends"
```

## Task 4.3: /settings restyle with shadcn Tabs

**Files:**
- Modify: `frontend/src/app/settings/page.tsx`

- [ ] **Step 1: Replace existing tab UI with shadcn Tabs**

```tsx
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";

<Tabs defaultValue="general" className="mt-6">
  <TabsList>
    <TabsTrigger value="general">General</TabsTrigger>
    <TabsTrigger value="credentials">Credentials</TabsTrigger>
    <TabsTrigger value="presets">Eval presets</TabsTrigger>
    <TabsTrigger value="integrations">Integrations</TabsTrigger>
    <TabsTrigger value="api-keys">API keys</TabsTrigger>
  </TabsList>
  <TabsContent value="general"><GlassCard className="p-5">...</GlassCard></TabsContent>
  ...
</Tabs>
```

- [ ] **Step 2: Replace toggles with shadcn Switch**

Find any `<input type="checkbox">` or custom toggle. Replace with `<Switch checked={...} onCheckedChange={...} />`.

- [ ] **Step 3: Add Sheet for credential edit (optional)**

Replace the inline edit form with a `<Sheet>` opening from the right when a credential is clicked. Keep the existing form fields. The credential list is in its own card; clicking a row opens the Sheet.

- [ ] **Step 4: Typecheck and dev-test, commit**

```bash
cd frontend && npm run typecheck
cd /Users/himanshu/Git/aegis && git add frontend/src/app/settings/page.tsx && git commit -m "feat(ui-overhaul): 4.3 — restyle settings with shadcn Tabs + Switch + Sheet"
```

## Task 4.4: /templates restyle

**Files:**
- Modify: `frontend/src/app/templates/page.tsx`

- [ ] **Step 1: Restyle template cards**

Each template card: `<GlassCard>` wrapped with `<HoverLift>`. Image area uses a deterministic gradient from a small palette (hash the template name to pick from 6 gradients).

```tsx
const GRADIENTS = [
  "from-primary-500 to-accent-500",
  "from-cat-llm to-cat-data",
  "from-cat-integration to-cat-quality",
  "from-cat-trigger to-cat-logic",
  "from-success to-cat-llm",
  "from-cat-data to-primary-500",
];

function gradientForName(name: string): string {
  let h = 0;
  for (const c of name) h = (h * 31 + c.charCodeAt(0)) >>> 0;
  return GRADIENTS[h % GRADIENTS.length];
}

// In the card:
<div className={`h-32 bg-gradient-to-br ${gradientForName(template.name)} relative`}>
  {/* Optional: render the template's first node-category icon at low opacity */}
</div>
<div className="p-4">
  <h3 className="text-body-lg font-semibold">{template.name}</h3>
  <p className="text-caption mt-1 line-clamp-2">{template.description}</p>
  <div className="mt-3 flex items-center gap-3 text-caption">
    <span>{pluralize(template.node_count, "node")}</span>
  </div>
  <Button variant="outline" className="mt-3 w-full" onClick={handleUse}>Use template</Button>
</div>
```

- [ ] **Step 2: Loading skeleton matches structure**

The existing skeleton (P2.7) should already show card-shaped skeletons; verify after restyle, adjust if heights don't match.

- [ ] **Step 3: Typecheck, dev-test, commit**

```bash
cd frontend && npm run typecheck
cd /Users/himanshu/Git/aegis && git add frontend/src/app/templates/page.tsx && git commit -m "feat(ui-overhaul): 4.4 — restyle templates with gradient cards"
```

## Task 4.5: /guardrails restyle

**Files:**
- Modify: `frontend/src/app/guardrails/page.tsx`
- Modify: `frontend/src/components/guardrails/GuardrailPlayground.tsx`

- [ ] **Step 1: Restyle GuardrailPlayground**

Split into a two-column layout inside one `<GlassCard>`:

```tsx
<GlassCard className="p-6">
  <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
    <div>
      <h3 className="text-heading mb-3">Configure</h3>
      {/* existing config form: Select for type, Textarea for rules, etc. — restyled */}
    </div>
    <div>
      <h3 className="text-heading mb-3">Result</h3>
      {/* Result panel with Badge for pass/fail + glow, redacted output mono, latency */}
    </div>
  </div>
</GlassCard>
```

Preset example chips strip above the playground:

```tsx
<div className="mb-4 flex flex-wrap gap-2">
  {presets.map(p => (
    <Button key={p.id} variant="outline" size="sm" onClick={() => loadPreset(p)}>
      {p.name}
    </Button>
  ))}
</div>
```

"How to use" expandable section (P3.7 already shipped) — verify still present, restyle if needed with new tokens.

- [ ] **Step 2: Typecheck, dev-test, commit**

```bash
cd frontend && npm run typecheck
cd /Users/himanshu/Git/aegis && git add frontend/src/app/guardrails/page.tsx frontend/src/components/guardrails/GuardrailPlayground.tsx && git commit -m "feat(ui-overhaul): 4.5 — restyle guardrails playground"
```

## Task 4.6: /workflows list restyle

**Files:**
- Modify: `frontend/src/app/workflows/page.tsx`

- [ ] **Step 1: Use WorkflowCard from dashboard**

Replace the existing list rendering with a grid of `<WorkflowCard>` (the one created in Task 2.6). 3 columns on desktop, 2 on tablet, 1 on mobile.

```tsx
<div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mt-6">
  {filteredWorkflows.map(w => <WorkflowCard key={w.id} workflow={w} />)}
</div>
```

Keep the existing search/filter/sort controls — restyle inputs with shadcn primitives.

- [ ] **Step 2: Typecheck, dev-test, commit**

```bash
cd frontend && npm run typecheck
cd /Users/himanshu/Git/aegis && git add frontend/src/app/workflows/page.tsx && git commit -m "feat(ui-overhaul): 4.6 — restyle /workflows list with WorkflowCard grid"
```

## Task 4.7: Layout chrome — AppNav and MobileNav

**Files:**
- Modify: `frontend/src/components/layout/AppNav.tsx`
- Modify: `frontend/src/components/layout/MobileNav.tsx`

- [ ] **Step 1: Restyle AppNav as floating glass bar**

In AppNav.tsx, wrapping container:

```tsx
<nav className="sticky top-3 mx-3 mt-3 z-30 flex items-center gap-2 bg-surface-elevated backdrop-blur-xl border border-border rounded-xl shadow-elev-2 px-4 py-2.5">
  {/* logo, nav links, command palette trigger, user menu */}
</nav>
```

- [ ] **Step 2: Active route indicator slides between items**

Use Framer `<motion.div layout>` keyed by pathname for an underline that slides between active nav items. Implementation:

Each NavLink renders relative; the active one renders a child motion div with `layoutId="nav-active"` so Framer animates it between items:

```tsx
{isActive && (
  <motion.span
    layoutId="nav-active"
    className="absolute -bottom-0.5 left-0 right-0 h-0.5 rounded bg-gradient-to-r from-primary-500 to-accent-500"
  />
)}
```

- [ ] **Step 3: MobileNav as bottom-sheet via shadcn Sheet**

```tsx
import { Sheet, SheetContent, SheetTrigger } from "@/components/ui/sheet";

<Sheet>
  <SheetTrigger asChild>
    <Button variant="ghost" size="icon-lg" className="md:hidden">
      <Menu />
    </Button>
  </SheetTrigger>
  <SheetContent side="bottom" className="rounded-t-2xl">
    {/* Nav items */}
  </SheetContent>
</Sheet>
```

- [ ] **Step 4: Typecheck, dev-test, commit**

```bash
cd frontend && npm run typecheck
cd /Users/himanshu/Git/aegis && git add frontend/src/components/layout/AppNav.tsx frontend/src/components/layout/MobileNav.tsx && git commit -m "feat(ui-overhaul): 4.7 — restyle AppNav as floating glass bar + Mobile Sheet"
```

## Task 4.8: Sweep `.interactive-card` and dead classes

**Files:** any file referencing legacy classes.

- [ ] **Step 1: Find usages**

```bash
cd frontend && grep -rn "interactive-card" src/
```

- [ ] **Step 2: Replace with `<GlassCard>` + `<HoverLift>`**

For each match, wrap the element in `<HoverLift><GlassCard>...</GlassCard></HoverLift>` and remove the class. Use `<Link>` wrapping when the card is navigational.

- [ ] **Step 3: Remove `.interactive-card` definition from globals.css**

Delete the `.interactive-card` rule from `globals.css` (lines 85-93 in the Phase 1 template).

- [ ] **Step 4: Typecheck, lint, commit**

```bash
cd frontend && npm run typecheck && npm run lint
cd /Users/himanshu/Git/aegis && git add -A frontend && git commit -m "feat(ui-overhaul): 4.8 — remove legacy .interactive-card class"
```

## Task 4.9: Phase 4 exit verification

**Files:** none.

- [ ] **Step 1: Lint and typecheck**

```bash
cd frontend && npm run typecheck && npm run lint
```

- [ ] **Step 2: Click through every route**

Visit `/`, `/workflows`, `/workflows/new`, `/workflows/[id]/edit`, `/runs`, `/runs/[id]`, `/observability`, `/templates`, `/settings`, `/guardrails`. Each should match the new visual language. No page looks "before."

- [ ] **Step 3: Run a workflow end-to-end**

Trigger from `/workflows`. Verify: dashboard live update (recent runs prepends a row) → canvas execution viz (nodes glow, edges flow) → run detail (timeline + quality panel renders, status badge updates if SSE wired).

- [ ] **Step 4: Phase 4 marker commit**

```bash
cd /Users/himanshu/Git/aegis && git commit --allow-empty -m "milestone(ui-overhaul): phase 4 — extend outward complete"
```

---

# Phase 5 — Polish & microinteractions

Goal: the difference between good and premium.

## Task 5.1: Sonner toast restyle

**Files:**
- Modify: `frontend/src/components/ui/toaster.tsx`

- [ ] **Step 1: Configure Sonner toast variants**

```tsx
import { Toaster as Sonner, type ToasterProps } from "sonner";

export function Toaster(props: ToasterProps) {
  return (
    <Sonner
      theme="dark"
      toastOptions={{
        classNames: {
          toast: "group bg-surface-elevated backdrop-blur-xl border border-border rounded-xl shadow-elev-2 p-4",
          title: "text-body font-medium",
          description: "text-caption",
          success: "border-l-2 border-l-success shadow-glow-success",
          error: "border-l-2 border-l-destructive shadow-glow-destructive",
          info: "",
          loading: "",
        },
        duration: 3500,
      }}
      {...props}
    />
  );
}
```

Verify `<Toaster />` is rendered once at the root layout.

- [ ] **Step 2: Trigger a toast in dev to verify**

E.g. delete a credential. Confirm success toast appears with success-glow border.

- [ ] **Step 3: Commit**

```bash
cd /Users/himanshu/Git/aegis && git add frontend/src/components/ui/toaster.tsx && git commit -m "feat(ui-overhaul): 5.1 — restyle Sonner toasts with status-glow"
```

## Task 5.2: Focus ring animation

**Files:**
- Modify: `frontend/src/app/globals.css`

- [ ] **Step 1: Add base focus-visible rule**

In `@layer base` block in globals.css, add:

```css
:focus-visible {
  outline: none;
  transition: box-shadow 160ms var(--ease-out);
}
```

The class-level focus-visible boxes (existing in `@layer components`) handle their own variations. The above is a sane default for plain elements.

- [ ] **Step 2: Verify nothing regressed**

```bash
cd frontend && npm run dev
```

Tab through `/` and `/settings`. Each focus event should show the ring animate in.

- [ ] **Step 3: Commit**

```bash
cd /Users/himanshu/Git/aegis && git add frontend/src/app/globals.css && git commit -m "feat(ui-overhaul): 5.2 — animate focus-visible transitions"
```

## Task 5.3: Hover affordance audit

**Files:** various.

- [ ] **Step 1: Click through every page**

For every visually-clickable thing that doesn't show a hover state, add one. For every non-clickable thing that shows pointer cursor, remove it.

Common spots to check:
- StatCard (decorative only — should NOT show pointer)
- Run status badges (not clickable — no pointer)
- All `<Link>` wrappers ARE clickable — verify hover state.

- [ ] **Step 2: Commit any fixes**

```bash
cd /Users/himanshu/Git/aegis && git add -A frontend && git commit -m "feat(ui-overhaul): 5.3 — hover affordance audit"
```

(If no changes needed, skip the commit.)

## Task 5.4: Screen reader audit

**Files:** various, only if regressions found.

- [ ] **Step 1: VoiceOver walk-through**

With VoiceOver (Cmd+F5 on Mac) enabled, walk through each route:
- Dashboard: live updates announce.
- Canvas: node state changes announce (P0.8 aria-live region — already there).
- Run detail: status changes announce.
- Dialog focus traps: tab through; shadcn Dialog handles this.
- Form errors: announce on submit.

- [ ] **Step 2: Fix any regressions**

If anything broke during the restyle, fix and commit.

```bash
cd /Users/himanshu/Git/aegis && git add -A frontend && git commit -m "feat(ui-overhaul): 5.4 — screen reader fixes"
```

(If no changes needed, skip the commit.)

## Task 5.5: Reduced motion final pass

**Files:** various.

- [ ] **Step 1: Toggle prefers-reduced-motion in OS settings**

(Mac: System Settings → Accessibility → Display → Reduce motion.)

- [ ] **Step 2: Reload each route**

Verify:
- Page enters: no slide-up.
- Stagger lists: instant render.
- Sparkline: no draw animation.
- Canvas active node: no glow pulse (static glow only).
- Canvas edges during run: no flow animation.
- Inspector switching: snap, not crossfade.
- Hover lift: still works (<120ms).
- Button press scale: still works.

If anything is animating that shouldn't be, find the component and gate it with `useReducedMotionStrict()`.

- [ ] **Step 3: Commit fixes if any**

```bash
cd /Users/himanshu/Git/aegis && git add -A frontend && git commit -m "feat(ui-overhaul): 5.5 — reduced motion final pass"
```

## Task 5.6: Mobile final pass

**Files:** various.

- [ ] **Step 1: At 375px on every route**

DevTools → toggle device. Verify:
- Dashboard: stats 2x2, columns single column, Recent Runs on top.
- Canvas: P2.14 fallback shows.
- Run detail: stacked layout.
- Settings: tabs scrollable or stacked.
- Modals: full-width with margins.
- Mobile nav: bottom sheet via Sheet from Task 4.7.

- [ ] **Step 2: Fix anything broken**

Common: a grid that doesn't collapse, a too-wide flex row, an absolutely-positioned element.

- [ ] **Step 3: Commit**

```bash
cd /Users/himanshu/Git/aegis && git add -A frontend && git commit -m "feat(ui-overhaul): 5.6 — mobile final pass"
```

## Task 5.7: Bundle size audit

**Files:** none.

- [ ] **Step 1: Run build**

```bash
cd frontend && npm run build
```

Note the JS bundle size from the output.

- [ ] **Step 2: Compare to start-of-overhaul baseline**

If you didn't capture the baseline at start, just check that no single chunk is unexpectedly large (>500KB gzipped). Framer Motion should be tree-shaken — if it shows as a giant chunk, audit imports for `import * as Motion from "framer-motion"` patterns and switch to named imports.

- [ ] **Step 3: Use analyzer if needed**

```bash
cd frontend && npm run analyze
```

Look at the report. Address any obvious bloat.

- [ ] **Step 4: Commit if any tree-shaking fixes applied**

```bash
cd /Users/himanshu/Git/aegis && git add -A frontend && git commit -m "feat(ui-overhaul): 5.7 — bundle size audit and tree-shaking fixes"
```

(Skip if no changes.)

## Task 5.8: Screenshot session

**Files:** none — this is a manual verification step.

- [ ] **Step 1: Start dev server, capture each scene**

```bash
cd frontend && npm run dev
```

Take screenshots of:
- `/` with data
- `/` empty state (clear all data or use a fresh browser profile)
- `/workflows/[id]/edit` mid-edit
- `/workflows/[id]/edit` running with active edges + glowing node
- `/runs/[id]` passed with evals
- `/runs/[id]` awaiting approval
- `/observability`
- `/settings` credentials tab
- Command palette open

- [ ] **Step 2: Look at each — does anything still feel "before"?**

Make a list. Fix any obvious issues (typically 1-2 small adjustments).

- [ ] **Step 3: Commit fixes**

```bash
cd /Users/himanshu/Git/aegis && git add -A frontend && git commit -m "feat(ui-overhaul): 5.8 — screenshot pass fixes"
```

## Task 5.9: Phase 5 exit verification

**Files:** none.

- [ ] **Step 1: Lint and typecheck clean**

```bash
cd frontend && npm run typecheck && npm run lint
```

- [ ] **Step 2: Record a 60-second screen capture**

Open the dev server. Record yourself going from `/` → click a workflow → run it → watch dashboard update → view run detail. Watch the recording back. Does it look intentional throughout?

- [ ] **Step 3: Phase 5 marker commit**

```bash
cd /Users/himanshu/Git/aegis && git commit --allow-empty -m "milestone(ui-overhaul): phase 5 — polish complete"
```

- [ ] **Step 4: Final report**

Compose a message (do NOT write a file) summarizing:
- Commits shipped, grouped by phase.
- Anything deferred and why.
- Anything that was already done.
- Visual issues noticed but not fixed.
- Bundle size delta.
- One sentence: "If I had one more day, I'd polish X."

---

# Reference — Glass token cheatsheet

When restyling, use these patterns:

**Cards / panels:**
```
className="bg-surface backdrop-blur-md border border-border rounded-xl shadow-elev-1"
```

**Important "hero" surfaces (max 1 per page):**
```
className="bg-surface backdrop-blur-md border border-border-glow rounded-xl shadow-glow-primary"
```

**Modals / popovers:**
```
className="bg-surface-elevated backdrop-blur-xl border border-border rounded-xl shadow-elev-3"
```

**Inputs:**
```
className="bg-surface-input border border-border rounded-md px-3 h-10 focus-visible:border-border-strong"
```

**Status badges:**
```
className="bg-{status}/12 text-{status} border-{status}/20"  // success, warning, destructive
```

**Animated focus (default):** handled by base layer (`:focus-visible { transition }`) plus component-level box-shadow rules.

---
