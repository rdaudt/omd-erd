from typing import Literal

from pydantic import BaseModel

Sensitivity = Literal["Public", "Internal", "Confidential"]


class ProductSummary(BaseModel):
    name: str
    display_name: str
    description: str
    domain: str | None
    owners: list[str]
    steward: str | None
    certification: Literal["Gold", "Silver", "Bronze"] | None
    table_count: int
    quality: int | None
    sensitivity: Sensitivity
    entra_group: str | None
    glossary_terms: list[str]
    tags: list[str]


class DatasetRow(BaseModel):
    name: str
    fqn: str
    description: str
    quality: int | None


class TestResultRow(BaseModel):
    table: str
    test: str
    status: str


class LineageGraph(BaseModel):
    nodes: list[str]
    edges: list[tuple[str, str]]


class ProductDetail(ProductSummary):
    datasets: list[DatasetRow]
    tests: list[TestResultRow]
    lineage: LineageGraph
