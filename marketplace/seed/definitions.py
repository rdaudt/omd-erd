"""What the seed creates in OMD. Names are fictional; tables are the existing AdventureWorks tables."""
from dataclasses import dataclass
from typing import Literal

AW = "MSSQL Desktop.AdventureWorks2019"
DW = "MSSQL Desktop.AdventureWorksDW2019"

ENTRA_PROPERTY = "entraGroup"
SENSITIVITY_CLASSIFICATION = "Sensitivity"


@dataclass(frozen=True)
class UserDef:
    name: str
    display_name: str

    @property
    def email(self) -> str:
        return f"{self.name}@example.com"


@dataclass(frozen=True)
class TeamDef:
    name: str
    display_name: str


@dataclass(frozen=True)
class ProductDef:
    name: str
    display_name: str
    description: str
    domain: str
    owner: str  # user name
    steward: str  # user name
    certification: Literal["Gold", "Silver", "Bronze"]
    entra_group: str
    tables: list[str]
    sensitivity_tag: Literal["Public", "Internal", "Confidential"] = "Public"  # tag under the Sensitivity classification


USERS = [
    UserDef("maria.chen", "Maria Chen"),
    UserDef("raj.patel", "Raj Patel"),
    UserDef("lee.park", "Lee Park"),
    UserDef("sofia.alvarez", "Sofia Alvarez"),
    UserDef("kenji.tanaka", "Kenji Tanaka"),
    UserDef("priya.nair", "Priya Nair"),
]

TEAMS = [
    TeamDef("sales-analytics", "Sales Analytics"),
    TeamDef("procurement", "Procurement"),
    TeamDef("people-analytics", "People Analytics"),
    TeamDef("product-data", "Product Data"),
]

DOMAINS = ["Sales", "Purchasing", "HR", "Production"]


def _group(domain: str, name: str) -> str:
    return f"GRP-DW-{domain.upper()}-{name.upper()}-READ"


PRODUCTS = [
    ProductDef(
        "internet-sales-mart", "Internet Sales Mart",
        "Star schema for online sales: orders, customers, products, dates and territories. Refreshed nightly.",
        "Sales", "maria.chen", "lee.park", "Gold", _group("Sales", "internet-sales-mart"),
        [f"{DW}.dbo.FactInternetSales", f"{DW}.dbo.DimCustomer", f"{DW}.dbo.DimProduct",
         f"{DW}.dbo.DimDate", f"{DW}.dbo.DimSalesTerritory"],
        sensitivity_tag="Confidential",
    ),
    ProductDef(
        "reseller-sales-mart", "Reseller Sales Mart",
        "Sales made through resellers, with reseller, product and territory dimensions.",
        "Sales", "maria.chen", "lee.park", "Silver", _group("Sales", "reseller-sales-mart"),
        [f"{DW}.dbo.FactResellerSales", f"{DW}.dbo.DimReseller", f"{DW}.dbo.DimProduct",
         f"{DW}.dbo.DimDate", f"{DW}.dbo.DimSalesTerritory"],
        sensitivity_tag="Internal",
    ),
    ProductDef(
        "sales-orders", "Sales Orders (Operational)",
        "Operational sales orders with line items, customers, territories and special offers.",
        "Sales", "sofia.alvarez", "lee.park", "Silver", _group("Sales", "sales-orders"),
        [f"{AW}.Sales.SalesOrderHeader", f"{AW}.Sales.SalesOrderDetail", f"{AW}.Sales.Customer",
         f"{AW}.Sales.SalesTerritory", f"{AW}.Sales.SpecialOffer"],
        sensitivity_tag="Internal",
    ),
    ProductDef(
        "purchasing-spend", "Purchasing Spend",
        "Purchase orders and vendor relationships, for spend and supplier analysis.",
        "Purchasing", "raj.patel", "kenji.tanaka", "Gold", _group("Purchasing", "purchasing-spend"),
        [f"{AW}.Purchasing.PurchaseOrderHeader", f"{AW}.Purchasing.PurchaseOrderDetail",
         f"{AW}.Purchasing.Vendor", f"{AW}.Purchasing.ProductVendor", f"{AW}.Purchasing.ShipMethod"],
        sensitivity_tag="Internal",
    ),
    ProductDef(
        "employee-directory", "Employee Directory",
        "Employees, departments, shifts and department history.",
        "HR", "priya.nair", "kenji.tanaka", "Bronze", _group("HR", "employee-directory"),
        [f"{AW}.HumanResources.Employee", f"{AW}.HumanResources.Department",
         f"{AW}.HumanResources.EmployeeDepartmentHistory", f"{AW}.HumanResources.Shift",
         f"{AW}.Person.Person"],
        sensitivity_tag="Confidential",
    ),
    ProductDef(
        "workforce-compensation", "Workforce Compensation",
        "Employee pay history joined to departments, for compensation analysis. Restricted use.",
        "HR", "priya.nair", "kenji.tanaka", "Silver", _group("HR", "workforce-compensation"),
        [f"{AW}.HumanResources.EmployeePayHistory", f"{AW}.HumanResources.Employee",
         f"{AW}.HumanResources.Department"],
        sensitivity_tag="Confidential",
    ),
    ProductDef(
        "product-catalog", "Product Catalog",
        "Products with categories, subcategories, models and descriptions.",
        "Production", "lee.park", "maria.chen", "Gold", _group("Production", "product-catalog"),
        [f"{AW}.Production.Product", f"{AW}.Production.ProductCategory",
         f"{AW}.Production.ProductSubcategory", f"{AW}.Production.ProductModel",
         f"{AW}.Production.ProductDescription"],
    ),
]


