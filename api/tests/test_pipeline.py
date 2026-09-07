from __future__ import annotations

import pytest
from sqlalchemy import create_engine, select, func
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings
from app.db.base import Base
import app.db.models
from app.db.models import Analysis, Company, Contact, Dirigeant, Website
from app.services.filter import delete_non_prospects
from app.services.ingestion import ingest_from_insee, enrich_from_rne
from app.services.insee import InseeClient
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
_SIREN_SCI = "111111111"
_SIREN_SARL = "222222222"


def _cleanup(session: Session) -> None:
    for siren in (TEST_SIREN, _SIREN_SCI, _SIREN_SARL):
        session.query(Company).filter(Company.siren == siren).delete()
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
    from app.services.website_probe import Candidate, ProbeResult

    fake_candidate = Candidate(url="https://testcompany.fr", domain="testcompany.fr", pattern="searxng")

    def fake_search_searxng(denomination, base_url, commune=None):
        return [fake_candidate]

    def fake_probe_many(candidates):
        return [
            ProbeResult(
                domain=c.domain, pattern=c.pattern, url=c.url,
                dns_resolved=False, error="dns_error",
            )
            for c in candidates
        ]

    monkeypatch.setattr(website_detect, "search_searxng", fake_search_searxng)
    monkeypatch.setattr(website_detect, "probe_many", fake_probe_many)

    detect_for_company(company, db)
    n_first = db.scalar(select(func.count()).select_from(Website).where(Website.company_id == company.id))
    detect_for_company(company, db)
    n_second = db.scalar(select(func.count()).select_from(Website).where(Website.company_id == company.id))

    assert n_first == n_second, "Re-détecter ne doit pas accumuler les websites"
    assert n_first > 0


def _insee_etab_with(siren: str, forme_juridique: str) -> dict:
    etab = _insee_etab()
    etab["siren"] = siren
    etab["uniteLegale"]["categorieJuridiqueUniteLegale"] = forme_juridique
    return etab


def test_filter_excludes_sci_keeps_sarl(db):
    ingest_from_insee(
        [
            _insee_etab_with(_SIREN_SCI, "6540"),   # SCI → doit être supprimée
            _insee_etab_with(_SIREN_SARL, "5499"),  # SARL → doit être conservée
        ],
        db=db,
    )

    result = delete_non_prospects(db)

    sci_count = db.scalar(select(func.count()).select_from(Company).where(Company.siren == _SIREN_SCI))
    sarl_count = db.scalar(select(func.count()).select_from(Company).where(Company.siren == _SIREN_SARL))

    assert sci_count == 0, "SCI (6540) doit être exclue par le filtre"
    assert sarl_count == 1, "SARL (5499) doit être conservée"
    assert result["deleted"] >= 1  # au moins la SCI insérée par ce test
    assert result["dry_run"] is False
    codes_deleted = {r["code"] for r in result["breakdown"]}
    assert "6540" in codes_deleted


def test_filter_dry_run_does_not_delete(db):
    ingest_from_insee([_insee_etab_with(_SIREN_SCI, "6540")], db=db)

    result = delete_non_prospects(db, dry_run=True)

    still_there = db.scalar(select(func.count()).select_from(Company).where(Company.siren == _SIREN_SCI))
    assert still_there == 1, "dry_run ne doit pas supprimer"
    assert result["dry_run"] is True
    assert result["deleted"] == 1  # would-be count


def test_nd_cleanup(db):
    etab = _insee_etab()
    etab["uniteLegale"]["denominationUniteLegale"] = "[ND]"
    etab["adresseEtablissement"]["codePostalEtablissement"] = "[ND]"
    ingest_from_insee([etab], db=db)

    company = db.scalar(select(Company).where(Company.siren == TEST_SIREN))
    assert company.denomination is None, "[ND] doit être nettoyé en None"
    assert company.code_postal is None


# ── Tests unitaires de _build_query (fonction pure, pas de réseau/DB) ─────────

_client = InseeClient(api_key="dummy")


def test_build_query_default_targets_societes():
    """Par défaut, la requête cible [5000 TO 6999] (sociétés commerciales + civiles/GIE)."""
    q = _client._build_query()
    assert "categorieJuridiqueUniteLegale:[5000 TO 6999]" in q


def test_build_query_none_none_omits_category_filter():
    """Passer categorie_min=None et categorie_max=None supprime le filtre catégorie."""
    q = _client._build_query(categorie_min=None, categorie_max=None)
    assert "categorieJuridiqueUniteLegale" not in q


def test_build_query_custom_range():
    """Un range personnalisé (ex : inclure les EI) est bien encodé."""
    q = _client._build_query(categorie_min=1000, categorie_max=6999)
    assert "categorieJuridiqueUniteLegale:[1000 TO 6999]" in q


def test_build_query_at_date_clause():
    """at_date génère une clause date exacte, pas une plage."""
    q = _client._build_query(at_date="2024-03-15")
    assert "dateCreationUniteLegale:2024-03-15" in q
    assert " TO " not in q.split("categorieJuridiqueUniteLegale")[0]


def test_build_query_rolling_window_clause():
    """Sans at_date, la clause de date est une plage [start TO today]."""
    q = _client._build_query(days=30)
    assert "dateCreationUniteLegale:[" in q
    assert " TO " in q


def test_build_query_active_only():
    """active_only=True ajoute le filtre etatAdministratifUniteLegale:A."""
    q_with = _client._build_query(active_only=True)
    q_without = _client._build_query(active_only=False)
    assert "etatAdministratifUniteLegale:A" in q_with
    assert "etatAdministratifUniteLegale:A" not in q_without


def test_build_query_always_includes_siege():
    """etablissementSiege:true est toujours présent (un siège par SIREN)."""
    q = _client._build_query()
    assert "etablissementSiege:true" in q


# ── Tests du scoring différencié par source ────────────────────────────────────

def _probe_ok(domain: str) -> "ProbeResult":
    from app.services.website_probe import ProbeResult
    return ProbeResult(
        domain=domain, pattern="x", url=f"https://{domain}",
        dns_resolved=True, http_status=200,
        final_url=f"https://{domain}", is_https=True,
    )


def test_score_detection_ranking_rne_osm_searxng():
    """RNE (95+5) > OSM (75+5) > SearXNG (60+5) pour un domaine HTTP 200 HTTPS."""
    from app.services.website_probe import score_detection

    rne_score = score_detection(_probe_ok("rne.fr"), "rne")
    osm_score = score_detection(_probe_ok("osm.fr"), "osm")
    searxng_score = score_detection(_probe_ok("searxng.fr"), "searxng")

    assert rne_score == 100, f"RNE HTTP 200 HTTPS attendu 100, obtenu {rne_score}"
    assert osm_score == 80, f"OSM HTTP 200 HTTPS attendu 80, obtenu {osm_score}"
    assert searxng_score == 65, f"SearXNG HTTP 200 HTTPS attendu 65, obtenu {searxng_score}"
    assert rne_score > osm_score > searxng_score


def test_detect_rne_vs_osm_confidence(db, monkeypatch):
    """detect_for_company lit la source depuis noms_de_domaine et l'applique au scoring."""
    from app.services import website_detect
    from app.services.website_probe import Candidate, ProbeResult

    ingest_from_insee([_insee_etab()], db=db)
    company = db.scalar(select(Company).where(Company.siren == TEST_SIREN))
    company.noms_de_domaine = [
        {"domain": "rne-example.fr", "source": "rne"},
        {"domain": "osm-example.fr", "source": "osm"},
    ]
    db.commit()
    db.refresh(company)

    def fake_probe_many(candidates):
        return [
            ProbeResult(
                domain=c.domain, pattern=c.pattern, url=c.url,
                dns_resolved=True, http_status=200,
                final_url=f"https://{c.domain}", is_https=True,
            )
            for c in candidates
        ]

    monkeypatch.setattr(website_detect, "probe_many", fake_probe_many)
    detect_for_company(company, db)

    websites = db.scalars(select(Website).where(Website.company_id == company.id)).all()
    by_source = {w.source: w for w in websites}

    assert "rne" in by_source and "osm" in by_source
    assert by_source["rne"].confidence == 100  # 95 + 5 HTTPS
    assert by_source["osm"].confidence == 80   # 75 + 5 HTTPS
    assert by_source["rne"].confidence > by_source["osm"].confidence


