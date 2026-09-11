# Product plan (original)

**This is the planning document written before any code existed.** It is kept for the
reasoning it records: why each technology was chosen, what the MVP was scoped to, and which
questions were open at the time.

It is not a description of the system as built. For that, see [the README](../README.md).

Where the two disagree, the README is current. Known divergences:

1. **Section 4.2 (trade schema)** is superseded. The real Trade Ledger export contradicted
   it; see [trade_store_and_advisor.md](trade_store_and_advisor.md) section 3.
2. **Section 5 (tech stack)** lists Chroma and `bge-m3`. Neither is used: the strategy
   document is small enough to inject whole, so retrieval was cut.
3. **Section 9 (getting started)** describes Sprint 1 and is historical.

Sections 4.7b (small-sample honesty) and 6 (MVP scope) are still referenced by the code and
the other documents, which is the main reason this file is preserved rather than deleted.

---

Personal AI trading assistant that grounds every recommendation in your own written strategy rules (Nabil v3) and your own trade history, and turns your trade log into daily / weekly / monthly reports. No code yet — this document is the breakdown we agreed on before writing a single file.

## 1. What this actually is

Not a signal generator. It never decides FOR you. Three jobs:

1. **Setup Review** — you describe a setup, whether it's already fully triggered or still forming (e.g. price is approaching a zone but the sweep/CHoCH/FVG sequence hasn't happened yet). The system retrieves the rules that apply and gives you a two-sided read: the case for it (what's aligned — zone grade, session, structure so far) and the case against it (what's still missing, what would invalidate it, what could make it something other than what it looks like — e.g. a break-and-go instead of a retracement). It's not a pass/fail stamp; it's "here's why this could work and here's specifically how it could fail," so you can decide with both sides in view.
2. **Reporting** — turns your logged trades into grounded daily/weekly/monthly reports: win rate, RR planned vs. achieved, rule-adherence, session and entry-model breakdowns. Numbers come from your data, never from the LLM's memory.
3. **Strategy Advisor** — two modes: (a) if you don't have a strategy defined yet (new instrument, new market, starting over), it helps you draft one from established frameworks rather than from nothing; (b) if you already have one and it's underperforming or has a known gap, it mines your trade history for the specific weak points and proposes concrete rule changes — not "trade better," but "your Model B entries taken outside the NY killzone are losing at X% vs Y% inside it, here's the rule change to consider."

Everything the LLM says has to trace back to either a retrieved rule chunk, a retrieved framework reference, or a computed stat. If none of those exist, it has to say "not enough information" instead of guessing — this is the whole point of doing RAG instead of just chatting with a model.

## 2. Decisions already made

| Decision | Choice | Why |
|---|---|---|
| Setup input | Text/structured first | You type the setup (instrument, session, bias, zone grade, entry model, RR). No vision model, no OCR, ships fast. |
| Screenshots | Phase 2 | Pipeline is designed so a vision step can slot in later without a rewrite (see §6). |
| Interface | Streamlit | One Python app, no separate frontend/backend split needed for a single-user tool. |
| LLM | Open-source, self-hosted via **Ollama** | RTX 4060 confirmed → assuming the 8GB VRAM variant (both desktop and laptop 4060 ship with 8GB; only the 4060 Ti has a 16GB option — say if yours is different). Two-tier setup: **`llama3.1:8b-instruct`** (or `qwen2.5:7b-instruct` — better German handling, worth A/B testing) fully in VRAM for the interactive Setup Review chat, where latency matters; **`qwen2.5:14b-instruct` q4** as a heavier option for Reports and Strategy Advisor, which run less often and can tolerate the slower speed from partial CPU offload at 8GB. Both swappable later for a hosted open-weight API if local speed frustrates you. |
| Trade log | New structured store, backfilled from your journal | You have ~20 trades in the existing git-journal — that's little enough, and valuable enough, to import as a one-time backfill in Phase 1 rather than deferring it. Once you're ready to build, send the journal (files or the repo) and step one is writing the parser that extracts the structured fields (§4.2) from your daily markdown into the new store. |

