# Graph Report - .  (2026-08-07)

## Corpus Check
- 454 files · ~450,120 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 3281 nodes · 8679 edges · 194 communities (147 shown, 47 thin omitted)
- Extraction: 98% EXTRACTED · 2% INFERRED · 0% AMBIGUOUS · INFERRED: 153 edges (avg confidence: 0.65)
- Token cost: 67,119 input · 3,982 output

## Community Hubs (Navigation)
- Canvas Chrome
- App Routes
- Node Inspector UI
- Observability API
- Evals & Embeddings
- Runs API
- Run Detail UI
- Settings UI
- Integrations
- Guardrails & Templates UI
- Credential Encryption
- Canvas Clipboard
- Workflow Compiler
- Root Layout
- DB Models
- Node Data Panel
- App Shell
- Observability UI
- Node Palette
- AI Assist Service
- Meta Ops API
- Loading & Panels
- Platform API
- Run Executor
- Guardrail Plugin
- AI Assist Service · assist
- Workflows API
- Eval Presets API
- Run Event Broker
- Auth Dependencies
- Human Approval
- Guardrail Enforcement
- Base Node UI
- Guardrails UI Components
- Group Node UI
- Datasets API
- Node Test Service
- Run Authoring
- Startup Gate
- Guardrail Policies API
- Tsconfig
- Workflow Compiler (2)
- Node Handlers
- Workflow
- Job Queue
- Loading & Panels · CanvasSidebar
- Feedback API
- Alerts
- Node Registry
- AI Assist Service · __init__
- Tracing
- Experiments API
- Eval Presets API · templates
- Tests
- Tests · test_assist_mvp2
- Eval Runner
- Components
- Run Authoring · CanvasTour
- Guardrail Enforcement · guardrail_presidio
- Alerts · observability_events
- Tests · test_node_test_api
- Run Authoring · expressions
- Graph Validation
- App Config
- AI Assist Service · test_assist
- Model Ref
- Package
- Canvas UI
- Alerts · alerts
- Node Data Panel · node_test
- App Config · config
- Tests · guardrail
- Worker Process
- Tests · test_api
- Tests · test_error_routing
- API Entrypoint
- Eval Preset Service
- Guardrail Plugin · token_tracker
- Package (2)
- Tests · test_structured_output_guardrail
- Alerts · quality_alerts
- Trace Plugin
- Run Authoring (4)
- Tests · workflow_context
- Tests · templates
- Run Authoring (5)
- Tests · workflow_import
- Tests · test_mvp2_foundation
- Tests (12)
- Code Sandbox
- Package (3)
- Knowledge
- Experiment Runner
- Tests · test_moderation_guardrail
- Tests · search
- Guardrails UI
- Workflow Compiler · test_compiler
- Tests · test_integrations_email
- Tests · test_experiment_gate
- AI Assist Service (5)
- DB Models · context_wrapper
- Canvas UI · useRunInput
- Tests · test_routing_adk2
- Canvas UI · CanvasContextMenu
- Workflow-Import UI
- Migrations
- Migrations · 013_alert_baseline_comparison
- Kb Cache
- Tests · test_phase8
- Tests · test_dataset_capture
- Ui-Audit-Issues
- Upgrade Plan
- 2026-07-01-Ui-Overhaul
- 13-Continue-Build-Run
- Frontend-Design-Audit
- Tests · test_workflows_eval
- Memory
- Isses
- Migrations · 009_agentops_tables_backfill
- Migrations · 011_workflow_templates
- Tests (21)
- .Eslintrc
- Package (4)
- Tailwind.Config UI
- 18-Publish-Lifecycle
- 16-Quality-Loop
- Migrations (12)
- Roadmap
- Upgrade Plan (2)
- Migrations (13)
- Next.Config
- 02-Guardrails
- Agentops Plan
- Package (5)
- Claude
- Audit-2026-08-07
- Roadmap (2)
- Roadmap (3)
- 2026-06-29-Aegis-Phase-2-Plan
- 2026-07-01-Ui-Overhaul (2)
- Package (6)
- Package (7)
- Package (8)
- Package (9)
- Package (10)
- Package (11)
- Postcss.Config
- Vercel
- Issues
- Issues (2)
- Aegis-Header
- 19-Run-Desk
- 21-Schedule-Board
- 22-Experiments-Variants
- 01B-Observability-Investigate
- 01C-Observability-Triage
- 01D-Observability-By-Workflow
- Settings UI (2)
- 2026-06-29-Aegis-Phase-2-Plan (2)
- 2026-06-29-Aegis-Mvp1-Design
- 2026-07-01-Ui-Overhaul-Design
- Ui-Ux-Audit-2026-07-25
- Ui-Ux-Audit-2026-07-25 (2)
- Ui-Ux-Audit-2026-07-25 (3)
- Ui-Ux-Audit-2026-07-25 (4)
- Ui-Ux-Audit-2026-07-25 (5)
- 06-Workflow-Builder
- 07-Workflow-Builder-Mobile
- 05-Workflow-Builder-Tour
- 04-Guardrail-Result
- Issues (3)
- Issues (4)
- Depth-Style
- Audit-Report
- Upgrade Plan (3)
- Upgrade Plan (4)

## God Nodes (most connected - your core abstractions)
1. `cn()` - 205 edges
2. `valid_graph()` - 62 edges
3. `compile_workflow()` - 50 edges
4. `Button` - 49 edges
5. `validate_workflow_graph()` - 45 edges
6. `api` - 45 edges
7. `WorkflowCanvasInner()` - 43 edges
8. `_build_adk_node()` - 37 edges
9. `render_template()` - 33 edges
10. `Base` - 29 edges

## Surprising Connections (you probably didn't know these)
- `Workflow compilation to ADK Workflow` --references--> `compile_workflow()`  [EXTRACTED]
  docs/architecture.md → backend/app/services/compiler.py
- `North star loop Build to Run to Trust` --semantically_similar_to--> `Closed-loop agent lifecycle (Author to Ship)`  [INFERRED] [semantically similar]
  agentops_plan.md → README.md
- `Chroma-reserved design language (warm near-black, bone, monochrome)` --semantically_similar_to--> `Obsidian + Oxide Copper palette (Canvas Run Lens)`  [INFERRED] [semantically similar]
  README.md → design-qa.md
