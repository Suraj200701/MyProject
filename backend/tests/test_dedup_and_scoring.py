"""Deduplication and AI lead scoring.

Dedup's design bias is **under-merge rather than over-merge**: a duplicate row is
a visible, fixable annoyance, whereas a false merge silently destroys a real
lead. Several tests below exist specifically to pin that bias down, so a later
"improvement" to the threshold can't quietly start merging distinct businesses.

Scoring is asserted on *ordering and reasons*, not on exact numbers — the weights
are a tuning decision, but "a contactable lead outranks an uncontactable one"
is the actual contract.
"""

import uuid

import pytest
from sqlalchemy import select

from models.lead import Company, Lead
from models.organization import Organization
from services.enrichment import dedup, scoring
from services.providers.base import NormalizedLead
from services.providers.http import PermanentProviderError

asyncio_test = pytest.mark.asyncio(loop_scope="session")


def lead(name: str, **kw) -> NormalizedLead:
    return NormalizedLead(company_name=name, **kw)


async def _org_id(session) -> uuid.UUID:
    stmt = select(Organization).order_by(Organization.created_at.desc()).limit(1)
    return (await session.execute(stmt)).scalar_one().id


# --- Normalization -------------------------------------------------------


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("Acme Private Limited", "acme"),
        ("ACME Pvt Ltd", "acme"),
        ("Acme Pvt. Ltd.", "acme"),
        ("Acme Ltd", "acme"),
        ("Acme LLP", "acme"),
        ("Acme Inc", "acme"),
        ("Acme Pvt Ltd Company", "acme"),   # stacked suffixes
        ("Acme & Sons", "acme"),
        ("Acme and Sons", "acme"),
        ("Acme & Co", "acme"),
        ("Acme and Co", "acme"),
        ("  Acme   Engineering  ", "acme engineering"),
        # A conjunction mid-name is part of the name, not a suffix.
        ("Smith and Wesson Ltd", "smith and wesson"),
    ],
)
def test_company_name_normalization(raw, expected):
    assert dedup.normalize_company_name(raw) == expected


@pytest.mark.parametrize("pair", [("Acme & Sons", "Acme and Sons"), ("Acme & Co", "Acme and Co")])
def test_ampersand_and_and_normalize_identically(pair):
    """Both spellings are the same company, so they must deduplicate together.

    They did not before: punctuation was stripped before suffix matching, which
    made every '&'-form entry in the suffix list unreachable.
    """
    assert dedup.normalize_company_name(pair[0]) == dedup.normalize_company_name(pair[1])


def test_the_most_specific_suffix_wins():
    """Shortest-first matching left "acme and co" as "acme and"."""
    assert dedup.normalize_company_name("Acme and Co") == "acme"


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("https://www.acme.com/contact", "acme.com"),
        ("acme.com", "acme.com"),
        ("http://shop.acme.co.in", "acme.co.in"),
        ("www.acme.co.uk", "acme.co.uk"),
        ("", ""),
        (None, ""),
    ],
)
def test_domain_normalization(raw, expected):
    assert dedup.normalize_domain(raw) == expected


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("+919876543210", "9876543210"),
        ("09876543210", "9876543210"),
        ("9876543210", "9876543210"),
        ("+91 98765 43210", "9876543210"),
    ],
)
def test_phone_keys_collapse_formatting(raw, expected):
    assert dedup.normalize_phone_key(raw) == expected


def test_city_normalization_ignores_country_suffix():
    assert dedup.normalize_city("Pune, India") == "pune"
    assert dedup.normalize_city("pune") == "pune"


# --- In-batch dedup: the priority chain ---------------------------------


def test_gstin_match_merges_even_when_names_differ():
    """A government registration number is definitive."""
    result = dedup.dedupe_within_batch([
        lead("Apex Switchgear Pvt Ltd", gst_number="27AAPFU0939F1ZV"),
        lead("Totally Different Trading Name", gst_number="27AAPFU0939F1ZV"),
    ])
    assert len(result.unique) == 1
    assert result.signals == {"gstin": 1}


