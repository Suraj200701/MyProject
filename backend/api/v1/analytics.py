"""Lead Intelligence analytics endpoints — the richer set of aggregates
behind `src/app/dashboard/intelligence/page.tsx` (top industries, top
cities, lead quality bands, provider performance, business summary). All
numbers are computed with real aggregate SQL queries scoped to the caller's
current organization."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_current_organization, get_current_user
from database.session import get_db
from models.organization import Organization
from models.user import User
from schemas.analytics import (
    BusinessSummaryOut,
    CityPoint,
    LeadQualityBand,
    NamedValuePoint,
    ProviderPerformancePoint,
)
from services import analytics_service

router = APIRouter(prefix="/analytics", tags=["Analytics"])


@router.get("/top-industries", response_model=list[NamedValuePoint])
async def get_top_industries(
    user: User = Depends(get_current_user),
    organization: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
):
    return await analytics_service.get_industry_distribution(db, organization.id)


@router.get("/top-cities", response_model=list[CityPoint])
async def get_top_cities(
    user: User = Depends(get_current_user),
    organization: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
):
    return await analytics_service.get_top_cities(db, organization.id)


@router.get("/lead-quality", response_model=list[LeadQualityBand])
async def get_lead_quality(
    user: User = Depends(get_current_user),
    organization: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
):
    return await analytics_service.get_lead_quality_bands(db, organization.id)


@router.get("/provider-performance", response_model=list[ProviderPerformancePoint])
async def get_provider_performance(
    user: User = Depends(get_current_user),
    organization: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
):
    return await analytics_service.get_provider_performance(db, organization.id)


@router.get("/business-summary", response_model=BusinessSummaryOut)
async def get_business_summary(
    user: User = Depends(get_current_user),
    organization: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
):
    return await analytics_service.get_business_summary(db, organization.id)
