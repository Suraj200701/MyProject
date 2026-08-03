"""Generates the API testing documentation set from the LIVE OpenAPI spec
(the actual FastAPI app's schema — not hand-transcribed, so it can never
drift from the real routes/models).

Outputs:
    backend/docs/API_TESTING.md
    backend/docs/postman/LeadMaster_API.postman_collection.json
    backend/docs/postman/LeadMaster_API.postman_environment.json

The schema is built **in-process** from the FastAPI app rather than scraped
from a running server. Scraping meant the docs silently described whatever
process happened to be listening on a hardcoded port — including a stale one
started before the routes you just added.

Usage (no server needed):
    python -m scripts.generate_api_docs
"""

import json
import re
import uuid
from pathlib import Path
from typing import Any

from config.settings import settings

BASE_DIR = Path(__file__).resolve().parent.parent
DOCS_DIR = BASE_DIR / "docs"
POSTMAN_DIR = DOCS_DIR / "postman"
# Origin only — OpenAPI paths already carry the /api/v1 prefix. Setting this
# to ".../api/v1" made every generated Postman request resolve to
# /api/v1/api/v1/... and 404.
#
# Follows the configured PORT so the examples match how this deployment
# actually runs, instead of a hardcoded 8000 that stopped being true when
# `.env` set PORT=8001.
POSTMAN_BASE_URL = f"http://localhost:{settings.PORT}"

SAMPLE_UUID = "3fa85f64-5717-4562-b3fc-2c963f66afa6"

# Field-name heuristics for realistic example values (used when the schema
# itself gives no example/default/enum to work from).
# Ordered most-specific -> least-specific; matching tries an EXACT field-name
# hit first, then falls back to the longest substring match so a generic key
# like "name" can never preempt a compound one like "contact_name".
FIELD_EXAMPLES: dict[str, Any] = {
    "current_password": "SecurePass123",
    "new_password": "NewSecurePass456",
    "confirm_password": "SecurePass123",
    "password": "SecurePass123",
    "contact_name": "Jane Doe",
    "full_name": "Ada Founder",
    "company_name": "Acme Corp",
    "invited_by": "founder@acmecorp.com",
    "company_type": "Private Ltd",
    "company": "Acme Switchgear",
    "job_title": "VP of Sales",
    "email": "founder@acmecorp.com",
    "phone": "+91 98765 43210",
    "website": "https://acmecorp.com",
    "url": "https://acmesupplies.com",
    "query": "Panel Builders in Pune",
    "location": "Pune, India",
    "industry": "Panel Builders",
    "country": "India",
    "city": "Pune",
    "text": "Called, left a voicemail — will follow up Thursday.",
    "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "code": "482913",
    "label": "Manual backup",
    "role": "member",
    "key": "theme",
    "timezone": "Asia/Kolkata",
    "locale": "en-IN",
    "radius_km": 50,
    "address": "MG Road, Pune, Maharashtra",
    "amount_cents": 24900,
    "revenue_band": "$1M-$5M",
    "gst_number": "27AAPFU0939F1ZV",
}

NUMERIC_FIELD_EXAMPLES: dict[str, float] = {
    "lat": 18.5204,
    "lng": 73.8567,
    "rating": 4.5,
}


def _best_field_match(lname: str, table: dict[str, Any]) -> Any | None:
    if lname in table:
        return table[lname]
    matches = [k for k in table if k in lname]
    if not matches:
        return None
    best = max(matches, key=len)
    return table[best]

TAG_ORDER = [
    "Health",
    "Auth",
    "Leads",
    "Search",
    "Dashboard",
    "Analytics",
    "Billing",
    "Files",
    "Notifications",
    "Map",
    "Admin",
    "Settings",
    "Team",
    "Exports",
]

