# Lead Providers

Every lead source implements the `LeadProvider` protocol in
`services/providers/base.py` and returns `NormalizedLead` values, so
deduplication, AI scoring, persistence and export behave identically no matter
where a lead came from. Adding a source means writing one adapter and one
registry entry — the search pipeline is not touched.

`services/providers/registry.py` is the single authority on which providers can
run: it decrypts each row's stored credentials, falls back to the platform values
in `.env`, and drops anything that has neither. A provider without credentials is
**skipped**, never attempted, so no credits are spent on a call that cannot
succeed.

## Catalogue

| Provider | Category | Credential | Returns coordinates | Notes |
| --- | --- | --- | --- | --- |
| Google Places | Maps | `GOOGLE_MAPS_API_KEY` | yes | Richest place data. Requires "Places API (New)" enabled. |
| Mappls (MapmyIndia) | Maps | `MAPPLS_CLIENT_ID` + `MAPPLS_CLIENT_SECRET` (OAuth2) | **only if licensed** | India-only. Coordinate delivery is a separate entitlement; without it Places responses omit lat/lng and geocoding answers 412. |
| Geoapify | Maps | `GEOAPIFY_API_KEY` | yes | OSM-derived. Places is `/v2`, geocoding `/v1`. |
| Bing Search | Search | `BING_SEARCH_API_KEY` | no | Retired for new Azure subscriptions (Aug 2025). |
| **OpenStreetMap** | Maps | **none** | yes | Nominatim geocoding + place search. |
| **Overpass API** | Search | **none** | yes | OSM POI search by tag, keyword and radius. |
| Company Website Search | Search | none | no | Crawls a company's own site for contacts. |
| IndiaMART / TradeIndia / LinkedIn / JustDial | — | — | — | Catalogue-only: no adapter, needs a partner agreement. Testing one reports that honestly. |
| OpenAI GPT | AI | `OPENAI_API_KEY` | — | Enrichment only; never sources leads. |

---

## OpenStreetMap (Nominatim)

Official public endpoints, no API key:

```
forward   GET https://nominatim.openstreetmap.org/search
reverse   GET https://nominatim.openstreetmap.org/reverse
tiles         https://tile.openstreetmap.org/{z}/{x}/{y}.png
```

Configuration — these are the only two variables the OSM integration adds:

```
OSM_USER_AGENT=LeadMasterAI/1.0
OVERPASS_URL=https://overpass-api.de/api/interpreter
```

### Usage policy is enforced in code, not assumed

Nominatim is donated infrastructure with a published policy, and it enforces it:

* An identifying `User-Agent` is **required** — requests without one are rejected.
  `OSM_USER_AGENT` supplies it on every call.
* Callers are capped at **1 request/second**. `osm_common.nominatim_limiter` is a
  process-wide gate, so no call site can accidentally burst past it.
* Identical queries are served from a 15-minute in-process cache rather than
  re-asked.

Nominatim is a *geocoder* first. Its `/search` endpoint does return POIs, which
makes a modest lead source, but the policy discourages bulk POI harvesting — that
is what Overpass is for, which is why the result cap here is deliberately low.

It is also the **last-resort geocoder** for the Map module. Because it needs no
key, `/map/geocode` and `/map/reverse-geocode` now work on a completely
unconfigured deployment. The chain is Google → Geoapify → Mappls → OpenStreetMap;
paid providers come first because OSM is rate-limited and donated.

**Coordinates arrive as strings** (`"23.0215374"`), not numbers.

---

## Overpass API

```
POST {OVERPASS_URL}     body: data=<Overpass QL>
```

No API key.

### It defends itself, and the design reflects that

Measured against the public instance while building this:

| Observation | Consequence |
| --- | --- |
| **429 on 8 of 12** requests spaced 1.2s apart | One request per search — every keyword and element type is unioned into a single query. Issuing one request per tag was what triggered the throttling. |
| **504** on heavier queries; the same query returned 504, 200 and 429 across probes | Retry with exponential backoff (`providers.http.request_json` treats 429/5xx as transient), and a failed Overpass degrades the search instead of failing it. |
| Error bodies are **HTML, not JSON** | Errors are surfaced as provider errors with a truncated body, never parsed as JSON. |
| An accepted query answers in **~10–35s** | `[timeout:25]` server-side with a 45s client timeout, so Overpass replies rather than leaving a multi-provider search hanging. |

