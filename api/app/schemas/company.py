from datetime import datetime

from pydantic import BaseModel, ConfigDict, computed_field

from app.services.contact_classify import GENERIQUE
from app.services import naf as naf_service
from app.services import inpi_roles


class DomainEntry(BaseModel):
    domain: str
    source: str  # "rne" | "osm"


class ContactRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    type: str         # "email" | "phone"
    value: str
    source: str       # "osm" | "page" | "rne"
    nature: str | None   # "nominatif" | "generique" | "incertain" | None
    suspicious: bool | None
    created_at: datetime

    @computed_field
    @property
    def warnings(self) -> list[str]:
        result: list[str] = []
        if self.suspicious:
            result.append(
                "origine incertaine, vérifier que ce contact appartient bien à l'entreprise"
            )
        if self.nature != GENERIQUE:
            result.append(
                "contact nominatif — donnée personnelle, vérifiez le droit de prospection avant usage"
            )
        return result


class WebsiteRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    url: str
    domain: str
    source: str
    dns_resolved: bool
    http_status: int | None
    final_url: str | None
    is_https: bool | None
    confidence: int
    is_selected: bool


class AnalysisRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    ownership_confirmed: bool
    ownership_signals: dict
    internal_links: list
    external_links: list
    has_legal_page: bool
    has_contact_info: bool
    provider_hint: str | None
    tech_stack: list[str]

    @computed_field
    @property
    def obsolete_tech(self) -> list[str]:
        from app.services.tech_detect import OBSOLESCENCE_SIGNALS
        return [t for t in self.tech_stack if t in OBSOLESCENCE_SIGNALS]

    wayback_first_seen: str | None
    sitemap_last_modified: str | None
    sitemap_page_count: int | None
    llm_score: int | None
    llm_obsolete: bool | None
    llm_verdict: str | None
    lighthouse_scores: dict | None
    lighthouse_seo: dict | None
    lighthouse_remarks: list | None
    analyzed_at: datetime


class DirigeantRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    nom: str | None
    prenoms: list[str]
    role: str | None
    beneficiaire_effectif: bool | None
    diffusion_commerciale: bool

    @computed_field
    @property
    def role_label(self) -> str:
        return inpi_roles.label(self.role)


class CompanyRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    siren: str
    denomination: str | None
    type_personne: str | None
    forme_juridique: str | None
    code_ape: str | None
    date_creation: str | None

    @computed_field
    @property
    def code_ape_label(self) -> str:
        return naf_service.label(self.code_ape)
    commune: str | None
    code_postal: str | None
    diffusion_insee: bool
    noms_de_domaine: list[DomainEntry]
    source_insee: bool
    source_rne: bool
    created_at: datetime
    updated_at: datetime
    websites: list[WebsiteRead]
    contacts: list[ContactRead]
    analysis: AnalysisRead | None


class CompanyDetail(CompanyRead):
    dirigeants: list[DirigeantRead]

    @computed_field
    @property
    def has_dirigeants_opposition(self) -> bool:
        return any(not d.diffusion_commerciale for d in self.dirigeants)


class IngestResult(BaseModel):
    fetched: int
    processed: int
    skipped: int


class EnrichResult(BaseModel):
    enriched: int
    candidates: int
    skipped: int = 0


class WebsiteDetectResult(BaseModel):
    processed: int
    candidates_probed: int


class LegalFormCount(BaseModel):
    code: str | None
    label: str
    count: int


class FilterResult(BaseModel):
    deleted: int
    dry_run: bool = False
    breakdown: list[LegalFormCount] = []


class OsmResult(BaseModel):
    clusters_processed: int
    matched: int


class EnrichSirenResult(BaseModel):
    siren: str
    rne_ok: bool
    rne_dirigeants: int
    osm_ok: bool
    osm_domain: str | None
    osm_contacts: int


class AnalyzeResult(BaseModel):
    done: int
    not_owned: int
    indeterminate: int
    no_site: int