TAG_INTRO = {
    "Health": "Liveness/readiness probes — no auth required.",
    "Auth": "Signup, login, tokens, password reset, email verification, OTP login, Google OAuth, and session management.",
    "Leads": "Lead CRUD, notes, and activity timeline. Every query is scoped to the caller's current organization.",
    "Search": "Runs a lead search (persists real Lead/Company rows), lists the provider catalogue, and the website scanner.",
    "Dashboard": "Real aggregate stats/charts for the dashboard home page.",
    "Analytics": "Deeper lead-intelligence analytics: top industries/cities, quality bands, provider performance.",
    "Billing": "Stripe-backed subscriptions, checkout, usage, payments/transactions/invoices, and the webhook receiver.",
    "Files": "Upload/download/delete documents (avatars, exports, attachments) via the pluggable storage backend.",
    "Notifications": "In-app notifications, read/unread state, per-category preferences, and push subscriptions.",
    "Map": "Geocoding, nearby-place search, and distance calculation. `/map/nearby-leads` works with no API key.",
    "Admin": "Platform-wide superadmin endpoints — every route requires `is_superadmin=true` on the caller.",
    "Settings": "Profile, organization, personal API keys, generic settings store, and backup snapshots.",
    "Exports": "Export Center — generate CSV/Excel/PDF/JSON exports of leads, search results, and reports, then download them via a signed URL.",
    "Team": "Workspace membership, invitations, and role management.",
}

AUTH_NOTE_NONE = "None — public endpoint."
AUTH_NOTE_BEARER = "**Required.** `Authorization: Bearer <access_token>`"
AUTH_NOTE_BEARER_ORG = (
    "**Required.** `Authorization: Bearer <access_token>` "
    "(resolves the caller's organization automatically; pass `X-Organization-Id` "
    "to target a specific workspace if the user belongs to more than one)"
)
AUTH_NOTE_SUPERADMIN = "**Required — superadmin only.** `Authorization: Bearer <access_token>` for a user with `is_superadmin=true`."


def resolve_schema(schema: dict, components: dict, seen: set[str] | None = None) -> dict:
    """Follows $ref chains to fully resolve a schema definition."""
    seen = seen or set()
    if "$ref" in schema:
        name = schema["$ref"].split("/")[-1]
        if name in seen:
            return {}
        return resolve_schema(components["schemas"][name], components, seen | {name})

    resolved = dict(schema)
    for combinator in ("allOf", "anyOf", "oneOf"):
        if combinator in schema:
            merged: dict = {}
            for sub in schema[combinator]:
                sub_resolved = resolve_schema(sub, components, seen)
                if sub_resolved.get("type") == "null":
                    continue
                merged.update(sub_resolved)
            resolved.update(merged)
    return resolved


def example_for_field(field_name: str, schema: dict, components: dict, depth: int = 0) -> Any:
    resolved = resolve_schema(schema, components)

    if "example" in resolved:
        return resolved["example"]
    if "default" in resolved and resolved["default"] is not None:
        return resolved["default"]
    if "enum" in resolved:
        return resolved["enum"][0]

    field_type = resolved.get("type")

    if field_type == "object" or "properties" in resolved:
        if depth > 4:
            return {}
        props = resolved.get("properties", {})
        return {k: example_for_field(k, v, components, depth + 1) for k, v in props.items()}

    if field_type == "array":
        item_schema = resolved.get("items", {})
        return [example_for_field(field_name, item_schema, components, depth + 1)]

    if field_type == "boolean":
        return True

    if field_type == "integer":
        if "minimum" in resolved:
            return resolved["minimum"]
        return 1

    if field_type == "number":
        lname = field_name.lower()
        match = _best_field_match(lname, NUMERIC_FIELD_EXAMPLES)
        return match if match is not None else 4.5

    if field_type == "string":
        fmt = resolved.get("format")
        lname = field_name.lower()
        if fmt == "uuid" or lname.endswith("_id") or lname == "id":
            return SAMPLE_UUID
        if fmt in ("date-time",):
            return "2026-07-30T09:00:00Z"
        if fmt == "date":
            return "2026-07-30"
        match = _best_field_match(lname, FIELD_EXAMPLES)
        return match if match is not None else "string"

    # nullable / unresolved anyOf-with-null field
    return None


FILE_PLACEHOLDER = "@/path/to/file.pdf"


def build_request_example(operation: dict, components: dict) -> dict | None:
    body = operation.get("requestBody")
    if not body:
        return None
    content = body.get("content", {})
    json_schema = content.get("application/json", {}).get("schema")
    if not json_schema:
        return None
    return example_for_field("body", json_schema, components)


def build_form_fields(operation: dict, components: dict) -> list[dict] | None:
    """For multipart/form-data bodies (file uploads): returns a list of
    {name, value, is_file, required} — None if this operation has no such
    body."""
    body = operation.get("requestBody")
    if not body:
        return None
    content = body.get("content", {})
    form_schema = content.get("multipart/form-data", {}).get("schema")
    if not form_schema:
        return None

    resolved = resolve_schema(form_schema, components)
    required = set(resolved.get("required", []))
    fields = []
    for name, field_schema in resolved.get("properties", {}).items():
        field_resolved = resolve_schema(field_schema, components)
        is_file = field_resolved.get("format") == "binary"
        value = FILE_PLACEHOLDER if is_file else example_for_field(name, field_schema, components)
        fields.append({"name": name, "value": value, "is_file": is_file, "required": name in required})
    return fields


