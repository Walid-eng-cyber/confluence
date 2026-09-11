# Pathlib is library that lets you work with filesystem paths.
from pathlib import Path 
import os
import sys
import time
from dotenv import load_dotenv
from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage
import re

# The path to the strategy markdown file.
# Writing Format explained :
# The strategy markdown file should be located in the "data/knowledge_base" directory.
# The filename should follow the format "<strategy_name>_strategy.md".
PROJECT_ROOT = Path(__file__).resolve().parent.parent
STRATEGY_PATH = PROJECT_ROOT / "data" / "knowledge_base" / "nabil_strategy.md"


strategy_text = STRATEGY_PATH.read_text(encoding = "utf-8")

load_dotenv()
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_RESTATE_MODEL = os.getenv(
    "OLLAMA_RESTATE_MODEL",
    os.getenv("OLLAMA_CHAT_MODEL", "deepseek-r1:8b"),
)
OLLAMA_MATCH_MODEL = os.getenv("OLLAMA_MATCH_MODEL", "qwen3:8b")
PROMPT_CONTEXT_CHARS = int(os.getenv("PROMPT_CONTEXT_CHARS", "3000"))
OLLAMA_NUM_CTX_RESTATE = int(os.getenv("OLLAMA_NUM_CTX_RESTATE", os.getenv("OLLAMA_NUM_CTX", "1536")))
OLLAMA_NUM_CTX_MATCH = int(os.getenv("OLLAMA_NUM_CTX_MATCH", "4096"))
OLLAMA_NUM_CTX_MATCH_CAP = int(os.getenv("OLLAMA_NUM_CTX_MATCH_CAP", "4096"))
OLLAMA_NUM_CTX_MATCH = min(OLLAMA_NUM_CTX_MATCH, OLLAMA_NUM_CTX_MATCH_CAP)
OLLAMA_SECTION_CTX_FLOOR = int(os.getenv("OLLAMA_SECTION_CTX_FLOOR", "2048"))
ENABLE_DYNAMIC_SECTION_CTX = os.getenv("ENABLE_DYNAMIC_SECTION_CTX", "0") == "1"
OLLAMA_RETRIES = int(os.getenv("OLLAMA_RETRIES", "1"))
OLLAMA_RETRY_DELAY_SEC = float(os.getenv("OLLAMA_RETRY_DELAY_SEC", "0.2"))
OLLAMA_RETRY_MAX_DELAY_SEC = float(os.getenv("OLLAMA_RETRY_MAX_DELAY_SEC", "1.0"))
OLLAMA_MATCH_TIMEOUT_SEC = float(os.getenv("OLLAMA_MATCH_TIMEOUT_SEC", "60"))
OLLAMA_MATCH_NUM_PREDICT = int(os.getenv("OLLAMA_MATCH_NUM_PREDICT", "768"))
OLLAMA_MATCH_NUM_PREDICT_RETRY = int(os.getenv("OLLAMA_MATCH_NUM_PREDICT_RETRY", "1536"))
OLLAMA_MATCH_KEEP_ALIVE = os.getenv("OLLAMA_MATCH_KEEP_ALIVE", "10m")

RAW_PARSE_DEBUG_ONCE = os.getenv("RAW_PARSE_DEBUG_ONCE", "1") == "1"
_RAW_PARSE_DEBUG_PRINTED = False


