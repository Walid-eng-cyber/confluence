from __future__ import annotations

import array
import os
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

from app.core.ollama_client import embed
from app.services.corpus_chunker import Chunk

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parents[2]

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
EMBED_MODEL = os.getenv("OLLAMA_EMBED_MODEL", "bge-m3")
EMBED_BATCH = int(os.getenv("CORPUS_EMBED_BATCH", "16"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS corpus_chunks (
    id            INTEGER PRIMARY KEY,
    source        TEXT NOT NULL,
    section       TEXT NOT NULL,
    section_title TEXT NOT NULL,
    subsection    TEXT NOT NULL,
    text          TEXT NOT NULL,
    ordinal       INTEGER NOT NULL,
    model         TEXT NOT NULL,
    dims          INTEGER NOT NULL,
    vector        BLOB NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_corpus_source ON corpus_chunks(source);
"""


@dataclass(frozen=True)
class Hit:
    chunk: Chunk
    score: float


def db_path() -> Path:
    configured = os.getenv("CORPUS_DB_PATH", "./data/vector_store/corpus.db")
    path = Path(configured)
    return path if path.is_absolute() else (PROJECT_ROOT / path).resolve()


def connect(path: Path | str | None = None) -> sqlite3.Connection:
    target = Path(path) if path is not None else db_path()
    if str(target) != ":memory:":
        target.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(target)
    conn.row_factory = sqlite3.Row
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    conn.commit()


def _pack(vector: list[float]) -> bytes:
    return array.array("f", vector).tobytes()


def _unpack(blob: bytes) -> array.array:
    out = array.array("f")
    out.frombytes(blob)
    return out


def embed_texts(texts: list[str], model: str | None = None) -> list[list[float]]:
    """Embed in batches, so one oversized request cannot stall the whole ingest."""
    model = model or EMBED_MODEL
    vectors: list[list[float]] = []
    for start in range(0, len(texts), EMBED_BATCH):
        batch = texts[start:start + EMBED_BATCH]
        vectors.extend(embed(batch, model=model, base_url=OLLAMA_BASE_URL))
    return vectors


def replace_source(
    conn: sqlite3.Connection,
    source: str,
    chunks: list[Chunk],
    model: str | None = None,
) -> int:
    """Embed and store one document's chunks, replacing any previous version of it."""
    model = model or EMBED_MODEL
    if not chunks:
        with conn:
            conn.execute("DELETE FROM corpus_chunks WHERE source = ?", (source,))
        return 0

    vectors = embed_texts([c.embedding_text() for c in chunks], model)
    dims = len(vectors[0])

    with conn:
        conn.execute("DELETE FROM corpus_chunks WHERE source = ?", (source,))
        conn.executemany(
            "INSERT INTO corpus_chunks (source, section, section_title, subsection, text,"
            " ordinal, model, dims, vector) VALUES (?,?,?,?,?,?,?,?,?)",
            [
                (c.source, c.section, c.section_title, c.subsection, c.text, c.ordinal,
                 model, dims, _pack(v))
                for c, v in zip(chunks, vectors)
            ],
        )
    return len(chunks)


def count_chunks(conn: sqlite3.Connection, source: str | None = None) -> int:
    if source is None:
        return conn.execute("SELECT COUNT(*) FROM corpus_chunks").fetchone()[0]
    return conn.execute(
        "SELECT COUNT(*) FROM corpus_chunks WHERE source = ?", (source,)
    ).fetchone()[0]


def sources(conn: sqlite3.Connection) -> list[tuple[str, int]]:
    return [
        (row["source"], row["n"])
        for row in conn.execute(
            "SELECT source, COUNT(*) AS n FROM corpus_chunks GROUP BY source ORDER BY source"
        )
    ]


def search(
    conn: sqlite3.Connection,
    query: str,
    limit: int = 5,
    source: str | None = None,
    model: str | None = None,
) -> list[Hit]:
    """Dense retrieval by cosine similarity, computed in process.

    Brute force on purpose. A few hundred chunks at 1024 dimensions is a millisecond of
    arithmetic; an approximate-nearest-neighbour index earns its keep in the thousands, and
    until then it is a dependency and a failure mode for nothing. The interface returns
    ranked hits, so swapping in a real index later changes only this function.
    """
    model = model or EMBED_MODEL
    sql = "SELECT * FROM corpus_chunks"
    params: list[object] = []
    if source is not None:
        sql += " WHERE source = ?"
        params.append(source)

    rows = list(conn.execute(sql, params))
    if not rows:
        return []

    query_vector = embed_texts([query], model)[0]
    q_norm = sum(x * x for x in query_vector) ** 0.5 or 1.0

    scored: list[Hit] = []
    for row in rows:
        vector = _unpack(row["vector"])
        if len(vector) != len(query_vector):
            # A chunk embedded by a different model cannot be compared. Skip rather than
            # return a meaningless score.
            continue
        dot = sum(a * b for a, b in zip(vector, query_vector))
        norm = sum(x * x for x in vector) ** 0.5 or 1.0
        scored.append(Hit(
            chunk=Chunk(
                source=row["source"],
                section=row["section"],
                section_title=row["section_title"],
                subsection=row["subsection"],
                text=row["text"],
                ordinal=row["ordinal"],
            ),
            score=dot / (norm * q_norm),
        ))

    scored.sort(key=lambda h: h.score, reverse=True)
    return scored[:limit]