- `Evaluation rigor: online evals + CI gates (P1.2)` --semantically_similar_to--> `Deterministic evaluators (exact/substring, regex, embedding similarity)`  [INFERRED] [semantically similar]
  docs/ROADMAP.md → upgrade_plan.md
- `Evaluation suite (faithfulness/helpfulness/relevance/toxicity, 1-5)` --semantically_similar_to--> `Deterministic evaluators (exact/substring, regex, embedding similarity)`  [INFERRED] [semantically similar]
  docs/superpowers/plans/2026-06-29-aegis-phase-2-plan.md → upgrade_plan.md

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Aegis run pipeline (validate to compile to execute on ADK)** — claude_run_pipeline, claude_graph_validation, claude_compiler, claude_executor, readme_adk [EXTRACTED 1.00]
- **AgentOps platform roadmap phases** — agentops_plan_phase1, agentops_plan_phase2, agentops_plan_phase3, agentops_plan_phase4, agentops_plan_phase5 [EXTRACTED 1.00]
- **Aegis roadmap priority feature gaps** — docs_roadmap_multi_model_support, docs_roadmap_bidirectional_mcp, docs_roadmap_rag_depth, docs_roadmap_eval_rigor, docs_roadmap_durable_execution [EXTRACTED 1.00]
- **Glass & glow UI overhaul system** — docs_superpowers_specs_2026_07_01_ui_overhaul_design_glass_and_glow, docs_superpowers_specs_2026_07_01_ui_overhaul_design_design_tokens, docs_superpowers_specs_2026_07_01_ui_overhaul_design_shadcn_migration, docs_superpowers_specs_2026_07_01_ui_overhaul_design_canvas_reskin, docs_superpowers_plans_2026_07_01_ui_overhaul_motion_primitives [EXTRACTED 1.00]
- **Three P0 audit findings (broken/misleading/inaccessible)** — docs_ui_ux_audit_2026_07_25_dead_focus_ring, docs_ui_ux_audit_2026_07_25_eval_chroma_bug, docs_ui_ux_audit_2026_07_25_utc_timezone_bug [EXTRACTED 1.00]
- **Server-side untrusted-input execution/exfiltration cluster** — isses_code_sandbox_breakout, isses_dns_rebinding_ssrf, isses_postgres_ssrf [INFERRED 0.75]
- **Aegis 2026 Audit Cycle** — audit_frontend_design_2026_07_20_frontend_design_audit, ui_audit_investigation, deep_audit_2026_08_07 [EXTRACTED 0.90]
- **Frontend Visual Evidence Collection** — img_workflow_home, img_observability, img_guardrails, img_guardrail_result, img_builder_tour, img_builder_desktop, img_builder_mobile [EXTRACTED 1.00]
- **Aegis UI Design System** — docs_design_homepage_mockups_13_continue_build_run, docs_design_homepage_mockups_14_open_or_run, docs_design_homepage_mockups_15_structure_index, docs_design_homepage_mockups_16_quality_loop, docs_design_homepage_mockups_17_start_from_pattern, docs_design_homepage_mockups_18_publish_lifecycle, docs_design_homepage_mockups_19_run_desk, docs_design_homepage_mockups_20_modules_and_agents, docs_design_homepage_mockups_21_schedule_board, docs_design_homepage_mockups_22_experiments_variants, docs_design_page_mockups_01_observability, docs_design_page_mockups_01b_observability_investigate, docs_design_page_mockups_01c_observability_triage, docs_design_page_mockups_01d_observability_by_workflow, docs_design_page_mockups_02_guardrails, docs_design_page_mockups_03_settings [EXTRACTED 0.90]

## Communities (194 total, 47 thin omitted)

### Community 0 - "Canvas Chrome"
Cohesion: 0.04
Nodes (84): CANVAS_RAIL_ITEMS, CanvasRail(), CanvasRailItem, CanvasRailProps, CanvasRailTab, CanvasStatusBar(), TONE_CLASSES, CanvasToolbar() (+76 more)

### Community 1 - "App Routes"
Cohesion: 0.05
Nodes (66): HomePage(), WorkflowCanvas, ErrorBoundaryProps, ErrorBoundaryState, HomeOverviewStrip(), EMPTY_HINTS, LifecycleColumn(), PublishLifecycleBoard() (+58 more)

### Community 2 - "Node Inspector UI"
Cohesion: 0.03
Nodes (74): ExpressionTextarea, ExpressionTextareaProps, Segment, NodeLiveResult, argBest(), buildCompareConfig(), charDiff(), CommentsSection() (+66 more)

### Community 3 - "Observability API"
Cohesion: 0.06
Nodes (76): observability_costs(), observability_dashboards(), observability_errors(), observability_overview(), observability_quality(), observability_runs(), observability_summary(), observability_trust() (+68 more)

### Community 4 - "Evals & Embeddings"
Cohesion: 0.06
Nodes (67): cosine_similarity_vectors(), embed_text(), _hashing_vector(), Any, Text embeddings for vector RAG (Gemini with TF-IDF fallback)., retrieve_by_embedding(), evaluate_embedding_similarity(), evaluate_exact() (+59 more)

### Community 5 - "Runs API"
Cohesion: 0.06
Nodes (68): approve_run(), _as_utc(), create_run(), export_run(), get_run(), get_run_llm_calls(), get_run_timeline(), get_run_trace() (+60 more)

### Community 6 - "Run Detail UI"
Cohesion: 0.08
Nodes (51): RunDeckProps, SessionRuns(), StatusMix(), TraceIdBadge(), EvalScoresChart(), EvalScoresChartProps, formatDelta(), radarPoints() (+43 more)

### Community 7 - "Settings UI"
Cohesion: 0.08
Nodes (48): CONFIG_HINTS, REQUIRED_CREDENTIAL_FIELDS, EdgeInspectorProps, ExperimentsPanel(), ExperimentsPanelProps, verdictBadge(), PanelSection(), RunControlProps (+40 more)

### Community 8 - "Integrations"
Cohesion: 0.07
Nodes (52): get_http_client(), _parameterize_query(), _pg_engine(), _post_integration_webhook(), Any, Integration node handlers — Slack, Email, Postgres (n8n-style)., run_discord_integration(), run_postgres_integration() (+44 more)

### Community 9 - "Guardrails & Templates UI"
Cohesion: 0.06
Nodes (47): CapabilityBadges(), complexityLabel(), FILTER_IDS, FILTER_OPTIONS, previewLayout(), TemplateCardProps, TemplateFilter, templateFlags() (+39 more)

