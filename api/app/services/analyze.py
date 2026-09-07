from __future__ import annotations

import logging
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session, selectinload

from app.core.progress import progress
from app.db.models import Analysis, Company, Contact, Website
from app.db.session import SessionLocal
from app.services.contact_classify import classify_contact
from app.services.lighthouse import parse_lighthouse, run_lighthouse
from app.services.page_reader import (
    check_ownership,
    crawl_site,
    is_parking_page,
)
from app.services.sitemap import get_sitemap_dates
from app.services.tech_detect import detect_tech
from app.services.wayback import get_first_seen

logger = logging.getLogger(__name__)


def _upsert_page_contacts(company_id: int, contacts: dict, db: Session) -> None:
    """Write page contacts into the contacts table (source="page"), idempotent."""
    rows = [
        {"company_id": company_id, "type": "email", "value": v, "source": "page",
         "nature": classify_contact("email", v)}
        for v in contacts["emails"]
    ] + [
        {"company_id": company_id, "type": "phone", "value": v, "source": "page",
         "nature": classify_contact("phone", v)}
        for v in contacts["phones"]
    ]
    if not rows:
        return
    insert_stmt = pg_insert(Contact).values(rows)
    stmt = insert_stmt.on_conflict_do_update(
        index_elements=["company_id", "type", "value"],
        set_={"nature": insert_stmt.excluded.nature},
        where=Contact.nature.is_(None),
    )
    db.execute(stmt)


def _mark_osm_contacts_suspicious(company_id: int, confirmed_domain: str, company: Company, db: Session) -> None:
    """Set suspicious=True on OSM contacts when the OSM domain doesn't match the confirmed site."""
    osm_domains = {
        e["domain"]
        for e in (company.noms_de_domaine or [])
        if isinstance(e, dict) and e.get("source") == "osm"
    }
    osm_contacts = db.scalars(
        select(Contact).where(
            Contact.company_id == company_id,
            Contact.source == "osm",
        )
    ).all()
    if not osm_contacts:
        return

    is_mismatch = confirmed_domain not in osm_domains
    for c in osm_contacts:
        c.suspicious = is_mismatch


