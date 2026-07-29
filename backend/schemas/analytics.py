"""Pydantic response models for the Dashboard and Lead Intelligence
analytics endpoints. Field names intentionally mirror the shapes the
frontend currently reads from `src/lib/mock-data.ts` (snake_case, per this
backend's existing schema convention) so wiring up the real endpoints later
is a small, mechanical change."""

import uuid

from pydantic import BaseModel


class DashboardStatsOut(BaseModel):
    total_leads: int
    today_leads: int
    conversion_rate: float
    avg_lead_score: float
    search_count: int
    credits_remaining: int
    credits_total: int


class MonthlyTrendPoint(BaseModel):
    """One point on the lead-growth chart: `leadGrowthData`."""

    month: str
    leads: int
    converted: int


class NamedValuePoint(BaseModel):
    """Generic name/value pair used for industry distribution etc."""

    name: str
    value: int


class CountryPoint(BaseModel):
    country: str
    leads: int


class DayPoint(BaseModel):
    """One point on the search-analytics chart: `searchAnalytics`."""

    day: str
    searches: int


class ProviderUsagePoint(BaseModel):
    name: str
    usage: int
    limit: int


class ExportTrendPoint(BaseModel):
    month: str
    csv: int
    excel: int
    pdf: int


class CityPoint(BaseModel):
    city: str
    country: str | None = None
    leads: int


class LeadQualityBand(BaseModel):
    id: str
    label: str
    min_score: int
    max_score: int
    count: int
    percentage: float


class ProviderPerformancePoint(BaseModel):
    provider_id: uuid.UUID
    name: str
    category: str
    status: str
    usage: int
    usage_limit: int
    leads_contributed: int


class BusinessSummaryOut(BaseModel):
    """Backs the "Business Analytics" card on the Lead Intelligence page."""

    top_company_type: str | None = None
    top_company_type_count: int = 0
    top_provider_name: str | None = None
    top_provider_lead_count: int = 0
    total_companies: int = 0
