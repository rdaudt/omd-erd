import httpx
import pytest

from app.config import Settings
from app.omd import OmdClient


def make_settings(**overrides) -> Settings:
    values = {"OMD_HOST": "http://omd.test/api", "OMD_TOKEN": "tok", **overrides}
    return Settings(_env_file=None, **values)


@pytest.fixture
def omd_client_factory():
    def factory(handler) -> OmdClient:
        return OmdClient(make_settings(), transport=httpx.MockTransport(handler))

    return factory
