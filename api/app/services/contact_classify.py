from __future__ import annotations

import re
import unicodedata

NOMINATIF = "nominatif"
GENERIQUE = "generique"
INCERTAIN = "incertain"

_GENERIC_PREFIXES: frozenset[str] = frozenset({
    "contact", "contacts", "info", "infos", "information",
    "accueil", "commercial", "secretariat", "direction", "hello", "bonjour",
    "rh", "service", "services", "admin", "administration",
    "comptabilite", "compta", "reception", "standard", "vente", "ventes",
    "devis", "support", "assistance", "technique", "communication", "marketing",
    "presse", "media", "partenariat", "recrutement", "emploi", "pro", "facturation",
    "invoice", "courrier", "agence", "bureau", "atelier", "numerique", "digital",
    "webmaster", "postmaster", "noreply", "no-reply", "no_reply", "newsletter",
    "reservation", "reservations", "commande", "commandes",
    "client", "clients", "gestion", "projet", "projets",
    "contact-us", "contact_us", "nous-contacter",
    "sav", "helpdesk", "boite",
    "dpo", "boutique", "magasin",
})

# Two-part patterns strongly suggesting a personal name (both parts ≥2 chars)
_NOMINATIF_RE = re.compile(
    r"^[a-z]{2,}[.\-_][a-z]{2,}$"  # prenom.nom, prenom-nom, prenom_nom
    r"|^[a-z]\.[a-z]{2,}$"          # p.nom (initial + surname)
)


def _strip_accents(s: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", s)
        if unicodedata.category(c) != "Mn"
    )


def classify_email(email: str) -> str:
    """Classify an email address as nominatif / generique / incertain.

    Rules (applied in order):
      1. Local part matches a known functional prefix → generique
      2. Local part matches a two-part personal pattern → nominatif
      3. Anything else → incertain (never silently generique)
    """
    local = _strip_accents(email.split("@")[0].lower())

    if local in _GENERIC_PREFIXES:
        return GENERIQUE

    if _NOMINATIF_RE.match(local):
        return NOMINATIF

    return INCERTAIN


def classify_contact(ctype: str, value: str) -> str:
    """Classify a contact by type+value. Phones are always generique (company standard)."""
    if ctype == "phone":
        return GENERIQUE
    if ctype == "email":
        return classify_email(value)
    return INCERTAIN
