from __future__ import annotations

import json
from pathlib import Path

_NAF_LABELS: dict[str, str] = json.loads(
    (Path(__file__).parent / "data" / "codes_naf.json").read_text(encoding="utf-8")
)


def label(code: str | None) -> str:
    """Return the human-readable label for a NAF/APE code.
    Accepts both formats: '47.25Z' (with dot, as stored in DB) and '4725Z' (without dot).
    Falls back to the raw code if not in the mapping, or 'Inconnu' if None."""
    if code is None:
        return "Inconnu"
    normalized = code.replace(".", "").upper()
    return _NAF_LABELS.get(normalized, code)
