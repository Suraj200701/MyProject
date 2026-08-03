"""Import runs: history recording, optional enrichment, and the Google Maps flow.

Relationship to `lead_import`
-----------------------------
`lead_import` owns parsing and the parse -> dedup -> score -> persist pipeline.
This module wraps a run in a `LeadImport` history row and adds the optional
website-enrichment pass, so the pipeline itself stays reusable and testable
without a history table.

The Google Maps workflow
------------------------
LeadMaster **does not scrape Google Maps**. It builds a normal
`google.com/maps/search/...` URL for the user to open, and then imports the CSV
their own extractor extension produced. That is the whole extent of the
integration: a link and a file upload. Nothing here fetches, parses or automates
Google Maps, and no Google credentials are involved.

Enrichment
----------
Maps exports carry a name, address, phone and sometimes a website — almost never
an email. Enrichment visits each lead's own website (through the SSRF-guarded
fetcher the scanner uses) and extracts emails, extra phones and a GSTIN. It is
opt-in per import because it is slow — one HTTP fetch per lead — and it runs
after the leads are already committed, so a slow or failing site degrades
enrichment rather than losing the import.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from urllib.parse import quote_plus

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config.settings import settings
from models.enums import ImportSource, ImportStatus
from models.lead import Company, Lead
from models.lead_import import LeadImport
from services import lead_import
from utils.exceptions import BadRequestError

logger = logging.getLogger("leadmaster.import")

GOOGLE_MAPS_SEARCH_BASE = "https://www.google.com/maps/search/"

# Cap on per-row errors persisted to the history row. A 10,000-row file where
# every row is malformed would otherwise write megabytes of JSON into a column
# that exists for human inspection.
MAX_PERSISTED_ROW_ERRORS = 50

# Enrichment fetches one website per lead. Bounded so a large import cannot open
# hundreds of concurrent sockets.
ENRICHMENT_CONCURRENCY = 5


def build_maps_search_url(keyword: str, location: str | None = None) -> str:
    """The Google Maps URL for this search.

    Exactly what a user would get by typing the query into Google Maps. Built
    server-side as well as client-side so the value stored in history matches
    what was opened.
    """
    keyword = (keyword or "").strip()
    if not keyword:
        raise BadRequestError("A keyword is required to build a Google Maps search")

    query = f"{keyword} {location.strip()}" if location and location.strip() else keyword
    # quote_plus, not quote: Maps treats "+" as a term separator in this path,
    # which is the form the documented /maps/search/ URL expects.
    return f"{GOOGLE_MAPS_SEARCH_BASE}{quote_plus(query)}"


@dataclass
class EnrichmentOutcome:
    enriched: int = 0
    attempted: int = 0


async def _record(
    db: AsyncSession,
    *,
    organization_id: uuid.UUID,
    user_id: uuid.UUID | None,
    source: ImportSource,
    file_name: str | None,
    file_size_bytes: int | None,
    keyword: str | None,
    location: str | None,
) -> LeadImport:
    """Creates the history row up front, so a crash mid-import leaves a trace."""
    row = LeadImport(
        organization_id=organization_id,
        user_id=user_id,
        source=source,
        status=ImportStatus.PROCESSING,
        file_name=(file_name or None) and file_name[:255],
        file_size_bytes=file_size_bytes,
        keyword=(keyword or None) and keyword[:200],
        location=(location or None) and location[:200],
    )
    db.add(row)
    await db.flush()
    return row


async def run_import(
    db: AsyncSession,
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
    content: bytes,
    *,
    source: ImportSource = ImportSource.CSV_UPLOAD,
    file_name: str | None = None,
    keyword: str | None = None,
    location: str | None = None,
    enrich: bool = False,
) -> tuple[LeadImport, lead_import.ImportResult]:
    """Imports a CSV and records the run in history.

    The history row is written **before** parsing so a failure is visible rather
    than silent, then updated with the outcome. A parse failure marks the row
    FAILED with the message instead of raising into a void.
    """
    record = await _record(
        db,
        organization_id=organization_id,
        user_id=user_id,
        source=source,
        file_name=file_name,
        file_size_bytes=len(content) if content else 0,
        keyword=keyword,
        location=location,
    )
    await db.commit()

    try:
        result = await lead_import.import_leads(db, organization_id, user_id, content)
    except BadRequestError as exc:
        # A rejected file (bad encoding, no name column, empty) is a user error,
        # not a server fault — record it and re-raise so the API still returns 400.
        record.status = ImportStatus.FAILED
        record.error_message = str(exc.detail if hasattr(exc, "detail") else exc)[:2000]
        record.completed_at = datetime.now(UTC)
        await db.commit()
        raise
    except Exception as exc:  # noqa: BLE001 — the row must not be left PROCESSING
        logger.exception("Import %s failed", record.id)
        record.status = ImportStatus.FAILED
        record.error_message = f"{type(exc).__name__}: {exc}"[:2000]
        record.completed_at = datetime.now(UTC)
        await db.commit()
        raise

    enrichment = EnrichmentOutcome()
    if enrich and result.lead_ids:
        enrichment = await enrich_leads(db, organization_id, result.lead_ids)

    record.total_rows = result.total_rows
    record.imported = result.imported
    record.duplicates_skipped = result.duplicates_skipped
    record.invalid_rows = result.invalid_rows
    record.enriched = enrichment.enriched
    record.dedup_signals = result.dedup_signals or None
    record.row_errors = (
        [
            {"line": e.line, "message": e.message, "company": e.company}
            for e in result.errors[:MAX_PERSISTED_ROW_ERRORS]
        ]
        or None
    )
    # "Completed but nothing landed" is worth distinguishing: the user should
    # look at their file, not at their filters.
    record.status = ImportStatus.COMPLETED if result.imported else ImportStatus.COMPLETED_EMPTY
    record.completed_at = datetime.now(UTC)
    await db.commit()

    logger.info(
        "Import %s (%s): %s imported, %s duplicates, %s invalid, %s enriched",
        record.id,
        source.value,
        result.imported,
        result.duplicates_skipped,
        result.invalid_rows,
        enrichment.enriched,
    )
    return record, result


async def enrich_leads(
    db: AsyncSession, organization_id: uuid.UUID, lead_ids: list[uuid.UUID]
) -> EnrichmentOutcome:
    """Fills missing email/phone/GSTIN by reading each lead's own website.

    Runs after the import has committed. Fetch failures are logged and skipped —
    an unreachable website is normal and must not fail the import that already
    succeeded.

    Only *missing* fields are filled; a value the user's file supplied is never
    overwritten by a scraped one.
    """
    outcome = EnrichmentOutcome()
    if not settings.SCANNER_ENABLED:
        logger.info("Enrichment skipped: SCANNER_ENABLED is false")
        return outcome

    stmt = (
        select(Lead, Company)
        .join(Company, Lead.company_id == Company.id)
        .where(Lead.id.in_(lead_ids), Lead.organization_id == organization_id)
    )
    rows = (await db.execute(stmt)).all()
    targets = [(lead, company) for lead, company in rows if company.website]
    outcome.attempted = len(targets)
    if not targets:
        return outcome

    from services.providers.website_search import build_website_profile

    semaphore = asyncio.Semaphore(ENRICHMENT_CONCURRENCY)

    async def enrich_one(lead: Lead, company: Company) -> bool:
        async with semaphore:
            try:
                profile = await build_website_profile(company.website)
            except Exception as exc:  # noqa: BLE001 — one bad site must not stop the batch
                logger.info("Enrichment fetch failed for %s: %s", company.website, exc)
                return False

        if profile is None or not profile.succeeded:
            return False

        changed = False
        if not lead.email and profile.emails:
            lead.email = profile.emails[0]
            changed = True
        if not lead.phone and profile.phones:
            lead.phone = profile.phones[0]
            changed = True
        if not company.gst_number and profile.gstin:
            # Only checksum-valid GSTINs reach here (the extractor validates).
            company.gst_number = profile.gstin
            changed = True
        return changed

    results = await asyncio.gather(
        *(enrich_one(lead, company) for lead, company in targets), return_exceptions=True
    )
    for value in results:
        if value is True:
            outcome.enriched += 1

    await db.commit()
    logger.info(
        "Enriched %s of %s lead(s) with a website", outcome.enriched, outcome.attempted
    )
    return outcome
