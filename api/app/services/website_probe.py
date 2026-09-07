from __future__ import annotations

import socket
import time
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeoutError
from dataclasses import dataclass
from urllib.parse import urlparse

import requests

USER_AGENT = "Mozilla/5.0"


@dataclass(frozen=True)
class Candidate:
    url: str
    domain: str
    pattern: str

DNS_TIMEOUT = 3.0
HTTP_TIMEOUT = 5.0
MAX_WORKERS = 10

_PARKING_DOMAINS = {
    "sedo.com", "sedoparking.com",
    "afternic.com",
    "dan.com",
    "hugedomains.com",
    "parkingcrew.net",
    "bodis.com",
    "above.com",
    "buydomains.com",
    "domainmarket.com",
    "undeveloped.com",
    "squadhelp.com",
    "epik.com",
    "flippa.com",
    "brandpa.com",
}


def _is_parking_redirect(final_url: str | None) -> bool:
    if not final_url:
        return False
    host = urlparse(final_url).hostname or ""
    host = host.removeprefix("www.")
    return host in _PARKING_DOMAINS or any(host.endswith("." + p) for p in _PARKING_DOMAINS)


@dataclass
class ProbeResult:
    domain: str
    pattern: str
    url: str
    dns_resolved: bool = False
    http_status: int | None = None
    final_url: str | None = None
    is_https: bool | None = None
    response_time_ms: int | None = None
    error: str | None = None
    is_parked: bool = False


def _resolve_dns(domain: str) -> bool:
    # Reject before hitting the IDNA codec: labels must be ≤ 63 chars
    if any(len(label) > 63 for label in domain.split(".")):
        return False
    # socket.setdefaulttimeout is process-global and not thread-safe;
    # wrap in a dedicated thread so we can enforce a timeout safely
    with ThreadPoolExecutor(max_workers=1) as ex:
        future = ex.submit(socket.getaddrinfo, domain, None)
        try:
            future.result(timeout=DNS_TIMEOUT)
            return True
        except (socket.gaierror, OSError, FuturesTimeoutError, UnicodeEncodeError):
            return False


def probe(candidate: Candidate, session: requests.Session | None = None) -> ProbeResult:
    result = ProbeResult(
        domain=candidate.domain,
        pattern=candidate.pattern,
        url=candidate.url,
    )

    if not _resolve_dns(candidate.domain):
        result.error = "dns_error"
        return result
    result.dns_resolved = True

    sess = session or requests.Session()
    headers = {"User-Agent": USER_AGENT}
    start = time.monotonic()
    try:
        resp = sess.head(
            candidate.url, headers=headers, timeout=HTTP_TIMEOUT,
            allow_redirects=True,
        )
        if resp.status_code >= 400:
            resp = sess.get(
                candidate.url, headers=headers, timeout=HTTP_TIMEOUT,
                allow_redirects=True, stream=True,
            )
            resp.close()
        result.http_status = resp.status_code
        result.final_url = resp.url
        result.is_https = resp.url.startswith("https://")
        result.response_time_ms = int((time.monotonic() - start) * 1000)
        result.is_parked = _is_parking_redirect(resp.url)
    except requests.exceptions.SSLError:
        result.error = "ssl_error"
    except requests.exceptions.Timeout:
        result.error = "timeout"
    except requests.exceptions.ConnectionError:
        result.error = "connection_error"
    except requests.exceptions.RequestException as exc:
        result.error = f"request_error:{type(exc).__name__}"
    finally:
        if session is None:
            sess.close()

    return result


def probe_many(candidates: list[Candidate]) -> list[ProbeResult]:
    if not candidates:
        return []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futures = [pool.submit(probe, c) for c in candidates]
        return [f.result() for f in futures]


def score_detection(result: ProbeResult, source: str) -> int:
    if not result.dns_resolved:
        return 0
    if result.is_parked:
        return 0

    # source ∈ "rne" | "osm" | "searxng"
    # Confidence ranking: rne (officially declared) > osm (fuzzy-matched) > searxng (web search)
    if source == "rne":
        if result.error or result.http_status is None:
            return 35
        base = 95

    elif source == "osm":
        if result.error or result.http_status is None:
            return 25
        status = result.http_status
        if status < 400:
            base = 75
        elif status in (401, 403, 429, 503):
            base = 65
        else:
            base = 40

    elif source == "searxng":
        if result.error or result.http_status is None:
            return 20
        status = result.http_status
        if status < 400:
            base = 60
        elif status in (401, 403, 429, 503):
            base = 50
        else:
            base = 30

    else:
        return 0

    if result.is_https:
        base += 5

    return min(base, 100)