### Community 10 - "Credential Encryption"
Cohesion: 0.06
Nodes (53): _coerce_config(), downgrade(), Encrypt existing plaintext credential secret values at rest (Fernet).…, config may come back as dict (PG JSONB) or str (SQLite JSON)., _rewrite(), _secret_keys(), upgrade(), create_credential() (+45 more)

### Community 11 - "Canvas Clipboard"
Cohesion: 0.07
Nodes (52): ClipboardStore, copyToClipboard(), duplicateFragment(), hasClipboard(), materialize(), materializeClipboard(), materializeFragmentAt(), nextNodeIndex() (+44 more)

### Community 12 - "Workflow Compiler"
Cohesion: 0.09
Nodes (55): AdkEdge, AST, _branch_default_label(), _build_adk_node(), _build_author_lookup(), _build_bound_workflow(), _build_graph_edges(), compile_workflow() (+47 more)

### Community 13 - "Root Layout"
Cohesion: 0.06
Nodes (45): metadata, plexMono, plexSans, Toaster, viewport, SettingsPage(), AppRail(), AppRailProps (+37 more)

### Community 14 - "DB Models"
Cohesion: 0.07
Nodes (43): Base, AlertEvent, AuditLog, Credential, Experiment, Feedback, JSONType, LlmCall (+35 more)

### Community 15 - "Node Data Panel"
Cohesion: 0.09
Nodes (44): ExpressionPreview(), hasBoundContext(), allUpstream(), directPredecessors(), NodeDataSection(), NodeEvidence, oneLine(), OutputBlock() (+36 more)

### Community 16 - "App Shell"
Cohesion: 0.06
Nodes (39): WorkflowPage(), HeaderActions(), ErrorBoundary, AppShell(), Action, ADD_NODE_EVENT, CommandPalette(), emitAddNode() (+31 more)

### Community 17 - "Observability UI"
Cohesion: 0.08
Nodes (36): AttentionItem, buildAttentionItems(), KIND_STATUS, kindClass(), kindLabel(), ObservabilityPage(), ObservabilitySummary, ObservabilityView (+28 more)

### Community 18 - "Node Palette"
Cohesion: 0.07
Nodes (39): ALL_CATS, DRAG_TYPE, NodePalette(), NodePaletteProps, CATEGORY_LABEL, NodeCategory, GraphContext, QuickAddMenu() (+31 more)

### Community 19 - "AI Assist Service"
Cohesion: 0.09
Nodes (40): AssistHistoryTurn, EdgeRef, GraphDiff, NodeSuggestion, _assign_positions(), AssistError, _capped_history(), _compute_graph_diff() (+32 more)

### Community 20 - "Meta Ops API"
Cohesion: 0.11
Nodes (32): list_node_types(), ops_config(), preview_cron(), preview_guardrail(), get, post, Read-only operational knobs (env-driven) for the Settings page., tracing_config() (+24 more)

### Community 21 - "Loading & Panels"
Cohesion: 0.08
Nodes (27): PanelStat(), PanelStatGrid(), STAT_TONES, WorkflowDataPanel(), WorkflowDataPanelProps, WorkflowQualityPanelProps, EvalTrendChart(), EvalTrendChartProps (+19 more)

### Community 22 - "Platform API"
Cohesion: 0.11
Nodes (34): get_deploy_descriptor(), get_published(), ingest_run(), IngestNodeEvent, IngestRunPayload, invoke_workflow(), InvokePayload, list_audit() (+26 more)

### Community 23 - "Run Executor"
Cohesion: 0.11
Nodes (36): configure_runtime_env(), Unset IDE-local Gemini proxy vars that break direct API calls., log_context(), _as_utc(), _commit_db(), _consume_with_timeout(), _ensure_api_key(), execute_run() (+28 more)

### Community 24 - "Guardrail Plugin"
Cohesion: 0.11
Nodes (30): _contents_to_text(), _decode_str_response(), _expects_json(), GuardrailPolicyPlugin, Any, BasePlugin, LlmResponse, Workflow-level guardrail policy enforced through ADK plugin callbacks. A per-… (+22 more)

### Community 25 - "AI Assist Service · assist"
Cohesion: 0.15
Nodes (34): compare(), edit_graph(), explain_run(), generate_schema(), generate_workflow(), _get_user_run(), EditGraphResponse, GenerateSchemaResponse (+26 more)

### Community 26 - "Workflows API"
Cohesion: 0.17
Nodes (36): batch_eval_snippets(), bulk_import_knowledge(), compare_runs(), delete_knowledge_document(), delete_workflow(), delete_workflow_memory(), duplicate_workflow(), eval_history() (+28 more)

### Community 27 - "Eval Presets API"
Cohesion: 0.12
Nodes (27): _as_list_item(), create_eval_preset(), delete_eval_preset(), list_eval_presets(), preview_eval_preset(), delete, get, patch (+19 more)

### Community 28 - "Run Event Broker"
Cohesion: 0.15
Nodes (27): _enqueue_event(), _extract_text_from_event(), _extract_text_parts(), _extract_token_usage(), _normalize_text_part(), _put_run_event(), Any, Queue (+19 more)

