from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class DirigeantData:
    nom: str | None = None
    prenoms: list[str] = field(default_factory=list)
    role: str | None = None
    beneficiaire_effectif: bool | None = None
    diffusion_commerciale: bool = True

@dataclass
class CompanyData:
    siren: str
    denomination: str | None = None
    type_personne: str | None = None
    forme_juridique: str | None = None
    code_ape: str | None = None
    date_creation: str | None = None
    commune: str | None = None
    code_postal: str | None = None
    code_insee_commune: str | None = None
    diffusion_insee: bool = True
    noms_de_domaine: list[str] = field(default_factory=list)
    dirigeants: list[DirigeantData] = field(default_factory=list)

def normalize_insee(etab: dict) -> CompanyData | None:
    siren = etab.get("siren")
    if not siren:
        return None

    u = etab.get("uniteLegale", {}) or {}
    a = etab.get("adresseEtablissement", {}) or {}

    name = u.get("denominationUniteLegale") or u.get("nomUniteLegale")
    name = name.strip() if name else None

    statut = u.get("statutDiffusionUniteLegale")
    diffusion_insee = statut == "O" if statut is not None else True

    return CompanyData(
        siren=siren,
        denomination=name,
        code_ape=u.get("activitePrincipaleUniteLegale"),
        date_creation=u.get("dateCreationUniteLegale"),
        commune=a.get("libelleCommuneEtablissement"),
        code_postal=a.get("codePostalEtablissement"),
        code_insee_commune=a.get("codeCommuneEtablissement"),
        diffusion_insee=diffusion_insee,
    )

def normalize_rne(payload: dict) -> CompanyData:
    formality = payload.get("formality") or {}
    siren = formality.get("siren") or payload.get("siren")

    diffusion_commerciale = bool(formality.get("diffusionCommerciale", True))
    diffusable_insee = formality.get("diffusionINSEE") != "N"
    type_personne = formality.get("typePersonne")
    forme_juridique = formality.get("formeJuridique")

    content = formality.get("content") or {}

    pm = content.get("personneMorale") or {}
    pp = content.get("personnePhysique") or {}

    identite_pm = pm.get("identite") or {}
    denomination = (identite_pm.get("entreprise") or {}).get("denomination")

    domaines: list[str] = []
    for d in identite_pm.get("nomsDeDomaine") or []:
        if d.get("nomDomaine"):
            domaines.append(d["nomDomaine"])
    for source in (pm, pp):
        for etab in source.get("autresEtablissements") or []:
            for d in etab.get("nomsDeDomaine") or []:
                if d.get("nomDomaine"):
                    domaines.append(d["nomDomaine"])
    domaines = sorted(set(domaines))

    dirigeants: list[DirigeantData] = []
    composition = pm.get("composition") or {}
    for pouvoir in composition.get("pouvoirs") or []:
        individu = pouvoir.get("individu") or {}
        desc = individu.get("descriptionPersonne") or {}
        if desc.get("nom") or desc.get("prenoms"):
            dirigeants.append(DirigeantData(
                nom=desc.get("nom"),
                prenoms=desc.get("prenoms") or [],
                role=pouvoir.get("roleEntreprise"),
                beneficiaire_effectif=pouvoir.get("beneficiaireEffectif"),
                diffusion_commerciale=diffusion_commerciale,
            ))

    entrepreneur = (pp.get("identite") or {}).get("entrepreneur") or {}
    desc_pp = entrepreneur.get("descriptionPersonne") or {}
    if desc_pp.get("nom") or desc_pp.get("prenoms"):
        dirigeants.append(DirigeantData(
            nom=desc_pp.get("nom"),
            prenoms=desc_pp.get("prenoms") or [],
            role="entrepreneur",
            beneficiaire_effectif=None,
            diffusion_commerciale=diffusion_commerciale,
        ))

    return CompanyData(
        siren=siren,
        denomination=denomination,
        type_personne=type_personne,
        forme_juridique=forme_juridique,
        diffusion_insee=diffusable_insee,
        noms_de_domaine=domaines,
        dirigeants=dirigeants,
    )