# ── Tests enrich_osm_for_company ──────────────────────────────────────────────

_POI_WITH_CONTACTS = {
    "tags": {
        "name": "Test Company",
        "website": "https://testcompany.fr",
        "phone": "+33123456789",
        "email": "contact@testcompany.fr",
    }
}


def test_enrich_osm_writes_domain_and_contacts(db, monkeypatch):
    """enrich_osm_for_company écrit le domaine et les contacts depuis un POI OSM matchant."""
    ingest_from_insee([_insee_etab()], db=db)
    company = db.scalar(select(Company).where(Company.siren == TEST_SIREN))
    company.code_insee_commune = "75101"
    db.commit()

    from app.services import osm as osm_module
    monkeypatch.setattr(osm_module, "_INTER_QUERY_DELAY", 0)
    monkeypatch.setattr(osm_module, "_fetch_pois_extended", lambda _: [_POI_WITH_CONTACTS])

    from app.services.osm import enrich_osm_for_company
    result = enrich_osm_for_company(TEST_SIREN, db)

    db.refresh(company)
    assert result["ok"] is True
    assert result["domain"] == "testcompany.fr"
    assert result["contacts"] == 2  # phone + email

    domains = [e["domain"] for e in company.noms_de_domaine]
    assert "testcompany.fr" in domains
    assert all(isinstance(e, dict) for e in company.noms_de_domaine)

    contacts = db.scalars(select(Contact).where(Contact.company_id == company.id)).all()
    by_type = {c.type: c for c in contacts}
    assert "email" in by_type and "phone" in by_type
    assert by_type["email"].source == "osm"
    assert by_type["email"].value == "contact@testcompany.fr"
    assert by_type["phone"].value == "+33123456789"
    assert by_type["email"].nature == "generique"   # contact@ est un préfixe générique
    assert by_type["phone"].nature == "generique"   # téléphones toujours génériques


# ── Tests unitaires de crawl_site (aucun réseau) ──────────────────────────────

from bs4 import BeautifulSoup as _BS


def _make_page(url: str, html: str) -> dict:
    soup = _BS(html, "lxml")
    return {
        "html": html,
        "text": soup.get_text(separator=" ", strip=True),
        "soup": soup,
        "final_url": url,
        "headers": {},
        "status": 200,
    }


_CRAWL_HOME = "https://example.fr"

# Text ≥ 200 chars with no ownership signals for "HOTEL DU TEST" / 74000 / ANNECY
_FILLER_200 = (
    "Bienvenue sur notre site professionnel. Nous proposons une large gamme de "
    "solutions adaptées à votre secteur d'activité depuis de nombreuses années. "
    "Notre équipe qualifiée est à votre disposition pour répondre à vos questions."
)


def test_crawl_site_basic_links(monkeypatch):
    """crawl_site collecte les liens internes et externes depuis la home."""
    from app.services import page_reader

    home_html = """
    <html><body>
      <a href="/about">About</a>
      <a href="/contact">Contact</a>
      <a href="https://partner.com/foo">Partner</a>
      <a href="mailto:info@example.fr">Mail</a>
    </body></html>
    """
    sub_html = "<html><body>Page</body></html>"

    def fake_fetch(url, timeout=8.0):
        if url == _CRAWL_HOME:
            return _make_page(url, home_html)
        return _make_page(url, sub_html)

    monkeypatch.setattr(page_reader, "fetch_page", fake_fetch)

    result = page_reader.crawl_site(_CRAWL_HOME)

    assert f"{_CRAWL_HOME}/about" in result["internal_links"]
    assert f"{_CRAWL_HOME}/contact" in result["internal_links"]
    assert "https://partner.com/foo" in result["external_links"]
    assert not any("mailto" in u for u in result["internal_links"] + result["external_links"])


def test_crawl_site_has_legal_page(monkeypatch):
    """has_legal_page est True quand un lien mentions légales est trouvé."""
    from app.services import page_reader

    home_html = """
    <html><body>
      <a href="/mentions-legales">Mentions légales</a>
    </body></html>
    """

    def fake_fetch(url, timeout=8.0):
        return _make_page(url, home_html if url == _CRAWL_HOME else "<html><body>ML</body></html>")

    monkeypatch.setattr(page_reader, "fetch_page", fake_fetch)

    result = page_reader.crawl_site(_CRAWL_HOME)

    assert result["has_legal_page"] is True


def test_crawl_site_has_contact_info_email(monkeypatch):
    """has_contact_info est True quand un email est trouvé sur la home."""
    from app.services import page_reader

    home_html = """
    <html><body>
      <a href="mailto:contact@example.fr">contact@example.fr</a>
    </body></html>
    """
    monkeypatch.setattr(page_reader, "fetch_page", lambda url, timeout=8.0: _make_page(url, home_html))

    result = page_reader.crawl_site(_CRAWL_HOME)

    assert result["has_contact_info"] is True


def test_crawl_site_provider_hint(monkeypatch):
    """provider_hint est rempli quand le footer contient un lien 'réalisé par'."""
    from app.services import page_reader

    home_html = """
    <html><body>
      <main><p>Contenu</p></main>
      <footer>
        <a href="https://agence-web.fr">Réalisé par Agence Web</a>
      </footer>
    </body></html>
    """
    monkeypatch.setattr(page_reader, "fetch_page", lambda url, timeout=8.0: _make_page(url, home_html))

    result = page_reader.crawl_site(_CRAWL_HOME)

    assert result["provider_hint"] is not None
    assert "Agence Web" in result["provider_hint"]


def test_crawl_site_sub_page_failure_is_graceful(monkeypatch):
    """Une erreur réseau sur une sous-page ne plante pas crawl_site."""
    from app.services import page_reader

    home_html = """
    <html><body>
      <a href="/page-ok">OK</a>
      <a href="/page-fail">Fail</a>
    </body></html>
    """

    def fake_fetch(url, timeout=8.0):
        if url == _CRAWL_HOME:
            return _make_page(url, home_html)
        if url.endswith("/page-ok"):
            return _make_page(url, "<html><body>OK</body></html>")
        raise ConnectionError("network error")

    monkeypatch.setattr(page_reader, "fetch_page", fake_fetch)

    result = page_reader.crawl_site(_CRAWL_HOME)

    assert isinstance(result["internal_links"], list)
    assert isinstance(result["has_legal_page"], bool)


def test_crawl_site_home_failure_returns_empty(monkeypatch):
    """Si la home est inaccessible, fetch_failed=True et les listes sont vides."""
    from app.services import page_reader

    def fake_fetch(url, timeout=8.0):
        raise ConnectionError("down")

    monkeypatch.setattr(page_reader, "fetch_page", fake_fetch)

    result = page_reader.crawl_site(_CRAWL_HOME)

    assert result["fetch_failed"] is True
    assert result["internal_links"] == []
    assert result["external_links"] == []
    assert result["has_legal_page"] is False
    assert result["has_contact_info"] is False
    assert result["provider_hint"] is None
    assert result["pages_text"] == ""
    assert result["home_page"] is None


