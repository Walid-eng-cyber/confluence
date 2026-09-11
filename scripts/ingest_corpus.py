"""Ingest the reference corpus into the embedded chunk store (J2).

Every markdown file in data/reference/ is chunked section-aware, embedded through Ollama,
and stored. Re-running replaces a document rather than duplicating it.

The reference corpus is kept in its own directory and its own database, apart from the
strategies in data/knowledge_base/. Per product_plan.md section 4.1, a draft built from
general methodology must never be contaminated with the trader's own rules.

Usage:
    python scripts/ingest_corpus.py [--dry-run] [--file <path>]
"""
from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services import corpus_store
from app.services.corpus_chunker import chunk_document

REFERENCE_DIR = PROJECT_ROOT / "data" / "reference"


def source_name(path: Path) -> str:
    return path.stem.replace("_", " ")


def main(argv: list[str]) -> int:
    dry_run = "--dry-run" in argv

    if "--file" in argv:
        index = argv.index("--file") + 1
        if index >= len(argv):
            print("--file needs a path", file=sys.stderr)
            return 2
        paths = [Path(argv[index])]
    else:
        paths = sorted(REFERENCE_DIR.glob("*.md"))

    if not paths:
        print(f"No markdown found in {REFERENCE_DIR}", file=sys.stderr)
        return 2

    plans: list[tuple[str, list]] = []
    for path in paths:
        if not path.exists():
            print(f"No such file: {path}", file=sys.stderr)
            return 2
        chunks = chunk_document(source_name(path), path.read_text(encoding="utf-8"))
        plans.append((source_name(path), chunks))
        longest = max((len(c.text) for c in chunks), default=0)
        print(f"{path.name}: {len(chunks)} chunks, longest {longest} chars")

    if dry_run:
        print("\n--dry-run: nothing embedded or written.")
        return 0

    print(f"\nEmbedding with {corpus_store.EMBED_MODEL} ...")
    conn = corpus_store.connect()
    try:
        corpus_store.init_schema(conn)
        for source, chunks in plans:
            written = corpus_store.replace_source(conn, source, chunks)
            print(f"  {source}: {written} chunks stored")
        print("\nCorpus now holds:")
        for source, count in corpus_store.sources(conn):
            print(f"  {source}: {count} chunks")
    finally:
        conn.close()

    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(main(sys.argv))
