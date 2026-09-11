# Foundations — how this app works, and how the technology underneath it works

This document is for understanding, not reference. It explains each technology from the
ground up, then shows exactly where this codebase uses it and why. Read it top to bottom
once; after that the other documents will make sense.

The through-line: **a language model is fluent, not truthful. Everything in this system is
arranged so the model is given the smallest possible job, and so that whatever it says can
be checked against something that is not a model.**

---

## 1. The problem this app exists to solve

You could paste your strategy into ChatGPT and ask "is this setup valid?" It would answer
confidently. The problem is you would have no way to tell a correct answer from a
confident-sounding wrong one, and no way to tell which of your rules it actually applied.

Three failure modes matter here:

1. **Invention.** The model states a rule your document does not contain.
2. **Misattribution.** The model quotes a real rule, but the wrong one for this situation.
3. **Silent failure.** Something breaks and the answer reads like "your rules don't cover
   this" instead of "I failed."

For trading decisions, the third is the dangerous one, because it looks like information.

Everything below is a response to those three.

---

## 2. Layer one: the language model

### What it actually does

A large language model is a next-token predictor. Given a sequence of tokens, it outputs a
probability distribution over what comes next, samples one, appends it, and repeats. That is
the whole mechanism.

A **token** is a subword chunk, not a word. "CHoCH" might be three tokens; "the" is one.
Roughly four characters per token in English — which is why this codebase estimates token
counts as `len(text) // 4` in `_estimate_token_count`.

### Why it hallucinates

Nothing in that mechanism represents truth. The model produces what is *plausible* given the
training data and the prompt. A fabricated quote from your strategy document is just as
plausible-looking as a real one, because "plausible" means "statistically typical text", not
"grounded in the document above."

This is not a bug to be prompted away. It is what the machine does. The engineering response
is not to ask nicely; it is to **verify the output against a source the model cannot
influence.** That is the single most important idea in this codebase.

### Context window

The model can only see a fixed number of tokens at once — prompt plus generated output. In
Ollama this is `num_ctx`. If the prompt is larger, the earliest content is lost.

This is the constraint that creates the entire field of retrieval: if your knowledge does not
fit in the window, you must select what goes in.

In this app, `OLLAMA_NUM_CTX_MATCH` defaults to 4096 tokens, and there is a cap
(`OLLAMA_NUM_CTX_MATCH_CAP`) because a larger window costs proportionally more VRAM and time.

### Output length

`num_predict` caps how many tokens the model may generate. This exists to prevent a runaway
answer, but it creates a failure mode this codebase handles explicitly: a model can burn its
entire generation budget on hidden reasoning and return *nothing visible*. You will see this
in the logs as:

```
[length-debug] len=0 preview=''
[length-retry] escalating generation cap to 1536
```

`_invoke_with_retry` detects `done_reason=length` with empty content and retries once at a
higher cap. Without that, a silent empty answer would be indistinguishable from "no rule
applies" — failure mode three.

### Temperature

Temperature controls how sharply the model favours its top prediction. 0 is nearly
deterministic; 1.0 is loose and creative. This codebase uses **0.1 everywhere** — you want
the same setup to produce the same read, not variety.

### Reasoning models and `/no_think`

Some models (qwen3, deepseek-r1) generate a hidden chain of thought before answering, wrapped
in `<think>...</think>`. That costs time and tokens. `/no_think` on the first line suppresses
it, and `_sanitize_model_text` strips any that leaks through anyway.

This is a good example of defensive layering: suppress it, *and* handle it if suppression
fails.

### Local models, quantization, and VRAM

A model's weights are numbers. At full precision each is 16 bits; an 8-billion-parameter
model would need ~16GB just to load. **Quantization** stores them at lower precision —
`q4_K_M` means roughly 4 bits per weight with a mixed-precision scheme — which cuts that to
about 5GB at a modest quality cost.

This is why `qwen3:8b` is ~5GB on disk and in VRAM. And it is why the two-model default
configuration does not fit your 8GB card: two 5GB models plus ~2GB of desktop usage needs
about 10GB against roughly 5.8GB free. When that happens, `llama-server` is killed and the
whole Ollama service can go down.

### What Ollama is

Ollama is a local server that loads model weights and exposes an HTTP API. It is the same
role a hosted API plays, running on your machine. Relevant controls:

- **`keep_alive`** — how long a model stays resident after a call. This codebase uses `10m`
  so a run of many small calls does not reload the model each time. The cost is that the
  model *stays* in VRAM, which is exactly what starves the second model.
- **Warmup** — `warm_match_model` makes one throwaway call so the first real call is not
  paying the load cost inside a timeout.

`langchain_ollama.ChatOllama` is a thin client over that API.

---

## 3. Layer two: making output machine-readable

A model returns prose. Code needs fields. Bridging that gap reliably is most of the work.

### The output contract

`MATCH_FACT_PROMPT` demands exactly this shape:

```
Quote: "<exact text from the section>"
Implication: <one or two sentences>
```

Narrow output is easier to parse, easier to verify, and leaves less room to wander.

### Parsing defensively

Models drift from any format, so `_extract_field_value` handles: markdown bold (`**Quote:**`),
curly quotes (`"` vs `"`), leading list markers, and a loose fallback if the strict line
match fails. `_normalize_structured_response` then rebuilds a clean, known-shaped string.

**The lesson that transfers:** never trust the format. Parse leniently, then re-emit strictly,
so everything downstream sees one shape.

### Guards

Two checks reject technically-valid but useless answers:

- **Heading guard** — a quote starting with `#` or ending with `:` is a section title, not a
  rule. Rejected.
- **Table row guard** — `_expected_table_column_count` counts columns in the section's table;
  a quote with fewer is a truncated row. Rejected.

Both downgrade to `NOT_COVERED` rather than being accepted.

---

## 4. Layer three: grounding — the core discipline

### Quote verification

`find_unverified_quotes` takes what the model claimed to quote, normalises whitespace and
markdown, and checks the text **actually appears in the section it was given**. If not, the
output is flagged `UNVERIFIED`.

This is what makes the difference between "the model says your rules say X" and "your rules
say X, here is the line." The model cannot fake it, because the check does not ask the model.

### Status semantics, and the rule that matters most

Four statuses, in `setup_review_poc.py`:

| Status | Meaning |
|---|---|
| `OK` | Evaluated, structured evidence returned |
| `NOT_COVERED` | The routed section genuinely offers no governing rule |
| `NOT_ROUTED` | The router deliberately made no call |
| `ERROR` | Runtime or model failure |

**`ERROR` is never collapsed into `NOT_COVERED`.** A timeout must not read as "your strategy
has nothing to say about this." That is failure mode three, and the whole status model exists
to prevent it.

### Fail-closed

`build_stage3_verdict`: any `ERROR` means the setup cannot be reviewed at all. Any unanswered
unknown means `INCOMPLETE`. Only a clean run is `COMPLETE`.

"Fail-closed" means **uncertainty produces refusal, not a guess.** The opposite — fail-open —
would let a crashed check pass silently.

### Compute, then narrate

For anything numeric, the model is not asked to calculate. `trade_stats.py` computes win
rates, net R and rule violations in Python; the model is handed the finished numbers and asked
only to phrase them.

Even that is checked — `find_ungrounded_numbers` compares every number in the narrative
against the computed findings. **And it is worth knowing its limit**, because it teaches
something: the check tests *set membership*. A number appearing anywhere in the findings
passes, even when the narrative attaches it to the wrong claim. Observed in practice: the
model wrote "Five sub-60-score trades (4W/3L)" against a computed 2W/3L and the check passed,
because 4 and 3 both appear elsewhere.

So: it catches invention, not misattribution. A guard you understand the limits of is worth
far more than one you trust blindly.

---

## 5. Layer four: retrieval and RAG

### What RAG actually is

Retrieval-Augmented Generation is three steps:

1. **Retrieve** — select relevant text from a corpus.
2. **Augment** — put that text into the prompt.
3. **Generate** — have the model answer using it.

That is all. There is no magic. RAG exists for three reasons: the corpus does not fit in the
context window; it changes more often than the model is trained; and having the source text
in the prompt lets you demand citations you can verify.

### Embeddings — the part worth understanding properly

An **embedding model** converts text into a fixed-length list of numbers — a vector, often
1024 dimensions. It is trained so that text with similar *meaning* lands at nearby points.

"Price swept the low then reversed" and "liquidity grab followed by reversal" share almost no
words, but a good embedding places them close together. That is the entire value proposition:
matching on meaning rather than spelling.