def test_domain_match_merges():
    result = dedup.dedupe_within_batch([
        lead("Apex Switchgear", website="https://apexswitchgear.com"),
        lead("Apex Switch Gear Pvt Ltd", website="http://www.apexswitchgear.com/about"),
    ])
    assert len(result.unique) == 1
    assert result.signals == {"domain": 1}


def test_phone_match_merges():
    result = dedup.dedupe_within_batch([
        lead("Nova Panels", phone="+919876543210"),
        lead("Nova Control Panels", phone="09876543210"),
    ])
    assert len(result.unique) == 1
    assert result.signals == {"phone": 1}


def test_name_and_city_match_merges_legal_suffix_variants():
    result = dedup.dedupe_within_batch([
        lead("Apex Switchgear Pvt Ltd", city="Pune"),
        lead("Apex Switchgear Private Limited", city="Pune, India"),
    ])
    assert len(result.unique) == 1
    assert result.signals == {"name+city": 1}


def test_same_name_in_different_cities_stays_separate():
    """Two genuinely different businesses can share a name."""
    result = dedup.dedupe_within_batch([
        lead("Apex Engineering", city="Pune"),
        lead("Apex Engineering", city="Chennai"),
    ])
    assert len(result.unique) == 2
    assert result.duplicates_in_batch == 0


def test_similar_but_distinct_names_are_not_merged():
    """Under-merge bias: these are different companies."""
    result = dedup.dedupe_within_batch([
        lead("Apex Switchgear", city="Pune"),
        lead("Apex Motors", city="Pune"),
    ])
    assert len(result.unique) == 2


def test_leads_with_no_shared_signal_are_kept():
    result = dedup.dedupe_within_batch([lead("A Ltd"), lead("B Ltd"), lead("C Ltd")])
    assert len(result.unique) == 3


def test_a_lead_with_only_a_name_and_no_city_never_merges():
    """No city means the name comparison is not allowed to run."""
    result = dedup.dedupe_within_batch([lead("Apex Switchgear"), lead("Apex Switchgear")])
    assert len(result.unique) == 2


# --- Merge semantics ----------------------------------------------------


def test_merge_combines_fields_from_both_records():
    """A Places record (coords, rating) + a Bing record (website) = one rich lead."""
    result = dedup.dedupe_within_batch([
        lead("Apex Switchgear", city="Pune", lat=18.5, lng=73.8, rating=4.5, phone="+919876543210"),
        lead("Apex Switchgear Pvt Ltd", city="Pune", website="https://apexswitchgear.com",
             email="sales@apexswitchgear.com", gst_number="27AAPFU0939F1ZV"),
    ])
    merged = result.unique[0]
    assert merged.lat == 18.5
    assert merged.rating == 4.5
    assert merged.website == "https://apexswitchgear.com"
    assert merged.email == "sales@apexswitchgear.com"
    assert merged.gst_number == "27AAPFU0939F1ZV"
    assert merged.phone == "+919876543210"


def test_merge_never_overwrites_an_existing_value():
    result = dedup.dedupe_within_batch([
        lead("Apex", city="Pune", email="first@apex.com"),
        lead("Apex", city="Pune", email="second@apex.com"),
    ])
    assert result.unique[0].email == "first@apex.com"


def test_merge_records_every_contributing_source():
    """Provenance must survive the merge for auditability."""
    a = lead("Apex", city="Pune", source_provider="Google Places")
    b = lead("Apex", city="Pune", source_provider="Bing Search")
    result = dedup.dedupe_within_batch([a, b])
    assert set(result.unique[0].raw["merged_sources"]) == {"Google Places", "Bing Search"}


def test_merge_unions_tags():
    result = dedup.dedupe_within_batch([
        lead("Apex", city="Pune", tags=["Electrical"]),
        lead("Apex", city="Pune", tags=["Electrical", "Manufacturer"]),
    ])
    assert sorted(result.unique[0].tags) == ["Electrical", "Manufacturer"]


def test_transitive_duplicates_are_caught_after_a_merge():
    """The survivor's fingerprint is refreshed, so a domain gained by merging
    still matches a later record in the same batch."""
    result = dedup.dedupe_within_batch([
        lead("Apex Switchgear", city="Pune"),
        lead("Apex Switchgear Pvt Ltd", city="Pune", website="https://apexswitchgear.com"),
        lead("Completely Other Name", website="https://apexswitchgear.com"),
    ])
    assert len(result.unique) == 1


