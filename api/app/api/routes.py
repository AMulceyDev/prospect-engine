from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.db.models import Company
from app.db.session import get_db
from app.schemas.company import (
    CompanyDetail,
    CompanyRead,
    EnrichResult,
    IngestResult,
    WebsiteDetectResult,
)
from app.services.ingestion import (
    enrich_pending_from_rne,
    ingest_from_insee,
)
from app.services.inpi import InpiClient
from app.services.insee import InseeClient
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
    db: Session = Depends(get_db),
    client: InseeClient = Depends(get_insee_client),
):
    data = client.fetch_recent_companies(days=days, rows=rows)
    result = ingest_from_insee(data, db=db)
    return IngestResult(fetched=len(data), **result)


@router.post("/ingest/enrich", response_model=EnrichResult)
def run_enrichment(
    limit: int = 100,
    db: Session = Depends(get_db),
    client: InpiClient = Depends(get_inpi_client),
):
    result = enrich_pending_from_rne(client, limit=limit, db=db)
    return EnrichResult(**result)


@router.post("/ingest/websites", response_model=WebsiteDetectResult)
def run_website_detection(limit: int = 50, db: Session = Depends(get_db)):
    return detect_pending_websites(limit=limit, db=db)


@router.get("/companies", response_model=list[CompanyRead])
def list_companies(
    skip: int = 0,
    limit: int = Query(default=50, le=200),
    code_postal: str | None = None,
    with_domain: bool | None = None,
    db: Session = Depends(get_db),
):
    stmt = select(Company)
    if code_postal:
        stmt = stmt.where(Company.code_postal == code_postal)
    if with_domain is True:
        stmt = stmt.where(Company.noms_de_domaine != [])
    elif with_domain is False:
        stmt = stmt.where(Company.noms_de_domaine == [])
    stmt = stmt.order_by(Company.updated_at.desc()).offset(skip).limit(limit)
    return db.scalars(stmt).all()


@router.get("/companies/{siren}", response_model=CompanyDetail)
def get_company(siren: str, db: Session = Depends(get_db)):
    stmt = (
        select(Company)
        .where(Company.siren == siren)
        .options(selectinload(Company.dirigeants), selectinload(Company.websites))
    )
    company = db.scalar(stmt)
    if company is None:
        raise HTTPException(status_code=404, detail="Company not found")
    return company

@router.delete("/companies", response_model=dict)
def clear_companies(db: Session = Depends(get_db)):
    deleted = db.query(Company).delete()
    db.commit()
    return {"deleted": deleted}