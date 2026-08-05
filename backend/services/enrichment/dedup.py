"""Lead deduplication.

Real providers return the same business under inconsistent names ("Acme Pvt
Ltd" vs "ACME Private Limited" vs "Acme Private Ltd."), and a multi-provider
search multiplies that. Without dedup, one search can create three rows for one
company and every downstream metric inflates.

Matching is a **priority chain**, strongest signal first:

  1. **GSTIN** — a government-issued registration number. An exact match is
     definitive.
  2. **Website domain** — registrable domain, normalized. Two businesses
     essentially never share one.
  3. **Phone** — normalized to `+<cc><digits>`. Strong, though shared
     switchboards in office parks produce occasional false positives, so it
     ranks below domain.
  4. **Normalized name + city** — legal-suffix-stripped name compared with a
     similarity ratio, scoped to the same city so two genuinely different
     "Apex Engineering" businesses in different cities stay separate.

Bias: **under-merge rather than over-merge.** A duplicate is a visible, fixable
annoyance; a false merge silently destroys a real lead. Hence the conservative
default similarity threshold and the city requirement on name matching.
"""

from __future__ import annotations

import logging
import re
import uuid
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from urllib.parse import urlparse

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from config.settings import settings
from models.lead import Company, Lead
from services.providers.base import NormalizedLead

logger = logging.getLogger("leadmaster.dedup")

# Legal-form suffixes and decorations stripped before name comparison.
#
# These are matched *after* punctuation has been stripped, so they must be
# written in punctuation-free form — an entry like "& co" could never match.
# Ampersands are folded to "and" first (see `normalize_company_name`) so both
# spellings of "Acme & Sons" / "Acme and Sons" reduce identically; without that
# the two spellings normalized differently and failed to deduplicate.
_LEGAL_SUFFIXES = (
    "private limited", "pvt limited", "pvt ltd", "p ltd",
    "private ltd", "limited", "ltd", "llp", "llc", "inc", "incorporated",
    "corporation", "corp", "company", "co", "gmbh", "s a", "sa", "bv", "nv",
    "plc", "and sons", "sons", "and co",
)
# Longest first, so "and co" wins over "co" and "private limited" over "limited".
# Matching in declaration order left "acme and co" as "acme and".
_LEGAL_SUFFIXES_BY_LENGTH = tuple(sorted(_LEGAL_SUFFIXES, key=len, reverse=True))

_PUNCT_RE = re.compile(r"[^\w\s]")
_WS_RE = re.compile(r"\s+")
_AMPERSAND_RE = re.compile(r"\s*&\s*")

_MULTI_PART_TLD_HEADS = frozenset({"co", "com", "net", "org", "gov", "edu", "ac", "or", "ne"})


# --- normalization --------------------------------------------------------


def normalize_company_name(name: str | None) -> str:
    """Lowercases, strips punctuation and legal suffixes for comparison."""
    if not name:
        return ""
    # Fold "&" to "and" before punctuation is stripped, so "Acme & Sons" and
    # "Acme and Sons" converge instead of becoming "acme sons" vs "acme".
    value = _AMPERSAND_RE.sub(" and ", name.lower())
    value = _PUNCT_RE.sub(" ", value)
    value = _WS_RE.sub(" ", value).strip()
    # Repeat: "Acme Pvt Ltd Company" carries two stackable suffixes.
    changed = True
    while changed:
        changed = False
        for suffix in _LEGAL_SUFFIXES_BY_LENGTH:
            if value.endswith(f" {suffix}"):
                value = value[: -(len(suffix) + 1)].strip()
                changed = True
                break  # restart from the longest suffix after each strip
    return value


def normalize_domain(website: str | None) -> str:
    """Extracts the registrable domain from a URL or bare host."""
    if not website:
        return ""
    raw = website.strip().lower()
    if "://" not in raw:
        raw = f"https://{raw}"
    try:
        host = (urlparse(raw).hostname or "").removeprefix("www.")
    except ValueError:
        return ""
    if not host:
        return ""
    parts = host.split(".")
    if len(parts) > 2 and parts[-2] in _MULTI_PART_TLD_HEADS and len(parts[-1]) <= 3:
        return ".".join(parts[-3:])
    return ".".join(parts[-2:]) if len(parts) >= 2 else host


def normalize_phone_key(phone: object) -> str:
    """Reduces a phone number to comparable digits (last 10 significant).

    Takes `object`, not `str | None`: provider payloads are arbitrary JSON and
    OpenStreetMap-derived sources emit all-digit phone tags as numbers. This used
    to raise `TypeError: expected string or bytes-like object, got 'int'` from
    `re.sub` and fail the entire search. `NormalizedLead` now coerces too — this
    stays defensive because dedup is also called with raw provider values.
    """
    if not phone:
        return ""
    digits = re.sub(r"\D", "", str(phone))
    if not digits:
        return ""
    # Compare on the last 10 digits so +919876543210, 09876543210 and
    # 9876543210 all collapse to the same key.
    return digits[-10:] if len(digits) >= 10 else digits