def test_crawl_site_returns_pages_text(monkeypatch):
    """pages_text agrège le texte de toutes les pages visitées."""
    from app.services import page_reader

    home_html = "<html><body><a href='/sub'>Sub</a> Texte accueil</body></html>"
    sub_html = "<html><body>Texte sous-page</body></html>"

    def fake_fetch(url, timeout=8.0):
        return _make_page(url, home_html if url == _CRAWL_HOME else sub_html)

    monkeypatch.setattr(page_reader, "fetch_page", fake_fetch)

    result = page_reader.crawl_site(_CRAWL_HOME)

    assert "Texte accueil" in result["pages_text"]
    assert "Texte sous-page" in result["pages_text"]
    assert result["home_page"] is not None
    assert result["fetch_failed"] is False


def test_crawl_site_useful_links_prioritized(monkeypatch):
    """Avec max_pages=3, les pages mentions-légales/contact sont visitées avant les génériques."""
    from app.services import page_reader

    links = ["/mentions-legales", "/contact"] + [f"/page-{i}" for i in range(5)]
    a_tags = "".join(f'<a href="{l}">Link</a>' for l in links)
    home_html = f"<html><body>{a_tags}</body></html>"

    visited: list[str] = []

    def fake_fetch(url, timeout=8.0):
        visited.append(url)
        return _make_page(url, home_html if url == _CRAWL_HOME else "<html><body>Sub</body></html>")

    monkeypatch.setattr(page_reader, "fetch_page", fake_fetch)

    page_reader.crawl_site(_CRAWL_HOME, max_pages=3)

    assert visited[0] == _CRAWL_HOME
    assert f"{_CRAWL_HOME}/mentions-legales" in visited[1:3]
    assert f"{_CRAWL_HOME}/contact" in visited[1:3]
    for i in range(5):
        assert f"{_CRAWL_HOME}/page-{i}" not in visited


def test_enrich_osm_idempotent(db, monkeypatch):
    """Appeler enrich_osm_for_company deux fois ne duplique ni domaine ni contacts."""
    ingest_from_insee([_insee_etab()], db=db)
    company = db.scalar(select(Company).where(Company.siren == TEST_SIREN))
    company.code_insee_commune = "75101"
    db.commit()

    from app.services import osm as osm_module
    monkeypatch.setattr(osm_module, "_INTER_QUERY_DELAY", 0)
    monkeypatch.setattr(osm_module, "_fetch_pois_extended", lambda _: [_POI_WITH_CONTACTS])

    from app.services.osm import enrich_osm_for_company
    enrich_osm_for_company(TEST_SIREN, db)
    enrich_osm_for_company(TEST_SIREN, db)

    db.refresh(company)
    osm_domains = [e for e in company.noms_de_domaine if e["source"] == "osm"]
    assert len(osm_domains) == 1, "Le domaine OSM ne doit pas être dupliqué"

    contact_count = db.scalar(
        select(func.count()).select_from(Contact).where(Contact.company_id == company.id)
    )
    assert contact_count == 2, "phone + email, pas de doublons (upsert ON CONFLICT DO NOTHING)"


# ── Tests unitaires scoring ownership lot B ────────────────────────────────────

def _make_company(siren="123456789", denomination="TEST SARL", code_postal="75001",
                  commune="PARIS", dirigeants=None) -> Company:
    c = Company(
        siren=siren,
        denomination=denomination,
        code_postal=code_postal,
        commune=commune,
        diffusion_insee=True,
        noms_de_domaine=[],
        source_insee=False,
        source_rne=False,
    )
    c.dirigeants = dirigeants or []
    return c


def test_scoring_siren_always_confirmed():
    """SIREN trouvé → confirmed, peu importe les autres signaux."""
    from app.services.page_reader import _extract_signals, _score_ownership
    company = _make_company()
    signals = _extract_signals("SIREN 123 456 789 présent dans le texte", company)
    verdict, score = _score_ownership(signals)
    assert verdict == "confirmed"
    assert signals.get("siren") is True


def test_scoring_no_siren_probable():
    """Sans SIREN, denomination + code_postal → probable (jamais confirmed)."""
    from app.services.page_reader import _extract_signals, _score_ownership
    company = _make_company()
    text = "TEST SARL, basée au 75001 Paris"
    signals = _extract_signals(text, company)
    verdict, score = _score_ownership(signals)
    assert verdict == "probable"
    assert score >= 2.0
    assert "siren" not in signals


def test_scoring_no_siren_no_signals_rejected():
    """Sans SIREN ni signaux suffisants → rejected."""
    from app.services.page_reader import _extract_signals, _score_ownership
    company = _make_company()
    signals = _extract_signals("bienvenue sur notre site web", company)
    verdict, score = _score_ownership(signals)
    assert verdict == "rejected"


def test_scoring_denomination_approx():
    """denomination_approx : dénomination sans abréviation juridique matchée dans le texte."""
    from app.services.page_reader import _extract_signals
    company = _make_company(denomination="HOTEL DU COLOMBIER SARL")
    signals = _extract_signals("Bienvenue à l'Hôtel du Colombier, votre hôtel de charme", company)
    # "HOTEL" (4 chars), "COLOMBIER" (9 chars) présents → approx match
    assert signals.get("denomination_approx") is True or signals.get("denomination") is True


def test_scoring_dirigeant_signal():
    """Nom du dirigeant présent dans le texte → signal dirigeant."""
    from app.services.page_reader import _extract_signals
    d = Dirigeant(nom="DUPONT", prenoms=["Jean"], role="gérant", diffusion_commerciale=True)
    company = _make_company(dirigeants=[d])
    signals = _extract_signals("Notre gérant Jean Dupont vous accueille.", company)
    assert signals.get("dirigeant") is True


def test_scoring_dirigeant_too_short_ignored():
    """Nom dirigeant < 4 chars ignoré pour éviter les faux positifs."""
    from app.services.page_reader import _extract_signals
    d = Dirigeant(nom="LI", prenoms=[], role="gérant", diffusion_commerciale=True)
    company = _make_company(dirigeants=[d])
    signals = _extract_signals("texte sans rapport", company)
    assert "dirigeant" not in signals


def test_check_ownership_verdict_in_result():
    """check_ownership retourne verdict + score + signals (signature text, company)."""
    from app.services import page_reader
    company = _make_company()
    # Short text → indeterminate; longer text with no signals → rejected
    long_no_signal_text = _FILLER_200
    result = page_reader.check_ownership(long_no_signal_text, company)
    assert "verdict" in result
    assert "score" in result
    assert "signals" in result
    assert result["verdict"] in ("confirmed", "probable", "rejected", "indeterminate")


# ── Tests signal domain_name (nouveau) ────────────────────────────────────────

def test_domain_name_signal_detected():
    """Les mots significatifs de la dénomination présents dans le domaine → domain_name=True."""
    from app.services.page_reader import _extract_signals
    company = _make_company(denomination="HOTEL DU COLOMBIER SARL")
    # domain_root "hotelducolombier" contient "hotel" et "colombier"
    signals = _extract_signals(_FILLER_200, company, domain="hotelducolombier.fr")
    assert signals.get("domain_name") is True


def test_domain_name_signal_absent_when_no_match():
    """Domaine sans rapport avec la dénomination → pas de signal domain_name."""
    from app.services.page_reader import _extract_signals
    company = _make_company(denomination="HOTEL DU COLOMBIER SARL")
    signals = _extract_signals(_FILLER_200, company, domain="plomberie-dupont.fr")
    assert signals.get("domain_name") is None