### Keyword → query

Two strategies, chosen **per keyword**:

1. **Tag selectors** for concepts OSM models directly — `amenity=restaurant`,
   `amenity=hospital`, `man_made=works`, `generator:source=solar`. Precise, and
   finds businesses whose *name* says nothing about what they do.
2. **Case-insensitive name regex** (`["name"~"...",i]`) for concepts OSM has no
   tag for. "PLC", "SCADA", "Panel Builder" and "Industrial Automation" are not
   OSM tags and never will be.

A keyword with tags uses **tags only** — the name regex is deliberately not added
alongside. Measured: tag-only for "hospital" answered in ~19s, while tag+regex was
throttled with a 429 and returned nothing. Precision that completes beats recall
that gets rejected. A keyword with no tag mapping still searches by name, so
nothing is silently unsupported.

Multi-keyword input is split on `,` `;` `|` `/` `+` and the word "and". The full
phrase is kept as a term too, so "industrial automation" still matches as a
phrase before its parts are tried.

### Geometry

Overpass requires a spatial filter, so a keyword+location search is two steps:

1. Geocode the location through Nominatim → lat/lon.
2. `(around:<radius_m>,<lat>,<lon>)`.

Note the argument order is **radius, latitude, longitude** — unlike the lon-first
GeoJSON convention Geoapify uses. Radius is clamped to **1–100 km** (default 25).

`out center tags <limit>` is required, not optional: ways and relations carry no
`lat`/`lon` of their own, only a `center` when asked for it, and most industrial
premises are mapped as ways.

### Example generated query

`hospital` within 15 km of Ahmedabad:

```
[out:json][timeout:25];
(
  node["amenity"="hospital"](around:15000,23.0215374,72.5800568);
  way["amenity"="hospital"](around:15000,23.0215374,72.5800568);
  relation["amenity"="hospital"](around:15000,23.0215374,72.5800568);
);
out center tags 10;
```

`PLC` (no OSM tag exists) falls back to a name match:

```
[out:json][timeout:25];
(
  node["name"~"PLC",i](around:15000,23.0215374,72.5800568);
  way["name"~"PLC",i](around:15000,23.0215374,72.5800568);
  relation["name"~"PLC",i](around:15000,23.0215374,72.5800568);
);
out center tags 10;
```

---

## Extracted fields

`osm_common.extract_osm_fields` reads the documented OSM tag vocabulary. Values
are **only ever read, never invented** — an absent tag yields `NULL`, because a
fabricated phone number is worse than a missing one.

| Field | OSM tags |
| --- | --- |
| Business name | `name`, `name:en`, `official_name`, `brand` |
| Category / subcategory | `amenity`, `shop`, `office`, `craft`, `healthcare`, `man_made`, `industrial`, `landuse`, `tourism`, `leisure`, `building` / `cuisine`, `healthcare:speciality`, `industry`, `generator:source` |
| Address, street, housenumber, area, city, district, state, country, postal code | `addr:*` |
| Latitude / longitude | element `lat`/`lon`, or `center` for ways and relations |
| Phone / mobile | `phone`, `contact:phone`, `telephone` / `contact:mobile`, `mobile`, `phone:mobile` |
| Website / email | `website`, `contact:website`, `url` / `email`, `contact:email` |
| Facebook, Instagram, LinkedIn, Twitter, YouTube, WhatsApp | `contact:<platform>` or bare `<platform>` |
| Opening hours, operator, brand, wheelchair | `opening_hours`, `operator`, `brand`, `wheelchair` |
| Payment methods | `payment:*` where the value is `yes`/`only`/`true` (so `payment:bitcoin=no` is not listed as accepted) |
| OSM identity | `{type}/{id}`, e.g. `node/440305869` |
| Place ID | Nominatim `place_id` (Overpass has no equivalent) |
| Source & licence | recorded on every lead; OSM data is ODbL-licensed and the attribution travels with the lead |

