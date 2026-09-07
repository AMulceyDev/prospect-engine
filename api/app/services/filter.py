from __future__ import annotations

from sqlalchemy import delete, func, or_
from sqlalchemy.orm import Session

from app.db.models import Company
from app.services.legal_forms import DEFAULT_EXCLUDE_PREFIXES, label


def delete_non_prospects(
    db: Session,
    exclude_prefixes: list[str] | None = None,
    dry_run: bool = False,
) -> dict:
    """Hard-delete companies whose legal form starts with any of the given prefixes.

    Uses DEFAULT_EXCLUDE_PREFIXES when exclude_prefixes is None.
    When dry_run=True, computes the breakdown without deleting.
    Returns {deleted, dry_run, breakdown} where `deleted` is the number of
    affected rows (actual if dry_run=False, would-be if dry_run=True).
    """
    prefixes = exclude_prefixes if exclude_prefixes is not None else DEFAULT_EXCLUDE_PREFIXES

    if not prefixes:
        return {"deleted": 0, "dry_run": dry_run, "breakdown": []}

    condition = or_(*(Company.forme_juridique.like(f"{p}%") for p in prefixes))

    # Compute breakdown before the DELETE so counts are always available.
    rows = (
        db.query(Company.forme_juridique, func.count(Company.id))
        .where(condition)
        .group_by(Company.forme_juridique)
        .order_by(func.count(Company.id).desc())
        .all()
    )
    breakdown = [{"code": code, "label": label(code), "count": count} for code, count in rows]
    total = sum(r["count"] for r in breakdown)

    if not dry_run:
        db.execute(delete(Company).where(condition))
        db.commit()

    return {"deleted": total, "dry_run": dry_run, "breakdown": breakdown}