def test_domain_plus_commune_not_probable_without_content_signal():
    """domain_name (1.5) + commune (0.5) = 2.0 mais aucun signal de contenu → rejected.

    SearXNG ayant trouvé le domaine par similarité de nom, domain_name est quasi-tautologique.
    Un faisceau domain+commune ne suffit pas à "probable" : il faut au moins un signal de contenu
    (denomination, code_postal, dirigeant) prouvant que l'on A LU quelque chose de cohérent.
    """
    from app.services.page_reader import _extract_signals, _score_ownership
    company = _make_company(denomination="HOTEL DU COLOMBIER SARL", commune="COLOMBIER")
    # Text has commune "COLOMBIER" but no denomination/CP/dirigeant signal
    text = _FILLER_200 + " Colombier est une belle commune."
    signals = _extract_signals(text, company, domain="hotelducolombier.fr")
    assert signals.get("domain_name") is True
    assert signals.get("commune") is True
    assert not signals.get("denomination") and not signals.get("denomination_approx")
    assert not signals.get("code_postal") and not signals.get("dirigeant")
    verdict, score = _score_ownership(signals)
    assert verdict == "rejected", (
        f"domain_name+commune seuls ne doivent pas valider 'probable', obtenu '{verdict}'"
    )


def test_domain_plus_code_postal_is_probable():
    """domain_name (1.5) + code_postal (1.0) = 2.5 avec signal fort de contenu → probable."""
    from app.services.page_reader import _extract_signals, _score_ownership
    company = _make_company(denomination="HOTEL DU COLOMBIER SARL", code_postal="35000")
    text = _FILLER_200 + " Adresse : 35000 Rennes."
    signals = _extract_signals(text, company, domain="hotelducolombier.fr")
    assert signals.get("domain_name") is True
    assert signals.get("code_postal") is True
    verdict, score = _score_ownership(signals)
    assert verdict == "probable"
    assert score >= 2.0


def test_domain_plus_denomination_approx_is_probable():
    """domain_name + denomination_approx (signal de contenu fort) → probable."""
    from app.services.page_reader import _extract_signals, _score_ownership
    company = _make_company(denomination="HOTEL DU COLOMBIER SARL")
    text = _FILLER_200 + " L'Hôtel du Colombier vous accueille chaleureusement."
    signals = _extract_signals(text, company, domain="hotelducolombier.fr")
    assert signals.get("domain_name") is True
    assert signals.get("denomination_approx") is True or signals.get("denomination") is True
    verdict, _ = _score_ownership(signals)
    assert verdict == "probable"


# ── Tests analyze_company : déselection + contacts ────────────────────────────

_ANALYZE_SIREN = "888888888"


def _cleanup_analyze(session: Session) -> None:
    session.query(Company).filter(Company.siren == _ANALYZE_SIREN).delete()
    session.commit()


def _make_db_company_with_website(db: Session, domain: str = "test.fr", osm_domain: str | None = None) -> tuple[Company, Website]:
    from app.services.ingestion import ingest_from_insee
    etab = {
        "siren": _ANALYZE_SIREN,
        "uniteLegale": {
            "denominationUniteLegale": "HOTEL DU TEST",
            "activitePrincipaleUniteLegale": "55.10Z",
            "dateCreationUniteLegale": "2020-01-01",
            "statutDiffusionUniteLegale": "O",
        },
        "adresseEtablissement": {
            "libelleCommuneEtablissement": "ANNECY",
            "codePostalEtablissement": "74000",
            "codeCommuneEtablissement": "74010",
        },
    }
    ingest_from_insee([etab], db=db)
    company = db.scalar(select(Company).where(Company.siren == _ANALYZE_SIREN))

    if osm_domain:
        company.noms_de_domaine = [{"domain": osm_domain, "source": "osm"}]
        db.commit()

    w = Website(
        company_id=company.id,
        url=f"https://{domain}",
        domain=domain,
        pattern="rne",
        source="rne",
        dns_resolved=True,
        http_status=200,
        final_url=f"https://{domain}",
        is_https=True,
        confidence=100,
        is_selected=True,
    )
    db.add(w)
    db.commit()
    db.refresh(company)
    return company, w


def _make_crawl_result(
    html: str,
    url: str = "https://test.fr",
    fetch_failed: bool = False,
    contacts: dict | None = None,
    internal_links: list | None = None,
    has_legal_page: bool = False,
) -> dict:
    """Build a fake crawl_site return dict for analyze tests."""
    page = _make_page(url, html)
    resolved_contacts = contacts or {"emails": [], "phones": []}
    return {
        "internal_links": internal_links or [],
        "external_links": [],
        "has_legal_page": has_legal_page,
        "has_contact_info": bool(resolved_contacts.get("emails") or resolved_contacts.get("phones")),
        "provider_hint": None,
        "pages_text": "" if fetch_failed else page["text"],
        "home_page": None if fetch_failed else page,
        "fetch_failed": fetch_failed,
        "contacts": resolved_contacts,
    }


def test_analyze_rejected_deselects_website(db, monkeypatch):
    """verdict=rejected → website.is_selected passe à False."""
    _cleanup_analyze(db)
    company, website = _make_db_company_with_website(db)

    from app.services import analyze as analyze_module

    # Crawl retourne du contenu lisible mais sans aucun signal d'ownership
    crawl_mock = _make_crawl_result(
        f"<html><body>{_FILLER_200}</body></html>",
        url="https://test.fr",
    )
    monkeypatch.setattr(analyze_module, "crawl_site", lambda url, **kw: crawl_mock)
    monkeypatch.setattr(analyze_module, "detect_tech", lambda page: [])
    monkeypatch.setattr(analyze_module, "get_first_seen", lambda domain: None)
    monkeypatch.setattr(analyze_module, "run_lighthouse", lambda url: None)

    from sqlalchemy.orm import selectinload
    company = db.scalar(
        select(Company).where(Company.siren == _ANALYZE_SIREN)
        .options(selectinload(Company.websites), selectinload(Company.dirigeants))
    )

    outcome = analyze_module.analyze_company(company, db)

    db.refresh(website)
    assert outcome == "not_owned"
    assert website.is_selected is False
    _cleanup_analyze(db)


def test_analyze_sitemap_always_stored(db, monkeypatch):
    """site_map (internal_links, has_legal_page…) est stocké même quand verdict=rejected."""
    _cleanup_analyze(db)
    company, website = _make_db_company_with_website(db)

    from app.services import analyze as analyze_module

    crawl_mock = _make_crawl_result(
        f"<html><body>{_FILLER_200}</body></html>",
        url="https://test.fr",
        internal_links=["https://test.fr/about", "https://test.fr/contact"],
        has_legal_page=True,
    )
    monkeypatch.setattr(analyze_module, "crawl_site", lambda url, **kw: crawl_mock)
    monkeypatch.setattr(analyze_module, "detect_tech", lambda page: [])
    monkeypatch.setattr(analyze_module, "get_first_seen", lambda domain: None)
    monkeypatch.setattr(analyze_module, "run_lighthouse", lambda url: None)

    from sqlalchemy.orm import selectinload
    company = db.scalar(
        select(Company).where(Company.siren == _ANALYZE_SIREN)
        .options(selectinload(Company.websites), selectinload(Company.dirigeants))
    )

    outcome = analyze_module.analyze_company(company, db)
    assert outcome == "not_owned"

    analysis = db.scalar(select(Analysis).where(Analysis.company_id == company.id))
    assert analysis is not None, "L'analyse doit être créée même sur rejected"
    assert "https://test.fr/about" in analysis.internal_links
    assert analysis.has_legal_page is True
    assert analysis.ownership_signals.get("verdict") == "rejected"
    _cleanup_analyze(db)


