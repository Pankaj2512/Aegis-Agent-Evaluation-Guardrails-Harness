# In-Depth UI/UX Audit — 2026-07-25

**Method.** Two independent passes, merged:

1. **Multi-agent code audit** — 7 parallel dimension auditors (accessibility, design tokens/theming, typography/numerics, component consistency, layout/responsiveness, state coverage, IA/copy) swept `frontend/src`; every finding was then **adversarially verified by a dedicated skeptic agent** that re-read the cited code and the design-system context before confirming (72 agents total; every finding below survived verification — several had severities corrected or evidence strengthened by the verifier).
2. **Live interactive pass** — drove the running app (all routes, all four observability views, canvas + node inspector, both dark and warm-light themes), with API probes to root-cause what the screen showed.

**The quality bar** is the repo's own design system: instrument aesthetic, chroma only for data semantics, flat elevation + hairlines, mono/tabular numerics, ≤220 ms reduced-motion-gated motion, both themes, shared `components/ui` primitives.

**Result: 74 confirmed findings — 3 P0, 42 P1, 29 P2.** Severity rubric: P0 = broken/misleading/inaccessible; P1 = clear design-system violation or real UX friction; P2 = polish.

## Top themes

1. **A dead focus ring, app-wide (P0).** `Button` uses Tailwind v4-only `ring-3` syntax in a v3 build — the primary interactive primitive has no visible keyboard focus anywhere. Several other v4-isms are dead in the vendored shadcn primitives.
2. **Misleading eval chroma (P0).** The trace's eval chip bands 1–5 judge scores on a 0–1 scale, so *every* eval — including a worst-case failing 1.0/5 — renders the green success tone. The core pass/fail chroma semantic is inverted on the flagship trace surface.
3. **Wrong timezone under a 'UTC' label (P0).** The schedule trigger's 'Next runs (UTC)' preview formats with `toLocaleString()` — local times presented as UTC.
4. **An error-state pandemic (13 P1/P2 findings).** Across the new Trust/Sessions/rubrics/policies surfaces, query failures render as *healthy empties* ('No sessions yet', 'No alert rules yet', green-check 'No failure clusters') or infinite skeletons. A failed request should never assert an empty truth.
5. **Formatter/label duplication that already drifted.** 8 status-tone maps, 7 ms-formatters, 5 guardrail-type label maps, 4 ad-hoc chips — same data, different names/formats on adjacent screens (e.g. p99 '5.7s' vs '9,114ms' one tab apart).
6. **Window inconsistency across observability views.** Adjacent tabs disagree on the same headline metrics because each computes over a different run window with only quiet captions.

## P0 — Broken / misleading / inaccessible (3)

### Information architecture & copy

#### Trace eval chip bands 1–5 LLM-judge scores on a 0..1 scale — failing evals always render a green 'success' chip
*`frontend/src/components/runs/TraceNodeRow.tsx:101`*

