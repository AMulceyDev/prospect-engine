from __future__ import annotations

import re
import time
import unicodedata
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from app.db.models import Company

_EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
_PHONE_RE = re.compile(r"(?:(?:\+|00)33[\s.\-]?|0)[1-9](?:[\s.\-]?\d{2}){4}")
_SIREN_RE = re.compile(r"\b\d{3}[\s.\-]?\d{3}[\s.\-]?\d{3}\b")

_MENTIONS_LEGALES_PATTERNS = re.compile(
    r"mentions?[_\-\s]?l[ée]gales?|legal|juridique|cgv|cgu|rgpd",
    re.IGNORECASE,
)

_PROVIDER_PATTERNS = re.compile(
    r"réalis[ée]\s*par|création\s*(du\s*)?site|fait\s*par|made\s*by"
    r"|designed?\s*by|developed?\s*by|par\s+l[''']agence|agence\s+web"
    r"|webmaster|powered\s*by",
    re.IGNORECASE,
)

_USEFUL_LINK_PATTERNS = re.compile(
    r"mentions?[_\-\s]?l[ée]gales?|legal|juridique|cgv|cgu|rgpd"
    r"|confidentialit[ée]|privacy|contact|about|[àa]-propos|nous[_\-\s]?contacter",
    re.IGNORECASE,
)

_SKIP_SCHEMES = re.compile(r"^(mailto:|tel:|javascript:|#)", re.IGNORECASE)

# Legal abbreviations stripped before denomination fuzzy-match
_LEGAL_ABBREVS_RE = re.compile(
    r"\b(s\.?a\.?r\.?l\.?|s\.?a\.?s\.?u?\.?|s\.?c\.?i\.?|s\.?n\.?c\.?|s\.?c\.?s\.?"
    r"|e\.?u\.?r\.?l\.?|e\.?a\.?r\.?l\.?|g\.?i\.?e\.?|s\.?e\.?l\.?"
    r"|sarl|sasu|sas|sci|snc|scs|eurl|earl|gie|sel|sa|se)\b",
    re.IGNORECASE,
)

_PARKING_TEXT_RE = re.compile(
    r"domain\s+(is\s+)?for\s+sale"
    r"|buy\s+this\s+domain"
    r"|purchase\s+this\s+domain"
    r"|make\s+an\s+offer"
    r"|inquire\s+about\s+this\s+domain"
    r"|ce\s+domaine\s+est\s+(en\s+vente|[àa]\s+vendre)"
    r"|acheter\s+ce\s+domaine"
    r"|domaine\s+[àa]\s+vendre",
    re.IGNORECASE,
)

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; ProspectEngine/1.0; +https://example.com/bot)"
    ),
    "Accept-Language": "fr-FR,fr;q=0.9",
}

# Minimum character count to consider page content readable
_MIN_CONTENT_LEN = 200

# Signals derived from reading page content (not from structural comparison)
_STRONG_CONTENT_SIGNALS = frozenset({"denomination", "denomination_approx", "code_postal", "dirigeant"})


def fetch_page(url: str, timeout: float = 15.0) -> dict:
    resp = requests.get(url, headers=_HEADERS, timeout=timeout, allow_redirects=True)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "lxml")
    return {
        "html": resp.text,
        "text": soup.get_text(separator=" ", strip=True),
        "soup": soup,
        "final_url": resp.url,
        "headers": dict(resp.headers),
        "status": resp.status_code,
    }


def _find_mentions_legales_url(page: dict) -> str | None:
    soup: BeautifulSoup = page["soup"]
    base = page["final_url"]
    for a in soup.find_all("a", href=True):
        href = a["href"]
        text = a.get_text(strip=True)
        if _MENTIONS_LEGALES_PATTERNS.search(href) or _MENTIONS_LEGALES_PATTERNS.search(text):
            return urljoin(base, href)
    return None


def _extract_links(page: dict) -> tuple[list[str], list[str]]:
    """Return (internal_links, external_links) from a fetched page."""
    soup: BeautifulSoup = page["soup"]
    base = page["final_url"]
    base_netloc = urlparse(base).netloc

    internal: list[str] = []
    external: list[str] = []
    seen: set[str] = set()

    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if _SKIP_SCHEMES.match(href):
            continue
        full = urljoin(base, href)
        parsed = urlparse(full)
        full = parsed._replace(fragment="").geturl()
        if full in seen:
            continue
        seen.add(full)
        if parsed.netloc == base_netloc:
            internal.append(full)
        elif parsed.netloc:
            external.append(full)

    return internal, external


def _detect_provider(page: dict) -> str | None:
    """Scan <footer> tags for a web-agency backlink. Returns a short hint or None."""
    soup: BeautifulSoup = page["soup"]
    base = page["final_url"]
    base_netloc = urlparse(base).netloc

    footers = soup.find_all("footer")
    if not footers:
        return None

    for footer in footers:
        for a in footer.find_all("a", href=True):
            text = a.get_text(strip=True)
            if not _PROVIDER_PATTERNS.search(text):
                continue
            full = urljoin(base, a["href"].strip())
            netloc = urlparse(full).netloc
            if netloc and netloc != base_netloc:
                return f"{text} ({full})" if text else full
            return text

        for el in footer.find_all(string=_PROVIDER_PATTERNS):
            snippet = el.strip()[:120]
            if snippet:
                return snippet

    return None