def test_analyze_indeterminate_does_not_deselect(db, monkeypatch):
    """Contenu trop court → verdict indeterminate → is_selected reste True."""
    _cleanup_analyze(db)
    company, website = _make_db_company_with_website(db)

    from app.services import analyze as analyze_module

    # Texte très court (< 200 chars) → indeterminate
    crawl_mock = _make_crawl_result(
        "<html><body>Bonjour</body></html>",
        url="https://test.fr",
    )
    monkeypatch.setattr(analyze_module, "crawl_site", lambda url, **kw: crawl_mock)
    monkeypatch.setattr(analyze_module, "detect_tech", lambda page: [])
    monkeypatch.setattr(analyze_module, "get_first_seen", lambda domain: None)
    monkeypatch.setattr(analyze_module, "run_lighthouse", lambda url: None)

    from sqlalchemy.orm import selectinload
    company = db.scalar(
        select(Company).where(Company.siren == _ANALYZE_SIREN)
        .options(selectinload(Company.websites), selectinload(Company.dirigeants))
    )

    outcome = analyze_module.analyze_company(company, db)

    db.refresh(website)
    assert outcome == "indeterminate"
    assert website.is_selected is True, "Un indéterminé ne doit jamais déselectionner le site"

    analysis = db.scalar(select(Analysis).where(Analysis.company_id == company.id))
    assert analysis is not None
    assert analysis.ownership_signals.get("verdict") == "indeterminate"
    _cleanup_analyze(db)


def test_analyze_fetch_failed_is_indeterminate(db, monkeypatch):
    """Échec réseau total → verdict indeterminate, is_selected inchangé."""
    _cleanup_analyze(db)
    company, website = _make_db_company_with_website(db)

    from app.services import analyze as analyze_module

    crawl_mock = _make_crawl_result("", fetch_failed=True)
    monkeypatch.setattr(analyze_module, "crawl_site", lambda url, **kw: crawl_mock)

    from sqlalchemy.orm import selectinload
    company = db.scalar(
        select(Company).where(Company.siren == _ANALYZE_SIREN)
        .options(selectinload(Company.websites), selectinload(Company.dirigeants))
    )

    outcome = analyze_module.analyze_company(company, db)

    db.refresh(website)
    assert outcome == "indeterminate"
    assert website.is_selected is True

    analysis = db.scalar(select(Analysis).where(Analysis.company_id == company.id))
    assert analysis.ownership_signals.get("reason") == "fetch_failed"
    _cleanup_analyze(db)


def test_analyze_parking_stores_analysis(db, monkeypatch):
    """Page parking → analysis stockée avec verdict=rejected, is_selected=False."""
    _cleanup_analyze(db)
    company, website = _make_db_company_with_website(db)

    from app.services import analyze as analyze_module

    parking_html = "<html><body>Ce domaine est à vendre. Achetez ce domaine maintenant.</body></html>"
    crawl_mock = _make_crawl_result(parking_html, url="https://test.fr")
    monkeypatch.setattr(analyze_module, "crawl_site", lambda url, **kw: crawl_mock)
    monkeypatch.setattr(analyze_module, "detect_tech", lambda page: [])
    monkeypatch.setattr(analyze_module, "get_first_seen", lambda domain: None)
    monkeypatch.setattr(analyze_module, "run_lighthouse", lambda url: None)

    from sqlalchemy.orm import selectinload
    company = db.scalar(
        select(Company).where(Company.siren == _ANALYZE_SIREN)
        .options(selectinload(Company.websites), selectinload(Company.dirigeants))
    )

    outcome = analyze_module.analyze_company(company, db)

    db.refresh(website)
    assert outcome == "not_owned"
    assert website.is_selected is False

    analysis = db.scalar(select(Analysis).where(Analysis.company_id == company.id))
    assert analysis is not None, "L'analyse doit être créée même pour une parking page"
    assert analysis.ownership_signals.get("reason") == "parking_page"
    _cleanup_analyze(db)


def test_analyze_page_contacts_written_to_contacts_table(db, monkeypatch):
    """Contacts trouvés sur le site → écrits dans contacts avec source='page'."""
    _cleanup_analyze(db)
    company, website = _make_db_company_with_website(db, domain="hoteldutest.fr")

    from app.services import analyze as analyze_module

    # SIREN dans le texte → confirmed (texte ≥ 200 chars pour dépasser le seuil indeterminate)
    siren_html = (
        f"<html><body>SIREN 888 888 888 — Hôtel du Test, Annecy 74000. "
        f"{_FILLER_200}"
        f"<a href='mailto:contact@hoteldutest.fr'>contact@hoteldutest.fr</a></body></html>"
    )

    crawl_mock = _make_crawl_result(
        siren_html,
        url="https://hoteldutest.fr",
        contacts={"emails": ["contact@hoteldutest.fr"], "phones": []},
    )
    monkeypatch.setattr(analyze_module, "crawl_site", lambda url, **kw: crawl_mock)
    monkeypatch.setattr(analyze_module, "detect_tech", lambda page: [])
    monkeypatch.setattr(analyze_module, "get_first_seen", lambda domain: None)
    monkeypatch.setattr(analyze_module, "get_sitemap_dates", lambda domain, **kw: None)
    monkeypatch.setattr(analyze_module, "run_lighthouse", lambda url: None)

    from sqlalchemy.orm import selectinload
    company = db.scalar(
        select(Company).where(Company.siren == _ANALYZE_SIREN)
        .options(selectinload(Company.websites), selectinload(Company.dirigeants))
    )

    analyze_module.analyze_company(company, db)

    page_contacts = db.scalars(
        select(Contact).where(Contact.company_id == company.id, Contact.source == "page")
    ).all()
    assert len(page_contacts) >= 1
    assert any(c.value == "contact@hoteldutest.fr" for c in page_contacts)
    _cleanup_analyze(db)


def test_analyze_osm_contacts_marked_suspicious_on_domain_mismatch(db, monkeypatch):
    """Contacts OSM dont le domaine ≠ site confirmé → suspicious=True."""
    _cleanup_analyze(db)
    # OSM a trouvé "agencetest.com", mais le vrai site est "hoteldutest.fr"
    company, website = _make_db_company_with_website(
        db, domain="hoteldutest.fr", osm_domain="agencetest.com"
    )

    # Insérer un contact OSM préexistant
    osm_contact = Contact(
        company_id=company.id,
        type="email",
        value="contact@agencetest.com",
        source="osm",
        suspicious=None,
    )
    db.add(osm_contact)
    db.commit()

    from app.services import analyze as analyze_module

    # Texte ≥ 200 chars avec SIREN → confirmed, sinon indeterminate et suspicious non mis à jour
    siren_html = (
        f"<html><body>SIREN 888 888 888 — Hôtel du Test Annecy 74000. "
        f"{_FILLER_200}</body></html>"
    )
    crawl_mock = _make_crawl_result(siren_html, url="https://hoteldutest.fr")
    monkeypatch.setattr(analyze_module, "crawl_site", lambda url, **kw: crawl_mock)
    monkeypatch.setattr(analyze_module, "detect_tech", lambda page: [])
    monkeypatch.setattr(analyze_module, "get_first_seen", lambda domain: None)
    monkeypatch.setattr(analyze_module, "get_sitemap_dates", lambda domain, **kw: None)
    monkeypatch.setattr(analyze_module, "run_lighthouse", lambda url: None)

    from sqlalchemy.orm import selectinload
    company = db.scalar(
        select(Company).where(Company.siren == _ANALYZE_SIREN)
        .options(selectinload(Company.websites), selectinload(Company.dirigeants))
    )

    analyze_module.analyze_company(company, db)

    db.refresh(osm_contact)
    assert osm_contact.suspicious is True
    _cleanup_analyze(db)


