from __future__ import annotations

import re


def _numeric_tokens(text: str) -> list[str]:
    return [match.group(0) for match in re.finditer(r"\d+(?:\.\d+)?", text)]


def find_ungrounded_numbers(narrative: str, findings: str) -> list[str]:
    """Advisory check that a narrator did not introduce numbers of its own.

    Compared numerically, so 22.9 matches a computed 22.90. Section numbers and small
    ordinals are ignored, so prose like "three flags" does not trip it.

    Known limit: this is set membership, not claim-level verification. A number that appears
    anywhere in the findings passes even when the narrative attaches it to the wrong claim,
    so a recombined win/loss split ("4W/3L" for a computed 2W/3L) is NOT caught. It detects
    fabricated magnitudes, not misattribution. Catching the latter needs the narrative's
    stat claims parsed and compared field by field.
    """
    grounded = {float(token) for token in _numeric_tokens(findings)}
    grounded.update(float(n) for n in range(0, 21))

    ungrounded: list[str] = []
    seen: set[float] = set()
    for token in _numeric_tokens(narrative):
        value = float(token)
        if value in grounded or value in seen:
            continue
        if re.search(rf"section\s+{re.escape(token)}\b", narrative, re.IGNORECASE):
            continue
        seen.add(value)
        ungrounded.append(token)
    return ungrounded
