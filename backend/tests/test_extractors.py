"""Extraction engine tests: email, phone, GSTIN, social, SEO signals.

No network and no database — these run against real HTML fixtures.
"""

import pytest

from services.enrichment import extractors

SAMPLE_PAGE = """
<html>
<head>
  <title>Apex Switchgear Pvt Ltd | Panel Builders in Pune</title>
  <meta name="description" content="LT panels and switchgear manufacturer.">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta property="og:site_name" content="Apex Switchgear">
</head>
<body>
  <h1>LT Panel Manufacturing</h1>
  <img src="logo@2x.png" alt="Apex logo">
  <img src="plant.jpg">
  <p>Reach us at <a href="mailto:sales@apexswitchgear.com">sales@apexswitchgear.com</a>
     or info@apexswitchgear.com. Careers: hr.team@apexswitchgear.com</p>
  <p>Call <a href="tel:+919876543210">+91 98765 43210</a> or 020-4567-8901</p>
  <p>GSTIN: 27AAPFU0939F1ZV</p>
  <a href="https://www.linkedin.com/company/apex-switchgear">LinkedIn</a>
  <a href="https://facebook.com/apexswitchgear">Facebook</a>
  <a href="https://facebook.com/sharer/sharer.php?u=x">Share</a>
  <a href="/contact">Contact Us</a>
  <a href="/about">About</a>
  <script>var tracking = "noreply@sentry.io";</script>
</body>
</html>
"""


@pytest.fixture(scope="module")
def page_text():
    return extractors.html_to_text(SAMPLE_PAGE)


# --- Email ---------------------------------------------------------------


def test_extracts_emails_from_page(page_text):
    emails = extractors.extract_emails(page_text, SAMPLE_PAGE)
    assert "sales@apexswitchgear.com" in emails
    assert "info@apexswitchgear.com" in emails


def test_role_emails_rank_first(page_text):
    emails = extractors.extract_emails(page_text, SAMPLE_PAGE)
    # sales@/info@ are stable contact points; a personal address shouldn't lead.
    assert emails[0].split("@")[0] in ("sales", "info")


def test_script_contents_are_not_scraped_for_emails(page_text):
    """html_to_text strips <script>, so tracking addresses never surface."""
    assert "sentry.io" not in page_text
    assert not any("sentry" in e for e in extractors.extract_emails(page_text, SAMPLE_PAGE))


@pytest.mark.parametrize(
    "noise",
    ["logo@2x.png", "user@example.com", "you@yourdomain.com", "a@b", "x@y.123"],
)
def test_rejects_email_noise(noise):
    assert noise.lower() not in extractors.extract_emails(noise)


def test_mailto_href_is_captured_even_without_page_text():
    html = '<a href="mailto:owner@acme.co.in?subject=Hi">Mail</a>'
    assert "owner@acme.co.in" in extractors.extract_emails("", html)


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("sales@apexswitchgear.com", "sales@apexswitchgear.com"),
        ("  Sales@Apex.CO.IN  ", "sales@apex.co.in"),
        # Deliberately typed, so a reserved/placeholder-looking domain is kept:
        # the scraped-page noise filter must not apply to user-supplied input.
        ("good@example.com", "good@example.com"),
        ("you@yourdomain.com", "you@yourdomain.com"),
        ("not-an-email", None),
        ("a@b", None),
        ("x@y.123", None),
        ("logo@2x.png", None),
        ("", None),
        (None, None),
    ],
)
def test_user_supplied_emails_are_only_syntax_checked(raw, expected):
    """CSV cells and form fields are asserted by a human, not harvested.

    Running them through the page-scraping noise filter silently dropped real
    addresses the user asked us to store.
    """
    assert extractors.normalize_supplied_email(raw) == expected


def test_scraped_emails_still_reject_template_boilerplate():
    """The stricter filter must remain in force for page content."""
    page = "Contact you@yourdomain.com or user@example.com"
    assert extractors.extract_emails(page) == []


# --- Phone ---------------------------------------------------------------


def test_extracts_and_normalizes_indian_mobile(page_text):
    phones = extractors.extract_phones(page_text, SAMPLE_PAGE)
    assert "+919876543210" in phones


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("9876543210", "+919876543210"),
        ("+91 98765 43210", "+919876543210"),
        ("091-98765-43210", "+919876543210"),
        ("+91-9876543210", "+919876543210"),
        ("+1 415 555 2671", "+14155552671"),
    ],
)
def test_phone_normalization_variants(raw, expected):
    assert expected in extractors.extract_phones(raw)


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("020-4567-8901", "+912045678901"),   # 4-4 subscriber grouping
        ("020-45678901", "+912045678901"),
        ("022 24001234", "+912224001234"),
        ("0120-4567890", "+911204567890"),
        ("011 23456789", "+911123456789"),
    ],
)
def test_extracts_indian_landlines(raw, expected):
    """Many manufacturers publish only a landline, so these must not be dropped."""
    assert expected in extractors.extract_phones(raw)


def test_landline_from_page_is_extracted(page_text):
    phones = extractors.extract_phones(page_text, SAMPLE_PAGE)
    assert "+912045678901" in phones


def test_mobiles_rank_above_landlines(page_text):
    """Mobiles are the better outreach channel, so they take the first slot."""
    phones = extractors.extract_phones(page_text, SAMPLE_PAGE)
    assert phones.index("+919876543210") < phones.index("+912045678901")