def test_analyze_osm_contacts_not_suspicious_when_domain_matches(db, monkeypatch):
    """Contacts OSM dont le domaine = site confirmé → suspicious=False."""
    _cleanup_analyze(db)
    company, website = _make_db_company_with_website(
        db, domain="hoteldutest.fr", osm_domain="hoteldutest.fr"
    )

    osm_contact = Contact(
        company_id=company.id,
        type="email",
        value="contact@hoteldutest.fr",
        source="osm",
        suspicious=None,
    )
    db.add(osm_contact)
    db.commit()

    from app.services import analyze as analyze_module

    siren_html = (
        f"<html><body>SIREN 888 888 888 — Hôtel du Test Annecy 74000. "
        f"{_FILLER_200}</body></html>"
    )
    crawl_mock = _make_crawl_result(siren_html, url="https://hoteldutest.fr")
    monkeypatch.setattr(analyze_module, "crawl_site", lambda url, **kw: crawl_mock)
    monkeypatch.setattr(analyze_module, "detect_tech", lambda page: [])
    monkeypatch.setattr(analyze_module, "get_first_seen", lambda domain: None)
    monkeypatch.setattr(analyze_module, "get_sitemap_dates", lambda domain, **kw: None)
    monkeypatch.setattr(analyze_module, "run_lighthouse", lambda url: None)

    from sqlalchemy.orm import selectinload
    company = db.scalar(
        select(Company).where(Company.siren == _ANALYZE_SIREN)
        .options(selectinload(Company.websites), selectinload(Company.dirigeants))
    )

    analyze_module.analyze_company(company, db)

    db.refresh(osm_contact)
    assert osm_contact.suspicious is False
    _cleanup_analyze(db)


# ── Tests réentrance analyze_pending ──────────────────────────────────────────

_REENTRY_SIREN = "777777777"


def _cleanup_reentry(session: Session) -> None:
    session.query(Company).filter(Company.siren == _REENTRY_SIREN).delete()
    session.commit()


def _make_db_company_with_analysis(
    db: Session,
    verdict: str,
    is_selected: bool = True,
) -> tuple[Company, Website]:
    """Insert a company+website+analysis with the given ownership verdict."""
    etab = {
        "siren": _REENTRY_SIREN,
        "uniteLegale": {
            "denominationUniteLegale": "REENTRY TEST",
            "activitePrincipaleUniteLegale": "62.01Z",
            "dateCreationUniteLegale": "2020-01-01",
            "statutDiffusionUniteLegale": "O",
        },
        "adresseEtablissement": {
            "libelleCommuneEtablissement": "LYON",
            "codePostalEtablissement": "69000",
            "codeCommuneEtablissement": "69123",
        },
    }
    ingest_from_insee([etab], db=db)
    company = db.scalar(select(Company).where(Company.siren == _REENTRY_SIREN))

    w = Website(
        company_id=company.id,
        url="https://reentry.fr",
        domain="reentry.fr",
        pattern="rne",
        source="rne",
        dns_resolved=True,
        http_status=200,
        final_url="https://reentry.fr",
        is_https=True,
        confidence=100,
        is_selected=is_selected,
    )
    db.add(w)
    db.flush()

    analysis = Analysis(
        company_id=company.id,
        website_id=w.id,
        ownership_confirmed=(verdict == "confirmed"),
        ownership_signals={"verdict": verdict, "score": 0.0},
        emails=[],
        phones=[],
        tech_stack=[],
        internal_links=[],
        external_links=[],
        has_legal_page=False,
        has_contact_info=False,
    )
    db.add(analysis)
    db.commit()
    db.refresh(company)
    return company, w


def test_analyze_pending_skips_existing_non_indeterminate(db, monkeypatch):
    """analyze_pending sans force saute les entreprises avec une analyse non-indeterminate."""
    _cleanup_reentry(db)
    _make_db_company_with_analysis(db, verdict="probable")

    from app.services import analyze as analyze_module

    call_count = [0]

    def counting_crawl(url, **kw):
        call_count[0] += 1
        return _make_crawl_result(_FILLER_200)

    monkeypatch.setattr(analyze_module, "crawl_site", counting_crawl)
    monkeypatch.setattr(analyze_module, "detect_tech", lambda page: [])
    monkeypatch.setattr(analyze_module, "get_first_seen", lambda domain: None)
    monkeypatch.setattr(analyze_module, "run_lighthouse", lambda url: None)

    result = analyze_module.analyze_pending(limit=10, force=False, db=db)

    assert call_count[0] == 0, "analyze_pending ne doit pas re-analyser une analyse 'probable'"
    _cleanup_reentry(db)


def test_analyze_pending_force_reanalyzes_existing(db, monkeypatch):
    """force=True → re-analyse même une entreprise avec une analyse non-indeterminate."""
    _cleanup_reentry(db)
    _make_db_company_with_analysis(db, verdict="probable")

    from app.services import analyze as analyze_module

    call_count = [0]

    def counting_crawl(url, **kw):
        call_count[0] += 1
        return _make_crawl_result(_FILLER_200)

    monkeypatch.setattr(analyze_module, "crawl_site", counting_crawl)
    monkeypatch.setattr(analyze_module, "detect_tech", lambda page: [])
    monkeypatch.setattr(analyze_module, "get_first_seen", lambda domain: None)
    monkeypatch.setattr(analyze_module, "run_lighthouse", lambda url: None)

    analyze_module.analyze_pending(limit=10, force=True, db=db)

    assert call_count[0] >= 1, "force=True doit re-analyser"
    _cleanup_reentry(db)


def test_analyze_pending_indeterminate_requeued(db, monkeypatch):
    """Une analyse 'indeterminate' est reprise par analyze_pending sans force."""
    _cleanup_reentry(db)
    _make_db_company_with_analysis(db, verdict="indeterminate")

    from app.services import analyze as analyze_module

    call_count = [0]

    def counting_crawl(url, **kw):
        call_count[0] += 1
        return _make_crawl_result(_FILLER_200)

    monkeypatch.setattr(analyze_module, "crawl_site", counting_crawl)
    monkeypatch.setattr(analyze_module, "detect_tech", lambda page: [])
    monkeypatch.setattr(analyze_module, "get_first_seen", lambda domain: None)
    monkeypatch.setattr(analyze_module, "run_lighthouse", lambda url: None)

    analyze_module.analyze_pending(limit=10, force=False, db=db)

    assert call_count[0] >= 1, "Un indéterminé doit être repris automatiquement"
    _cleanup_reentry(db)


# ── Tests unitaires tech_detect ───────────────────────────────────────────────

def _make_tech_page(html: str = "", headers: dict | None = None) -> dict:
    return {"html": html, "headers": headers or {}}


def test_tech_detect_obsolescence_signals_are_age_markers_only():
    """OBSOLESCENCE_SIGNALS ne contient que de vrais marqueurs d'âge, pas des CMS courants."""
    from app.services.tech_detect import OBSOLESCENCE_SIGNALS
    # CMS courants maintenus ne doivent PAS être dans OBSOLESCENCE_SIGNALS
    for modern_tech in ("WordPress", "Drupal", "PrestaShop", "Bootstrap", "jQuery",
                        "React", "Vue.js", "Angular", "Shopify", "Wix"):
        assert modern_tech not in OBSOLESCENCE_SIGNALS, (
            f"{modern_tech} est dans OBSOLESCENCE_SIGNALS mais c'est une techno maintenue"
        )
    # Les vrais marqueurs doivent être présents
    for dead_tech in ("jQuery 1.x", "jQuery 2.x", "Font Awesome 4", "Flash",
                      "Prototype.js", "Scriptaculous", "MooTools", "FrontPage"):
        assert dead_tech in OBSOLESCENCE_SIGNALS, (
            f"{dead_tech} devrait être dans OBSOLESCENCE_SIGNALS"
        )


def test_tech_detect_jquery_1x():
    """jquery-1.x.y.min.js → 'jQuery 1.x' (signal obsolescence) ET 'jQuery' (générique)."""
    from app.services.tech_detect import detect_tech, OBSOLESCENCE_SIGNALS
    page = _make_tech_page('<script src="/js/jquery-1.12.4.min.js"></script>')
    result = detect_tech(page)
    assert "jQuery 1.x" in result
    assert "jQuery" in result
    assert "jQuery 1.x" in OBSOLESCENCE_SIGNALS


def test_tech_detect_jquery_2x():
    """jquery-2.x → 'jQuery 2.x' (signal obsolescence)."""
    from app.services.tech_detect import detect_tech
    page = _make_tech_page('<script src="/vendor/jquery-2.2.4.min.js"></script>')
    result = detect_tech(page)
    assert "jQuery 2.x" in result