def test_threshold_is_configurable_per_call():
    pair = [lead("Apex Switchgear", city="Pune"), lead("Apex Switch", city="Pune")]
    assert len(dedup.dedupe_within_batch(pair, name_threshold=0.99).unique) == 2
    assert len(dedup.dedupe_within_batch(pair, name_threshold=0.60).unique) == 1


# --- Dedup against existing rows (DB) -----------------------------------


@asyncio_test
async def test_existing_lead_is_detected_by_gstin(db_session, signed_up_user):
    org_id = await _org_id(db_session)
    company = Company(name="Apex Switchgear Pvt Ltd", gst_number="27AAPFU0939F1ZV", city="Pune")
    db_session.add(company)
    await db_session.flush()
    db_session.add(Lead(organization_id=org_id, company_id=company.id, lead_score=50, status="new"))
    await db_session.commit()

    result = await dedup.deduplicate(
        db_session, org_id, [lead("Renamed Trading Co", gst_number="27AAPFU0939F1ZV", city="Pune")]
    )
    assert result.unique == []
    assert result.duplicates_existing == 1
    assert result.signals == {"existing:gstin": 1}


@asyncio_test
async def test_existing_lead_is_detected_by_domain(db_session, signed_up_user):
    org_id = await _org_id(db_session)
    company = Company(name="Nova Panels", website="https://www.novapanels.co.in/", city="Thane")
    db_session.add(company)
    await db_session.flush()
    db_session.add(Lead(organization_id=org_id, company_id=company.id, lead_score=50, status="new"))
    await db_session.commit()

    result = await dedup.deduplicate(
        db_session, org_id, [lead("Nova Control Panels", website="http://novapanels.co.in/contact")]
    )
    assert result.duplicates_existing == 1


@asyncio_test
async def test_existing_matches_expose_the_matched_lead_id(db_session, signed_up_user):
    """Callers that would rather enrich the existing row need its id."""
    org_id = await _org_id(db_session)
    company = Company(name="Apex", gst_number="27AAPFU0939F1ZV", city="Pune")
    db_session.add(company)
    await db_session.flush()
    existing = Lead(organization_id=org_id, company_id=company.id, lead_score=50, status="new")
    db_session.add(existing)
    await db_session.commit()

    result = await dedup.deduplicate(
        db_session, org_id, [lead("Apex", gst_number="27AAPFU0939F1ZV", city="Pune")]
    )
    assert [lead_id for _, lead_id in result.existing_matches] == [existing.id]


@asyncio_test
async def test_another_organizations_leads_are_not_treated_as_duplicates(db_session, signed_up_user, client):
    """Dedup must never leak across tenants."""
    org_id = await _org_id(db_session)
    owner_id = (
        await db_session.execute(select(Organization.owner_id).where(Organization.id == org_id))
    ).scalar_one()
    other_org = Organization(name=f"Other Org {uuid.uuid4().hex[:8]}", owner_id=owner_id)
    db_session.add(other_org)
    company = Company(name="Apex", gst_number="27AAPFU0939F1ZV", city="Pune")
    db_session.add(company)
    await db_session.flush()
    db_session.add(Lead(organization_id=other_org.id, company_id=company.id, lead_score=50, status="new"))
    await db_session.commit()

    result = await dedup.deduplicate(
        db_session, org_id, [lead("Apex", gst_number="27AAPFU0939F1ZV", city="Pune")]
    )
    assert len(result.unique) == 1
    assert result.duplicates_existing == 0


@asyncio_test
async def test_a_genuinely_new_lead_survives(db_session, signed_up_user):
    org_id = await _org_id(db_session)
    result = await dedup.deduplicate(
        db_session, org_id, [lead("Brand New Co", website="https://brandnew.example", city="Pune")]
    )
    assert len(result.unique) == 1
    assert result.total_removed == 0


@asyncio_test
async def test_dedup_can_be_disabled(db_session, signed_up_user, monkeypatch):
    org_id = await _org_id(db_session)
    monkeypatch.setattr(dedup.settings, "DEDUP_ENABLED", False, raising=False)
    duplicates = [lead("Apex", city="Pune"), lead("Apex", city="Pune")]
    result = await dedup.deduplicate(db_session, org_id, duplicates)
    assert len(result.unique) == 2


