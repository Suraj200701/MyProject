"""CSV lead import and manual lead entry.

Both are first-class lead sources alongside the API providers: they produce
`NormalizedLead` values and go through the same deduplication and scoring
pipeline, so an imported lead is indistinguishable in quality from a
provider-sourced one.

CSV handling decisions
----------------------
* **Flexible headers.** Real spreadsheets say "Company", "company_name",
  "Company Name" or "Organisation". A header alias map absorbs that rather than
  rejecting the file, because a strict schema means users hand-edit exports.
* **Per-row errors, not all-or-nothing.** A 500-row file with 3 bad rows imports
  497 and reports the 3 with line numbers. Rejecting the whole file would be
  hostile for a data-entry workflow.
* **Encoding tolerance.** Excel on Windows commonly emits UTF-8-with-BOM or
  cp1252; both are handled, since a mojibake company name is a silent data
  quality bug.
* **GSTIN is validated on import** with the same checksum used for scraped data
  — invalid values are reported per-row instead of being stored as if verified.
"""

from __future__ import annotations

import csv
import io
import logging
import uuid
from dataclasses import dataclass, field

from sqlalchemy.ext.asyncio import AsyncSession

from config.settings import settings
from models.lead import Lead
from services.enrichment import dedup, extractors, scoring
from services.providers.base import NormalizedLead
from utils.exceptions import BadRequestError

logger = logging.getLogger("leadmaster.import")

MANUAL_SOURCE = "Manual Entry"
CSV_SOURCE = "CSV Import"

# Accepted header spellings -> canonical field. Lowercased and stripped of
# non-alphanumerics before lookup, so "Company Name", "company_name" and
# "COMPANY-NAME" all collapse to the same key.
_HEADER_ALIASES: dict[str, str] = {
    "company": "company_name",
    "companyname": "company_name",
    "organisation": "company_name",
    "organization": "company_name",
    "business": "company_name",
    "businessname": "company_name",
    "name": "company_name",
    "industry": "industry",
    "sector": "industry",
    "vertical": "industry",
    "companytype": "company_type",
    "type": "company_type",
    "entitytype": "company_type",
    "revenue": "revenue_band",
    "revenueband": "revenue_band",
    "turnover": "revenue_band",
    "website": "website",
    "url": "website",
    "web": "website",
    "domain": "website",
    "gst": "gst_number",
    "gstin": "gst_number",
    "gstnumber": "gst_number",
    "gstno": "gst_number",
    "city": "city",
    "town": "city",
    "location": "city",
    "country": "country",
    "contact": "contact_name",
    "contactname": "contact_name",
    "contactperson": "contact_name",
    "person": "contact_name",
    "email": "email",
    "emailaddress": "email",
    "mail": "email",
    "phone": "phone",
    "phonenumber": "phone",
    "mobile": "phone",
    "contactnumber": "phone",
    "telephone": "phone",
    "tags": "tags",
    "rating": "rating",
    "lat": "lat",
    "latitude": "lat",
    "lng": "lng",
    "long": "lng",
    "longitude": "lng",
}


@dataclass
class RowError:
    line: int
    message: str
    # Echoed back so the user can find the row in their spreadsheet.
    company: str | None = None


@dataclass
class ImportResult:
    """Summary of an import run."""

    total_rows: int = 0
    imported: int = 0
    duplicates_skipped: int = 0
    invalid_rows: int = 0
    errors: list[RowError] = field(default_factory=list)
    dedup_signals: dict[str, int] = field(default_factory=dict)
    lead_ids: list[uuid.UUID] = field(default_factory=list)


def _canonical_header(raw: str) -> str | None:
    key = "".join(ch for ch in (raw or "").lower() if ch.isalnum())
    return _HEADER_ALIASES.get(key)


def _decode_csv(content: bytes) -> str:
    """Decodes CSV bytes, tolerating Excel's usual encodings."""
    for encoding in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise BadRequestError("Could not decode the CSV file — save it as UTF-8 and try again")


