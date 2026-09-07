from datetime import date, timedelta

import requests

BASE_URL = "https://api.insee.fr/api-sirene/3.11/siret"


class InseeClient:

    def __init__(self, api_key: str):
        self.api_key = api_key

    @property
    def headers(self):
        return {
            "X-INSEE-Api-Key-Integration": self.api_key,
            "Accept": "application/json",
        }

    def _build_query(
        self,
        days: int = 30,
        at_date: str | None = None,
        active_only: bool = False,
        categorie_min: int | None = 5000,
        categorie_max: int | None = 6999,
    ) -> str:
        # Date clause: exact date or rolling window
        if at_date:
            q = f"dateCreationUniteLegale:{at_date}"
        else:
            today = date.today()
            start = today - timedelta(days=days)
            q = f"dateCreationUniteLegale:[{start.isoformat()} TO {today.isoformat()}]"

        # One row per company instead of one per establishment
        q += " AND etablissementSiege:true"

        if active_only:
            q += " AND etatAdministratifUniteLegale:A"

        # Positive category targeting: default [5000 TO 6999] covers sociétés commerciales
        # (5xxx) and sociétés civiles/GIE (6xxx). Pass None/None to disable the filter.
        # Note: results are always sorted by SIREN ascending (API limitation) — within the
        # target range this is acceptable since low SIRENs belong to the excluded public
        # sector (7xxx) which this filter already eliminates.
        if categorie_min is not None or categorie_max is not None:
            lo = categorie_min if categorie_min is not None else 0
            hi = categorie_max if categorie_max is not None else 9999
            q += f" AND categorieJuridiqueUniteLegale:[{lo} TO {hi}]"

        return q

    def fetch_recent_companies(
        self,
        days: int = 30,
        at_date: str | None = None,
        start: int = 0,
        rows: int = 100,
        active_only: bool = False,
        categorie_min: int | None = 5000,
        categorie_max: int | None = 6999,
    ) -> list[dict]:
        params = {
            "q": self._build_query(
                days=days,
                at_date=at_date,
                active_only=active_only,
                categorie_min=categorie_min,
                categorie_max=categorie_max,
            ),
            "debut": start,
            "nombre": rows,
        }
        response = requests.get(BASE_URL, headers=self.headers, params=params, timeout=30)
        response.raise_for_status()
        return response.json().get("etablissements", [])
