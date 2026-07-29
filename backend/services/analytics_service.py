"""Aggregate SQL queries backing the Dashboard and Lead Intelligence pages.

Every function is scoped to a single organization (except provider catalog
data, which is global — `api_providers` has no `organization_id`) and
computes its numbers with real COUNT/GROUP BY/date_trunc queries against the
live database. On a freshly-seeded org with zero rows these all degrade to
zeros/empty lists rather than raising.
"""

from calendar import month_abbr
from datetime import UTC, date, datetime, timedelta
from uuid import UUID

from sqlalchemy import and_, case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.billing import CreditWallet, Subscription, SubscriptionPlan
from models.enums import ExportFormat, LeadStatus, SubscriptionStatus
from models.lead import Company, Lead
from models.search import ApiProvider, Export, Search
from schemas.analytics import (
    BusinessSummaryOut,
    CityPoint,
    CountryPoint,
    DashboardStatsOut,
    DayPoint,
    ExportTrendPoint,
    LeadQualityBand,
    MonthlyTrendPoint,
    NamedValuePoint,
    ProviderPerformancePoint,
    ProviderUsagePoint,
)

_QUALITY_BANDS = [
    ("excellent", "Excellent (85+)", 85, 101),
    ("good", "Good (70-84)", 70, 85),
    ("fair", "Fair (50-69)", 50, 70),
    ("weak", "Weak (<50)", 0, 50),
]


def _enum_value(v: object) -> str:
    return v.value if hasattr(v, "value") else str(v)


def _last_n_months(n: int) -> list[date]:
    """Returns the first-of-month date for each of the last `n` months,
    oldest first, ending with the current month."""
    first_of_this_month = datetime.now(UTC).date().replace(day=1)
    months: list[date] = []
    cursor = first_of_this_month
    for _ in range(n):
        months.append(cursor)
        prev_month = cursor.month - 1 or 12
        prev_year = cursor.year - 1 if cursor.month == 1 else cursor.year
        cursor = cursor.replace(year=prev_year, month=prev_month)
    return list(reversed(months))


def _as_utc_datetime(d: date) -> datetime:
    return datetime(d.year, d.month, d.day, tzinfo=UTC)


async def get_dashboard_stats(db: AsyncSession, organization_id: UUID) -> DashboardStatsOut:
    total_leads = (
        await db.execute(select(func.count(Lead.id)).where(Lead.organization_id == organization_id))
    ).scalar_one() or 0

    today_start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    today_leads = (
        await db.execute(
            select(func.count(Lead.id)).where(
                Lead.organization_id == organization_id, Lead.created_at >= today_start
            )
        )
    ).scalar_one() or 0

    converted = (
        await db.execute(
            select(func.count(Lead.id)).where(
                Lead.organization_id == organization_id, Lead.status == LeadStatus.CONVERTED
            )
        )
    ).scalar_one() or 0
    conversion_rate = round((converted / total_leads) * 100, 1) if total_leads else 0.0

    avg_score = (
        await db.execute(select(func.avg(Lead.lead_score)).where(Lead.organization_id == organization_id))
    ).scalar_one()
    avg_lead_score = round(float(avg_score), 1) if avg_score is not None else 0.0

    search_count = (
        await db.execute(select(func.count(Search.id)).where(Search.organization_id == organization_id))
    ).scalar_one() or 0

    credits_remaining = (
        await db.execute(select(CreditWallet.balance).where(CreditWallet.organization_id == organization_id))
    ).scalar_one_or_none() or 0

    credits_total = (
        await db.execute(
            select(SubscriptionPlan.credits_included)
            .join(Subscription, Subscription.plan_id == SubscriptionPlan.id)
            .where(
                Subscription.organization_id == organization_id,
                Subscription.status == SubscriptionStatus.ACTIVE,
            )
        )
    ).scalar_one_or_none() or 0

    return DashboardStatsOut(
        total_leads=total_leads,
        today_leads=today_leads,
        conversion_rate=conversion_rate,
        avg_lead_score=avg_lead_score,
        search_count=search_count,
        credits_remaining=credits_remaining,
        credits_total=credits_total,
    )


