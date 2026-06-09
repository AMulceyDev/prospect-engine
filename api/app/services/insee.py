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

    def build_recent_query(self, days: int):
        today = date.today()
        start = today - timedelta(days=days)

        return (
            f"dateCreationUniteLegale:["
            f"{start.isoformat()} TO {today.isoformat()}]"
        )

    def fetch_recent_companies(
        self,
        days: int = 30,
        start: int = 0,
        rows: int = 100,
    ):
        params = {
            "q": self.build_recent_query(days),
            "start": start,
            "rows": rows,
        }

        response = requests.get(
            BASE_URL,
            headers=self.headers,
            params=params,
            timeout=30,
        )

        response.raise_for_status()

        return response.json().get("etablissements", [])