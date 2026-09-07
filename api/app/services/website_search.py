from __future__ import annotations

import logging
import re
import unicodedata
from urllib.parse import urlparse

import requests

from app.services.website_probe import Candidate

logger = logging.getLogger(__name__)

SEARXNG_TIMEOUT = 6.0
MAX_RESULTS = 5

BLOCKLIST_SUFFIXES = (
    "societe.com", "pagesjaunes.fr", "infogreffe.fr", "verif.com",
    "wordpress.com", "wixsite.com", "blogspot.com", "github.io",
    "herokuapp.com", "cloudfront.net", "amazonaws.com",
    "google.com", "facebook.com", "linkedin.com", "twitter.com",
    "instagram.com", "youtube.com", "sharepoint.com", "azurewebsites.net",
)

TLDS_KEEP = (".fr", ".com", ".net", ".eu", ".bzh", ".paris", ".org")


def _slug(denomination: str) -> str:
    nfkd = unicodedata.normalize("NFKD", denomination)
    text = "".join(c for c in nfkd if not unicodedata.combining(c)).lower()
    return re.sub(r"[^a-z0-9]+", "", text)


def _is_plausible(domain: str, slug: str) -> bool:
    if not domain or "*" in domain or domain.count(".") < 1:
        return False
    domain = domain.lower().strip()
    if any(domain == b or domain.endswith("." + b) for b in BLOCKLIST_SUFFIXES):
        return False
    if not domain.endswith(TLDS_KEEP):
        return False
    label = domain.split(".")[0].replace("-", "")
    return len(slug) >= 4 and slug[:4] in label


def search_searxng(denomination: str | None, base_url: str, commune: str | None = None) -> list[Candidate]:
    if not denomination:
        return []
    denomination = denomination.strip()
    if not denomination or denomination == "[ND]":
        return []

    slug = _slug(denomination)
    if len(slug) < 4:
        return []

    query = f"{denomination} {commune.strip()}" if commune and commune.strip() else denomination

    try:
        resp = requests.get(
            f"{base_url.rstrip('/')}/search",
            params={"q": query, "format": "json", "categories": "general"},
            timeout=SEARXNG_TIMEOUT,
            headers={"User-Agent": "ProspectEngine/0.1"},
        )
        resp.raise_for_status()
        data = resp.json()
    except (requests.RequestException, ValueError) as exc:
        logger.warning("SearXNG search failed for %r: %s", denomination, exc)
        return []

    candidates: list[Candidate] = []
    seen: set[str] = set()

    for result in data.get("results", []):
        url = result.get("url", "")
        try:
            domain = urlparse(url).netloc.removeprefix("www.")
        except Exception:
            continue

        if not domain or domain in seen:
            continue
        if not _is_plausible(domain, slug):
            continue

        seen.add(domain)
        candidates.append(Candidate(url=f"https://{domain}", domain=domain, pattern="searxng"))

        if len(candidates) >= MAX_RESULTS:
            break

    return candidates
