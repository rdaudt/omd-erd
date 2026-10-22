from typing import Literal

from pydantic import BaseModel, Field


class CatalogItem(BaseModel):
    id: str
    name: str
    fullyQualifiedName: str


class ColumnModel(BaseModel):
    name: str
    dataType: str
    nullable: bool
    primaryKey: bool = False
    foreignKey: bool = False
    description: str | None = None


class TableModel(BaseModel):
    id: str
    name: str
    fullyQualifiedName: str
    entityType: Literal["table", "view"]
    description: str | None = None
    owner: str | None = None
    tags: list[str] = Field(default_factory=list)
    tier: str | None = None
    columns: list[ColumnModel]


class RelationshipModel(BaseModel):
    id: str
    sourceTableId: str
    sourceColumn: str
    targetTableId: str
    targetColumn: str


class GraphResponse(BaseModel):
    source: Literal["live", "sample"]
    schema_: CatalogItem = Field(alias="schema")
    tables: list[TableModel]
    relationships: list[RelationshipModel]
    notices: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    model_config = {"populate_by_name": True}
