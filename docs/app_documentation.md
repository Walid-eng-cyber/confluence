# App reference

Operator reference for the Streamlit app: what each section does, every configuration
variable, and how to run things.

This document deliberately does **not** re-explain how the pipelines work. That lives in
[the README](../README.md) as a summary and in [foundations.md](foundations.md) as an
explanation from first principles. Duplicating it here is how documentation goes stale.

## 1. Sections

The app is one page with five sections. Navigation is session state rather than `st.tabs`,
because a tab's selection is client-side and is lost on rerun, which threw the user into a
different section whenever a filter fired.

A strategy picker sits beside the navigation. Everything below respects it.

| Section | What it shows | Model calls |
|---|---|---|
| Setup Review | Status counts, Stage 3 verdict, the two-sided case with precedent, per-item Stage 2 evidence, Stage 1 raw output | One per run plus one per routed item-section pair |
| Strategy | The selected strategy rendered from its own source file, its thresholds, and a section filter | None |
| Trade Tracker | Metrics, equity curve, filters on instrument / outcome / criterion 2, colour-coded table, rule flags for the current selection, notes | None |
| Reports | Day, week, month or all-logged. Metrics, RR discipline, per-instrument table, rule breaches, and the raw findings block handed to the model | One, behind a button |
| Advisor | Whole-strategy stats, score-bucket and criterion-2 segments, rule-adherence flags | One, behind a button |

Reports and Advisor render every number immediately and put narration behind a button,
because the numbers cost nothing and the narration costs a model call.

## 2. Strategy scoping

The picker changes more than the Strategy section. Trade Tracker, Reports and Advisor all
query scoped to the selected strategy, so switching changes the trade history with it.

A strategy with no logged trades shows an empty state naming how many trades exist under
other strategies and why they are withheld. It is never filled with sample data: every
figure in this system is supposed to trace to a trade that was actually taken.

## 3. Configuration

All optional. Defaults shown.

### Models and endpoint

| Variable | Default | Purpose |
|---|---|---|
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama endpoint |
| `OLLAMA_CHAT_MODEL` | `deepseek-r1:8b` | Fallback for the Stage 1 restate model |
| `OLLAMA_RESTATE_MODEL` | `OLLAMA_CHAT_MODEL` | Stage 1 only |
| `OLLAMA_MATCH_MODEL` | `qwen3:8b` | Stage 2 matching and quoting |
| `OLLAMA_ADVISOR_MODEL` | match model | Advisor narration |
| `OLLAMA_REPORT_MODEL` | match model | Report narration |

A configured model that is not installed falls back to the match model rather than failing.

**The default is two different 8B models, which needs roughly 10GB of VRAM.** On an 8GB card
that terminates llama-server. Point `OLLAMA_RESTATE_MODEL` at the match model until the
two-tier split is worth the swap cost.

### Context and generation

| Variable | Default | Purpose |
|---|---|---|
| `OLLAMA_NUM_CTX_RESTATE` | `1536` | Stage 1 context window |
| `OLLAMA_NUM_CTX` | `1536` | Fallback for the above |
| `OLLAMA_NUM_CTX_MATCH` | `4096` | Stage 2 context window |
| `OLLAMA_NUM_CTX_MATCH_CAP` | `4096` | Ceiling on Stage 2 context |
| `OLLAMA_SECTION_CTX_FLOOR` | `2048` | Floor for per-section dynamic sizing |
| `OLLAMA_NUM_CTX_ADVISOR` | `4096` | Advisor context window |
| `OLLAMA_NUM_CTX_REPORT` | `4096` | Report context window |
| `OLLAMA_MATCH_NUM_PREDICT` | `768` | Stage 2 output cap |
| `OLLAMA_MATCH_NUM_PREDICT_RETRY` | `1536` | Raised cap for the one length-capped rescue |
| `OLLAMA_ADVISOR_NUM_PREDICT` | `1024` | Advisor output cap |
| `OLLAMA_REPORT_NUM_PREDICT` | `768` | Report output cap |
| `PROMPT_CONTEXT_CHARS` | `3000` | Excerpt budget for whole-document prompting |

### Reliability

| Variable | Default | Purpose |
|---|---|---|
| `OLLAMA_MATCH_TIMEOUT_SEC` | `60` | Bounds a Stage 2 call, converting a hang into an explicit ERROR |
| `OLLAMA_RETRIES` | `1` | Retry attempts |
| `OLLAMA_RETRY_DELAY_SEC` | `0.2` | Initial backoff |
| `OLLAMA_RETRY_MAX_DELAY_SEC` | `1.0` | Backoff ceiling |
| `OLLAMA_MATCH_KEEP_ALIVE` | `10m` | How long the match model stays resident |
| `OLLAMA_ADVISOR_KEEP_ALIVE` | `10m` | Advisor model residency |
| `OLLAMA_REPORT_KEEP_ALIVE` | `10m` | Report model residency |
| `RAW_PARSE_DEBUG_ONCE` | `1` | Print one raw response when parsing fails |

### Behaviour flags

