# Frontend ↔ Backend API Mapping

> **Status: integration complete.** Every page and component listed below now
> calls the live API. The mock modules this document was written against
> (`src/lib/mock-data.ts`, `src/components/team/mock-data.ts`,
> `src/components/billing/mock-data.ts`) have been deleted. The tables are kept
> as the field-by-field contract reference between the two sides — read
> "mock → endpoint" rows as "view model ← endpoint".

This document maps every frontend page/component to the backend endpoint(s)
that feed it, field-by-field.

**Base URL:** `http://127.0.0.1:8001/api/v1` in this repo's local setup — the
backend's `.env` sets `PORT=8001`, and the frontend's `.env.local` sets
`NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8001` (origin only, **no**
`/api/v1` suffix — the API modules append the versioned path themselves).

**Legend:** 🟢 direct replacement (shapes match closely) · 🟡 replacement
needs light client-side transformation · 🔴 backend uses documented
placeholder data (see `backend/README.md#whats-real-vs-what-needs-your-api-keys`)

---

## Table of contents

1. [Auth pages](#1-auth-pages)
2. [Onboarding](#2-onboarding)
3. [Dashboard home](#3-dashboard-home--srcappdashboardpagetsx)
4. [Lead Search](#4-lead-search--srcappdashboardsearchpagetsx)
5. [Map Search](#5-map-search--srcappdashboardmappagetsx)
6. [Lead Database](#6-lead-database--srcappdashboardleadspagetsx)
7. [Lead Profile](#7-lead-profile--srcappdashboardleadsidpagetsx)
8. [API Manager](#8-api-manager--srcappdashboardapi-managerpagetsx)
9. [Website Scanner](#9-website-scanner--srcappdashboardscannerpagetsx)
10. [Export Center](#10-export-center--srcappdashboardexportpagetsx)
11. [Lead Intelligence](#11-lead-intelligence--srcappdashboardintelligencepagetsx)
12. [Settings](#12-settings--srcappdashboardsettingspagetsx)
13. [Team](#13-team--srcappdashboardteampagetsx)
14. [Billing](#14-billing--srcappdashboardbillingpagetsx)
15. [Shared layout components](#15-shared-layout-components)
16. [Landing page](#16-landing-page--srcapppagetsx)
17. [Fields with no backend equivalent yet](#17-fields-with-no-backend-equivalent-yet)
18. [Suggested integration approach](#suggested-integration-approach)

---

## 1. Auth pages

| Page | Backend endpoint | Notes |
|---|---|---|
| `src/app/login/page.tsx` | 🟢 `POST /auth/login` | Body: `{email, password, remember_me}`. Response has `access_token`, `refresh_token`, `user` — store both tokens, redirect on 200. |
| `src/app/login/page.tsx` (Google button) | 🟢 `GET /auth/google/login` | Full-page redirect (not fetch) — browser navigates there, Google redirects back to `/auth/google/callback`, which redirects to `{FRONTEND_URL}/dashboard?access_token=...`. Frontend should read that query param on the dashboard's first load and store it. |
| `src/app/signup/page.tsx` | 🟢 `POST /auth/signup` | Body: `{email, password, full_name, company_name}`. Same token response shape as login; also creates the org + Free subscription server-side (nothing extra for the frontend to do). |
| `src/app/forgot-password/page.tsx` | 🟢 `POST /auth/forgot-password` | Body: `{email}`. Always returns 200 with a generic message (doesn't leak whether the account exists) — matches the frontend's existing "check your email" UX exactly. |
| `src/app/verify-email/page.tsx` | 🟡 `POST /auth/verify-email` | Body: `{token}` — the token comes from the query string of the emailed link (`/verify-email?token=...`), not from a 6-digit code as the current mock UI assumes. **The OTP-style 6-box input UI should be replaced** with "click the link in your email" + a "Resend" button calling `POST /auth/resend-verification` (Bearer auth). |
| `src/app/two-factor/page.tsx` | 🟡 `POST /auth/otp/verify` | Body: `{email, code, purpose: "login"}` — this backend implements OTP as a *login method* (`POST /auth/otp/request` + `/otp/verify`), not as a 2FA step layered on top of password login. To match the current two-step UI, call `POST /auth/otp/request` right after a successful password login, then this screen verifies it. There's no separate "enable 2FA on my account" toggle server-side yet (see [§17](#17-fields-with-no-backend-equivalent-yet)). |
| Session persistence | 🟢 `POST /auth/refresh` | Body: `{refresh_token}`. Call when the access token expires (30 min default) to get a fresh pair without re-prompting for a password. |
| Logout | 🟢 `POST /auth/logout` | Bearer auth, no body. Revokes all of the user's active sessions server-side. |

## 2. Onboarding

`src/app/onboarding/page.tsx` collects business type, industries, data
sources, countries, volume, and team size — **none of this is persisted
anywhere in the current backend.** The closest fit:

- 🟡 Persist the collected answers via `PUT /settings/organization/onboarding`
  (generic KV store — see `GET/PUT /settings/{scope}/{key}` with
  `scope=organization`, `key=onboarding`) so they survive a refresh and can
  inform future personalization. This wasn't a named field the backend
  explicitly models (organization industry/company_size *are* real
  columns via `PATCH /settings/organization` — map "business type" there;
  everything else — target industries, data sources, countries, volume —
  fits the generic settings store instead).
- The final "Go to Dashboard" step needs no API call — it's purely a UI
  transition today, and can stay that way.

## 3. Dashboard home — `src/app/dashboard/page.tsx`

| Mock export (`src/lib/mock-data.ts`) | Backend endpoint | Match |
|---|---|---|
| `dashboardStats` | `GET /dashboard/stats` | 🟢 Same fields (`total_leads`, `today_leads`, `conversion_rate`, `avg_lead_score`, `search_count`, `credits_remaining`, `credits_total`) — just snake_case instead of camelCase. |
| `leadGrowthData` | `GET /dashboard/lead-growth` | 🟢 `[{month, leads, converted}]`, last 6 months, gap-filled. |
| `industryDistribution` | `GET /dashboard/industry-distribution` | 🟢 `[{name, value}]`. |
| `countryAnalytics` | `GET /dashboard/country-analytics` | 🟢 `[{country, leads}]`. |
| `searchAnalytics` | `GET /dashboard/search-analytics` | 🟢 `[{day, searches}]`, last 7 days. |
| `apiUsageData` | `GET /dashboard/api-usage` | 🟢 `[{name, usage, limit}]`. |
| `exportAnalytics` | `GET /dashboard/export-analytics` | 🟢 `[{month, csv, excel, pdf}]`. |
| `AiRecommendations` widget copy | — | 🔴 No backend endpoint generates AI recommendation text — this widget has no real data source yet; keep it static or scope a new endpoint. |
| `RecentSearches` widget | `GET /search/history?page_size=5` | 🟢 Use `items` from the paginated response. |
| `HighValueLeads` widget | `GET /leads?sort_by=lead_score&sort_order=desc&page_size=5` | 🟢 |
| `WebsiteScanResults` widget | `GET /scans?page_size=3` | 🟢 |
| `ProviderHealth` widget | `GET /providers` | 🟢 Filter/sort client-side by `status`. |
| `DailyReport` widget | Composite of `/dashboard/stats` + `/analytics/business-summary` | 🟡 No single endpoint returns this exact shape — compose from two calls. |

All 6 stat cards, all 6 charts: 🟢 direct swap. All routes need `Authorization: Bearer` (org resolved automatically).

## 4. Lead Search — `src/app/dashboard/search/page.tsx`

| Frontend behavior | Backend endpoint | Notes |
|---|---|---|
| Submitting the search bar | 🔴 `POST /search` | Body: `{query, location, industry, country}`. **Important UX change:** the backend runs synchronously and returns a *completed* result in one call (typically 1-2s) — the frontend's staged "provider-by-provider progress" animation (`SearchProgress` component ticking each provider from pending→searching→done) has no real incremental signal to drive it. Either (a) fake the stagger client-side over the single response's `provider_runs` array after the real call resolves, or (b) keep it simple and just show a single loading state. Response's `provider_runs[]` still gives you real per-provider result counts to display once done. |
| Results grid | Response's leads are **not** returned inline — call `GET /leads?page_size=24&sort_by=lead_score&sort_order=desc` immediately after a successful search to fetch the newly-created leads (or filter by `search_id` — not currently exposed as a query param; open item, see §17). | 🟡 |
| Filter panel (industry/country/provider/company type/rating/score) | `GET /leads` query params: `industry`, `country`, `min_score`, `max_score` | 🟡 `provider`, `companyType`, and `rating` filters aren't supported as query params on `GET /leads` yet — would need a small backend addition. `city`/`keyword` free-text is covered by the `search` param (matches company name only, not multi-keyword). |
| AI suggestion chips | — | 🔴 Static list, no backend needed. |
| Search Timeline panel | `GET /search/history` | 🟢 |

## 5. Map Search — `src/app/dashboard/map/page.tsx`

| Frontend behavior | Backend endpoint | Notes |
|---|---|---|
| Pin positions from `mockLeads[].lat/lng` | 🟢 `GET /leads` then filter client-side for non-null lat/lng, **or** `POST /map/nearby-leads` | Coordinates are now real: the Google Places and Mappls providers both populate `lat`/`lng` on the `Company` row, so searched leads appear on the map without a separate geocoding pass. Leads from providers that return no coordinates (Bing Search, Company Website Search) and from CSV import without `lat`/`lng` columns still have null coordinates — geocode those via `POST /map/geocode`. |
| Radius slider → distance filtering | 🟢 `POST /map/nearby-leads` body `{lat, lng, radius_km, industry?}` | Real haversine math server-side — replaces the frontend's client-side `map-utils.ts` distance calc entirely. No API key needed. |
| Provider toggle (Google Maps/Mappls/OSM) | — | 🔴 Cosmetic only in both frontend and backend — no functional difference server-side regardless of which is "selected". |
| Address search / geocoding | 🟢 `POST /map/geocode` | Needs `GOOGLE_MAPS_API_KEY` configured. |

## 6. Lead Database — `src/app/dashboard/leads/page.tsx`

| Frontend behavior | Backend endpoint | Notes |
|---|---|---|
| Table data (`mockLeads`, 120 rows) | 🟢 `GET /leads` | Paginated (`page`, `page_size`), sortable (`sort_by=created_at\|lead_score\|company`, `sort_order`), filterable (`search`, `industry`, `status`, `country`, `min_score`, `max_score`). Swap TanStack Table's client-side `getPaginationRowModel`/`getSortedRowModel`/`getFilteredRowModel` for server-side pagination — pass table state as query params instead. |
| Row → lead profile navigation | — | Unchanged, still routes to `/dashboard/leads/{lead.id}` — `id` is now a real UUID string instead of `lead_N`. |
| "Saved Views" dropdown | — | 🔴 No backend concept of saved views yet — cosmetic/local-only for now. |
| Bulk delete | 🟢 `POST /leads/bulk-delete` | Body: `{ids: [...]}`. |
| Column visibility toggle | — | Pure client-side UI state, no backend involvement either way. |
| CSV import | 🟢 `POST /leads/import` | **New endpoint.** `multipart/form-data` with a single `file` field — not JSON. Send as `FormData`; do **not** set `Content-Type` manually, let the browser add the multipart boundary. Returns `{total_rows, imported, duplicates_skipped, invalid_rows, errors[], dedup_signals}`; render `errors[]` (each has `line`, `message`, `company`) as a per-row report, since a bad GSTIN/email/phone imports the lead *without* that field rather than failing the file. No frontend screen exists for this yet — it is the backend half of an import button the Lead Database page can add. |
| Manual "Add Lead" | 🟢 `POST /leads` | Contract unchanged. Two additions, both opt-in by omission: leave `lead_score` at `0`/absent and the lead is scored by the same engine used for search results; omit `ai_summary` and one is generated from the lead's real attributes. Passing either explicitly is always respected. |

## 7. Lead Profile — `src/app/dashboard/leads/[id]/page.tsx`

| Frontend section | Backend endpoint | Notes |
|---|---|---|
| Header, Company Information, Contact Details, AI Summary | 🟢 `GET /leads/{id}` | Returns the flattened `LeadDetailOut` shape — company fields (industry/city/country/website/rating/revenue_band/gst_number) are already merged in, matching the frontend's denormalized `Lead` type almost field-for-field (see the table below). |
| Notes section | 🟢 `GET /leads/{id}/notes`, `POST /leads/{id}/notes` | Body: `{text}`. |
| Tags section | 🟡 `PATCH /leads/{id}` body `{tags: [...]}` | No dedicated "add one tag" endpoint — send the full updated tags array. |
| Lead Timeline widget | 🟢 `GET /leads/{id}/activities` | Auto-populated by the backend on creation/status-change/note-added — no manual seeding needed like the frontend's invented mock timeline. |
| Location / map mini-card | 🟡 Uses `lead.company.lat/lng` from the detail response | Same caveat as §5 — may be null until geocoded. |
| "Scan Website" button | 🟢 Links to `/dashboard/scanner`; could pre-fill via `POST /scan-website` body `{url: lead.website}` | |

**`LeadOut` field mapping** (`schemas/lead.py`) vs. frontend `Lead` type:

| Frontend (`src/lib/types.ts`) | Backend (`LeadOut`) | Match |
|---|---|---|
| `id` | `id` | 🟢 (UUID string instead of `lead_N`) |
| `company` | `company` | 🟢 |
| `industry` | `industry` | 🟢 |
| `city`, `country` | `city`, `country` | 🟢 |
| `contactName` | `contact_name` | 🟢 (casing) |
| `email`, `phone`, `website` | `email`, `phone`, `website` | 🟢 |
| `rating` | `rating` | 🟢 |
| `revenue` | `revenue_band` | 🟢 (renamed) |
| `leadScore` | `lead_score` | 🟢 (casing) |
| `status` | `status` | 🟢 |
| `companyType` | `company_type` | 🟢 (casing) |
| `provider` | `provider` | 🟢 |
| `tags` | `tags` | 🟢 |
| `createdAt` | `created_at` | 🟢 (casing) |
| `gst` | `gst_number` | 🟢 (renamed) |
| `lat`, `lng` | `lat`, `lng` | 🟡 often `null` until geocoded (see §5) |
| `aiSummary` | `ai_summary` | 🟢 (casing) |

## 8. API Manager — `src/app/dashboard/api-manager/page.tsx`

| Frontend behavior | Backend endpoint | Notes |
|---|---|---|
| Provider grid (`apiProviders` mock) | 🟢 `GET /providers` | Field names match closely: `usage`→`usage_count`, `limit`→`usage_limit`, everything else identical. |
| Stat row (connected count, requests today, avg latency, issues) | 🟡 Compute client-side from the `/providers` response | No dedicated aggregate endpoint — trivial to derive in the frontend from the list, same as the current mock version does. |
| "Test Connection" button | 🟢 `POST /providers/{id}/test` | Performs a REAL authenticated round-trip using the credentials a search would use (Mappls exchanges an OAuth token and reports its expiry; Google Places / Bing issue one-result queries; OpenAI lists models). Always HTTP 200 — `success: false` means the provider rejected us, with its status code, error body and exception in `details`. The traceback stays in the server log. Requires `api_keys.manage`. |
| — (no UI yet) | 🟢 `POST /providers/system-checks` | Real checks for SMTP (connect + STARTTLS + LOGIN), Stripe (`Account.retrieve`), Redis (`PING`) and Postgres (`SELECT 1`). These have no `ApiProvider` row, so they are not per-provider. |
| Credentials tab | 🟢 `GET /providers/credentials`, `PUT /providers/{id}/credentials`, `DELETE /providers/{id}/credentials` | Write-only: values are encrypted with `PROVIDER_CREDENTIAL_ENCRYPTION_KEY` and never returned, so the form reports whether each field is set rather than pre-filling it. Requires the `api_keys.manage` permission. Providers needing a pair (Mappls: client id + secret) use `api_secret` as well. |
| "Connect"/"Disconnect" toggle, credential management, sparkline | — | 🔴 Not modeled server-side — `ApiProvider.connected` and `api_key_encrypted` columns exist in the DB but there's no route to mutate them yet (open item, see §17). |
| Usage Analytics chart | 🟢 `GET /dashboard/api-usage` | |

## 9. Website Scanner — `src/app/dashboard/scanner/page.tsx`

| Frontend behavior | Backend endpoint | Notes |
|---|---|---|
| Submitting a URL to scan | 🔴 `POST /scan-website` | Body: `{url}`. Backend **ports the exact same deterministic hash algorithm** the frontend's `src/components/scanner/mock-data.ts` uses (same domain → same result, both client and server side) — see backend README for details. Response is synchronous/immediate; the frontend's multi-stage "Connecting → Reading → Extracting..." progress animation has no real incremental backend signal, same caveat as lead search — fake the stagger client-side, then render the real response once it lands. |
| Report fields | 🟢 `WebsiteScanOut` | `confidence_score`, `company_name`, `contact_person`, `emails[]`, `phones[]`, `gst_number`, `gst_verified`, `social_links[]` (array of `{platform, found, handle}` — frontend expects the same shape), `ssl_valid`, `mobile_friendly`, `load_time_ms`, `seo_score`, `scan_duration_ms`. Near-exact match to the frontend's `ScanReport` type. |
| Recent Scans list | 🟢 `GET /scans` | |

## 10. Export Center — `src/app/dashboard/export/page.tsx`

**Fully implemented.** The `/exports` router generates real CSV / Excel / PDF /
JSON files, logs them to the `exports` table, and serves them back over two
authenticated download paths.

| Frontend behavior | Backend endpoint | Notes |
|---|---|---|
| `ExportWizard` submit (`export-wizard.tsx`) | 🟢 `POST /exports` | One call covers the whole wizard. `source` → `scope` (`all`/`filtered`/`selected` — the union already matches), `format` → `format` (lowercase the label: `"Excel"` → `"excel"`), `fields` → `columns`, `fileName` → `file_name` (send the stem only; the extension is appended server-side). |
| Wizard `fields` checkboxes (`EXPORT_FIELDS`) | 🟢 `columns` | The eight labels (`Company`, `Industry`, `City`, `Contact`, `Email`, `Phone`, `Lead Score`, `Status`) are accepted **verbatim** — no client-side mapping needed. API keys (`lead_score`) work too. Unmatched names come back in `ignored_columns` instead of failing. |
| Wizard format picker (`FORMAT_META`) | 🟡 `GET /exports/formats` | Optional: serves formats, extensions, media types, the full lead-column catalogue and this deployment's limits, so the picker stops being a hardcoded list that can drift from the backend. |
| Wizard progress bar | 🟡 `POST /exports` status | Small exports return `201` with `status="ready"` immediately, so the simulated progress steps can be dropped. Large ones return `202` with `status="processing"` — poll `GET /exports/{id}` and drive the bar from the real status. |
| `DownloadCenter` list (`INITIAL_EXPORTS`) | 🟢 `GET /exports` | Paginated, newest first. Replace the `INITIAL_EXPORTS` mock; the response items map field-for-field onto `ExportRecord` (table below). |
| Download button | 🟢 `POST /exports/{id}/download-token` then `GET /exports/{id}/download?token=…` | **Use the token flow in the browser.** A plain `<a href>` / `window.open` cannot set an `Authorization` header, and putting the access token in the URL would leak a long-lived credential into history and proxy logs. The returned `download_url` is ready to assign to `<a href>`. |
| `ExportAnalyticsChart` | 🟢 `GET /dashboard/export-analytics` | Already existed; now returns real data, because exports finally write `Export` rows. |
| "Expired" badge | 🟢 `status` field | Files are deleted after `EXPORT_RETENTION_HOURS` and the row flips to `expired`; `download_url` becomes `null`. |
| — (new capability) | 🟢 `DELETE /exports/{id}` | No mock equivalent — lets a user remove an export and its file early. |

**`ExportOut` field mapping** (`schemas/export.py`) vs. the frontend
`ExportRecord` type (`src/components/export/types.ts`):

| Frontend (`ExportRecord`) | Backend (`ExportOut`) | Match |
|---|---|---|
| `id` | `id` | 🟢 (UUID string instead of `exp-N`) |
| `fileName` | `file_name` | 🟢 rename only |
| `format` | `format` | 🟡 backend is lowercase (`"excel"`), frontend labels are title-case (`"Excel"`) — capitalize for display, and note `excel` ⇄ `.xlsx` |
| `rowCount` | `row_count` | 🟢 rename only |
| `sizeLabel` | `size_label` | 🟢 pre-formatted server-side (`"1.2 MB"`), so the client needs no byte-formatting logic. `size_bytes` is also returned for programmatic use. |
| `createdAt` | `created_at` | 🟢 ISO-8601 |
| `status` | `status` | 🟡 frontend union is `"ready" \| "expired"`; the backend adds `"processing"` and `"failed"` — extend the union, and render `error_message` for failures |
| — | `resource` | 🔵 new: `leads` / `search_results` / `dashboard_report` / `analytics_report` |
| — | `download_url` | 🔵 new: `null` unless currently downloadable. **Root-relative** (`/api/v1/exports/…`) — join it against the origin, not against an API base that already ends in `/api/v1`, or you get `/api/v1/api/v1/…` and a 404. |
| — | `download_count`, `expires_at`, `error_message`, `ignored_columns` | 🔵 new |

**Beyond the current UI.** The wizard only offers leads today, but the endpoint
also exports `search_results` (pass `search_id`), `dashboard_report` and
`analytics_report` — the latter two as multi-section documents (one worksheet per
section in Excel, one page per section in PDF). Adding an "Export report" button
to the dashboard or analytics pages needs no backend work.

**RBAC.** Creating and deleting exports requires the `leads.export` permission:
Owner, Admin and Member have it; **Viewer does not** and gets a `403`. Reading
history needs only membership, so a viewer can see that an export happened. Hide
or disable the wizard's submit for viewers to avoid a dead-end `403`.

**Rate limiting.** Export creation is capped per user per hour
(`EXPORT_RATE_LIMIT_PER_HOUR`, default 30) and returns `429`; downloads and
history reads are not capped.

## 11. Lead Intelligence — `src/app/dashboard/intelligence/page.tsx`

| Mock export | Backend endpoint | Match |
|---|---|---|
| KPI row (total leads, avg score, conversion, search-to-lead ratio) | `GET /dashboard/stats` (first three) + compute ratio client-side | 🟡 |
| Top Industries | `GET /analytics/top-industries` | 🟢 |
| Top Cities | `GET /analytics/top-cities` | 🟢 |
| Lead Trends chart | `GET /dashboard/lead-growth` | 🟢 (same endpoint as the dashboard page) |
| Search Performance | `GET /dashboard/search-analytics` | 🟢 |
| Provider Performance | `GET /analytics/provider-performance` | 🟢 |
| Lead Quality bands | `GET /analytics/lead-quality` | 🟢 Returns `{id, label, min_score, max_score, count, percentage}` per band. |
| Business Analytics summary | `GET /analytics/business-summary` | 🟢 |

## 12. Settings — `src/app/dashboard/settings/page.tsx`

| Settings section | Backend endpoint | Notes |
|---|---|---|
| Profile | 🟢 `GET/PATCH /settings/profile` | |
| Organization | 🟢 `GET/PATCH /settings/organization` | PATCH requires Owner/Admin role. |
| API Keys | 🟢 `GET/POST /settings/api-keys`, `DELETE /settings/api-keys/{id}` | The full plaintext key is returned **only** in the `POST` response — matches the frontend's existing "shown once" warning UX exactly. |
| Security → password change | 🟢 `POST /auth/change-password` | Body: `{current_password, new_password}`. |
| Security → Active Sessions | 🟢 `GET /auth/sessions`, `DELETE /auth/sessions/{id}` | |
| Security → 2FA toggle | — | 🔴 No account-level "2FA enabled" flag/endpoint yet (only the OTP-as-login-method flow described in §1) — `User.two_factor_enabled` column exists but nothing sets it. |
| Theme | — | Frontend-only (dark-only product) — no backend needed, matches current implementation. |
| Notifications preferences | 🟢 `GET /notifications/preferences`, `PATCH /notifications/preferences/{category}` | |
| Backup | 🟢 `GET/POST /settings/backups` | Real DB rows with an estimated size, not an actual export/restore engine (documented in backend README). |
| Providers (lightweight section) | 🟢 `GET /providers` | Links through to the full API Manager page. |
| Billing (lightweight section) | 🟢 `GET /billing/subscription`, `GET /billing/usage` | |
| Team (lightweight section) | 🟢 `GET /team/members` | |

## 13. Team — `src/app/dashboard/team/page.tsx`

| Frontend section | Backend endpoint | Notes |
|---|---|---|
| Workspace info card | 🟢 `GET /settings/organization` + `GET /billing/subscription` + `GET /team/members` | Composed client-side. `OrganizationOut.created_at` was added for the "Created" field. |
| Members list | 🟢 `GET /team/members` | Returns `{id, user_id, name, email, avatar_url, role, status, joined_at, last_active}` — near-exact match. |
| Invite Member dialog | 🟢 `POST /team/invite` | Body: `{email, role}`. Owner/Admin only. Sends a real invitation email. |
| Roles & Permissions matrix | 🟢 `GET /team/roles` + `GET /team/permissions` | Added so the table reflects the matrix `require_permission` actually enforces, rather than a client-side copy of the seed data. `superadmin` is excluded — it is a platform flag, not an assignable workspace role. |
| Recent Leads / Recent Searches | 🟢 `GET /leads?page_size=3`, `GET /search/history?page_size=3` | Renamed from "Shared": there is no per-resource owner server-side, so the old "Shared by <person>" line was fabricated. Rows now show real provenance (source provider; location + result count). |
| Pending Invitations list | 🟢 `GET /team/invitations` | |
| Resend / Cancel invite | 🟢 `POST /team/invitations/{id}/resend`, `DELETE /team/invitations/{id}` | |

## 14. Billing — `src/app/dashboard/billing/page.tsx`

| Frontend section | Backend endpoint | Notes |
|---|---|---|
| Manage Payment Method dialog | — | 🔴 Deliberately not implemented server-side (no real card collection, per platform safety rules) — real flow is Stripe Checkout (`POST /billing/checkout`) which redirects to a Stripe-hosted page instead of an in-app card form. **The frontend's current in-app "masked card" dialog UI doesn't match this flow and should be replaced** with a redirect-to-Stripe-Checkout button. |
| Current Plan card | 🟢 `GET /billing/plans`, `GET /billing/subscription` | |
| Credits & Add-ons | 🟢 `GET /billing/credit-packs`, `POST /billing/credits/checkout` | The pack catalogue is served by the backend so price/credit amounts have one definition; the client sends only `pack_id`. |
| Upgrade/Downgrade | 🟢 `POST /billing/checkout` body `{plan_id}` → returns a real Stripe Checkout URL to redirect to (needs `STRIPE_SECRET_KEY` configured) | |
| Usage row (credits/seats/searches/exports) | 🟢 `GET /billing/usage` | Field names match closely. |
| Credits & Add-ons | 🟢 `POST /billing/credits/checkout` body `{amount_cents}` | Same Stripe Checkout redirect pattern. |
| Invoice History | 🟢 `GET /billing/invoices` | |
| Payment history (if added) | 🟢 `GET /billing/payments`, `GET /billing/transactions` | |
| Refund button (if added) | 🟢 `POST /billing/payments/{id}/refund` | Owner/Admin only. |

## 15. Shared layout components

| Component | Backend endpoint | Notes |
|---|---|---|
| `src/components/layout/notification-panel.tsx` | 🟢 `GET /notifications`, `GET /notifications/unread-count`, `POST /notifications/{id}/read`, `POST /notifications/read-all` | Field mapping: mock `read: boolean` ↔ real `read` (already a computed boolean field derived from `read_at`, not the raw timestamp) — no transformation needed. |
| `src/components/layout/command-palette.tsx` (Ctrl+K search) | 🟡 No unified search endpoint | Currently searches the local `mockLeads`/`searchHistory`/`apiProviders` arrays client-side. Closest real equivalent: `GET /leads?search=<query>&page_size=5` for the leads section; provider/search-history sections would need their own small queries (`GET /providers`, `GET /search/history?page_size=3`) run in parallel — there's no single combined endpoint. |
| `src/components/layout/sidebar.tsx` | — | Static nav, no data. |
| `src/components/layout/topbar.tsx` (credits badge) | 🟢 `GET /billing/usage` (credits fields) | |

## 16. Landing page — `src/app/page.tsx`

Fully static marketing content — no backend calls needed or expected. The
hero's animated "live results" mock is intentionally decorative.

---

## 17. Fields with no backend equivalent yet

Gaps found while writing this mapping — worth scoping as follow-up work.

Two entries have since been closed and are kept here, struck through, so the
list stays readable as a record rather than quietly changing shape:

- ~~**Export Center has no backend module at all** (§10)~~ — **done.** The
  `/exports` router now covers creation, history, both download paths and
  deletion, for leads, search results, and dashboard/analytics reports.
- ~~**Search results generation doesn't set `Company.lat/lng`**~~ — **done.**
  The Google Places and Mappls providers both populate coordinates, so Map
  Search shows pins for freshly-searched leads without a separate geocoding
  pass. Leads from providers that return no coordinates (Bing, Company Website
  Search) and CSV imports without lat/lng columns still need `POST /map/geocode`.

Still open:

- **API Manager's connect/disconnect + credential management** aren't
  exposed via any route (`ApiProvider.connected`/`api_key_encrypted`
  columns exist but are unreachable from the API surface).
- **`GET /leads` has no `search_id`, `provider`, `company_type`, or
  `rating` query params** — needed for the Lead Search page's full filter
  set and for "show me the leads this specific search just found".
- **No account-level 2FA toggle** — `User.two_factor_enabled` exists as a
  column but nothing reads or writes it; only OTP-as-a-login-method is
  implemented.
- **No "saved views" or "shared leads/searches" concept** — both are
  purely decorative in the current frontend and have no backing table.

## Suggested integration approach

1. Add a typed fetch client (`src/lib/api-client.ts`) wrapping `fetch`
   with the `NEXT_PUBLIC_API_URL` base, automatic `Authorization: Bearer`
   header injection from stored tokens, and one interceptor that calls
   `POST /auth/refresh` on a 401 and retries once before giving up.
2. Replace each `import { X } from "@/lib/mock-data"` with a
   [TanStack Query](https://tanstack.com/query) hook calling the mapped
   endpoint above (TanStack Query is already a project dependency —
   see `src/components/providers.tsx`) — this gets loading/error states
   and caching for free with minimal component changes, since most
   components already just consume a plain array/object prop.
3. Do it page-by-page in the order above (Dashboard → Search → Leads →
   Map → the rest) — each is independent and the mock data can stay in
   place for pages not yet migrated.
4. Set real environment values (`GOOGLE_MAPS_API_KEY`, `STRIPE_*`) before
   migrating the Map and Billing pages specifically, or those pages will
   correctly show configuration-error states from the backend.
