"""AI lead scoring and summary generation.

Two paths, both operating on **real** lead data:

1. **LLM scoring** (when `OPENAI_API_KEY` is set) — sends a compact batch of
   lead attributes to a chat-completions endpoint and asks for a 0-100 fit score
   plus a one-line rationale. Batched (not one call per lead) to keep token
   spend and latency proportional to a search rather than to its result count.

2. **Signal-based scoring** (the fallback) — a deterministic weighted model over
   observable facts: contactability (email/phone), verification (GSTIN), web
   presence, rating, and how completely the record is filled in. This is a
   legitimate heuristic over real data, **not** placeholder output: the same
   lead always scores the same, and the score moves for defensible reasons. It
   is also what runs when the LLM is unavailable, so scoring never fails a
   search.

The LLM result is clamped and validated against the same 0-100 range; a model
that returns nonsense degrades to the heuristic for that lead rather than
writing a garbage score.
"""

from __future__ import annotations

import json
import logging

from config.settings import settings
from services.providers.base import NormalizedLead
from services.providers.http import (
    PermanentProviderError,
    TransientProviderError,
    request_json,
)

logger = logging.getLogger("leadmaster.scoring")

# --- Signal-based scorer --------------------------------------------------

# Weights sum to 100. Contactability dominates because a lead you cannot reach
# has no pipeline value regardless of how attractive the company looks.
_WEIGHTS = {
    "has_email": 26,
    "has_phone": 22,
    "has_website": 14,
    "has_gstin": 12,
    "rating": 12,
    "completeness": 8,
    "industry_match": 6,
}

_COMPLETENESS_FIELDS = (
    "industry", "company_type", "city", "country", "lat", "lng", "contact_name", "revenue_band",
)


def score_lead_by_signals(lead: NormalizedLead, target_industry: str | None = None) -> int:
    """Deterministic 0-100 score from observable lead attributes."""
    score = 0.0

    if lead.email:
        score += _WEIGHTS["has_email"]
    if lead.phone:
        score += _WEIGHTS["has_phone"]
    if lead.website:
        score += _WEIGHTS["has_website"]
    if lead.gst_number:
        score += _WEIGHTS["has_gstin"]

    # Ratings are 0-5; anything below 3 contributes nothing rather than
    # negatively, since a low rating may just reflect few reviews.
    if lead.rating is not None:
        normalized = max(0.0, (float(lead.rating) - 3.0) / 2.0)
        score += _WEIGHTS["rating"] * min(1.0, normalized)

    present = sum(1 for field in _COMPLETENESS_FIELDS if getattr(lead, field, None) not in (None, ""))
    score += _WEIGHTS["completeness"] * (present / len(_COMPLETENESS_FIELDS))

    if target_industry and lead.industry:
        if target_industry.strip().lower() in lead.industry.strip().lower():
            score += _WEIGHTS["industry_match"]

    return max(1, min(100, round(score)))


def build_summary_from_signals(lead: NormalizedLead, score: int) -> str:
    """One-line rationale describing what the score is actually based on."""
    intent = "high-intent" if score >= 75 else "moderate-intent" if score >= 50 else "low-signal"
    have: list[str] = []
    if lead.email:
        have.append("email")
    if lead.phone:
        have.append("phone")
    if lead.gst_number:
        have.append("verified GSTIN")
    if lead.website:
        have.append("website")

    contact_note = f"Contactable via {', '.join(have)}." if have else "No direct contact details found yet."
    location = f" in {lead.city}" if lead.city else ""
    industry = f" {lead.industry}" if lead.industry else ""
    source = f" Sourced via {lead.source_provider}." if lead.source_provider else ""

    return (
        f"{lead.company_name} is a {intent}{industry} lead{location}. "
        f"{contact_note}{source}"
    )[:1000]


# --- LLM scorer -----------------------------------------------------------