# --- Signal-based scoring -----------------------------------------------


def test_contactable_lead_outranks_an_uncontactable_one():
    reachable = lead("A", email="s@a.com", phone="+919876543210", website="https://a.com")
    bare = lead("B")
    assert scoring.score_lead_by_signals(reachable) > scoring.score_lead_by_signals(bare)


def test_scoring_is_deterministic():
    """Not a placeholder: the same lead must always score the same."""
    subject = lead("A", email="s@a.com", city="Pune", rating=4.4)
    scores = {scoring.score_lead_by_signals(subject) for _ in range(20)}
    assert len(scores) == 1


def test_every_signal_can_only_help():
    base = lead("A")
    baseline = scoring.score_lead_by_signals(base)
    for field, value in (
        ("email", "s@a.com"), ("phone", "+919876543210"),
        ("website", "https://a.com"), ("gst_number", "27AAPFU0939F1ZV"),
    ):
        enriched = lead("A", **{field: value})
        assert scoring.score_lead_by_signals(enriched) > baseline, field


def test_scores_stay_within_one_to_hundred():
    everything = lead(
        "A", email="s@a.com", phone="+919876543210", website="https://a.com",
        gst_number="27AAPFU0939F1ZV", rating=5.0, industry="Electrical", company_type="Manufacturer",
        city="Pune", country="India", lat=1.0, lng=2.0, contact_name="R", revenue_band="10-50Cr",
    )
    assert scoring.score_lead_by_signals(everything, "Electrical") == 100
    assert scoring.score_lead_by_signals(lead("A")) >= 1


def test_a_low_rating_does_not_subtract():
    """Few reviews shouldn't be punished as if they were bad reviews."""
    assert scoring.score_lead_by_signals(lead("A", rating=1.0)) == scoring.score_lead_by_signals(lead("A"))


def test_industry_match_adds_only_on_a_real_match():
    subject = lead("A", industry="Electrical Equipment")
    assert scoring.score_lead_by_signals(subject, "Electrical") > scoring.score_lead_by_signals(subject, "Textiles")


def test_summary_states_the_reasons_for_the_score():
    subject = lead("Apex Switchgear", email="s@a.com", phone="+91987", city="Pune",
                   industry="Electrical", source_provider="Google Places")
    summary = scoring.build_summary_from_signals(subject, scoring.score_lead_by_signals(subject))
    assert "Apex Switchgear" in summary
    assert "email" in summary and "phone" in summary
    assert "Google Places" in summary


def test_summary_admits_when_there_are_no_contact_details():
    summary = scoring.build_summary_from_signals(lead("Ghost Co"), 10)
    assert "No direct contact details" in summary


# --- LLM scoring path ---------------------------------------------------


@asyncio_test
async def test_llm_scores_are_used_when_configured(monkeypatch):
    leads = [lead("A", email="a@a.com"), lead("B")]

    async def fake_request_json(*a, **k):
        return {
            "choices": [{"message": {"content": '{"scores":[{"id":0,"score":91,"summary":"Strong fit."},'
                                                '{"id":1,"score":12,"summary":"Weak."}]}'}}]
        }, 300

    monkeypatch.setattr(scoring.settings, "AI_SCORING_ENABLED", True, raising=False)
    monkeypatch.setattr(scoring.settings, "OPENAI_API_KEY", "sk-test", raising=False)
    monkeypatch.setattr(scoring, "request_json", fake_request_json)

    results = await scoring.score_leads(leads)
    assert results == [(91, "Strong fit."), (12, "Weak.")]


@asyncio_test
async def test_llm_failure_falls_back_to_signal_scores(monkeypatch):
    """An LLM outage must degrade quality, not break the search."""
    async def failing(*a, **k):
        raise PermanentProviderError("Authentication rejected (401)")

    monkeypatch.setattr(scoring.settings, "AI_SCORING_ENABLED", True, raising=False)
    monkeypatch.setattr(scoring.settings, "OPENAI_API_KEY", "sk-test", raising=False)
    monkeypatch.setattr(scoring, "request_json", failing)

    subject = lead("A", email="a@a.com", phone="+919876543210")
    results = await scoring.score_leads([subject])
    assert results == [(scoring.score_lead_by_signals(subject), scoring.build_summary_from_signals(
        subject, scoring.score_lead_by_signals(subject)))]


