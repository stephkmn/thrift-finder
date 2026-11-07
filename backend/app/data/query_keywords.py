
"""Convert clothing attributes into search keywords."""

from backend.app.schemas import Attributes

MISSING = {"", "unknown", "none", "n/a", "not applicable"}
NEGATIVE_PREFIXES = ("no ", "without ", "remove ")


def build_keywords(edited: Attributes) -> str:
    """Create positive search keywords from edited attributes."""
    parts: list[str] = []
    seen: set[str] = set()

    candidates = [
        edited.color,
        edited.fabric,
        edited.category,
        edited.fit,
    ]
    candidates.extend(edited.others or [])

    for candidate in candidates:
        value = " ".join(candidate.split())
        folded = value.casefold()

        if (
            not value
            or folded in MISSING
            or folded in seen
            or folded.startswith(NEGATIVE_PREFIXES)
        ):
            continue

        parts.append(value)
        seen.add(folded)

    return " ".join(parts)