## 3. Architecture

```
                         ┌─────────────────────────┐
                         │   Strategy Knowledge     │
                         │   Base (Nabil v3 rules,  │      one-time / on-edit
                         │   markdown, versioned)   │◄──── ingestion
                         └────────────┬─────────────┘
                                      │ chunk + embed
                                      ▼
                         ┌─────────────────────────┐
                         │   Vector Store (Chroma) │
                         │   + BM25 keyword index  │  hybrid retrieval
                         └────────────┬─────────────┘
                                      │
   ┌──────────────┐   setup text     │ retrieved rule chunks
   │   Streamlit  │─────────────────►│
   │      UI      │                  ▼
   │              │        ┌───────────────────────┐
   │              │        │   LangGraph: Setup     │
   │              │◄───────│   Review Agent         │
   │              │  recommendation + citations     │
   │              │        └───────────────────────┘
   │              │
   │              │        ┌───────────────────────┐
   │              │  ask   │   LangGraph: Report    │
   │              │───────►│   Agent                │
   │              │◄───────│  (reads structured DB, │
   │              │ report │  computes stats first, │
   │              │        │  LLM narrates them)    │
   │              │        └───────────┬───────────┘
   │              │                    │
   │              │        ┌───────────▼───────────┐
   │              │  ask   │  LangGraph: Strategy   │
   │              │───────►│  Advisor Agent         │
   │              │◄───────│  (segments stats by    │
   └──────────────┘ advice │  rule dimension, or    │
                            │  drafts a new strategy │
                            │  from frameworks KB)   │
                            └───────────┬───────────┘
                                        ▼
                         ┌─────────────────────────┐
                         │  Structured Trade Store  │
                         │  (SQLite) — one row per  │
                         │  logged trade            │
                         └─────────────────────────┘
```

Three separate LangGraph graphs, not one monolithic agent — Setup Review, Reporting, and Strategy Advisor have different failure modes and different grounding sources (single-instance rules vs. aggregate numbers vs. cross-referencing numbers against rules), so keeping them as separate graphs makes each easier to debug and test.

## 4. Component breakdown

### 4.1 Strategy Knowledge Bases (RAG sources #1 and #3)
Two separate corpora, kept apart so retrieval doesn't blur "your rules" with "general frameworks":
- **Your strategy KB** (used by Setup Review, Reporting, and Strategy Advisor mode (b)) — described below.
- **Frameworks reference KB** (used only by Strategy Advisor mode (a), cold-start) — a small curated corpus of general strategy frameworks and risk-management fundamentals, kept separate so a cold-start draft never gets contaminated with rules from a strategy for a different instrument/style.

- Your Nabil v3 rules written up as structured markdown: multi-timeframe bias (Daily/1H/15M/1M), zone grading (A/B/C), the two entry models (Confirmation vs. Location) and the velocity rule that picks between them, liquidity/session rules, stop placement, the 3RR minimum, partial-TP management, the news filter.
- Section-aware chunking (one chunk per rule cluster, not fixed-size windows) — these rules are short and precise; splitting mid-rule would break retrieval.
- Explicitly flagged as an **open gap** in the knowledge base: no entry model exists yet for "break-and-go" markets. The agent should say so rather than inventing a rule when a setup looks like that.

### 4.2 Structured Trade Store (RAG source #2, and the reporting source of truth)
Proposed schema per trade (SQLite table, adjust before we build it):

`date, instrument, session (Tokyo/London/NY-killzone/dead-zone), daily_bias, htf_zone_grade (A/B/C), entry_model (confirmation/location), sweep_before_fvg (bool), rr_planned, rr_achieved, outcome (win/loss/BE), stop_moved (bool), notes`

This is what daily/weekly/monthly reports query — never the LLM's own numbers.

### 4.3 Retrieval layer
Hybrid: dense embeddings (multilingual, since your rules mix German/English) + BM25 keyword match. Trading vocabulary (CHoCH, FVG, PDH/PDL) needs exact keyword hits that pure semantic similarity sometimes misses — hybrid retrieval covers both.

