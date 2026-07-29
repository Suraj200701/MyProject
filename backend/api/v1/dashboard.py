"""Dashboard summary + trend endpoints backing the main Dashboard page
(`dashboardStats`, `leadGrowthData`, `industryDistribution`,
`countryAnalytics`, `searchAnalytics`, `apiUsageData`, `exportAnalytics` in
`src/lib/mock-data.ts`). All numbers are computed with real aggregate SQL
queries scoped to the caller's current organization."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_current_organization, get_current_user
from database.session import get_db
from models.organization import Organization
from models.user import User
from schemas.analytics import (
    CountryPoint,
    DashboardStatsOut,
    DayPoint,
    ExportTrendPoint,
    MonthlyTrendPoint,
    NamedValuePoint,
    ProviderUsagePoint,
)
from services import analytics_service

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("/stats", response_model=DashboardStatsOut)
async def get_stats(
    user: User = Depends(get_current_user),
    organization: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
):
    return await analytics_service.get_dashboard_stats(db, organization.id)


@router.get("/lead-growth", response_model=list[MonthlyTrendPoint])
async def get_lead_growth(
    user: User = Depends(get_current_user),
    organization: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
):
    return await analytics_service.get_lead_growth(db, organization.id)


@router.get("/industry-distribution", response_model=list[NamedValuePoint])
async def get_industry_distribution(
    user: User = Depends(get_current_user),
    organization: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
):
    return await analytics_service.get_industry_distribution(db, organization.id)


@router.get("/country-analytics", response_model=list[CountryPoint])
async def get_country_analytics(
    user: User = Depends(get_current_user),
    organization: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
):
    return await analytics_service.get_country_analytics(db, organization.id)


@router.get("/search-analytics", response_model=list[DayPoint])
async def get_search_analytics(
    user: User = Depends(get_current_user),
    organization: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
):
    return await analytics_service.get_search_analytics(db, organization.id)


@router.get("/api-usage", response_model=list[ProviderUsagePoint])
async def get_api_usage(
    user: User = Depends(get_current_user),
    organization: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
):
    return await analytics_service.get_api_usage(db)


@router.get("/export-analytics", response_model=list[ExportTrendPoint])
async def get_export_analytics(
    user: User = Depends(get_current_user),
    organization: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
):
    return await analytics_service.get_export_analytics(db, organization.id)
