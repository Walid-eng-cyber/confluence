# Epic J — reference corpus, retrieval and recommendation

The first part of this system that performs retrieval-augmented generation over a corpus,
rather than deterministic routing over one document. This is the complete reference for the
epic: what is built, how it works, what is measured, and what remains.

For how embeddings and RAG work in general, read [foundations.md](foundations.md) section 5
first. This document is about this implementation.

---

## 1. Why Epic J exists

Everything else in this system retrieves by knowing the answer in advance. Setup Review's
router maps keywords to section numbers the trader authored. The Advisor pulls the sections
its own flags name. Both are lookup tables, and for one 4,700-token document that is
strictly better than embeddings: the eval measures 55/55 section hits, and "the keyword
table sent this to section 6" is auditable in a way cosine distance is not.

A reference corpus is different in three ways that all point at vector search:

1. **You did not author it**, so you cannot hand-write a routing table for it.
2. **It is open to growth** — methodology references, multiple frameworks, eventually more
   than fits in a context window.
3. **It is queried open-endedly.** "Which approach suits a range-bound instrument with no
   session liquidity" has no keyword that maps to a section number.

Every property that makes routing work for the strategy document is absent here. That is
what makes this the honest home for retrieval, and it is why the plan's Chroma and `bge-m3`
sat unused until now.

## 2. Item status

| # | Item | Status |
|---|---|---|
| J1 | Reference documents in markdown | Two written; more is additive |
| J2 | Section-aware chunking, embedding, storage | Done |
| J3 | Dense retrieval with scoring | Done |
| J4 | Recommendation: intake → retrieve → cited methodologies | **Not built** |
| J5 | Retrieval eval: fixed questions, expected sources, scored | **Not built** |
| J6 | Hybrid dense + BM25 | Deferred — but now justified, see section 8 |
| J7 | Cold-start rule drafting (this is F4) | Deferred |

## 3. Prerequisites, and a trap worth recording

Epic J needs an embedding model served by Ollama. Getting there exposed a machine-level
problem worth writing down, because the symptom was misleading.

`ollama pull bge-m3` **exited 0 and produced no output, and the model was not installed.**
The real cause: the C: drive was 100% full, zero bytes free. The same pull through
`/api/pull` reported it plainly:

```
max retries exceeded: ... -partial: There is not enough space on the disk.
```

Compounding it, the models were split across two stores. Ollama was serving
`C:\Users\walid\.ollama\models` (qwen3, deepseek-r1) while `OLLAMA_MODELS` in the registry
pointed at `D:\ollama\models`, which already held `bge-m3` plus llama3.1, llama3.2 and
qwen2.5. Each store held half of what the project needed.

Resolved by consolidating into D:, which is also backlog item A5:

1. Copy blobs and manifests from the C: store into D: (blobs are content-addressed, so
   copying without clobbering is safe).
2. Restart Ollama with `OLLAMA_MODELS=D:\ollama\models`.
3. Verify chat **and** embeddings respond from the consolidated store.
4. Only then remove the duplicate C: store.

That order matters: verify before deleting. It freed 9.9GB on a disk with none, and because
the registry variable already pointed at D:, a normal Ollama restart now finds all six
models.

**If embeddings fail with "model not found" after a pull that appeared to succeed, check disk
space before anything else.**

## 4. The corpus

`data/reference/` holds the methodology documents. Current contents:

| Document | Chunks | From `###` subsections | Chars: min / median / max |
|---|---|---|---|
| `ict_concepts.md` | 18 | 3 | 213 / 557 / 952 |
| `risk_and_sizing.md` | 10 | 1 | 257 / 532 / 731 |

Both are **original summaries of publicly taught concepts**, written for this system. No
third-party material is ingested. This is not a formality: the repository is public, so
ingesting copyrighted trading material would publish it. Writing originals also produces
better chunks, because the structure is under our control.

Adding a document is: drop a markdown file with numbered `## n. Title` headings into
`data/reference/`, run the ingest script. No code change.

### Corpus separation

