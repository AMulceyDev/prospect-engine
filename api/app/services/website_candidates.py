from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

STOPWORDS = {
    "sci", "sarl", "sas", "sasu", "eurl", "snc", "sa", "selarl", "scp", "spfpl",
    "sccv", "scm", "gie", "ei", "eirl", "et", "de", "des", "du", "la", "le", "les",
    "aux", "au", "compagnie", "cie", "groupe", "holding", "france",
}

TLDS = ("fr", "com")


@dataclass(frozen=True)
class Candidate:
    url: str
    domain: str
    pattern: str


def _strip_accents(text: str) -> str:
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def _tokens(denomination: str) -> list[str]:
    text = _strip_accents(denomination).lower()
    raw = re.split(r"[^a-z0-9]+", text)
    return [t for t in raw if t]


def generate_candidates(denomination: str | None) -> list[Candidate]:
    if not denomination:
        return []
    denomination = denomination.strip()
    if not denomination or denomination == "[ND]":
        return []

    tokens = _tokens(denomination)
    if not tokens:
        return []

    brand = [t for t in tokens if t not in STOPWORDS] or tokens

    bases: list[tuple[str, str]] = []

    def add(slug: str, name: str) -> None:
        if slug and (slug, name) not in bases and not any(s == slug for s, _ in bases):
            bases.append((slug, name))

    add("".join(brand), "brand_join")
    add("-".join(brand), "brand_hyphen")
    add("".join(tokens), "full_join")
    add("-".join(tokens), "full_hyphen")

    candidates: list[Candidate] = []
    seen: set[str] = set()
    for slug, base_name in bases:
        if len(slug.replace("-", "")) < 2:
            continue
        for tld in TLDS:
            domain = f"{slug}.{tld}"
            if domain in seen:
                continue
            seen.add(domain)
            candidates.append(
                Candidate(
                    url=f"https://{domain}",
                    domain=domain,
                    pattern=f"{base_name}.{tld}",
                )
            )
    return candidates