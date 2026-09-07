from __future__ import annotations

import logging

import requests

logger = logging.getLogger(__name__)

_CDX_URL = "https://web.archive.org/cdx/search/cdx"


def get_first_seen(domain: str, timeout: float = 20.0) -> str | None:
    """Return the earliest Wayback Machine archive date (YYYYMMDD) for the domain, or None."""
    try:
        resp = requests.get(
            _CDX_URL,
            params={
                "url": domain,
                "matchType": "domain",
                "output": "json",
                "limit": 1,
                "from": "19960101",
                "fl": "timestamp",
                "filter": "statuscode:200",
                "collapse": "timestamp:6",
            },
            timeout=timeout,
        )
        resp.raise_for_status()
        rows = resp.json()
        if len(rows) > 1:
            return rows[1][0][:8]  # YYYYMMDD
    except Exception as exc:
        logger.warning("Wayback Machine unavailable for %s: %s", domain, exc)
    return None
