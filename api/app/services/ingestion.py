from __future__ import annotations

import logging
from datetime import UTC, datetime

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.db.models import Company, Dirigeant, RawPayload
from app.db.session import SessionLocal
from app.services.normalize import CompanyData, normalize_insee, normalize_rne

logger = logging.getLogger(__name__)


def ingest_from_insee(etablissements: list[dict], db: Session | None = None) -> dict:
    # db=None is supported so this function can be called outside a request context
    own_session = db is None
    db = db or SessionLocal()
    seen: set[str] = set()
    processed = 0
    skipped = 0

    try:
        for etab in etablissements:
            data = normalize_insee(etab)
            if data is None:
                skipped += 1
                continue

            # Multiple établissements can share a siren; only upsert once per siren
            if data.siren in seen:
                continue
            seen.add(data.siren)

            now = datetime.now(UTC)
            values = {
                "siren": data.siren,
                "denomination": data.denomination,
                "code_ape": data.code_ape,
                "date_creation": data.date_creation,
                "commune": data.commune,
                "code_postal": data.code_postal,
                "code_insee_commune": data.code_insee_commune,
                "diffusion_insee": data.diffusion_insee,
                "source_insee": True,
                "insee_synced_at": now,
            }
            stmt = insert(Company).values(**values)
            # On conflict: update INSEE fields but never touch source_rne or noms_de_domaine
            stmt = stmt.on_conflict_do_update(
                index_elements=["siren"],
                set_={
                    "denomination": stmt.excluded.denomination,
                    "code_ape": stmt.excluded.code_ape,
                    "date_creation": stmt.excluded.date_creation,
                    "commune": stmt.excluded.commune,
                    "code_postal": stmt.excluded.code_postal,
                    "code_insee_commune": stmt.excluded.code_insee_commune,
                    "diffusion_insee": stmt.excluded.diffusion_insee,
                    "source_insee": True,
                    "insee_synced_at": stmt.excluded.insee_synced_at,
                    "updated_at": now,
                },
            )
            db.execute(stmt)
            db.add(RawPayload(siren=data.siren, source="insee", payload=etab))
            processed += 1

        db.commit()
    finally:
        if own_session:
            db.close()

    return {"processed": processed, "skipped": skipped}


def _apply_rne(company: Company, data: CompanyData, db: Session) -> None:
    now = datetime.now(UTC)

    if data.denomination and not company.denomination:
        company.denomination = data.denomination
    if data.type_personne:
        company.type_personne = data.type_personne
    if data.forme_juridique:
        company.forme_juridique = data.forme_juridique
    if data.noms_de_domaine:
        company.noms_de_domaine = data.noms_de_domaine
    company.diffusion_insee = data.diffusion_insee
    company.source_rne = True
    company.rne_synced_at = now

    # Replace dirigeants wholesale on each sync
    db.execute(delete(Dirigeant).where(Dirigeant.company_id == company.id))
    for p in data.dirigeants:
        db.add(
            Dirigeant(
                company_id=company.id,
                nom=p.nom,
                prenoms=p.prenoms,
                role=p.role,
                beneficiaire_effectif=p.beneficiaire_effectif,
                diffusion_commerciale=p.diffusion_commerciale,
                synced_at=now,
            )
        )


def enrich_from_rne(siren: str, client, db: Session | None = None) -> bool:
    own_session = db is None
    db = db or SessionLocal()
    try:
        company = db.scalar(select(Company).where(Company.siren == siren))
        if company is None:
            return False

        payload = client.get_company(siren)
        if payload is None:
            # Mark as attempted so we don't retry on every enrichment run
            company.source_rne = True
            company.rne_synced_at = datetime.now(UTC)
            db.commit()
            return False

        db.add(RawPayload(siren=siren, source="rne", payload=payload))
        data = normalize_rne(payload)
        _apply_rne(company, data, db)

        db.commit()
        return True
    finally:
        if own_session:
            db.close()


def enrich_pending_from_rne(client, limit: int = 100, db: Session | None = None) -> dict:
    own_session = db is None
    db = db or SessionLocal()
    enriched = 0
    try:
        sirens = db.scalars(
            select(Company.siren).where(Company.source_rne.is_(False)).limit(limit)
        ).all()
        for siren in sirens:
            try:
                if enrich_from_rne(siren, client, db=db):
                    enriched += 1
            except Exception:
                db.rollback()
                logger.warning("Failed to enrich siren %s", siren, exc_info=True)
        return {"enriched": enriched, "candidates": len(sirens)}
    finally:
        if own_session:
            db.close()
