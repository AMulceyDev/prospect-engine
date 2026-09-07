from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
from urllib.parse import urlparse

import requests

logger = logging.getLogger(__name__)

_TIMEOUT = 8.0
_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; ProspectEngine/1.0)"}


def get_sitemap_dates(domain: str, is_https: bool = True) -> dict | None:
    """Fetch /sitemap.xml and return URL count + most recent lastmod date.

    Handles <sitemapindex> by following the first child sitemap.

    Returns {"last_modified": str | None, "page_count": int} or None on failure.

    Note: <lastmod> is frequently absent or auto-generated to today's date by
    CMS plugins, making it an unreliable freshness signal. Treat page_count and
    last_modified as weak indicators only — never as decisive scoring factors.
    """
    xml_text = _fetch_sitemap_xml(domain, "/sitemap.xml", is_https)
    if xml_text is None:
        return None

    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        logger.debug("Sitemap XML parse error for %s: %s", domain, exc)
        return None

    if _local_tag(root.tag) == "sitemapindex":
        xml_text = _follow_first_sub(root, domain, is_https)
        if xml_text is None:
            return None
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError as exc:
            logger.debug("Sub-sitemap XML parse error for %s: %s", domain, exc)
            return None

    return _extract_url_stats(root, domain)


# ── internal helpers ──────────────────────────────────────────────────────────

def _local_tag(tag: str) -> str:
    """Strip XML namespace from a tag string."""
    return tag.split("}")[-1] if "}" in tag else tag


def _fetch_sitemap_xml(domain: str, path: str, is_https: bool) -> str | None:
    schemes = ["https", "http"] if is_https else ["http", "https"]
    for scheme in schemes:
        url = f"{scheme}://{domain}{path}"
        try:
            resp = requests.get(url, timeout=_TIMEOUT, allow_redirects=True, headers=_HEADERS)
            if resp.status_code == 200 and resp.text.strip().startswith("<"):
                return resp.text
        except Exception:
            continue
    return None


def _follow_first_sub(index_root: ET.Element, domain: str, is_https: bool) -> str | None:
    """Return the XML text of the first <sitemap><loc> entry in a sitemapindex."""
    for sitemap_el in index_root:
        if _local_tag(sitemap_el.tag) != "sitemap":
            continue
        for child in sitemap_el:
            if _local_tag(child.tag) == "loc" and child.text:
                parsed = urlparse(child.text.strip())
                path = parsed.path or "/sitemap.xml"
                return _fetch_sitemap_xml(domain, path, is_https)
    return None


def _extract_url_stats(root: ET.Element, domain: str) -> dict | None:
    dates: list[str] = []
    url_count = 0

    for url_el in root:
        if _local_tag(url_el.tag) != "url":
            continue
        url_count += 1
        for child in url_el:
            if _local_tag(child.tag) == "lastmod" and child.text:
                raw = child.text.strip()
                if len(raw) >= 10:
                    dates.append(raw[:10])  # keep YYYY-MM-DD

    if url_count == 0:
        logger.debug("Sitemap for %s contained no <url> entries", domain)
        return None

    last_modified = max(dates) if dates else None
    logger.debug("Sitemap for %s: %d URLs, last_modified=%s", domain, url_count, last_modified)
    return {"last_modified": last_modified, "page_count": url_count}
