"""Lead search, provider catalogue, and website scanner endpoints."""

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_current_organization, get_current_user
from database.session import get_db
from models.organization import Organization
from models.search import ApiProvider, Search, WebsiteScan
from models.user import User
from schemas.search import ApiProviderOut, SearchCreate, SearchOut, WebsiteScanCreate, WebsiteScanOut
from services import search_service
from utils.pagination import Page, PaginationParams, paginate, pagination_params

router = APIRouter(tags=["Search"])


@router.post("/search", response_model=SearchOut, status_code=201)
async def create_search(
    payload: SearchCreate,
    organization: Organization = Depends(get_current_organization),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    search = await search_service.run_search(db, organization.id, user.id, payload)
    return SearchOut(
        id=search.id,
        query=search.query,
        location=search.location,
        status=search.status,
        results_count=search.results_count,
        created_at=search.created_at,
        completed_at=search.completed_at,
        provider_runs=[
            {
                "provider_id": run.provider_id,
                "provider_name": (await db.get(ApiProvider, run.provider_id)).name,
                "status": run.status,
                "results_found": run.results_found,
            }
            for run in search.provider_runs
        ],
    )


@router.get("/search/history", response_model=Page[SearchOut])
async def search_history(
    params: PaginationParams = Depends(pagination_params),
    organization: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Search).where(Search.organization_id == organization.id).order_by(Search.created_at.desc())
    searches, meta = await paginate(db, stmt, params)
    items = [
        SearchOut(
            id=s.id,
            query=s.query,
            location=s.location,
            status=s.status,
            results_count=s.results_count,
            created_at=s.created_at,
            completed_at=s.completed_at,
        )
        for s in searches
    ]
    return Page(items=items, meta=meta)


@router.get("/providers", response_model=list[ApiProviderOut])
async def list_providers(db: AsyncSession = Depends(get_db)):
    providers = (await db.execute(select(ApiProvider).order_by(ApiProvider.name))).scalars().all()
    return providers


@router.post("/scan-website", response_model=WebsiteScanOut, status_code=201)
async def scan_website(
    payload: WebsiteScanCreate,
    organization: Organization = Depends(get_current_organization),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    scan = await search_service.scan_website(db, organization.id, user.id, payload)
    return scan


@router.get("/scans", response_model=Page[WebsiteScanOut])
async def list_scans(
    params: PaginationParams = Depends(pagination_params),
    organization: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(WebsiteScan)
        .where(WebsiteScan.organization_id == organization.id)
        .order_by(WebsiteScan.created_at.desc())
    )
    scans, meta = await paginate(db, stmt, params)
    return Page(items=scans, meta=meta)