def analyze_company(company: Company, db: Session) -> str:
    """Analyze the selected website of a company.

    Returns one of: "no_site", "not_owned", "indeterminate", "done".

    Deselection (is_selected=False) only happens on a clear rejection:
    content was successfully read AND no ownership signals were found.
    Indeterminate outcomes (fetch failure, thin content) leave the site selected.

    # DEBT: ownership_signals->>'verdict' is queried as JSONB text in analyze_pending.
    # A dedicated ownership_verdict column in analyses would be cleaner for the UI.
    """
    website = next((w for w in company.websites if w.is_selected), None)
    if not website:
        return "no_site"

    url = website.final_url or website.url
    domain = website.domain

    # Single network pass — crawl collects all content needed for ownership + contacts
    crawl = crawl_site(url)

    # Upsert analysis row and always write site_map fields
    analysis = db.scalar(select(Analysis).where(Analysis.company_id == company.id))
    if analysis is None:
        analysis = Analysis(company_id=company.id, website_id=website.id)
        db.add(analysis)

    analysis.internal_links = crawl["internal_links"]
    analysis.external_links = crawl["external_links"]
    analysis.has_legal_page = crawl["has_legal_page"]
    analysis.has_contact_info = crawl["has_contact_info"]
    analysis.provider_hint = crawl["provider_hint"]
    analysis.analyzed_at = datetime.now(UTC)

    # Home fetch failed entirely — cannot conclude ownership
    if crawl["fetch_failed"]:
        analysis.ownership_confirmed = False
        analysis.ownership_signals = {"verdict": "indeterminate", "reason": "fetch_failed", "score": 0}
        db.commit()
        return "indeterminate"

    home_page = crawl["home_page"]

    # Parking page → clear non-ownership signal, deselect
    if is_parking_page(home_page):
        website.is_selected = False
        _mark_osm_contacts_suspicious(company.id, domain, company, db)
        analysis.ownership_confirmed = False
        analysis.ownership_signals = {"verdict": "rejected", "reason": "parking_page", "score": 0}
        db.commit()
        return "not_owned"

    # Pure ownership check against all crawled content (no network)
    pages_text = crawl["pages_text"]
    rule_result = check_ownership(pages_text, company, domain=domain)
    verdict = rule_result["verdict"]
    ownership_signals = {**rule_result["signals"], "verdict": verdict, "score": rule_result["score"]}

    analysis.ownership_confirmed = verdict == "confirmed"
    analysis.ownership_signals = ownership_signals

    if verdict == "rejected":
        # Content read, no signals → clear non-ownership, deselect
        website.is_selected = False
        _mark_osm_contacts_suspicious(company.id, domain, company, db)
        db.commit()
        return "not_owned"

    if verdict == "indeterminate":
        # Thin content — cannot conclude, leave site selected for future re-analysis
        db.commit()
        return "indeterminate"

    # verdict in ("confirmed", "probable") — write contacts for both
    contacts = crawl["contacts"]
    _upsert_page_contacts(company.id, contacts, db)
    _mark_osm_contacts_suspicious(company.id, domain, company, db)

    # Tier 1 audit (confirmed + probable): fast, no subprocess
    tech_stack = detect_tech(home_page)
    wayback_first_seen = get_first_seen(domain)
    sitemap = get_sitemap_dates(domain, is_https=bool(website.is_https))

    # Tier 2 audit (confirmed only): Lighthouse — Chromium subprocess, 30-120s
    lh_scores: dict | None = None
    lh_seo: dict | None = None
    lh_remarks: list | None = None

    if verdict == "confirmed":
        lh_raw = run_lighthouse(url)
        if lh_raw:
            parsed = parse_lighthouse(lh_raw)
            lh_scores = parsed["scores"]
            lh_seo = parsed["seo"]
            lh_remarks = parsed["remarks"]

    analysis.tech_stack = tech_stack
    analysis.wayback_first_seen = wayback_first_seen
    analysis.sitemap_last_modified = sitemap["last_modified"] if sitemap else None
    analysis.sitemap_page_count = sitemap["page_count"] if sitemap else None
    analysis.llm_score = None
    analysis.llm_obsolete = None
    analysis.llm_verdict = None
    analysis.lighthouse_scores = lh_scores
    analysis.lighthouse_seo = lh_seo
    analysis.lighthouse_remarks = lh_remarks

    db.commit()
    return "done"


def analyze_pending(
    limit: int = 10,
    sirens: list[str] | None = None,
    force: bool = False,
    db: Session | None = None,
) -> dict:
    """Analyze companies with a selected website.

    Default (no sirens, no force): skips companies that already have a
    non-indeterminate analysis. Indeterminate analyses are re-queued because
    they represent fetch failures or thin content that may resolve on retry.

    force=True: re-analyzes all companies regardless of existing analysis.

    sirens: always re-analyzes the given SIRENs (force has no additional effect).
    """
    own_session = db is None
    db = db or SessionLocal()
    done = not_owned = indeterminate = no_site = 0

    try:
        stmt = (
            select(Company)
            .join(Website, (Website.company_id == Company.id) & Website.is_selected)
            .options(
                selectinload(Company.websites),
                selectinload(Company.dirigeants),
            )
        )
        if sirens:
            stmt = stmt.where(Company.siren.in_(sirens))
        elif force:
            stmt = stmt.limit(limit)
        else:
            # Pending = no analysis yet, or indeterminate (re-tryable)
            stmt = (
                stmt
                .outerjoin(Analysis, Analysis.company_id == Company.id)
                .where(
                    (Analysis.id.is_(None))
                    | (Analysis.ownership_signals["verdict"].astext == "indeterminate")
                )
                .limit(limit)
            )
        companies = db.scalars(stmt).all()
        total = len(companies)
        progress.set("analyze", 0, total)

        for i, company in enumerate(companies):
            outcome = analyze_company(company, db)
            if outcome == "done":
                done += 1
            elif outcome == "not_owned":
                not_owned += 1
            elif outcome == "indeterminate":
                indeterminate += 1
            else:
                no_site += 1
            progress.set("analyze", i + 1, total)
    finally:
        progress.reset()
        if own_session:
            db.close()

    return {
        "done": done,
        "not_owned": not_owned,
        "indeterminate": indeterminate,
        "no_site": no_site,
    }