def build_response_example(operation: dict, components: dict) -> tuple[str, dict | list | None]:
    responses = operation.get("responses", {})
    for code in ("200", "201"):
        if code in responses:
            content = responses[code].get("content", {})
            json_schema = content.get("application/json", {}).get("schema")
            if json_schema:
                return code, example_for_field("response", json_schema, components)
            return code, None
    return next(iter(responses), "200"), None


def query_params(operation: dict) -> list[dict]:
    return [p for p in operation.get("parameters", []) if p.get("in") == "query"]


def path_params(operation: dict) -> list[dict]:
    return [p for p in operation.get("parameters", []) if p.get("in") == "path"]


def auth_note(operation: dict, path: str) -> str:
    if "/webhook" in path:
        return AUTH_NOTE_NONE + " (trust established via Stripe-Signature header verification instead)"
    if not operation.get("security"):
        return AUTH_NOTE_NONE
    if "/admin" in path:
        return AUTH_NOTE_SUPERADMIN
    org_scoped_tags = {"Leads", "Search", "Dashboard", "Analytics", "Billing", "Files", "Map", "Settings", "Team"}
    if any(t in org_scoped_tags for t in operation.get("tags", [])):
        return AUTH_NOTE_BEARER_ORG
    return AUTH_NOTE_BEARER


def build_curl(
    method: str,
    full_url: str,
    operation: dict,
    request_example: dict | None,
    form_fields: list[dict] | None = None,
) -> str:
    """Builds a copy-pasteable curl command. Each element in `parts` is one
    line's content *without* a trailing continuation backslash — those are
    added exactly once when joining, so lines never end up doubled."""
    parts = [f"curl -X {method.upper()}", f'"{full_url}"']
    if operation.get("security"):
        parts.append('-H "Authorization: Bearer $ACCESS_TOKEN"')
    if form_fields is not None:
        for field in form_fields:
            if field["is_file"]:
                parts.append(f'-F "{field["name"]}={field["value"]}"')
            elif field["value"] is not None:
                parts.append(f'-F "{field["name"]}={field["value"]}"')
    elif request_example is not None:
        parts.append('-H "Content-Type: application/json"')
        body_json = json.dumps(request_example, indent=2)
        parts.append(f"-d '{body_json}'")
    return " \\\n  ".join(parts)


