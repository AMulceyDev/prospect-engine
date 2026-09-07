from __future__ import annotations

import difflib
import logging
import re
import time
import unicodedata
from urllib.parse import urlparse

import requests
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.db.models import Company, Contact
from app.services.contact_classify import classify_contact

logger = logging.getLogger(__name__)

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
OVERPASS_TIMEOUT = 30
MATCH_THRESHOLD = 0.72
_INTER_QUERY_DELAY = 1.0  # polite delay between Overpass requests

_LEGAL_TERMS = re.compile(
    r"\b(sarl|sas|sasu|eurl|sa|sci|snc|scp|gie|ei|eirl|"
    r"holding|groupe|compagnie|cie|france)\b",
    re.IGNORECASE,
)


def _normalize_name(name: str) -> str:
    nfkd = unicodedata.normalize("NFKD", name)
    text = "".join(c for c in nfkd if not unicodedata.combining(c)).lower()
    text = _LEGAL_TERMS.sub("", text)
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]+", " ", text)).strip()


def _extract_domain(url: str) -> str | None:
    try:
        parsed = urlparse(url if "://" in url else f"https://{url}")
        # Strip leading www. so it matches RNE-style domain storage
        return parsed.netloc.removeprefix("www.") or None
    except Exception:
        return None


def _fetch_pois(code_insee: str) -> list[dict]:
    # Use ref:INSEE rather than name to avoid commune name ambiguity
    query = f"""
[out:json][timeout:{OVERPASS_TIMEOUT}];
area["ref:INSEE"="{code_insee}"]["admin_level"="8"]->.a;
(
  node["name"]["website"](area.a);
  way["name"]["website"](area.a);
  node["name"]["contact:website"](area.a);
  way["name"]["contact:website"](area.a);
);
out body;
"""
    try:
        resp = requests.post(
            OVERPASS_URL,
            data={"data": query},
            timeout=OVERPASS_TIMEOUT + 5,
            headers={"User-Agent": "ProspectEngine/0.1"},
        )
        resp.raise_for_status()
        return resp.json().get("elements", [])
    except (requests.RequestException, ValueError) as exc:
        logger.warning("Overpass failed for INSEE %s: %s", code_insee, exc)
        return []


def _best_match(
    poi_name: str,
    candidates: list[tuple[int, str]],
) -> tuple[int, float] | None:
    """Return (company_id, score) of the best match above MATCH_THRESHOLD, or None."""
    norm_poi = _normalize_name(poi_name)
    if not norm_poi:
        return None
    best_id, best_score = None, 0.0
    for company_id, denomination in candidates:
        score = difflib.SequenceMatcher(
            None, norm_poi, _normalize_name(denomination or "")
        ).ratio()
        if score > best_score:
            best_score, best_id = score, company_id
    if best_id is not None and best_score >= MATCH_THRESHOLD:
        return best_id, best_score
    return None


def _fetch_pois_extended(code_insee: str) -> list[dict]:
    """Broader Overpass query for per-company enrichment: includes phone/email-only POIs."""
    query = f"""
[out:json][timeout:{OVERPASS_TIMEOUT}];
area["ref:INSEE"="{code_insee}"]["admin_level"="8"]->.a;
(
  node["name"]["website"](area.a);
  way["name"]["website"](area.a);
  node["name"]["contact:website"](area.a);
  way["name"]["contact:website"](area.a);
  node["name"]["phone"](area.a);
  way["name"]["phone"](area.a);
  node["name"]["email"](area.a);
  way["name"]["email"](area.a);
  node["name"]["contact:phone"](area.a);
  way["name"]["contact:phone"](area.a);
  node["name"]["contact:email"](area.a);
  way["name"]["contact:email"](area.a);
);
out body;
"""
    try:
        resp = requests.post(
            OVERPASS_URL,
            data={"data": query},
            timeout=OVERPASS_TIMEOUT + 5,
            headers={"User-Agent": "ProspectEngine/0.1"},
        )
        resp.raise_for_status()
        return resp.json().get("elements", [])
    except (requests.RequestException, ValueError) as exc:
        logger.warning("Overpass extended failed for INSEE %s: %s", code_insee, exc)
        return []