def parse_csv(content: bytes) -> tuple[list[NormalizedLead], list[RowError], int]:
    """Parses CSV bytes into leads plus per-row errors.

    Returns `(leads, errors, total_data_rows)`.
    """
    text = _decode_csv(content)

    # Sniff the delimiter: European exports frequently use ';'.
    sample = text[:4096]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
    except csv.Error:
        dialect = csv.excel

    reader = csv.reader(io.StringIO(text), dialect)
    try:
        header_row = next(reader)
    except StopIteration:
        raise BadRequestError("The CSV file is empty") from None

    mapping: dict[int, str] = {}
    for index, raw in enumerate(header_row):
        canonical = _canonical_header(raw)
        if canonical and canonical not in mapping.values():
            mapping[index] = canonical

    if "company_name" not in mapping.values():
        recognized = sorted(set(_HEADER_ALIASES.values()))
        raise BadRequestError(
            "The CSV must include a company name column (accepted headers: "
            f"company, company_name, organisation, business, name). Recognized columns: {', '.join(recognized)}"
        )

    leads: list[NormalizedLead] = []
    errors: list[RowError] = []
    total = 0

    for line_number, row in enumerate(reader, start=2):
        if not any((cell or "").strip() for cell in row):
            continue  # blank spacer row
        total += 1

        if total > settings.CSV_IMPORT_MAX_ROWS:
            errors.append(
                RowError(
                    line=line_number,
                    message=f"File exceeds the {settings.CSV_IMPORT_MAX_ROWS}-row limit; remaining rows were not imported",
                )
            )
            break

        values: dict[str, str] = {}
        for index, field_name in mapping.items():
            if index < len(row):
                value = (row[index] or "").strip()
                if value:
                    values[field_name] = value

        company_name = values.get("company_name")
        if not company_name:
            errors.append(RowError(line=line_number, message="Missing company name"))
            continue

        gstin = values.get("gst_number")
        if gstin:
            gstin = gstin.replace(" ", "").upper()
            if not extractors.is_valid_gstin(gstin):
                errors.append(
                    RowError(
                        line=line_number,
                        message=f"Invalid GSTIN '{gstin}' (failed checksum) — lead imported without it",
                        company=company_name,
                    )
                )
                gstin = None

        email = values.get("email")
        if email:
            # Syntax check only. `extract_emails` additionally filters
            # placeholder-looking domains, which is right when scraping a page
            # but wrong here — the user typed this cell on purpose.
            normalized_email = extractors.normalize_supplied_email(email)
            if normalized_email is None:
                errors.append(
                    RowError(line=line_number, message=f"Invalid email '{email}' — lead imported without it", company=company_name)
                )
            email = normalized_email

        phone = values.get("phone")
        if phone:
            normalized_phones = extractors.extract_phones(phone)
            phone = normalized_phones[0] if normalized_phones else None
            if phone is None:
                errors.append(
                    RowError(
                        line=line_number,
                        message=f"Unrecognized phone '{values['phone']}' — lead imported without it",
                        company=company_name,
                    )
                )

        tags_raw = values.get("tags") or ""
        tags = [t.strip() for t in tags_raw.replace("|", ",").split(",") if t.strip()]

        leads.append(
            NormalizedLead(
                company_name=company_name,
                industry=values.get("industry"),
                company_type=values.get("company_type"),
                revenue_band=values.get("revenue_band"),
                website=values.get("website"),
                gst_number=gstin,
                city=values.get("city"),
                country=values.get("country"),
                lat=_as_float(values.get("lat")),
                lng=_as_float(values.get("lng")),
                rating=_as_float(values.get("rating")),
                contact_name=values.get("contact_name"),
                email=email,
                phone=phone,
                tags=tags,
                raw={"source_row": line_number},
                source_provider=CSV_SOURCE,
            )
        )

    return leads, errors, total


def _as_float(value: str | None) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        return None


async def import_leads(
    db: AsyncSession,
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
    content: bytes,
) -> ImportResult:
    """Parses, deduplicates, scores and persists leads from a CSV file."""
    leads, errors, total = parse_csv(content)

    result = ImportResult(total_rows=total, invalid_rows=len(errors), errors=errors)
    if not leads:
        return result

    dedup_result = await dedup.deduplicate(db, organization_id, leads)
    result.duplicates_skipped = dedup_result.total_removed
    result.dedup_signals = dedup_result.signals

    scores = await scoring.score_leads(dedup_result.unique)

    from services.search_service import _get_or_create_company

    for lead, (score, summary) in zip(dedup_result.unique, scores):
        company = await _get_or_create_company(db, lead)
        row = Lead(
            organization_id=organization_id,
            company_id=company.id,
            contact_name=lead.contact_name,
            email=lead.email,
            phone=lead.phone,
            lead_score=score,
            status="new",
            tags=lead.tags or None,
            created_by_id=user_id,
            ai_summary=summary,
        )
        db.add(row)
        await db.flush()
        result.lead_ids.append(row.id)
        result.imported += 1

    await db.commit()
    logger.info(
        "CSV import for org %s: %s imported, %s duplicates, %s invalid",
        organization_id,
        result.imported,
        result.duplicates_skipped,
        result.invalid_rows,
    )
    return result


async def score_manual_lead(lead: NormalizedLead) -> tuple[int, str]:
    """Scores a manually-entered lead with the same engine used for search."""
    scores = await scoring.score_leads([lead], lead.industry)
    return scores[0] if scores else (scoring.score_lead_by_signals(lead), "")
