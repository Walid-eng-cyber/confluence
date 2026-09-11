# Reference corpus and retrieval (Epic J, J2-J3)

The first part of this system that actually does retrieval-augmented generation over a
corpus, rather than deterministic routing over one document.

## 1. What exists

1. `data/reference/` — methodology documents, kept apart from `data/knowledge_base/`.
2. `app/services/corpus_chunker.py` — section-aware chunking.
3. `app/services/corpus_store.py` — embedded chunks in SQLite, cosine search.
4. `scripts/ingest_corpus.py` — chunk, embed, store; re-runnable.

Current corpus: 28 chunks across two documents (ICT concepts, risk and sizing).

Not built yet: the recommendation feature (J4) and the retrieval eval (J5).

## 2. Why there is no Chroma

The plan called for Chroma. It is not used, for two reasons.

**It does not work in this environment.** `chromadb` 0.5.23 is installed but cannot import:
a protobuf conflict (`googleapis-common-protos` gencode 6.33.5 against protobuf runtime
5.29.6, reached through opentelemetry). Fixing it means moving protobuf, which risks
streamlit and langchain.

**At this size it buys nothing.** A vector database provides approximate-nearest-neighbour
indexing, persistence and metadata filtering. At 28 chunks — or a few hundred — exact cosine
over every row is a millisecond of arithmetic, and ANN is an approximation of something
already instant. Persistence comes from SQLite, which the project already uses.

So vectors are stored as float32 blobs in SQLite and compared in process. `search()` is the
only place that knows this; swapping in a real index later changes that function and nothing
else. The threshold worth revisiting is somewhere in the low thousands of chunks.

`chromadb` and `langchain-chroma` have been removed from requirements.txt until something
needs them.

## 3. Chunking, and the lesson behind it

Chunking is where RAG systems usually fail, and this project already learned how. Epic B cut
chunking for the strategy document because its sections depend on each other — the scoring
rubric needs zone grading, bias logic and the structure-break criterion at once, so a chunk
containing one rule without the others retrieves something misleading.

The reference corpus is different: separate documents, loosely coupled sections. But the same
danger applies within a document, so:

1. **Section-aware, not fixed-window.** One chunk per `###` subsection, or per numbered `##`
   section where there are none. A table or rule list is never cut in half.
2. **Oversized sections split on paragraph boundaries**, never mid-sentence.
3. **The heading trail is embedded with the text.** Each chunk's embedded form begins
   `<document> | <section>. <title> — <subsection>`, so a retrieved chunk carries where it
   came from. This is the direct answer to "a rule without the context that makes it
   correct".

Measured: 18 chunks from the ICT document, 10 from risk and sizing, longest 952 characters
against a 2200 limit.

## 4. A real limitation, measured

Retrieval works, but dense-only retrieval misses on vocabulary. Asked where the
position-sizing formula is:

| Query | Rank of the section that contains it |
|---|---|
| "how much should I risk per trade" | **1st, score 0.667** |
| "position size formula" | 5th, score 0.459 |
| "how big should my position be" | **not in the top 5** |

The section is `2. Fixed fractional risk`, and it does contain the size formula. It ranks
first only when the query borrows the vocabulary the section uses. The chunk's language is
dominated by risk-fraction phrasing, so the embedding sits closer to queries phrased that
way than to "how big should my position be".

This is the textbook weakness of dense retrieval, and it is concrete evidence for why
hybrid dense+BM25 (backlog J6) exists: a lexical scorer would match "position size"
literally. J6 was deferred until dense-only was observed failing. It has now been observed
failing, with a reproducible example.

**Do not read the working queries as proof the corpus is well retrievable.** That is what the
retrieval eval (J5) is for: fixed questions with expected source sections, scored, so
retrieval quality is measured rather than sampled.

## 5. Running it

```powershell
d:/confluence-scaffold/.venv-1/Scripts/python.exe scripts/ingest_corpus.py --dry-run
d:/confluence-scaffold/.venv-1/Scripts/python.exe scripts/ingest_corpus.py
```

Re-running replaces a document by source name rather than duplicating it.

Configuration:

| Variable | Default | Purpose |
|---|---|---|
| `OLLAMA_EMBED_MODEL` | `bge-m3` | Embedding model, served by Ollama |
| `CORPUS_DB_PATH` | `./data/vector_store/corpus.db` | Chunk and vector store |
| `CORPUS_EMBED_BATCH` | `16` | Texts per embed request |

`bge-m3` produces 1024 dimensions. A chunk embedded by a different model is skipped at search
time rather than compared, because vectors from different models are not comparable.

## 6. Corpus separation

The reference corpus lives in its own directory and its own database, separate from the
strategies in `data/knowledge_base/` and the trade store. Per product_plan.md section 4.1, a
draft built from general methodology must never be contaminated with the trader's own rules,
and retrieval must never blur the two. Keeping them in different files makes that structural
rather than a matter of remembering.

The documents are original summaries of publicly taught concepts, written for this system.
No third-party material is ingested — which matters, because this repository is public.
