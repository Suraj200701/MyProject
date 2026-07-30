# Migration Analysis: Lead Search, Website Scanner, Export

**Status: analysis only — no code has been written.** This document is
scoped strictly to the three modules named in the request. Nothing here
proposes touching auth, payments, PostgreSQL models for other domains,
Redis, notifications, team management, settings, admin APIs, analytics
APIs, Docker config, the existing test suite, `docs/API_TESTING.md`,
the Postman collection, or `docs/FRONTEND_BACKEND_MAPPING.md` — those
stay exactly as they are.

This is a new, additive file (`docs/MIGRATION_PLAN_search_scanner_export.md`)
and does not modify anything else.

## Ground truth this analysis is based on

Re-read directly from the live code (not from memory) before writing this:

- `backend/services/search_service.py` — `run_search()` and `scan_website()`
- `backend/api/v1/search.py` — the only router touching these two modules
- `backend/models/search.py` — `ApiProvider`, `Search`, `SearchProviderRun`, `WebsiteScan`, `Export`
- `backend/services/storage.py` — the existing file-storage abstraction
- `backend/requirements.txt` — confirmed which packages are/aren't already installed
- `backend/config/settings.py` — confirmed which env vars already exist
- `backend/tests/test_search_and_rbac.py` — the existing tests that exercise these two modules
- `src/components/export/export-wizard.tsx`, `src/components/export/types.ts` — frontend Export contract

---

## 1. Migration plan

### 1.1 Lead Search