@asyncio_test
async def test_a_partial_llm_response_is_completed_with_signal_scores(monkeypatch):
    async def partial(*a, **k):
        return {"choices": [{"message": {"content": '{"scores":[{"id":0,"score":88,"summary":"Good."}]}'}}]}, 100

    monkeypatch.setattr(scoring.settings, "AI_SCORING_ENABLED", True, raising=False)
    monkeypatch.setattr(scoring.settings, "OPENAI_API_KEY", "sk-test", raising=False)
    monkeypatch.setattr(scoring, "request_json", partial)

    results = await scoring.score_leads([lead("A"), lead("B", email="b@b.com")])
    assert results[0] == (88, "Good.")
    assert results[1][0] == scoring.score_lead_by_signals(lead("B", email="b@b.com"))


@asyncio_test
async def test_llm_garbage_is_rejected_rather_than_stored(monkeypatch):
    async def garbage(*a, **k):
        return {"choices": [{"message": {"content": "not json at all"}}]}, 50

    monkeypatch.setattr(scoring.settings, "AI_SCORING_ENABLED", True, raising=False)
    monkeypatch.setattr(scoring.settings, "OPENAI_API_KEY", "sk-test", raising=False)
    monkeypatch.setattr(scoring, "request_json", garbage)

    results = await scoring.score_leads([lead("A")])
    assert results[0][0] == scoring.score_lead_by_signals(lead("A"))


@asyncio_test
async def test_out_of_range_llm_scores_are_clamped(monkeypatch):
    async def wild(*a, **k):
        return {"choices": [{"message": {"content":
                '{"scores":[{"id":0,"score":5000,"summary":"x"},{"id":1,"score":-40,"summary":"y"}]}'}}]}, 50

    monkeypatch.setattr(scoring.settings, "AI_SCORING_ENABLED", True, raising=False)
    monkeypatch.setattr(scoring.settings, "OPENAI_API_KEY", "sk-test", raising=False)
    monkeypatch.setattr(scoring, "request_json", wild)

    results = await scoring.score_leads([lead("A"), lead("B")])
    assert results[0][0] == 100
    assert results[1][0] == 1


@asyncio_test
async def test_llm_indexes_outside_the_batch_are_ignored(monkeypatch):
    """A model hallucinating an id must not write a score onto the wrong lead."""
    async def bad_ids(*a, **k):
        return {"choices": [{"message": {"content":
                '{"scores":[{"id":99,"score":100,"summary":"nope"}]}'}}]}, 50

    monkeypatch.setattr(scoring.settings, "AI_SCORING_ENABLED", True, raising=False)
    monkeypatch.setattr(scoring.settings, "OPENAI_API_KEY", "sk-test", raising=False)
    monkeypatch.setattr(scoring, "request_json", bad_ids)

    results = await scoring.score_leads([lead("A")])
    assert results[0][0] == scoring.score_lead_by_signals(lead("A"))


@asyncio_test
async def test_llm_is_not_called_without_a_key(monkeypatch):
    called = {"n": 0}

    async def spy(*a, **k):
        called["n"] += 1
        return {}, 0

    monkeypatch.setattr(scoring.settings, "OPENAI_API_KEY", "", raising=False)
    monkeypatch.setattr(scoring, "request_json", spy)

    await scoring.score_leads([lead("A")])
    assert called["n"] == 0


@asyncio_test
async def test_empty_batch_scores_to_empty():
    assert await scoring.score_leads([]) == []


def test_prompt_payload_excludes_raw_provider_blobs_and_pii():
    """Only derived booleans go to the model — not scraped emails/phones."""
    payload = scoring._lead_to_prompt_payload(
        0, lead("A", email="secret@a.com", phone="+919876543210", raw={"internal": "blob"})
    )
    assert payload["has_email"] is True
    assert "secret@a.com" not in str(payload)
    assert "+919876543210" not in str(payload)
    assert "blob" not in str(payload)
