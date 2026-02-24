# PyMarkdownEditor Roadmap

## Vision

PyMarkdownEditor aims to become an **extremely user-friendly, powerful Markdown editor** where Markdown feels natural,
intelligent, and fluid — while preserving:

* Deterministic behavior
* Clean architecture
* Offline-first capability
* Plugin-first extensibility

AI is an **optional capability layer**, not the product’s core identity.

---

# Product Vision Pillars

## 1. Smart Markdown UX

Make Markdown feel effortless:

* Selection-aware formatting
* Context-aware link/code/list handling
* Inline helpers that never interrupt writing flow
* Diff-based transformations instead of destructive rewrites

Markdown remains primary. Intelligence augments it.

---

## 2. Extensible by Design

Plugins are first-class citizens.

* Stable `IAppAPI` contract
* Built-in plugins serve as reference
* External plugins via entrypoints
* Clear governance model for plugin acceptance

The editor core remains minimal and stable.

---

## 3. AI as Optional Power (Never Noise)

AI features must be:

* Opt-in
* Deterministic when disabled
* Transparent (diff previews, sources shown)
* Explicit (no silent edits)
* Private (clear visibility of what data is sent)

AI enhances editing — it does not replace it.

---

# Roadmap Phases

---

## Phase 0 — Settings & Configuration Surface (Foundational UX)

Add a first-class Settings UI to expose configurable behaviour safely and consistently.

### Deliverables

* Dedicated **Settings dialog** (tabbed; searchable)
* Rendering configuration (preview engine, Markdown extensions, CSS/theme)
* Editor UI preferences (wrap, font, tab width, preview visibility)
* Plugin management entry-point and plugin-specific settings
* AI configuration (provider selection, tokens, model settings)
* Import/export of settings (optional; later)

### Design Principles

* All settings are **explicit**, discoverable, and reversible.
* Settings changes are **safe-by-default** (no destructive actions).
* AI credentials/settings are stored securely (OS keyring where possible).
* Plugin settings are namespaced (e.g. `plugins/<plugin_id>/...`).

---

## Phase 1 — Capability Layer (Optional AI Framework)

Build infrastructure without altering core editing behavior.

### Deliverables

* `IAIClient` protocol
* `AIRequest`, `AIResponse`, `AIError`
* Provider adapters (OpenAI, Anthropic; local LLM later)
* Structured metadata (tokens, latency, model info)
* Feature flag: `ai/enabled = false` by default
* Settings UI for provider + model configuration

### Design Principles

* No UI logic in core AI layer
* All AI outputs structured and inspectable
* Cancellation + rate limiting support

---

## Phase 2 — Local Retrieval Engine (RAG v1)

Introduce optional document-aware intelligence.

### v1 Scope

* Chunk current document
* Chunk open project folder
* Return ranked chunks with citations
* Local vector store only

### Contracts

* `IEmbeddingClient`
* `IVectorStore`
* `RetrievalQuery`
* Citation metadata model

Hybrid retrieval and remote stores remain future considerations.

---

## Phase 3 — Agent System

Agents are structured tools, not chatbots.

### Core Contracts

`IAgent`:

* `id`
* `name`
* `description`
* supported `modes`
* `run(context) -> AgentResult`

`AgentResult` supports:

* Suggested edits (patch/diff)
* Commentary
* Citations
* Structured output

---

## Initial Built-in Agents (v1)

### 1. Proofreader

* UK English enforcement
* Grammar and clarity checks
* “Light touch” vs “Strict” mode
* Diff-based output only

### 2. Copywriter

* Notes → polished copy
* Preset templates (LinkedIn, email, blog)
* Brand voice profiles

### 3. Book Planner

* Outline generation
* Chapter scaffolding
* Terminology consistency via project retrieval

Future agents may include:

* Technical Writer
* Summariser / Task Extractor
* Documentation Assistant
* Curriculum Vitae Writer

---

## Phase 4 — Editor-Integrated Agent Console

AI must feel native, not bolted on.

### Agent Panel (Dock)

* Agent selector
* Scope selector (selection / document / folder)
* Output mode (suggest / comment-only)
* Diff view with accept/reject controls
* Citation viewer

Modes:

* Proofread Mode
* Copywriter Mode
* Book Planner Mode

---

## Phase 5 — Plugin-Based Agent Ecosystem

* Agents packaged as plugins
* Built-in agents serve as reference implementations
* External agent repositories supported
* Governance and signing model defined

