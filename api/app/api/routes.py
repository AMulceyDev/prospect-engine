import requests as _requests

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.db.models import Company, Contact, Dirigeant
from app.db.session import get_db
from app.schemas.company import (
    AnalyzeResult,
    CompanyDetail,
    CompanyRead,
    EnrichResult,
    EnrichSirenResult,
    FilterResult,
    IngestResult,
    LegalFormCount,
    WebsiteDetectResult,
)
from app.services.contact_classify import classify_contact
from app.core.progress import progress
from app.services.analyze import analyze_pending
from app.services.filter import delete_non_prospects
from app.services.legal_forms import DEFAULT_EXCLUDE_PREFIXES, label
from app.services.ingestion import (
    enrich_from_rne,
    enrich_pending_from_rne,
    ingest_from_insee,
)
from app.services.inpi import InpiClient, RNEAuthError, RNEQuotaExceeded
from app.services.insee import InseeClient
from app.services.osm import enrich_osm_for_company
from app.services.website_detect import detect_pending_websites

router = APIRouter()


def get_insee_client() -> InseeClient:
    return InseeClient(api_key=settings.insee_api_key)


def get_inpi_client() -> InpiClient:
    return InpiClient(
        username=settings.inpi_username,
        password=settings.inpi_password,
    )


@router.post("/ingest/run", response_model=IngestResult)
def run_ingestion(
    days: int = 120,
    rows: int = 50,
    at_date: str | None = None,
    active_only: bool = False,
    categorie_min: int | None = 5000,
    categorie_max: int | None = 6999,
    db: Session = Depends(get_db),
    client: InseeClient = Depends(get_insee_client),
):
    try:
        data = client.fetch_recent_companies(
            days=days,
            at_date=at_date,
            rows=rows,
            active_only=active_only,
            categorie_min=categorie_min,
            categorie_max=categorie_max,
        )
    except _requests.exceptions.HTTPError as exc:
        status = exc.response.status_code if exc.response is not None else 502
        if status == 401:
            raise HTTPException(status_code=401, detail="INSEE API key missing or invalid — set INSEE_API_KEY in your environment.")
        raise HTTPException(status_code=502, detail=f"INSEE API error: {status}")
    except _requests.exceptions.RequestException as exc:
        raise HTTPException(status_code=502, detail=f"INSEE API unreachable: {exc}")
    result = ingest_from_insee(data, db=db)
    return IngestResult(fetched=len(data), **result)


@router.post("/ingest/enrich", response_model=EnrichResult)
def run_enrichment(
    limit: int = 100,
    db: Session = Depends(get_db),
    client: InpiClient = Depends(get_inpi_client),
):
    try:
        result = enrich_pending_from_rne(client, limit=limit, db=db)
    except RNEAuthError:
        raise HTTPException(status_code=401, detail="INPI credentials missing or invalid — set INPI_USERNAME and INPI_PASSWORD.")
    except RNEQuotaExceeded:
        raise HTTPException(status_code=429, detail="Daily RNE quota exceeded — try again tomorrow.")
    return EnrichResult(**result)


@router.post("/ingest/enrich/{siren}", response_model=EnrichResult)
def run_enrichment_one(
    siren: str,
    db: Session = Depends(get_db),
    client: InpiClient = Depends(get_inpi_client),
):
    try:
        success = enrich_from_rne(siren, client, db=db)
    except RNEAuthError:
        raise HTTPException(status_code=401, detail="INPI credentials missing or invalid — set INPI_USERNAME and INPI_PASSWORD.")
    except RNEQuotaExceeded:
        raise HTTPException(status_code=429, detail="Daily RNE quota exceeded — try again tomorrow.")
    return EnrichResult(enriched=1 if success else 0, candidates=1)


@router.post("/ingest/filter", response_model=FilterResult)
def run_filter(
    exclude_prefixes: list[str] | None = Query(default=None),
    dry_run: bool = False,
    db: Session = Depends(get_db),
):
    result = delete_non_prospects(db, exclude_prefixes=exclude_prefixes, dry_run=dry_run)
    return FilterResult(**result)


@router.post("/ingest/websites", response_model=WebsiteDetectResult)
def run_website_detection(limit: int | None = None, db: Session = Depends(get_db)):
    return detect_pending_websites(limit=limit, db=db)


