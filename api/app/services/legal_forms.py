"""
Mapping partiel des codes catégorie juridique INSEE (niveau III) vers des libellés lisibles.
Source : nomenclature INSEE des catégories juridiques.
Couvre les codes courants — à compléter depuis le fichier INSEE officiel si besoin.
"""
from __future__ import annotations

LEGAL_FORM_LABELS: dict[str, str] = {
    # ── Entrepreneurs individuels (1xxx) ──────────────────────────────────────
    "1000": "Entrepreneur individuel",
    "1100": "Artisan-commerçant",
    "1200": "Artisan",
    "1300": "Commerçant",
    "1400": "Auxiliaire indépendant",
    "1500": "Officier public ou ministériel",
    "1600": "Officier public ou ministériel (autre)",
    "1700": "Agent commercial",
    "1900": "Autre personne physique",
    # ── Sociétés de personnes (52xx) ──────────────────────────────────────────
    "5202": "Société en nom collectif (SNC)",
    "5306": "Société en commandite simple",
    # ── SARL / EURL (54xx) ────────────────────────────────────────────────────
    "5410": "SARL à associé unique (EURL)",
    "5485": "SARL à capital variable",
    "5499": "Société à responsabilité limitée (SARL)",
    # ── Société anonyme (55xx) ────────────────────────────────────────────────
    "5505": "SA à directoire",
    "5510": "SA à conseil d'administration",
    "5599": "Société anonyme (SA)",
    # ── SAS / SASU / SPFPL (57xx) ────────────────────────────────────────────
    "5710": "Société par actions simplifiée (SAS)",
    "5720": "Société par actions simplifiée unipersonnelle (SASU)",
    "5770": "Société de participations financières de profession libérale SAS (SPFPL SAS)",
    # ── Groupements (62xx) ────────────────────────────────────────────────────
    "6220": "Groupement d'intérêt économique (GIE)",
    # ── Sociétés civiles (65xx) ───────────────────────────────────────────────
    "6521": "Société civile de placement immobilier (SCPI)",
    "6532": "Société civile immobilière de construction-vente",
    "6533": "Société civile d'attribution",
    "6534": "Société civile d'accession progressive à la propriété",
    "6540": "Société civile immobilière (SCI)",
    "6541": "Société civile immobilière de construction vente",
    "6552": "Société civile de professions libérales (SCP)",
    "6564": "SCP d'huissiers",
    "6589": "Société civile de moyens (SCM)",
    "6595": "Société d'exercice libéral à responsabilité limitée (SELARL)",
    "6596": "SELARL à associé unique",
    "6597": "Société civile d'exploitation agricole (SCEA)",
    "6599": "Autre société civile",
    # ── Associations (92xx) ───────────────────────────────────────────────────
    "9220": "Association déclarée (loi 1901)",
    "9222": "Association intermédiaire",
    "9223": "Groupement d'employeurs",
    "9230": "Association reconnue d'utilité publique (RUP)",
    "9260": "Association droit local (Alsace-Moselle)",
    # ── Fondations (93xx) ─────────────────────────────────────────────────────
    "9300": "Fondation reconnue d'utilité publique",
}

# Prefixes excluded by default: EI (1xxx), sociétés civiles (65xx),
# associations (92xx), fondations (93xx).
DEFAULT_EXCLUDE_PREFIXES: list[str] = ["1", "65", "92", "93"]


def label(code: str | None) -> str:
    """Return the human-readable label for a legal form code.
    Falls back to the raw code if not in the mapping, or 'Inconnu' if None."""
    if code is None:
        return "Inconnu"
    return LEGAL_FORM_LABELS.get(code, code)
