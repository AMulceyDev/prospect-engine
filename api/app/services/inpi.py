import logging
import time

import requests

logger = logging.getLogger("inpi.rne")

BASE_URL = "https://registre-national-entreprises.inpi.fr"


class RNEError(Exception):
    pass


class RNEAuthError(RNEError):
    pass


class RNEQuotaExceeded(RNEError):
    pass


class InpiClient:
    def __init__(self, username: str, password: str, base_url: str = BASE_URL,
                 timeout: float = 30.0, max_retries: int = 5):
        self.username = username
        self.password = password
        self.base_url = base_url
        self.timeout = timeout
        self.max_retries = max_retries
        self._token: str | None = None
        self._session = requests.Session()
        self._session.headers.update({"Accept": "application/json"})

    def _login(self) -> str:
        resp = self._session.post(
            f"{self.base_url}/api/sso/login",
            json={"username": self.username, "password": self.password},
            timeout=self.timeout,
        )
        if resp.status_code in (401, 403):
            raise RNEAuthError("Identifiants INPI refusés.")
        resp.raise_for_status()
        token = resp.json().get("token")
        if not token:
            raise RNEAuthError("Réponse de login sans token.")
        self._token = token
        logger.info("Token RNE obtenu.")
        return token

    def _auth_header(self) -> dict[str, str]:
        token = self._token or self._login()
        return {"Authorization": f"Bearer {token}"}

    def _request(self, method: str, path: str, allow_404: bool = False, **kwargs):
        retried_auth = False
        for attempt in range(self.max_retries + 1):
            headers = {**kwargs.pop("headers", {}), **self._auth_header()}
            resp = self._session.request(
                method, f"{self.base_url}{path}", headers=headers,
                timeout=self.timeout, **kwargs,
            )
            if resp.status_code == 401 and not retried_auth:
                self._token = None
                retried_auth = True
                continue
            if resp.status_code == 404 and allow_404:
                return None
            if resp.status_code == 429:
                if attempt >= self.max_retries:
                    raise RNEQuotaExceeded("Quota journalier RNE dépassé.")
                time.sleep(2 ** attempt)
                continue
            if resp.status_code >= 500:
                if attempt >= self.max_retries:
                    resp.raise_for_status()
                time.sleep(2 ** attempt)
                continue
            resp.raise_for_status()
            return resp
        raise RNEError("Tentatives épuisées.")

    def get_company(self, siren: str) -> dict | None:
        resp = self._request("GET", f"/api/companies/{siren}", allow_404=True)
        if resp is None:
            return None
        return resp.json()