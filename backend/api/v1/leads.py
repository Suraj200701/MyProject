"""Lead CRUD, notes, and activity timeline — every query is scoped to the
caller's current organization."""

import uuid

from fastapi import APIRouter, Depends, File, Query, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_current_organization, get_current_user
from config.settings import settings
from database.session import get_db
from models.lead import Lead
from models.organization import Organization
from models.search import ApiProvider
from models.user import User
from repositories.lead_repository import LeadRepository
from schemas.common import MessageResponse
from schemas.lead import (
    BulkDeleteRequest,
    CsvImportResult,
    CsvImportRowError,
    EnrichLeadsRequest,
    EnrichmentOutcomeOut,
    EnrichmentSummaryOut,
    LeadActivityOut,
    LeadCreate,
    LeadDetailOut,
    LeadNoteCreate,
    LeadNoteOut,
    LeadOut,
    LeadUpdate,
    SortOrder,
)
from services import lead_import, usage_service
from services.enrichment.lead_enrichment import LeadEnricher
from services.providers.base import NormalizedLead
from utils.exceptions import BadRequestError, NotFoundError
from utils.pagination import Page, PaginationParams, paginate, pagination_params

router = APIRouter(prefix="/leads", tags=["Leads"])

# Browsers and spreadsheet tools disagree on the CSV MIME type; accept the
# common variants plus the generic octet-stream that some clients send.
_CSV_CONTENT_TYPES = frozenset(
    {
        "text/csv",
        "application/csv",
        "text/plain",
        "application/vnd.ms-excel",
        "application/octet-stream",
    }
)


async def _provider_name(db: AsyncSession, provider_id: uuid.UUID | None) -> str | None:
    if provider_id is None:
        return None
    provider = await db.get(ApiProvider, provider_id)
    return provider.name if provider else None


