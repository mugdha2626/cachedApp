"""Pure ingestion-pipeline logic: parse, split, and freshness rating.

Everything here is deterministic and I/O-free so it can be unit-tested without a
database or network. The service layer feeds these outputs into summarisation,
embedding, and persistence.
"""

import re
from dataclasses import dataclass
from datetime import date, datetime

# A word is ~0.75 tokens, so a token budget maps to a smaller word budget.
_WORDS_PER_TOKEN = 0.75
_FALLBACK_OVERLAP = 0.15  # fraction of a window repeated into the next one

_HEADER_RE = re.compile(r"^#{1,6}\s+\S")
_BLANK_RUN_RE = re.compile(r"\n{3,}")
_TRAILING_WS_RE = re.compile(r"[ \t]+$", re.MULTILINE)

_MONTHS = {
    m: i
    for i, m in enumerate(
        "january february march april may june july august september october "
        "november december".split(),
        start=1,
    )
}
_ISO_RE = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")
_MONTH_YEAR_RE = re.compile(r"\b(" + "|".join(_MONTHS) + r")\s+(\d{4})\b", re.IGNORECASE)
_YEAR_RE = re.compile(r"\b(19|20)\d{2}\b")

_FRESHNESS_HALF_LIFE_YEARS = 5.0
_FRESHNESS_FLOOR = 0.1
_NEUTRAL_FRESHNESS = 0.5


@dataclass(frozen=True, slots=True)
class PageDraft:
    order_index: int
    raw_text: str


def normalize(text: str) -> str:
    """Trim trailing whitespace and collapse blank-line runs, keeping headers."""
    text = _TRAILING_WS_RE.sub("", text)
    text = _BLANK_RUN_RE.sub("\n\n", text)
    return text.strip()


def split_into_pages(text: str, max_page_tokens: int) -> list[PageDraft]:
    """Split into pages on markdown headers, windowing any oversized section.

    Deep-research artifacts are usually organised by sub-question, so headers are
    the natural page boundary. Preamble before the first header becomes its own
    page. Sections longer than the token budget are cut into overlapping windows.
    """
    sections = _split_on_headers(normalize(text))
    drafts: list[PageDraft] = []
    for section in sections:
        for chunk in _window(section, max_page_tokens):
            drafts.append(PageDraft(order_index=len(drafts), raw_text=chunk))
    return drafts


def _split_on_headers(text: str) -> list[str]:
    sections: list[str] = []
    current: list[str] = []
    for line in text.splitlines():
        if _HEADER_RE.match(line) and current:
            sections.append("\n".join(current).strip())
            current = []
        current.append(line)
    if current:
        sections.append("\n".join(current).strip())
    return [s for s in sections if s]


def _window(section: str, max_page_tokens: int) -> list[str]:
    words = section.split()
    budget = max(1, int(max_page_tokens * _WORDS_PER_TOKEN))
    if len(words) <= budget:
        return [section]

    step = max(1, budget - int(budget * _FALLBACK_OVERLAP))
    chunks: list[str] = []
    for start in range(0, len(words), step):
        chunks.append(" ".join(words[start : start + budget]))
        if start + budget >= len(words):
            break
    return chunks


def rate_freshness(text: str, now: datetime | None = None) -> float:
    """Score recency in [0, 1] from the most recent date mentioned in the text.

    Neutral (0.5) when no date is determinable; decays linearly toward a floor
    over roughly the half-life, and future dates saturate at 1.0.
    """
    today = (now or datetime.now()).date()
    latest = _latest_date(text)
    if latest is None:
        return _NEUTRAL_FRESHNESS

    age_years = (today - latest).days / 365.25
    freshness = 1.0 - age_years / _FRESHNESS_HALF_LIFE_YEARS
    return max(_FRESHNESS_FLOOR, min(1.0, freshness))


def _latest_date(text: str) -> date | None:
    candidates: list[date] = []

    for year, month, day in _ISO_RE.findall(text):
        parsed = _safe_date(int(year), int(month), int(day))
        if parsed:
            candidates.append(parsed)

    for month_name, year in _MONTH_YEAR_RE.findall(text):
        candidates.append(date(int(year), _MONTHS[month_name.lower()], 1))

    for match in _YEAR_RE.finditer(text):
        candidates.append(date(int(match.group()), 1, 1))

    return max(candidates) if candidates else None


def _safe_date(year: int, month: int, day: int) -> date | None:
    try:
        return date(year, month, day)
    except ValueError:
        return None