evalTone() bands the node eval aggregate with 0..1 thresholds (>=0.7 success, >=0.4 warning), and the local comment claims the score is '(0..1)'. But the LLM-judge aggregate is a weighted mean of 1–5 dimension scores (backend/app/services/eval.py compute_aggregate_score, toxicity inverted as 6-x; RunDetailView.tsx:413 correctly renders it as `${evalAggregate.toFixed(2)} / 5`, and AlertsCard's eval_avg hint says '1–5'). The minimum possible LLM-judge aggregate is 1.0, which is >= 0.7, so every LLM-judge eval chip on the run trace — including a worst-case 1.0/5 that fails the threshold — shows the green success tone. This inverts the design system's core 'eval pass/fail band' chroma semantics on the primary trace surface. Only deterministic evals (0/1 exact/regex/schema aggregates) band correctly.

**Fix:** Band by the value's actual scale: `const tone = score > 1 ? (score >= 3.5 ? "success" : score >= 2.5 ? "warning" : "destructive") : (score >= 0.7 ? ...)`, and append the scale to the chip copy (`eval 3.40/5`) and title so the number is self-describing. Update the evalAggregate() doc comment.

### Design tokens & theming

#### Button focus ring never renders: Tailwind v4-only `ring-3` in a v3 build
*`frontend/src/components/ui/button.tsx:8`*

The project runs Tailwind v3.4.19 (package.json / node_modules), but Button's base classes use v4-only `ring-3`. Compiling a probe against the project's own tailwind.config.ts emits NO CSS for `ring-3` (while `ring-2` compiles), so `focus-visible:ring-3 focus-visible:ring-ring/50` produces no ring at all — `ring-ring/50` only sets a color variable that nothing consumes. The only surviving focus affordance is `focus-visible:border-ring`, a 1px border tint that is ~1.4:1 contrast against the default bone (dark) / ink (light) primary button fill — effectively invisible keyboard focus on the app's most common interactive element, in BOTH themes. `aria-invalid:ring-3` and `aria-invalid:ring-destructive/20` are dead for the same reason. This silently violates the system's 'interactive elements need visible focus (focus-ring)' bar everywhere Button is used.

**Fix:** Replace `ring-3` with `ring-2` (both occurrences in the cva base string), or apply the house `.focus-ring` utility from globals.css (`box-shadow: 0 0 0 2px var(--bg), 0 0 0 4px var(--ring)`), which is what the rest of the app uses.

### Typography & numerics

#### Schedule trigger preview labeled "Next runs (UTC)" renders local-time values
*`frontend/src/components/canvas/NodeInspector.tsx:355`*

The trigger node's cron preview heading says "Next runs (UTC)" (line 352) and the hint says "Standard 5-field cron (UTC)" (line 345), but each timestamp is rendered with new Date(runAt).toLocaleString(), which converts to the browser's local timezone. The backend genuinely returns UTC instants (backend/app/services/cron_utils.py: `itr.get_next(datetime).replace(tzinfo=timezone.utc)`, serialized via isoformat in api/meta.py), so for any user not in UTC the values shown under the UTC label are wrong per that label — a user verifying `0 9 * * 1-5` in IST sees "2:30:00 pm" under "Next runs (UTC)". Line 362 ("Last scheduled run: {new Date(lastFiredAt).toLocaleString()}") has the same raw-formatting problem. These timestamps are also plain sans text — the design system requires all timestamps in font-mono + tabular-nums.

**Fix:** Make label and value agree: either format in UTC — new Date(runAt).toLocaleString(undefined, { timeZone: "UTC", timeZoneName: "short" }) — or relabel the block "Next runs (local time)". Wrap the list items and the "Last scheduled run" value in font-mono tabular-nums (or reuse formatFullTimestamp with an explicit UTC variant in lib/format-date.ts).

## P1 — Design-system violations & real UX friction (42)

### Accessibility

#### Observability view switcher is a role="tablist" whose children are not tabs
*`frontend/src/app/observability/page.tsx:456`*

The Triage | Trust | Sessions | Cost & usage switcher wraps FilterChip components in role="tablist", but FilterChip (src/components/ui/filter-chip.tsx:12-15) renders a plain <button> with aria-pressed and no role="tab", aria-selected, or aria-controls. ARIA requires tablist children to be role="tab"; screen readers will announce an empty/broken tab list, and none of the tablist keyboard conventions (arrow-key navigation) exist. The same FilterChips are correctly wrapped in role="group" in TriageStream.tsx:56, so this one surface has invalid semantics. Properly built tablists exist elsewhere (CanvasSidebar.tsx:102-122, WorkflowCanvas.tsx:2465-2496), proving the intended pattern.

**Fix:** Change role="tablist" to role="group" (matching TriageStream.tsx:56), since FilterChip already exposes aria-pressed toggle state; or, if tab semantics are wanted, add role="tab"/aria-selected/aria-controls props to FilterChip and wire arrow-key handling.

#### Canvas right-panel resize handle is keyboard-focusable but has no visible focus indicator
*`frontend/src/components/canvas/WorkflowCanvas.tsx:2463`*

useResizablePanel's handleProps (src/hooks/use-resizable-panel.ts:184-199) makes the handle a tabIndex=0 role="separator" with arrow-key resizing — good — but the right-panel handle div omits the focus-ring class that its twin in CanvasSidebar.tsx:96 has. globals.css globally suppresses the native indicator (`:focus-visible { outline: none; }`, line ~255), and the handle is a 3px transparent strip, so when a keyboard user tabs onto it there is zero visual indication of focus: an invisible interactive control.

**Fix:** Add the focus-ring class (and ideally focus-visible:bg-primary/30) to this handle, mirroring CanvasSidebar.tsx:96: className="focus-ring absolute inset-y-0 -left-px z-10 block w-[3px] …".

#### Visible <Label> elements rendered without htmlFor/id association to their controls
*`frontend/src/components/settings/EvalRubricCard.tsx:210`*

The Label primitive (src/components/ui/label.tsx) is a plain sibling <label>, so without htmlFor + a matching control id there is no programmatic association: screen readers announce the Input/Textarea/Select with no name, and clicking the label doesn't focus the field. Sites: EvalRubricCard.tsx:210 (Internal name), 219 (Display label), 227 (Criteria), 236 (LLM instruction); WorkflowDataPanel.tsx:275 (Title), 284 (Content), 297 (Bulk import); WorkflowGuardrailField.tsx:41 ("Workflow guardrail policy" Label with two unlabeled Radix Selects at 45-66 and 69-83, whose accessible name degrades to the current value, e.g. "None"). The codebase convention already exists — GuardrailPlayground.tsx uses useId + fieldId() with htmlFor/id on every field, as does NodeInspector — so these recently added cards drifted.

**Fix:** Follow the GuardrailPlayground pattern: const baseId = useId(); give each control id={`${baseId}-name`} and each Label htmlFor the same id; for the two WorkflowGuardrailField Selects put id on SelectTrigger and htmlFor on the Label (plus aria-label="Guardrail mode" on the second Select).

#### Form controls whose only name is a placeholder (no Label, no aria-label)
*`frontend/src/components/canvas/ExperimentsPanel.tsx:182`*

Placeholder text is not an accessible name (it vanishes on input and is not reliably announced). Sites: ExperimentsPanel.tsx:182 ("New dataset name…" Input), 200 ("Add test input…" Input) and the dataset Select at 168-171 whose SelectTrigger has no aria-label (unlike the capture-filter Select at 225 which has one); EvalRubricCard.tsx:278-296 (three "Test on a sample" Textareas: sample input, sample output, retrieved context); AssistRail.tsx:176-180 (AI-assist instruction Textarea); NodePalette.tsx:106-111 (node search Input). Nearby controls in the same files (e.g. ExperimentsPanel's "Capture filter"/"Baseline version" Selects, QuickAddMenu.tsx:239 search) all carry aria-label, so these are omissions, not a different convention.

**Fix:** Add aria-label to each control (e.g. aria-label="New dataset name", aria-label="Dataset", aria-label="Sample output to grade", aria-label="Describe an edit", aria-label="Search nodes"), or attach proper Label/htmlFor pairs where a visible label fits.

### Consistency & duplication

#### Run/severity status→tone map re-implemented 8+ times and already drifted (running = warning vs active vs muted)
*`frontend/src/components/observability/SessionsView.tsx:60`*

lib/run-status.ts is the canonical status→variant map (running/pending/queued → warning, awaiting_approval → accent), but at least eight components re-implement their own map and the semantics have drifted: lib/run-status.ts:3-17 (runStatusVariant: running→warning), components/observability/run-row.tsx:16-22 (statusDotClass: running→bg-warning, awaiting_approval→bg-accent), components/observability/SessionsView.tsx:60-66 (StatusMix inline: only failed/cancelled/completed colored, so a RUNNING session count renders text-muted), components/observability/ViolationBreakdown.tsx:30-34 (statusTone), app/observability/page.tsx:254-265 (kindClass: awaiting→text-accent), components/runs/TraceNodeRow.tsx:43-51 (statusRing: running→ring-warning) and 108-114 (guardrailTone), components/canvas/run/RunDeck.tsx:283-299 (statusClass: running/awaiting_approval→text-active, a different token than everywhere else) and 325 (eventClass), components/canvas/run/RunNodeResultCard.tsx:38-46 (statusTone: running→border-active). The same run status gets amber on /observability, 'active' hue on the canvas RunDeck, and plain muted in SessionsView — a direct violation of 'chroma reserved for data semantics' being consistent.

**Fix:** Extend lib/run-status.ts with the missing projections — runStatusTextClass(status), runStatusDotClass(status), guardrailTone(status) — and replace the local maps in SessionsView, run-row, ViolationBreakdown, TraceNodeRow, RunDeck, RunNodeResultCard, and observability/page.tsx with imports, deciding once whether live statuses are 'warning' or 'active'.

#### Guardrail rail-type label map duplicated 5x with drifted vocabulary; ViolationBreakdown's copy is missing json_schema so the raw enum leaks to the UI
*`frontend/src/components/observability/ViolationBreakdown.tsx:13`*

Five independent human-label maps exist for the same GuardrailType enum: components/observability/ViolationBreakdown.tsx:13-28 (typeLabel — has no json_schema case, so a json_schema violation row on the Trust dashboard prints the raw 'json_schema' token), components/guardrails/VerdictPanel.tsx:20-27 (TYPE_LABELS: 'rules', 'prompt injection', 'json schema'), components/guardrails/GuardrailPlayground.tsx:68-83 (guardrailTypeLabel: 'Keyword rules', 'PII scan', 'Injection check') plus its own third vocabulary in the SelectItems at 233-237 ('Rules', 'Presidio PII'), components/guardrails/PolicyTemplates.tsx:37-42 (ruleSummary prints raw rules_json values), and components/canvas/NodeInspector.tsx:2332-2337 ('Rule-based (keywords, regex, PII)', 'Prompt injection shield (Gemini)'). The same rail is named 'rules', 'Rules', 'keyword rules', 'Keyword rules', and 'Rule-based (keywords, regex, PII)' depending on the surface.

**Fix:** Create one GUARDRAIL_TYPE_LABELS map (e.g. in src/lib/ or next to the GuardrailType type in types/workflow.ts) with a short label per rail (and optional long/hint text for the NodeInspector select), import it in all five sites, and add the missing json_schema entry.

#### Millisecond/latency formatter implemented 7 times with 4+ visibly different output formats, including on the same screen
*`frontend/src/components/observability/CostDashboard.tsx:61`*

There is no shared ms formatter in lib/format.ts, so each surface rolled its own and they disagree: components/observability/CostDashboard.tsx:61-64 (formatLatency never converts to seconds — a 12,340ms p99 renders '12,340ms' on the Cost & usage view) vs components/observability/TrustDashboard.tsx:23-26 (ms(): '12.3s' for the same value on the Trust view of the same /observability page); components/runs/TraceNodeRow.tsx:54-57 (formatMs: '940 ms' / '1.2 s' with a space) vs components/runs/TraceTimeline.tsx:26-30 (formatTick: '940ms' / '1.2s' without a space) — both rendered inside the same Node timeline card; components/runs/RunDetailView.tsx:44-50 (formatDuration: '940 ms'); components/canvas/run/RunDeck.tsx:140-146 (formatDuration: trailing-zero-stripped, toFixed(2) under 10s); components/canvas/run/RunNodeResultCard.tsx:112 (inline toFixed(2)). All numerics are mono/tabular, but the unit formatting is inconsistent across and within surfaces.

**Fix:** Add a canonical formatMs(ms) to src/lib/format.ts (e.g. <1000 → '940ms', otherwise '1.2s'/'12s') alongside formatCostUsd, and replace the seven local implementations with it.

#### Compact mono chip re-implemented ad hoc in 4+ feature components, with tone classes copy-pasted from Badge and already drifted
*`frontend/src/app/observability/page.tsx:444`*

The 'rounded border px-1.5 py-0.5 font-mono text-2xs' chip is hand-built in: app/observability/page.tsx:430-453 (liveBadge — uses border-success/30 bg-success/10, drifted from the Badge success variant's border-success/25 bg-success/12), components/runs/TraceNodeRow.tsx:63-90 (TraceChip + CHIP_TONE whose success/warning/destructive/outline strings are verbatim copies of badgeVariants in ui/badge.tsx:11-15), components/guardrails/VerdictPanel.tsx:29-35 (local Chip), and components/guardrails/PolicyTemplates.tsx:103-105 (category chip, which alone uses text-micro instead of text-2xs). Four hand-rolled variants of the same primitive means the next token change to Badge tones will not propagate, and one has already diverged.

**Fix:** Add a shared compact chip to src/components/ui/ (e.g. a Badge size="chip" or a Chip component that reuses badgeVariants tones with mono/2xs metrics) and replace liveBadge, TraceChip, VerdictPanel Chip, and the PolicyTemplates category chip with it.

#### Two stacked passed/warned/failed severity bars rendered on the same Trust screen with drifted height and opacity
*`frontend/src/components/observability/ViolationBreakdown.tsx:91`*

TrustDashboard's Safety pillar (components/observability/TrustDashboard.tsx:179-192) renders a stacked guardrail-severity bar as h-2 with bg-success/70, bg-warning/70, bg-destructive/70. ViolationBreakdown (components/observability/ViolationBreakdown.tsx:91-98) renders the identical data concept as h-1.5 with bg-success/60, bg-warning/70, bg-destructive/70. ViolationBreakdown is mounted BY TrustDashboard (TrustDashboard.tsx:207), so both implementations appear on the same Trust view a few hundred pixels apart, showing the same passed/warned/failed semantics at different weights — duplicated component logic that has already drifted.

**Fix:** Extract a shared <SeverityBar passed warned failed height?> primitive in src/components/ui/ with one set of segment opacities, and use it in both TrustDashboard's Safety pillar and ViolationBreakdown's per-type rows.

#### Centralized queryKeys shadowed by inline duplicates; queryKeys.runSession is dead while SessionsView invents its own keys
*`frontend/src/components/observability/SessionsView.tsx:20`*

CLAUDE.md states cache keys are centralized in src/lib/query-keys.ts ('add new keys there, don't inline them'), but the recently added surfaces inline them — including duplicating keys that already exist centrally: queryKeys.evalPresets (query-keys.ts:12) exists yet EvalRubricCard.tsx:35,102,374 inlines ["eval-presets"]; queryKeys.alertRules (query-keys.ts:13) exists yet AlertsCard.tsx:47,55 inlines ["alert-rules"]; queryKeys.runSession (query-keys.ts:23, ["run-session", id]) is completely unused while SessionsView.tsx:20 invents ["session-runs", sessionId] and :82 invents ["run-sessions"]; ["guardrail-policies"] is inlined in three files (SavedPolicies.tsx:67,72; PolicyTemplates.tsx:67; WorkflowGuardrailField.tsx:35); ["observability-errors"] is inlined in both app/observability/page.tsx:324 and TrustDashboard.tsx:58. Inline string keys that must match across files for invalidation to work is exactly the drift this convention prevents (the near-miss 'run-session' vs 'session-runs' shows it happening).

**Fix:** Add the missing entries to lib/query-keys.ts (guardrailPolicies, guardrailPolicyTemplates, runSessions, sessionRuns(id), observabilityErrors, observabilityCosts, alertEvents), delete or repurpose the dead runSession key, and replace every inline literal with the queryKeys reference.

#### PolicyTemplates and SavedPolicies hand-roll the SectionCard shell and drop the surface-card highlight every other card has
*`frontend/src/components/guardrails/PolicyTemplates.tsx:77`*

ui/section-card.tsx is the house recipe ('surface-card rounded-lg border border-border bg-surface shadow-elev-1' + hairline header with title/description/actions). PolicyTemplates.tsx:77-86 and SavedPolicies.tsx:101-109 rebuild this exact shell as raw <section>/<header> markup but omit the surface-card class, so these two cards lose the ::before inset top highlight (globals.css:274-284) that SectionCard, Card, and GlassCard all apply — a visible surface-treatment drift between the guardrails page's right column and every other card in the app. GuardrailPlayground.tsx:170 and 282 also hand-roll the shell (they do keep surface-card). Both PolicyTemplates and SavedPolicies map 1:1 onto SectionCard's title/description/children API.

**Fix:** Replace the hand-rolled <section>/<header> in PolicyTemplates and SavedPolicies with <SectionCard title description>, passing the Sparkles icon inside the title node; at minimum add the missing surface-card class.

### Information architecture & copy

#### Observability PageHeader description is Triage-only copy, stays stale on Trust / Sessions / Cost views
*`frontend/src/app/observability/page.tsx:484`*

The PageHeader description is hardcoded to the Triage view's job ('Triage regressions, failures, and blocked runs…') but renders unchanged while the view toggle switches to Trust, Sessions, or Cost & usage (lines 515–520). A user on the Cost view reads a header telling them they're triaging failures — wrong orientation copy on a primary surface, and it contradicts each view's actual content (SLO tiles, session threads, spend tables).

**Fix:** Derive the description from `view`, e.g. a `VIEW_COPY: Record<view, string>` map — triage: existing copy; trust: "Quality, safety, cost, and reliability SLOs over the recent run window."; sessions: "Multi-turn runs grouped by session."; cost: "Spend, tokens, and latency by workflow, node, and model." — and pass `VIEW_COPY[view]`.

#### Observability view toggle not persisted in the URL — reload and deep links always reset to Triage
*`frontend/src/app/observability/page.tsx:272`*

The Triage/Trust/Sessions/Cost switch is plain useState, so /observability cannot deep-link any view: reload, back/forward, and shared links all land on Triage. The app already established the URL-param pattern for exactly this (templates honours ?filter= via window.location.search on mount, app/templates/page.tsx:450–456, and the guardrails banner links to /templates?filter=guardrail). The gap is self-inflicted inside the page too: TrustDashboard's own footer link (TrustDashboard.tsx:277, 'Drill into per-run traces from any run') points at href="/observability", which navigates the user off the Trust view back to Triage.

**Fix:** Initialize view from `new URLSearchParams(window.location.search).get("view")` after mount (same pattern as templates/page.tsx) and `history.replaceState` a `?view=` param in setView's wrapper. Then update the TrustDashboard footer link to a real target (e.g. `/observability?view=triage` with copy that says so, or drop the self-link).

#### Settings still says 'Eval presets' in the page header, section nav, and command palette after the section was renamed 'Eval rubrics'
*`frontend/src/app/settings/page.tsx:202`*

The section itself is titled 'Eval rubrics' (EvalRubricCard.tsx:149) and all its actions say rubric ('New rubric', 'Rubric saved', 'Delete rubric?'), but three navigation surfaces still advertise the old name: the Settings PageHeader description ('…eval presets, and alerts', settings/page.tsx:202), the SettingsNav anchor label ('Eval presets', SettingsNav.tsx:10), and the command palette's Settings entry ('Credentials, API auth, and evaluation presets', CommandPalette.tsx:121). Users searching for 'rubrics' find nav items that don't exist, and the nav label doesn't match the section heading it scrolls to. The canvas NodeInspector eval section also still labels the same rubric picker 'Eval preset' (NodeInspector.tsx:1896).

**Fix:** Rename all four sites to rubric terminology: settings/page.tsx:202 → '…eval rubrics, and alerts.'; SettingsNav.tsx:10 label → 'Eval rubrics'; CommandPalette.tsx:121 → '…and eval rubrics'; NodeInspector.tsx:1896 label → 'Eval rubric'. (The anchor id `settings-presets` can stay — only labels are user-facing.)

### Layout & responsiveness

#### RunDeck Stop/collapse controls live inside the horizontally scrolling step strip and scroll out of view during live runs
*`frontend/src/components/canvas/run/RunDeck.tsx:614`*

The run-lens header row is one `overflow-x-auto` container holding both the step strip (`<ol className="flex min-w-max flex-1">`, each li `min-w-[138px] sm:min-w-[152px]`) and, after it in flow, the status/Stop/collapse cluster (line 636 `ml-auto flex shrink-0 ... border-l`). With ~5+ nodes the strip exceeds the deck width (5x152 + connectors + controls > 1000px), the container scrolls, and at the default scroll position the live elapsed timer, the Stop button (line 650) and the collapse toggle are pushed off-screen right — the user must discover horizontal scroll to stop a live run. min-w-max on the ol guarantees it never shrinks.

**Fix:** Move the `ml-auto` controls cluster outside the overflow-x-auto element (wrap only the <ol> in a `min-w-0 flex-1 overflow-x-auto` div), or make the cluster `sticky right-0 bg-surface` so it stays pinned while the strip scrolls.

#### NodeInspector sticky header floats inside the canvas panel's p-4 wrapper — 16px see-through gutters when pinned, plus double horizontal padding on all fields
*`frontend/src/components/canvas/NodeInspector.tsx:1186`*

The inspector header is styled as a full-bleed docking bar (`sticky top-0 z-10 ... border-b bg-surface-elevated` with a category rule `absolute inset-y-0 left-0 w-[3px]`), but its only call site renders it inside `<div className="space-y-4 p-4">` (WorkflowCanvas.tsx:2514) within the scroll container at WorkflowCanvas.tsx:2508. When the panel scrolls, the header pins at the scrollport top while form content scrolls visibly through the 16px gutters on either side of it, and the 3px category rule sits 16px away from the panel edge instead of hugging it. The inspector body also adds its own `px-4` (line 1235), so every field gets 32px padding per side — at the panel's 320px minimum width (useResizablePanel min: 320) content is squeezed to ~256px, making rows like the Reliability `grid grid-cols-3 gap-2` (line 2702) ~76px per numeric input.

**Fix:** Remove `p-4` from the configure tabpanel wrapper in WorkflowCanvas.tsx:2514 (NodeInspector already pads its own body via px-4) and add `p-4` locally to the EdgeInspector / multi-select branches, so the sticky header spans the full panel width.

#### PageHeader actions slot combines shrink-0 with flex-wrap — wrap can never trigger, run-detail header overflows horizontally at sm–md widths
*`frontend/src/components/ui/page-header.tsx:45`*

A flex item with `shrink-0` keeps its single-line max-content width, so the `flex-wrap` on the same element is inert — in `sm:flex-row` mode the actions cluster never wraps. RunDetailView passes six controls (Back, feedback group, status Badge, TraceIdBadge, Export, Workflows — RunDetailView.tsx:296–387), roughly 550px of chrome; between 640px and ~900px viewports the header overflows the page-container and forces horizontal page scroll. Same inert `shrink-0 flex-wrap` combo on the TraceNodeRow chip cluster (frontend/src/components/runs/TraceNodeRow.tsx:179 `flex shrink-0 flex-wrap items-center justify-end gap-1.5`), which instead squeezes the node label to near-zero before its chips ever wrap.

**Fix:** Drop `shrink-0` (or replace with `min-w-0 justify-end`) on the PageHeader actions container so flex-wrap can engage; same change on the TraceNodeRow chip cluster.

#### Run payload text uses whitespace-pre-wrap without break-words — long unbroken tokens (URLs, ids, base64, minified JSON) overflow their bordered cards
*`frontend/src/components/runs/RunDetailView.tsx:517`*

`whitespace-pre-wrap` wraps only at whitespace; a single long token overflows the rounded/bordered card horizontally with no scroll or clip. This renders user-supplied and model-generated text, where unbroken tokens are routine. Sites (all verified, none have break-words/overflow): RunDetailView.tsx:517 (run input), :465 (approval review), :567 (final output <pre>); TraceNodeRow.tsx:359 (node output); ExplainFailureCallout.tsx:70 (explanation); RunResultsPanel.tsx:117 (approval review) and :221 (final output) — the last two live in the canvas right panel at 320–520px width, where overflow is most likely. Contrast: HighlightedSample.tsx:170 and NodeInspector's pres correctly add break-words.

**Fix:** Add `break-words` to all seven pre-wrap payload blocks (for the <pre> at RunDetailView.tsx:567 also works; alternatively give it overflow-x-auto).

### Live-app behavior

#### Canvas marks itself dirty on selection-only interaction — 'Leave site?' guard fires after just clicking a node
*`frontend/src/components/canvas/WorkflowCanvas.tsx`*

Opened a workflow whose status bar read 'Saved', clicked the Trigger node (selection only — no move/edit) and toggled the app theme; navigating away then triggered the browser 'Leave site? unsaved changes' dialog. Selection/theme-only interactions are marking the graph dirty, so users get scary unsaved-changes prompts after read-only visits.

**Fix:** Exclude selection-only changes (and any non-graph state) from the dirty computation — compare persisted graph fields (node positions/data/edges) rather than React Flow's full state, or ignore `selected` flags when diffing.

#### Cross-view metric contradictions: same metric, different values and windows on adjacent observability tabs
*`frontend/src/app/observability/page.tsx`*

Observed live: Trust tab shows latency p99 5.7s / cost $0.2418 ('last 500 runs'); Cost & usage tab shows p99 9,114ms / total spend $0.4427 ('1,279 runs'); Triage tiles show p50 192ms ('last 500') while Cost shows p50 217ms ('935 samples'); eval pass rate is '—' on Triage/home ('last 100 runs') but 50% on Trust ('last 500'). Each view is internally consistent, but adjacent tabs contradict each other with only quiet window captions.

**Fix:** Pick one canonical window for headline tiles across views (the /trust window), or make the window a visible, shared control ('Window: last 500 runs') so differing numbers are explained where they differ.

#### PASS RATE tile shows '—' beside '15 eval runs' when no run carries a pass/fail verdict
*`frontend/src/components/home/HomeOverviewStrip.tsx`*

API-confirmed: quality reports eval_run_count=15 but eval_pass_count=0 and eval_fail_count=0 (no thresholds configured), so eval_pass_rate=None renders as '—' directly above the caption '15 eval runs' (home PASS RATE tile and the observability EVAL PASS RATE tile). Reads as broken data: 15 evals but a dash.

**Fix:** When eval_run_count > 0 but no verdicts exist, fall back to showing the average score ('avg 3.2 / 5') or caption honestly: '15 scored · no pass/fail thresholds set'.

#### 'Live updates offline — values may be stale' banner flaps and fires during initial SSE connect
*`frontend/src/providers/ObservabilityStreamProvider.tsx`*

Observed live: the observability badge flipped 'Updates offline' → 'Live updates' → 'Updates offline' across consecutive views within one minute, and the alarming full-width offline banner shows on every fresh page load before the SSE stream finishes connecting (stream emits nothing for seconds). The claim 'values may be stale' is wrong on first paint — the snapshot was just fetched.

**Fix:** Add a 'connecting' grace state (no banner for the first ~5s / until first failure), debounce the offline flip (e.g. 10s of sustained disconnect), and soften copy while data is fresh.

#### Eval rubrics list lost pagination in the settings refactor — unbounded list of dozens of rubrics
*`frontend/src/components/settings/EvalRubricCard.tsx:141`*

The old inline eval-presets section paginated custom presets 5 per page with a pager; EvalRubricCard renders every custom rubric in one unbounded list (dev DB shows a full screen of identical 'Enriched' rows). A long list buries the editor form and 'Test on a sample' panel beneath it.

**Fix:** Restore pagination (5–8/page like the old PRESETS_PAGE_SIZE) or cap with a max-height scroll region + count, keeping the editor visible.

#### Cost breakdown lists duplicate same-name workflow rows with no disambiguation
*`frontend/src/components/observability/CostBreakdownTable.tsx`*

Observed live on Cost & usage → By workflow: 'Half Hourly' appears 5×, 'Cron Flow' 4×, 'My Agent Workflow' 2× — distinct workflow ids sharing one name, rendered as identical rows. Users cannot tell which row is which workflow.

**Fix:** Disambiguate rows that share a name (append a short id suffix or created date), or aggregate by name with an expandable breakdown; also consider linking each row to the workflow.

### Loading/empty/error states

#### TrustDashboard renders a permanent loading spinner if /trust errors
*`frontend/src/components/observability/TrustDashboard.tsx:63`*

The Trust view's only guard is `isLoading || !trust`. When api.getObservabilityTrust rejects (request() in lib/api.ts:89 throws on non-OK), isLoading goes false, trust stays undefined, and the entire Trust tab is stuck on 'Loading trust metrics…' forever — an error presented as an in-progress load, with no retry and no message. The sibling CostDashboard (CostDashboard.tsx:101-112) already handles isLoading/isError/refetch correctly with ApiConnectionState, so the pattern exists in the codebase.

**Fix:** Destructure `isError, error, refetch` from the useQuery, keep the LoadingState for `isLoading` only, and render `<ApiConnectionState description="Trust metrics could not be loaded…" error={error} onRetry={() => void refetch()} />` on error, mirroring CostDashboard.

#### ViolationBreakdown shows an infinite 'Loading violations…' skeleton on query error
*`frontend/src/components/observability/ViolationBreakdown.tsx:49`*

Same broken guard as TrustDashboard: `if (isLoading || !data)` returns the list skeleton. If /guardrails/violations 500s, the SectionCard shows a shimmering 'Loading violations…' list forever inside the Trust view — the safety drill-down silently never arrives and the user has no way to know it failed or retry.

**Fix:** Add `isError, refetch` to the destructure; on error render the SectionCard with an inline error line ('Couldn't load guardrail violations') plus a Retry button instead of the LoadingState.

#### Failed errors query renders green-check 'No failure clusters' — false healthy signal
*`frontend/src/app/observability/page.tsx:600`*

Both callers of FailureClusters pass an errored query as an empty success: app/observability/page.tsx:600-604 and TrustDashboard.tsx:210-214 do `clusters={errors?.clusters ?? []} loading={errorsLoading}` with no isError. When getObservabilityErrors fails, FailureClusters.tsx:39-43 renders a CheckCircle2 in text-success with 'No failure clusters in the recent window.' — the reliability panel asserts the system is clean precisely when the health check itself failed. Neither call site reads `isError` from the query.

**Fix:** Add an `error?: boolean` prop to FailureClusters that renders 'Couldn't load failure clusters' (no success check) with a retry affordance; pass `error={errorsIsError}` from both call sites (observability page and TrustDashboard).

#### SessionsView shows 'No sessions yet' EmptyState when the sessions query fails
*`frontend/src/components/observability/SessionsView.tsx:81`*

The sessions query destructures only `data, isLoading`; `sessions` defaults to []. On a /runs/sessions failure the Sessions tab confidently renders the onboarding EmptyState ('No sessions yet — pass a session_id…', line 102-108), telling the user their sessions don't exist rather than that the request failed. The nested SessionRuns query (line 19-25) has the same hole: on error it renders 'No runs.' for a session that demonstrably has runs (its run_count is displayed on the same row).

**Fix:** Destructure `isError, refetch` in both queries; in SessionsView render an inline error branch with Retry before the EmptyState check, and in SessionRuns render 'Couldn't load runs for this session' instead of 'No runs.' on error.

#### AlertsCard renders 'No alert rules yet' on rules-query error; alert events fail invisibly
*`frontend/src/components/settings/AlertsCard.tsx:47`*

`rules` defaults to [] and isError is never read, so a failed listAlertRules renders the Bell EmptyState 'No alert rules yet' (lines 241-248) — an operator checking their alerting after an incident is told their rules are gone. The events query (line 48-52) is worse: `events = []` and the 'Recent alert events' section is gated on `events.length > 0` (line 251), so a failure silently hides fired alerts with zero indication anything is missing.

**Fix:** Read `isError` from both queries; render an inline destructive-text error row with a Retry action in place of the rules EmptyState, and under the events section show 'Couldn't load recent alert events' when that query errors.

#### EvalRubricCard shows 'No custom rubrics yet.' when the presets query fails
*`frontend/src/components/settings/EvalRubricCard.tsx:34`*

`presets` defaults to [] with no isError handling, so a failed listEvalPresets renders 'No custom rubrics yet.' (line 155). A user who has authored rubrics is told they don't exist; they may recreate one (create will collide or duplicate) or believe their rubrics were deleted. Mutations in this file are handled well (pending flags + failure toasts), which makes the missing list error state stand out.

**Fix:** Destructure `isError, refetch`; add an error branch before the `custom.length === 0` check: 'Couldn't load rubrics' + Retry button.

#### SavedPolicies shows 'No saved policies yet' EmptyState when the policies query errors
*`frontend/src/components/guardrails/SavedPolicies.tsx:63`*

`policies` defaults to [] and isError is unread, so on a failed listGuardrailPolicies the guardrails page renders the Bookmark EmptyState 'No saved policies yet — Configure a guardrail above, then save it to reuse the setup.' (lines 142-148). This also cascades: WorkflowGuardrailField (canvas trigger section) reads the same ["guardrail-policies"] cache, so the user is misled on two surfaces about their policies not existing.

**Fix:** Destructure `isError, refetch` and render an error branch ('Couldn't load saved policies' + Retry) between the isLoading and empty checks.

#### PolicyTemplates has neither an empty state nor an error state — renders a bare hairline box
*`frontend/src/components/guardrails/PolicyTemplates.tsx:92`*

After isLoading, the component unconditionally renders `<ul className="divide-y divide-border overflow-hidden rounded-md border border-border">` and maps templates. If getGuardrailPolicyTemplates fails (templates defaults to []) or legitimately returns zero templates, the card shows an empty bordered rectangle with no content, no message, and no retry — indistinguishable from a rendering bug. Every neighboring card (SavedPolicies, AlertsCard) at least has an EmptyState.

**Fix:** Read `isError, refetch` from the query; render an error branch with Retry on failure, and an `EmptyState compact` ('No templates available') when `templates.length === 0`, only rendering the bordered ul when there are items.

#### Run approval Approve/Reject buttons have no pending state — double-submit and approve/reject race
*`frontend/src/components/runs/RunDetailView.tsx:470`*

In the 'Approval required' panel, both buttons fire `await api.approveRun(...)` from onClick with no in-flight flag: neither button is disabled while a decision is pending, and there is no loading label. A double-click sends the approval twice, and a user can click Approve then Reject (or vice-versa) while the first request is in flight, racing two contradictory decisions on a human-approval gate. Every other mutation in this file (feedback thumbs at line 317, `disabled={feedbackGiven !== null}`) and across the app (ExperimentsPanel's single `pending` flag) is double-click-safe — this one governs the highest-stakes action.

**Fix:** Add `const [deciding, setDeciding] = useState<"approve" | "reject" | null>(null)`; set it before the call, clear in finally, and put `disabled={deciding !== null}` on both buttons with 'Approving…'/'Rejecting…' labels.

#### ExperimentsPanel: datasets and versions query failures are completely silent
*`frontend/src/components/canvas/ExperimentsPanel.tsx:59`*

The datasets query (line 59-62) and versions query (line 71-74) destructure only `data` with [] defaults — no isLoading, no isError. If listDatasets fails, the dataset Select, 'Add test input' row, and the Capture control all silently vanish (they're gated on `datasets.length > 0` / `activeDataset`), making the panel look like the user has no datasets; creating a 'replacement' dataset then collides with the invisible existing one. If listVersions fails, the baseline picker is empty and Regression dead-ends with the toast 'Pick a baseline version' that cannot be satisfied. Only the experiments history query (line 63) handles loading/empty.

**Fix:** Destructure `isError, refetch` on both queries and render a compact inline error row inside the Datasets / Run experiment sections ('Couldn't load datasets' / 'Couldn't load versions' + retry) when they fail.

### Design tokens & theming

#### Dead Tailwind v4 syntax across vendored shadcn primitives; tw-animate-css ships 54 raw @utility blocks
*`frontend/src/components/ui/popover.tsx:33`*

Several ui/ primitives were vendored from a Tailwind v4 shadcn registry and carry v4-only syntax that compiles to nothing under this v3 setup (verified with a compile probe against the real globals.css + config): `outline-hidden` (popover.tsx:33), `origin-(--radix-*-transform-origin)` (popover.tsx:33, tooltip.tsx:45), `data-open:`/`data-closed:` animation variants (popover.tsx:33, dialog.tsx:64, tooltip.tsx:45, sheet.tsx:65, select.tsx, dropdown-menu.tsx), and trailing-important `h-10!`/`rounded-md!`/`pl-2.5!` (command.tsx:74). Additionally `@import "tw-animate-css"` (globals.css:1) is a v4-only library: the probe build emits ZERO `.animate-in`/`fade-in-0`/`zoom-in-95`/`slide-in-*` utilities — even dialog's overlay, which uses correct v3 `data-[state=open]:animate-in` syntax, animates nothing — and passes 54 raw `@utility` at-rules through to the shipped CSS as dead bytes browsers ignore. Net effect: all overlay open/close transitions are silent no-ops and the command palette input sizing overrides don't apply.

**Fix:** Rewrite to v3 syntax: `outline-hidden`→`outline-none`, `data-open:`→`data-[state=open]:`, `h-10!`→`!h-10`, drop the `origin-(--…)` shorthand for `origin-[var(--…)]`; replace tw-animate-css with the v3 `tailwindcss-animate` plugin (add to tailwind.config plugins) or delete the animation classes outright.

#### Hardcoded white sheen (36 sites, 21 files) instead of the theme-flipping --surface-highlight token — light theme loses all card/input lift
*`frontend/src/components/ui/input.tsx:11`*

Nearly every ui/ primitive hardcodes the top-edge sheen as `shadow-[inset_0_1px_0_rgba(255,255,255,0.025–0.04)]` — 36 occurrences across 21 files: ui/input.tsx:11, textarea.tsx:10, select.tsx:47, badge.tsx:5, tabs.tsx:39, switch.tsx:20, filter-chip.tsx:17, alert.tsx:54, input-group.tsx:17, stat-card.tsx:24, dialog.tsx:109, sheet.tsx:92+102, command.tsx:73+74+177, dropdown-menu.tsx:203, form-field.tsx:42+50, layout/ShortcutsHelp.tsx:62, layout/CommandPalette.tsx:141, observability/TraceIdBadge.tsx:47, results/RunResultsPanel.tsx (8 sites), results/GuardrailEventsPanel.tsx:67+71, app/workflows/new/page.tsx:425+452+454 — plus the same pattern as `before:bg-white/10` in popover.tsx:33 and dialog.tsx:64. globals.css defines theme-aware tokens for exactly this (`--surface-highlight`: 0.035 white in dark → rgba(255,253,248,0.5) in light; `--surface-overlay-highlight` is defined in both themes and referenced NOWHERE). Newer canvas code already uses the token form (`shadow-[inset_0_1px_0_var(--surface-highlight)]` in RunDeck.tsx:605, WorkflowDataPanel.tsx:188, WorkflowQualityPanel.tsx:140, WorkflowCanvas.tsx:2103) — proven drift. In the warm-light theme, 3.5% white over #f1ede6 paper is invisible, so every input/select/badge/tab/dialog-footer silently loses the intended 50%-warm-white sheen.

**Fix:** Mechanical replace: `shadow-[inset_0_1px_0_rgba(255,255,255,0.035)]` (and the 0.025/0.03/0.04 variants) → `shadow-[inset_0_1px_0_var(--surface-highlight)]`; popover/dialog `before:bg-white/10` → `before:bg-[var(--surface-overlay-highlight)]`.

#### Decorative gradients on chrome (StatCard, AppRail) violate the flat-elevation rule
*`frontend/src/components/ui/stat-card.tsx:17`*

The design system explicitly bans decorative gradients ('Flat elevation... no decorative gradient lighting' — globals.css invariants; body even forces `background-image: none`). StatCard — a shared primitive rendered on the home page and all four observability dashboards — paints `bg-gradient-to-b from-surface-elevated to-surface`, and the primary nav rail does the same (AppRail.tsx:25: `border-r border-border bg-gradient-to-b from-surface-elevated to-surface`). These are the only two `bg-gradient-*` uses in the codebase; every comparable card (SectionCard, .panel, .dashboard-panel) is a flat token surface with the sanctioned ::before sheen, which StatCard already applies via its `surface-card` class — the gradient double-dips on top of it.

**Fix:** Replace `bg-gradient-to-b from-surface-elevated to-surface` with `bg-surface-elevated` in both stat-card.tsx:17 and AppRail.tsx:25; the existing `surface-card` sheen already supplies the lift.

#### Home page StatCard numerics render without font-mono/tabular-nums (drifted from every other dashboard)
*`frontend/src/components/home/HomeOverviewStrip.tsx:77`*

HomeOverviewStrip passes all four StatCard values — workflow count (line 77), run count (86), pass-rate percentage (112), and cost via formatCostUsd (137) — with no font-mono/tabular-nums wrapper, and neither StatCard's value element (stat-card.tsx:30, `text-[30px] font-semibold`) nor NumberTween applies it. Every other StatCard consumer got this right by hand-wrapping: OpsStatRow.tsx:106, TrustDashboard.tsx:80, CostDashboard.tsx:186 all use `<span className="font-mono tabular-nums">`. So the app's landing surface violates the 'ALL numerics use font-mono + tabular-nums' rule while duplicating the styling responsibility across four callers — classic primitive-level gap.

**Fix:** Add `font-mono tabular-nums` to StatCard's value element (stat-card.tsx:30) so the primitive owns numeric styling; the redundant per-caller wrappers in OpsStatRow/TrustDashboard/CostDashboard can then be dropped.

### Typography & numerics

#### AlertsCard timestamps bypass the app's date formatters — 'fired' badge shows time-of-day with no date
*`frontend/src/components/settings/AlertsCard.tsx:194`*

Every other surface (run-row.tsx:107-109, RunDetailView.tsx:432-441, VersionHistory.tsx:192-193, ExperimentsPanel.tsx:324-325, SessionsView, ViolationBreakdown) uses formatRelativeTime with formatFullTimestamp as a hover title. AlertsCard alone uses raw calls: line 194 renders `fired {new Date(rule.last_fired_at).toLocaleTimeString()}` inside a sans-serif Badge — a bare time of day ("3:42:11 PM") that becomes ambiguous/misleading once the rule last fired on a previous day — and line 256 renders alert-event times with raw new Date(...).toLocaleString(). Two more sites duplicate the raw pattern instead of the helpers: app/settings/page.tsx:353 (`{new Date(entry.at).toLocaleString()}` in the API-key audit log) and components/results/EvalTrendChart.tsx:41 (tooltip title).

**Fix:** Line 194: `fired {formatRelativeTime(rule.last_fired_at)}` and add title={formatFullTimestamp(rule.last_fired_at)} (Badge already supports title via span). Line 256, settings/page.tsx:353, EvalTrendChart.tsx:41: replace raw toLocaleString() with formatFullTimestamp()/formatRelativeTime() from lib/format-date.ts.

#### Eight ad-hoc duration formatters have drifted — same run-detail page mixes "1.2 s" and "1.2s"; observability tiles disagree on ms-vs-seconds
*`frontend/src/components/runs/TraceNodeRow.tsx:56`*

Duration/latency formatting is re-implemented in eight places and the outputs have diverged: TraceNodeRow.tsx:54-57 formatMs → "940 ms"/"1.2 s" (space before unit); RunDetailView.tsx:44-50 formatDuration → same spaced style; TraceTimeline.tsx:26-30 formatTick → "940ms"/"1.2s" (no space) — so on ONE run-detail page the axis ticks read "1.2s" while the row labels beside them read "1.2 s"; TrustDashboard.tsx:23-26 ms() → "940ms"/"1.2s" with toFixed(1); CostDashboard.tsx:61-64 formatLatency → "12,345ms" (never switches to seconds); OpsStatRow.tsx:75-77 → `${toLocaleString()}ms` (never seconds), so the observability Triage tab shows "Latency p50 12,345ms" while the adjacent Trust tab shows "12.3s" for the same magnitude; RunDeck.tsx:140-146 formatDuration → trailing-zero-trimmed "1.2s"; RunNodeResultCard.tsx:112 inline → toFixed(2) "0.94s". This is duplicated ad-hoc logic that has already drifted across sibling surfaces.

**Fix:** Add one formatDurationMs(ms) to src/lib/format.ts (canonical: "940ms" below 1s, "1.2s"/"12s" above, no space, toLocaleString for large ms) and replace all eight local implementations with it.

#### StatCard trend line renders numerics in sans-serif — violates mono+tabular rule on every dashboard tile
*`frontend/src/components/ui/stat-card.tsx:33`*

StatCard's trend renders as plain `text-xs text-muted` with no font-mono/tabular-nums, but nearly every call site passes numeric strings: TrustDashboard.tsx:84 `${trust.eval_passed}/${trust.eval_evaluated} evaluated`, :103 `${trust.guardrail_blocked_runs} blocked · ${g.warned} warned`, :112 `p95 ${ms(...)} · p50 ${ms(...)}`, :130 `${trust.failed_runs} failed of ...`; OpsStatRow.tsx:77 `p95 12,345ms`, :82 `1,234 runs scanned`, :146 `N blocked`; CostDashboard.tsx:187 `1,234 runs`, :197 `1,234 samples`; HomeOverviewStrip.tsx:78/100/129/139. The design system says ALL numerics (latency, counts, percentiles) use font-mono + tabular-nums; the values above these trends are mono, so the mixed rows visibly clash. Precedent for mono numeric-with-words lines already exists (TrustDashboard.tsx:145 uses `font-mono text-2xs tabular-nums` for "12 pass / 3 fail").

**Fix:** Change the trend paragraph in stat-card.tsx to `mt-1 font-mono text-2xs tabular-nums text-muted` (one-line fix that corrects every tile), matching the existing mono metadata rows in TrustDashboard/OpsStatRow.

#### Home overview stat values are sans-serif and ungrouped — drift from every other StatCard value in the app
*`frontend/src/components/home/HomeOverviewStrip.tsx:137`*

All observability StatCards wrap their value in `<span className="font-mono tabular-nums">` (CostDashboard.tsx:186, OpsStatRow.tsx:106/121/126, TrustDashboard.tsx:80-126). The home overview strip does not: line 137 passes the cost string bare (`value={costs ? formatCostUsd(costs.total_cost_usd) : DASH}`), and lines 77/86/112 pass <NumberTween> with no mono className — NumberTween.tsx:48-52 renders a plain span. So the home page shows dollar amounts and run counts in the sans display face while /observability shows the identical metrics in mono. Additionally NumberTween.tsx:50 uses `display.toFixed(precision)`, so a large run_count renders as "12345" on home while OpsStatRow.tsx:90 renders the same summary.run_count as "12,345" via toLocaleString.

**Fix:** Wrap all four HomeOverviewStrip values in <span className="font-mono tabular-nums"> (or pass className="font-mono tabular-nums" to NumberTween), and change NumberTween's render to display.toLocaleString(undefined, { minimumFractionDigits: precision, maximumFractionDigits: precision }) so tweened counts keep thousands grouping.

## P2 — Polish (29)

| Finding | Where | Fix |
|---|---|---|
| NodePalette category filter pills expose active state visually only (no aria-pressed) | `frontend/src/components/canvas/NodePalette.tsx:115` | Add aria-pressed={activeCat === "all"} / aria-pressed={activeCat === c} to the pill buttons (and wrap the row in role="group" aria-label="Filter nodes by category"), or reuse FilterChip. |
| EvalRubricCard 'Score sample' async result appears without aria-live announcement | `frontend/src/components/settings/EvalRubricCard.tsx:308` | Wrap the preview/RAG result area in a container with aria-live="polite" (matching VerdictPanel.tsx:41), so scores, skip messages, and errors are announced when they land. |
| Invented h-7 Button size repeated in 5 places despite existing xs (h-6) and sm (h-8) variants | `frontend/src/components/guardrails/PolicyTemplates.tsx:117` | Standardize these row-action buttons on size="xs" (or size="sm" unmodified); if h-7 is genuinely needed, add it once as a real size variant in ui/button.tsx and drop the className overrides. |
| Select size="sm" variant exists but is bypassed with className h-8 text-xs; Input has no small variant so the same override is scattered | `frontend/src/components/canvas/ExperimentsPanel.tsx:225` | Use size="sm" on the two ExperimentsPanel SelectTriggers (keep only layout classes like flex-1), and add a size="sm" (h-8 text-xs) variant to ui/input.tsx, then replace the seven h-8 className overrides with it. |
| Sibling settings cards render their empty state two different ways: bare paragraph vs EmptyState primitive | `frontend/src/components/settings/EvalRubricCard.tsx:155` | Replace the paragraph with <EmptyState compact icon={Pencil} title="No custom rubrics yet" description="Create one below — rubrics plug into evaluation nodes." /> to match AlertsCard and SavedPolicies. |
| Hover-revealed destructive delete icon-button duplicated verbatim in two files, with a third drifted variant in AlertsCard | `frontend/src/components/guardrails/SavedPolicies.tsx:183` | Extract one shared row-delete control (e.g. <Button variant="ghost" size="icon-xs" className="hover:text-destructive"> wrapped in a RowDeleteButton with the hover-reveal classes) and use it in SavedPolicies, EvalRubricCard, and AlertsCard so visibility and sizing match. |
| Same guardrail engine has three different display names across Playground, canvas inspector, and Trust drill-down | `frontend/src/components/guardrails/GuardrailPlayground.tsx:233` | Create one shared label map (e.g. `GUARDRAIL_TYPE_LABELS` in src/lib) with a single name per type ('Keyword rules', 'PII scan', 'Prompt injection', 'Moderation', 'LLM classifier', 'Structured output') and use it in GuardrailPlayground's select + guardrailTypeLabel, ViolationBreakdown.typeLabel, and the NodeInspector engine select (keeping inspector parentheticals as suffixes). |
| "Run a workflow" CTAs on Observability navigate to the create-workflow page, not a run action | `frontend/src/app/observability/page.tsx:508` | Either relabel to match the destination ('Create a workflow') or point the CTA at "/" (workflows home) with label 'Open a workflow to run it'. Apply the same to the CostDashboard props at line 516. |
| Settings 'No credentials yet.' / 'No custom rubrics yet.' empty states are bare paragraphs with no fix-it guidance, unlike sibling sections | `frontend/src/app/settings/page.tsx:371` | Replace both paragraphs with `<EmptyState compact icon={…} title="No credentials yet" description="Add one below — Slack, Discord, Email, and Postgres nodes reference credentials by name." />` (and the rubric equivalent pointing at the 'New rubric' form below). |
| Workflow guardrail policy picker is a dead end when the user has no saved policies | `frontend/src/components/canvas/WorkflowGuardrailField.tsx:86` | When `policies.length === 0`, change the hint to 'No saved policies yet — adopt one on the Guardrails page.' and link the phrase to /guardrails (Next Link with focus-ring). |
| Alert rule builder uses lowercase placeholders as the only visible labels ('threshold', 'window (min)') | `frontend/src/components/settings/AlertsCard.tsx:120` | Give the three fields visible Labels (Label component above each, matching the rest of settings) or at minimum sentence-case the placeholders to real hints ('Threshold, e.g. 0.5'); keep the aria-labels. |
| Capitalization drift: lowercase 'cancel edit' action and Title-Case 'Eval & Safety' category vs sentence-case chrome | `frontend/src/components/settings/EvalRubricCard.tsx:204` | Change 'cancel edit' → 'Cancel edit' and NODE_CATEGORIES quality label 'Eval & Safety' → 'Eval & safety'. |
| RunDeck body is lg:overflow-hidden with no per-section scroll — trace rows and the 'Review approval' control can be clipped unreachable at short viewports | `frontend/src/components/canvas/run/RunDeck.tsx:611` | Add `lg:overflow-y-auto` to each of the three body <section>s (they already have min-h-0), or keep the outer overflow-y-auto at lg instead of overflow-hidden. |
| Five StatCard tiles in grid-cols-2/sm:grid-cols-3 leave an orphan tile and empty cells at every width below lg | `frontend/src/components/observability/TrustDashboard.tsx:76` | Give the fifth card `className="col-span-2 sm:col-span-1"` (StatCard already forwards className) so it fills the base 2-col row, and reorder/span so the sm row is 3+2 with the wide tile last — or use `grid-cols-2 lg:grid-cols-5` only. |
| divide-x on the wrapping run-stat grid paints stray left borders on wrapped rows below lg | `frontend/src/components/runs/RunDetailView.tsx:392` | Replace divide-x with the gap-hairline technique: `grid grid-cols-2 gap-px bg-border sm:grid-cols-3 lg:grid-cols-6` with `bg-surface` on each cell — correct 1px rules in both axes at every breakpoint (apply to the skeleton too). |
| CostBreakdownTable name-cell truncate is inert in an auto-layout table — long names force whole-table horizontal scroll instead | `frontend/src/components/observability/CostBreakdownTable.tsx:132` | Make the name column absorb slack so truncate works: add `w-full max-w-0` to the name <td>/<th> (or set `table-fixed` on the table with explicit widths for the numeric columns). |
| AlertsCard comparison-row hint is squeezed into one column of a 5-col grid while 2 columns sit empty | `frontend/src/components/settings/AlertsCard.tsx:152` | Span the remaining columns: `cn("self-center text-2xs text-subtle", comparison === "baseline" ? "sm:col-span-1" : "sm:col-span-3")` — or move the hint out of the grid onto its own full-width form-hint line. |
| TraceTimeline axis tick labels are distributed with justify-between and drift off the percent-positioned gridlines | `frontend/src/components/runs/TraceTimeline.tsx:122` | Position each tick absolutely on the same axis geometry: wrap in a `relative h-4` div and give each label `absolute -translate-x-1/2` with `left: (i/GRID_STEPS)*100%` (first/last anchored with translate-x-0/-translate-x-full). |
| /workflows renders the identical page as / (duplicate route, two URLs for one surface) | `frontend/src/app/workflows/page.tsx` | Make /workflows a redirect to / (or vice versa) so one canonical URL exists. |
| Trace rows print the node duration twice (header right + bar right) | `frontend/src/components/runs/TraceNodeRow.tsx:116` | Drop the header duration (keep status badge there) and let the bar-right value be the single duration; or keep header-only and drop the bar label. |
| Saved json_schema policy loads into the playground whose Type select has no such option | `frontend/src/components/guardrails/SavedPolicies.tsx:31` | Either filter json_schema policies out of the playground's Load coercion (fall back to 'rules' with a toast explaining schema policies are tested on the canvas), or add the select item + a read-only notice. |
| Node palette category chips clip at the panel edge with no scroll affordance | `frontend/src/components/canvas/NodePalette.tsx` | Add a fade-out mask + horizontal scroll affordance (or wrap chips to two rows). |
| Trust view has no zero-telemetry empty state — renders 'last 0 runs' and dash tiles | `frontend/src/components/observability/TrustDashboard.tsx:71` | After the load guard, early-return an `EmptyState` (icon ShieldCheck, 'Run a workflow to start building trust metrics', CTA to /workflows/new) when `trust.runs_scanned === 0 && trust.guardrail_events.total === 0`. |
| RecentActivityRail asserts 'No runs yet' when the summary query fails | `frontend/src/components/home/RecentActivityRail.tsx:29` | Read `isError` and swap the EmptyState for a one-line muted 'Couldn't load recent activity' message (no CTA) when the query errored. |
| Canvas reference-data loads swallow errors with empty catch — pickers silently render empty | `frontend/src/components/canvas/NodeInspector.tsx:1100` | Track a `referenceLoadError` flag set in those catch handlers and render a small `form-hint text-destructive` line near the affected pickers ('Couldn't load credentials/presets — reopen the inspector to retry'); in WorkflowGuardrailField read `isError` from the query and show the same hint under the select. |
| Destructive Button uses raw `text-white` instead of a foreground token | `frontend/src/components/ui/button.tsx:21` | Add `--destructive-foreground` (e.g. #fbf8f3 warm white) to both theme blocks in globals.css, expose it as `destructive.foreground` in tailwind.config.ts, and use `text-destructive-foreground`. |
| Category hue used as fills, colored text, and >2px bars — beyond the '<=2px rule, never fills' contract | `frontend/src/components/canvas/NodeInspector.tsx:1195` | Normalize category rules to `w-0.5` (2px) in NodeInspector:1188 and workflows/new:265; make the inspector/palette icon chips monochrome (`bg-surface-input text-muted`) keeping hue only on the 2px left rule; set the category label text at NodeInspector:1203 to `text-muted`; shrink or de-saturate the TraceNodeRow dot (e.g. 2px ring in catColor instead of solid fill). |
| Token counts formatted four different ways; trace drill-down counts lack thousands grouping | `frontend/src/components/runs/TraceNodeRow.tsx:316` | At minimum apply .toLocaleString() at TraceNodeRow.tsx:316 and :390. Preferably move a single formatTokens() into src/lib/format.ts (pick one abbreviation casing) and reuse it in CostDashboard, BaseNode, TrustDashboard, and RunDeck. |
| Micro-eyebrow label role exists at three competing sizes (.text-micro 11px vs ad-hoc 10px vs 12px), diverging even within one component | `frontend/src/components/canvas/NodeInspector.tsx:104` | Standardize the role on the existing .text-micro utility (add a text-subtle color override where needed): replace the ad-hoc `text-2xs/text-xs font-medium uppercase tracking-wider` stacks with `text-micro`, starting with the intra-file conflict at NodeInspector.tsx:104 vs :126 and the recently added guardrail/settings components. |

## Verification & provenance

- Code-audit findings each carry an adversarial-verification verdict (the skeptic re-read the cited file plus mitigating context — theme CSS, parents, siblings — before confirming; severities above are the *verifier's*, which in several cases corrected the finder). Full machine-readable findings, including verifier notes and code evidence, in `docs/ui-ux-audit-2026-07-25.findings.json`.
- Live findings are marked by the **Live-app behavior** section headers / 'Observed live' phrasing and were captured against the dev servers on 2026-07-25 (dark + warm-light, 1474–1542 px viewports). Three were root-caused via API probes (pass-rate verdict counts, SSE stream behavior, `toLocaleString` call site).
- Independent cross-confirmation: the live pass and the code audit each independently surfaced the 'Next runs (UTC)' bug, the stale observability header, the unpersisted view toggle, and the eval-presets naming drift.

## Suggested attack order

1. The three P0s (focus ring, eval-chip scale, UTC label) — small diffs, outsized correctness/a11y impact.
2. The error-state sweep — one shared pattern (error → inline retry row; never a healthy empty) applied across the 13 state findings.
3. The consolidation quartet: one status-tone map, one ms/duration formatter, one guardrail-type label map, one shared Chip — deletes most of the drift class.
4. Observability coherence: harmonized/labeled windows, view-aware header, URL-persisted view.
5. Everything else per table.
