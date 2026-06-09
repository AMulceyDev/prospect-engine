from datetime import datetime

from pydantic import BaseModel, ConfigDict


class DirigeantRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    nom: str | None
    prenoms: list[str]
    role: str | None
    beneficiaire_effectif: bool | None
    diffusion_commerciale: bool


class CompanyRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    siren: str
    denomination: str | None
    type_personne: str | None
    forme_juridique: str | None
    code_ape: str | None
    date_creation: str | None
    commune: str | None
    code_postal: str | None
    diffusion_insee: bool
    noms_de_domaine: list[str]
    source_insee: bool
    source_rne: bool
    created_at: datetime
    updated_at: datetime


class CompanyDetail(CompanyRead):
    dirigeants: list[DirigeantRead]


class IngestResult(BaseModel):
    fetched: int
    processed: int
    skipped: int


class EnrichResult(BaseModel):
    enriched: int
    candidates: int