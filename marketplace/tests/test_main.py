import httpx
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import main
from app.omd import OmdError


def test_health_reports_omd_down_without_crashing(monkeypatch):
    class Down:
        def get(self, *a, **k):
            raise OmdError(503, "Cannot reach OpenMetadata")

    main.app.dependency_overrides[main.get_omd] = lambda: Down()
    try:
        body = TestClient(main.app).get("/api/health").json()
    finally:
        main.app.dependency_overrides.clear()
    assert body == {"status": "ok", "omd": "down"}


def test_omd_error_becomes_503_with_message():
    app = FastAPI()
    app.add_exception_handler(OmdError, main.omd_error_handler)

    @app.get("/boom")
    def boom():
        raise OmdError(401, "OpenMetadata rejected the token")

    r = TestClient(app).get("/boom")
    assert r.status_code == 503
    assert r.json() == {"detail": "OpenMetadata rejected the token"}


def test_root_serves_the_marketplace_page_and_api_still_wins():
    client = TestClient(main.app)
    page = client.get("/")
    assert page.status_code == 200 and "Data Marketplace" in page.text
    assert client.get("/vendor/bootstrap/bootstrap.min.css").status_code == 200
    assert client.get("/api/products/definitely-missing").status_code in (404, 503)


def test_startup_warms_the_catalog_and_survives_omd_being_down(monkeypatch):
    calls = []

    class Catalog:
        def list_products(self):
            calls.append(1)
            raise OmdError(503, "down")

    monkeypatch.setattr(main, "get_catalog", lambda: Catalog())
    with TestClient(main.app):
        pass
    assert calls == [1]