### 4.4 Setup Review graph (LangGraph)
1. Parse your free-text setup into structured fields (instrument, session, claimed/observed zone grade, claimed entry model, RR if known, and — importantly — a **status** field: `triggered` vs. `forming`). A forming setup will have some fields still unknown (e.g. "sweep happened, CHoCH not confirmed yet, waiting on FVG") — the parser has to represent "not yet known" rather than forcing a guess.
2. Retrieve the specific rule chunks relevant to the fields that ARE known, plus the rules governing whatever comes next in the sequence (e.g. if sweep just happened, retrieve the CHoCH/FVG/entry rules for what should happen after).
3. Build the two-sided case instead of a single verdict:
   - **Supporting case**: which known facts align with the rules — right zone grade, right session/killzone, correct sequence so far, liquidity pool identified correctly.
   - **Risk/invalidation case**: what's still unconfirmed and would need to happen for the setup to remain valid (e.g. "still needs CHoCH before this is a valid Confirmation entry"); what would specifically invalidate it (e.g. price closing back through the zone, the move looking like a break-and-go rather than a retracement — the known strategy gap from §4.1); RR risk if the stop ends up needing to go past a further liquidity pool; any rule not yet checkable from the input (e.g. news filter).
4. Pull similar past trades from the structured store (same zone grade + entry model, and same forming/triggered pattern if you've logged near-misses) so both sides of the case reference your own track record, not just the rulebook — confirmed as a standard step, not optional. With only ~20 trades logged so far, "similar" will often mean 1-3 matches rather than a solid sample; the response should surface those specific past trades (not a stat) rather than imply a trend that isn't there yet.
5. Compose the response as the two-sided case with explicit citations to the rule for each point — never a bare "take it" / "skip it," and never silent about what's still unknown when the setup is still forming.

### 4.5 Report graph (LangGraph)
1. Fetch trades for the requested period from SQLite.
2. Compute stats in code (win rate, RR planned vs. achieved, rule-violation count, distribution by zone grade/entry model/session) — deterministic, no LLM involved in the arithmetic.
3. Retrieve any strategy notes worth surfacing (e.g. reminding you of the break-and-go gap if it shows up in the period).
4. LLM narrates the computed numbers into a readable report. It's given the numbers, not asked to recall or estimate them.

### 4.6 Streamlit UI
Three views: "Review a setup" (text form → recommendation), "Reports" (pick day/week/month → generated report + the raw stats table underneath it, so you can verify the LLM didn't drift from the numbers), and "Strategy Advisor" (see below).

### 4.7 Strategy Advisor graph (LangGraph) — new
Two distinct entry points, because "I have no strategy" and "my strategy has a hole in it" need different grounding:

**(a) Cold-start (no strategy yet).** Needs its own small knowledge base — a curated set of established framework references (trend-following, mean-reversion, breakout, SMC/ICT, position-sizing and risk-management fundamentals) so the LLM is drafting from real trading literature, not inventing rules from nothing. Flow: ask about instrument/market, timeframe, risk tolerance, and trading style preference → retrieve matching framework chunks → draft a first-version rule set in the same structured format as §4.1, flagged clearly as a starting draft to be tested, not gospel.

**(b) Critique/improve (strategy exists, e.g. Nabil v3).** This is the higher-value mode given where you actually are. Flow: pull the same segmented stats the Report graph computes (win rate by zone grade, by entry model, by session, by RR bucket) → diff the weak segments against what the current rules say should happen there → surface the specific mismatches ("Model B outside NY killzone: 20% win rate over 12 trades vs. 65% inside it — rule doesn't currently restrict Model B by session") → propose a concrete rule amendment, not just a diagnosis. Every claim is a specific number from your own data, tied to a specific existing rule; a segment with too few trades to be meaningful (e.g. under ~10) is called out as inconclusive rather than acted on, so the advisor doesn't overfit rule changes to a handful of trades.

With ~20 trades total to start, most individual segments (zone grade × entry model × session, sliced three ways) will land under that threshold immediately — normal for day one, not a flaw in the design. Early on the advisor should mostly say "not enough data on X yet" and lean on whole-strategy-level observations (overall win rate, overall RR discipline) rather than fine-grained segment critiques; it gets more precise as the log grows. Worth being upfront with you about this rather than having it manufacture confident-sounding advice off 2-3 trades per bucket.

Rule changes it proposes are never auto-applied to §4.1's knowledge base — you review and merge them in, so the strategy doc stays something you authored, with the advisor's suggestions as changelog entries you accepted or rejected.

## 5. Tech stack (with the alternatives considered)

| Layer | Choice | Alternatives considered | Why this one |
|---|---|---|---|
| Vector DB | Chroma | Qdrant, pgvector, Pinecone | Local, file-based, zero infra for a single-user tool. Qdrant is the upgrade path if this ever needs multi-user or filtering at scale; Pinecone/pgvector don't fit "self-hosted, private" as cleanly here. |
| Embeddings | `bge-m3` served through Ollama | `intfloat/multilingual-e5-base` via sentence-transformers, OpenAI `text-embedding-3` | Local/free and multilingual (your notes mix German and English). Serving it through Ollama alongside the chat model means one runtime for both, and it skips installing a separate sentence-transformers/torch stack — confirmed while checking `requirements.txt` in A1: that route pulls torch's full CUDA dependency set (multiple GB) just to embed text. |
| LLM serving | Ollama (local) | Together/Groq hosted open-weight, vLLM self-hosted | Simplest local setup; vLLM is the upgrade if you get a real GPU box and want throughput; hosted APIs are the fallback if local inference is too slow for interactive use. |
| Orchestration | LangGraph | Plain LangChain chains | You need branching/validation logic (zone grade checks, conditional retrieval) — graph state machine fits better than a linear chain. |
| Trade store | SQLite | Postgres, flat JSON | Single user, single machine, zero setup; trivial to move to Postgres later if this grows. |
| UI | Streamlit | FastAPI + custom frontend | Matches your "streamlit web app" choice — fastest path to something usable daily. |

## 6. MVP — the actual first build

"Phase 1" above was already everything you want long-term minus the deferred phases; it's not an MVP, it's the full v1 feature set. An MVP is narrower on purpose: the smallest slice that proves the core idea — grounded advice instead of generic LLM guessing — actually works, before investing in the more sophisticated parts. Cutting scope here isn't losing features, it's sequencing them so we validate cheap assumptions before building expensive ones on top.

**In the MVP:**

| Piece | MVP version | Why this is enough to start |
|---|---|---|
| Strategy KB | Nabil v3 rules as markdown, chunked, embedded, **dense retrieval only** | Hybrid (dense+BM25) is a retrieval-quality upgrade you add once you've actually seen dense-only miss an exact term like "CHoCH" — not a day-one requirement. |
| Trade store | SQLite, core schema, **one-time backfill from your ~20-trade journal** (manual cleanup allowed — it's a 20-row job, not worth a general-purpose parser yet) | Without this, Setup Review has zero trades to reference and Strategy Advisor has zero data — this single step unlocks both other features, so it's the first thing built, not an afterthought. |
| Setup Review | Text input, **triggered setups only** (defer forming/pre-trigger status), two-sided support/risk case, always pulls similar past trades | The two-sided output is a prompting decision, cheap to include. The forming-setup status field (parsing "unknown yet" fields, sequencing logic) is real added complexity — worth doing once the triggered-case version is proven to give useful, correctly-cited answers. |
| Reports | Daily/weekly/monthly, same stats function with a different date range | No reason to cut two of three — it's the same code path, not three separate features. |
| Strategy Advisor | Critique mode only, **whole-strategy stats + rule-based flags** (e.g. "3 trades taken below 3RR", "2 trades in the dead zone") — not fine-grained segment mining | With 20 trades, segment-level diffing (win rate for one specific zone-grade × entry-model × session combo) would mostly return "not enough data" anyway, per §4.7b. Ship the version that's honest about that; add segment mining once the log has enough volume to make it real. |
| UI | Streamlit, one page, tabs for the three functions, no polish | Function over form until the pipeline is proven. |

**Deliberately cut from MVP** (each is a real feature, just sequenced later): forming/pre-trigger setup handling in Setup Review, hybrid retrieval, segment-level Strategy Advisor critiques, Strategy Advisor cold-start mode, screenshot/vision input, backfill importer generalized beyond your current journal.

## 7. Phased roadmap (after the MVP)

- **v1.1:** forming/pre-trigger setup status in Setup Review; hybrid (dense+BM25) retrieval; segment-level Strategy Advisor critiques once trade volume supports it.
- **Phase 2:** screenshot/chart input (vision model or OCR + chart-reading prompt) feeding the same Setup Review graph; Strategy Advisor cold-start mode (a) and its frameworks reference KB, if/when you need to draft a strategy for a different instrument.
- **Phase 3:** hook in the TradingView Pine Script indicator you're building, and/or the ICT market-structure ML project, as an additional signal source feeding retrieval context.
- **Phase 4:** packaging/deployment (Docker) if you want it running somewhere other than your own machine.

## 8. Open questions before we start building

1. ~~Ollama assumption~~ — **resolved**: RTX 4060 (8GB assumed), two-tier model plan in §2.
2. Trade store schema in §4.2 — still open: anything to add/remove (e.g. do you want to log the liquidity pool targeted, or partial-TP fills)?
3. ~~Similar past trades in Setup Review~~ — **resolved**: yes, always on (§4.4 step 4).
4. ~~Trade volume for Strategy Advisor~~ — **resolved**: ~20 trades in your existing journal, to be backfilled in Phase 1 (§2, §4.7b). Still open: what format is the journal in — plain prose per day, or does it already have any consistent structure (headers, a table, tags) I can anchor a parser on? Easier to design the importer once I've actually seen a sample day or two.
5. For the cold-start frameworks KB (§4.7a) — deferred to Phase 2 by default above — say now if you actually want it in Phase 1 (e.g. because you're planning a strategy for a different instrument soon).

## 9. Getting started (Sprint 1 / A1 — done)

Repo scaffold exists: `app/{core,ingestion,retrieval,generation,models,services}`, `data/{knowledge_base,trades,vector_store}`, `scripts/`, `tests/`, `config/`, plus `requirements.txt`, `.env.example`, `.gitignore`.

`requirements.txt` was dependency-resolved twice before settling: the first pass (`langchain`, `langgraph`, `chromadb`, `sentence-transformers`, per the original A1 backlog line) resolved cleanly but pulled torch's full CUDA stack (multiple GB of `nvidia-*` packages) just to run the embedding model. Since you're serving the chat model through Ollama anyway, switching embeddings to Ollama's `bge-m3` (multilingual, so it handles the German/English mix) removes sentence-transformers/torch from the dependency tree entirely — one runtime doing both jobs, much lighter install. Updated in §5's tech stack table.

To set this up on your machine (A2, next):

```bash
python -m venv .venv
# Linux/macOS:
source .venv/bin/activate
# Windows (PowerShell):
.venv\Scripts\Activate.ps1

pip install -r requirements.txt
cp .env.example .env

# Ollama models — one-time pull
ollama pull llama3.1:8b-instruct   # or qwen2.5:7b-instruct
ollama pull qwen2.5:14b-instruct   # heavier tier, Reports/Advisor — can wait until you reach Epic E/F
ollama pull bge-m3                 # embeddings
```

Once `pip install` and the Ollama pulls finish without errors, A1 and the first half of A2 are done — say so and we move to writing the Nabil v3 strategy markdown (B1), which is the next thing Sprint 1 actually needs.

## 10. Next step

When you're ready to start, send over the journal (or a couple of sample days of it) so the backfill importer can be designed against real formatting rather than guesses, and settle §8.2 and §8.5. Build order follows §6: repo scaffold (done) → strategy KB seeded from Nabil v3 → SQLite schema + backfill importer → Setup Review graph (triggered-only) → Report graph → Strategy Advisor (whole-strategy stats) → Streamlit UI wiring the three together. Everything in the "deliberately cut" list stays out until the MVP is working end to end.