_SYSTEM_PROMPT = (
    "You are a B2B lead qualification assistant for an industrial/electrical "
    "sales team. For each lead, return a fit score from 0-100 and a one-sentence "
    "rationale grounded ONLY in the attributes provided. Do not invent facts. "
    "Higher scores mean easier to contact and better matched to the target "
    "industry. Respond with JSON only."
)


def _lead_to_prompt_payload(index: int, lead: NormalizedLead) -> dict:
    """Only the attributes the model should reason over — no raw provider blobs."""
    return {
        "id": index,
        "company": lead.company_name,
        "industry": lead.industry,
        "city": lead.city,
        "country": lead.country,
        "has_email": bool(lead.email),
        "has_phone": bool(lead.phone),
        "has_website": bool(lead.website),
        "has_gstin": bool(lead.gst_number),
        "rating": lead.rating,
        "company_type": lead.company_type,
    }


async def score_leads_with_llm(
    leads: list[NormalizedLead], target_industry: str | None = None
) -> dict[int, tuple[int, str]]:
    """Scores a batch via the LLM. Returns `{index: (score, summary)}`.

    Returns an empty dict on any failure — the caller then falls back to
    signal-based scoring, so a provider outage degrades quality rather than
    breaking the search.
    """
    if not leads:
        return {}

    payload = {
        "model": settings.AI_SCORING_MODEL,
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "target_industry": target_industry,
                        "leads": [_lead_to_prompt_payload(i, lead) for i, lead in enumerate(leads)],
                        "response_schema": {
                            "scores": [{"id": "int", "score": "int 0-100", "summary": "string"}]
                        },
                    }
                ),
            },
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.2,
    }

    try:
        response, _latency = await request_json(
            "POST",
            f"{settings.OPENAI_BASE_URL.rstrip('/')}/chat/completions",
            json_body=payload,
            headers={
                "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
                "Content-Type": "application/json",
            },
            timeout=settings.AI_SCORING_TIMEOUT_SECONDS,
        )
    except (TransientProviderError, PermanentProviderError) as exc:
        logger.warning("AI scoring unavailable, using signal-based scores: %s", exc)
        return {}

    try:
        content = response["choices"][0]["message"]["content"]
        parsed = json.loads(content)
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        logger.warning("Could not parse AI scoring response: %s", exc)
        return {}

    scores: dict[int, tuple[int, str]] = {}
    for entry in parsed.get("scores") or []:
        try:
            index = int(entry["id"])
            raw_score = int(entry["score"])
        except (KeyError, TypeError, ValueError):
            continue
        if not 0 <= index < len(leads):
            continue
        summary = str(entry.get("summary") or "").strip()[:1000]
        scores[index] = (max(1, min(100, raw_score)), summary)

    return scores


# --- Public entry point --------------------------------------------------


def ai_scoring_available() -> bool:
    return bool(settings.AI_SCORING_ENABLED and settings.OPENAI_API_KEY)


async def score_leads(
    leads: list[NormalizedLead], target_industry: str | None = None
) -> list[tuple[int, str]]:
    """Scores every lead, returning `[(score, summary)]` aligned to input order.

    Uses the LLM when configured and falls back per-lead to signal-based scoring
    for anything the model didn't return — so a partial LLM response still
    yields a complete, usable result set.
    """
    if not leads:
        return []

    llm_scores: dict[int, tuple[int, str]] = {}
    if ai_scoring_available():
        batch = leads[: settings.AI_SCORING_MAX_LEADS_PER_SEARCH]
        llm_scores = await score_leads_with_llm(batch, target_industry)

    results: list[tuple[int, str]] = []
    for index, lead in enumerate(leads):
        if index in llm_scores:
            score, summary = llm_scores[index]
            if not summary:
                summary = build_summary_from_signals(lead, score)
            results.append((score, summary))
        else:
            score = score_lead_by_signals(lead, target_industry)
            results.append((score, build_summary_from_signals(lead, score)))
    return results