def test_tech_detect_font_awesome_4():
    """Chemin /font-awesome/4.x/ → 'Font Awesome 4' (signal obsolescence) ET 'Font Awesome'."""
    from app.services.tech_detect import detect_tech, OBSOLESCENCE_SIGNALS
    page = _make_tech_page('<link href="/assets/font-awesome/4.7.0/css/font-awesome.min.css">')
    result = detect_tech(page)
    assert "Font Awesome 4" in result
    assert "Font Awesome" in result
    assert "Font Awesome 4" in OBSOLESCENCE_SIGNALS


def test_tech_detect_flash():
    """Présence du type MIME Flash → 'Flash' (signal obsolescence)."""
    from app.services.tech_detect import detect_tech
    page = _make_tech_page('<object type="application/x-shockwave-flash" data="player.swf">')
    result = detect_tech(page)
    assert "Flash" in result


def test_tech_detect_modern_jquery_not_obsolete():
    """jQuery générique (sans version 1.x/2.x) → 'jQuery' mais pas 'jQuery 1.x'."""
    from app.services.tech_detect import detect_tech
    page = _make_tech_page('<script src="/js/jquery.min.js"></script>')
    result = detect_tech(page)
    assert "jQuery" in result
    assert "jQuery 1.x" not in result
    assert "jQuery 2.x" not in result


def test_tech_detect_wordpress_header_only():
    """WordPress via wp-content → détecté, mais absence dans OBSOLESCENCE_SIGNALS."""
    from app.services.tech_detect import detect_tech, OBSOLESCENCE_SIGNALS
    page = _make_tech_page('<script src="/wp-content/themes/mytheme/script.js"></script>')
    result = detect_tech(page)
    assert "WordPress" in result
    detected_obs = [t for t in result if t in OBSOLESCENCE_SIGNALS]
    assert detected_obs == [], f"WordPress ne devrait pas déclencher OBSOLESCENCE_SIGNALS, trouvé: {detected_obs}"


def test_tech_detect_cloudflare_via_header():
    """CF-Ray header → Cloudflare détecté via headers."""
    from app.services.tech_detect import detect_tech
    page = _make_tech_page(headers={"CF-Ray": "abc123-CDG"})
    result = detect_tech(page)
    assert "Cloudflare" in result


def test_tech_detect_prototype_js():
    """prototype.js → 'Prototype.js' dans OBSOLESCENCE_SIGNALS."""
    from app.services.tech_detect import detect_tech, OBSOLESCENCE_SIGNALS
    page = _make_tech_page('<script src="/js/prototype.js"></script>')
    result = detect_tech(page)
    assert "Prototype.js" in result
    assert "Prototype.js" in OBSOLESCENCE_SIGNALS


# ── Tests unitaires sitemap ───────────────────────────────────────────────────

_SIMPLE_SITEMAP = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>https://example.fr/</loc><lastmod>2023-06-15</lastmod></url>
  <url><loc>https://example.fr/about</loc><lastmod>2022-11-01</lastmod></url>
  <url><loc>https://example.fr/contact</loc></url>
</urlset>"""

_SITEMAPINDEX = """<?xml version="1.0" encoding="UTF-8"?>
<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <sitemap><loc>https://example.fr/sitemap-pages.xml</loc></sitemap>
  <sitemap><loc>https://example.fr/sitemap-blog.xml</loc></sitemap>
</sitemapindex>"""

_SUB_SITEMAP = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>https://example.fr/page1</loc><lastmod>2024-01-10</lastmod></url>
  <url><loc>https://example.fr/page2</loc><lastmod>2021-03-05</lastmod></url>
</urlset>"""


def test_sitemap_parses_simple_urlset(monkeypatch):
    """Un sitemap standard retourne page_count et la date lastmod la plus récente."""
    from app.services import sitemap as sitemap_module

    monkeypatch.setattr(sitemap_module, "_fetch_sitemap_xml", lambda domain, path, is_https: _SIMPLE_SITEMAP)

    result = sitemap_module.get_sitemap_dates("example.fr")

    assert result is not None
    assert result["page_count"] == 3
    assert result["last_modified"] == "2023-06-15"  # max des deux dates présentes


def test_sitemap_handles_absent_lastmod(monkeypatch):
    """Si aucun lastmod n'est présent, last_modified est None mais page_count est correct."""
    from app.services import sitemap as sitemap_module

    xml = """<?xml version="1.0"?>
    <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
      <url><loc>https://example.fr/</loc></url>
      <url><loc>https://example.fr/about</loc></url>
    </urlset>"""

    monkeypatch.setattr(sitemap_module, "_fetch_sitemap_xml", lambda domain, path, is_https: xml)

    result = sitemap_module.get_sitemap_dates("example.fr")

    assert result is not None
    assert result["page_count"] == 2
    assert result["last_modified"] is None


def test_sitemap_follows_sitemapindex(monkeypatch):
    """Un sitemapindex → suit le premier enfant et extrait ses URLs."""
    from app.services import sitemap as sitemap_module

    def fake_fetch(domain, path, is_https):
        if path == "/sitemap.xml":
            return _SITEMAPINDEX
        return _SUB_SITEMAP

    monkeypatch.setattr(sitemap_module, "_fetch_sitemap_xml", fake_fetch)

    result = sitemap_module.get_sitemap_dates("example.fr")

    assert result is not None
    assert result["page_count"] == 2
    assert result["last_modified"] == "2024-01-10"


def test_sitemap_returns_none_on_fetch_failure(monkeypatch):
    """Si /sitemap.xml est introuvable, retourne None sans exception."""
    from app.services import sitemap as sitemap_module

    monkeypatch.setattr(sitemap_module, "_fetch_sitemap_xml", lambda domain, path, is_https: None)

    result = sitemap_module.get_sitemap_dates("example.fr")

    assert result is None


def test_sitemap_returns_none_on_empty_urlset(monkeypatch):
    """Un sitemap avec 0 <url> → None (pas de donnée exploitable)."""
    from app.services import sitemap as sitemap_module

    xml = """<?xml version="1.0"?>
    <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"></urlset>"""

    monkeypatch.setattr(sitemap_module, "_fetch_sitemap_xml", lambda domain, path, is_https: xml)

    result = sitemap_module.get_sitemap_dates("example.fr")

    assert result is None


# ── Tests unitaires contact_classify ─────────────────────────────────────────

def test_classify_email_generique_prefixes():
    """Préfixes fonctionnels connus → generique."""
    from app.services.contact_classify import classify_email, GENERIQUE
    for addr in ("contact@example.fr", "info@example.fr", "accueil@example.fr",
                 "direction@example.fr", "rh@example.fr", "commercial@example.fr",
                 "noreply@example.fr", "no-reply@example.fr", "newsletter@example.fr"):
        assert classify_email(addr) == GENERIQUE, f"{addr} attendu generique"


def test_classify_email_nominatif_two_part():
    """Deux parties séparées par . - _ → nominatif."""
    from app.services.contact_classify import classify_email, NOMINATIF
    for addr in ("jean.dupont@example.fr", "marie-claire@example.fr",
                 "pierre_martin@example.fr", "j.dupont@example.fr"):
        assert classify_email(addr) == NOMINATIF, f"{addr} attendu nominatif"


def test_classify_email_incertain_single_word():
    """Mot unique non dans la liste générique → incertain (jamais generique par défaut)."""
    from app.services.contact_classify import classify_email, INCERTAIN
    for addr in ("jean@boulangerie-jean.fr", "pierre@example.fr", "hotel@example.fr",
                 "dupont@example.fr"):
        assert classify_email(addr) == INCERTAIN, f"{addr} attendu incertain"