The reference corpus has its own directory and its own database, separate from the
strategies in `data/knowledge_base/` and from the trade store. Per
[product_plan.md](product_plan.md) section 4.1, a draft built from general methodology must
never be contaminated with the trader's own rules, and retrieval must never blur the two.

Keeping them in different files and different databases makes that structural rather than a
matter of remembering. When J4 and J7 arrive, they query the corpus store only.

## 5. Chunking

`app/services/corpus_chunker.py`. Chunking is where RAG systems usually fail, and this
project already learned how.

Epic B cut chunking for the strategy document because its sections depend on each other: the
scoring rubric needs zone grading, bias logic and the structure-break criterion at once, so
a chunk holding one rule without the others retrieves something misleading. The reference
corpus is looser — separate documents, loosely coupled sections — but the same danger applies
within a document. Hence three rules:

**1. Section-aware, not fixed-window.** One chunk per `###` subsection, or per numbered `##`
section where there are none, plus any preamble before the first subsection. A table or rule
list is never cut in half.

**2. Oversized sections split on paragraph boundaries.** `TARGET_CHARS` 1400, `MAX_CHARS`
2200. Splitting happens between paragraphs, never mid-sentence. In the current corpus nothing
needed splitting — the longest chunk is 952 characters.

**3. The heading trail is embedded with the text.** Each chunk's embedded form is:

```
<document> | <section>. <title> — <subsection>

<chunk text>
```

So a retrieved chunk carries where it came from, into both the similarity computation and the
prompt that will eventually cite it. This is the direct answer to "a rule without the context
that makes it correct".

## 6. Embedding and storage

`app/services/corpus_store.py`, with the HTTP call in `app/core/ollama_client.py`.

`bge-m3` through Ollama's `/api/embed`, 1024 dimensions, multilingual — which matters because
the original notes mix German and English. Embedding happens in batches
(`CORPUS_EMBED_BATCH`, default 16) so one oversized request cannot stall an ingest.

Vectors are stored as **float32 blobs in SQLite**, alongside the chunk text and its metadata:

```sql
corpus_chunks(id, source, section, section_title, subsection, text, ordinal,
              model, dims, vector)
```

The whole store is currently 147KB for 28 chunks.

`model` and `dims` are recorded per row, and `search()` **skips any chunk whose dimension
count differs from the query vector** rather than comparing them. Vectors from different
models are not comparable, and silently scoring them would produce numbers that look fine and
mean nothing.

Re-ingesting replaces a document by source name rather than duplicating it, the same pattern
the trade importer uses.

### Why there is no Chroma

The plan called for it. Two reasons it is not used.

**It does not work in this environment.** `chromadb` 0.5.23 is installed but cannot import:

```
google.protobuf.runtime_version.VersionError: Detected incompatible Protobuf
Gencode/Runtime versions ... gencode 6.33.5 runtime 5.29.6
```

`googleapis-common-protos` ships generated code newer than the installed protobuf runtime,
reached through opentelemetry. Fixing it means moving protobuf underneath streamlit and
langchain — a real risk for no current benefit.

**At this size it buys nothing.** A vector database provides approximate-nearest-neighbour
indexing, persistence and metadata filtering. Exact cosine over 28 rows — or a few hundred —
is a millisecond of arithmetic, so ANN would be an approximation of something already
instant. Persistence comes from SQLite, which the project already uses.

`search()` is the only function that knows how vectors are stored, so swapping in a real
index later changes that function and nothing else. **The threshold worth revisiting is the
low thousands of chunks.** `chromadb` and `langchain-chroma` are removed from
`requirements.txt` until then, which also keeps any future container image small.

## 7. Retrieval

```python
search(conn, query, limit=5, source=None, model=None) -> list[Hit]
```

Embed the query, compute cosine similarity against every stored vector, return the top hits
ranked. `Hit` carries the reconstructed `Chunk` and its score, so a caller can cite the
document, section and subsection a passage came from.

Optional `source` narrows to one document — the mechanism J4 will use to compare
methodologies against each other.