async def get_lead_growth(db: AsyncSession, organization_id: UUID) -> list[MonthlyTrendPoint]:
    months = _last_n_months(6)
    start = _as_utc_datetime(months[0])
    month_expr = func.date_trunc("month", Lead.created_at)

    stmt = (
        select(
            month_expr.label("month"),
            func.count(Lead.id),
            func.sum(case((Lead.status == LeadStatus.CONVERTED, 1), else_=0)),
        )
        .where(Lead.organization_id == organization_id, Lead.created_at >= start)
        .group_by(month_expr)
    )
    rows = (await db.execute(stmt)).all()
    buckets = {(r[0].year, r[0].month): (r[1] or 0, r[2] or 0) for r in rows}

    return [
        MonthlyTrendPoint(
            month=month_abbr[m.month],
            leads=buckets.get((m.year, m.month), (0, 0))[0],
            converted=buckets.get((m.year, m.month), (0, 0))[1],
        )
        for m in months
    ]


async def get_industry_distribution(db: AsyncSession, organization_id: UUID) -> list[NamedValuePoint]:
    stmt = (
        select(Company.industry, func.count(Lead.id))
        .join(Lead, Lead.company_id == Company.id)
        .where(Lead.organization_id == organization_id, Company.industry.is_not(None))
        .group_by(Company.industry)
        .order_by(func.count(Lead.id).desc())
    )
    rows = (await db.execute(stmt)).all()
    return [NamedValuePoint(name=r[0], value=r[1]) for r in rows]


async def get_country_analytics(db: AsyncSession, organization_id: UUID) -> list[CountryPoint]:
    stmt = (
        select(Company.country, func.count(Lead.id))
        .join(Lead, Lead.company_id == Company.id)
        .where(Lead.organization_id == organization_id, Company.country.is_not(None))
        .group_by(Company.country)
        .order_by(func.count(Lead.id).desc())
    )
    rows = (await db.execute(stmt)).all()
    return [CountryPoint(country=r[0], leads=r[1]) for r in rows]


async def get_search_analytics(db: AsyncSession, organization_id: UUID) -> list[DayPoint]:
    today = datetime.now(UTC).date()
    days = [today - timedelta(days=i) for i in range(6, -1, -1)]
    start = _as_utc_datetime(days[0])
    day_expr = func.date_trunc("day", Search.created_at)

    stmt = (
        select(day_expr.label("day"), func.count(Search.id))
        .where(Search.organization_id == organization_id, Search.created_at >= start)
        .group_by(day_expr)
    )
    rows = (await db.execute(stmt)).all()
    counts = {r[0].date(): r[1] or 0 for r in rows}

    return [DayPoint(day=d.strftime("%a"), searches=counts.get(d, 0)) for d in days]


async def get_api_usage(db: AsyncSession) -> list[ProviderUsagePoint]:
    stmt = select(ApiProvider.name, ApiProvider.usage_count, ApiProvider.usage_limit).order_by(ApiProvider.name)
    rows = (await db.execute(stmt)).all()
    return [ProviderUsagePoint(name=r[0], usage=r[1], limit=r[2]) for r in rows]


async def get_export_analytics(db: AsyncSession, organization_id: UUID) -> list[ExportTrendPoint]:
    months = _last_n_months(6)
    start = _as_utc_datetime(months[0])
    month_expr = func.date_trunc("month", Export.created_at)

    stmt = (
        select(month_expr.label("month"), Export.format, func.count(Export.id))
        .where(Export.organization_id == organization_id, Export.created_at >= start)
        .group_by(month_expr, Export.format)
    )
    rows = (await db.execute(stmt)).all()

    buckets: dict[tuple[int, int], dict[str, int]] = {}
    for month_dt, fmt, cnt in rows:
        key = (month_dt.year, month_dt.month)
        buckets.setdefault(key, {})[_enum_value(fmt)] = cnt or 0

    result = []
    for m in months:
        bucket = buckets.get((m.year, m.month), {})
        result.append(
            ExportTrendPoint(
                month=month_abbr[m.month],
                csv=bucket.get(ExportFormat.CSV.value, 0),
                excel=bucket.get(ExportFormat.EXCEL.value, 0),
                pdf=bucket.get(ExportFormat.PDF.value, 0),
            )
        )
    return result


