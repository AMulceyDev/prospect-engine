from __future__ import annotations

INPI_ROLE_LABELS: dict[str, str] = {
    # À compléter depuis la nomenclature officielle INPI RNE
}


def label(code: str | None) -> str:
    """Return the human-readable label for an INPI role code.
    Falls back to the raw code if not in the mapping, or 'Inconnu' if None."""
    if code is None:
        return "Inconnu"
    return INPI_ROLE_LABELS.get(str(code), code)