## 8. Measured quality, including where it fails

Sensible results are easy to demonstrate and prove little. What follows is the failure,
because it is the useful part.

Asked where the position-sizing formula is — it is in `risk_and_sizing.md` section 2, *Fixed
fractional risk*, which contains the formula outright:

| Query | Rank of the section that contains it |
|---|---|
| "how much should I risk per trade" | **1st, score 0.667** |
| "position size formula" | 5th, score 0.459 |
| "how big should my position be" | **outside the top 5** |

The section ranks first only when the query borrows the vocabulary it uses. Its language is
dominated by risk-fraction phrasing, so the embedding sits closer to queries phrased that way
than to "how big should my position be" — even though answering that question is the
section's entire purpose.

This is the textbook weakness of dense retrieval, and it is **concrete, reproducible evidence
for hybrid dense+BM25 (J6)**, which the backlog deferred "until dense-only is observed
failing". A lexical scorer would match "position size" literally. It has now been observed
failing, so J6 has an evidence-based trigger rather than being a plan item.

Queries that do work — timing to section 11, stop-moving to section 9, structure breaks to
section 3 — should be read as sampling, not as proof the corpus is well retrievable.

## 9. What remains, and how to build it

### J5, retrieval eval — do this before J4

Everything above is anecdote. J5 makes it measurement, mirroring `scripts/eval_match.py`:
10-15 fixed questions, each with the document and section that should answer it, scored for
hit rate at k and for how often the expected source appears at all.

Build this **before** the recommendation feature, or J4 is a narration layer on top of
retrieval nobody has measured. The existing eval discipline applies: keep a change only if
hit rate improves or holds.

### J4, recommendation

Intake (instrument, timeframe, risk tolerance, style) → one retrieval query per rule area →
2-3 methodologies with cited reasons. Each claim must quote a retrieved chunk, verified
against that chunk's text the way `find_unverified_quotes` verifies against a strategy
section. Retrieved-chunk verification is the piece that keeps this honest, and it does not
exist yet.

### J6, hybrid retrieval

Add BM25 over the same chunks and merge the rankings. Section 8 is the justification.

### J7, cold-start drafting

Formerly F4. Draft a rule set in the same numbered-H2 shape as a strategy document, so
`parse_numbered_h2_sections` can read it and Setup Review can route against it. The output
must be structurally compatible or the rest of the system cannot use it. Every drafted rule
carries whether it is supported by a retrieved chunk or model-supplied, and the draft stays
provisional until the trader accepts it — section 4.7 is explicit that advisor output is
never auto-applied.

## 10. Running it

```powershell
d:/confluence-scaffold/.venv-1/Scripts/python.exe scripts/ingest_corpus.py --dry-run
d:/confluence-scaffold/.venv-1/Scripts/python.exe scripts/ingest_corpus.py
d:/confluence-scaffold/.venv-1/Scripts/python.exe scripts/ingest_corpus.py --file data/reference/risk_and_sizing.md
```

`--dry-run` chunks and reports without embedding or writing, which is the fast way to check
a new document chunks sensibly before spending the embedding time.

## 11. Configuration

| Variable | Default | Purpose |
|---|---|---|
| `OLLAMA_EMBED_MODEL` | `bge-m3` | Embedding model, served by Ollama |
| `CORPUS_DB_PATH` | `./data/vector_store/corpus.db` | Chunk and vector store |
| `CORPUS_EMBED_BATCH` | `16` | Texts per embed request |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Shared with the chat models |

The corpus database is gitignored (`data/vector_store/*`), so vectors are rebuilt by running
the ingest rather than committed.

## 12. Files

| File | Role |
|---|---|
| `data/reference/*.md` | The corpus |
| `app/services/corpus_chunker.py` | Section-aware chunking, heading trail |
| `app/services/corpus_store.py` | Embedding, storage, cosine search |
| `app/core/ollama_client.py` | `embed()` against `/api/embed` |
| `scripts/ingest_corpus.py` | Chunk, embed, store; re-runnable |
