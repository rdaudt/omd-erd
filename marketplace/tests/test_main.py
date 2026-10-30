import httpx
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
    @main.app.get("/api/_boom")
    def boom():
        raise OmdError(401, "OpenMetadata rejected the token")

    r = TestClient(main.app).get("/api/_boom")
    assert r.status_code == 503
    assert r.json() == {"detail": "OpenMetadata rejected the token"}
