from __future__ import annotations

import pytest
from sqlalchemy import create_engine, select, func
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings
from app.db.base import Base
import app.db.models
from app.db.models import Company, Dirigeant, Website
from app.services.ingestion import ingest_from_insee, enrich_from_rne
from app.services.website_detect import detect_for_company


@pytest.fixture(scope="module")
def engine():
    eng = create_engine(settings.database_url)
    Base.metadata.create_all(eng)
    yield eng
    eng.dispose()


@pytest.fixture
def db(engine) -> Session:
    TestSession = sessionmaker(bind=engine)
    session = TestSession()
    _cleanup(session)
    yield session
    _cleanup(session)
    session.close()


TEST_SIREN = "999999999"


def _cleanup(session: Session) -> None:
    session.query(Company).filter(Company.siren == TEST_SIREN).delete()
    session.commit()


def _insee_etab() -> dict:
    return {
        "siren": TEST_SIREN,
        "uniteLegale": {
            "denominationUniteLegale": "TEST COMPANY",
            "activitePrincipaleUniteLegale": "62.01Z",
            "dateCreationUniteLegale": "2026-01-01",
            "statutDiffusionUniteLegale": "O",
        },
        "adresseEtablissement": {
            "libelleCommuneEtablissement": "PARIS",
            "codePostalEtablissement": "75001",
            "codeCommuneEtablissement": "75101",
        },
    }


def _rne_payload() -> dict:
    return {
        "siren": TEST_SIREN,
        "formality": {
            "siren": TEST_SIREN,
            "typePersonne": "M",
            "formeJuridique": "5710",
            "diffusionCommerciale": True,
            "diffusionINSEE": "O",
            "content": {
                "personneMorale": {
                    "composition": {
                        "pouvoirs": [
                            {
                                "roleEntreprise": "30",
                                "individu": {"descriptionPersonne": {
                                    "nom": "DUPONT", "prenoms": ["Jean"]
                                }},
                            },
                            {
                                "roleEntreprise": "75",
                                "individu": {"descriptionPersonne": {
                                    "nom": "MARTIN", "prenoms": ["Claire"]
                                }},
                            },
                        ]
                    }
                }
            },
        },
    }


class _FakeRneClient:
    def get_company(self, siren: str) -> dict:
        return _rne_payload()

def test_ingest_insee_idempotent(db):
    etabs = [_insee_etab()]
    ingest_from_insee(etabs, db=db)
    ingest_from_insee(etabs, db=db)

    count = db.scalar(select(func.count()).select_from(Company).where(Company.siren == TEST_SIREN))
    assert count == 1, "Réimporter le même SIREN doit donner une seule company"


def test_ingest_insee_same_siren_multiple_etabs(db):
    etabs = [_insee_etab(), _insee_etab()]
    ingest_from_insee(etabs, db=db)

    count = db.scalar(select(func.count()).select_from(Company).where(Company.siren == TEST_SIREN))
    assert count == 1


def test_enrich_rne_idempotent(db):
    ingest_from_insee([_insee_etab()], db=db)
    client = _FakeRneClient()

    enrich_from_rne(TEST_SIREN, client, db=db)
    enrich_from_rne(TEST_SIREN, client, db=db)

    company = db.scalar(select(Company).where(Company.siren == TEST_SIREN))
    dirigeants = db.scalars(select(Dirigeant).where(Dirigeant.company_id == company.id)).all()
    assert len(dirigeants) == 2, "Réenrichir ne doit pas dupliquer les dirigeants"
    assert company.source_rne is True


def test_detect_websites_idempotent(db, monkeypatch):
    ingest_from_insee([_insee_etab()], db=db)
    company = db.scalar(select(Company).where(Company.siren == TEST_SIREN))

    from app.services import website_detect
    from app.services.website_probe import ProbeResult

    def fake_probe_many(candidates):
        return [
            ProbeResult(
                domain=c.domain, pattern=c.pattern, url=c.url,
                dns_resolved=False, error="dns_error",
            )
            for c in candidates
        ]

    monkeypatch.setattr(website_detect, "probe_many", fake_probe_many)

    detect_for_company(company, db)
    n_first = db.scalar(select(func.count()).select_from(Website).where(Website.company_id == company.id))
    detect_for_company(company, db)
    n_second = db.scalar(select(func.count()).select_from(Website).where(Website.company_id == company.id))

    assert n_first == n_second, "Re-détecter ne doit pas accumuler les websites"
    assert n_first > 0


def test_nd_cleanup(db):
    etab = _insee_etab()
    etab["uniteLegale"]["denominationUniteLegale"] = "[ND]"
    etab["adresseEtablissement"]["codePostalEtablissement"] = "[ND]"
    ingest_from_insee([etab], db=db)

    company = db.scalar(select(Company).where(Company.siren == TEST_SIREN))
    assert company.denomination is None, "[ND] doit être nettoyé en None"
    assert company.code_postal is None