def _aggregate_contacts(pages: list[dict]) -> dict:
    """Extract and deduplicate contacts across multiple pages."""
    emails: set[str] = set()
    phones: set[str] = set()
    for page in pages:
        c = extract_contacts(page)
        emails.update(c["emails"])
        phones.update(c["phones"])
    return {"emails": sorted(emails), "phones": sorted(phones)}


def crawl_site(
    url: str,
    max_pages: int = 10,
    timeout_per_page: float = 8.0,
    total_budget: float = 30.0,
) -> dict:
    """Shallow crawl of a website (depth=1).

    Fetches the home page plus directly linked internal pages, up to max_pages.
    Useful pages (legal/contact/about) are prioritised over generic ones so the
    checklist booleans are reliable even when max_pages is hit early.

    Returns:
        internal_links   — deduplicated internal URLs found across all visited pages
        external_links   — deduplicated external URLs found across all visited pages
        has_legal_page   — mentions légales / CGU / politique de confidentialité found
        has_contact_info — email or phone found
        provider_hint    — web-agency backlink text/URL from footer, or None
        pages_text       — concatenated text from all visited pages (for ownership check)
        home_page        — the fetched home page dict (for parking check / tech detect)
        fetch_failed     — True if the home page could not be fetched at all
        contacts         — aggregated contacts from all visited pages
    """
    _EMPTY: dict = {
        "internal_links": [],
        "external_links": [],
        "has_legal_page": False,
        "has_contact_info": False,
        "provider_hint": None,
        "pages_text": "",
        "home_page": None,
        "fetch_failed": True,
        "contacts": {"emails": [], "phones": []},
    }

    deadline = time.monotonic() + total_budget

    try:
        home = fetch_page(url, timeout=timeout_per_page)
    except Exception:
        return _EMPTY

    home_internal, home_external = _extract_links(home)
    base_netloc = urlparse(home["final_url"]).netloc

    all_internal: set[str] = set(home_internal)
    all_external: set[str] = set(home_external)
    visited: set[str] = {home["final_url"]}

    useful = [u for u in home_internal if _USEFUL_LINK_PATTERNS.search(u)]
    generic = [u for u in home_internal if u not in useful]
    candidates = useful + generic

    pages_visited = [home]
    for candidate in candidates:
        if len(visited) >= max_pages:
            break
        if time.monotonic() >= deadline:
            break
        if candidate in visited:
            continue
        try:
            page = fetch_page(candidate, timeout=timeout_per_page)
        except Exception:
            continue
        visited.add(candidate)
        pages_visited.append(page)
        p_internal, p_external = _extract_links(page)
        all_internal.update(p_internal)
        all_external.update(p_external)

    has_legal_page = False
    has_contact_info = False
    provider_hint: str | None = None

    for page in pages_visited:
        if not has_legal_page:
            if _find_mentions_legales_url(page):
                has_legal_page = True
            if _USEFUL_LINK_PATTERNS.search(page["final_url"]):
                has_legal_page = True

        if not has_contact_info:
            contacts = extract_contacts(page)
            if contacts["emails"] or contacts["phones"]:
                has_contact_info = True

        if provider_hint is None:
            provider_hint = _detect_provider(page)

    return {
        "internal_links": sorted(all_internal - {home["final_url"]}),
        "external_links": sorted(all_external),
        "has_legal_page": has_legal_page,
        "has_contact_info": has_contact_info,
        "provider_hint": provider_hint,
        "pages_text": " ".join(p["text"] for p in pages_visited),
        "home_page": home,
        "fetch_failed": False,
        "contacts": _aggregate_contacts(pages_visited),
    }


def _merge_pages(main: dict, extra: dict) -> dict:
    return {
        **main,
        "text": main["text"] + " " + extra["text"],
        "html": main["html"] + extra["html"],
    }


def is_parking_page(page: dict) -> bool:
    return bool(_PARKING_TEXT_RE.search(page.get("text", "")))


def check_ownership(text: str, company: Company, domain: str | None = None) -> dict:
    """Graduated ownership check (confirmed / probable / rejected / indeterminate).

    Pure function — no network calls. All content is passed in as `text`.

    Returns {"verdict": str, "score": float, "signals": dict}.

    Verdicts:
        confirmed    — SIREN present (excludes homonyms, confirms alone)
        probable     — score ≥ 2.0 AND at least one strong content signal
        rejected     — content read but no sufficient ownership signals
        indeterminate — content too thin to score reliably (< 200 chars)
    """
    if len(text.strip()) < _MIN_CONTENT_LEN:
        return {"verdict": "indeterminate", "score": 0.0, "signals": {"reason": "empty_content"}}

    signals = _extract_signals(text, company, domain=domain)
    verdict, score = _score_ownership(signals)
    return {"verdict": verdict, "score": score, "signals": signals}


