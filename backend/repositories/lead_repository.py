"""Lead/company queries scoped to an organization."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import Select, select
from sqlalchemy.orm import joinedload, selectinload

from models.lead import Company, Lead, LeadActivity, LeadNote
from repositories.base import BaseRepository


class LeadRepository(BaseRepository[Lead]):
    model = Lead

    def list_for_org(
        self,
        org_id: uuid.UUID,
        *,
        search: str | None = None,
        industry: str | None = None,
        status: str | None = None,
        country: str | None = None,
        min_score: int | None = None,
        max_score: int | None = None,
        sort_by: str = "created_at",
        sort_order: str = "desc",
    ) -> Select:
        stmt = (
            select(Lead)
            .join(Company, Lead.company_id == Company.id)
            .options(joinedload(Lead.company))
            .where(Lead.organization_id == org_id)
        )

        if search:
            pattern = f"%{search.lower()}%"
            stmt = stmt.where(Company.name.ilike(pattern))
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

        sort_columns = {
            "created_at": Lead.created_at,
            "lead_score": Lead.lead_score,
            "company": Company.name,
        }
        column = sort_columns.get(sort_by, Lead.created_at)
        stmt = stmt.order_by(column.asc() if sort_order == "asc" else column.desc())
        return stmt

    async def get_with_company(self, lead_id: uuid.UUID, org_id: uuid.UUID) -> Lead | None:
        stmt = (
            select(Lead)
            .where(Lead.id == lead_id, Lead.organization_id == org_id)
            .options(
                joinedload(Lead.company),
                selectinload(Lead.notes),
                selectinload(Lead.activities),
            )
        )
        return (await self.session.execute(stmt)).unique().scalar_one_or_none()

    async def add_note(self, lead_id: uuid.UUID, author_id: uuid.UUID | None, text: str) -> LeadNote:
        note = LeadNote(lead_id=lead_id, author_id=author_id, text=text, created_at=datetime.now(UTC))
        self.session.add(note)
        await self.session.flush()
        return note

    async def add_activity(
        self, lead_id: uuid.UUID, event_type: str, description: str, extra_data: dict | None = None
    ) -> LeadActivity:
        activity = LeadActivity(
            lead_id=lead_id,
            event_type=event_type,
            description=description,
            extra_data=extra_data,
            created_at=datetime.now(UTC),
        )
        self.session.add(activity)
        await self.session.flush()
        return activity

    async def get_or_create_company(self, org_id: uuid.UUID, data) -> Company:
        """Dedupe by (name) within a simple heuristic — companies aren't
        strictly org-scoped in the schema (they can be shared/discovered
        by multiple orgs), so dedupe by name+city to avoid over-merging
        unrelated companies that happen to share a name."""
        stmt = select(Company).where(Company.name == data.company, Company.city == data.city)
        existing = (await self.session.execute(stmt)).scalar_one_or_none()
        if existing:
            return existing

        company = Company(
            name=data.company,
            industry=data.industry,
            company_type=data.company_type,
            revenue_band=data.revenue_band,
            website=data.website,
            gst_number=data.gst_number,
            city=data.city,
            country=data.country,
            lat=data.lat,
            lng=data.lng,
            rating=data.rating,
        )
        self.session.add(company)
        await self.session.flush()
        return company
