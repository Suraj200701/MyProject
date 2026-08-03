"""Import runs and the Google Maps Search helper.

What this module does and deliberately does not do
--------------------------------------------------
`POST /imports/google-maps/search-url` returns a plain
`https://www.google.com/maps/search/...` link for the user to open. Nothing here
requests, renders or parses Google Maps, and no Google credentials are used.

`POST /imports/google-maps` accepts a CSV the user exported themselves — with
their own browser extension, in their own browser — and runs it through the same
parse -> deduplicate -> score -> (optionally) enrich -> save pipeline as any
other CSV. From this server's point of view it is a file upload; where the file
came from is not something it inspects or automates.

The separate `POST /leads/import` endpoint predates this and still works; it
shares the pipeline but does not record history, so it is left untouched.
"""

import uuid

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_current_organization, get_current_user
from config.settings import settings
from database.session import get_db
from models.enums import ImportSource
from models.lead_import import LeadImport
from models.organization import Organization
from models.user import User
from schemas.lead_import import LeadImportOut, MapsSearchRequest, MapsSearchUrlOut
from services import import_service
from utils.exceptions import BadRequestError, NotFoundError
from utils.pagination import Page, PaginationParams, paginate, pagination_params

router = APIRouter(prefix="/imports", tags=["Imports"])

_CSV_CONTENT_TYPES = {
    "text/csv",
    "application/csv",
    "text/plain",
    "application/vnd.ms-excel",
    "application/octet-stream",
}


@router.post("/google-maps/search-url", response_model=MapsSearchUrlOut)
async def google_maps_search_url(
    payload: MapsSearchRequest,
    _user: User = Depends(get_current_user),
    _organization: Organization = Depends(get_current_organization),
):
    """Builds the Google Maps search URL for a keyword + location.

    Returned rather than followed: the client opens it in a tab (or a desktop
    window). This exists as an endpoint so the URL the user opened and the one
    recorded against the import are produced by the same code.
    """
    return MapsSearchUrlOut(
        url=import_service.build_maps_search_url(payload.keyword, payload.location),
        keyword=payload.keyword.strip(),
        location=(payload.location or "").strip() or None,
    )


@router.post("/google-maps", response_model=LeadImportOut, status_code=201)
async def import_google_maps_export(
    file: UploadFile = File(..., description="CSV exported by your Google Maps extractor extension"),
    keyword: str | None = Form(default=None, max_length=200),
    location: str | None = Form(default=None, max_length=200),
    enrich: bool = Form(default=False),
    organization: Organization = Depends(get_current_organization),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Imports a CSV exported by the user's own Google Maps extractor extension.

    `keyword`/`location` are the search the export came from; they are stored on
    the history row so a run is recognisable later ("Dentists in Ahmedabad — 84
    leads" rather than "export(3).csv").

    Set `enrich=true` to visit each lead's website afterwards and fill in missing
    emails, phones and GSTINs. It runs after the leads are committed, so a slow
    or unreachable site costs enrichment, not the import.
    """
    content = await _read_csv_upload(file)
    record, _result = await import_service.run_import(
        db,
        organization.id,
        user.id,
        content,
        source=ImportSource.GOOGLE_MAPS_EXTRACTOR,
        file_name=file.filename,
        keyword=keyword,
        location=location,
        enrich=enrich,
    )
    return LeadImportOut.model_validate(record)


@router.post("", response_model=LeadImportOut, status_code=201)
async def import_csv(
    file: UploadFile = File(..., description="CSV file with a company name column"),
    enrich: bool = Form(default=False),
    organization: Organization = Depends(get_current_organization),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Imports a generic CSV, recording the run in history."""
    content = await _read_csv_upload(file)
    record, _result = await import_service.run_import(
        db,
        organization.id,
        user.id,
        content,
        source=ImportSource.CSV_UPLOAD,
        file_name=file.filename,
        enrich=enrich,
    )
    return LeadImportOut.model_validate(record)


@router.get("", response_model=Page[LeadImportOut])
async def list_imports(
    source: ImportSource | None = Query(default=None),
    organization: Organization = Depends(get_current_organization),
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    params: PaginationParams = Depends(pagination_params),
):
    """Import history for the caller's organization, newest first."""
    stmt = (
        select(LeadImport)
        .where(LeadImport.organization_id == organization.id)
        .order_by(LeadImport.created_at.desc())
    )
    if source is not None:
        stmt = stmt.where(LeadImport.source == source)

    items, meta = await paginate(db, stmt, params)
    return Page(items=[LeadImportOut.model_validate(i) for i in items], meta=meta)


@router.get("/{import_id}", response_model=LeadImportOut)
async def get_import(
    import_id: uuid.UUID,
    organization: Organization = Depends(get_current_organization),
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """One import run, including its per-row errors."""
    stmt = select(LeadImport).where(
        LeadImport.id == import_id,
        # Scoped to the org: an import id from another workspace must 404, not leak.
        LeadImport.organization_id == organization.id,
    )
    record = (await db.execute(stmt)).scalar_one_or_none()
    if record is None:
        raise NotFoundError("Import not found")
    return LeadImportOut.model_validate(record)


async def _read_csv_upload(file: UploadFile) -> bytes:
    """Validates and reads an uploaded CSV.

    Content type is checked loosely because browsers report CSV inconsistently
    (`application/vnd.ms-excel` when Excel is installed, `application/octet-stream`
    from some download managers) — rejecting on it alone would block legitimate
    files. The parser is the real gate.
    """
    if file.content_type and file.content_type not in _CSV_CONTENT_TYPES:
        raise BadRequestError(f"Expected a CSV file, received '{file.content_type}'")

    content = await file.read()
    max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    if len(content) > max_bytes:
        raise BadRequestError(f"File exceeds the {settings.MAX_UPLOAD_SIZE_MB}MB limit")
    if not content.strip():
        raise BadRequestError("The uploaded file is empty")
    return content