@pytest.mark.parametrize("junk", ["2024", "12345", "0000", "199", "1234567"])
def test_rejects_non_phone_numbers(junk):
    assert extractors.extract_phones(junk) == []


@pytest.mark.parametrize(
    "junk",
    [
        "INV0001234567",          # digits embedded in an identifier
        "ORDER0001234567",
        "SKU 0012345678901234",
        "Invoice 2024-0001234",
        "Rs 1,20,000",
        "01.02.2024",
        "PIN 411001",
        "v1.2.3.4",
    ],
)
def test_rejects_digit_runs_that_are_not_phones(junk):
    """A fabricated phone number is worse than a missing one.

    These all previously produced false positives (or would have under a looser
    pattern): a leading-0 digit run inside a serial number is not a landline.
    """
    assert extractors.extract_phones(junk) == []


def test_tel_href_is_captured():
    html = '<a href="tel:+919812345678">Call</a>'
    assert "+919812345678" in extractors.extract_phones("", html)


# --- GSTIN --------------------------------------------------------------


def test_extracts_valid_gstin(page_text):
    result = extractors.extract_gstin(page_text)
    assert result.primary == "27AAPFU0939F1ZV"
    assert result.invalid_checksum == []


def test_canonical_gstin_validates():
    assert extractors.is_valid_gstin("27AAPFU0939F1ZV")


def test_checksum_is_enforced_not_just_shape():
    """A shape-valid GSTIN with a wrong check char must be rejected."""
    assert not extractors.is_valid_gstin("27AAPFU0939F1ZA")


def test_all_wrong_check_characters_are_rejected():
    alphabet = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    first14 = "27AAPFU0939F1Z"
    correct = extractors.gstin_checksum_char(first14)
    accepted = [c for c in alphabet if c != correct and extractors.is_valid_gstin(first14 + c)]
    assert accepted == []


def test_checksum_round_trip_is_self_consistent():
    """Appending our computed check char must always yield a valid GSTIN."""
    for first14 in ("29AAGCB7383J1Z", "07AAACH7409R1Z", "19AABCT1332L1Z", "33QPTGD6812B1Z"):
        candidate = first14 + extractors.gstin_checksum_char(first14)
        assert extractors.is_valid_gstin(candidate), candidate


@pytest.mark.parametrize(
    "bad",
    [
        "",
        "27AAPFU0939F1Z",          # too short
        "00AAPFU0939F1ZV",         # invalid state code 00
        "40AAPFU0939F1ZV",         # state code out of range
        "27AAPFU0939F1YV",         # 14th char must be Z
        "27aapfu0939f1zv!",        # junk
    ],
)
def test_rejects_invalid_gstins(bad):
    assert not extractors.is_valid_gstin(bad)


def test_invalid_checksum_candidates_are_reported_not_dropped():
    """Surfacing these makes a real format change visible in logs."""
    result = extractors.extract_gstin("Old: 27AAPFU0939F1ZA New: 27AAPFU0939F1ZV")
    assert result.valid == ["27AAPFU0939F1ZV"]
    assert result.invalid_checksum == ["27AAPFU0939F1ZA"]


# --- Social links -------------------------------------------------------


def test_extracts_social_handles():
    links = {s["platform"]: s for s in extractors.extract_social_links(SAMPLE_PAGE)}
    assert links["LinkedIn"]["found"] is True
    assert "apex-switchgear" in links["LinkedIn"]["handle"]
    assert links["Facebook"]["found"] is True


def test_share_widgets_are_not_treated_as_profiles():
    html = '<a href="https://facebook.com/sharer/sharer.php?u=x">Share</a>'
    links = {s["platform"]: s for s in extractors.extract_social_links(html)}
    assert links["Facebook"]["found"] is False


def test_all_platforms_always_present_for_stable_frontend_shape():
    links = extractors.extract_social_links("<html></html>")
    assert {s["platform"] for s in links} == {"LinkedIn", "Facebook", "Instagram", "X"}
    assert all(s["found"] is False for s in links)


# --- Company name & SEO -------------------------------------------------


def test_prefers_og_site_name_for_company():
    assert extractors.extract_company_name(SAMPLE_PAGE, "apexswitchgear.com") == "Apex Switchgear"


def test_falls_back_to_domain_when_no_metadata():
    assert extractors.extract_company_name("", "acme-switchgear.co.in") == "Acme Switchgear"


def test_title_marketing_suffix_is_trimmed():
    html = "<html><head><title>Nova Panels | Best in Pune</title></head></html>"
    assert extractors.extract_company_name(html, "nova.com") == "Nova Panels"


def test_seo_signals_reflect_real_page_content():
    signals = extractors.extract_seo_signals(SAMPLE_PAGE)
    assert signals["has_title"] is True
    assert signals["has_meta_description"] is True
    assert signals["has_h1"] is True
    assert signals["has_viewport"] is True
    assert signals["image_count"] == 2
    assert signals["images_with_alt"] == 1


def test_seo_score_ranges_and_ordering():
    rich = extractors.score_seo(extractors.extract_seo_signals(SAMPLE_PAGE))
    bare = extractors.score_seo(extractors.extract_seo_signals("<html><body>hi</body></html>"))
    assert 0 <= bare < rich <= 100