---

# Settings Dialog Plan

The Settings dialog is the home for all configurable behaviour, including rendering options and AI credentials.

## Tabs

1. **General**
2. **Editor**
3. **Preview & Rendering**
4. **Export**
5. **Plugins**
6. **AI**
7. **Privacy & Safety**
8. **Advanced / Diagnostics**

---

# Rendering & Editor Settings Catalogue

The goal is to expose meaningful options without making the UI noisy. Defaults remain sensible.

## General

* `ui/theme`: default / midnight / paper
* `ui/language`: (future) en-UK default
* `ui/restore_session`: reopen last files (future)
* `ui/telemetry`: off by default (likely never)

## Editor

* `editor/font_family`
* `editor/font_size`
* `editor/tab_width_spaces`
* `editor/line_wrap`: on/off
* `editor/show_line_numbers`: (future)
* `editor/highlight_current_line`: (future)
* `editor/auto_pair_brackets`: (future)
* `editor/smart_paste_links`: on/off
* `editor/smart_format_toggles`: on/off (bold/italic toggles)
* `editor/trim_trailing_whitespace_on_save`: (future)

## Preview & Rendering

### Preview Engine

* `render/engine`: `text` (QTextBrowser) / `web` (QWebEngineView) / `auto`
* `render/webengine_enabled`: true/false (alias for env override)
* `render/refresh_mode`: on-change / debounced
* `render/debounce_ms`

### Markdown Parser + Extensions

Expose safe toggles mapped to `python-markdown` extensions:

* `render/md_extensions/extra`: on/off
* `render/md_extensions/fenced_code`: on/off
* `render/md_extensions/codehilite`: on/off
* `render/md_extensions/toc`: on/off
* `render/md_extensions/sane_lists`: on/off
* `render/md_extensions/smarty`: on/off
* `render/pymdownx/enabled`: on/off (master toggle)
    * `render/pymdownx/arithmatex`: on/off
    * (future) other pymdown extensions

### Styling

* `render/css/theme`: default / custom
* `render/css/custom_path`: path to custom CSS file (future)
* `render/open_external_links`: on/off
* `render/allow_remote_images`: on/off (default off for privacy)

## Export

* `export/default_format`: html/pdf
* `export/pdf_engine`: classic/webengine
* `export/pdf_page_size`: A4/Letter
* `export/pdf_margins_mm`: (top/right/bottom/left)
* `export/html_embed_css`: on/off
* `export/open_after_export`: on/off (future)

## Plugins

* `plugins/enabled`: master toggle (future)
* `plugins/allow_external_installs`: on/off
* `plugins/require_signed_plugins`: (future)
* `plugins/catalog_url`: (future)
* plugin-scoped keys:
    * `plugins/<plugin_id>/<key>` (via AppAPI get/set plugin setting)

## Privacy & Safety

* `privacy/send_selection_only_by_default`: true/false
* `privacy/confirm_before_ai_send`: true/false (default true)
* `privacy/redact_secrets`: on/off (future secret scanning)
* `privacy/allow_project_folder_rag`: on/off
* `privacy/allow_file_paths_in_prompts`: on/off
* `privacy/log_ai_requests_locally`: on/off (default off)

## Advanced / Diagnostics

* `diagnostics/show_loaded_config_path`: on/off
* `diagnostics/show_plugin_errors`: on/off
* `diagnostics/ai_trace_level`: off/basic/verbose
* `diagnostics/rag_index_stats`: on/off

---

# AI Settings Catalogue

Settings must be separated into:

1) **Global AI settings** (affect all providers)
2) **Provider-specific settings** (OpenAI/Anthropic/etc.)
3) **Model/runtime settings** (per-provider, per-agent, per-task)

## 1) Global AI Settings (Provider-Agnostic)

These apply regardless of which API is selected.

### Enablement & Behaviour

* `ai/enabled`: true/false (default false)
* `ai/provider`: `openai` / `anthropic` / `local` / `none`
* `ai/default_agent`: `proofreader` / `copywriter` / `book_planner`
* `ai/streaming`: on/off (if supported)
* `ai/timeout_seconds`
* `ai/max_retries`
* `ai/backoff_strategy`: fixed/exponential
* `ai/request_concurrency`: (future)

### Output Policy

* `ai/output_mode_default`: diff/comment-only
* `ai/require_diff_for_edits`: true/false (default true)
* `ai/show_citations`: true/false (default true for RAG agents)
* `ai/uk_english_default`: true/false
* `ai/safety_level`: strict/standard (future)