| Variable | Default | Purpose |
|---|---|---|
| `ENABLE_SIDE_CLASSIFICATION` | `0` | Adds the `Side` field so the two-sided case can argue each fact. **Off by default**: enabling it changes the match prompt the eval harness measures, so re-baseline first. With it off, rule-matched facts are listed as unclassified and the output says so. |
| `ENABLE_DYNAMIC_SECTION_CTX` | `0` | Per-section context sizing with cached clients |
| `OLLAMA_DISABLE_THINKING` | `0` | Sends Ollama's `think: false`, stopping qwen3 spending most of its generation budget on reasoning that is then stripped. Measured 3x faster end to end. **Off by default**: it changes what the model generates, so re-baseline the eval before promoting. |

### Data

| Variable | Default | Purpose |
|---|---|---|
| `TRADE_DB_PATH` | `./data/trades/confluence.db` | SQLite store |
| `DEFAULT_STRATEGY_ID` | the config marked `"default": true` | Which strategy the app opens on |

## 4. Performance

Measured on qwen3:8b, RTX 4060, one Setup Review run over the default setup.

| | Baseline | With both switches |
|---|---|---|
| Setup Review, warm | ~146s | **~46s** |
| Setup Review, cold model | — | ~57s |
| One Stage 2 match call | 9.3s | 3.4s |
| Tokens generated per match call | 310 | 52 |
| Report narration | 21.8s, **often empty** | 8.3s, 863 chars |

Two changes, in order of effect:

1. **`OLLAMA_DISABLE_THINKING=1`.** Stage 2 is one model call per routed item-section pair
   and dominates the run. Generation runs at a healthy 45 tok/s, so the cost was not the
   hardware: qwen3 was generating ~310 tokens to produce ~55 tokens of answer, the rest
   being `<think>` content that `_sanitize_model_text` discards afterwards.

   `/no_think` in the prompt does **not** suppress it — measured 353 tokens with it versus
   342 without. Ollama's `think: false` parameter does, but `langchain-ollama` 0.2.2 has no
   such parameter and, being a permissive pydantic model, accepts `think=False` and silently
   drops it. `app/core/ollama_client.py` calls `/api/chat` directly to send it.

2. **One model for both stages**, e.g. `OLLAMA_RESTATE_MODEL=qwen3:8b`. Avoids swapping two
   5GB models on an 8GB card, and the reasoning model extracted six facts where qwen3
   extracts four — each extra fact costs another Stage 2 call, so the restate model choice
   multiplies through the run.

Suppressing thinking also fixed a bug rather than only saving time. With thinking on, the
report and advisor narrations sometimes spent all 768 output tokens reasoning and returned
**nothing visible**, which surfaced as an empty narrative with no error. It was
intermittent, because it depended on how long the model happened to think. Both nodes now
detect empty output and say what happened instead of showing nothing.

Not yet done, in rough order of remaining value:

1. **Group items by section.** Two facts routed to the same section are two calls today; one
   call per section would cut the call count. Changes the prompt, so it needs re-baselining.
2. **Run Stage 2 calls concurrently.** They are independent. Limited by KV-cache memory on
   8GB, so expect two slots rather than many.
3. **Stream per-item results into the UI.** Does not reduce total time, but the run stops
   looking like a 50-second blank spinner.

## 5. Running

```powershell
cd d:/confluence-scaffold/confluence
d:/confluence-scaffold/.venv-1/Scripts/python.exe -m streamlit run streamlit_app.py
```

Then <http://localhost:8501>.

Command-line equivalents, each with a `--stats-only` path that skips the model entirely:

```powershell
d:/confluence-scaffold/.venv-1/Scripts/python.exe scripts/run_report.py --period month --anchor 2026-09-15
d:/confluence-scaffold/.venv-1/Scripts/python.exe scripts/run_strategy_advisor.py --stats-only
d:/confluence-scaffold/.venv-1/Scripts/python.exe scripts/setup_review_poc.py
d:/confluence-scaffold/.venv-1/Scripts/python.exe scripts/import_trade_ledger.py <xlsx> [--dry-run] [--strategy <id>]
```

## 6. Adding a strategy

1. Write the rules as markdown with numbered `## n. Title` headings into
   `data/knowledge_base/`.
2. Add a JSON config to `data/strategies/` giving its id, name, document path, keyword and
   routing tables, thresholds and flag sections.
3. Restart the app. No code change.

Keyword routing is substring matching, so a keyword must not be able to appear inside an
unrelated word. `ob` matches "problem" and "job"; `grade` matches "A-grade".

## 7. Known limits

1. Row-level quote precision varies with section complexity. See
   [eval_pipeline_and_results.md](eval_pipeline_and_results.md).
2. Some runs need the length-cap retry for specific sections.
3. `ENABLE_SIDE_CLASSIFICATION` is off, so the two-sided case ships unclassified until the
   eval is re-baselined.
4. The dead-zone rule check reports NOT CHECKABLE because session is not logged per trade.
5. Reports cannot break down by entry model, session or zone grade: those fields are
   populated for none of the logged trades.

## 8. Related documents

| Document | Covers |
|---|---|
| [foundations.md](foundations.md) | How the technology works, from tokens to LangGraph |
| [precedent.md](precedent.md) | Precedent from the trade log in Setup Review |
| [reports.md](reports.md) | The period report |
| [trade_store_and_advisor.md](trade_store_and_advisor.md) | Schema decisions and the advisor's flags |
| [eval_pipeline_and_results.md](eval_pipeline_and_results.md) | Quality measurement |
| [product_plan.md](product_plan.md) | The original plan, superseded in places |
