# Aegis Frontend UI/UX Audit — 2026-07-11

Empirical audit: every page driven in Chrome (desktop 1440px + mobile 390px),
axe-core 4.10 scans, 10-stop keyboard probes per page, API-down / overflow /
empty-state testing. Supersedes the previous static audit — most of its majors
were resolved by the redesign; its NodeInspector label finding was confirmed
live and is now fixed.

## Fixed in this audit pass

| Sev | Finding | Fix |
|---|---|---|
| critical (axe) | Settings: 2 unnamed buttons (alert metric/operator SelectTriggers) | `aria-label` on both |
| critical (axe) | Canvas: close button inside `role="tablist"` violates aria-required-children | X moved outside the tablist |
| serious (axe) | `--fg-subtle` (#6f6c62) ≈3.5:1 contrast on elevated surfaces (canvas "Input" label etc.) | token raised to #8b8779 (≥4.5:1) |
| major (a11y) | **41 `<Label>`s in NodeInspector without `htmlFor`** — screen readers couldn't associate inspector fields | all 41 associated with generated control ids |
| moderate (axe) | Landmark violation on every page: CommandDialog rendered its sr-only header outside `<main>`/dialog | header moved inside DialogContent |
| moderate (axe) | Templates: heading order jumped h1→h3 | card titles → h2 |
| minor (a11y) | Missing visible focus ring: failure-cluster links, guardrail preset buttons, run feedback thumbs, canvas back links, panel close X | `.focus-ring` applied |
| minor (UX) | API-down: home/canvas sat in loading skeletons ~15s (React Query 3-retry default) before the error state | `retry: 1` on list + canvas queries |
| minor (copy) | Stale post-IA labels: "Dashboard"/"Back to dashboard" in 9 places (dashboard no longer exists) | renamed to Workflows |

Post-fix axe status: home / settings / templates / canvas (inspector open) —
**0 violations** (Next.js dev-overlay portal excluded).

## Verified healthy (no action needed)

- **States**: API-down shows retryable `ApiConnectionState` everywhere (canvas has
  distinct not-found / auth / network branches); 404 page correct; empty canvas
  shows "Add first step"; empty datasets/experiments/alerts carry guidance copy.
- **Overflow**: 170-char workflow names truncate with ellipsis in home rows and
  the canvas toolbar; long inputs clamp in run rows; unbounded lists were capped
  in the density pass (scheduled workflows, preset library, leaderboard).
- **Mobile (390px)**: nav collapses to a sheet, stat grids stack, run-row meta
  columns hide, canvas shows its intentional larger-screen guard. No horizontal
  scroll on any audited page.
- **Keyboard**: logical tab order on all pages; skip-link present; quick-add menu
  supports ↑/↓/Enter/Esc (Esc closes cleanly); ⌘S/⌘D/Del/⌘K shortcuts work;
  destructive actions gated by confirm dialogs.
- **Consistency**: single type scale (Plex Sans/Mono), category color reserved
  for data semantics, status pills uniform (dot + mono), icon buttons all named,
  RunComparison/Settings/Guardrail form labels already associated.

## Backlog cleared — 2026-07-11 (second pass)

All five remaining items were fixed, adversarially reviewed by four independent
verification agents, and behaviorally proven in Chrome (8/8 probes + 3 mobile
mutation-path probes):

- [x] **Mobile canvas (<768px)** now renders in a layout-locked mode instead of a
  dead-end: pan/zoom/select/config-edit and Run work; every structural mutation
  path is gated (drag, connect, palette add, quick-add, keyboard Delete/⌘D,
  edge delete, drop). Banner: "Layout locked on small screens". The read-only
  and historical-version banners stack in one flow container (no overlap even
  when the text wraps at 320px).
- [x] **Toasts** offset 112px above the bottom edge (16px on touch) — measured
  clear of the run FAB (toast.bottom 788 < fab.top 803 @900px viewport).
- [x] **Text-size one-offs eliminated**: new `text-2xs` (10px/14px) Tailwind token;
  all 58 `text-[9px]`/`text-[10px]`/`text-[11px]` occurrences consolidated to
  `text-2xs`/`text-xs`. Sole exception: the `.text-micro` token definition.
- [x] **Reduced motion end-to-end**: all five React Flow viewport animations use
  a `useReducedMotionStrict`-gated duration (proven: fitView snaps instantly
  under `prefers-reduced-motion` and animates without it), and a global
  `<MotionConfig reducedMotion="user">` now covers every framer-motion
  animation (BaseNode layout/size, error tooltip, run FAB pop).
- [x] **Home list virtualized** past 80 rows (12 DOM rows for a 556-row
  workspace; windowed scrolling verified). `itemHeight` 72 keeps the
  virtualized and plain branches pixel-identical (border-box).

Remaining known gap (accepted): none from the original audit. New observations
from the verification pass, accepted as-is: the mobile width check is
viewport-based (a narrowed desktop window also locks layout — intentional);
workflow-level operations (Save / Import / field edits via inspector) stay
available on mobile by design.
