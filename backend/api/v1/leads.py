"""Lead CRUD, notes, and activity timeline — every query is scoped to the
caller's current organization."""

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_current_organization, get_current_user
from database.session import get_db
from models.lead import Lead
from models.organization import Organization
from models.search import ApiProvider
from models.user import User
from repositories.lead_repository import LeadRepository
from schemas.common import MessageResponse
from schemas.lead import (
    BulkDeleteRequest,
    LeadActivityOut,
    LeadCreate,
    LeadDetailOut,
    LeadNoteCreate,
    LeadNoteOut,
    LeadOut,
    LeadUpdate,
    SortOrder,
)
from utils.exceptions import NotFoundError
from utils.pagination import Page, PaginationParams, paginate, pagination_params

router = APIRouter(prefix="/leads", tags=["Leads"])


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
    repo = LeadRepository(db)
    company = await repo.get_or_create_company(organization.id, payload)

    lead = await repo.create(
        organization_id=organization.id,
        company_id=company.id,
        contact_name=payload.contact_name,
        email=payload.email,
        phone=payload.phone,
        lead_score=payload.lead_score,
        status=payload.status,
        tags=payload.tags,
        ai_summary=payload.ai_summary,
        created_by_id=user.id,
    )
    await repo.add_activity(lead.id, "created", "Lead added to database")
    await db.commit()
    await db.refresh(lead)
    return LeadOut.from_lead(lead)


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
