from __future__ import annotations

import logging
from datetime import UTC, datetime

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db.models import Company, Website
from app.db.session import SessionLocal
from app.services.website_candidates import Candidate, generate_candidates
from app.services.website_probe import ProbeResult, probe_many, score_detection

logger = logging.getLogger(__name__)


def detect_for_company(company: Company, db: Session) -> int:
    db.execute(delete(Website).where(Website.company_id == company.id))

    now = datetime.now(UTC)
    rows: list[Website] = []

    rne_candidates = [
        Candidate(url=f"https://{d}", domain=d, pattern="rne_declared")
        for d in (company.noms_de_domaine or [])
    ]
    rne_results = probe_many(rne_candidates)
    for res in rne_results:
        rows.append(_to_row(company.id, res, source="rne", now=now))

    if not company.noms_de_domaine:
        gen_candidates = generate_candidates(company.denomination)
        gen_results = probe_many(gen_candidates)
        for res in gen_results:
            rows.append(_to_row(company.id, res, source="generated", now=now))

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


def detect_pending_websites(limit: int = 50, db: Session | None = None) -> dict:
    own_session = db is None
    db = db or SessionLocal()
    processed = 0
    probed = 0
    try:
        already_done = select(Website.company_id).distinct()
        companies = db.scalars(
            select(Company).where(Company.id.not_in(already_done)).limit(limit)
        ).all()
        for company in companies:
            try:
                probed += detect_for_company(company, db)
                processed += 1
            except Exception:
                db.rollback()
                logger.warning(
                    "Failed to detect websites for company %s", company.siren, exc_info=True
                )
        return {"processed": processed, "candidates_probed": probed}
    finally:
        if own_session:
            db.close()
