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
