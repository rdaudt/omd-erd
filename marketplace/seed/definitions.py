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
    sensitivity_tag: str | None = None  # a tag under the Sensitivity classification, e.g. "Internal"


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
    ),
    ProductDef(
        "reseller-sales-mart", "Reseller Sales Mart",
        "Sales made through resellers, with reseller, product and territory dimensions.",
        "Sales", "maria.chen", "lee.park", "Silver", _group("Sales", "reseller-sales-mart"),
        [f"{DW}.dbo.FactResellerSales", f"{DW}.dbo.DimReseller", f"{DW}.dbo.DimProduct",
         f"{DW}.dbo.DimDate", f"{DW}.dbo.DimSalesTerritory"],
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
    ),
    ProductDef(
        "workforce-compensation", "Workforce Compensation",
        "Employee pay history joined to departments, for compensation analysis. Restricted use.",
        "HR", "priya.nair", "kenji.tanaka", "Silver", _group("HR", "workforce-compensation"),
        [f"{AW}.HumanResources.EmployeePayHistory", f"{AW}.HumanResources.Employee",
         f"{AW}.HumanResources.Department"],
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