def normalize_city(city: str | None) -> str:
    if not city:
        return ""
    # "Pune, India" and "pune" should compare equal.
    first = city.split(",")[0]
    return _WS_RE.sub(" ", _PUNCT_RE.sub(" ", first.lower())).strip()


def name_similarity(a: str, b: str) -> float:
    """Similarity ratio between two already-normalized names (0-1)."""
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    return SequenceMatcher(None, a, b).ratio()


# --- fingerprints --------------------------------------------------------


@dataclass(frozen=True)
class LeadFingerprint:
    """Comparable identity of a lead."""

    gstin: str = ""
    domain: str = ""
    phone: str = ""
    name: str = ""
    city: str = ""

    @classmethod
    def from_normalized(cls, lead: NormalizedLead) -> "LeadFingerprint":
        return cls(
            gstin=(lead.gst_number or "").strip().upper(),
            domain=normalize_domain(lead.website),
            phone=normalize_phone_key(lead.phone),
            name=normalize_company_name(lead.company_name),
            city=normalize_city(lead.city),
        )

    @classmethod
    def from_db(cls, company: Company, lead_phone: str | None = None) -> "LeadFingerprint":
        return cls(
            gstin=(company.gst_number or "").strip().upper(),
            domain=normalize_domain(company.website),
            phone=normalize_phone_key(lead_phone),
            name=normalize_company_name(company.name),
            city=normalize_city(company.city),
        )

    def matches(self, other: "LeadFingerprint", name_threshold: float) -> str | None:
        """Returns the matching signal's name, or None if these are distinct."""
        if self.gstin and self.gstin == other.gstin:
            return "gstin"
        if self.domain and self.domain == other.domain:
            return "domain"
        if self.phone and self.phone == other.phone:
            return "phone"
        if self.name and other.name and self.city and self.city == other.city:
            if name_similarity(self.name, other.name) >= name_threshold:
                return "name+city"
        return None


@dataclass
class DedupResult:
    """Outcome of deduplicating a batch of provider results."""

    unique: list[NormalizedLead] = field(default_factory=list)
    duplicates_in_batch: int = 0
    duplicates_existing: int = 0
    # Leads dropped because the organization already has them, paired with the
    # id of the existing lead they matched. A caller that would rather enrich
    # the existing row than skip the result can walk this; the search and import
    # pipelines currently only count them.
    existing_matches: list[tuple[NormalizedLead, uuid.UUID]] = field(default_factory=list)
    signals: dict[str, int] = field(default_factory=dict)

    @property
    def total_removed(self) -> int:
        return self.duplicates_in_batch + self.duplicates_existing

    def _count(self, signal: str) -> None:
        self.signals[signal] = self.signals.get(signal, 0) + 1


def dedupe_within_batch(leads: list[NormalizedLead], name_threshold: float | None = None) -> DedupResult:
    """Collapses duplicates inside one batch, merging fields as it goes.

    When two records describe the same business, the survivor absorbs any field
    the other has and it lacks — so a Places record (coordinates, rating) plus a
    Bing record (website) become one richer lead rather than two partial ones.
    """
    threshold = name_threshold if name_threshold is not None else settings.DEDUP_NAME_SIMILARITY_THRESHOLD
    result = DedupResult()
    fingerprints: list[LeadFingerprint] = []

    for lead in leads:
        fingerprint = LeadFingerprint.from_normalized(lead)
        matched_index = None
        matched_signal = None
        for index, existing in enumerate(fingerprints):
            signal = fingerprint.matches(existing, threshold)
            if signal:
                matched_index, matched_signal = index, signal
                break

        if matched_index is None:
            fingerprints.append(fingerprint)
            result.unique.append(lead)
            continue

        _merge_into(result.unique[matched_index], lead)
        # The survivor may have gained a domain/phone/GSTIN from the merge, so
        # refresh its fingerprint to catch transitive duplicates later in the batch.
        fingerprints[matched_index] = LeadFingerprint.from_normalized(result.unique[matched_index])
        result.duplicates_in_batch += 1
        result._count(matched_signal)

    return result


def _merge_into(target: NormalizedLead, other: NormalizedLead) -> None:
    """Fills empty fields on `target` from `other`. Never overwrites a value."""
    for attr in (
        "industry", "company_type", "revenue_band", "website", "gst_number",
        "city", "country", "lat", "lng", "rating", "contact_name", "email", "phone",
    ):
        if getattr(target, attr, None) in (None, "") and getattr(other, attr, None) not in (None, ""):
            setattr(target, attr, getattr(other, attr))

    for tag in other.tags:
        if tag and tag not in target.tags:
            target.tags.append(tag)

    if other.raw:
        merged = dict(other.raw)
        merged.update(target.raw or {})
        target.raw = merged

    # Record every contributing source so provenance survives the merge.
    if other.source_provider and other.source_provider != target.source_provider:
        sources = target.raw.setdefault("merged_sources", [])
        for name in (target.source_provider, other.source_provider):
            if name and name not in sources:
                sources.append(name)


