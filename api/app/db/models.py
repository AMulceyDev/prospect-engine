from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def _utcnow() -> datetime:
    return datetime.now(UTC)


class Company(Base):
    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    siren: Mapped[str] = mapped_column(String(9), unique=True, index=True)

    denomination: Mapped[str | None] = mapped_column(String)
    type_personne: Mapped[str | None] = mapped_column(String)
    forme_juridique: Mapped[str | None] = mapped_column(String)
    code_ape: Mapped[str | None] = mapped_column(String)
    date_creation: Mapped[str | None] = mapped_column(String)

    commune: Mapped[str | None] = mapped_column(String)
    code_postal: Mapped[str | None] = mapped_column(String)
    code_insee_commune: Mapped[str | None] = mapped_column(String)

    # False means the company opted out of public diffusion
    diffusion_insee: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    noms_de_domaine: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)

    source_insee: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    source_rne: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )
    insee_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rne_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    dirigeants: Mapped[list["Dirigeant"]] = relationship(
        back_populates="company", cascade="all, delete-orphan"
    )
    websites: Mapped[list["Website"]] = relationship(
        back_populates="company", cascade="all, delete-orphan"
    )
    analysis: Mapped["Analysis | None"] = relationship(
        back_populates="company", cascade="all, delete-orphan", uselist=False
    )
    contacts: Mapped[list["Contact"]] = relationship(
        back_populates="company", cascade="all, delete-orphan"
    )


class Dirigeant(Base):
    __tablename__ = "dirigeants"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True, nullable=False
    )

    nom: Mapped[str | None] = mapped_column(String)
    prenoms: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    role: Mapped[str | None] = mapped_column(String)
    beneficiaire_effectif: Mapped[bool | None] = mapped_column(Boolean)
    diffusion_commerciale: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    company: Mapped["Company"] = relationship(back_populates="dirigeants")


class Website(Base):
    __tablename__ = "websites"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True, nullable=False
    )

    url: Mapped[str] = mapped_column(String, nullable=False)
    domain: Mapped[str] = mapped_column(String, nullable=False)
    pattern: Mapped[str] = mapped_column(String, nullable=False)
    source: Mapped[str] = mapped_column(String, nullable=False)  # "rne" | "searxng"

    dns_resolved: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    http_status: Mapped[int | None] = mapped_column(Integer)
    final_url: Mapped[str | None] = mapped_column(String)
    is_https: Mapped[bool | None] = mapped_column(Boolean)
    response_time_ms: Mapped[int | None] = mapped_column(Integer)
    error: Mapped[str | None] = mapped_column(String)

    confidence: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_selected: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )

    company: Mapped["Company"] = relationship(back_populates="websites")


class Analysis(Base):
    __tablename__ = "analyses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), unique=True, index=True, nullable=False
    )
    website_id: Mapped[int] = mapped_column(
        ForeignKey("websites.id", ondelete="CASCADE"), nullable=False
    )

    ownership_confirmed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    ownership_signals: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    tech_stack: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    wayback_first_seen: Mapped[str | None] = mapped_column(String)

    llm_score: Mapped[int | None] = mapped_column(Integer)
    llm_obsolete: Mapped[bool | None] = mapped_column(Boolean)
    llm_verdict: Mapped[str | None] = mapped_column(String)

    lighthouse_scores: Mapped[dict | None] = mapped_column(JSONB)
    lighthouse_seo: Mapped[dict | None] = mapped_column(JSONB)
    lighthouse_remarks: Mapped[list | None] = mapped_column(JSONB)

    # Lot C — sitemap (weak freshness signal; lastmod often auto-generated)
    sitemap_last_modified: Mapped[str | None] = mapped_column(String)
    sitemap_page_count: Mapped[int | None] = mapped_column(Integer)

    # Lot A — site map (shallow crawl)
    internal_links: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    external_links: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    has_legal_page: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    has_contact_info: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    provider_hint: Mapped[str | None] = mapped_column(String)

    analyzed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )

    company: Mapped["Company"] = relationship(back_populates="analysis")
    website: Mapped["Website"] = relationship()


class Contact(Base):
    __tablename__ = "contacts"
    __table_args__ = (
        UniqueConstraint("company_id", "type", "value", name="uq_contacts_company_type_value"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True, nullable=False
    )
    type: Mapped[str] = mapped_column(String, nullable=False)    # "email" | "phone"
    value: Mapped[str] = mapped_column(String, nullable=False)
    source: Mapped[str] = mapped_column(String, nullable=False)  # "osm" | "page" | "rne"
    nature: Mapped[str | None] = mapped_column(String)           # "nominatif" | "generique" | NULL (lot C)
    suspicious: Mapped[bool | None] = mapped_column(Boolean)     # NULL=unknown, True=OSM domain mismatch
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )

    company: Mapped["Company"] = relationship(back_populates="contacts")


class RawPayload(Base):
    __tablename__ = "raw_payloads"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    siren: Mapped[str] = mapped_column(String(9), index=True, nullable=False)
    source: Mapped[str] = mapped_column(String, nullable=False)  # "insee" | "rne"
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