| Phase | Scope | Risk |
|---|---|---|
| **0 — Foundation** | Introduce a `SearchProviderClient` protocol (one `async def search(query, location, filters) -> list[RawResult]` method) that both a real provider adapter and the *existing* placeholder generator implement. Wrap `run_search()`'s per-provider loop to call `client.search(...)` per connected provider instead of always generating fake rows inline. | Low — pure refactor of `search_service.py`, no behavior change if no provider is marked `connected=True` yet (falls through to today's placeholder path). |
| **1 — First real provider (Google Places)** | Implement `GooglePlacesClient` calling the real Places API Text Search endpoint. Gate it behind `ApiProvider.connected` (already a column, currently always `False`/unused) so it only activates once explicitly turned on for that provider row. | Low-medium — one well-scoped external integration, reuses the `GOOGLE_MAPS_API_KEY` that already exists for the Map module. |
| **2 — Decide execution model** | Real provider calls (Places: ~200-500ms; IndiaMART/TradeIndia/JustDial: unknown, likely slower) may no longer fit comfortably inside one synchronous request once more than one real provider is live. Decide now (before building more providers) whether `POST /search` stays synchronous or becomes job-based (see [§8](#8-api-contract-changes-if-any)) — this affects every subsequent phase's shape. | Architectural decision point — needs your sign-off before Phase 3. |
| **3 — Additional providers** | IndiaMART, TradeIndia, JustDial, LinkedIn — each is its own partner-onboarding process (see [§6](#6-paid-api-requirements)), added one at a time behind the same `connected` gate. | Medium-high per provider — mostly business/legal lead time, not engineering time (see [§9](#9-risks-and-recommendations)). |
| **4 — Retire the placeholder** | Once every catalogued provider has a real adapter, either delete the placeholder generator or keep it behind an explicit `DEMO_MODE` flag for sales demos / offline dev (recommended — it's genuinely useful for that, and tests currently depend on similar deterministic behavior). | Low. |

### 1.2 Website Scanner

| Phase | Scope | Risk |
|---|---|---|
| **1 — Real fetch** | Replace the SHA-256-seeded RNG with an actual `httpx.AsyncClient().get(url)` call. Extract emails/phones via regex over the real HTML/text response (works with zero new paid dependencies). Derive `ssl_valid` from whether the HTTPS request actually succeeded (real signal, not random). | Low — self-contained, no paid API required. |
| **2 — Structured parsing** | Add an HTML parser (new dependency — see [§5](#5-new-environment-variables-required)/[§6](#6-paid-api-requirements)) to reliably pull `<meta>`/`<link>` tags and anchor `href`s for social-link detection, instead of regex-over-raw-text. GST-pattern regex logic carries over unchanged, just runs against real page text. | Low-medium. |
| **3 (optional) — Real SEO/perf scoring** | Swap the random `seo_score`/`load_time_ms` for a real call to Google PageSpeed Insights (free tier). | Low — optional, free API, but adds latency (PageSpeed audits take several seconds). |
| **4 — Confidence score** | Same formula shape as today (`positive_signals / total_signals`), just computed from real findings instead of RNG outputs. No change needed to the formula itself. | None — cosmetic swap of inputs. |

### 1.3 Export

This module **has no backend implementation today** — this is net-new
build, not a migration of existing logic, but scoped tightly to reuse
existing infrastructure rather than add anything new architecturally:

| Phase | Scope | Risk |
|---|---|---|
| **1 — CSV/JSON, synchronous** | New `api/v1/exports.py` + `services/export_service.py`. Generates CSV/JSON using Python's stdlib (`csv`, `json` — zero new dependencies), writes the file via the **existing, unmodified** `services/storage.py` abstraction, creates a real row in the **existing, unmodified** `Export` table. | Low — every piece of infrastructure this needs already exists and is being reused, not changed. |
| **2 — Excel + PDF** | Add Excel (needs `openpyxl`) and PDF (needs a rendering library) generation paths. | Low-medium — two new dependencies, no external service/API needed. |
| **3 — Background generation** | For large exports, move generation into a Celery task (**existing, unmodified** Celery infra) so the endpoint returns immediately with `status=processing` — this is exactly what `ExportStatus.PROCESSING` (already defined in `models/enums.py`, currently unused by anything) was modeled for. | Low — reuses existing job infrastructure, no new moving parts. |

---

## 2. Placeholder implementations that currently exist

Quoting the actual behavior, verified in code:

**Lead Search** (`search_service.run_search`): for every `ApiProvider` in
categories Search/Business/Maps (regardless of its `connected` flag —
that field is set but never checked), generates `random.randint(8, 45)`
fake "results found", then materializes up to 8 real `Company`+`Lead`
rows per provider by combining one of **10 name prefixes** × **8
suffixes** × **6 hardcoded cities**, with a random score 40-98. No
network call is made to any of the 7 catalogued providers.

**Website Scanner** (`search_service.scan_website`): seeds Python's
`random.Random` with `sha256(domain)` so the *same domain always produces
the same fake report* — but the target URL is **never fetched over the
network**. `ssl_valid`, `mobile_friendly`, `seo_score`, `load_time_ms`,
and the GST number are all derived purely from the domain-seeded RNG, not
from any real property of the site.

**Export**: does not exist server-side at all — no router, no service.
`src/components/export/export-wizard.tsx` simulates a 4-stage progress
bar with `setTimeout` and, on "Download", generates a client-side
`Blob` containing a two-line plain-text placeholder (`LeadMaster AI
export — {fileName}\nRows: {count}`) — **not** a real CSV/Excel/PDF/JSON
of any lead data.

---

## 3. Database changes required

| Module | Change | Type | Risk |
|---|---|---|---|
| Lead Search | *(none required to start)* | — | — |
| Lead Search (optional) | `Lead.raw_provider_payload JSONB NULL` — retain the original provider response for audit/debugging | Additive, nullable | Zero — new nullable column, no existing-row impact |
| Lead Search (only if async execution is chosen, §8) | A way to track job state — either a new `Search.task_id VARCHAR NULL` column, or none at all if relying on Celery's own result backend for status lookups | Additive, nullable (if added) | Zero |
| Website Scanner | **None** — `WebsiteScan` already has every column a real scan would populate (`ssl_valid`, `mobile_friendly`, `seo_score`, `load_time_ms`, `social_links` JSONB, etc.) | — | None — pure service-layer swap |
| Export | **None required** — `Export` already has `file_name`, `format`, `row_count`, `size_bytes`, `status`, `storage_path`, `expires_at` | — | None |
| Export (optional) | `Export.filters JSONB NULL` — record what source/filter/columns were used, for parity with `Search.filters` and for audit/support purposes | Additive, nullable | Zero |
| Cross-cutting (only if per-organization provider credentials are wanted) | `ApiProvider` is currently a **global** catalogue with no `organization_id` — storing an org's own IndiaMART account would need a new `organization_provider_credentials` table (`org_id`, `provider_id`, `encrypted_key`) | New table | Low, but see recommendation below — likely unnecessary for v1 |

**Recommendation on the cross-cutting item:** don't build per-org
credentials yet. Google Places, IndiaMART, etc. are naturally
platform-billed (LeadMaster pays the provider, not each customer
organization) in this product's model — a single shared, encrypted,
platform-level key per provider (stored in `ApiProvider.api_key_encrypted`,
which already exists and is already unused) is simpler and sufficient
until/unless a specific customer needs to bring their own provider
account.

Every change listed above is additive/nullable — **none require
touching or backfilling existing rows**, and none require a destructive
migration.

---

## 4. New API keys required

| Provider | Purpose | How it's obtained |
|---|---|---|
| Google Places API | Real lead search results | **Reuses the existing `GOOGLE_MAPS_API_KEY`** (same Google Cloud project) — just enable the "Places API" product on that key in Google Cloud Console. No new key needed. |
| Google PageSpeed Insights API | Real SEO/mobile-friendliness scoring (optional, scanner Phase 3) | Free tier; can reuse `GOOGLE_MAPS_API_KEY` if same GCP project, or issue a dedicated key |
| OpenAI (or another LLM provider) | Real AI-generated `ai_summary` text instead of the current templated string (`"{company} is a {high/moderate}-intent lead discovered via {provider}."`) | Self-serve at platform.openai.com |
| IndiaMART | Real search results from this provider | Requires an active IndiaMART **Seller/Partner account** — API access is granted through their business partner program, not instant self-serve signup |
| TradeIndia | Real search results from this provider | Same pattern — partner program, not self-serve |
| JustDial | Real search results from this provider | Same pattern — partner program, more restricted than the above two |
| LinkedIn (Sales Navigator / official API) | Real search results from this provider | Requires LinkedIn Partner Program approval — historically difficult for a new SaaS to obtain (see [§9](#9-risks-and-recommendations)) |
| A bot-blocking-proxy service (e.g. ScraperAPI, Bright Data) | Fallback for website-scanner targets that block plain `httpx` requests | Only needed if/when real-world testing shows target sites are blocking direct fetches — not certain to be needed, budget for it as a contingency |

---

## 5. New environment variables required

```
# Lead Search — real AI summaries
OPENAI_API_KEY=

# Lead Search — additional real providers (each needs partner approval first, see §4/§6)
INDIAMART_API_KEY=
INDIAMART_CRM_KEY=
TRADEINDIA_API_KEY=
TRADEINDIA_USER_ID=
JUSTDIAL_API_KEY=
LINKEDIN_CLIENT_ID=
LINKEDIN_CLIENT_SECRET=

# Cross-cutting — encrypting ApiProvider.api_key_encrypted at rest
# (that column already exists and is already unused/plaintext-capable today)
FIELD_ENCRYPTION_KEY=

# Website Scanner — optional real SEO scoring
GOOGLE_PAGESPEED_API_KEY=

# Website Scanner — optional bot-blocking fallback
SCRAPER_PROXY_API_KEY=

# Export — how long a generated file stays downloadable
# (maps to the already-existing but currently-unused Export.expires_at)
EXPORT_FILE_EXPIRE_HOURS=48
```

No new environment variables are needed for CSV/JSON export generation
(stdlib only), or for the Website Scanner's Phase 1 (real fetch uses
`httpx`, already installed, no key required).

**`GOOGLE_MAPS_API_KEY` — already exists, no addition needed** — flagging
this explicitly since Google Places is the recommended first real
provider and it rides on the existing key.

---

## 6. Paid API requirements

| Provider | Pricing model | Self-serve? |
|---|---|---|
| Google Places Text Search | Pay-per-request (~$32/1,000 requests under standard Google Maps Platform pricing; ~$200/mo free credit typically available) | **Yes** — sign up and get a key same-day |
| Google PageSpeed Insights | Free, quota-limited | Yes |
| OpenAI (gpt-4o-mini class) | Pay-per-token; short summaries are very cheap (~$0.15 / 1M input tokens) | Yes |
| IndiaMART | Not published per-call pricing — bundled into a paid Seller account (commonly an annual plan) before API access is even granted | **No** — business agreement required |
| TradeIndia | Similar partner-bundled pricing, not published per-call | **No** |
| JustDial | Similar, more restricted than the above two | **No** |
| LinkedIn Sales Navigator / official API | Enterprise partner tier — effectively unavailable without a negotiated partnership | **No**, and not recommended near-term (see §9) |
| Bot-blocking proxy (ScraperAPI/Bright Data class) | Pay-per-request or monthly tiers, only needed as a scanner fallback | Yes, if needed |

**Bottom line:** Google Places + OpenAI + PageSpeed can all be live
within a day of you providing keys — self-serve, cheap, no partner
negotiation. IndiaMART/TradeIndia/JustDial/LinkedIn are **business
development timelines, not engineering timelines** — code can be written
and ready, but won't function until those relationships exist.

---

## 7. Frontend compatibility impact

| Page | Impact | Detail |
|---|---|---|
| `src/app/dashboard/search/page.tsx` | **None if execution stays synchronous** (recommended for the Google-Places-only phase). **Contract change if/when job-based execution is introduced** (see §8) — the existing `SearchProgress` component already renders a staged per-provider progress UI today purely as decoration; moving to real async execution would make that UI *functionally real* instead of decorative, which is a UX upgrade, not a regression, but does require rewiring it to poll rather than just await one response. |
| `src/app/dashboard/scanner/page.tsx` | **None**, if `WebsiteScanOut`'s response shape is kept identical (recommended) — same fields, real values instead of hash-derived ones. The frontend's staged `ScanStepper` progress animation has the identical "decorative today, could become real later" characteristic as search, same recommendation: leave the contract alone, decide separately/later whether to make the progress UI real. |
| `src/app/dashboard/export/page.tsx` | **Purely additive** — this page currently makes zero backend calls, so wiring it to new endpoints breaks nothing that exists today. The export wizard's existing step structure (source → format → configure → review → progress → done) maps cleanly onto a `POST /exports` + poll `GET /exports/{id}` + `GET /exports/{id}/download` flow without a redesign. |

No changes to `docs/FRONTEND_BACKEND_MAPPING.md` are proposed as part of
this analysis — if/when implementation happens, that document's Search/
Scanner/Export sections would need a follow-up update to reflect the new
reality, but that's a separate, later step and out of scope for this
analysis-only pass.

---

## 8. API contract changes (if any)

| Endpoint | Change | Breaking? |
|---|---|---|
| `POST /search` | **Recommended: no change for Phase 1** (Google Places only) — stays synchronous, same `SearchOut` response shape, since Places responds in well under a second. | No |
| `POST /search` | **If/when slower providers are added** (IndiaMART etc.), recommend switching to: return `202 Accepted` + `{search_id, status: "running"}` immediately, with a **new** `GET /search/{id}` endpoint (doesn't exist today) to poll for completion/results. | **Yes** — response status code and shape both change; needs explicit versioning or coordinated frontend release, not a silent swap. |
| `POST /scan-website` | **No change recommended** — keep synchronous, same `WebsiteScanOut` shape. | No |
| `GET /providers` | **Optional addition**: `last_tested_at` / `last_error` fields, so the frontend's currently-decorative "Test Connection" button (per `docs/FRONTEND_BACKEND_MAPPING.md` §8) has real data to display. Purely additive (new optional fields), doesn't remove/rename anything existing. | No (additive only) |
| *(new)* `POST /exports` | Net-new endpoint. Recommend returning `202` + `{export_id, status: "processing"}` for anything beyond a trivial CSV, mirroring the pattern already established by the Files module (`GET /files/{id}/download`) rather than inventing a new response convention. | N/A — net-new, nothing to break |
| *(new)* `GET /exports`, `GET /exports/{id}`, `GET /exports/{id}/download` | Net-new endpoints, same pagination/detail/download pattern as `GET /files`. | N/A |

---

## 9. Risks and recommendations

**Legal / Terms-of-Service risk (LinkedIn specifically):** scraping
LinkedIn or using unofficial means to extract contact data violates
their Terms of Service and carries real exposure — account bans, cease-
and-desist, and in some jurisdictions CFAA-adjacent legal risk for
automated unauthorized access. **Recommendation: do not scrape LinkedIn.**
Only surface LinkedIn as a "real" provider if official Partner API
access is actually granted; otherwise leave it in the catalogue marked
unsupported/coming-soon rather than building around an assumption of
future approval.

**Data privacy risk:** real scraped/sourced lead data (emails, phone
numbers, GST numbers) is personal/business data subject to India's DPDP
Act and potentially GDPR for EU-adjacent contacts. **Recommendation:**
define a data retention and lawful-basis policy before enabling any real
provider broadly — this is a compliance decision for you to make, not
something to default silently in code.

**Cost & abuse risk:** the current placeholder gives users an unlimited,
instant, free-feeling "40 leads across 7 providers in one search"
experience. Real APIs cost real money per call. **Recommendation:** tie
real provider usage into the *already-built, unmodified* `CreditWallet`/
`Transaction` billing tables before enabling real search broadly, so
usage has a cost model from day one rather than retrofitting one after
users have gotten used to unlimited free searches.

**Reliability risk:** third-party APIs fail, time out, or change
response shape without notice. **Recommendation:** wrap every real
provider call in the `tenacity` retry library (already a dependency,
currently unused anywhere in the codebase) with a fallback to marking
that provider `ProviderStatus.DEGRADED` (enum value already exists,
currently unused) rather than failing the whole search when one provider
misbehaves.

**Bot-blocking risk (scanner):** many real sites block simple
`httpx`-style requests (Cloudflare challenges, etc.). Not every target
URL a user submits will be fetchable without a proxy service.
**Recommendation:** budget for a proxy fallback as a likely (not certain)
follow-up cost rather than assuming Phase 1's plain fetch will always
work.

**⚠️ Direct conflict with "do not modify existing tests":** two existing
assertions in `tests/test_search_and_rbac.py` are **inherently
incompatible** with real implementations and will need a deliberate
decision from you before any implementation work, not a silent change:

1. `test_website_scan_is_deterministic_per_domain` asserts that scanning
   the same domain twice yields the *same* `confidence_score` and
   `gst_number` — true by construction for the hash-seeded placeholder,
   but **cannot hold** once the scanner fetches a real, possibly-changing
   web page (a real site's content isn't guaranteed stable between two
   fetches).
2. `test_search_persists_real_leads` asserts `POST /search` returns
   `status == "completed"` synchronously in the same response — this
   breaks if/when the job-based execution model from §8 is adopted for
   slower providers.

Flagging both explicitly rather than deciding unilaterally: implementing
real search/scanning as described above **will** require updating these
two tests (not deleting the coverage — rewriting what they assert to
match the new, real behavior). Please confirm this is acceptable before
that implementation work begins, since it falls just outside the letter
of "don't modify existing tests" even though it's a necessary
consequence of the change you're asking for.

**Sequencing recommendation**, lowest-risk to highest-risk:

1. **Website Scanner real fetch** — no paid API, no partner approval, immediate concrete improvement, contained blast radius.
2. **Export (CSV/JSON, synchronous)** — no external dependency at all, pure engineering, highest confidence delivery.
3. **Lead Search via Google Places** — self-serve key already 90% in place (`GOOGLE_MAPS_API_KEY`), cheap, fast.
4. **Export (Excel/PDF, background jobs)** — builds on #2 once it's stable.
5. **Additional search providers (IndiaMART/TradeIndia/JustDial/LinkedIn)** — start the business-development conversations for these now if you want them, in parallel with 1-4, since their lead time is measured in weeks/months of partner approval, not engineering days — but don't block 1-4 waiting on them.

---

## Decisions needed from you before any code is written

1. **Search execution model**: stay synchronous for now (Google Places only), or design for job-based/async from the start?
2. **LinkedIn**: officially out of scope until Partner API access exists, or should it be dropped from the provider catalogue entirely?
3. **Test updates**: confirmed OK to update the two specific assertions named in §9 (not remove test coverage, rewrite it) once real implementations land?
4. **Which providers to actually pursue** beyond Google Places — worth starting IndiaMART/TradeIndia partner conversations now, given their lead time?
5. **Export formats for v1**: CSV+JSON only first, or is Excel/PDF needed immediately?
6. **Credit metering** (Addendum A-1): confirm it lands *before* any paid provider is switched on?
7. **Placeholder-row cleanup** (Addendum A-6): OK to purge demo-era `searches`/`leads`/`website_scans` per environment at cutover?

---

# Addendum — second code-level pass

A second review of the same files surfaced items not covered above. These
**extend** the analysis; nothing above is retracted. Two are blocking-grade
(A-1, A-2).

## A-1 🔴 Nothing in the codebase ever debits credits

§9 above recommends tying real usage into `CreditWallet`/`Transaction`.
Worth stating more sharply, because it is a prerequisite rather than a
follow-up:

- `TransactionType.CREDIT_USAGE` is defined at `models/enums.py:90` and
  **referenced nowhere else in the codebase** (verified by grep across all
  of `backend/`, excluding the generated migration).
- No code path anywhere decrements `CreditWallet.balance`.
  `services/billing_service.py` only ever *increments* it (lines 290, 318
  — plan grant and top-up).
- `GET /billing/usage` derives `credits_used` as
  `credits_limit - wallet.balance` (`billing_service.py:441`), so it
  currently reports **0 used, always** — by construction, not by accident.

Consequence: `POST /search` and `POST /scan-website` are unmetered. The
only limit is the global 60 req/min-per-IP in `middleware/rate_limit.py`.
At ~$32 per 1,000 Places requests, that is uncapped third-party spend per
authenticated caller.

> Debit-before-call, refund-on-failure, plus a per-org daily cap in Redis
> (the fixed-window counter in `middleware/rate_limit.py` is a working
> pattern to copy) and a 24h Redis cache on `(query, location, filters)`.
> Keep any paid provider behind an explicit opt-in flag, default off.

## A-2 🔴 SSRF in the Website Scanner (not covered above)

Phase 1 of the scanner plan is "replace the RNG with an actual
`httpx.AsyncClient().get(url)`". That single change turns
`POST /scan-website` into a server-side request forgery primitive: an
authenticated caller supplies an arbitrary URL and the server fetches it
from inside your network. Targets of concern include
`http://169.254.169.254/` (cloud instance metadata / IAM credentials),
`http://localhost:8000` (this API itself), and any RFC-1918 address.

This is the most security-sensitive change in the whole plan, and the
scanner is otherwise the *easiest* module to build — a bad combination,
because it invites shipping quickly.

> Defence in depth, all five required:
> 1. Resolve DNS first and reject private/loopback/link-local/reserved
>    resolved IPs (`ipaddress.ip_address(...).is_private` and friends) —
>    check **post-resolution**, never on the hostname string (DNS rebinding).
> 2. Re-validate after **every** redirect hop, with a hop cap.
> 3. Allow `http`/`https` only — reject `file:`, `gopher:`, `ftp:`.
> 4. Enforce the byte cap **while streaming**, not after the body lands.
> 5. Ship a `SCANNER_ALLOW_PRIVATE_NETWORKS=false` kill-switch and make a
>    security review of this guard the release gate for the module.

## A-3 🟠 `Search.results_count` is internally inconsistent today

`search_service.py:68` invents `found = rng.randint(8, 45)` per provider
and sums it into `results_count`, while line 80 caps actual row creation at
`min(found, 8)`. A search therefore reports e.g. 136 results while
persisting 40 leads — verified live earlier in this project
(`results_count: 136`, `total_items: 40`).

Making search real **fixes** this as a side effect (count will equal rows
persisted). Worth knowing it is a genuine pre-existing data-integrity bug,
not just cosmetic drift — and that historical rows keep the inflated values.

## A-4 🟠 `scan_duration_ms` is deliberately padded

`search_service.py:198` computes real elapsed time (~1ms, since nothing is
fetched) and then adds `rng.randint(1800, 3200)` to make it look like a
plausible network scan. A real scanner will often report *faster*
durations than the placeholder on fast sites. Any dashboard or SLA
built on this field is currently reading fiction.

## A-5 🟠 Old and new metric values are not comparable

No schema or type change, but these fields change meaning — the sharp
edge of the migration:

| Field | Today | After |
|---|---|---|
| `Lead.lead_score` | `rng.randint(40, 98)` (`:97`) | Real signal-derived score |
| `WebsiteScan.confidence_score` | Weighted count of random booleans (`:191-193`) | Weighted function of real findings |
| `ApiProvider.usage_count` | Incremented for calls never made (`:79`) | Real API call count |
| `WebsiteScan.gst_number` | Structurally plausible, **checksum-invalid** (`:174-178`) | Real extracted GSTIN, or `NULL` |

**All existing lead-quality analytics** (`GET /analytics/lead-quality`,
`/analytics/provider-performance`, the dashboard's avg-lead-score card)
are currently computed over `rng.randint(40, 98)`. They will shift
materially — that is a correctness improvement, but it will look like a
regression on any dashboard someone has been watching.

## A-6 🟡 Placeholder rows are indistinguishable from real ones

Existing `searches` / `leads` / `website_scans` rows carry invented
scores, fake GSTINs and non-deliverable emails, in the same tables real
data will land in. Analytics will silently blend them.

> One-time purge of placeholder-era rows per environment at cutover (they
> are demo data, not customer data). If any must be retained, add a
> nullable `data_source` marker to separate them.

## A-7 🟡 No encryption utility exists for `api_key_encrypted`

§5 above proposes a `FIELD_ENCRYPTION_KEY` env var. Note that
`ApiProvider.api_key_encrypted` (`models/search.py:27`) exists but is
**read and written by nothing**, and there is **no crypto helper anywhere
in `backend/`** (verified by grep). Writing plaintext into a column named
`_encrypted` would be worse than not storing it at all.

> Implement the Fernet helper *before* any code path writes to that
> column, and document key rotation from day one.

## A-8 🟡 Real search unblocks Map Search — worth sequencing for

`search_service.py:86-93` creates `Company` rows with no `lat`/`lng`, no
`website`, no `gst_number`. The missing coordinates are the direct cause
of `POST /map/nearby-leads` returning `[]` for searched leads — the gap
already logged in `FRONTEND_BACKEND_MAPPING.md` §5/§17.

Google Places responses include `geometry.location`, so populating
`lat`/`lng` during Phase 1 fixes the Map Search page **with no frontend
change**. That is a free win worth doing in the same pass, not later.

## A-9 🟡 Export specifics not covered above

- **Memory:** a 50k-row export materialised in memory will OOM the
  container. Stream CSV/JSON row-by-row; use `openpyxl` write-only mode;
  cap PDF rows well below the CSV limit (PDF suits summary reports, not
  50k-row dumps).
- **Access control:** export files contain the org's full lead database
  including contact PII. `GET /exports/{id}/download` must be org-scoped
  exactly as `services/document_service.py` already does, must never be
  served from a public static path, and must honour `expires_at` on
  download rather than only in listings.
- **Format-case mismatch:** the frontend's `ExportFormat` is
  `"CSV" | "Excel" | "PDF" | "JSON"` (`src/components/export/types.ts:1`)
  while the backend enum is lowercase (`models/enums.py`). Needs a
  deliberate mapping on one side — cheapest is accepting case-insensitive
  input server-side.
- **Dedupe (search, related):** `get_or_create_company` in
  `repositories/lead_repository.py` dedupes on `(name, city)` only. Real
  providers return the same business under inconsistent names ("Acme Pvt
  Ltd" vs "ACME Private Limited"); multi-provider search multiplies this.
  Prefer a priority chain — website domain → normalised phone → fuzzy
  name+city — applied both within a result set and against existing rows.

## A-10 Revised sequencing rationale

The order in §9 above (Scanner → Export → Places) is sound on cost and
blockers. One adjustment worth considering: **Export before Scanner.**
Export has no paid dependency *and* no security-review gate, whereas the
scanner's SSRF surface (A-2) means its true critical path includes a
security review, not just implementation. Export is the lower-variance
delivery.

Both orderings are defensible; Phase 0 items (A-1 metering, A-7 crypto)
should precede any *paid* provider either way.