def enrich_osm_for_company(siren: str, db: Session) -> dict:
    """Single-company OSM enrichment: one Overpass query, fuzzy-match, writes domain +
    contacts. Returns {"ok": bool, "domain": str|None, "contacts": int}."""
    company = db.scalar(select(Company).where(Company.siren == siren))
    if company is None or not company.code_insee_commune:
        return {"ok": False, "domain": None, "contacts": 0}

    time.sleep(_INTER_QUERY_DELAY)
    pois = _fetch_pois_extended(company.code_insee_commune)
    if not pois:
        return {"ok": False, "domain": None, "contacts": 0}

    norm_company = _normalize_name(company.denomination or "")
    best_poi: dict | None = None
    best_score = 0.0
    for poi in pois:
        name = poi.get("tags", {}).get("name", "")
        if not name:
            continue
        score = difflib.SequenceMatcher(None, _normalize_name(name), norm_company).ratio()
        if score > best_score:
            best_score = score
            best_poi = poi

    if best_poi is None or best_score < MATCH_THRESHOLD:
        return {"ok": False, "domain": None, "contacts": 0}

    tags = best_poi.get("tags", {})

    domain: str | None = None
    website = tags.get("website") or tags.get("contact:website")
    if website:
        domain = _extract_domain(website)
        if domain:
            existing = {e["domain"] for e in company.noms_de_domaine}
            if domain not in existing:
                company.noms_de_domaine = [*company.noms_de_domaine, {"domain": domain, "source": "osm"}]

    contacts_written = 0
    for ctype, keys in [
        ("phone", ["phone", "contact:phone"]),
        ("email", ["email", "contact:email"]),
    ]:
        for key in keys:
            value = tags.get(key)
            if value:
                insert_stmt = pg_insert(Contact).values(
                    company_id=company.id,
                    type=ctype,
                    value=value,
                    source="osm",
                    nature=classify_contact(ctype, value),
                )
                stmt = insert_stmt.on_conflict_do_update(
                    index_elements=["company_id", "type", "value"],
                    set_={"nature": insert_stmt.excluded.nature},
                    where=Contact.nature.is_(None),
                )
                result = db.execute(stmt)
                contacts_written += result.rowcount
                break  # first matching tag variant wins

    db.commit()
    return {"ok": True, "domain": domain, "contacts": contacts_written}


# NOTE: enrich_with_osm (bulk, per-municipality) is no longer called via API since
# POST /ingest/osm was removed in lot 5. Kept for potential future use or CLI tooling.
def enrich_with_osm(db: Session) -> dict:
    """For each municipality with companies that have no known domains, query OSM Overpass
    and write matched domains into noms_de_domaine for the next website detection run."""
    companies = db.scalars(
        select(Company)
        .where(Company.code_insee_commune.isnot(None))
        .where(Company.noms_de_domaine == [])
    ).all()

    by_municipality: dict[str, list[Company]] = {}
    for c in companies:
        by_municipality.setdefault(c.code_insee_commune, []).append(c)

    clusters_processed = 0
    matched = 0
    first = True

    for code_insee, municipality_companies in by_municipality.items():
        if not first:
            time.sleep(_INTER_QUERY_DELAY)
        first = False

        pois = _fetch_pois(code_insee)
        clusters_processed += 1
        if not pois:
            continue

        candidates = [(c.id, c.denomination) for c in municipality_companies]
        company_by_id = {c.id: c for c in municipality_companies}

        for element in pois:
            tags = element.get("tags", {})
            poi_name = tags.get("name", "")
            website = tags.get("website") or tags.get("contact:website")
            if not poi_name or not website:
                continue

            match = _best_match(poi_name, candidates)
            if match is None:
                continue

            company_id, _ = match
            domain = _extract_domain(website)
            if not domain:
                continue

            company = company_by_id[company_id]
            existing = {e["domain"] for e in company.noms_de_domaine}
            if domain not in existing:
                company.noms_de_domaine = [*company.noms_de_domaine, {"domain": domain, "source": "osm"}]
                matched += 1

    db.commit()
    return {"clusters_processed": clusters_processed, "matched": matched}
