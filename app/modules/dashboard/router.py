from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, Query

from app.api.dependencies.permissions import require_roles
from app.domains.shared.enums import UserRole
from app.modules.dashboard.dependencies import get_dashboard_service
from app.modules.dashboard.schemas import (
    DashboardOverviewResponse,
    RevenueSeriesResponse,
    SalesSeriesResponse,
    TopDestinationsResponse,
    TopPackagesResponse,
)
from app.modules.dashboard.service import DashboardService

router = APIRouter(
    prefix="/admin/dashboard",
    tags=["Admin dashboard"],
    dependencies=[Depends(require_roles(UserRole.ADMIN))],
)


@router.get("/overview", response_model=DashboardOverviewResponse, summary="Resumo do dashboard")
def get_overview(
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    service: DashboardService = Depends(get_dashboard_service),
) -> DashboardOverviewResponse:
    return service.overview(start_date=start_date, end_date=end_date)


@router.get("/revenue", response_model=RevenueSeriesResponse, summary="Série histórica de receita")
def get_revenue(
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    group_by: Literal["day", "month"] = Query(default="month"),
    service: DashboardService = Depends(get_dashboard_service),
) -> RevenueSeriesResponse:
    return service.revenue_series(start_date=start_date, end_date=end_date, group_by=group_by)


@router.get("/sales", response_model=SalesSeriesResponse, summary="Série histórica de vendas")
def get_sales(
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    group_by: Literal["day", "month"] = Query(default="month"),
    service: DashboardService = Depends(get_dashboard_service),
) -> SalesSeriesResponse:
    return service.sales_series(start_date=start_date, end_date=end_date, group_by=group_by)


@router.get(
    "/destinations",
    response_model=TopDestinationsResponse,
    summary="Destinos mais vendidos",
)
def get_top_destinations(
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    limit: int = Query(default=5, ge=1, le=20),
    service: DashboardService = Depends(get_dashboard_service),
) -> TopDestinationsResponse:
    return service.top_destinations(start_date=start_date, end_date=end_date, limit=limit)


@router.get("/packages", response_model=TopPackagesResponse, summary="Pacotes com mais vendas")
def get_top_packages(
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    limit: int = Query(default=10, ge=1, le=20),
    service: DashboardService = Depends(get_dashboard_service),
) -> TopPackagesResponse:
    return service.top_packages(start_date=start_date, end_date=end_date, limit=limit)
