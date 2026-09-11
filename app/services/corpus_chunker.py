from __future__ import annotations

import re
from dataclasses import dataclass

# Roughly four characters per token for mixed markdown. A chunk much larger than this stops
# being specific enough to retrieve; much smaller and it loses the context that makes it
# correct.
TARGET_CHARS = 1400
MAX_CHARS = 2200


@dataclass(frozen=True)
class Chunk:
    source: str
    section: str
    section_title: str
    subsection: str
    text: str
    ordinal: int

    def heading_trail(self) -> str:
        trail = f"{self.section}. {self.section_title}" if self.section_title else self.source
        if self.subsection:
            trail += f" — {self.subsection}"
        return trail

    def embedding_text(self) -> str:
        """What actually gets embedded.

        The heading trail is prepended so a chunk carries where it came from. This is the
        specific failure the strategy document taught: a rule retrieved without the context
        that makes it correct is worse than no rule. Here the trail travels with the text.
        """
        return f"{self.source} | {self.heading_trail()}\n\n{self.text}"


def _split_long(text: str, limit: int) -> list[str]:
    """Split on paragraph boundaries, never mid-sentence."""
    if len(text) <= limit:
        return [text]

    parts: list[str] = []
    current = ""
    for paragraph in re.split(r"\n\s*\n", text):
        candidate = f"{current}\n\n{paragraph}".strip() if current else paragraph
        if len(candidate) <= limit or not current:
            current = candidate
        else:
            parts.append(current)
            current = paragraph
    if current:
        parts.append(current)
    return parts


def chunk_document(source: str, markdown: str) -> list[Chunk]:
    """Split a methodology document into retrievable chunks.

    Section-aware rather than fixed-window: one chunk per `###` subsection, or per numbered
    `##` section where it has none. A section longer than MAX_CHARS is split on paragraph
    boundaries, so a table or a rule list is never cut in half.
    """
    heading = re.compile(r"(?m)^##\s+(?P<num>\d+)\.\s+(?P<title>.+?)\s*$")
    matches = list(heading.finditer(markdown))
    chunks: list[Chunk] = []
    ordinal = 0

    for index, match in enumerate(matches):
        number, title = match.group("num"), match.group("title")
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(markdown)
        body = markdown[start:end].strip()
        if not body:
            continue

        # Split into subsections, keeping any preamble before the first one.
        pieces: list[tuple[str, str]] = []
        sub = list(re.finditer(r"(?m)^###\s+(?P<sub>.+?)\s*$", body))
        if sub:
            preamble = body[: sub[0].start()].strip()
            if preamble:
                pieces.append(("", preamble))
            for j, s in enumerate(sub):
                s_end = sub[j + 1].start() if j + 1 < len(sub) else len(body)
                s_body = body[s.end():s_end].strip()
                if s_body:
                    pieces.append((s.group("sub"), s_body))
        else:
            pieces.append(("", body))

        for subsection, text in pieces:
            for part in _split_long(text, MAX_CHARS):
                chunks.append(Chunk(
                    source=source,
                    section=number,
                    section_title=title,
                    subsection=subsection,
                    text=part.strip(),
                    ordinal=ordinal,
                ))
                ordinal += 1

    return chunks