def _list_installed_ollama_models() -> set[str]:
    """Return locally installed Ollama model tags from `ollama list`."""
    try:
        import subprocess

        proc = subprocess.run(
            ["ollama", "list"],
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode != 0:
            return set()

        names: set[str] = set()
        for idx, line in enumerate(proc.stdout.splitlines()):
            if idx == 0:
                continue
            cols = line.split()
            if cols:
                names.add(cols[0])
        return names
    except Exception:
        return set()


def _resolve_match_model() -> str:
    """Pick match model; fall back to restate model if configured one is missing."""
    installed = _list_installed_ollama_models()
    if not installed:
        return OLLAMA_MATCH_MODEL
    if OLLAMA_MATCH_MODEL in installed:
        return OLLAMA_MATCH_MODEL

    print(
        (
            f"[model-warning] match model '{OLLAMA_MATCH_MODEL}' not installed; "
            f"falling back to '{OLLAMA_RESTATE_MODEL}'."
        ),
        file=sys.stderr,
    )
    return OLLAMA_RESTATE_MODEL

# Route extracted facts to governing numbered H2 sections in nabil_strategy.md.
ROUTING_MAP: dict[str, list[str]] = {
    "zone_grade": ["6"],
    "bias": ["3"],
    "target_pool": ["4", "5"],
    "rr": ["10"],
    "session": ["11"],
    "news": ["14"],
    "structure_break": ["8"],
    "sweep_vs_break": ["15"],
}

# Topic recognizers for Call 1 fact lines (case-insensitive substring checks).
KEYWORDS: dict[str, list[str]] = {
    "zone_grade": ["a-grade", "b-grade", "c-grade", "zone grade", "demand zone", "supply zone"],
    "bias": ["bias", "higher high", "higher highs", "higher low", "higher lows", "daily bias"],
    "target_pool": ["target pool", "pool", "liquidity", "liquidity pool", "pool has been taken", "pool taken"],
    "rr": ["rr", "risk reward", "risk-reward", "risk/reward", "risk to reward", "r:r"],
    "session": ["session", "london", "new york", "newyork", "timing", "cest", "cet"],
    "news": ["news", "release", "tier 1", "tier-1", "economic"],
    "structure_break": ["choch", "bos", "structure break", "criterion 2", "opposing swing", "last lower high", "last higher low"],
    "sweep_vs_break": ["swept", "sweep", "break", "reclaim", "retest"],
}

def route(fact: str) -> list[str]:
    """Return section numbers whose rules govern the provided fact line."""
    fact_lower = fact.lower()
    sections: list[str] = []
    for topic, words in KEYWORDS.items():
        if any(word in fact_lower for word in words):
            sections.extend(ROUTING_MAP[topic])
    return sorted(set(sections), key=int)

# 2. Constants(new) - module-level, so they are define once when the file loads.

SYSTEM_PROMPT = """You are a trading setup consultant. Your only source of truth is the \
strategy document provided in the next message, in full.

Answer in exactly three stages, in this order. Do not skip ahead to a conclusion before \
finishing stage 1 and stage 2.

STAGE 1 — Restate the input.
List every fact given in the setup description, exactly as stated, changing nothing. \
Then list what is NOT stated that the document's rules would need (e.g. RR, whether a \
specific pool has been swept, session timing, news risk). Do not guess these, list them \
as unknown.

STAGE 2 — Match facts to rules, with quotes.
For each fact from Stage 1, find the exact section of the document it relates to and \
quote the relevant line or table row before saying what it implies. If a fact could \
match more than one rule, check which one actually applies before choosing, do not use \
the first rule that sounds similar. If nothing in the document applies to a given fact, \
say so instead of inventing a connection.

STAGE 3 — Verdict.
Only now give your read: state your position first, then the reasoning that led to it. \
If a required fact from Stage 1's "unknown" list is missing, say the verdict is \
incomplete because of that, do not fill the gap with an assumption. If your read \
conflicts with how the trader described the setup, say so rather than agreeing by \
default. Cite the specific section for every claim.
"""

RESTATE_PROMPT = """List every fact in the following trading setup description, exactly \
as stated, changing nothing. Then list what relevant information is NOT stated (things \
like RR, whether a specific liquidity pool has been taken, session timing, news risk). \
Do not guess these, just list them as unknown.

Unknowns rule (mandatory):
- Only list these four unknown categories when missing:
    - Risk-reward ratio (RR)
    - Whether a specific liquidity pool has been taken
    - Session timing
    - News risk
- Do not add any other unknown categories.

Output format rules (mandatory):
- Use these literal section markers exactly:
    === FACTS ===
    === UNKNOWN ===
- Under each marker, write one item per line as a plain bullet starting with "- ".
- Do not output any other headings.

Setup:
{setup_description}
"""

def restate_facts(llm, setup_description: str) -> str:
    response = llm.invoke([HumanMessage(content=RESTATE_PROMPT.format(setup_description=setup_description))])
    return response.content

def _strip_markdown_list_marker(line: str) -> str:
    line = line.replace("**", "").strip()
    line = re.sub(r"^\s*(?:[-*•]|\d+[\.)])\s+", "", line)
    return line.strip()

def parse_restate_output(text: str) -> tuple[list[str], list[str]]:
    """Parse Call 1 output into facts and unknowns lists.

    Assumes one item per line under two headings and strips markdown bullets/bold.
    """
    facts: list[str] = []
    unknowns: list[str] = []
    current: str | None = None

    marker_facts_re = re.compile(r"^={3,}\s*facts\s*={3,}$", re.IGNORECASE)
    marker_unknowns_re = re.compile(r"^={3,}\s*unknown(?:s)?\s*={3,}$", re.IGNORECASE)
    facts_heading_re = re.compile(r"^(?:#{1,6}\s+)?\*{0,2}\s*(?:facts?|stated\s+facts?)\s*\*{0,2}\s*:?\s*$", re.IGNORECASE)
    unknowns_heading_re = re.compile(
        r"^(?:#{1,6}\s+)?\*{0,2}\s*(?:information\s+not\s+stated|relevant\s+information\s+not\s+stated|unknowns?|missing\s+information|not\s+stated)\s*\*{0,2}\s*:?\s*$",
        re.IGNORECASE,
    )

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        heading = line.replace("**", "").strip()
        if marker_facts_re.match(heading) or facts_heading_re.match(heading):
            current = "facts"
            continue
        if marker_unknowns_re.match(heading) or unknowns_heading_re.match(heading) or re.search(r"\bnot\s+stated\b", heading, re.IGNORECASE):
            current = "unknowns"
            continue

        if current is None:
            continue

        cleaned = _strip_markdown_list_marker(line)
        if cleaned:
            if current == "facts":
                facts.append(cleaned)
            else:
                unknowns.append(cleaned)

    return facts, unknowns

def _keyword_set(text: str) -> set[str]:
    return {
        w for w in re.findall(r"[a-zA-Z0-9_]{3,}", text.lower())
        if w not in {"the", "and", "for", "with", "that", "this", "from", "into", "then"}
    }

def _split_markdown_sections(markdown_text: str) -> list[tuple[str, str]]:
    parts = re.split(r"(?m)^##\s+", markdown_text)
    sections: list[tuple[str, str]] = []
    if parts and parts[0].strip():
        sections.append(("Introduction", parts[0].strip()))
    for part in parts[1:]:
        lines = part.splitlines()
        if not lines:
            continue
        title = lines[0].strip()
        body = "\n".join(lines[1:]).strip()
        sections.append((title, body))
    return sections

def parse_numbered_h2_sections(markdown_text: str) -> dict[str, str]:
    """Map numbered H2 sections (e.g. '## 6. Zone grading') to full section text.

    Each value includes the section heading itself and everything until the next
    H2 heading of the same level.
    """
    heading_re = re.compile(r"(?m)^##\s+(?P<num>\d+)\.\s+.*$")
    matches = list(heading_re.finditer(markdown_text))
    sections: dict[str, str] = {}

    for idx, match in enumerate(matches):
        number = match.group("num")
        start = match.start()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(markdown_text)
        sections[number] = markdown_text[start:end].rstrip()

    return sections

def extract_sections(markdown_text: str) -> dict[str, str]:
    """Compatibility wrapper returning numbered H2 sections."""
    return parse_numbered_h2_sections(markdown_text)

def parse_strategy_sections(strategy_path: Path = STRATEGY_PATH) -> dict[str, str]:
    """Read the strategy file once and return numbered H2 sections."""
    return parse_numbered_h2_sections(strategy_path.read_text(encoding="utf-8"))

def _standalone_section_parser_test(strategy_path: Path = STRATEGY_PATH) -> None:
    sections = parse_strategy_sections(strategy_path)
    for key in ("6", "14"):
        print(f"\n--- SECTION {key} ---\n")
        print(sections.get(key, f"<missing section {key}>"))

def build_relevant_strategy_excerpt(
    strategy_text: str,
    setup_description: str,
    restated_facts: str,
    max_chars: int,
) -> str:
    sections = _split_markdown_sections(strategy_text)
    query_terms = _keyword_set(f"{setup_description}\n{restated_facts}")

    scored: list[tuple[int, str, str]] = []
    for title, body in sections:
        combined = f"{title}\n{body}"
        section_terms = _keyword_set(combined)
        overlap = len(query_terms & section_terms)
        # Mild bias to include foundational rules and execution details.
        title_l = title.lower()
        if "core principle" in title_l or "framework" in title_l or "entry" in title_l:
            overlap += 2
        scored.append((overlap, title, body))

    scored.sort(key=lambda x: x[0], reverse=True)

    picked: list[str] = []
    used = 0
    for score, title, body in scored:
        if score <= 0 and picked:
            continue
        block = f"## {title}\n{body}\n"
        if used + len(block) > max_chars:
            continue
        picked.append(block)
        used += len(block)
        if used >= max_chars:
            break

    if not picked:
        return strategy_text[:max_chars]
    return "\n".join(picked)


def _section_excerpt_for_item(section_text: str, item_text: str, max_lines: int = 16, neighbor_window: int = 1) -> str:
    """Return a compact, item-focused excerpt from a section to lower generation cost."""
    lines = section_text.splitlines()
    if len(lines) <= max_lines:
        return section_text

    tokens = _keyword_set(item_text)
    if not tokens:
        return "\n".join(lines[:max_lines])

    selected: set[int] = set()
    for idx, line in enumerate(lines):
        line_tokens = _keyword_set(line)
        if tokens & line_tokens:
            start = max(0, idx - neighbor_window)
            end = min(len(lines), idx + neighbor_window + 1)
            selected.update(range(start, end))

    # Always keep heading/top context for coherence.
    selected.update(range(0, min(3, len(lines))))

    if not selected:
        return "\n".join(lines[:max_lines])

    ordered = sorted(selected)
    compact_lines: list[str] = []
    for i in ordered:
        compact_lines.append(lines[i])
        if len(compact_lines) >= max_lines:
            break

    return "\n".join(compact_lines)


def _prepare_section_text_for_prompt(section_number: str, section_text: str, item_text: str) -> str:
    """Prepare section text for prompting, excluding known non-governing examples."""
    prepared = section_text

    # Section 15 contains rule definitions plus a break-and-go examples block.
    # Keep only the definitional portion to avoid lexical attraction to examples.
    if section_number == "15":
        marker = "\n### The break-and-go gap"
        if marker in prepared:
            prepared = prepared.split(marker, 1)[0].rstrip()

    return _section_excerpt_for_item(prepared, item_text)


def _estimate_token_count(text: str) -> int:
    # Rough heuristic: ~4 chars per token for mixed markdown/text.
    return max(1, len(text) // 4)


def _recommended_num_ctx_for_section(section_text: str) -> int:
    estimated = _estimate_token_count(section_text)
    target = estimated + 1024
    return min(OLLAMA_NUM_CTX_MATCH_CAP, max(OLLAMA_SECTION_CTX_FLOOR, target))


def _build_match_llm(
    model: str,
    num_ctx: int,
    num_predict: int,
    cache: dict[tuple[int, int], ChatOllama],
) -> ChatOllama:
    key = (num_ctx, num_predict)
    if key in cache:
        return cache[key]

    client = ChatOllama(
        base_url=OLLAMA_BASE_URL,
        model=model,
        temperature=0.1,
        num_ctx=num_ctx,
        num_predict=num_predict,
        keep_alive=OLLAMA_MATCH_KEEP_ALIVE,
    )
    cache[key] = client
    return client


def _expected_table_column_count(section_text: str) -> int | None:
    lines = section_text.splitlines()
    for line in lines:
        candidate = line.strip()
        if not (candidate.startswith("|") and candidate.endswith("|")):
            continue
        if re.fullmatch(r"\|\s*[-: ]+\|(?:\s*[-: ]+\|)+", candidate):
            continue

        cells = [cell.strip() for cell in candidate.strip("|").split("|")]
        non_empty = [cell for cell in cells if cell]
        if len(non_empty) >= 2:
            return len(non_empty)
    return None


def _table_row_guard(status: str, response_text: str, second_field: str, section_text: str) -> tuple[str, str]:
    if status != "OK":
        return status, response_text

    expected_cols = _expected_table_column_count(section_text)
    if expected_cols is None:
        return status, response_text

    quote = _extract_field_value(response_text, "Quote")
    if not quote:
        return status, response_text

    q = quote.strip()
    if q.upper() == "NOT COVERED" or q == "N/A":
        return status, response_text

    quote_cols = [cell.strip() for cell in q.strip("|").split("|") if cell.strip()]
    if len(quote_cols) < expected_cols:
        return (
            "NOT_COVERED",
            (
                "Status: NOT_COVERED\n"
                'Quote: "NOT COVERED"\n'
                f"{second_field}: table row quote incomplete ({len(quote_cols)}/{expected_cols} columns)."
            ),
        )

    return status, response_text

def _normalize(text: str) -> str:
    text = text.replace("**", "")
    text = text.replace("*", "")
    text = re.sub(r"\s+", " ", text)
    return text.strip()

def find_unverified_quotes(response_text: str, source_text: str) -> list[str]:
    quoted = re.findall(r'Quote:\s*"([^"]+)"', response_text)
    normalized_source = _normalize(source_text)
    unverified = []
    for q in quoted:
        if _normalize(q) in {"NOT COVERED", "N/A", "ERROR"}:
            continue
        if _normalize(q) not in normalized_source:
            unverified.append(q)
    return unverified


def _sanitize_model_text(text: str) -> str:
    """Normalize common formatting drift before extracting labeled fields."""
    cleaned = re.sub(r"(?is)<think>.*?</think>", "", text)
    cleaned = cleaned.replace("**", "")
    cleaned = cleaned.translate(str.maketrans({
        "\u201c": '"',
        "\u201d": '"',
        "\u2018": "'",
        "\u2019": "'",
    }))
    return cleaned

def _extract_field_value(text: str, field: str) -> str | None:
    text = _sanitize_model_text(text)
    line_pattern = re.compile(rf"(?i)^\s*{re.escape(field)}\s*:\s*(.+?)\s*$")

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        match = line_pattern.match(line)
        if not match:
            continue

        value = match.group(1).strip()
        value = re.sub(r"^\*\*(.+)\*\*$", r"\1", value).strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'", "`"}:
            value = value[1:-1].strip()
        return value if value else None

    fallback = re.search(rf"(?im)^\s*{re.escape(field)}\s*:\s*(.*)$", text)
    if fallback:
        value = fallback.group(1).strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'", "`"}:
            value = value[1:-1].strip()
        return value if value else None

    return None

def _normalize_structured_response(text: str, second_field: str) -> tuple[str, str]:
    """Keep only Status + Quote + second_field with explicit ERROR separation."""
    quote = _extract_field_value(text, "Quote")
    detail = _extract_field_value(text, second_field)

    if not quote:
        return (
            "ERROR",
            (
                "Status: ERROR\n"
                "Quote: N/A\n"
                f"{second_field}: model output missing required Quote field."
            ),
        )
    if not detail:
        return (
            "ERROR",
            (
                "Status: ERROR\n"
                "Quote: N/A\n"
                f"{second_field}: model output missing required {second_field} field."
            ),
        )

    if quote.strip().upper() == "NOT COVERED":
        return (
            "NOT_COVERED",
            (
                "Status: NOT_COVERED\n"
                'Quote: "NOT COVERED"\n'
                f"{second_field}: {detail}"
            ),
        )

    q = quote.strip()
    if q.startswith("#") or q.endswith(":"):
        return (
            "NOT_COVERED",
            (
                "Status: NOT_COVERED\n"
                'Quote: "NOT COVERED"\n'
                f"{second_field}: heading-like quote rejected by guard."
            ),
        )

    return (
        "OK",
        (
            "Status: OK\n"
            f'Quote: "{quote}"\n'
            f"{second_field}: {detail}"
        ),
    )

def _invoke_with_retry(llm, prompt: str, second_field: str, llm_on_length_retry=None) -> tuple[str, str]:
    """Invoke model with retries and return a safe, parseable response string."""
    global _RAW_PARSE_DEBUG_PRINTED

    last_error = ""
    attempts = OLLAMA_RETRIES + 1

    for attempt in range(1, attempts + 1):
        try:
            start = time.time()
            response = llm.invoke([HumanMessage(content=prompt)])
            elapsed = time.time() - start
            if elapsed > OLLAMA_MATCH_TIMEOUT_SEC:
                raise TimeoutError(f"match call exceeded {OLLAMA_MATCH_TIMEOUT_SEC}s")
            text = response.content.strip()
            done_reason = str((response.response_metadata or {}).get("done_reason", "")).lower()
            if not text and done_reason == "length":
                raw_content = response.content if isinstance(response.content, str) else str(response.content)
                print(
                    f"[length-debug] len={len(raw_content)} preview={repr(raw_content[:200])}",
                    file=sys.stderr,
                )
                if llm_on_length_retry is not None:
                    print(
                        f"[length-retry] escalating generation cap to {OLLAMA_MATCH_NUM_PREDICT_RETRY}",
                        file=sys.stderr,
                    )
                    retry_resp = llm_on_length_retry.invoke([HumanMessage(content=prompt)])
                    retry_text = retry_resp.content.strip()
                    retry_reason = str((retry_resp.response_metadata or {}).get("done_reason", "")).lower()
                    retry_status, retry_normalized = _normalize_structured_response(retry_text, second_field)
                    if retry_status != "ERROR":
                        return retry_status, retry_normalized
                    if retry_text:
                        return retry_status, retry_normalized
                    return (
                        "ERROR",
                        (
                            "Status: ERROR\n"
                            "Quote: N/A\n"
                            f"{second_field}: model output exhausted token cap before visible answer.\n"
                            "Error: done_reason=length on base and retry caps "
                            f"({OLLAMA_MATCH_NUM_PREDICT} -> {OLLAMA_MATCH_NUM_PREDICT_RETRY}), "
                            f"retry_done_reason={retry_reason}"
                        ),
                    )
                return (
                    "ERROR",
                    (
                        "Status: ERROR\n"
                        "Quote: N/A\n"
                        f"{second_field}: model output exhausted token cap before visible answer.\n"
                        f"Error: done_reason=length, num_predict={OLLAMA_MATCH_NUM_PREDICT}"
                    ),
                )
            status, normalized = _normalize_structured_response(text, second_field)
            if status == "ERROR" and RAW_PARSE_DEBUG_ONCE and not _RAW_PARSE_DEBUG_PRINTED:
                print(f"[raw-parse-debug-response] type={type(response).__name__} repr={repr(response)}", file=sys.stderr)
                print(f"[raw-parse-debug-content-type] {type(response.content).__name__}", file=sys.stderr)
                print(f"[raw-parse-debug] {repr(text[:600])}", file=sys.stderr)
                _RAW_PARSE_DEBUG_PRINTED = True
            return status, normalized
        except Exception as exc:
            last_error = repr(exc)
            print(f"[match-error] attempt {attempt}/{attempts}: {last_error}", file=sys.stderr)
            is_500 = "code:500" in last_error.lower()
            if attempt < attempts and is_500:
                backoff = min(OLLAMA_RETRY_DELAY_SEC * (2 ** (attempt - 1)), OLLAMA_RETRY_MAX_DELAY_SEC)
                time.sleep(backoff)
                continue
            break

    return (
        "ERROR",
        (
            "Status: ERROR\n"
            "Quote: N/A\n"
            f"{second_field}: model call failed after retries.\n"
            f"Error: {last_error}"
        ),
    )


def _overall_status(statuses: list[str]) -> str:
    if any(s == "ERROR" for s in statuses):
        return "ERROR"
    if any(s == "OK" for s in statuses):
        return "OK"
    if any(s == "NOT_COVERED" for s in statuses):
        return "NOT_COVERED"
    return "NOT_ROUTED"

MATCH_FACT_PROMPT = """/no_think

You are given one fact about a trading setup, and the section of a \
trading strategy document that governs it.

Quote the single line or table row from the section below that applies to this fact, then \
state what it implies for this setup.

Rules:
- Quote text that appears in the section below, exactly as written. Do not paraphrase and do \
not reconstruct a table row from memory.
- If the section does not actually address this fact, write: NOT COVERED
- Do not add rules that are not in the text below.
- Do not give a verdict on the trade.

Answer in exactly this format:
Quote: "<exact text from the section>"
Implication: <one or two sentences>

=== FACT ===
{fact}

=== SECTION {section_number} ===
{section_text}
"""

MATCH_UNKNOWN_PROMPT = """/no_think

You are given one piece of information that is MISSING from a \
trading setup description, and the section of a trading strategy document that needs it.

Quote the line or table row from the section below that requires this information, then state \
what cannot be decided without it.

Rules:
- Quote text that appears in the section below, exactly as written. Do not paraphrase and do \
not reconstruct a table row from memory.
- Do not guess or assume a value for the missing information.
- If the section does not actually require this information, write: NOT COVERED
- Do not give a verdict on the trade.

Answer in exactly this format:
Quote: "<exact text from the section>"
Blocks: <what cannot be determined without it, one or two sentences>

=== MISSING INFORMATION ===
{unknown}

=== SECTION {section_number} ===
{section_text}
"""

def match_one_fact(
    llm,
    sections: dict[str, str],
    fact: str,
    llm_on_length_retry=None,
    llm_for_ctx=None,
    llm_on_length_retry_for_ctx=None,
) -> tuple[str, str]:
    section_numbers = route(fact)
    if not section_numbers:
        return (
            "NOT_ROUTED",
            f"FACT: {fact}\n"
            "Route: []\n"
            "Status: NOT_ROUTED\n"
            "Section: not covered\n"
            "Quote: N/A\n"
            "Implication: not covered by routing rules (no model call)."
        )

    outputs: list[str] = []
    statuses: list[str] = []
    for section_number in section_numbers:
        section_text = sections.get(section_number, "").strip()
        if not section_text:
            statuses.append("ERROR")
            outputs.append(
                f"Section {section_number}:\n"
                "Status: ERROR\n"
                "Quote: N/A\n"
                "Implication: routed section was not found in the parsed strategy map."
            )
            continue

        excerpt = _prepare_section_text_for_prompt(section_number, section_text, fact)
        prompt = MATCH_FACT_PROMPT.format(
            fact=fact,
            section_number=section_number,
            section_text=excerpt,
        )
        if ENABLE_DYNAMIC_SECTION_CTX:
            section_ctx = _recommended_num_ctx_for_section(excerpt)
            active_llm = llm_for_ctx(section_ctx) if llm_for_ctx is not None else llm
            retry_llm = (
                llm_on_length_retry_for_ctx(section_ctx)
                if llm_on_length_retry_for_ctx is not None
                else llm_on_length_retry
            )
        else:
            active_llm = llm
            retry_llm = llm_on_length_retry

        status, response_text = _invoke_with_retry(
            active_llm,
            prompt,
            "Implication",
            llm_on_length_retry=retry_llm,
        )
        status, response_text = _table_row_guard(status, response_text, "Implication", section_text)
        statuses.append(status)
        outputs.append(f"Section {section_number}:\n{response_text}")

        section_unverified = find_unverified_quotes(response_text, section_text)
        for quote in section_unverified:
            outputs.append(
                f"Verification: UNVERIFIED quote in section {section_number}: \"{quote}\""
            )

    overall = _overall_status(statuses)
    return (
        overall,
        f"FACT: {fact}\nRoute: {section_numbers}\nStatus: {overall}\n" + "\n\n".join(outputs),
    )

def match_one_unknown(
    llm,
    sections: dict[str, str],
    unknown: str,
    llm_on_length_retry=None,
    llm_for_ctx=None,
    llm_on_length_retry_for_ctx=None,
) -> tuple[str, str]:
    section_numbers = route(unknown)
    if not section_numbers:
        return (
            "NOT_ROUTED",
            f"UNKNOWN: {unknown}\n"
            "Route: []\n"
            "Status: NOT_ROUTED\n"
            "Section: not covered\n"
            "Quote: N/A\n"
            "Blocks: not covered by routing rules (no model call)."
        )

    outputs: list[str] = []
    statuses: list[str] = []
    for section_number in section_numbers:
        section_text = sections.get(section_number, "").strip()
        if not section_text:
            statuses.append("ERROR")
            outputs.append(
                f"Section {section_number}:\n"
                "Status: ERROR\n"
                "Quote: N/A\n"
                "Blocks: routed section was not found in the parsed strategy map."
            )
            continue

        excerpt = _prepare_section_text_for_prompt(section_number, section_text, unknown)
        prompt = MATCH_UNKNOWN_PROMPT.format(
            unknown=unknown,
            section_number=section_number,
            section_text=excerpt,
        )
        if ENABLE_DYNAMIC_SECTION_CTX:
            section_ctx = _recommended_num_ctx_for_section(excerpt)
            active_llm = llm_for_ctx(section_ctx) if llm_for_ctx is not None else llm
            retry_llm = (
                llm_on_length_retry_for_ctx(section_ctx)
                if llm_on_length_retry_for_ctx is not None
                else llm_on_length_retry
            )
        else:
            active_llm = llm
            retry_llm = llm_on_length_retry

        status, response_text = _invoke_with_retry(
            active_llm,
            prompt,
            "Blocks",
            llm_on_length_retry=retry_llm,
        )
        status, response_text = _table_row_guard(status, response_text, "Blocks", section_text)
        statuses.append(status)
        outputs.append(f"Section {section_number}:\n{response_text}")

        section_unverified = find_unverified_quotes(response_text, section_text)
        for quote in section_unverified:
            outputs.append(
                f"Verification: UNVERIFIED quote in section {section_number}: \"{quote}\""
            )

    overall = _overall_status(statuses)
    return (
        overall,
        f"UNKNOWN: {unknown}\nRoute: {section_numbers}\nStatus: {overall}\n" + "\n\n".join(outputs),
    )


def build_stage3_verdict(
    fact_results: list[tuple[str, str, str]],
    unknown_results: list[tuple[str, str, str]],
) -> str:
    error_facts = [item for status, item, _ in fact_results if status == "ERROR"]
    error_unknowns = [item for status, item, _ in unknown_results if status == "ERROR"]

    if error_facts or error_unknowns:
        failed = error_unknowns + error_facts
        return (
            "Status: ERROR\n"
            "Verdict: cannot review this setup.\n"
            "Reason: one or more required checks failed to evaluate due to model/runtime errors.\n"
            f"Failed items: {', '.join(failed)}"
        )

    if unknown_results:
        pending = [item for _, item, _ in unknown_results]
        return (
            "Status: INCOMPLETE\n"
            "Verdict: cannot issue a trade call from this setup description.\n"
            "Reason: required information is missing.\n"
            f"Missing items: {', '.join(pending)}"
        )

    return (
        "Status: COMPLETE\n"
        "Verdict: all routed checks completed with no missing required inputs.\n"
        "Reason: no blocking unknowns and no evaluation errors were detected."
    )

def build_human_message(strategy_text: str , setup_description: str) -> str:
    strategy_excerpt = build_relevant_strategy_excerpt(
        strategy_text=strategy_text,
        setup_description=setup_description,
        restated_facts="",
        max_chars=PROMPT_CONTEXT_CHARS,
    )
    return f"""=== STRATEGY DOCUMENT (RELEVANT EXCERPT) ===
{strategy_excerpt}

{setup_description}
Evaluate this setup against the strategy document above."""


def warm_match_model(llm) -> None:
    """Preload match model to avoid first-call cold-load timeout."""
    try:
        llm.invoke([HumanMessage(content="/no_think\nReply exactly: READY")])
    except Exception as exc:
        print(f"[warmup-error] {repr(exc)}", file=sys.stderr)

# 4. Script body — only runs when you execute this file directly
if __name__ == "__main__":
    # Make console printing robust on Windows terminals using legacy encodings.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    if "--test-sections" in sys.argv:
        _standalone_section_parser_test(STRATEGY_PATH)
        raise SystemExit(0)

    strategy_text = STRATEGY_PATH.read_text(encoding="utf-8")
    sections = extract_sections(strategy_text)

    setup_description = (
        "XAUUSD. Daily bias bullish, higher highs and higher lows intact. "
        "H1 pulled back into an A-grade demand zone. Price just swept the zone's low "
        "and is starting to react upward, no CHoCH confirmed yet."
    )

    if "--test-call1-parser" in sys.argv:
        llm_restate = ChatOllama(
            base_url=OLLAMA_BASE_URL,
            model=OLLAMA_RESTATE_MODEL,
            temperature=0.1,
            num_ctx=OLLAMA_NUM_CTX_RESTATE,
        )
        restated = restate_facts(llm_restate, setup_description)
        print("\n--- CALL 1 RAW OUTPUT ---\n")
        print(restated)

        facts, unknowns = parse_restate_output(restated)
        print("\n--- PARSED FACTS ---\n")
        for idx, item in enumerate(facts, start=1):
            print(f"{idx}. {item}")

        print("\n--- PARSED UNKNOWNS ---\n")
        for idx, item in enumerate(unknowns, start=1):
            print(f"{idx}. {item}")

        raise SystemExit(0)


    effective_match_model = _resolve_match_model()

    llm_restate = ChatOllama(
        base_url=OLLAMA_BASE_URL,
        model=OLLAMA_RESTATE_MODEL,
        temperature=0.1,
        num_ctx=OLLAMA_NUM_CTX_RESTATE,
    )
    llm_match = ChatOllama(
        base_url=OLLAMA_BASE_URL,
        model=effective_match_model,
        temperature=0.1,
        num_ctx=OLLAMA_NUM_CTX_MATCH,
        num_predict=OLLAMA_MATCH_NUM_PREDICT,
        keep_alive=OLLAMA_MATCH_KEEP_ALIVE,
    )
    llm_match_retry = ChatOllama(
        base_url=OLLAMA_BASE_URL,
        model=effective_match_model,
        temperature=0.1,
        num_ctx=OLLAMA_NUM_CTX_MATCH,
        num_predict=OLLAMA_MATCH_NUM_PREDICT_RETRY,
        keep_alive=OLLAMA_MATCH_KEEP_ALIVE,
    )

    warm_match_model(llm_match)

    llm_cache_base: dict[tuple[int, int], ChatOllama] = {}
    llm_cache_retry: dict[tuple[int, int], ChatOllama] = {}

    def llm_for_ctx(num_ctx: int):
        return _build_match_llm(
            model=effective_match_model,
            num_ctx=num_ctx,
            num_predict=OLLAMA_MATCH_NUM_PREDICT,
            cache=llm_cache_base,
        )

    def llm_retry_for_ctx(num_ctx: int):
        return _build_match_llm(
            model=effective_match_model,
            num_ctx=num_ctx,
            num_predict=OLLAMA_MATCH_NUM_PREDICT_RETRY,
            cache=llm_cache_retry,
        )

    restated = restate_facts(llm_restate, setup_description)
    print("\n--- STAGE 1: RESTATED FACTS ---\n")
    print(restated)

    facts, unknowns = parse_restate_output(restated)
    print("\n--- STAGE 2: MATCHED RULES ---\n")
    fact_results: list[tuple[str, str, str]] = []
    unknown_results: list[tuple[str, str, str]] = []
    for fact in facts:
        status, output = match_one_fact(
            llm_match,
            sections,
            fact,
            llm_on_length_retry=llm_match_retry,
            llm_for_ctx=llm_for_ctx,
            llm_on_length_retry_for_ctx=llm_retry_for_ctx,
        )
        fact_results.append((status, fact, output))
        print(output)
    for unknown in unknowns:
        status, output = match_one_unknown(
            llm_match,
            sections,
            unknown,
            llm_on_length_retry=llm_match_retry,
            llm_for_ctx=llm_for_ctx,
            llm_on_length_retry_for_ctx=llm_retry_for_ctx,
        )
        unknown_results.append((status, unknown, output))
        print(output)

    print("\n--- STAGE 3: VERDICT ---\n")
    print(build_stage3_verdict(fact_results, unknown_results))