def test_classify_phone_is_generique():
    """Téléphones → toujours generique."""
    from app.services.contact_classify import classify_contact, GENERIQUE
    assert classify_contact("phone", "+33123456789") == GENERIQUE
    assert classify_contact("phone", "0123456789") == GENERIQUE


def test_classify_incertain_never_silent():
    """incertain porte le même avertissement RGPD que nominatif — vérification sur ContactRead."""
    from app.schemas.company import ContactRead
    from datetime import datetime, UTC

    contact_incertain = ContactRead(
        id=1, type="email", value="jean@boulangerie-jean.fr",
        source="page", nature="incertain", suspicious=False,
        created_at=datetime.now(UTC),
    )
    contact_generique = ContactRead(
        id=2, type="email", value="contact@example.fr",
        source="page", nature="generique", suspicious=False,
        created_at=datetime.now(UTC),
    )
    assert any("prospection" in w for w in contact_incertain.warnings), \
        "incertain doit porter l'avertissement RGPD"
    assert not any("prospection" in w for w in contact_generique.warnings), \
        "generique ne doit pas porter l'avertissement RGPD"


def test_classify_suspicious_adds_warning():
    """suspicious=True → avertissement d'origine incertaine dans ContactRead.warnings."""
    from app.schemas.company import ContactRead
    from datetime import datetime, UTC

    c = ContactRead(
        id=1, type="email", value="contact@example.fr",
        source="osm", nature="generique", suspicious=True,
        created_at=datetime.now(UTC),
    )
    assert any("origine incertaine" in w for w in c.warnings)


def test_classify_generique_not_suspicious_no_warnings():
    """generique + suspicious=False → aucun avertissement."""
    from app.schemas.company import ContactRead
    from datetime import datetime, UTC

    c = ContactRead(
        id=1, type="email", value="contact@example.fr",
        source="page", nature="generique", suspicious=False,
        created_at=datetime.now(UTC),
    )
    assert c.warnings == []


def test_classify_nature_none_gets_rgpd_warning():
    """nature=None (contact non classifié, héritage) → avertissement RGPD par précaution."""
    from app.schemas.company import ContactRead
    from datetime import datetime, UTC

    c = ContactRead(
        id=1, type="email", value="x@example.fr",
        source="page", nature=None, suspicious=None,
        created_at=datetime.now(UTC),
    )
    assert any("prospection" in w for w in c.warnings)


# ── Tests tier 1/2 de l'audit dans analyze_company ───────────────────────────

def test_analyze_tier1_runs_on_probable(db, monkeypatch):
    """Verdict probable → tier 1 (tech+wayback+sitemap) appelé, Lighthouse pas appelé."""
    _cleanup_analyze(db)
    # Denomination + code_postal dans le texte → probable (pas de SIREN)
    company, website = _make_db_company_with_website(db, domain="hoteldutest.fr")

    from app.services import analyze as analyze_module

    probable_html = (
        f"<html><body>Hôtel du Test, Annecy 74000. {_FILLER_200}</body></html>"
    )
    crawl_mock = _make_crawl_result(probable_html, url="https://hoteldutest.fr")
    monkeypatch.setattr(analyze_module, "crawl_site", lambda url, **kw: crawl_mock)

    tier1_calls: dict[str, int] = {"tech": 0, "wayback": 0, "sitemap": 0}
    lh_called = [False]

    monkeypatch.setattr(analyze_module, "detect_tech", lambda page: (tier1_calls.__setitem__("tech", tier1_calls["tech"] + 1) or []))
    monkeypatch.setattr(analyze_module, "get_first_seen", lambda domain: (tier1_calls.__setitem__("wayback", tier1_calls["wayback"] + 1) or None))
    monkeypatch.setattr(analyze_module, "get_sitemap_dates", lambda domain, **kw: (tier1_calls.__setitem__("sitemap", tier1_calls["sitemap"] + 1) or None))
    monkeypatch.setattr(analyze_module, "run_lighthouse", lambda url: (lh_called.__setitem__(0, True) or None))

    from sqlalchemy.orm import selectinload
    company = db.scalar(
        select(Company).where(Company.siren == _ANALYZE_SIREN)
        .options(selectinload(Company.websites), selectinload(Company.dirigeants))
    )

    outcome = analyze_module.analyze_company(company, db)

    assert outcome == "done", f"Attendu 'done' pour probable, obtenu '{outcome}'"
    assert tier1_calls["tech"] == 1, "detect_tech doit être appelé sur probable"
    assert tier1_calls["wayback"] == 1, "get_first_seen doit être appelé sur probable"
    assert tier1_calls["sitemap"] == 1, "get_sitemap_dates doit être appelé sur probable"
    assert not lh_called[0], "Lighthouse ne doit PAS être appelé sur probable"
    _cleanup_analyze(db)


def test_analyze_tier2_runs_only_on_confirmed(db, monkeypatch):
    """Verdict confirmed → tier 1 ET tier 2 (Lighthouse) appelés."""
    _cleanup_analyze(db)
    company, website = _make_db_company_with_website(db, domain="hoteldutest.fr")

    from app.services import analyze as analyze_module

    siren_html = (
        f"<html><body>SIREN 888 888 888 — Hôtel du Test Annecy 74000. {_FILLER_200}</body></html>"
    )
    crawl_mock = _make_crawl_result(siren_html, url="https://hoteldutest.fr")
    monkeypatch.setattr(analyze_module, "crawl_site", lambda url, **kw: crawl_mock)

    lh_called = [False]
    monkeypatch.setattr(analyze_module, "detect_tech", lambda page: [])
    monkeypatch.setattr(analyze_module, "get_first_seen", lambda domain: None)
    monkeypatch.setattr(analyze_module, "get_sitemap_dates", lambda domain, **kw: None)
    monkeypatch.setattr(analyze_module, "run_lighthouse", lambda url: (lh_called.__setitem__(0, True) or None))

    from sqlalchemy.orm import selectinload
    company = db.scalar(
        select(Company).where(Company.siren == _ANALYZE_SIREN)
        .options(selectinload(Company.websites), selectinload(Company.dirigeants))
    )

    outcome = analyze_module.analyze_company(company, db)

    assert outcome == "done"
    assert lh_called[0], "Lighthouse doit être appelé sur confirmed"
    _cleanup_analyze(db)


def test_analyze_sitemap_results_written_to_analysis(db, monkeypatch):
    """Résultats du sitemap stockés dans analysis.sitemap_last_modified et sitemap_page_count."""
    _cleanup_analyze(db)
    company, website = _make_db_company_with_website(db, domain="hoteldutest.fr")

    from app.services import analyze as analyze_module

    siren_html = (
        f"<html><body>SIREN 888 888 888 — Hôtel du Test Annecy 74000. {_FILLER_200}</body></html>"
    )
    crawl_mock = _make_crawl_result(siren_html, url="https://hoteldutest.fr")
    monkeypatch.setattr(analyze_module, "crawl_site", lambda url, **kw: crawl_mock)
    monkeypatch.setattr(analyze_module, "detect_tech", lambda page: [])
    monkeypatch.setattr(analyze_module, "get_first_seen", lambda domain: None)
    monkeypatch.setattr(analyze_module, "get_sitemap_dates",
                        lambda domain, **kw: {"last_modified": "2022-09-14", "page_count": 37})
    monkeypatch.setattr(analyze_module, "run_lighthouse", lambda url: None)

    from sqlalchemy.orm import selectinload
    company = db.scalar(
        select(Company).where(Company.siren == _ANALYZE_SIREN)
        .options(selectinload(Company.websites), selectinload(Company.dirigeants))
    )

    analyze_module.analyze_company(company, db)

    analysis = db.scalar(select(Analysis).where(Analysis.company_id == company.id))
    assert analysis.sitemap_last_modified == "2022-09-14"
    assert analysis.sitemap_page_count == 37
    _cleanup_analyze(db)