### Context Scope Defaults

* `ai/scope_default`: selection/document
* `ai/include_document_title`: on/off
* `ai/include_front_matter`: on/off (future)
* `ai/include_project_context`: on/off (requires RAG)
* `ai/max_context_chars`: guardrail
* `ai/max_tokens_output`: guardrail

### RAG Controls (Global)

* `rag/enabled`: true/false
* `rag/scope`: selection/document/project
* `rag/top_k`: e.g., 5/10/20
* `rag/min_score`: threshold
* `rag/index_on_open`: on/off
* `rag/index_on_save`: on/off
* `rag/chunk_size`: e.g., 800 chars
* `rag/chunk_overlap`: e.g., 120 chars
* `rag/vector_store`: local (default)
* `rag/cache_embeddings`: on/off
* `rag/cache_max_mb`

### Secure Storage

* `ai/credential_store`: keyring/file (keyring preferred)
* `ai/api_key_ref`: keyring lookup key (not plaintext)

---

## 2) Provider-Specific AI Settings

These keys live under a provider namespace:

### OpenAI (example)

* `ai/openai/api_key_ref`
* `ai/openai/base_url` (optional; for proxies/enterprise)
* `ai/openai/org_id` (optional)
* `ai/openai/project_id` (optional)
* `ai/openai/default_model`
* `ai/openai/reasoning_effort` (if supported by chosen model family)
* `ai/openai/temperature_default`
* `ai/openai/top_p_default`
* `ai/openai/max_output_tokens_default`

### Anthropic (example)

* `ai/anthropic/api_key_ref`
* `ai/anthropic/base_url` (optional)
* `ai/anthropic/default_model`
* `ai/anthropic/temperature_default`
* `ai/anthropic/top_p_default`
* `ai/anthropic/max_output_tokens_default`

### Local LLM (future)

* `ai/local/provider`: ollama/lmstudio/custom
* `ai/local/base_url`
* `ai/local/default_model`
* `ai/local/embedding_model`
* `ai/local/context_window_tokens`

---

## 3) Agent-Level Settings (Applies Across Providers)

Agents should have configurable behaviour independent of provider.

Namespace pattern:

`ai/agents/<agent_id>/...`

### Proofreader

* `ai/agents/proofreader/strictness`: light/standard/strict
* `ai/agents/proofreader/focus`: grammar/clarity/tone/all
* `ai/agents/proofreader/preserve_style`: on/off
* `ai/agents/proofreader/avoid_rewrites`: on/off
* `ai/agents/proofreader/prefer_uk_spelling`: on/off
* `ai/agents/proofreader/formatting_policy`: preserve/normalize

### Copywriter

* `ai/agents/copywriter/tone`: formal/neutral/warm
* `ai/agents/copywriter/length`: short/medium/long
* `ai/agents/copywriter/audience`: free text
* `ai/agents/copywriter/brand_voice_profile`: profile id
* `ai/agents/copywriter/templates_enabled`: on/off

### Book Planner

* `ai/agents/book_planner/genre`
* `ai/agents/book_planner/target_length_words`
* `ai/agents/book_planner/chapter_count_target`
* `ai/agents/book_planner/style_constraints`
* `ai/agents/book_planner/glossary_mode`: off/on
* `ai/agents/book_planner/outline_format`: bullets/headings/json

---

# Engineering Milestones

## Milestone A — Core Contracts + Settings Dialog

* AI interfaces
* Feature flag
* Settings dialog scaffolding (tabs + storage)
* Rendering options exposed safely

## Milestone B — Retrieval v1

* Local document indexing
* Citation support
* Deterministic test suite

## Milestone C — Agents v1

* Proofreader
* Copywriter
* Book Planner
* Diff/patch system

## Milestone D — Plugin Marketplace

* Agent plugin loading
* External extension documentation
* Governance documentation

---

# Non-Functional Guarantees

* Offline-first remains default.
* No AI dependency required.
* Deterministic tests (AI fully mockable).
* API keys stored securely (OS keyring).
* Clear visibility of transmitted content.
* Background indexing only; no UI blocking.
* Bounded embedding cache storage.

---

# Scope Boundaries

PyMarkdownEditor is:

* A Markdown editor first.
* An extensible platform second.
* An AI-capable editor third.

It is not:

* A chat application.
* A cloud-dependent writing platform.
* A replacement for deterministic editing.