@dataclass(frozen=True)
class TestDef:
    table: str
    name: str
    definition: str
    parameters: list[dict]
    outcome: Literal["Success", "Failed"]


# Two table-level tests per table. Which ones "fail" is chosen so product quality scores spread across buckets.
TEST_KINDS = [
    ("row_count_positive", "tableRowCountToBeBetween", [{"name": "minValue", "value": "1"}]),
    ("column_count_in_range", "tableColumnCountToBeBetween",
     [{"name": "minColValue", "value": "1"}, {"name": "maxColValue", "value": "200"}]),
]

FAILING: dict[str, list[str]] = {
    f"{DW}.dbo.FactInternetSales": ["column_count_in_range"],
    f"{DW}.dbo.DimReseller": ["column_count_in_range"],
    f"{DW}.dbo.FactResellerSales": ["row_count_positive"],
    f"{AW}.Sales.SalesOrderDetail": ["row_count_positive", "column_count_in_range"],
    f"{AW}.HumanResources.Shift": ["row_count_positive"],
    f"{AW}.HumanResources.EmployeeDepartmentHistory": ["row_count_positive"],
    f"{AW}.Person.Person": ["row_count_positive", "column_count_in_range"],
    f"{AW}.HumanResources.EmployeePayHistory": ["row_count_positive"],
}


def build_tests() -> list[TestDef]:
    tables = sorted({t for p in PRODUCTS for t in p.tables})
    return [
        TestDef(t, name, definition, params, "Failed" if name in FAILING.get(t, []) else "Success")
        for t in tables for name, definition, params in TEST_KINDS
    ]


# (upstream, downstream) table pairs
LINEAGE: list[tuple[str, str]] = [
    (f"{DW}.dbo.DimCustomer", f"{DW}.dbo.FactInternetSales"),
    (f"{DW}.dbo.DimProduct", f"{DW}.dbo.FactInternetSales"),
    (f"{DW}.dbo.DimDate", f"{DW}.dbo.FactInternetSales"),
    (f"{DW}.dbo.DimSalesTerritory", f"{DW}.dbo.FactInternetSales"),
    (f"{DW}.dbo.DimReseller", f"{DW}.dbo.FactResellerSales"),
    (f"{DW}.dbo.DimProduct", f"{DW}.dbo.FactResellerSales"),
    (f"{AW}.Sales.SalesOrderHeader", f"{DW}.dbo.FactInternetSales"),
    (f"{AW}.Sales.Customer", f"{AW}.Sales.SalesOrderHeader"),
    (f"{AW}.Sales.SalesTerritory", f"{AW}.Sales.SalesOrderHeader"),
    (f"{AW}.Sales.SalesOrderHeader", f"{AW}.Sales.SalesOrderDetail"),
    (f"{AW}.Purchasing.Vendor", f"{AW}.Purchasing.PurchaseOrderHeader"),
    (f"{AW}.Purchasing.PurchaseOrderHeader", f"{AW}.Purchasing.PurchaseOrderDetail"),
    (f"{AW}.Purchasing.ProductVendor", f"{AW}.Purchasing.PurchaseOrderDetail"),
    (f"{AW}.HumanResources.Department", f"{AW}.HumanResources.EmployeeDepartmentHistory"),
    (f"{AW}.HumanResources.Employee", f"{AW}.HumanResources.EmployeePayHistory"),
    (f"{AW}.Production.ProductCategory", f"{AW}.Production.ProductSubcategory"),
    (f"{AW}.Production.ProductSubcategory", f"{AW}.Production.Product"),
]