@router.get("", response_model=Page[LeadOut])
async def list_leads(
    search: str | None = Query(default=None),
    industry: str | None = Query(default=None),
    status: str | None = Query(default=None),
    country: str | None = Query(default=None),
    min_score: int | None = Query(default=None, ge=0, le=100),
    max_score: int | None = Query(default=None, ge=0, le=100),
    sort_by: str = Query(default="created_at"),
    sort_order: SortOrder = Query(default="desc"),
    params: PaginationParams = Depends(pagination_params),
    organization: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
):
    repo = LeadRepository(db)
    stmt = repo.list_for_org(
        organization.id,
        search=search,
        industry=industry,
        status=status,
        country=country,
        min_score=min_score,
        max_score=max_score,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    leads, meta = await paginate(db, stmt, params)

    provider_ids = {lead.provider_id for lead in leads if lead.provider_id}
    providers = {}
    if provider_ids:
        rows = (await db.execute(select(ApiProvider).where(ApiProvider.id.in_(provider_ids)))).scalars().all()
        providers = {p.id: p.name for p in rows}

    items = [LeadOut.from_lead(lead, providers.get(lead.provider_id)) for lead in leads]
    return Page(items=items, meta=meta)


@router.get("/{lead_id}", response_model=LeadDetailOut)
async def get_lead(
    lead_id: uuid.UUID,
    organization: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
):
    repo = LeadRepository(db)
    lead = await repo.get_with_company(lead_id, organization.id)
    if lead is None:
        raise NotFoundError("Lead not found")

    provider_name = await _provider_name(db, lead.provider_id)
    base = LeadOut.from_lead(lead, provider_name)
    return LeadDetailOut(
        **base.model_dump(),
        notes=[LeadNoteOut.model_validate(n) for n in lead.notes],
        activities=[LeadActivityOut.model_validate(a) for a in sorted(lead.activities, key=lambda a: a.created_at)],
    )


@router.post("", response_model=LeadOut, status_code=201)
async def create_lead(
    payload: LeadCreate,
    organization: Organization = Depends(get_current_organization),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Manual lead entry.

    Contract is unchanged. Two additions, both opt-in by omission:
      * If `lead_score` is left at its default 0, the lead is scored by the same
        engine used for search results, so a hand-entered lead is comparable to
        a sourced one instead of sitting at zero forever. An explicit score is
        always respected.
      * If `ai_summary` is omitted, one is generated from the lead's real
        attributes.
    Duplicate detection runs against the organization's existing leads and is
    reported via the `X-Duplicate-Of` response header rather than by rejecting
    the request — a human typing a lead in is the authority on whether it's new.
    """
    repo = LeadRepository(db)
    company = await repo.get_or_create_company(organization.id, payload)

    normalized = NormalizedLead(
        company_name=payload.company,
        industry=payload.industry,
        company_type=payload.company_type,
        revenue_band=payload.revenue_band,
        website=payload.website,
        gst_number=payload.gst_number,
        city=payload.city,
        country=payload.country,
        lat=payload.lat,
        lng=payload.lng,
        rating=payload.rating,
        contact_name=payload.contact_name,
        email=payload.email,
        phone=payload.phone,
        tags=payload.tags or [],
        source_provider=lead_import.MANUAL_SOURCE,
    )

    lead_score = payload.lead_score
    ai_summary = payload.ai_summary
    if not lead_score or not ai_summary:
        generated_score, generated_summary = await lead_import.score_manual_lead(normalized)
        lead_score = lead_score or generated_score
        ai_summary = ai_summary or generated_summary

    lead = await repo.create(
        organization_id=organization.id,
        company_id=company.id,
        contact_name=payload.contact_name,
        email=payload.email,
        phone=payload.phone,
        lead_score=lead_score,
        status=payload.status,
        tags=payload.tags,
        ai_summary=ai_summary,
        created_by_id=user.id,
    )
    await repo.add_activity(lead.id, "created", "Lead added manually")
    await db.commit()
    await db.refresh(lead)
    return LeadOut.from_lead(lead)


@router.post("/import", response_model=CsvImportResult, status_code=201)
async def import_leads_csv(
    file: UploadFile = File(..., description="CSV file with a company name column"),
    organization: Organization = Depends(get_current_organization),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Bulk-imports leads from a CSV file.

    Headers are matched flexibly (`Company`, `company_name`, `Organisation`, …).
    Rows are validated individually: a bad GSTIN, email or phone is reported and
    the lead is still imported without that field, rather than failing the whole
    file. Imported leads are deduplicated and scored like any other source.
    """
    if file.content_type and file.content_type not in _CSV_CONTENT_TYPES:
        raise BadRequestError(
            f"Expected a CSV file, received '{file.content_type}'"
        )

    content = await file.read()
    max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    if len(content) > max_bytes:
        raise BadRequestError(f"File exceeds the {settings.MAX_UPLOAD_SIZE_MB}MB limit")
    if not content.strip():
        raise BadRequestError("The uploaded file is empty")

    result = await lead_import.import_leads(db, organization.id, user.id, content)
    return CsvImportResult(
        total_rows=result.total_rows,
        imported=result.imported,
        duplicates_skipped=result.duplicates_skipped,
        invalid_rows=result.invalid_rows,
        errors=[
            CsvImportRowError(line=e.line, message=e.message, company=e.company)
            for e in result.errors[:100]
        ],
        dedup_signals=result.dedup_signals,
    )


@router.patch("/{lead_id}", response_model=LeadOut)
async def update_lead(
    lead_id: uuid.UUID,
    payload: LeadUpdate,
    organization: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
):
    repo = LeadRepository(db)
    lead = await repo.get_with_company(lead_id, organization.id)
    if lead is None:
        raise NotFoundError("Lead not found")

    updates = payload.model_dump(exclude_unset=True)
    status_changed = "status" in updates and updates["status"] != lead.status
    for field, value in updates.items():
        setattr(lead, field, value)

    if status_changed:
        await repo.add_activity(lead.id, "status_changed", f"Status changed to {updates['status']}")

    await db.commit()
    await db.refresh(lead)
    provider_name = await _provider_name(db, lead.provider_id)
    return LeadOut.from_lead(lead, provider_name)


@router.delete("/{lead_id}", response_model=MessageResponse)
async def delete_lead(
    lead_id: uuid.UUID,
    organization: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
):
    repo = LeadRepository(db)
    lead = await repo.get(lead_id)
    if lead is None or lead.organization_id != organization.id:
        raise NotFoundError("Lead not found")
    await repo.delete(lead)
    await db.commit()
    return MessageResponse(message="Lead deleted")


@router.post("/bulk-delete", response_model=MessageResponse)
async def bulk_delete_leads(
    payload: BulkDeleteRequest,
    organization: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Lead).where(
        Lead.id.in_(payload.ids),
        Lead.organization_id == organization.id,
    )
    leads = (await db.execute(stmt)).scalars().all()
    for lead in leads:
        await db.delete(lead)
    await db.commit()
    return MessageResponse(message=f"Deleted {len(leads)} lead(s)")


@router.post("/{lead_id}/notes", response_model=LeadNoteOut, status_code=201)
async def add_note(
    lead_id: uuid.UUID,
    payload: LeadNoteCreate,
    organization: Organization = Depends(get_current_organization),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    repo = LeadRepository(db)
    lead = await repo.get(lead_id)
    if lead is None or lead.organization_id != organization.id:
        raise NotFoundError("Lead not found")

    note = await repo.add_note(lead_id, user.id, payload.text)
    await repo.add_activity(lead_id, "note_added", "A note was added")
    await db.commit()
    await db.refresh(note)
    return note


@router.get("/{lead_id}/notes", response_model=list[LeadNoteOut])
async def list_notes(
    lead_id: uuid.UUID,
    organization: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
):
    repo = LeadRepository(db)
    lead = await repo.get_with_company(lead_id, organization.id)
    if lead is None:
        raise NotFoundError("Lead not found")
    return sorted(lead.notes, key=lambda n: n.created_at, reverse=True)


@router.get("/{lead_id}/activities", response_model=list[LeadActivityOut])
async def list_activities(
    lead_id: uuid.UUID,
    organization: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
):
    repo = LeadRepository(db)
    lead = await repo.get_with_company(lead_id, organization.id)
    if lead is None:
        raise NotFoundError("Lead not found")
    return sorted(lead.activities, key=lambda a: a.created_at)


@router.post("/enrich", response_model=EnrichmentSummaryOut, status_code=200)
async def enrich_leads(
    payload: EnrichLeadsRequest,
    organization: Organization = Depends(get_current_organization),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Enriches leads with publicly available contact information.

    Discovery uses the official Google Places API and only when its key is
    configured; without it the lead keeps an empty website and enrichment still
    runs on whatever public data exists. Crawling reuses the scanner's guarded
    fetch path, so only publicly reachable pages are read.

    Credits settle against leads that actually performed outbound work, so a
    cached or skipped lead costs nothing.
    """
    enricher = LeadEnricher()

    lead_ids = list(payload.lead_ids)
    if payload.all_unenriched and not lead_ids:
        # Server-side selection, oldest first, bounded by `limit`.
        stmt = (
            select(Lead.id)
            .where(
                Lead.organization_id == organization.id,
                Lead.enrichment_status.is_(None),
            )
            .order_by(Lead.created_at)
            .limit(payload.limit)
        )
        lead_ids = list((await db.execute(stmt)).scalars().all())

    if not lead_ids:
        raise BadRequestError("Select at least one lead to enrich.")

    exempt = usage_service.is_metering_exempt(user)
    summary = await enricher.enrich_many(
        db, organization.id, lead_ids, metering_exempt=exempt
    )

    return EnrichmentSummaryOut(
        total=summary.total,
        processed=summary.processed,
        website_found=summary.website_found,
        phone_found=summary.phone_found,
        email_found=summary.email_found,
        gst_found=summary.gst_found,
        social_found=summary.social_found,
        no_website=summary.no_website,
        failed=summary.failed,
        credits_charged=summary.credits_charged,
        discovery_available=enricher.discovery_available,
        results=[
            EnrichmentOutcomeOut(
                lead_id=o.lead_id,
                status=o.status,
                website=o.website,
                website_confidence=o.website_confidence,
                fields_added=o.fields_added,
                field_sources=o.field_sources,
                error=o.error,
            )
            for o in summary.results
        ],
    )
