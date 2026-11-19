from datetime import date
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ReportPeriod(BaseModel):
    start_date: date
    end_date: date


class DashboardOverviewResponse(BaseModel):
    period: ReportPeriod
    revenue: Decimal = Field(description="Receita de compras confirmadas/concluídas com pagamento aprovado.")
    gross_profit: Decimal | None = Field(
        description="Receita menos custo registrado; null quando existir compra sem custo informado."
    )
    profit_data_complete: bool
    purchases_without_cost: int
    sales_count: int = Field(description="Quantidade de transações, não quantidade de passageiros.")
    units_sold: int
    average_ticket: Decimal
    active_clients: int
    new_clients: int


class RevenuePoint(BaseModel):
    period: date
    revenue: Decimal
    gross_profit: Decimal | None
    purchases_without_cost: int


class RevenueSeriesResponse(BaseModel):
    period: ReportPeriod
    group_by: str
    items: list[RevenuePoint]


class SalesPoint(BaseModel):
    period: date
    sales_count: int
    units_sold: int


class SalesSeriesResponse(BaseModel):
    period: ReportPeriod
    group_by: str
    items: list[SalesPoint]


class TopDestinationItem(BaseModel):
    destination_id: UUID
    destination_name: str
    country: str
    sales_count: int
    units_sold: int
    revenue: Decimal


class TopDestinationsResponse(BaseModel):
    period: ReportPeriod
    items: list[TopDestinationItem]


class TopPackageItem(BaseModel):
    package_id: UUID
    title: str
    origin: str
    destination: str
    sales_count: int
    units_sold: int
    revenue: Decimal
    total_seats: int
    available_seats: int
    occupancy_rate: Decimal


class TopPackagesResponse(BaseModel):
    period: ReportPeriod
    items: list[TopPackageItem]