**Similarity** is usually cosine similarity — the angle between two vectors. Same direction
means similar meaning, regardless of magnitude.

So retrieval works like this: embed every chunk of your corpus once, store the vectors; at
query time, embed the question and find the nearest stored vectors.

`bge-m3` is the embedding model planned here — multilingual, which matters because the
original notes mix German and English.

### Chunking — the hard part

You cannot embed a whole book as one vector; meaning would be averaged into mush. So the
corpus is split into chunks, each embedded separately.

Chunking is where RAG systems usually fail. Too small and a rule loses the context that makes
it correct. Too large and the vector becomes unspecific.

**This is precisely why this app does not chunk your strategy document.** It is ~4,700 tokens
and its sections depend on each other — the scoring rubric needs zone grading, bias logic and
the structure-break criterion simultaneously. Chunking it would retrieve a rule *without what
makes it correct*. The project cut chunking (Epic B2/B3) for exactly this reason.

### Vector databases

A vector database — Chroma here — stores vectors with their source text and metadata, and
searches them quickly. At small scale you could do this with a loop and cosine similarity; a
vector DB adds approximate nearest-neighbour indexing, persistence and metadata filtering.

### Dense vs lexical, and hybrid

Embedding search is called **dense** retrieval. It matches meaning but can miss exact terms.
**BM25** is the classic lexical method — a TF-IDF descendant that scores documents by term
overlap, weighting rare words. It nails exact matches and understands no meaning at all.

Trading vocabulary is full of exact terms — CHoCH, FVG, PDH/PDL. **Hybrid** retrieval runs
both and merges. That is Epic B5/J6, deferred until dense-only is observed failing.

### What this app does instead — and why it is better here

**There is currently no RAG in this system.** No embeddings, no vectors, no Chroma. What the
`retrieve` node does is *deterministic keyword routing*:

```python
KEYWORDS = {"zone_grade": ["a-grade", "demand zone", ...], ...}
ROUTING_MAP = {"zone_grade": ["6"], "bias": ["3"], ...}
```

A fact mentioning "A-grade demand zone" routes to section 6. A hand-written lookup table.

This is retrieval-augmented generation in shape — select context, inject, generate — with a
lookup table as the retriever. And for this corpus it is **better** than vectors:

- The eval measures **55/55 section hits**. Embedding similarity would not guarantee that.
- "The keyword table sent this to §6" is auditable. "Cosine distance ranked §6 highest" is not.
- One small document needs no index.

**The transferable lesson: use the simplest retrieval that works. Reach for vectors when the
corpus is too large to enumerate, too unstructured to route by hand, or queried in ways you
cannot anticipate.**

### When this app will need real RAG

When a corpus appears that has those properties: a library of *other people's* trading
methodologies for the cold-start advisor. You did not write it, cannot hand-index it, and
queries against it are open-ended. That is Epic J, and it is the first honest use for Chroma
here.

---

## 6. Layer five: orchestration — LangGraph

### The problem it solves

A simple pipeline is a function calling functions. That works until you need branching,
retries, inspectable intermediate state, or loops — at which point control flow gets buried in
nested conditionals.

**LangGraph** models the pipeline as a state machine: a shared state object, nodes that
transform it, edges that define order.

### The three pieces

**State** — a `TypedDict` describing every field that flows through:

```python
class SetupReviewState(TypedDict, total=False):
    setup_description: str
    facts: list[str]
    routes: dict[str, list[str]]
    ...
```

**Nodes** — plain functions taking state and returning *only the fields they change*:

```python
def retrieve_node(state):
    sections = load_sections()
    return {"sections": sections, "routes": {...}}
```

LangGraph merges that partial return into the state. Nodes do not mutate; they describe a
delta.

**Edges** — the flow. `START → parse → retrieve → validate → recommend → END`.

### Why it is worth it here

The Setup Review graph is linear, so LangGraph buys no branching today. What it buys is
**inspectability**: the routing plan exists as `state["routes"]` before any model is called,
so you can see what the system decided to look at without running a single token of
inference. In a linear script that decision was buried inside a loop.

It also gives a natural place for the things that come next: conditional edges (skip
narration when nothing fired), loops (re-retrieve if quotes fail verification), and
checkpointing.

### The two graphs

