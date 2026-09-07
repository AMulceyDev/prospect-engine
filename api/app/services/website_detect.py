from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.progress import progress
from app.db.models import Company, Website
from app.db.session import SessionLocal
from app.services.website_probe import Candidate, ProbeResult, probe_many, score_detection
from app.services.website_search import search_searxng

logger = logging.getLogger(__name__)

COMPANY_WORKERS = 5


def detect_for_company(company: Company, db: Session) -> int:
    db.execute(delete(Website).where(Website.company_id == company.id))

    now = datetime.now(UTC)
    rows: list[Website] = []

    if company.noms_de_domaine:
        # Domains declared in RNE or found via OSM — probe directly, preserving source.
        # Each entry: {"domain": str, "source": "rne" | "osm"}
        entries = company.noms_de_domaine
        known_candidates = [
            Candidate(url=f"https://{e['domain']}", domain=e["domain"], pattern=f"{e['source']}_declared")
            for e in entries
        ]
        for entry, res in zip(entries, probe_many(known_candidates), strict=True):
            rows.append(_to_row(company.id, res, source=entry["source"], now=now))
    else:
        # No known domain — discover via SearXNG then probe.
        candidates = search_searxng(company.denomination, settings.searxng_url, commune=company.commune)
        for res in probe_many(candidates):
            rows.append(_to_row(company.id, res, source="searxng", now=now))

    if not rows:
        return 0

    best = max(rows, key=lambda r: r.confidence)
    if best.confidence > 45:
        best.is_selected = True

    db.add_all(rows)
    db.commit()
    return len(rows)


def _to_row(company_id: int, res: ProbeResult, source: str, now: datetime) -> Website:
    return Website(
        company_id=company_id,
        url=res.url,
        domain=res.domain,
        pattern=res.pattern,
        source=source,
        dns_resolved=res.dns_resolved,
        http_status=res.http_status,
        final_url=res.final_url,
        is_https=res.is_https,
        response_time_ms=res.response_time_ms,
        error=res.error,
        confidence=score_detection(res, source),
        is_selected=False,
        checked_at=now,
    )


def _process_company(siren: str) -> int:
    """Worker: owns its own DB session so it is safe to run in a thread."""
    db = SessionLocal()
    try:
        company = db.scalar(select(Company).where(Company.siren == siren))
        if company is None:
            return 0
        return detect_for_company(company, db)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def detect_pending_websites(limit: int | None = None, db: Session | None = None) -> dict:
    # Use the caller's session only to fetch the work list, then close it before
    # spawning threads — sessions must not be shared across threads.
    own_session = db is None
    db = db or SessionLocal()
    try:
        already_done = select(Website.company_id).distinct()
        stmt = select(Company.siren).where(Company.id.not_in(already_done))
        if limit is not None:
            stmt = stmt.limit(limit)
        sirens = db.scalars(stmt).all()
    finally:
        if own_session:
            db.close()

    processed = 0
    probed = 0
    total = len(sirens)
    progress.set("websites", 0, total)
    try:
        with ThreadPoolExecutor(max_workers=COMPANY_WORKERS) as pool:
            futures = {pool.submit(_process_company, siren): siren for siren in sirens}
            for future in as_completed(futures):
                siren = futures[future]
                try:
                    probed += future.result()
                    processed += 1
                except Exception:
                    logger.warning(
                        "Failed to detect websites for company %s", siren, exc_info=True
                    )
                progress.set("websites", processed, total)
    finally:
        progress.reset()

    return {"processed": processed, "candidates_probed": probed}
