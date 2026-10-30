import httpx

from app.config import Settings


class OmdError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status
        self.message = message


class OmdClient:
    def __init__(self, settings: Settings, transport: httpx.BaseTransport | None = None):
        host = settings.omd_host.rstrip("/")
        base = host + "/v1" if host.endswith("/api") else host + "/api/v1"
        self._http = httpx.Client(
            base_url=base,
            headers={"Authorization": f"Bearer {settings.omd_token}"},
            timeout=settings.request_timeout_seconds,
            transport=transport,
        )

    def _request(self, method: str, path: str, **kwargs) -> dict:
        try:
            response = self._http.request(method, path, **kwargs)
        except httpx.HTTPError:
            raise OmdError(503, "Cannot reach OpenMetadata. Is it running?") from None
        if response.status_code == 401:
            raise OmdError(401, "OpenMetadata rejected the access token.")
        if response.status_code >= 500:
            raise OmdError(response.status_code, "OpenMetadata returned a server error.")
        if response.status_code >= 400:
            raise OmdError(response.status_code, response.text[:300])
        return response.json() if response.content else {}

    def get(self, path: str, params: dict | None = None) -> dict:
        return self._request("GET", path, params=params)

    def put(self, path: str, json: dict) -> dict:
        return self._request("PUT", path, json=json)

    def post(self, path: str, json: dict) -> dict:
        return self._request("POST", path, json=json)

    def patch(self, path: str, ops: list[dict]) -> dict:
        return self._request("PATCH", path, json=ops, headers={"Content-Type": "application/json-patch+json"})

    def list_all(self, path: str, params: dict | None = None, page_size: int = 100) -> list[dict]:
        items: list[dict] = []
        query = {**(params or {}), "limit": page_size}
        while True:
            page = self.get(path, query)
            items.extend(page.get("data", []))
            after = (page.get("paging") or {}).get("after")
            if not after:
                return items
            query = {**query, "after": after}