```
Setup Review:      parse → retrieve → validate → recommend
Strategy Advisor:  compute → retrieve → narrate
```

Note the Advisor **computes before retrieving** — the statistics determine which strategy
sections are worth pulling. Order encodes intent.

---

## 7. Layer six: the data

**SQLite** is a database that is just a file — no server, no configuration. For a single-user
tool that is the right answer, and moving to Postgres later is mechanical.

The schema lesson here is one you will hit in your own project: **the plan specified fields
the real data did not have.** Session, zone grade, entry model and sweep-before-FVG were in
the design; the actual ledger export had none of them.

They are kept as nullable columns and **left NULL rather than inferred from the notes**,
because guessing would put invented data into exactly the store that reports are supposed to
be grounded in. The honest cost is visible in the product: the dead-zone rule check reports
`NOT CHECKABLE` instead of pretending.

---

## 8. Layer seven: the interface

**Streamlit** turns a Python script into a web app. Its model is unusual and worth
understanding: **on every interaction it re-runs your entire script top to bottom.** There is
no event handler; `if st.button(...)` is simply `True` on the run following a click.

Consequences you can see in this codebase:

- **Anything expensive must be cached.** `@st.cache_resource` holds the compiled graph and
  its model clients; `@st.cache_data` holds query results. Without these, every click would
  rebuild everything.
- **State must be explicit.** `st.session_state` survives reruns; local variables do not.
  Navigation lives there, which is why the app uses buttons rather than `st.tabs` — a tab's
  selection is client-side and was lost on every rerun, throwing you into another section
  whenever a filter fired.

---

## 9. Putting it together: one request end to end

You type: *"XAUUSD, daily bias bullish, H1 pulled back into an A-grade demand zone, swept the
low, no CHoCH yet."*

1. **UI** — Streamlit reruns, `st.button` returns `True`, the service is called.
2. **parse** — Stage 1 model call turns prose into facts and unknowns. *(model, once)*
3. **retrieve** — Python reads the strategy file, splits it into numbered sections, and routes
   each item by keyword. *No model.* "A-grade demand zone" → §6. Now visible in state.
4. **validate** — For each item-section pair, a narrow model call is made with **only that
   section** in the prompt, demanding a quote. The quote is verified against that section's
   text. Guards reject headings and partial rows. Each result gets a status.
   *(model, once per pair)*
5. **recommend** — Python composes the two-sided case from verified evidence only, and the
   fail-closed verdict from the statuses. *No model.*
6. **UI** — renders verdict, case, and per-item evidence.

Count the model calls: one to parse, one per routed pair, zero for the decisions. **Every
judgement that could be deterministic is deterministic.**

---

## 10. The principles worth stealing for your own build

1. **Give the model the smallest possible job.** Not "evaluate this setup" — "quote the line
   in this one section that applies to this one fact."
2. **Verify against something that is not a model.** A quote must appear in the source. A
   number must come from code.
3. **Distinguish failure from absence.** `ERROR` is not `NOT_COVERED`. Almost every system
   that quietly misleads people has collapsed those two.
4. **Fail closed.** When uncertain, refuse rather than guess.
5. **Determinism first, retrieval second, embeddings last.** Use the simplest selection
   mechanism your corpus allows.
6. **Parse leniently, emit strictly.** Absorb format drift at the boundary; keep one shape
   inside.
7. **Know what your guards do not catch.** A limitation you have written down is a feature; an
   assumption you have not tested is a liability.
8. **Say what you cannot answer.** `NOT CHECKABLE` and `INCONCLUSIVE` are product features,
   not gaps.

---

## 11. Where to go next in the code

| To understand | Read |
|---|---|
| Prompting, parsing, guards, verification | `scripts/setup_review_poc.py` |
| Section parsing (`parse_numbered_h2_sections`) and routing (`route`) | `scripts/setup_review_poc.py` |
| Graph structure and state | `app/graphs/setup_review_graph.py` |
| Compute-then-narrate, and the grounding check | `app/graphs/strategy_advisor_graph.py` |
| Deterministic statistics and rule checks | `app/services/trade_stats.py` |
| Schema decisions | `app/services/trade_store.py` |
| Streamlit rerun model and caching | `app/ui/` |
| How quality is measured | `scripts/eval_match.py`, `docs/eval_pipeline_and_results.md` |