@router.post("/analyze/run", response_model=AnalyzeResult)
def run_analyze(
    limit: int = 10,
    sirens: str | None = Query(None, description="Comma-separated SIRENs to analyze"),
    force: bool = False,
    db: Session = Depends(get_db),
):
    siren_list = [s.strip() for s in sirens.split(",")] if sirens else None
    return analyze_pending(limit=limit, sirens=siren_list, force=force, db=db)


@router.post("/enrich/{siren}", response_model=EnrichSirenResult)
def enrich_company(
    siren: str,
    db: Session = Depends(get_db),
    client: InpiClient = Depends(get_inpi_client),
):
    company = db.scalar(select(Company).where(Company.siren == siren))
    if company is None:
        raise HTTPException(status_code=404, detail="Company not found")

    rne_ok = False
    try:
        rne_ok = enrich_from_rne(siren, client, db=db)
    except RNEAuthError:
        raise HTTPException(status_code=401, detail="INPI credentials missing or invalid — set INPI_USERNAME and INPI_PASSWORD.")
    except RNEQuotaExceeded:
        raise HTTPException(status_code=429, detail="Daily RNE quota exceeded — try again tomorrow.")

    rne_dirigeants = db.scalar(
        select(func.count()).select_from(Dirigeant).where(Dirigeant.company_id == company.id)
    )

    osm = enrich_osm_for_company(siren, db=db)

    return EnrichSirenResult(
        siren=siren,
        rne_ok=rne_ok,
        rne_dirigeants=rne_dirigeants or 0,
        osm_ok=osm["ok"],
        osm_domain=osm["domain"],
        osm_contacts=osm["contacts"],
    )


@router.get("/companies", response_model=list[CompanyRead])
def list_companies(
    skip: int = 0,
    limit: int | None = Query(default=None),
    code_postal: str | None = None,
    with_domain: bool | None = None,
    db: Session = Depends(get_db),
):
    stmt = select(Company).options(
        selectinload(Company.websites),
        selectinload(Company.contacts),
        selectinload(Company.analysis),
    )
    if code_postal:
        stmt = stmt.where(Company.code_postal == code_postal)
    if with_domain is True:
        stmt = stmt.where(Company.noms_de_domaine != [])
    elif with_domain is False:
        stmt = stmt.where(Company.noms_de_domaine == [])
    stmt = stmt.order_by(Company.updated_at.desc()).offset(skip)
    if limit is not None:
        stmt = stmt.limit(limit)
    return db.scalars(stmt).all()


@router.get("/companies/stats/legal-forms", response_model=list[LegalFormCount])
def company_legal_form_stats(db: Session = Depends(get_db)):
    """Distribution of all companies in DB by forme_juridique, with INSEE labels."""
    rows = (
        db.query(Company.forme_juridique, func.count(Company.id))
        .group_by(Company.forme_juridique)
        .order_by(func.count(Company.id).desc())
        .all()
    )
    return [LegalFormCount(code=code, label=label(code), count=count) for code, count in rows]


@router.get("/companies/{siren}", response_model=CompanyDetail)
def get_company(siren: str, db: Session = Depends(get_db)):
    stmt = (
        select(Company)
        .where(Company.siren == siren)
        .options(
            selectinload(Company.dirigeants),
            selectinload(Company.websites),
            selectinload(Company.contacts),
            selectinload(Company.analysis),
        )
    )
    company = db.scalar(stmt)
    if company is None:
        raise HTTPException(status_code=404, detail="Company not found")
    return company


@router.post("/contacts/classify", response_model=dict)
def classify_null_contacts(db: Session = Depends(get_db)):
    """Backfill: classify all contacts whose nature is NULL. Idempotent — never overwrites
    an already-classified contact."""
    contacts = db.scalars(select(Contact).where(Contact.nature.is_(None))).all()
    updated = 0
    for c in contacts:
        c.nature = classify_contact(c.type, c.value)
        updated += 1
    db.commit()
    return {"updated": updated}


@router.get("/progress")
def get_progress():
    return progress.to_dict()


@router.delete("/companies", response_model=dict)
def clear_companies(
    sirens: str | None = Query(None, description="Comma-separated SIRENs — omit to delete all"),
    db: Session = Depends(get_db),
):
    if sirens:
        siren_list = [s.strip() for s in sirens.split(",")]
        deleted = db.query(Company).filter(Company.siren.in_(siren_list)).delete(synchronize_session=False)
    else:
        deleted = db.query(Company).delete()
    db.commit()
    return {"deleted": deleted}
