import httpx
import pytest

from app.omd import OmdError


def test_list_all_follows_paging_after(omd_client_factory):
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.params.get("after"))
        if request.url.params.get("after") is None:
            return httpx.Response(200, json={"data": [{"n": 1}], "paging": {"after": "abc"}})
        return httpx.Response(200, json={"data": [{"n": 2}], "paging": {}})

    client = omd_client_factory(handler)
    assert client.list_all("/tables") == [{"n": 1}, {"n": 2}]
    assert calls == [None, "abc"]


def test_get_sends_bearer_token_and_v1_base(omd_client_factory):
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["auth"] = request.headers["authorization"]
        seen["path"] = request.url.path
        return httpx.Response(200, json={})

    omd_client_factory(handler).get("/tables")
    assert seen == {"auth": "Bearer tok", "path": "/api/v1/tables"}


def test_unreachable_raises_omd_error(omd_client_factory):
    def handler(request):
        raise httpx.ConnectError("down")

    with pytest.raises(OmdError) as exc:
        omd_client_factory(handler).get("/tables")
    assert "reach" in exc.value.message.lower()


def test_401_raises_omd_error_with_status_401(omd_client_factory):
    client = omd_client_factory(lambda r: httpx.Response(401, json={"message": "no"}))
    with pytest.raises(OmdError) as exc:
        client.get("/tables")
    assert exc.value.status == 401


def test_host_without_api_suffix_gets_api_v1(omd_client_factory):
    from app.omd import OmdClient
    from tests.conftest import make_settings

    seen = {}

    def handler(request):
        seen["path"] = request.url.path
        return httpx.Response(200, json={})

    OmdClient(make_settings(OMD_HOST="http://omd.test"), transport=httpx.MockTransport(handler)).get("/x")
    assert seen["path"] == "/api/v1/x"


def test_timeout_is_reported_as_timeout_not_unreachable(omd_client_factory):
    def handler(request):
        raise httpx.ReadTimeout("slow")

    with pytest.raises(OmdError) as exc:
        omd_client_factory(handler).get("/tables")
    assert "timed out" in exc.value.message.lower()
