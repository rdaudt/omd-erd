from dataclasses import dataclass
from types import SimpleNamespace

import pytest


@dataclass
class Page:
    entities: list[object]
    after: str | None = None


def entity(entity_id: str, name: str, fqn: str):
    # Generated OpenMetadata fields are Pydantic RootModels, whose values live in .root.
    return SimpleNamespace(
        id=SimpleNamespace(root=entity_id),
        name=SimpleNamespace(root=name),
        fullyQualifiedName=SimpleNamespace(root=fqn),
    )


class FakeReader:
    def __init__(self):
        self.pages = {}
        self.parents = {}
        self.calls = []

    def add_pages(self, entity_name: str, pages: list[Page], **filters: str):
        self.pages[(entity_name, tuple(sorted(filters.items())))] = pages

    def add_parent(self, entity_name: str, parent_id: str, parent: object):
        self.parents[(entity_name, parent_id)] = parent

    def get_by_id(self, *, entity, entity_id: str, fields: list[str]):
        self.calls.append(SimpleNamespace(method="get_by_id", entity=entity, entity_id=entity_id, fields=fields))
        return self.parents.get((entity.__name__, entity_id))

    def list_entities(self, *, entity, fields: list[str], params: dict[str, str | int]):
        self.calls.append(SimpleNamespace(method="list_entities", entity=entity, fields=fields, params=params))
        filters = tuple(sorted((key, value) for key, value in params.items() if key not in {"after", "limit"}))
        pages = self.pages[(entity.__name__, filters)]
        index = 0 if "after" not in params else 1
        return pages[index]


@pytest.fixture
def fake_reader():
    return FakeReader()
