"""Turns database state into `Dataset` values for the Export Center.

Split from `export_service.py` on purpose: this module decides *what* goes in an
export, the service decides *when and how* it is produced, and
`services/exporters/` decides what the bytes look like.

Sync/async duality
------------------
The request path runs on the async engine; the Celery worker that handles large
exports runs on the sync engine (`database/sync_session.py`). Rather than write
each query twice, this module is factored so the only thing that differs between
the two is the `execute` call:

  * `*_statement()` returns a plain SQLAlchemy `Select` — valid on both engines.
  * `lead_row()` / `assemble_*` are pure functions over already-fetched objects.
  * `load_*_dataset()` (async) and `load_*_dataset_sync()` are thin wrappers that
    fetch and then call the same assembler.

Dashboard and analytics reports are built from `analytics_service`, which is
async-only. That is deliberate and safe: those reports are aggregates of a few
dozen rows, so they never cross the async threshold and are always generated
inline on the request path. `supports_background()` encodes that rule.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Select, func, select
from sqlalchemy.orm import joinedload

from models.enums import ExportResource
from models.lead import Company, Lead
from models.search import ApiProvider, Search
from services.exporters.dataset import Column, Dataset, ReportSection

# --- Column catalogues ----------------------------------------------------

# The full set of lead fields an export can contain. `key` is the API-facing
# identifier; `label` is the header the recipient sees.
#
# The first eight deliberately match the frontend wizard's EXPORT_FIELDS list
# (src/components/export/types.ts) so its checkbox state maps straight onto this
# catalogue — see `resolve_columns`, which accepts either form.
LEAD_COLUMNS: tuple[Column, ...] = (
    Column("company", "Company", 32),
    Column("industry", "Industry", 20),
    Column("city", "City", 16),
    Column("contact_name", "Contact", 20),
    Column("email", "Email", 28),
    Column("phone", "Phone", 16),
    Column("lead_score", "Lead Score", 11),
    Column("status", "Status", 12),
    Column("country", "Country", 14),
    Column("company_type", "Company Type", 18),
    Column("revenue_band", "Revenue Band", 16),
    Column("website", "Website", 28),
    Column("gst_number", "GST Number", 18),
    Column("rating", "Rating", 9),
    Column("tags", "Tags", 22),
    Column("provider", "Source", 20),
    Column("lat", "Latitude", 11),
    Column("lng", "Longitude", 11),
    Column("ai_summary", "AI Summary", 48),
    Column("created_at", "Created At", 20),
)

# Applied when the caller does not name any columns. Narrower than the full
# catalogue: a default export that includes ai_summary and coordinates is
# unwieldy in a spreadsheet, and those are opt-in rather than opt-out.
DEFAULT_LEAD_COLUMN_KEYS: tuple[str, ...] = (
    "company", "industry", "city", "country", "contact_name", "email",
    "phone", "lead_score", "status", "website", "gst_number", "provider", "created_at",
)


def _normalize_token(value: str) -> str:
    """Collapses a key or label to a comparable token.

    "Lead Score", "lead_score" and "leadScore" all reduce to "leadscore", which
    is what lets the frontend send its display labels unchanged.
    """
    return "".join(ch for ch in str(value).lower() if ch.isalnum())


def resolve_columns(catalogue: tuple[Column, ...], requested: list[str] | None) -> list[Column]:
    """Selects and orders columns from `catalogue`.

    Accepts API keys ("lead_score") or display labels ("Lead Score"), matched
    case- and separator-insensitively. Unknown names are ignored rather than
    rejected: a stray column in a saved export preset should not fail the export.
    Order follows the caller's request, so column order is controllable.
    """
    if not requested:
        default = {k: None for k in DEFAULT_LEAD_COLUMN_KEYS}
        return [c for c in catalogue if c.key in default] or list(catalogue)

    by_token: dict[str, Column] = {}
    for column in catalogue:
        by_token.setdefault(_normalize_token(column.key), column)
        by_token.setdefault(_normalize_token(column.label), column)

    resolved: list[Column] = []
    seen: set[str] = set()
    for name in requested:
        column = by_token.get(_normalize_token(name))
        if column is not None and column.key not in seen:
            resolved.append(column)
            seen.add(column.key)

    # Every requested name was unrecognized — fall back rather than produce a
    # file with a header and no columns.
    return resolved or resolve_columns(catalogue, None)


def unknown_column_names(catalogue: tuple[Column, ...], requested: list[str] | None) -> list[str]:
    """Requested names that matched nothing. Surfaced as a warning, not an error."""
    if not requested:
        return []
    known = {_normalize_token(c.key) for c in catalogue} | {_normalize_token(c.label) for c in catalogue}
    return [n for n in requested if _normalize_token(n) not in known]


# --- Lead statements ------------------------------------------------------


def leads_statement(
    organization_id: uuid.UUID,
    *,
    lead_ids: list[uuid.UUID] | None = None,
    filters: dict | None = None,
) -> Select:
    """Statement for a lead export, always scoped to one organization.

    Filter semantics intentionally mirror `LeadRepository.list_for_org`, so
    "export this filtered view" produces exactly the rows `GET /leads` shows for
    the same query string. Reimplementing the predicates differently here is how
    an export silently disagrees with the table it came from.
    """
    stmt = (
        select(Lead)
        .join(Company, Lead.company_id == Company.id)
        # `joinedload` is required, not an optimization: `lead_row` reads
        # `lead.company`, and on the async engine a lazy load there raises
        # MissingGreenlet. The explicit join above is for filtering/sorting on
        # company columns; this is what actually populates the relationship.
        .options(joinedload(Lead.company))
        .where(Lead.organization_id == organization_id)
    )

    if lead_ids:
        stmt = stmt.where(Lead.id.in_(lead_ids))

    filters = filters or {}
    search = filters.get("search")
    industry = filters.get("industry")
    status = filters.get("status")
    country = filters.get("country")
    min_score = filters.get("min_score")
    max_score = filters.get("max_score")
    search_id = filters.get("search_id")

    if search:
        stmt = stmt.where(Company.name.ilike(f"%{str(search).lower()}%"))
    if industry and industry != "all":
        stmt = stmt.where(Company.industry == industry)
    if status and status != "all":
        stmt = stmt.where(Lead.status == status)
    if country and country != "all":
        stmt = stmt.where(Company.country == country)
    if min_score is not None:
        stmt = stmt.where(Lead.lead_score >= min_score)
    if max_score is not None:
        stmt = stmt.where(Lead.lead_score <= max_score)
    if search_id is not None:
        stmt = stmt.where(Lead.search_id == search_id)

    sort_columns = {
        "created_at": Lead.created_at,
        "lead_score": Lead.lead_score,
        "company": Company.name,
    }
    column = sort_columns.get(filters.get("sort_by") or "created_at", Lead.created_at)
    descending = (filters.get("sort_order") or "desc") != "asc"
    # Tie-break on id so paging/streaming a large export is deterministic —
    # without it Postgres may return equal-keyed rows in a different order per
    # chunk and a row can be duplicated or dropped across chunk boundaries.
    stmt = stmt.order_by(column.desc() if descending else column.asc(), Lead.id.asc())
    return stmt


def count_statement(stmt: Select) -> Select:
    """Row-count statement for a data statement, used for the preflight check."""
    return select(func.count()).select_from(stmt.order_by(None).subquery())


def provider_names_statement(provider_ids: set[uuid.UUID]) -> Select:
    return select(ApiProvider.id, ApiProvider.name).where(ApiProvider.id.in_(provider_ids))


# --- Row mapping ----------------------------------------------------------


def lead_row(lead: Lead, provider_names: dict[uuid.UUID, str] | None = None) -> dict[str, Any]:
    """Flattens a Lead + its Company into one export row.

    Mirrors `LeadOut.from_lead`'s flattening so an exported row and the same lead
    in the API carry the same values under the same names.
    """
    company = lead.company
    names = provider_names or {}
    return {
        "company": company.name if company else None,
        "industry": company.industry if company else None,
        "city": company.city if company else None,
        "country": company.country if company else None,
        "company_type": company.company_type if company else None,
        "revenue_band": company.revenue_band if company else None,
        "website": company.website if company else None,
        "gst_number": company.gst_number if company else None,
        "rating": company.rating if company else None,
        "lat": company.lat if company else None,
        "lng": company.lng if company else None,
        "contact_name": lead.contact_name,
        "email": lead.email,
        "phone": lead.phone,
        "lead_score": lead.lead_score,
        # `status` is an enum on the model; export its value, not "LeadStatus.NEW".
        "status": lead.status.value if hasattr(lead.status, "value") else lead.status,
        "tags": list(lead.tags) if lead.tags else [],
        "provider": names.get(lead.provider_id) if lead.provider_id else None,
        "ai_summary": lead.ai_summary,
        "created_at": lead.created_at,
    }


# --- Dataset assembly (pure) ---------------------------------------------


def assemble_leads_dataset(
    *,
    rows: list[dict],
    columns: list[Column],
    organization_name: str,
    scope_label: str,
    filters: dict | None = None,
    truncated_at: int | None = None,
) -> Dataset:
    metadata = {
        "Organization": organization_name,
        "Generated": datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC"),
        "Scope": scope_label,
        "Rows": f"{len(rows):,}",
    }
    applied = _describe_filters(filters)
    if applied:
        metadata["Filters"] = applied
    if truncated_at is not None:
        # Stated in the file itself, not just in the API response: a truncated
        # export that looks complete is how someone works from partial data.
        metadata["Truncated"] = (
            f"Capped at {truncated_at:,} rows by the server's export limit"
        )

    return Dataset(
        title="LeadMaster AI — Leads Export",
        subtitle=f"{len(rows):,} lead(s) · {scope_label}",
        columns=columns,
        rows=rows,
        metadata=metadata,
    )


def assemble_search_results_dataset(
    *,
    rows: list[dict],
    columns: list[Column],
    organization_name: str,
    search: Search,
    truncated_at: int | None = None,
) -> Dataset:
    metadata = {
        "Organization": organization_name,
        "Generated": datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC"),
        "Search query": search.query or "—",
        "Location": search.location or "—",
        "Search run": search.created_at.strftime("%Y-%m-%d %H:%M UTC") if search.created_at else "—",
        "Results recorded": f"{search.results_count:,}",
        "Rows exported": f"{len(rows):,}",
    }
    if truncated_at is not None:
        metadata["Truncated"] = f"Capped at {truncated_at:,} rows by the server's export limit"

    return Dataset(
        title="LeadMaster AI — Search Results",
        subtitle=f'Results for "{search.query}"' if search.query else "Search results",
        columns=columns,
        rows=rows,
        metadata=metadata,
    )


def _describe_filters(filters: dict | None) -> str:
    """Human-readable summary of the filters that produced an export."""
    if not filters:
        return ""
    labels = {
        "search": "name contains",
        "industry": "industry",
        "status": "status",
        "country": "country",
        "min_score": "score ≥",
        "max_score": "score ≤",
        "search_id": "from search",
    }
    parts = []
    for key, label in labels.items():
        value = filters.get(key)
        if value is None or value == "" or value == "all":
            continue
        parts.append(f"{label} {value}")
    return "; ".join(parts)


# --- Async loaders (request path) ----------------------------------------


async def load_leads_dataset(
    db,
    *,
    organization_id: uuid.UUID,
    organization_name: str,
    columns: list[Column],
    scope_label: str,
    lead_ids: list[uuid.UUID] | None = None,
    filters: dict | None = None,
    max_rows: int,
) -> Dataset:
    stmt = leads_statement(organization_id, lead_ids=lead_ids, filters=filters)
    total = (await db.execute(count_statement(stmt))).scalar_one()
    leads = (await db.execute(stmt.limit(max_rows))).unique().scalars().all()
    names = await _load_provider_names(db, leads)
    return assemble_leads_dataset(
        rows=[lead_row(l, names) for l in leads],
        columns=columns,
        organization_name=organization_name,
        scope_label=scope_label,
        filters=filters,
        truncated_at=max_rows if total > max_rows else None,
    )


async def load_search_results_dataset(
    db,
    *,
    organization_id: uuid.UUID,
    organization_name: str,
    search: Search,
    columns: list[Column],
    max_rows: int,
) -> Dataset:
    stmt = leads_statement(organization_id, filters={"search_id": search.id})
    total = (await db.execute(count_statement(stmt))).scalar_one()
    leads = (await db.execute(stmt.limit(max_rows))).unique().scalars().all()
    names = await _load_provider_names(db, leads)
    return assemble_search_results_dataset(
        rows=[lead_row(l, names) for l in leads],
        columns=columns,
        organization_name=organization_name,
        search=search,
        truncated_at=max_rows if total > max_rows else None,
    )


async def _load_provider_names(db, leads) -> dict[uuid.UUID, str]:
    """Batch-resolves provider names.

    One query for the whole page rather than one per lead — `Lead` has no
    `provider` relationship to eager-load, so this is the same approach
    `GET /leads` takes.
    """
    provider_ids = {l.provider_id for l in leads if l.provider_id}
    if not provider_ids:
        return {}
    rows = (await db.execute(provider_names_statement(provider_ids))).all()
    return {row[0]: row[1] for row in rows}


# --- Sync loaders (Celery worker) ---------------------------------------


def load_leads_dataset_sync(
    db,
    *,
    organization_id: uuid.UUID,
    organization_name: str,
    columns: list[Column],
    scope_label: str,
    lead_ids: list[uuid.UUID] | None = None,
    filters: dict | None = None,
    max_rows: int,
) -> Dataset:
    """Sync twin of `load_leads_dataset`, sharing its statement and mapper."""
    stmt = leads_statement(organization_id, lead_ids=lead_ids, filters=filters)
    total = db.execute(count_statement(stmt)).scalar_one()
    leads = db.execute(stmt.limit(max_rows)).unique().scalars().all()
    names = _load_provider_names_sync(db, leads)
    return assemble_leads_dataset(
        rows=[lead_row(l, names) for l in leads],
        columns=columns,
        organization_name=organization_name,
        scope_label=scope_label,
        filters=filters,
        truncated_at=max_rows if total > max_rows else None,
    )


def load_search_results_dataset_sync(
    db,
    *,
    organization_id: uuid.UUID,
    organization_name: str,
    search: Search,
    columns: list[Column],
    max_rows: int,
) -> Dataset:
    stmt = leads_statement(organization_id, filters={"search_id": search.id})
    total = db.execute(count_statement(stmt)).scalar_one()
    leads = db.execute(stmt.limit(max_rows)).unique().scalars().all()
    names = _load_provider_names_sync(db, leads)
    return assemble_search_results_dataset(
        rows=[lead_row(l, names) for l in leads],
        columns=columns,
        organization_name=organization_name,
        search=search,
        truncated_at=max_rows if total > max_rows else None,
    )


def _load_provider_names_sync(db, leads) -> dict[uuid.UUID, str]:
    provider_ids = {l.provider_id for l in leads if l.provider_id}
    if not provider_ids:
        return {}
    return {row[0]: row[1] for row in db.execute(provider_names_statement(provider_ids)).all()}


# --- Reports --------------------------------------------------------------


async def load_dashboard_dataset(db, *, organization_id: uuid.UUID, organization_name: str) -> Dataset:
    """The dashboard, as a report: the same figures the dashboard screen shows.

    Built from `analytics_service` so the report and the UI can never disagree —
    duplicating the aggregate SQL here is how a report starts quietly reporting
    different numbers than the screen it is named after.
    """
    from services import analytics_service

    stats = await analytics_service.get_dashboard_stats(db, organization_id)
    growth = await analytics_service.get_lead_growth(db, organization_id)
    industries = await analytics_service.get_industry_distribution(db, organization_id)
    countries = await analytics_service.get_country_analytics(db, organization_id)
    searches = await analytics_service.get_search_analytics(db, organization_id)
    exports = await analytics_service.get_export_analytics(db, organization_id)

    sections = [
        ReportSection(
            title="Summary",
            columns=[Column("metric", "Metric", 28), Column("value", "Value", 18)],
            rows=[
                {"metric": "Total leads", "value": stats.total_leads},
                {"metric": "Leads added today", "value": stats.today_leads},
                {"metric": "Conversion rate (%)", "value": stats.conversion_rate},
                {"metric": "Average lead score", "value": stats.avg_lead_score},
                {"metric": "Searches run", "value": stats.search_count},
                {"metric": "Credits remaining", "value": stats.credits_remaining},
                {"metric": "Credits in plan", "value": stats.credits_total},
            ],
        ),
        ReportSection(
            title="Lead Growth",
            note="Leads created and converted per month.",
            columns=[Column("month", "Month", 14), Column("leads", "Leads", 12), Column("converted", "Converted", 12)],
            rows=[{"month": p.month, "leads": p.leads, "converted": p.converted} for p in growth],
        ),
        ReportSection(
            title="Industry Distribution",
            columns=[Column("name", "Industry", 30), Column("value", "Leads", 12)],
            rows=[{"name": p.name, "value": p.value} for p in industries],
        ),
        ReportSection(
            title="Country Analytics",
            columns=[Column("country", "Country", 26), Column("leads", "Leads", 12)],
            rows=[{"country": p.country, "leads": p.leads} for p in countries],
        ),
        ReportSection(
            title="Search Activity",
            note="Searches run per day over the recent window.",
            columns=[Column("day", "Day", 16), Column("searches", "Searches", 12)],
            rows=[{"day": p.day, "searches": p.searches} for p in searches],
        ),
        ReportSection(
            title="Export Activity",
            columns=[
                Column("month", "Month", 14), Column("csv", "CSV", 10),
                Column("excel", "Excel", 10), Column("pdf", "PDF", 10),
            ],
            rows=[{"month": p.month, "csv": p.csv, "excel": p.excel, "pdf": p.pdf} for p in exports],
        ),
    ]

    return Dataset(
        title="LeadMaster AI — Dashboard Report",
        subtitle="Snapshot of headline metrics and recent activity",
        sections=sections,
        metadata={
            "Organization": organization_name,
            "Generated": datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC"),
        },
    )


async def load_analytics_dataset(db, *, organization_id: uuid.UUID, organization_name: str) -> Dataset:
    """The deeper analytics cuts: quality bands, geography, provider performance."""
    from services import analytics_service

    industries = await analytics_service.get_industry_distribution(db, organization_id)
    cities = await analytics_service.get_top_cities(db, organization_id)
    quality = await analytics_service.get_lead_quality_bands(db, organization_id)
    providers = await analytics_service.get_provider_performance(db, organization_id)
    summary = await analytics_service.get_business_summary(db, organization_id)

    sections = [
        ReportSection(
            title="Business Summary",
            columns=[Column("metric", "Metric", 30), Column("value", "Value", 26)],
            rows=[
                {"metric": "Top company type", "value": summary.top_company_type or "—"},
                {"metric": "Leads of that type", "value": summary.top_company_type_count},
                {"metric": "Top provider", "value": summary.top_provider_name or "—"},
                {"metric": "Leads from top provider", "value": summary.top_provider_lead_count},
                {"metric": "Companies on record", "value": summary.total_companies},
            ],
        ),
        ReportSection(
            title="Lead Quality Bands",
            note="Distribution of leads across score bands.",
            columns=[
                Column("label", "Band", 20), Column("min_score", "Min Score", 11),
                Column("max_score", "Max Score", 11), Column("count", "Leads", 10),
                Column("percentage", "Share (%)", 11),
            ],
            rows=[
                {
                    "label": b.label, "min_score": b.min_score, "max_score": b.max_score,
                    "count": b.count, "percentage": b.percentage,
                }
                for b in quality
            ],
        ),
        ReportSection(
            title="Top Industries",
            columns=[Column("name", "Industry", 30), Column("value", "Leads", 12)],
            rows=[{"name": p.name, "value": p.value} for p in industries],
        ),
        ReportSection(
            title="Top Cities",
            columns=[Column("city", "City", 24), Column("country", "Country", 20), Column("leads", "Leads", 12)],
            rows=[{"city": p.city, "country": p.country, "leads": p.leads} for p in cities],
        ),
        ReportSection(
            title="Provider Performance",
            note="Usage against quota and how many leads each provider contributed.",
            columns=[
                Column("name", "Provider", 26), Column("category", "Category", 16),
                Column("status", "Status", 12), Column("usage", "Calls Used", 12),
                Column("usage_limit", "Quota", 12), Column("leads_contributed", "Leads", 12),
            ],
            rows=[
                {
                    "name": p.name, "category": p.category, "status": p.status,
                    "usage": p.usage, "usage_limit": p.usage_limit,
                    "leads_contributed": p.leads_contributed,
                }
                for p in providers
            ],
        ),
    ]

    return Dataset(
        title="LeadMaster AI — Analytics Report",
        subtitle="Lead quality, geography, and provider performance",
        sections=sections,
        metadata={
            "Organization": organization_name,
            "Generated": datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC"),
        },
    )


# --- Capability flags -----------------------------------------------------

# Resources whose datasets can be built by the sync Celery worker. Reports are
# excluded because they are assembled from the async-only analytics service —
# and they never need it: each is a few dozen aggregate rows, well under the
# async threshold, so they are always generated inline.
_BACKGROUND_CAPABLE = frozenset({ExportResource.LEADS, ExportResource.SEARCH_RESULTS})


def supports_background(resource: ExportResource) -> bool:
    return resource in _BACKGROUND_CAPABLE