def load_spec() -> dict:
    """Builds the OpenAPI schema straight from the app object.

    Importing `main` is enough — FastAPI generates the schema from the
    registered routes, so this cannot describe a different process's routes.
    """
    from main import app

    return app.openapi()


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def main() -> None:
    spec = load_spec()
    components = spec.get("components", {})
    base_url = POSTMAN_BASE_URL

    # --- group operations by tag, preserving TAG_ORDER ---
    by_tag: dict[str, list[tuple[str, str, dict]]] = {tag: [] for tag in TAG_ORDER}
    for path, methods in spec["paths"].items():
        for method, operation in methods.items():
            if method not in ("get", "post", "put", "patch", "delete"):
                continue
            tag = (operation.get("tags") or ["Other"])[0]
            by_tag.setdefault(tag, []).append((method, path, operation))

    # Anything tagged outside TAG_ORDER would be counted but never rendered,
    # which is how the entire Exports module went missing from these docs.
    unlisted = sorted(tag for tag, ops in by_tag.items() if ops and tag not in TAG_ORDER)
    if unlisted:
        raise SystemExit(
            f"Tag(s) {unlisted} are not in TAG_ORDER — their endpoints would be "
            f"silently omitted from the docs and Postman collection. Add them "
            f"(and a TAG_INTRO entry) to scripts/generate_api_docs.py."
        )

    total_endpoints = sum(len(v) for v in by_tag.values())

    # ================= Markdown =================
    md: list[str] = []
    md.append("# LeadMaster AI — API Testing Guide\n")
    md.append(
        f"Auto-generated from the FastAPI app's own OpenAPI schema — "
        f"every example below reflects the actual request/response models in the code, "
        f"not hand-written guesses. {total_endpoints} endpoints across {len([t for t in by_tag if by_tag[t]])} modules.\n"
    )
    md.append("## Base URL\n")
    md.append(f"```\n{base_url}/api/v1\n```\n")
    md.append("## Authentication\n")
    md.append(
        "Most endpoints require a JWT access token obtained from `POST /auth/login` or "
        "`POST /auth/signup`, sent as:\n\n"
        "```\nAuthorization: Bearer <access_token>\n```\n\n"
        "Endpoints tagged **org-scoped** additionally resolve the caller's active organization "
        "automatically from their membership — pass `X-Organization-Id: <uuid>` explicitly only if "
        "the user belongs to more than one workspace and you need a specific one. Admin endpoints "
        "require the caller's `is_superadmin` flag to be `true`.\n"
    )
    md.append("## Table of contents\n")
    for tag in TAG_ORDER:
        if by_tag.get(tag):
            md.append(f"- [{tag}](#{slugify(tag)}) — {len(by_tag[tag])} endpoint(s)")
    md.append("")

    for tag in TAG_ORDER:
        ops = by_tag.get(tag)
        if not ops:
            continue
        md.append(f"\n---\n\n## {tag}\n")
        if tag in TAG_INTRO:
            md.append(f"{TAG_INTRO[tag]}\n")

        for method, path, operation in ops:
            summary = operation.get("summary", "")
            full_url = f"{base_url}{path}"
            md.append(f"\n### `{method.upper()} {path}`\n")
            md.append(f"**{summary}**\n")

            md.append(f"- **Method:** `{method.upper()}`")
            md.append(f"- **URL:** `{full_url}`")
            md.append(f"- **Authentication:** {auth_note(operation, path)}")

            pparams = path_params(operation)
            if pparams:
                md.append("- **Path parameters:**")
                for p in pparams:
                    ptype = p.get("schema", {}).get("type", "string")
                    md.append(f"  - `{p['name']}` ({ptype}) — {p.get('description', 'required')}")

            qparams = query_params(operation)
            if qparams:
                md.append("- **Query parameters:**")
                for p in qparams:
                    pschema = resolve_schema(p.get("schema", {}), components)
                    ptype = pschema.get("type") or "string"
                    default = pschema.get("default")
                    required = " *(required)*" if p.get("required") else ""
                    default_str = f", default: `{default}`" if default is not None else ""
                    md.append(f"  - `{p['name']}` ({ptype}{default_str}){required}")

            request_example = build_request_example(operation, components)
            form_fields = build_form_fields(operation, components)

            md.append("\n**Headers:**")
            md.append("```")
            if operation.get("security"):
                md.append("Authorization: Bearer <access_token>")
            if request_example is not None:
                md.append("Content-Type: application/json")
            elif form_fields is not None:
                md.append("Content-Type: multipart/form-data")
            if not operation.get("security") and request_example is None and form_fields is None:
                md.append("(none required)")
            md.append("```")

            if request_example is not None:
                md.append("\n**Request Body:**")
                md.append("```json")
                md.append(json.dumps(request_example, indent=2))
                md.append("```")
            elif form_fields is not None:
                md.append("\n**Request Body** (`multipart/form-data`):")
                md.append("")
                md.append("| Field | Value | Required |")
                md.append("|---|---|---|")
                for f in form_fields:
                    label = f'file upload — {f["value"]}' if f["is_file"] else str(f["value"])
                    md.append(f'| `{f["name"]}` | {label} | {"yes" if f["required"] else "no"} |')

            status_code, response_example = build_response_example(operation, components)
            md.append(f"\n**Response Body** (`{status_code}`):")
            md.append("```json")
            md.append(json.dumps(response_example, indent=2) if response_example is not None else "{}")
            md.append("```")

            md.append("\n**Example curl:**")
            md.append("```bash")
            md.append(build_curl(method, full_url, operation, request_example, form_fields))
            md.append("```")

    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    (DOCS_DIR / "API_TESTING.md").write_text("\n".join(md), encoding="utf-8")
    print(f"Wrote {DOCS_DIR / 'API_TESTING.md'} ({total_endpoints} endpoints)")

    # ================= Postman collection =================
    collection = {
        "info": {
            "_postman_id": str(uuid.uuid4()),
            "name": "LeadMaster AI API",
            "description": "Auto-generated from the live OpenAPI schema. Run 'Auth > Login' first — "
            "it saves {{access_token}}/{{refresh_token}} automatically via a test script.",
            "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json",
        },
        "auth": {"type": "bearer", "bearer": [{"key": "token", "value": "{{access_token}}", "type": "string"}]},
        # `base_url` is the ORIGIN only. Request paths below are the full OpenAPI
        # paths and already begin with /api/v1, so a base_url that also ended in
        # /api/v1 would resolve every request to /api/v1/api/v1/... and 404.
        "variable": [{"key": "base_url", "value": POSTMAN_BASE_URL, "type": "string"}],
        "item": [],
    }

    for tag in TAG_ORDER:
        ops = by_tag.get(tag)
        if not ops:
            continue
        folder: dict = {"name": tag, "item": []}
        for method, path, operation in ops:
            request_example = build_request_example(operation, components)
            form_fields = build_form_fields(operation, components)
            item = {
                "name": operation.get("summary", f"{method.upper()} {path}"),
                "request": {
                    "method": method.upper(),
                    "header": [],
                    "url": {
                        "raw": "{{base_url}}" + path,
                        "host": ["{{base_url}}"],
                        "path": [seg for seg in path.split("/") if seg],
                    },
                },
                "response": [],
            }
            if not operation.get("security"):
                item["request"]["auth"] = {"type": "noauth"}

            qparams = query_params(operation)
            if qparams:
                item["request"]["url"]["query"] = [
                    {"key": p["name"], "value": "", "disabled": not p.get("required", False)}
                    for p in qparams
                ]

            if request_example is not None:
                item["request"]["header"].append({"key": "Content-Type", "value": "application/json"})
                item["request"]["body"] = {
                    "mode": "raw",
                    "raw": json.dumps(request_example, indent=2),
                    "options": {"raw": {"language": "json"}},
                }
            elif form_fields is not None:
                # Postman sets the multipart Content-Type + boundary itself —
                # explicitly setting the header here would break the request.
                item["request"]["body"] = {
                    "mode": "formdata",
                    "formdata": [
                        {
                            "key": f["name"],
                            "type": "file" if f["is_file"] else "text",
                            "value": "" if f["is_file"] else str(f["value"]),
                            "disabled": not f["required"],
                        }
                        for f in form_fields
                    ],
                }

            if path == "/api/v1/auth/login" and method == "post":
                item["event"] = [
                    {
                        "listen": "test",
                        "script": {
                            "type": "text/javascript",
                            "exec": [
                                "const data = pm.response.json();",
                                "if (data.access_token) {",
                                "    pm.collectionVariables.set('access_token', data.access_token);",
                                "    pm.collectionVariables.set('refresh_token', data.refresh_token);",
                                "}",
                            ],
                        },
                    }
                ]
            if path == "/api/v1/auth/signup" and method == "post":
                item["event"] = [
                    {
                        "listen": "test",
                        "script": {
                            "type": "text/javascript",
                            "exec": [
                                "const data = pm.response.json();",
                                "if (data.access_token) {",
                                "    pm.collectionVariables.set('access_token', data.access_token);",
                                "    pm.collectionVariables.set('refresh_token', data.refresh_token);",
                                "}",
                            ],
                        },
                    }
                ]

            folder["item"].append(item)
        collection["item"].append(folder)

    collection["variable"] = [
        {"key": "base_url", "value": POSTMAN_BASE_URL, "type": "string"},
        {"key": "access_token", "value": "", "type": "string"},
        {"key": "refresh_token", "value": "", "type": "string"},
    ]

    POSTMAN_DIR.mkdir(parents=True, exist_ok=True)
    (POSTMAN_DIR / "LeadMaster_API.postman_collection.json").write_text(
        json.dumps(collection, indent=2), encoding="utf-8"
    )
    print(f"Wrote {POSTMAN_DIR / 'LeadMaster_API.postman_collection.json'}")

    # ================= Postman environment =================
    environment = {
        "id": str(uuid.uuid4()),
        "name": "LeadMaster AI — Local",
        "values": [
            {"key": "base_url", "value": POSTMAN_BASE_URL, "enabled": True},
            {"key": "access_token", "value": "", "enabled": True},
            {"key": "refresh_token", "value": "", "enabled": True},
            {"key": "organization_id", "value": "", "enabled": True},
        ],
        "_postman_variable_scope": "environment",
    }
    (POSTMAN_DIR / "LeadMaster_API.postman_environment.json").write_text(
        json.dumps(environment, indent=2), encoding="utf-8"
    )
    print(f"Wrote {POSTMAN_DIR / 'LeadMaster_API.postman_environment.json'}")


if __name__ == "__main__":
    main()