async def get_top_cities(db: AsyncSession, organization_id: UUID, limit: int = 8) -> list[CityPoint]:
    stmt = (
        select(Company.city, func.min(Company.country), func.count(Lead.id))
        .join(Lead, Lead.company_id == Company.id)
        .where(Lead.organization_id == organization_id, Company.city.is_not(None))
        .group_by(Company.city)
        .order_by(func.count(Lead.id).desc())
        .limit(limit)
    )
    rows = (await db.execute(stmt)).all()
    return [CityPoint(city=r[0], country=r[1], leads=r[2]) for r in rows]


async def get_lead_quality_bands(db: AsyncSession, organization_id: UUID) -> list[LeadQualityBand]:
    total = (
        await db.execute(select(func.count(Lead.id)).where(Lead.organization_id == organization_id))
    ).scalar_one() or 0

    band_exprs = [
        func.sum(case((and_(Lead.lead_score >= lo, Lead.lead_score < hi), 1), else_=0)).label(band_id)
        for band_id, _label, lo, hi in _QUALITY_BANDS
    ]
    stmt = select(*band_exprs).where(Lead.organization_id == organization_id)
    row = (await db.execute(stmt)).one()

    result = []
    for (band_id, label, lo, hi), count in zip(_QUALITY_BANDS, row, strict=True):
        count = count or 0
        pct = round((count / total) * 100, 1) if total else 0.0
        result.append(
            LeadQualityBand(id=band_id, label=label, min_score=lo, max_score=hi, count=count, percentage=pct)
        )
    return result


async def get_provider_performance(db: AsyncSession, organization_id: UUID) -> list[ProviderPerformancePoint]:
    leads_contributed = func.count(Lead.id).label("leads_contributed")
    stmt = (
        select(
            ApiProvider.id,
            ApiProvider.name,
            ApiProvider.category,
            ApiProvider.status,
            ApiProvider.usage_count,
            ApiProvider.usage_limit,
            leads_contributed,
        )
        .outerjoin(
            Lead,
            and_(Lead.provider_id == ApiProvider.id, Lead.organization_id == organization_id),
        )
        .group_by(ApiProvider.id)
        .order_by(leads_contributed.desc())
    )
    rows = (await db.execute(stmt)).all()
    return [
        ProviderPerformancePoint(
            provider_id=r[0],
            name=r[1],
            category=_enum_value(r[2]),
            status=_enum_value(r[3]),
            usage=r[4],
            usage_limit=r[5],
            leads_contributed=r[6] or 0,
        )
        for r in rows
    ]


async def get_business_summary(db: AsyncSession, organization_id: UUID) -> BusinessSummaryOut:
    company_type_row = (
        await db.execute(
            select(Company.company_type, func.count(Lead.id))
            .join(Lead, Lead.company_id == Company.id)
            .where(Lead.organization_id == organization_id, Company.company_type.is_not(None))
            .group_by(Company.company_type)
            .order_by(func.count(Lead.id).desc())
            .limit(1)
        )
    ).first()

    provider_row = (
        await db.execute(
            select(ApiProvider.name, func.count(Lead.id).label("cnt"))
            .join(Lead, and_(Lead.provider_id == ApiProvider.id, Lead.organization_id == organization_id))
            .group_by(ApiProvider.id, ApiProvider.name)
            .order_by(func.count(Lead.id).desc())
            .limit(1)
        )
    ).first()

    total_companies = (
        await db.execute(
            select(func.count(func.distinct(Lead.company_id))).where(Lead.organization_id == organization_id)
        )
    ).scalar_one() or 0

    return BusinessSummaryOut(
        top_company_type=company_type_row[0] if company_type_row else None,
        top_company_type_count=company_type_row[1] if company_type_row else 0,
        top_provider_name=provider_row[0] if provider_row else None,
        top_provider_lead_count=provider_row[1] if provider_row else 0,
        total_companies=total_companies,
    )