### Community 29 - "Auth Dependencies"
Cohesion: 0.11
Nodes (22): alias, _api_key_user_map(), get_current_user_id(), Query, UUID, Map api key -> (user_id, role). Values may be a bare uuid string or {"user_id":…, _resolve_api_token(), role_from_api_key() (+14 more)

### Community 30 - "Human Approval"
Cohesion: 0.13
Nodes (25): clear_approval_state(), HumanApprovalTimeout, Any, Exception, Human-in-the-loop approval for paused workflow runs (Lyzr SuperFlow)., submit_approval(), wait_for_approval(), _execute_code() (+17 more)

### Community 31 - "Guardrail Enforcement"
Cohesion: 0.12
Nodes (25): apply_fail_behavior(), GuardrailBlockedError, Any, Exception, Parse a length bound; None (or unparseable) means the bound is unset., LLM cleanup pass: remove the violating material, keep the substance., redact_pii(), _rewrite_content() (+17 more)

### Community 32 - "Base Node UI"
Cohesion: 0.13
Nodes (19): BaseNode, BORDER_BY_STATE, ExtendedNodeData, formatTokens(), NodeChip(), NodeChipRow(), NodeRuntimeState, NodeTelemetry (+11 more)

### Community 33 - "Guardrails UI Components"
Cohesion: 0.14
Nodes (24): policyPresets, PolicyTemplates(), PolicyTemplatesProps, ruleSummary(), toConfig(), configFromRules(), GUARDRAIL_TYPES, PLAYGROUND_GUARDRAIL_TYPES (+16 more)

### Community 34 - "Group Node UI"
Cohesion: 0.13
Nodes (19): FrameData, GroupNode, StatusDot(), registry, StaggerRecord, useEntryStagger(), HoverLift(), Props (+11 more)

### Community 35 - "Datasets API"
Cohesion: 0.20
Nodes (27): add_item(), add_run_input(), capture_runs(), create_dataset(), DatasetCapture, DatasetCreate, DatasetImport, DatasetItemCreate (+19 more)

### Community 36 - "Node Test Service"
Cohesion: 0.16
Nodes (27): _build_test_context(), _cap_rendered(), _execute_node(), _format_result(), _gemini_text(), get_user_workflow(), _last_node_output(), latest_graph() (+19 more)

### Community 37 - "Run Authoring"
Cohesion: 0.13
Nodes (26): _ancestors(), _node_data(), _node_type(), prune_graph_for_start(), Any, ValueError, Authoring-only run helpers: pin outputs + run-from-here. These features let the…, Raised when pin/run-from-here parameters are invalid for the graph. (+18 more)

### Community 38 - "Startup Gate"
Cohesion: 0.12
Nodes (24): _alembic_head_revisions(), check_migrations_current(), _current_db_revisions(), MigrationsBehindError, Mark orphaned running jobs as failed after a crash or deploy., Raised when the database is behind the latest Alembic revision., Resolve the current Alembic head revision(s) from alembic/versions., Compare the DB's Alembic revision to head; log loudly / refuse to boot if… (+16 more)

### Community 39 - "Guardrail Policies API"
Cohesion: 0.15
Nodes (25): create_policy(), delete_policy(), enrich_graph_guardrail_policies(), _get_policy(), list_policies(), list_templates(), PolicyCreate, PolicyUpdate (+17 more)

### Community 40 - "Tsconfig"
Cohesion: 0.07
Nodes (26): compilerOptions, allowJs, esModuleInterop, incremental, isolatedModules, jsx, lib, module (+18 more)

### Community 41 - "Workflow Compiler (2)"
Cohesion: 0.09
Nodes (26): LLM-call traces (llm_calls table, gen_ai.* spans), North star loop Build to Run to Trust, Phase 1 Truthful runtime, Phase 2 Evals that catch regressions, Phase 4 Observability you can operate on, Phase 5 Platform (harness for any agent), Version regression gate (candidate vs current on dataset), Token and cost accounting via ADK plugin (+18 more)

### Community 42 - "Node Handlers"
Cohesion: 0.14
Nodes (24): HumanApprovalDenied, _coerce_item_output(), _ensure_memory_bucket(), _load_workflow_kb_documents(), _make_code_fn(), _make_delay_fn(), _make_filter_fn(), _make_human_approval_fn() (+16 more)

### Community 43 - "Workflow"
Cohesion: 0.19
Nodes (23): create_workflow(), import_workflow(), patch, Workflow, Create a new workflow from an aegis-workflow-v1 export JSON., update_workflow(), GuardrailPreviewRequest, GuardrailPreviewResponse (+15 more)

### Community 44 - "Job Queue"
Cohesion: 0.19
Nodes (22): BackgroundJob, create_job(), dispatch_job(), get_job(), mark_job_completed(), mark_job_failed(), mark_job_running(), Any (+14 more)

### Community 45 - "Loading & Panels · CanvasSidebar"
Cohesion: 0.12
Nodes (22): CanvasSidebar(), CanvasSidebarProps, RunComparison, SidebarTab, TabPanelFade(), tabs, VersionHistory, WorkflowDataPanel (+14 more)

### Community 46 - "Feedback API"
Cohesion: 0.11
Nodes (19): create_feedback(), FeedbackCreate, list_run_feedback(), BaseModel, get, post, Session, UUID (+11 more)

### Community 47 - "Alerts"
Cohesion: 0.19
Nodes (22): AlertRule, Threshold rule evaluated by the scheduler tick., _breached(), evaluate_alert_rules(), _metric_over_window(), _metric_value(), _percentile(), AlertRule (+14 more)

### Community 48 - "Node Registry"
Cohesion: 0.23
Nodes (21): get_node_meta(), NodeTypeMeta, Canonical node type metadata for the agentic workflow builder., _ctx(), _iter_fn(), Tests for the iteration node (map-over-list, Dify-style single-node loop). The…, _run(), test_iteration_empty_items_yields_empty_array() (+13 more)

### Community 49 - "AI Assist Service · __init__"
Cohesion: 0.20
Nodes (21): AssistHistoryTurn, One prior turn of a copilot thread. ``role`` is ``"user"`` (a past instruction)…, SuggestionsDraft, _current_graph(), _last_prompt(), _mock_response(), patch, Tests for threaded copilot history on the edit-graph / suggest-nodes assist… (+13 more)

### Community 50 - "Tracing"
Cohesion: 0.14
Nodes (17): get_trace_id(), init_tracing(), install_http_middleware(), NodeSpanTracker, _parse_headers(), Any, OpenTelemetry tracing for workflow execution and HTTP requests., Tracks in-flight ADK node spans for a single workflow run. (+9 more)

### Community 51 - "Experiments API"
Cohesion: 0.19
Nodes (20): _check_version(), create_experiment(), experiment_gate(), ExperimentCreate, get_experiment(), list_experiments(), BaseModel, get (+12 more)

### Community 52 - "Eval Presets API · templates"
Cohesion: 0.19
Nodes (20): _builtin_items(), create_template(), list_eval_presets(), list_templates(), _persisted_item(), get, post, Session (+12 more)

### Community 53 - "Tests"
Cohesion: 0.15
Nodes (19): GuardrailPolicy, Named, reusable guardrail rule bundle., check_workflow_budget(), Session, Workflow, Per-workflow budget enforcement: cost/day, runs/hour, tokens/run. Budgets live…, Return a breach reason, or None when the run may proceed., tokens_per_run_limit() (+11 more)

### Community 54 - "Tests · test_assist_mvp2"
Cohesion: 0.22
Nodes (21): _EditGraphDraft, _GeneratedSchemaDraft, GenNode, Gemini structured-output shape for edit-graph (mirrors GeneratedWorkflowDraft)., Gemini structured-output shape. schema_object_json is a JSON-encoded string…, A node as returned by Gemini structured output., _current_graph(), _edit_draft_add_guardrail() (+13 more)

### Community 55 - "Eval Runner"
Cohesion: 0.16
Nodes (18): compute_aggregate_score(), EvalScores, Live rubric preview — run the LLM judge on a sample input/output. Powers the…, BaseModel, _build_eval_prompt(), evaluate_content_async(), _evaluate_content_sync(), evaluate_node_async() (+10 more)

### Community 56 - "Components"
Cohesion: 0.09
Nodes (21): aliases, components, hooks, lib, ui, utils, iconLibrary, menuAccent (+13 more)

### Community 57 - "Run Authoring · CanvasTour"
Cohesion: 0.19
Nodes (18): FirstRunHero(), CanvasTour(), computePosition(), findVisibleAnchor(), Position, resolveStepIndex(), warnDev(), GettingStartedBanner() (+10 more)

### Community 58 - "Guardrail Enforcement · guardrail_presidio"
Cohesion: 0.18
Nodes (19): _analyzer_available(), _default_entities(), detect_pii_presidio(), _get_analyzer(), Any, Optional Microsoft Presidio integration for entity-based PII detection., redact_pii_presidio(), PromptInjectionVerdict (+11 more)

### Community 59 - "Alerts · observability_events"
Cohesion: 0.17
Nodes (17): broadcast_observability_event(), Any, Queue, User-scoped SSE fan-out for live observability updates., stream_observability_events(), subscribe_observability(), unsubscribe_observability(), maybe_emit_eval_regression() (+9 more)

### Community 60 - "Tests · test_node_test_api"
Cohesion: 0.19
Nodes (19): _agent_workflow(), Tests for the ephemeral node-test and expression-preview endpoints. No test…, _seed_run(), _seed_workflow(), test_expression_preview_from_run_steps_resolution(), test_expression_preview_most_recent_run_when_no_run_id(), test_expression_preview_oversize_expression_400(), test_expression_preview_render_error_is_data_not_500() (+11 more)

### Community 61 - "Run Authoring · expressions"
Cohesion: 0.19
Nodes (18): _coerce_number(), evaluate_condition(), Any, Template expression rendering for workflow context (n8n-style mapping)., Evaluate a structured IF condition (n8n-style, expression operands)., Replace ``{{path}}`` placeholders using workflow context., _render_operand(), render_template() (+10 more)

### Community 62 - "Graph Validation"
Cohesion: 0.21
Nodes (18): GraphValidationError, _is_annotation(), _is_number(), _node_data(), ValueError, Enforce n8n-style error-branch rules: at most one error edge per node and only…, Reject non-numeric config for fields the compiler parses as numbers., Validate canvas graph before save or compile. Returns summary metadata. (+10 more)

### Community 63 - "App Config"
Cohesion: 0.17
Nodes (15): configure_logging(), StructuredFormatter, active_run_count(), claim_pending_runs(), UUID, Dedicated worker loop for pending workflow runs., start_run_worker(), stop_run_worker() (+7 more)

### Community 64 - "AI Assist Service · test_assist"
Cohesion: 0.27
Nodes (18): GenEdge, GeneratedWorkflowDraft, _invalid_draft(), _mock_response(), patch, _suggest_graph(), test_explain_run_failed_returns_fixes(), test_explain_run_no_api_key_returns_400() (+10 more)

### Community 65 - "Model Ref"
Cohesion: 0.20
Nodes (17): available_models(), _coerce(), default_ref(), ModelRef, Pluggable model-selection seam for evaluation judges and guardrail classifiers.…, Models the UI may offer today (Gemini-only). Grows with multi-provider., Resolve an override to a concrete model string, defaulting to Gemini. Non-…, Model for an LLM-as-judge eval. Reads an optional preset['judge_model']. (+9 more)

### Community 66 - "Package"
Cohesion: 0.11
Nodes (19): clsx, cmdk, framer-motion, dependencies, clsx, cmdk, framer-motion, geist (+11 more)

### Community 67 - "Canvas UI"
Cohesion: 0.16
Nodes (16): PostRunTransport(), PostRunTransportProps, RunProgressStrip(), RunProgressStripProps, useElapsedSeconds(), deriveState(), isCompletedStatus(), isFailedStatus() (+8 more)

### Community 68 - "Alerts · alerts"
Cohesion: 0.22
Nodes (17): AlertRuleCreate, AlertRuleUpdate, create_rule(), delete_rule(), list_events(), list_rules(), AlertRule, BaseModel (+9 more)

### Community 69 - "Node Data Panel · node_test"
Cohesion: 0.20
Nodes (16): expression_preview(), node_test(), post, Session, UUID, Ephemeral node-test and expression-preview endpoints (canvas authoring aids).…, ContextAvailable, ExpressionPreviewRequest (+8 more)

### Community 70 - "App Config · config"
Cohesion: 0.16
Nodes (13): Settings, Any, BaseModel, rag_aggregate(), RagScores, RAG-specific evaluation scorers. Standard RAG quality dimensions an LLM judge…, Mean of the three RAG dimensions (1-5), rounded., Score a RAG triple. Returns per-dimension scores + aggregate, or a skip/error… (+5 more)

### Community 71 - "Tests · guardrail"
Cohesion: 0.19
Nodes (14): _parse_guardrail_status(), GuardrailResult, LlmGuardrailVerdict, ModerationVerdict, BaseModel, Dedicated toxicity/moderation rail — structured category scoring via Gemini., validate_content_llm(), validate_guardrail_content() (+6 more)

### Community 72 - "Worker Process"
Cohesion: 0.20
Nodes (17): purge_old_runs(), _claim_schedule_fire(), _create_scheduled_run_row(), cron_matches_now(), _evaluate_alerts(), _maybe_run_retention(), Any, datetime (+9 more)

### Community 73 - "Tests · test_api"
Cohesion: 0.15
Nodes (15): Build a graph that satisfies Trigger → … → End validation., valid_graph(), test_create_and_list_workflow(), test_create_run_requires_gemini_for_agent_workflow(), test_trigger_workflow_accepts_json_input(), test_compile_if_switch_nodes(), test_if_missing_branch_rejected(), test_if_node_requires_true_false_edges() (+7 more)

### Community 74 - "Tests · test_error_routing"
Cohesion: 0.17
Nodes (16): _error_graph(), _FakeCtx, Tests for per-node error-branch routing (n8n-style). A node that fails but…, Minimal stand-in for the ADK Context the wrapper writes ctx.route on., input_schema with a required field fails deterministically when the field is…, _run(), test_error_branch_not_taken_on_success(), test_error_branch_taken_on_failure() (+8 more)

### Community 75 - "API Entrypoint"
Cohesion: 0.19
Nodes (15): AsyncClient, shutdown_http_client(), startup_http_client(), health(), _health_db_counts(), lifespan(), FastAPI, # NOTE: schema is owned by Alembic (single source of truth). We intentionally (+7 more)

### Community 76 - "Eval Preset Service"
Cohesion: 0.30
Nodes (16): EvaluationPreset, build_eval_instruction(), _batch_load_custom_presets(), builtin_preset_rows(), enrich_graph_eval_presets(), get_preset_config(), list_all_presets(), list_user_presets() (+8 more)

### Community 77 - "Guardrail Plugin · token_tracker"
Cohesion: 0.19
Nodes (10): _apply_call_resilience(), Any, BasePlugin, Per-run token and cost accounting via ADK plugin callbacks. ADK 2.x's workflow…, Accumulates LLM token usage per ADK agent name for a single run., Flatten genai contents/parts into readable prompt text., Per-agent usage rows with cost estimates attached., Set a bounded per-call timeout + backoff retry on the outgoing LlmRequest. Uses… (+2 more)

### Community 78 - "Package (2)"
Cohesion: 0.12
Nodes (17): eslint, eslint-config-next, devDependencies, eslint, eslint-config-next, postcss, tailwindcss, @types/node (+9 more)

### Community 79 - "Tests · test_structured_output_guardrail"
Cohesion: 0.18
Nodes (15): _parse_schema(), Parse ``text`` as JSON and validate it against ``schema``. Pure — no LLM.…, Ask the model to coerce ``text`` into JSON matching ``schema``. Returns the…, Enforce a JSON schema on output; on failure, re-ask the model to repair it…, _repair_to_schema(), validate_against_schema(), validate_structured_output(), Structured-output guardrail: JSON-schema validation + bounded re-ask. The re-… (+7 more)

### Community 80 - "Alerts · quality_alerts"
Cohesion: 0.20
Nodes (14): Any, UUID, Workflow, WorkflowRun, quality_webhook_for_run(), Dispatch workflow webhooks for quality events (eval fail, guardrail block)., schedule_quality_webhook(), WorkflowRun (+6 more)

### Community 81 - "Trace Plugin"
Cohesion: 0.27
Nodes (7): Any, BasePlugin, Exception, Per-run tool-call capture via ADK plugin callbacks (Trust-layer trace tree).…, Accumulates tool-call spans (name/args/result/timing) per ADK agent., _summarize(), TracePlugin

### Community 82 - "Run Authoring (4)"
Cohesion: 0.14
Nodes (15): Workflow compilation to ADK Workflow, Executor + in-memory SSE run event broker, Execution modes: inline vs worker (single-process constraint), Graph DAG validation (Trigger to End, acyclic), Node type system (28 types, 6 categories, spans both apps), Run pipeline (validation, compilation, execution), Durable execution / run resilience (P1.3), ADK-native graph execution (branching, fan-out JoinNode) (+7 more)

### Community 83 - "Tests · workflow_context"
Cohesion: 0.19
Nodes (8): Mutable workflow context passed through node execution., test_batch_last_scheduled_run_at_empty(), test_build_summary_fetches_runs_once(), test_workflow_context_snapshot_truncates_large_outputs(), test_context_from_json_input(), test_context_from_plain_text(), test_record_step_updates_last_output(), test_snapshot_for_metrics_excludes_memory()

### Community 84 - "Tests · templates"
Cohesion: 0.22
Nodes (9): Helpers for standard Trigger → … → End workflow graphs., Prepend Trigger and append End, wiring entry/exit automatically. When…, wrap_graph_with_trigger_end(), Stamp the DB at Alembic head so the startup migration gate sees it current. The…, setup_database(), _stamp_alembic_head(), _create_calculator_workflow(), test_create_run_rejects_empty_input() (+1 more)

### Community 85 - "Run Authoring (5)"
Cohesion: 0.21
Nodes (7): NodeNotFoundError, Exception, Requested node_id is absent from the workflow's current graph., Any, Accumulates run input and per-step outputs for expression mapping., Snapshot safe for metrics/SSE — excludes workflow memory., WorkflowContext

### Community 86 - "Tests · workflow_import"
Cohesion: 0.27
Nodes (11): normalize_workflow_import(), ValueError, Parse and validate aegis-workflow-v1 export payloads for import., Extract name, description, and graph from an export or partial import payload., WorkflowImportError, _sample_export(), test_export_workflow_matches_import_format(), test_import_into_existing_workflow_versions_graph() (+3 more)

### Community 87 - "Tests · test_mvp2_foundation"
Cohesion: 0.19
Nodes (6): _make_workflow(), Tests for MVP2 backend foundation: timeline, deploy, dashboards, crypto, cost…, test_cost_alert_rule_is_supported(), test_credential_secret_encrypted_at_rest(), test_deploy_descriptor_after_publish_includes_mcp_tool(), test_deploy_descriptor_requires_published_version()

### Community 88 - "Tests (12)"
Cohesion: 0.18
Nodes (12): Exception, get, Request, rate_limit_middleware(), RBAC-lite: viewer keys are read-only across all mutating API methods., unhandled_exception_handler(), viewer_role_middleware(), rate_limited_path() (+4 more)

### Community 89 - "Code Sandbox"
Cohesion: 0.18
Nodes (6): Attribute, _SafetyVisitor, Call, Import, ImportFrom, Name

### Community 90 - "Package (3)"
Cohesion: 0.18
Nodes (10): name, private, scripts, analyze, build, dev, lint, start (+2 more)

### Community 91 - "Knowledge"
Cohesion: 0.29
Nodes (8): create_knowledge_document(), KnowledgeDocument, KnowledgeBulkImport, KnowledgeDocumentCreate, KnowledgeDocumentResponse, BaseModel, apply_embedding(), Session

### Community 92 - "Experiment Runner"
Cohesion: 0.44
Nodes (9): _aggregate(), Any, UUID, Batch experiments: run a dataset against workflow version(s), score, compare.…, run_experiment(), _run_one_item(), _run_version_over_items(), _session() (+1 more)

### Community 93 - "Tests · test_moderation_guardrail"
Cohesion: 0.31
Nodes (8): _evaluate_moderation_scores(), Map category scores + thresholds to a verdict. Pure and side-effect-free so it…, Trust-layer Phase 3: moderation/toxicity guardrail rail. Covers the pure…, test_above_default_threshold_flags(), test_below_threshold_passes(), test_custom_single_threshold(), test_malformed_scores_do_not_crash(), test_per_category_thresholds_override_default()

### Community 94 - "Tests · search"
Cohesion: 0.40
Nodes (8): run_search(), search_duckduckgo(), search_exa(), asyncio, patch, test_run_search_duckduckgo(), test_run_search_exa_without_key(), test_search_duckduckgo_formats_results()

### Community 95 - "Guardrails UI"
Cohesion: 0.33
Nodes (9): escapeRegExp(), findKeywordMatches(), findPiiMatches(), HighlightedSample(), HighlightedSampleProps, MatchSpan, mergeSpans(), PII_PATTERNS (+1 more)

### Community 96 - "Workflow Compiler · test_compiler"
Cohesion: 0.33
Nodes (8): _safe_eval(), topological_sort(), test_compile_google_search_enables_server_side_tool_invocations(), test_compile_workflow_metadata_adk_names(), test_safe_eval_allows_simple_pow(), test_safe_eval_blocks_large_exponent(), test_topological_sort_linear(), test_topological_sort_rejects_cycles()

### Community 97 - "Tests · test_integrations_email"
Cohesion: 0.42
Nodes (8): Return an error message when the recipient is invalid; None if acceptable., run_email_integration(), _validate_single_email_recipient(), asyncio, test_email_missing_to_after_render(), test_email_rejects_multiple_recipients(), test_email_single_recipient_succeeds_without_smtp(), test_email_without_smtp_does_not_leak_payload()

### Community 98 - "Tests · test_experiment_gate"
Cohesion: 0.39
Nodes (7): Trust-layer Phase 2: GET /api/experiments/{id}/gate CI regression gate. Wraps a…, _seed_experiment(), test_gate_failed_regression_and_strict_409(), test_gate_not_applicable_for_batch(), test_gate_passed_regression(), test_gate_pending_while_running(), _verdict()

### Community 99 - "AI Assist Service (5)"
Cohesion: 0.32
Nodes (8): CompareVariantResult, compare_variants(), Wrap a single node between a trigger and end for single-node execution., Execute one variant as a single-node LLM run, capturing telemetry. Reuses the…, Run each variant (base_config merged with overrides) as a single-node run.…, _run_single_node_variant(), _single_node_graph(), CompareVariantResult

### Community 100 - "DB Models · context_wrapper"
Cohesion: 0.36
Nodes (6): _normalize_output(), Any, Wrap compiled node callables to maintain workflow context across execution. The…, ClassifierDecision, BaseModel, RouterDecision

### Community 101 - "Canvas UI · useRunInput"
Cohesion: 0.39
Nodes (7): coerce(), deriveFields(), normalizeField(), readStored(), RunField, StoredInput, useRunInput()

### Community 102 - "Tests · test_routing_adk2"
Cohesion: 0.48
Nodes (6): _branch_graph(), Regression: conditional routing must work under ADK 2.x. ADK 2.x routes…, _run_graph(), test_if_decision_is_not_leaked_as_output(), test_if_routes_correct_branch(), parametrize

### Community 103 - "Canvas UI · CanvasContextMenu"
Cohesion: 0.48
Nodes (6): buildNodeRunMenuItems(), CanvasContextMenu(), CanvasContextMenuProps, ContextMenuItem, firstEnabledIndex(), isSeparator()

### Community 104 - "Workflow-Import UI"
Cohesion: 0.33
Nodes (5): parseWorkflowExport(), readWorkflowExportFile(), WORKFLOW_EXPORT_FORMAT, WorkflowExportPayload, WorkflowImportError

### Community 105 - "Migrations"
Cohesion: 0.73
Nodes (5): _columns(), downgrade(), _existing_tables(), _inspector(), upgrade()

### Community 106 - "Migrations · 013_alert_baseline_comparison"
Cohesion: 0.73
Nodes (5): _columns(), downgrade(), _existing_tables(), _inspector(), upgrade()

### Community 107 - "Kb Cache"
Cohesion: 0.40
Nodes (5): load_workflow_kb_documents(), Any, Session, UUID, Per-run knowledge document cache.

### Community 108 - "Tests · test_phase8"
Cohesion: 0.47
Nodes (4): count_scheduled_workflows(), scheduler_status(), test_count_scheduled_workflows(), test_scheduler_status_shape()

### Community 109 - "Tests · test_dataset_capture"
Cohesion: 0.60
Nodes (5): _cleanup(), Bulk capture of production runs into a golden dataset. Covers the filter modes…, _seed(), test_capture_failed_then_dedups(), test_capture_low_eval()

### Community 110 - "Ui-Audit-Issues"
Cohesion: 0.33
Nodes (6): Copper as dedicated active semantic token (not blanket warning), Obsidian + Oxide Copper palette (Canvas Run Lens), Aegis Frontend UI/UX Audit 2026-07-11, Mobile canvas layout-lock mode, text-2xs Tailwind token consolidation, Chroma-reserved design language (warm near-black, bone, monochrome)

### Community 111 - "Upgrade Plan"
Cohesion: 0.40
Nodes (6): Evaluation rigor: online evals + CI gates (P1.2), Evaluation suite (faithfulness/helpfulness/relevance/toxicity, 1-5), P0: misleading eval chroma (1-5 scores banded on 0-1), User-defined eval presets & weighting (EvaluationPreset model), Deterministic evaluators (exact/substring, regex, embedding similarity), OpenTelemetry tracing export (Jaeger/LangFuse/Datadog)

### Community 112 - "2026-07-01-Ui-Overhaul"
Cohesion: 0.33
Nodes (6): Motion primitives (PageEnter, StaggerList, HoverLift, NumberTween, useGlowPulse), Reduced-motion gating (useReducedMotionStrict), Design token system (CSS variables + Tailwind config), Glass & glow visual language, Design-system quality bar (instrument aesthetic, chroma for data only), Hardcoded white sheen vs --surface-highlight token (light theme loses lift)

### Community 113 - "13-Continue-Build-Run"
Cohesion: 0.40
Nodes (5): Aegis Workflow, UI Mockup: Continue Build and Run, UI Mockup: Open or Run Workflows, UI Mockup: Structure Index of Workflows, UI Mockup: Start from Pattern Templates

### Community 114 - "Frontend-Design-Audit"
Cohesion: 0.40
Nodes (5): Aegis Frontend Design Audit (2026-07-20), Guardrails Playground Screenshot, Home Error State Screenshot, Observability Triage Screenshot, Workflow Home Screenshot

### Community 115 - "Tests · test_workflows_eval"
Cohesion: 0.50
Nodes (4): _extract_run_eval_metrics(), _flatten_eval_scores(), WorkflowRun, test_extract_run_eval_metrics_flattens_completed_run_scores()

### Community 116 - "Memory"
Cohesion: 0.60
Nodes (4): get_workflow_memory(), BaseModel, WorkflowMemoryEntry, WorkflowMemoryResponse

### Community 117 - "Isses"
Cohesion: 0.40
Nodes (5): Code Node sandbox breakout via json.codecs traversal, DNS rebinding SSRF (TOCTOU) in HTTP Node, Postgres integration SSRF (no URL/IP validation), Read-only regex bypass via CTE (WITH ... DELETE), SMTP integration blocks the event loop

### Community 118 - "Migrations · 009_agentops_tables_backfill"
Cohesion: 0.83
Nodes (3): downgrade(), _existing_tables(), upgrade()

### Community 119 - "Migrations · 011_workflow_templates"
Cohesion: 0.83
Nodes (3): downgrade(), _existing_tables(), upgrade()

### Community 120 - "Tests (21)"
Cohesion: 0.50
Nodes (3): EvalThresholdBlockedError, Exception, test_eval_threshold_blocked_error_carries_aggregate()

### Community 121 - ".Eslintrc"
Cohesion: 0.50
Nodes (3): extends, next/core-web-vitals, next/typescript

### Community 122 - "Package (4)"
Cohesion: 0.50
Nodes (4): react, DeploySheetBody(), isNoPublishedVersion(), react

### Community 124 - "18-Publish-Lifecycle"
Cohesion: 0.67
Nodes (3): Aegis Agent, UI Mockup: Publish Lifecycle Stages, UI Mockup: Modules and Agents Library

### Community 125 - "16-Quality-Loop"
Cohesion: 0.67
Nodes (3): Aegis Evaluation, UI Mockup: Quality Loop and Posture, UI Mockup: Observability Dashboard

### Community 134 - "Migrations (12)"
Cohesion: 0.67
Nodes (3): Alembic schema ownership + startup head gate, Backend layering (routers, schemas, services, models), Data model (24 SQLAlchemy tables, workflow to version to run)

### Community 135 - "Roadmap"
Cohesion: 0.67
Nodes (3): Gemini-only runtime constraint, Multi-model / multi-provider support (P0.1), Provider abstraction (LiteLLM-style shim)

### Community 136 - "Upgrade Plan (2)"
Cohesion: 0.67
Nodes (3): Guardrail engine (blocklist/regex/PII, block vs warn), Advanced PII (Microsoft Presidio) + prompt injection shield, Guardrail graceful fallbacks & PII masking/redaction

### Community 137 - "Migrations (13)"
Cohesion: 0.67
Nodes (3): shadcn/ui primitive migration (Radix-backed), P0: dead focus ring (Tailwind v4 ring-3 in v3 build), Tailwind v4 syntax dead in v3 build (vendored shadcn primitives)

## Knowledge Gaps
- **375 isolated node(s):** `next/core-web-vitals`, `next/typescript`, `$schema`, `style`, `rsc` (+370 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **47 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `cn()` connect `Canvas Chrome` to `Base Node UI`, `Guardrails UI Components`, `Node Inspector UI`, `Group Node UI`, `App Routes`, `Run Detail UI`, `Canvas UI · CanvasContextMenu`, `Settings UI`, `Guardrails & Templates UI`, `Canvas Clipboard`, `Root Layout`, `Loading & Panels · CanvasSidebar`, `Node Data Panel`, `Observability UI`, `Node Palette`, `Loading & Panels`, `Run Authoring · CanvasTour`?**
  _High betweenness centrality (0.031) - this node is a cross-community bridge._
- **Why does `validate_workflow_graph()` connect `Graph Validation` to `AI Assist Service · test_assist`, `Runs API`, `Run Authoring`, `Worker Process`, `Tests · test_api`, `Tests · test_error_routing`, `Workflow`, `Workflow Compiler`, `AI Assist Service`, `Eval Presets API · templates`, `Tests · workflow_import`, `Workflows API`?**
  _High betweenness centrality (0.013) - this node is a cross-community bridge._
- **Why does `compile_workflow()` connect `Workflow Compiler` to `Workflow Compiler · test_compiler`, `AI Assist Service (5)`, `Evals & Embeddings`, `Tests · test_routing_adk2`, `Tests · guardrail`, `Integrations`, `Tests · test_api`, `Tests · test_error_routing`, `Node Registry`, `Alerts · quality_alerts`, `Run Authoring (4)`, `AI Assist Service`, `Run Executor`, `Alerts · observability_events`, `Graph Validation`, `Guardrail Enforcement`?**
  _High betweenness centrality (0.012) - this node is a cross-community bridge._
- **What connects `next/core-web-vitals`, `next/typescript`, `$schema` to the rest of the system?**
  _375 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Canvas Chrome` be split into smaller, more focused modules?**
  _Cohesion score 0.03549654518357946 - nodes in this community are weakly interconnected._
- **Should `App Routes` be split into smaller, more focused modules?**
  _Cohesion score 0.047928331466965284 - nodes in this community are weakly interconnected._
- **Should `Node Inspector UI` be split into smaller, more focused modules?**
  _Cohesion score 0.031710362047440696 - nodes in this community are weakly interconnected._