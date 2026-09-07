# Product Backlog & Sprint Plan — Confluence

Companion to README.md (architecture) and the MVP defined there (§6). This is the backlog broken into buildable items, plus Sprint 1 scoped to be finishable in one day.

## How this is organized

Epics map to the MVP components. Size is rough effort (S = under 1h, M = 1-3h, L = half day+). "MVP" column: **Y** = in the MVP as defined, **L** = later (v1.1/Phase 2+, listed for completeness so nothing gets lost, not for tomorrow).

## Epic A — Environment & Infrastructure

| # | Item | Size | MVP |
|---|---|---|---|
| A1 | Python project scaffold: venv, `requirements.txt` (langchain, langgraph, chromadb, ollama client) — **done**, embeddings moved to Ollama-served `bge-m3` instead of sentence-transformers, see README §5 | S | Y |
| A2 | Install Ollama, pull `llama3.1:8b-instruct` (or `qwen2.5:7b-instruct`) and `bge-m3` (embeddings), confirm both run and respond on your RTX 4060 | S | Y |
| A3 | Pull `qwen2.5:14b-instruct` (q4) for the heavier Report/Advisor tier, confirm it loads (partial offload expected) | S | L — only needed once Reports/Advisor are built |
| A4 | Repo folder structure per README §5/§6 (`app/`, `data/`, `scripts/`) | S | Y |

## Epic B — Strategy Knowledge Base

| # | Item | Size | MVP |
|---|---|---|---|
| B1 | Write Nabil v3 rules as structured markdown (multi-timeframe bias, zone grading, two entry models + velocity rule, liquidity/sessions, stop placement, 3RR minimum, partial-TP, news filter, the break-and-go open gap) | M | Y |
| B2 | Chunking script: section-aware split of B1 into rule-cluster chunks | S | Y |
| B3 | Embedding + ingestion script: embed chunks via Ollama (`bge-m3`), store in Chroma | S | Y |
| B4 | Manual retrieval sanity check: run 4-5 sample queries, confirm the right rule chunk comes back | S | Y |
| B5 | Add BM25 keyword index alongside B3, combine into hybrid retrieval | M | L (v1.1) |

## Epic C — Structured Trade Store & Backfill

| # | Item | Size | MVP |
|---|---|---|---|
| C1 | Finalize SQLite schema (README §4.2 fields — confirm/adjust before writing) | S | Y |
| C2 | Manual backfill of your ~20 journal trades into the schema (one-off, hand-cleaned — not a general parser) | M | Y |
| C3 | Basic query helpers: fetch by date range, fetch "similar" (same zone grade + entry model) | S | Y |
| C4 | General-purpose journal parser (auto-extract structured fields from future daily markdown entries) | L | L (v1.1+) |

## Epic D — Setup Review

| # | Item | Size | MVP |
|---|---|---|---|
| D1 | Core loop: setup description (text) → retrieve rule chunks (Epic B) → LLM answer with citations | M | Y — **this is Sprint 1's target** |
| D2 | Add similar-past-trades lookup (Epic C3) into the prompt context | S | Y |
| D3 | Wrap as a LangGraph graph (parse → retrieve → validate → recommend nodes) instead of a linear script | M | Y |
| D4 | Two-sided support/risk case output shape | S | Y |
| D5 | Forming/pre-trigger setup status (unknown-field handling, sequence-aware retrieval) | L | L (v1.1) |

## Epic E — Reports

| # | Item | Size | MVP |
|---|---|---|---|
| E1 | Stats function: win rate, RR planned vs. achieved, entry-model/session/zone-grade breakdown, given a date range | M | Y |
| E2 | LangGraph wrapper: fetch → compute (E1) → LLM narrates the numbers | S | Y |
| E3 | Daily/weekly/monthly are the same code path with different date ranges — no extra work beyond E1/E2 | — | Y |

## Epic F — Strategy Advisor

| # | Item | Size | MVP |
|---|---|---|---|
| F1 | Whole-strategy stats + rule-based flags (RR<3 trades taken, dead-zone entries, etc.) | M | Y |
| F2 | LangGraph wrapper: compute (F1) → retrieve relevant strategy notes → LLM narrates findings | S | Y |
| F3 | Segment-level mismatch mining (win rate per zone-grade × entry-model × session, diffed against rules) | L | L — needs more logged trades to be meaningful |
| F4 | Cold-start mode: frameworks reference KB + drafting flow | L | L (Phase 2) |

## Epic G — Streamlit UI

| # | Item | Size | MVP |
|---|---|---|---|
| G1 | Single-page app, 3 tabs: Review / Reports / Advisor | M | Y |
| G2 | Wire each tab to its LangGraph graph (D3, E2, F2) | M | Y |
| G3 | Show raw stats table under generated reports (grounding-check UI, per README §4.6) | S | Y |

## Epic H — Later (not in MVP, tracked so it isn't lost)

Screenshot/vision input for Setup Review, TradingView Pine Script indicator integration, ICT market-structure ML project as a retrieval source, Docker packaging/deployment, general journal parser (C4), hybrid retrieval (B5), segment-level Advisor critiques (F3), cold-start Advisor (F4).

---

## Sprint 1 — Tomorrow

**Goal:** prove the core RAG loop actually works before building anything else on top of it — type a real setup description, get back an answer grounded in your actual Nabil v3 rules, with citations you can verify against the source text. No trade store, no LangGraph branching, no UI yet. If this doesn't produce trustworthy, well-grounded answers, everything downstream (Reports, Advisor) needs to be reconsidered before more time goes into them — so this is deliberately the first and only thing in Sprint 1.

**Not in scope for tomorrow** (all correctly sequenced later per the backlog above): trade store/backfill, similar-trades lookup, two-sided case formatting, LangGraph graph structure, UI, Reports, Advisor.

| Task | From | Est. |
|---|---|---|
| Environment: venv, install deps, Ollama running with your chosen model | A1, A2 | 45 min |
| Write Nabil v3 rules as markdown KB (I can draft this now from what you've already told me, so tomorrow starts at review/fix instead of writing from scratch — see note below) | B1 | 45 min (mostly review if pre-drafted) |
| Chunk + embed + store in Chroma | B2, B3 | 60 min |
| Retrieval sanity check with 4-5 sample queries | B4 | 30 min |
| Core loop: setup text in → retrieve → LLM answer with citations, as a plain script (no graph yet) | D1 | 90-120 min |
| Test against 3 real setups from your own trading, check the citations actually match your rules | — | 45 min |
| Note what broke / what to fix — feeds Sprint 2 | — | 15 min |

**Total: ~5-6 hours**, leaves buffer for Ollama/dependency issues, which are the most likely source of delay on a first setup.

**Sprint 2 (not tomorrow, next session):** D2-D4 (similar trades, LangGraph wrapping, two-sided case) — turns Sprint 1's proof-of-concept script into the actual MVP Setup Review feature.

**Offer:** I can draft the Nabil v3 markdown KB (B1) right now, from what's already in our conversation, so tomorrow you're reviewing/correcting it rather than writing it from scratch — that alone would free up ~30-40 minutes of the sprint. Say the word and I'll do it before tomorrow.