def _extract_signals(text: str, company: Company, domain: str | None = None) -> dict:
    signals: dict = {}
    text_lower = text.lower()

    if company.siren:
        for m in _SIREN_RE.findall(text):
            if re.sub(r"[\s.\-]", "", m) == company.siren:
                signals["siren"] = True
                break

    if company.denomination:
        denom = company.denomination.strip()
        if denom.lower() in text_lower:
            signals["denomination"] = True
        elif not signals.get("denomination"):
            if _denomination_approx_match(denom, text_lower):
                signals["denomination_approx"] = True

    if company.code_postal and company.code_postal in text:
        signals["code_postal"] = True

    if company.commune:
        commune_norm = _normalise_str(company.commune)
        if commune_norm and commune_norm in _normalise_str(text):
            signals["commune"] = True

    for dirigeant in getattr(company, "dirigeants", None) or []:
        nom = (dirigeant.nom or "").strip()
        if len(nom) >= 4 and nom.lower() in text_lower:
            signals["dirigeant"] = True
            break

    # Domain-name signal: significant denomination words found in domain root
    # Structural signal (quasi-tautological for SearXNG results) — corroborating only.
    if domain and company.denomination:
        domain_root = domain.split(".")[0]
        if _denomination_in_domain(company.denomination, domain_root):
            signals["domain_name"] = True

    return signals


def _denomination_in_domain(denomination: str, domain_root: str) -> bool:
    """True if ≥80% of significant denomination words (≥4 chars) appear in the domain root."""
    stripped = _LEGAL_ABBREVS_RE.sub("", denomination)
    words = [
        _strip_accents(w.lower())
        for w in re.findall(r"[a-zA-ZÀ-ÿ]{4,}", stripped)
        if w.lower() not in {"pour", "avec", "dans", "chez"}
    ]
    if not words:
        return False
    domain_norm = _strip_accents(domain_root.lower())
    matched = sum(1 for w in words if w in domain_norm)
    return matched / len(words) >= 0.8


def _strip_accents(s: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", s)
        if unicodedata.category(c) != "Mn"
    )


def _normalise_str(s: str) -> str:
    """Lowercase + strip accents + collapse whitespace."""
    return re.sub(r"\s+", " ", _strip_accents(s.lower()).strip())


def _denomination_approx_match(denomination: str, text_lower: str) -> bool:
    """True if ≥80% of significant words (≥4 chars, non-legal) of the denomination appear in text.

    Both sides are accent-normalized before comparison.
    """
    stripped = _LEGAL_ABBREVS_RE.sub("", denomination)
    words = [
        _strip_accents(w.lower())
        for w in re.findall(r"[a-zA-ZÀ-ÿ]{4,}", stripped)
        if w.lower() not in {"pour", "avec", "dans", "chez"}
    ]
    if not words:
        return False
    text_norm = _strip_accents(text_lower)
    matched = sum(1 for w in words if w in text_norm)
    return matched / len(words) >= 0.8


_SIGNAL_WEIGHTS: dict[str, float] = {
    "siren": 4.0,
    "denomination": 2.0,
    "domain_name": 1.5,
    "denomination_approx": 1.0,
    "code_postal": 1.0,
    "dirigeant": 1.0,
    "commune": 0.5,
}


def _score_ownership(signals: dict) -> tuple[str, float]:
    """Return (verdict, score).

    Rules:
        confirmed    — siren present (unconditional)
        probable     — score ≥ 2.0 AND at least one strong content signal
        rejected     — everything else

    Strong content signals (derived from reading the page, not structural comparison):
        denomination, denomination_approx, code_postal, dirigeant

    domain_name and commune are corroborating signals only — they never make
    a site "probable" on their own because domain_name is quasi-tautological
    (SearXNG found the domain by name similarity) and commune is weak.
    """
    if signals.get("siren"):
        score = sum(_SIGNAL_WEIGHTS.get(k, 0) for k in signals if signals[k] is True)
        return "confirmed", score

    score = sum(
        _SIGNAL_WEIGHTS.get(k, 0)
        for k in signals
        if k not in ("source", "reason") and signals[k] is True
    )
    has_content_signal = any(signals.get(k) for k in _STRONG_CONTENT_SIGNALS)

    if score >= 2.0 and has_content_signal:
        return "probable", score
    return "rejected", score


def extract_contacts(page: dict) -> dict:
    soup: BeautifulSoup = page["soup"]
    text = page["text"]

    emails: set[str] = set()
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if href.startswith("mailto:"):
            addr = href[7:].split("?")[0].strip()
            if addr:
                emails.add(addr.lower())
    for m in _EMAIL_RE.findall(text):
        emails.add(m.lower())

    junk_exts = {".png", ".jpg", ".gif", ".svg", ".js", ".css", ".woff"}
    emails = {e for e in emails if not any(e.endswith(x) for x in junk_exts)}

    phones = list({_normalise_phone(p) for p in _PHONE_RE.findall(text)})

    return {"emails": sorted(emails), "phones": phones}


def _normalise_phone(raw: str) -> str:
    digits = re.sub(r"\D", "", raw)
    if digits.startswith("33") and len(digits) == 11:
        digits = "0" + digits[2:]
    return digits