Fields without a column on `Company`/`Lead` (socials, opening hours, operator,
payment methods, OSM identity) are preserved verbatim in `NormalizedLead.raw`.
They are stored, not surfaced through the API yet — surfacing them would need new
columns, and the brief for this integration was not to change the schema.

### Data quality, honestly

OSM is volunteer-mapped, so coverage varies by area and tag:

* **Coordinates: near-universal.** Every lead sourced from Overpass in testing
  had a position.
* **Contact details: sparse.** Roughly 1 in 8 hospitals and 1 in 4 restaurants
  sampled around Ahmedabad carried a phone or website. The website-enrichment
  path (visit the site, extract contacts) still does the heavy lifting.
* **Tagging is occasionally wrong.** A node tagged `amenity=hospital` but named
  "Paldi Bus Stand" appeared in a real search. That is upstream OSM data, not a
  parsing bug, and it is not silently corrected — the lead is reported as the map
  describes it.

---

## Error handling

A provider failure never fails a search. `_query_providers` gathers every
adapter concurrently and records a `SearchProviderRun` per provider with
`completed`, `failed` or `skipped`, so the UI can explain a thin result set
instead of looking broken:

* **skipped** — no credentials, or a required input is missing (Overpass without
  a location). Nothing was sent.
* **failed** — the provider was reached and refused, or was throttled or timed
  out after retries. Other providers' results are kept.
* **completed** — results returned, possibly zero.

## Testing a provider

`POST /providers/{id}/test` performs a real authenticated round-trip using the
same credentials a search would. For OpenStreetMap and Overpass there is no
credential, so the test proves reachability and — for Nominatim — that the
required `User-Agent` is set. Overpass answering 429 is reported as "reachable
but busy" rather than as a misconfiguration, because that is what it means.

---

## Lead Source: Map / API / Auto

`POST /search` accepts an optional `mode`. **Omitting it queries every configured
provider**, which is exactly how search behaved before this existed — so
integrations that predate the feature are unaffected.

| `mode` | Queries | Needs credentials |
| --- | --- | --- |
| `map` | OpenStreetMap + Overpass | no |
| `api` | Google Places, Mappls, Geoapify, Bing, Company Website Search | yes, per provider |
| `auto` | API first; falls back to the map providers | no (degrades gracefully) |
| *(omitted)* | everything configured | — |

The split is by **capability, not by "has no credential"**. Company Website
Search also needs no key, but it crawls company websites rather than reading a
public map, so it sits on the API side — otherwise Map Mode would quietly start
fetching third-party sites.

### What Auto considers a successful API run

Any lead returned by any API provider. Not "no provider failed": a run where
Google errored and Mappls returned twelve leads is a success, and spending
Overpass calls on top of it would be waste. The fallback therefore fires when the
API side returns **zero leads** — including the common case of a fresh deployment
with no keys entered, where there is no API provider to call at all.

### Credits

The reservation covers only the providers the chosen mode can call; Auto also
reserves the map side because the fallback may run. Settlement prices the
**results actually produced, per originating provider**, so a provider that never
ran settles to zero and the over-reservation is refunded. That is what makes
"never charge for a provider that wasn't used" true by construction rather than
by a special case.

---

## Map Mode: extract, review, import

Map Mode is a review workflow rather than a one-shot search, so it is two calls:

```
POST /map/extract   keyword + location -> public results (nothing saved)
POST /map/import    selected results   -> leads, via the normal pipeline
```

Extraction is **unmetered** — OSM and Overpass are free public services, so a
preview costs nothing to serve. Credits settle on import, where leads are created.

Imported leads go through the same deduplicate → score → persist path as any
provider result, so they are indistinguishable downstream and work with the
existing lead table and exports unchanged.

### Why it is not a browser extractor over a commercial map

The brief asked for a browser-side extractor needing no API key. Built against a
commercial map's rendered page, that would mean working around its terms and its
anti-bot measures — which the same brief forbids. OpenStreetMap and Overpass
publish their data under an open licence (ODbL) and permit programmatic access,
so Map Mode gets the intended result — no API key, no extension, only publicly
available data — without needing to bypass anything. A proxy service does not
change that calculus, which is why ScraperAPI is not pointed at a map provider.

### Source tracking