async def dedupe_against_existing(
    db: AsyncSession,
    organization_id: uuid.UUID,
    result: DedupResult,
    name_threshold: float | None = None,
) -> DedupResult:
    """Drops batch leads that already exist in the organization's database.

    Candidate lookup is narrowed in SQL by GSTIN / domain / phone / city before
    the fuzzy name comparison runs in Python, so this does not load the whole
    lead table to compare against.
    """
    threshold = name_threshold if name_threshold is not None else settings.DEDUP_NAME_SIMILARITY_THRESHOLD
    if not result.unique:
        return result

    candidates = await _load_candidates(db, organization_id, result.unique)
    if not candidates:
        return result

    kept: list[NormalizedLead] = []
    for lead in result.unique:
        fingerprint = LeadFingerprint.from_normalized(lead)
        match_id = None
        match_signal = None
        for lead_id, existing_fp in candidates:
            signal = fingerprint.matches(existing_fp, threshold)
            if signal:
                match_id, match_signal = lead_id, signal
                break

        if match_id is None:
            kept.append(lead)
        else:
            result.duplicates_existing += 1
            result._count(f"existing:{match_signal}")
            result.existing_matches.append((lead, match_id))

    result.unique = kept
    return result


async def _load_candidates(
    db: AsyncSession, organization_id: uuid.UUID, leads: list[NormalizedLead]
) -> list[tuple[uuid.UUID, LeadFingerprint]]:
    """Loads only the existing leads that could plausibly match this batch."""
    gstins = {(l.gst_number or "").strip().upper() for l in leads if l.gst_number}
    domains = {normalize_domain(l.website) for l in leads if l.website}
    phones = {normalize_phone_key(l.phone) for l in leads if l.phone}
    cities = {normalize_city(l.city) for l in leads if l.city}
    gstins.discard("")
    domains.discard("")
    phones.discard("")
    cities.discard("")

    stmt = select(Lead, Company).join(Company, Lead.company_id == Company.id).where(
        Lead.organization_id == organization_id
    )

    clauses = []
    if gstins:
        clauses.append(Company.gst_number.in_(gstins))
    if domains:
        # Substring match: stored websites carry scheme/www/paths, so an exact
        # comparison against a registrable domain would miss real matches.
        for domain in domains:
            clauses.append(Company.website.ilike(f"%{domain}%"))
    if phones:
        # `phones` holds *normalized* keys (digits only, last 10). Stored numbers
        # keep whatever formatting the provider sent — "0755 277 4851" — so
        # comparing the key against the raw column matched nothing whenever the
        # stored value had separators, and the duplicate was admitted. Strip the
        # column to digits so both sides are in the same alphabet.
        digits_only = func.regexp_replace(Lead.phone, r"[^0-9]", "", "g")
        for phone in phones:
            clauses.append(digits_only.ilike(f"%{phone}%"))
    if cities:
        # Two forms, because `normalize_city` is not just a lowercase: it takes
        # the text before the first comma ("Bhopal, Madhya Pradesh 462003" ->
        # "bhopal"). Comparing that against the raw lowercased column missed
        # every row stored with a full address-style city, which is exactly what
        # map providers return.
        #
        # Both clauses are kept rather than replacing one with the other: the
        # raw form still matches rows stored as a bare city name, and widening
        # candidate lookup can only find more duplicates, never fewer.
        #
        # Neither can use a plain index on `city`; if city-only dedup ever
        # dominates the query plan, add `CREATE INDEX ... ON companies
        # (lower(split_part(city, ',', 1)))`. Not done yet because the clause is
        # OR'd with the others, scoped to one organization, and capped at 500
        # rows below.
        clauses.append(func.lower(Company.city).in_(cities))
        clauses.append(
            func.btrim(func.lower(func.split_part(Company.city, ",", 1))).in_(cities)
        )

    if not clauses:
        return []

    from sqlalchemy import or_

    stmt = stmt.where(or_(*clauses)).limit(500)
    rows = (await db.execute(stmt)).all()
    return [(lead.id, LeadFingerprint.from_db(company, lead.phone)) for lead, company in rows]


async def deduplicate(
    db: AsyncSession,
    organization_id: uuid.UUID,
    leads: list[NormalizedLead],
) -> DedupResult:
    """Full dedup pass: within the batch, then against existing rows."""
    if not settings.DEDUP_ENABLED:
        return DedupResult(unique=list(leads))

    result = dedupe_within_batch(leads)
    result = await dedupe_against_existing(db, organization_id, result)

    if result.total_removed:
        logger.info(
            "Dedup removed %s lead(s) for org %s (in-batch=%s, existing=%s, signals=%s)",
            result.total_removed,
            organization_id,
            result.duplicates_in_batch,
            result.duplicates_existing,
            result.signals,
        )
    return result
