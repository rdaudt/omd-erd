export type CatalogItem = {
  id: string;
  name: string;
  fullyQualifiedName: string;
};

export type ColumnModel = {
  name: string;
  dataType: string;
  nullable: boolean;
  primaryKey: boolean;
  foreignKey: boolean;
  description: string | null;
};

export type EntityType = 'table' | 'view';
export type EntityDisplayMode = 'tables' | 'views' | 'both';

export type TableModel = {
  id: string;
  name: string;
  fullyQualifiedName: string;
  entityType: EntityType;
  description: string | null;
  owner: string | null;
  tags: string[];
  tier: string | null;
  columns: ColumnModel[];
};

export type RelationshipModel = {
  id: string;
  sourceTableId: string;
  sourceColumn: string;
  targetTableId: string;
  targetColumn: string;
};

export type GraphResponse = {
  source: 'live' | 'sample';
  schema: CatalogItem;
  tables: TableModel[];
  relationships: RelationshipModel[];
  notices: string[];
  warnings: string[];
};