Every lead records where it came from, in columns that outlive the provider row
(`Lead.provider_id` is `SET NULL` when a catalogue entry is deleted, and was
never set for scanner, import or manual leads):

| `source_type` | `source_provider` |
| --- | --- |
| `map` | `OpenStreetMap`, `Overpass API` |
| `api` | `Google Places`, `Mappls (MapmyIndia)`, `Geoapify`, `Bing Search`, … |
| `scanner` | `Website Scanner` |

Rows created before the columns existed are `NULL`, which reads correctly as
"recorded before provenance was tracked". Backfilling them would be inventing
history.

---

## ScraperAPI

A **fetch backend**, not a lead source: it holds a credential (so it appears in
the API Manager with a Test Connection) but has no adapter and never appears in a
search's provider runs.

```
GET https://api.scraperapi.com/account?api_key=…   # the Test Connection probe
GET https://api.scraperapi.com/?api_key=…&url=…    # proxied fetch
```

The account endpoint is used for testing because it is authenticated and does not
consume a request from the plan, so checking a key costs nothing. It also reports
`requestCount`/`requestLimit`, which matters: a key can be valid and still be out
of requests.

Its purpose is the website-crawling path, where real business sites sit behind
WAFs that reject datacenter IPs for reasons unrelated to the site being wrong. It
is deliberately **not** wired to any map or search provider whose terms prohibit
automated access.

---

## Mappls: what this account can actually do

Measured against the live project (`scope=READ`), one request per endpoint:

| API | Status | Used by the pipeline |
| --- | --- | --- |
| OAuth token | ✅ 200, ~23h token | yes, cached per client id |
| Text Search | ✅ 200, **paginates** 10/page | yes — primary discovery |
| Nearby | ✅ 200 (204 when nothing is in range) | yes — area-scoped discovery |
| Geocode | ✅ 200 | yes — **address components only** |
| Autosuggest | ✅ 200 | available for location input |
| Reverse Geocode | ✅ 200 | only when coords exist and address does not |
| Distance Matrix | ✅ 200 | on demand only |
| Route (`route_adv`) | ✅ 200 | on demand only |
| Snap to Road | ✅ enabled (412 `NoSegment` on off-road test points) | not used in lead search |
| Place Detail (`/places/details/json`) | ❌ 404 | — |
| Place Detail (O2O `entity/{eLoc}`) | ⚠️ 200 but returns only `{name, address, eloc}` | gap-fill only |
| POI along route | ❌ 404 on every path variant tried | unavailable |

### Coordinates are the one real gap

Neither Text Search nor Geocode returns `latitude`/`longitude` on this project.
Geocode answers 200 with a complete administrative breakdown — locality,
district, city, state, pincode, eLoc, `confidenceScore` — and no position.

So "geocode the address to get coordinates" cannot be satisfied by Mappls here.
Leads keep `lat`/`lng` as NULL rather than being given a fabricated position, and
map plotting comes from a provider that does return coordinates. The Test
Connection reports `coordinates` as a separate capability for exactly this
reason: calling Geocode "available" while it silently withholds the field it is
being relied on for would send an operator hunting in the wrong place.

### Why Nominatim resolves the search location

Mappls Text Search matches on business **name**, not area — "electrical panel
manufacturer in Bhopal" returns firms in Kerala and Haryana whose names match.
Nearby *is* area-scoped but needs a lat/lng reference point, which Mappls cannot
produce on this account.

One Nominatim lookup per search fills that single gap: it is already a
dependency (Overpass uses it identically), needs no key, and turns the same query
into Bhopal businesses. Measured: 8 nationwide name-matches before, 11 Bhopal
businesses after.

### Request budget

A 25-result search costs **4 Mappls requests**: 1 Nearby + 3 Text Search pages.
Place Detail and Geocode contributed **zero** because every result already had an
address and a parseable city — they are called only to fill a gap, never
speculatively:

```
Text Search (paginated)
  └─ Place Detail   only when a result has no address
  └─ Geocode        only when city or pincode is still missing   [cached per address]
```

Route, Distance Matrix and Snap to Road are never called by a search. Place
Detail and Geocode results are cached, so repeating a search re-runs only Text
Search.
