# LeadMaster AI — API Testing Guide

Auto-generated from the FastAPI app's own OpenAPI schema — every example below reflects the actual request/response models in the code, not hand-written guesses. 122 endpoints across 15 modules.

## Base URL

```
http://localhost:8001/api/v1
```

## Authentication

Most endpoints require a JWT access token obtained from `POST /auth/login` or `POST /auth/signup`, sent as:

```
Authorization: Bearer <access_token>
```

Endpoints tagged **org-scoped** additionally resolve the caller's active organization automatically from their membership — pass `X-Organization-Id: <uuid>` explicitly only if the user belongs to more than one workspace and you need a specific one. Admin endpoints require the caller's `is_superadmin` flag to be `true`.

## Table of contents

- [Health](#health) — 2 endpoint(s)
- [Auth](#auth) — 16 endpoint(s)
- [Leads](#leads) — 10 endpoint(s)
- [Search](#search) — 10 endpoint(s)
- [Dashboard](#dashboard) — 7 endpoint(s)
- [Analytics](#analytics) — 5 endpoint(s)
- [Billing](#billing) — 11 endpoint(s)
- [Files](#files) — 5 endpoint(s)
- [Notifications](#notifications) — 7 endpoint(s)
- [Map](#map) — 6 endpoint(s)
- [Admin](#admin) — 10 endpoint(s)
- [Settings](#settings) — 11 endpoint(s)
- [Team](#team) — 10 endpoint(s)
- [Exports](#exports) — 7 endpoint(s)
- [Imports](#imports) — 5 endpoint(s)


---

## Health

Liveness/readiness probes — no auth required.


### `GET /api/v1/health`

**Health**

- **Method:** `GET`
- **URL:** `http://localhost:8001/api/v1/health`
- **Authentication:** None — public endpoint.

**Headers:**
```
(none required)
```

**Response Body** (`200`):
```json
{}
```

**Example curl:**
```bash
curl -X GET \
  "http://localhost:8001/api/v1/health"
```

### `GET /api/v1/health/ready`

**Readiness**

- **Method:** `GET`
- **URL:** `http://localhost:8001/api/v1/health/ready`
- **Authentication:** None — public endpoint.

**Headers:**
```
(none required)
```

**Response Body** (`200`):
```json
{}
```

**Example curl:**
```bash
curl -X GET \
  "http://localhost:8001/api/v1/health/ready"
```

---

## Auth

Signup, login, tokens, password reset, email verification, OTP login, Google OAuth, and session management.


### `POST /api/v1/auth/signup`

**Signup**

- **Method:** `POST`
- **URL:** `http://localhost:8001/api/v1/auth/signup`
- **Authentication:** None — public endpoint.

**Headers:**
```
Content-Type: application/json
```

**Request Body:**
```json
{
  "email": "founder@acmecorp.com",
  "password": "SecurePass123",
  "full_name": "Ada Founder",
  "company_name": "Acme Corp"
}
```

**Response Body** (`201`):
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "user": {
    "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "email": "founder@acmecorp.com",
    "phone": "+91 98765 43210",
    "is_active": true,
    "is_email_verified": true,
    "two_factor_enabled": true,
    "created_at": "2026-07-30T09:00:00Z",
    "last_login_at": "2026-07-30T09:00:00Z",
    "role": {
      "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
      "name": "string"
    },
    "profile": {
      "full_name": "Ada Founder",
      "avatar_url": "https://acmesupplies.com",
      "job_title": "VP of Sales",
      "timezone": "Asia/Kolkata",
      "locale": "en-IN"
    }
  }
}
```

**Example curl:**
```bash
curl -X POST \
  "http://localhost:8001/api/v1/auth/signup" \
  -H "Content-Type: application/json" \
  -d '{
  "email": "founder@acmecorp.com",
  "password": "SecurePass123",
  "full_name": "Ada Founder",
  "company_name": "Acme Corp"
}'
```

### `POST /api/v1/auth/login`

**Login**

- **Method:** `POST`
- **URL:** `http://localhost:8001/api/v1/auth/login`
- **Authentication:** None — public endpoint.

**Headers:**
```
Content-Type: application/json
```

**Request Body:**
```json
{
  "email": "founder@acmecorp.com",
  "password": "SecurePass123",
  "remember_me": false
}
```

**Response Body** (`200`):
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "user": {
    "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "email": "founder@acmecorp.com",
    "phone": "+91 98765 43210",
    "is_active": true,
    "is_email_verified": true,
    "two_factor_enabled": true,
    "created_at": "2026-07-30T09:00:00Z",
    "last_login_at": "2026-07-30T09:00:00Z",
    "role": {
      "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
      "name": "string"
    },
    "profile": {
      "full_name": "Ada Founder",
      "avatar_url": "https://acmesupplies.com",
      "job_title": "VP of Sales",
      "timezone": "Asia/Kolkata",
      "locale": "en-IN"
    }
  }
}
```

**Example curl:**
```bash
curl -X POST \
  "http://localhost:8001/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d '{
  "email": "founder@acmecorp.com",
  "password": "SecurePass123",
  "remember_me": false
}'
```

### `POST /api/v1/auth/refresh`

**Refresh**

- **Method:** `POST`
- **URL:** `http://localhost:8001/api/v1/auth/refresh`
- **Authentication:** None — public endpoint.

**Headers:**
```
Content-Type: application/json
```

**Request Body:**
```json
{
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

**Response Body** (`200`):
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "user": {
    "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "email": "founder@acmecorp.com",
    "phone": "+91 98765 43210",
    "is_active": true,
    "is_email_verified": true,
    "two_factor_enabled": true,
    "created_at": "2026-07-30T09:00:00Z",
    "last_login_at": "2026-07-30T09:00:00Z",
    "role": {
      "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
      "name": "string"
    },
    "profile": {
      "full_name": "Ada Founder",
      "avatar_url": "https://acmesupplies.com",
      "job_title": "VP of Sales",
      "timezone": "Asia/Kolkata",
      "locale": "en-IN"
    }
  }
}
```

**Example curl:**
```bash
curl -X POST \
  "http://localhost:8001/api/v1/auth/refresh" \
  -H "Content-Type: application/json" \
  -d '{
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}'
```

### `POST /api/v1/auth/logout`

**Logout**

- **Method:** `POST`
- **URL:** `http://localhost:8001/api/v1/auth/logout`
- **Authentication:** **Required.** `Authorization: Bearer <access_token>`

**Headers:**
```
Authorization: Bearer <access_token>
```

**Response Body** (`200`):
```json
{
  "success": true,
  "message": "string"
}
```

**Example curl:**
```bash
curl -X POST \
  "http://localhost:8001/api/v1/auth/logout" \
  -H "Authorization: Bearer $ACCESS_TOKEN"
```

### `GET /api/v1/auth/me`

**Me**

- **Method:** `GET`
- **URL:** `http://localhost:8001/api/v1/auth/me`
- **Authentication:** **Required.** `Authorization: Bearer <access_token>`

**Headers:**
```
Authorization: Bearer <access_token>
```

**Response Body** (`200`):
```json
{
  "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "email": "founder@acmecorp.com",
  "phone": "+91 98765 43210",
  "is_active": true,
  "is_email_verified": true,
  "two_factor_enabled": true,
  "created_at": "2026-07-30T09:00:00Z",
  "last_login_at": "2026-07-30T09:00:00Z",
  "role": {
    "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "name": "string"
  },
  "profile": {
    "full_name": "Ada Founder",
    "avatar_url": "https://acmesupplies.com",
    "job_title": "VP of Sales",
    "timezone": "Asia/Kolkata",
    "locale": "en-IN"
  }
}
```

**Example curl:**
```bash
curl -X GET \
  "http://localhost:8001/api/v1/auth/me" \
  -H "Authorization: Bearer $ACCESS_TOKEN"
```

### `POST /api/v1/auth/change-password`

**Change Password**

- **Method:** `POST`
- **URL:** `http://localhost:8001/api/v1/auth/change-password`
- **Authentication:** **Required.** `Authorization: Bearer <access_token>`

**Headers:**
```
Authorization: Bearer <access_token>
Content-Type: application/json
```

**Request Body:**
```json
{
  "current_password": "SecurePass123",
  "new_password": "NewSecurePass456"
}
```

**Response Body** (`200`):
```json
{
  "success": true,
  "message": "string"
}
```

**Example curl:**
```bash
curl -X POST \
  "http://localhost:8001/api/v1/auth/change-password" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
  "current_password": "SecurePass123",
  "new_password": "NewSecurePass456"
}'
```

### `POST /api/v1/auth/forgot-password`

**Forgot Password**

- **Method:** `POST`
- **URL:** `http://localhost:8001/api/v1/auth/forgot-password`
- **Authentication:** None — public endpoint.

**Headers:**
```
Content-Type: application/json
```

**Request Body:**
```json
{
  "email": "founder@acmecorp.com"
}
```

**Response Body** (`200`):
```json
{
  "success": true,
  "message": "string"
}
```

**Example curl:**
```bash
curl -X POST \
  "http://localhost:8001/api/v1/auth/forgot-password" \
  -H "Content-Type: application/json" \
  -d '{
  "email": "founder@acmecorp.com"
}'
```

### `POST /api/v1/auth/reset-password`

**Reset Password**

- **Method:** `POST`
- **URL:** `http://localhost:8001/api/v1/auth/reset-password`
- **Authentication:** None — public endpoint.

**Headers:**
```
Content-Type: application/json
```

**Request Body:**
```json
{
  "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "new_password": "NewSecurePass456"
}
```

**Response Body** (`200`):
```json
{
  "success": true,
  "message": "string"
}
```

**Example curl:**
```bash
curl -X POST \
  "http://localhost:8001/api/v1/auth/reset-password" \
  -H "Content-Type: application/json" \
  -d '{
  "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "new_password": "NewSecurePass456"
}'
```

### `POST /api/v1/auth/verify-email`

**Verify Email**

- **Method:** `POST`
- **URL:** `http://localhost:8001/api/v1/auth/verify-email`
- **Authentication:** None — public endpoint.

**Headers:**
```
Content-Type: application/json
```

**Request Body:**
```json
{
  "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

**Response Body** (`200`):
```json
{
  "success": true,
  "message": "string"
}
```

**Example curl:**
```bash
curl -X POST \
  "http://localhost:8001/api/v1/auth/verify-email" \
  -H "Content-Type: application/json" \
  -d '{
  "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}'
```

### `POST /api/v1/auth/resend-verification`

**Resend Verification**

- **Method:** `POST`
- **URL:** `http://localhost:8001/api/v1/auth/resend-verification`
- **Authentication:** **Required.** `Authorization: Bearer <access_token>`

**Headers:**
```
Authorization: Bearer <access_token>
```

**Response Body** (`200`):
```json
{
  "success": true,
  "message": "string"
}
```

**Example curl:**
```bash
curl -X POST \
  "http://localhost:8001/api/v1/auth/resend-verification" \
  -H "Authorization: Bearer $ACCESS_TOKEN"
```

### `POST /api/v1/auth/otp/request`

**Request Otp**

- **Method:** `POST`
- **URL:** `http://localhost:8001/api/v1/auth/otp/request`
- **Authentication:** None — public endpoint.

**Headers:**
```
Content-Type: application/json
```

**Request Body:**
```json
{
  "email": "founder@acmecorp.com",
  "purpose": "login"
}
```

**Response Body** (`200`):
```json
{
  "success": true,
  "message": "string"
}
```

**Example curl:**
```bash
curl -X POST \
  "http://localhost:8001/api/v1/auth/otp/request" \
  -H "Content-Type: application/json" \
  -d '{
  "email": "founder@acmecorp.com",
  "purpose": "login"
}'
```

### `POST /api/v1/auth/otp/verify`

**Verify Otp Endpoint**

- **Method:** `POST`
- **URL:** `http://localhost:8001/api/v1/auth/otp/verify`
- **Authentication:** None — public endpoint.

**Headers:**
```
Content-Type: application/json
```

**Request Body:**
```json
{
  "email": "founder@acmecorp.com",
  "code": "482913",
  "purpose": "login"
}
```

**Response Body** (`200`):
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "user": {
    "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "email": "founder@acmecorp.com",
    "phone": "+91 98765 43210",
    "is_active": true,
    "is_email_verified": true,
    "two_factor_enabled": true,
    "created_at": "2026-07-30T09:00:00Z",
    "last_login_at": "2026-07-30T09:00:00Z",
    "role": {
      "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
      "name": "string"
    },
    "profile": {
      "full_name": "Ada Founder",
      "avatar_url": "https://acmesupplies.com",
      "job_title": "VP of Sales",
      "timezone": "Asia/Kolkata",
      "locale": "en-IN"
    }
  }
}
```

**Example curl:**
```bash
curl -X POST \
  "http://localhost:8001/api/v1/auth/otp/verify" \
  -H "Content-Type: application/json" \
  -d '{
  "email": "founder@acmecorp.com",
  "code": "482913",
  "purpose": "login"
}'
```

### `GET /api/v1/auth/sessions`

**List Sessions**

- **Method:** `GET`
- **URL:** `http://localhost:8001/api/v1/auth/sessions`
- **Authentication:** **Required.** `Authorization: Bearer <access_token>`

**Headers:**
```
Authorization: Bearer <access_token>
```

**Response Body** (`200`):
```json
[
  {
    "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "device_label": "Manual backup",
    "ip_address": "MG Road, Pune, Maharashtra",
    "location": "Pune, India",
    "last_active_at": "2026-07-30T09:00:00Z",
    "created_at": "2026-07-30T09:00:00Z",
    "is_current": false
  }
]
```

**Example curl:**
```bash
curl -X GET \
  "http://localhost:8001/api/v1/auth/sessions" \
  -H "Authorization: Bearer $ACCESS_TOKEN"
```

### `DELETE /api/v1/auth/sessions/{session_id}`

**Revoke Session**

- **Method:** `DELETE`
- **URL:** `http://localhost:8001/api/v1/auth/sessions/{session_id}`
- **Authentication:** **Required.** `Authorization: Bearer <access_token>`
- **Path parameters:**
  - `session_id` (string) — required

**Headers:**
```
Authorization: Bearer <access_token>
```

**Response Body** (`200`):
```json
{
  "success": true,
  "message": "string"
}
```

**Example curl:**
```bash
curl -X DELETE \
  "http://localhost:8001/api/v1/auth/sessions/{session_id}" \
  -H "Authorization: Bearer $ACCESS_TOKEN"
```

### `GET /api/v1/auth/google/login`

**Google Login**

- **Method:** `GET`
- **URL:** `http://localhost:8001/api/v1/auth/google/login`
- **Authentication:** None — public endpoint.

**Headers:**
```
(none required)
```

**Response Body** (`200`):
```json
{}
```

**Example curl:**
```bash
curl -X GET \
  "http://localhost:8001/api/v1/auth/google/login"
```

### `GET /api/v1/auth/google/callback`

**Google Callback**

- **Method:** `GET`
- **URL:** `http://localhost:8001/api/v1/auth/google/callback`
- **Authentication:** None — public endpoint.
- **Query parameters:**
  - `code` (string) *(required)*
  - `state` (string) *(required)*

**Headers:**
```
(none required)
```

**Response Body** (`200`):
```json
{}
```

**Example curl:**
```bash
curl -X GET \
  "http://localhost:8001/api/v1/auth/google/callback"
```

---

## Leads

Lead CRUD, notes, and activity timeline. Every query is scoped to the caller's current organization.


### `GET /api/v1/leads`

**List Leads**

- **Method:** `GET`
- **URL:** `http://localhost:8001/api/v1/leads`
- **Authentication:** **Required.** `Authorization: Bearer <access_token>` (resolves the caller's organization automatically; pass `X-Organization-Id` to target a specific workspace if the user belongs to more than one)
- **Query parameters:**
  - `search` (string)
  - `industry` (string)
  - `status` (string)
  - `country` (string)
  - `min_score` (integer)
  - `max_score` (integer)
  - `sort_by` (string, default: `created_at`)
  - `sort_order` (string, default: `desc`)
  - `page` (integer, default: `1`)
  - `page_size` (integer, default: `20`)

**Headers:**
```
Authorization: Bearer <access_token>
```

**Response Body** (`200`):
```json
{
  "items": [
    {
      "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
      "company": "Acme Switchgear",
      "industry": "Panel Builders",
      "city": "Pune",
      "country": "India",
      "contact_name": "Jane Doe",
      "email": "founder@acmecorp.com",
      "phone": "+91 98765 43210",
      "website": "https://acmecorp.com",
      "rating": 4.5,
      "revenue_band": "$1M-$5M",
      "lead_score": 1,
      "status": "new",
      "company_type": "Private Ltd",
      "provider": "string",
      "tags": [
        "string"
      ],
      "created_at": "2026-07-30T09:00:00Z",
      "gst_number": "27AAPFU0939F1ZV",
      "lat": 18.5204,
      "lng": 73.8567,
      "ai_summary": "string"
    }
  ],
  "meta": {
    "page": 1,
    "page_size": 1,
    "total_items": 1,
    "total_pages": 1,
    "has_next": true,
    "has_previous": true
  }
}
```

**Example curl:**
```bash
curl -X GET \
  "http://localhost:8001/api/v1/leads" \
  -H "Authorization: Bearer $ACCESS_TOKEN"
```

### `POST /api/v1/leads`

**Create Lead**

- **Method:** `POST`
- **URL:** `http://localhost:8001/api/v1/leads`
- **Authentication:** **Required.** `Authorization: Bearer <access_token>` (resolves the caller's organization automatically; pass `X-Organization-Id` to target a specific workspace if the user belongs to more than one)

**Headers:**
```
Authorization: Bearer <access_token>
Content-Type: application/json
```

**Request Body:**
```json
{
  "company": "Acme Switchgear",
  "industry": "Panel Builders",
  "company_type": "Private Ltd",
  "revenue_band": "$1M-$5M",
  "website": "https://acmecorp.com",
  "gst_number": "27AAPFU0939F1ZV",
  "city": "Pune",
  "country": "India",
  "lat": 18.5204,
  "lng": 73.8567,
  "rating": 4.5,
  "contact_name": "Jane Doe",
  "email": "founder@acmecorp.com",
  "phone": "+91 98765 43210",
  "lead_score": 0,
  "status": "new",
  "tags": [
    "string"
  ],
  "ai_summary": "string"
}
```

**Response Body** (`201`):
```json
{
  "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "company": "Acme Switchgear",
  "industry": "Panel Builders",
  "city": "Pune",
  "country": "India",
  "contact_name": "Jane Doe",
  "email": "founder@acmecorp.com",
  "phone": "+91 98765 43210",
  "website": "https://acmecorp.com",
  "rating": 4.5,
  "revenue_band": "$1M-$5M",
  "lead_score": 1,
  "status": "new",
  "company_type": "Private Ltd",
  "provider": "string",
  "tags": [
    "string"
  ],
  "created_at": "2026-07-30T09:00:00Z",
  "gst_number": "27AAPFU0939F1ZV",
  "lat": 18.5204,
  "lng": 73.8567,
  "ai_summary": "string"
}
```

**Example curl:**
```bash
curl -X POST \
  "http://localhost:8001/api/v1/leads" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
  "company": "Acme Switchgear",
  "industry": "Panel Builders",
  "company_type": "Private Ltd",
  "revenue_band": "$1M-$5M",
  "website": "https://acmecorp.com",
  "gst_number": "27AAPFU0939F1ZV",
  "city": "Pune",
  "country": "India",
  "lat": 18.5204,
  "lng": 73.8567,
  "rating": 4.5,
  "contact_name": "Jane Doe",
  "email": "founder@acmecorp.com",
  "phone": "+91 98765 43210",
  "lead_score": 0,
  "status": "new",
  "tags": [
    "string"
  ],
  "ai_summary": "string"
}'
```

### `GET /api/v1/leads/{lead_id}`

**Get Lead**

- **Method:** `GET`
- **URL:** `http://localhost:8001/api/v1/leads/{lead_id}`
- **Authentication:** **Required.** `Authorization: Bearer <access_token>` (resolves the caller's organization automatically; pass `X-Organization-Id` to target a specific workspace if the user belongs to more than one)
- **Path parameters:**
  - `lead_id` (string) — required

**Headers:**
```
Authorization: Bearer <access_token>
```

**Response Body** (`200`):
```json
{
  "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "company": "Acme Switchgear",
  "industry": "Panel Builders",
  "city": "Pune",
  "country": "India",
  "contact_name": "Jane Doe",
  "email": "founder@acmecorp.com",
  "phone": "+91 98765 43210",
  "website": "https://acmecorp.com",
  "rating": 4.5,
  "revenue_band": "$1M-$5M",
  "lead_score": 1,
  "status": "new",
  "company_type": "Private Ltd",
  "provider": "string",
  "tags": [
    "string"
  ],
  "created_at": "2026-07-30T09:00:00Z",
  "gst_number": "27AAPFU0939F1ZV",
  "lat": 18.5204,
  "lng": 73.8567,
  "ai_summary": "string",
  "notes": [
    {
      "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
      "lead_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
      "author_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
      "text": "Called, left a voicemail \u2014 will follow up Thursday.",
      "created_at": "2026-07-30T09:00:00Z"
    }
  ],
  "activities": [
    {
      "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
      "lead_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
      "event_type": "string",
      "description": "string",
      "extra_data": {},
      "created_at": "2026-07-30T09:00:00Z"
    }
  ]
}
```

**Example curl:**
```bash
curl -X GET \
  "http://localhost:8001/api/v1/leads/{lead_id}" \
  -H "Authorization: Bearer $ACCESS_TOKEN"
```

### `PATCH /api/v1/leads/{lead_id}`

**Update Lead**

- **Method:** `PATCH`
- **URL:** `http://localhost:8001/api/v1/leads/{lead_id}`
- **Authentication:** **Required.** `Authorization: Bearer <access_token>` (resolves the caller's organization automatically; pass `X-Organization-Id` to target a specific workspace if the user belongs to more than one)
- **Path parameters:**
  - `lead_id` (string) — required

**Headers:**
```
Authorization: Bearer <access_token>
Content-Type: application/json
```

**Request Body:**
```json
{
  "status": "new",
  "tags": [
    "string"
  ],
  "contact_name": "Jane Doe",
  "email": "founder@acmecorp.com",
  "phone": "+91 98765 43210",
  "lead_score": 0.0,
  "ai_summary": "string"
}
```

**Response Body** (`200`):
```json
{
  "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "company": "Acme Switchgear",
  "industry": "Panel Builders",
  "city": "Pune",
  "country": "India",
  "contact_name": "Jane Doe",
  "email": "founder@acmecorp.com",
  "phone": "+91 98765 43210",
  "website": "https://acmecorp.com",
  "rating": 4.5,
  "revenue_band": "$1M-$5M",
  "lead_score": 1,
  "status": "new",
  "company_type": "Private Ltd",
  "provider": "string",
  "tags": [
    "string"
  ],
  "created_at": "2026-07-30T09:00:00Z",
  "gst_number": "27AAPFU0939F1ZV",
  "lat": 18.5204,
  "lng": 73.8567,
  "ai_summary": "string"
}
```

**Example curl:**
```bash
curl -X PATCH \
  "http://localhost:8001/api/v1/leads/{lead_id}" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
  "status": "new",
  "tags": [
    "string"
  ],
  "contact_name": "Jane Doe",
  "email": "founder@acmecorp.com",
  "phone": "+91 98765 43210",
  "lead_score": 0.0,
  "ai_summary": "string"
}'
```

### `DELETE /api/v1/leads/{lead_id}`

**Delete Lead**

- **Method:** `DELETE`
- **URL:** `http://localhost:8001/api/v1/leads/{lead_id}`
- **Authentication:** **Required.** `Authorization: Bearer <access_token>` (resolves the caller's organization automatically; pass `X-Organization-Id` to target a specific workspace if the user belongs to more than one)
- **Path parameters:**
  - `lead_id` (string) — required

**Headers:**
```
Authorization: Bearer <access_token>
```

**Response Body** (`200`):
```json
{
  "success": true,
  "message": "string"
}
```

**Example curl:**
```bash
curl -X DELETE \
  "http://localhost:8001/api/v1/leads/{lead_id}" \
  -H "Authorization: Bearer $ACCESS_TOKEN"
```

### `POST /api/v1/leads/import`

**Import Leads Csv**

- **Method:** `POST`
- **URL:** `http://localhost:8001/api/v1/leads/import`
- **Authentication:** **Required.** `Authorization: Bearer <access_token>` (resolves the caller's organization automatically; pass `X-Organization-Id` to target a specific workspace if the user belongs to more than one)

**Headers:**
```
Authorization: Bearer <access_token>
Content-Type: multipart/form-data
```

**Request Body** (`multipart/form-data`):

| Field | Value | Required |
|---|---|---|
| `file` | file upload — @/path/to/file.pdf | yes |

**Response Body** (`201`):
```json
{
  "total_rows": 1,
  "imported": 1,
  "duplicates_skipped": 1,
  "invalid_rows": 1,
  "errors": [
    {
      "line": 1,
      "message": "string",
      "company": "Acme Switchgear"
    }
  ],
  "dedup_signals": {}
}
```

**Example curl:**
```bash
curl -X POST \
  "http://localhost:8001/api/v1/leads/import" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -F "file=@/path/to/file.pdf"
```

### `POST /api/v1/leads/bulk-delete`

**Bulk Delete Leads**

- **Method:** `POST`
- **URL:** `http://localhost:8001/api/v1/leads/bulk-delete`
- **Authentication:** **Required.** `Authorization: Bearer <access_token>` (resolves the caller's organization automatically; pass `X-Organization-Id` to target a specific workspace if the user belongs to more than one)

**Headers:**
```
Authorization: Bearer <access_token>
Content-Type: application/json
```

**Request Body:**
```json
{
  "ids": [
    "3fa85f64-5717-4562-b3fc-2c963f66afa6"
  ]
}
```

**Response Body** (`200`):
```json
{
  "success": true,
  "message": "string"
}
```

**Example curl:**
```bash
curl -X POST \
  "http://localhost:8001/api/v1/leads/bulk-delete" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
  "ids": [
    "3fa85f64-5717-4562-b3fc-2c963f66afa6"
  ]
}'
```

### `POST /api/v1/leads/{lead_id}/notes`

**Add Note**

- **Method:** `POST`
- **URL:** `http://localhost:8001/api/v1/leads/{lead_id}/notes`
- **Authentication:** **Required.** `Authorization: Bearer <access_token>` (resolves the caller's organization automatically; pass `X-Organization-Id` to target a specific workspace if the user belongs to more than one)
- **Path parameters:**
  - `lead_id` (string) — required

**Headers:**
```
Authorization: Bearer <access_token>
Content-Type: application/json
```

**Request Body:**
```json
{
  "text": "Called, left a voicemail \u2014 will follow up Thursday."
}
```

**Response Body** (`201`):
```json
{
  "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "lead_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "author_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "text": "Called, left a voicemail \u2014 will follow up Thursday.",
  "created_at": "2026-07-30T09:00:00Z"
}
```

**Example curl:**
```bash
curl -X POST \
  "http://localhost:8001/api/v1/leads/{lead_id}/notes" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
  "text": "Called, left a voicemail \u2014 will follow up Thursday."
}'
```

### `GET /api/v1/leads/{lead_id}/notes`

**List Notes**

- **Method:** `GET`
- **URL:** `http://localhost:8001/api/v1/leads/{lead_id}/notes`
- **Authentication:** **Required.** `Authorization: Bearer <access_token>` (resolves the caller's organization automatically; pass `X-Organization-Id` to target a specific workspace if the user belongs to more than one)
- **Path parameters:**
  - `lead_id` (string) — required

**Headers:**
```
Authorization: Bearer <access_token>
```

**Response Body** (`200`):
```json
[
  {
    "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "lead_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "author_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "text": "Called, left a voicemail \u2014 will follow up Thursday.",
    "created_at": "2026-07-30T09:00:00Z"
  }
]
```

**Example curl:**
```bash
curl -X GET \
  "http://localhost:8001/api/v1/leads/{lead_id}/notes" \
  -H "Authorization: Bearer $ACCESS_TOKEN"
```

### `GET /api/v1/leads/{lead_id}/activities`

**List Activities**

- **Method:** `GET`
- **URL:** `http://localhost:8001/api/v1/leads/{lead_id}/activities`
- **Authentication:** **Required.** `Authorization: Bearer <access_token>` (resolves the caller's organization automatically; pass `X-Organization-Id` to target a specific workspace if the user belongs to more than one)
- **Path parameters:**
  - `lead_id` (string) — required

**Headers:**
```
Authorization: Bearer <access_token>
```

**Response Body** (`200`):
```json
[
  {
    "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "lead_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "event_type": "string",
    "description": "string",
    "extra_data": {},
    "created_at": "2026-07-30T09:00:00Z"
  }
]
```

**Example curl:**
```bash
curl -X GET \
  "http://localhost:8001/api/v1/leads/{lead_id}/activities" \
  -H "Authorization: Bearer $ACCESS_TOKEN"
```

---

## Search

Runs a lead search (persists real Lead/Company rows), lists the provider catalogue, and the website scanner.


### `POST /api/v1/search`

**Create Search**

- **Method:** `POST`
- **URL:** `http://localhost:8001/api/v1/search`
- **Authentication:** **Required.** `Authorization: Bearer <access_token>` (resolves the caller's organization automatically; pass `X-Organization-Id` to target a specific workspace if the user belongs to more than one)

**Headers:**
```
Authorization: Bearer <access_token>
Content-Type: application/json
```

**Request Body:**
```json
{
  "query": "Panel Builders in Pune",
  "location": "Pune, India",
  "industry": "Panel Builders",
  "country": "India"
}
```

**Response Body** (`201`):
```json
{
  "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "query": "Panel Builders in Pune",
  "location": "Pune, India",
  "status": "running",
  "results_count": 1,
  "created_at": "2026-07-30T09:00:00Z",
  "completed_at": "2026-07-30T09:00:00Z",
  "provider_runs": [
    {
      "provider_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
      "provider_name": "string",
      "status": "running",
      "results_found": 1
    }
  ]
}
```

**Example curl:**
```bash
curl -X POST \
  "http://localhost:8001/api/v1/search" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
  "query": "Panel Builders in Pune",
  "location": "Pune, India",
  "industry": "Panel Builders",
  "country": "India"
}'
```

### `GET /api/v1/search/history`

**Search History**

- **Method:** `GET`
- **URL:** `http://localhost:8001/api/v1/search/history`
- **Authentication:** **Required.** `Authorization: Bearer <access_token>` (resolves the caller's organization automatically; pass `X-Organization-Id` to target a specific workspace if the user belongs to more than one)
- **Query parameters:**
  - `page` (integer, default: `1`)
  - `page_size` (integer, default: `20`)

**Headers:**
```
Authorization: Bearer <access_token>
```

**Response Body** (`200`):
```json
{
  "items": [
    {
      "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
      "query": "Panel Builders in Pune",
      "location": "Pune, India",
      "status": "running",
      "results_count": 1,
      "created_at": "2026-07-30T09:00:00Z",
      "completed_at": "2026-07-30T09:00:00Z",
      "provider_runs": [
        {
          "provider_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
          "provider_name": "string",
          "status": "running",
          "results_found": 1
        }
      ]
    }
  ],
  "meta": {
    "page": 1,
    "page_size": 1,
    "total_items": 1,
    "total_pages": 1,
    "has_next": true,
    "has_previous": true
  }
}
```

**Example curl:**
```bash
curl -X GET \
  "http://localhost:8001/api/v1/search/history" \
  -H "Authorization: Bearer $ACCESS_TOKEN"
```

### `GET /api/v1/providers`

**List Providers**

- **Method:** `GET`
- **URL:** `http://localhost:8001/api/v1/providers`
- **Authentication:** None — public endpoint.

**Headers:**
```
(none required)
```

**Response Body** (`200`):
```json
[
  {
    "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "name": "string",
    "category": "Search",
    "status": "healthy",
    "logo": "string",
    "description": "string",
    "usage_count": 1,
    "usage_limit": 1,
    "latency_ms": 1,
    "connected": true
  }
]
```

**Example curl:**
```bash
curl -X GET \
  "http://localhost:8001/api/v1/providers"
```

### `GET /api/v1/providers/credentials`

**List Provider Credentials**

- **Method:** `GET`
- **URL:** `http://localhost:8001/api/v1/providers/credentials`
- **Authentication:** **Required.** `Authorization: Bearer <access_token>` (resolves the caller's organization automatically; pass `X-Organization-Id` to target a specific workspace if the user belongs to more than one)

**Headers:**
```
Authorization: Bearer <access_token>
```

**Response Body** (`200`):
```json
[
  {
    "provider_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "name": "string",
    "source": "workspace",
    "key": {
      "label": "Manual backup",
      "env_var": "string",
      "is_set": true
    },
    "secret": {
      "label": "Manual backup",
      "env_var": "string",
      "is_set": true
    },
    "help_url": "https://acmesupplies.com"
  }
]
```

**Example curl:**
```bash
curl -X GET \
  "http://localhost:8001/api/v1/providers/credentials" \
  -H "Authorization: Bearer $ACCESS_TOKEN"
```

### `PUT /api/v1/providers/{provider_id}/credentials`

**Set Provider Credentials**

- **Method:** `PUT`
- **URL:** `http://localhost:8001/api/v1/providers/{provider_id}/credentials`
- **Authentication:** **Required.** `Authorization: Bearer <access_token>` (resolves the caller's organization automatically; pass `X-Organization-Id` to target a specific workspace if the user belongs to more than one)
- **Path parameters:**
  - `provider_id` (string) — required

**Headers:**
```
Authorization: Bearer <access_token>
Content-Type: application/json
```

**Request Body:**
```json
{
  "api_key": "theme",
  "api_secret": "string"
}
```

**Response Body** (`200`):
```json
{
  "provider_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "name": "string",
  "source": "workspace",
  "key": {
    "label": "Manual backup",
    "env_var": "string",
    "is_set": true
  },
  "secret": {
    "label": "Manual backup",
    "env_var": "string",
    "is_set": true
  },
  "help_url": "https://acmesupplies.com"
}
```

**Example curl:**
```bash
curl -X PUT \
  "http://localhost:8001/api/v1/providers/{provider_id}/credentials" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
  "api_key": "theme",
  "api_secret": "string"
}'
```

### `DELETE /api/v1/providers/{provider_id}/credentials`

**Clear Provider Credentials**

- **Method:** `DELETE`
- **URL:** `http://localhost:8001/api/v1/providers/{provider_id}/credentials`
- **Authentication:** **Required.** `Authorization: Bearer <access_token>` (resolves the caller's organization automatically; pass `X-Organization-Id` to target a specific workspace if the user belongs to more than one)
- **Path parameters:**
  - `provider_id` (string) — required

**Headers:**
```
Authorization: Bearer <access_token>
```

**Response Body** (`200`):
```json
{
  "provider_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "name": "string",
  "source": "workspace",
  "key": {
    "label": "Manual backup",
    "env_var": "string",
    "is_set": true
  },
  "secret": {
    "label": "Manual backup",
    "env_var": "string",
    "is_set": true
  },
  "help_url": "https://acmesupplies.com"
}
```

**Example curl:**
```bash
curl -X DELETE \
  "http://localhost:8001/api/v1/providers/{provider_id}/credentials" \
  -H "Authorization: Bearer $ACCESS_TOKEN"
```

### `POST /api/v1/providers/{provider_id}/test`

**Test Provider Connection**

- **Method:** `POST`
- **URL:** `http://localhost:8001/api/v1/providers/{provider_id}/test`
- **Authentication:** **Required.** `Authorization: Bearer <access_token>` (resolves the caller's organization automatically; pass `X-Organization-Id` to target a specific workspace if the user belongs to more than one)
- **Path parameters:**
  - `provider_id` (string) — required

**Headers:**
```
Authorization: Bearer <access_token>
```

**Response Body** (`200`):
```json
{
  "provider": "string",
  "success": true,
  "authenticated": true,
  "message": "string",
  "latency_ms": 1,
  "details": {}
}
```

**Example curl:**
```bash
curl -X POST \
  "http://localhost:8001/api/v1/providers/{provider_id}/test" \
  -H "Authorization: Bearer $ACCESS_TOKEN"
```

### `POST /api/v1/providers/system-checks`

**System Dependency Checks**

- **Method:** `POST`
- **URL:** `http://localhost:8001/api/v1/providers/system-checks`
- **Authentication:** **Required.** `Authorization: Bearer <access_token>` (resolves the caller's organization automatically; pass `X-Organization-Id` to target a specific workspace if the user belongs to more than one)

**Headers:**
```
Authorization: Bearer <access_token>
```

**Response Body** (`200`):
```json
[
  {
    "provider": "string",
    "success": true,
    "authenticated": true,
    "message": "string",
    "latency_ms": 1,
    "details": {}
  }
]
```

**Example curl:**
```bash
curl -X POST \
  "http://localhost:8001/api/v1/providers/system-checks" \
  -H "Authorization: Bearer $ACCESS_TOKEN"
```

### `POST /api/v1/scan-website`

**Scan Website**

- **Method:** `POST`
- **URL:** `http://localhost:8001/api/v1/scan-website`
- **Authentication:** **Required.** `Authorization: Bearer <access_token>` (resolves the caller's organization automatically; pass `X-Organization-Id` to target a specific workspace if the user belongs to more than one)

**Headers:**
```
Authorization: Bearer <access_token>
Content-Type: application/json
```

**Request Body:**
```json
{
  "url": "https://acmesupplies.com"
}
```

**Response Body** (`201`):
```json
{
  "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "url": "https://acmesupplies.com",
  "domain": "string",
  "company_name": "Acme Corp",
  "contact_person": "string",
  "confidence_score": 1,
  "emails": [
    "founder@acmecorp.com"
  ],
  "phones": [
    "+91 98765 43210"
  ],
  "gst_number": "27AAPFU0939F1ZV",
  "gst_verified": true,
  "social_links": [
    {
      "platform": "string",
      "found": true,
      "handle": "string"
    }
  ],
  "ssl_valid": true,
  "mobile_friendly": true,
  "load_time_ms": 1,
  "seo_score": 1,
  "scan_duration_ms": 1,
  "created_at": "2026-07-30T09:00:00Z"
}
```

**Example curl:**
```bash
curl -X POST \
  "http://localhost:8001/api/v1/scan-website" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
  "url": "https://acmesupplies.com"
}'
```

### `GET /api/v1/scans`

**List Scans**

- **Method:** `GET`
- **URL:** `http://localhost:8001/api/v1/scans`
- **Authentication:** **Required.** `Authorization: Bearer <access_token>` (resolves the caller's organization automatically; pass `X-Organization-Id` to target a specific workspace if the user belongs to more than one)
- **Query parameters:**
  - `page` (integer, default: `1`)
  - `page_size` (integer, default: `20`)

**Headers:**
```
Authorization: Bearer <access_token>
```

**Response Body** (`200`):
```json
{
  "items": [
    {
      "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
      "url": "https://acmesupplies.com",
      "domain": "string",
      "company_name": "Acme Corp",
      "contact_person": "string",
      "confidence_score": 1,
      "emails": [
        "founder@acmecorp.com"
      ],
      "phones": [
        "+91 98765 43210"
      ],
      "gst_number": "27AAPFU0939F1ZV",
      "gst_verified": true,
      "social_links": [
        {
          "platform": "string",
          "found": true,
          "handle": "string"
        }
      ],
      "ssl_valid": true,
      "mobile_friendly": true,
      "load_time_ms": 1,
      "seo_score": 1,
      "scan_duration_ms": 1,
      "created_at": "2026-07-30T09:00:00Z"
    }
  ],
  "meta": {
    "page": 1,
    "page_size": 1,
    "total_items": 1,
    "total_pages": 1,
    "has_next": true,
    "has_previous": true
  }
}
```

**Example curl:**
```bash
curl -X GET \
  "http://localhost:8001/api/v1/scans" \
  -H "Authorization: Bearer $ACCESS_TOKEN"
```

---

## Dashboard

Real aggregate stats/charts for the dashboard home page.


### `GET /api/v1/dashboard/stats`

**Get Stats**

- **Method:** `GET`
- **URL:** `http://localhost:8001/api/v1/dashboard/stats`
- **Authentication:** **Required.** `Authorization: Bearer <access_token>` (resolves the caller's organization automatically; pass `X-Organization-Id` to target a specific workspace if the user belongs to more than one)

**Headers:**
```
Authorization: Bearer <access_token>
```

**Response Body** (`200`):
```json
{
  "total_leads": 1,
  "today_leads": 1,
  "conversion_rate": 4.5,
  "avg_lead_score": 4.5,
  "search_count": 1,
  "credits_remaining": 1,
  "credits_total": 1
}
```

**Example curl:**
```bash
curl -X GET \
  "http://localhost:8001/api/v1/dashboard/stats" \
  -H "Authorization: Bearer $ACCESS_TOKEN"
```

### `GET /api/v1/dashboard/lead-growth`

**Get Lead Growth**

- **Method:** `GET`
- **URL:** `http://localhost:8001/api/v1/dashboard/lead-growth`
- **Authentication:** **Required.** `Authorization: Bearer <access_token>` (resolves the caller's organization automatically; pass `X-Organization-Id` to target a specific workspace if the user belongs to more than one)

**Headers:**
```
Authorization: Bearer <access_token>
```

**Response Body** (`200`):
```json
[
  {
    "month": "string",
    "leads": 1,
    "converted": 1
  }
]
```

**Example curl:**
```bash
curl -X GET \
  "http://localhost:8001/api/v1/dashboard/lead-growth" \
  -H "Authorization: Bearer $ACCESS_TOKEN"
```

### `GET /api/v1/dashboard/industry-distribution`

**Get Industry Distribution**

- **Method:** `GET`
- **URL:** `http://localhost:8001/api/v1/dashboard/industry-distribution`
- **Authentication:** **Required.** `Authorization: Bearer <access_token>` (resolves the caller's organization automatically; pass `X-Organization-Id` to target a specific workspace if the user belongs to more than one)

**Headers:**
```
Authorization: Bearer <access_token>
```

**Response Body** (`200`):
```json
[
  {
    "name": "string",
    "value": 1
  }
]
```

**Example curl:**
```bash
curl -X GET \
  "http://localhost:8001/api/v1/dashboard/industry-distribution" \
  -H "Authorization: Bearer $ACCESS_TOKEN"
```

### `GET /api/v1/dashboard/country-analytics`

**Get Country Analytics**

- **Method:** `GET`
- **URL:** `http://localhost:8001/api/v1/dashboard/country-analytics`
- **Authentication:** **Required.** `Authorization: Bearer <access_token>` (resolves the caller's organization automatically; pass `X-Organization-Id` to target a specific workspace if the user belongs to more than one)

**Headers:**
```
Authorization: Bearer <access_token>
```

**Response Body** (`200`):
```json
[
  {
    "country": "India",
    "leads": 1
  }
]
```

**Example curl:**
```bash
curl -X GET \
  "http://localhost:8001/api/v1/dashboard/country-analytics" \
  -H "Authorization: Bearer $ACCESS_TOKEN"
```

### `GET /api/v1/dashboard/search-analytics`

**Get Search Analytics**

- **Method:** `GET`
- **URL:** `http://localhost:8001/api/v1/dashboard/search-analytics`
- **Authentication:** **Required.** `Authorization: Bearer <access_token>` (resolves the caller's organization automatically; pass `X-Organization-Id` to target a specific workspace if the user belongs to more than one)

**Headers:**
```
Authorization: Bearer <access_token>
```

**Response Body** (`200`):
```json
[
  {
    "day": "string",
    "searches": 1
  }
]
```

**Example curl:**
```bash
curl -X GET \
  "http://localhost:8001/api/v1/dashboard/search-analytics" \
  -H "Authorization: Bearer $ACCESS_TOKEN"
```

### `GET /api/v1/dashboard/api-usage`

**Get Api Usage**

- **Method:** `GET`
- **URL:** `http://localhost:8001/api/v1/dashboard/api-usage`
- **Authentication:** **Required.** `Authorization: Bearer <access_token>` (resolves the caller's organization automatically; pass `X-Organization-Id` to target a specific workspace if the user belongs to more than one)

**Headers:**
```
Authorization: Bearer <access_token>
```

**Response Body** (`200`):
```json
[
  {
    "name": "string",
    "usage": 1,
    "limit": 1
  }
]
```

**Example curl:**
```bash
curl -X GET \
  "http://localhost:8001/api/v1/dashboard/api-usage" \
  -H "Authorization: Bearer $ACCESS_TOKEN"
```

### `GET /api/v1/dashboard/export-analytics`

**Get Export Analytics**

- **Method:** `GET`
- **URL:** `http://localhost:8001/api/v1/dashboard/export-analytics`
- **Authentication:** **Required.** `Authorization: Bearer <access_token>` (resolves the caller's organization automatically; pass `X-Organization-Id` to target a specific workspace if the user belongs to more than one)

**Headers:**
```
Authorization: Bearer <access_token>
```

**Response Body** (`200`):
```json
[
  {
    "month": "string",
    "csv": 1,
    "excel": 1,
    "pdf": 1
  }
]
```

**Example curl:**
```bash
curl -X GET \
  "http://localhost:8001/api/v1/dashboard/export-analytics" \
  -H "Authorization: Bearer $ACCESS_TOKEN"
```

---

## Analytics

Deeper lead-intelligence analytics: top industries/cities, quality bands, provider performance.


### `GET /api/v1/analytics/top-industries`

**Get Top Industries**

- **Method:** `GET`
- **URL:** `http://localhost:8001/api/v1/analytics/top-industries`
- **Authentication:** **Required.** `Authorization: Bearer <access_token>` (resolves the caller's organization automatically; pass `X-Organization-Id` to target a specific workspace if the user belongs to more than one)

**Headers:**
```
Authorization: Bearer <access_token>
```

**Response Body** (`200`):
```json
[
  {
    "name": "string",
    "value": 1
  }
]
```

**Example curl:**
```bash
curl -X GET \
  "http://localhost:8001/api/v1/analytics/top-industries" \
  -H "Authorization: Bearer $ACCESS_TOKEN"
```

### `GET /api/v1/analytics/top-cities`

**Get Top Cities**

- **Method:** `GET`
- **URL:** `http://localhost:8001/api/v1/analytics/top-cities`
- **Authentication:** **Required.** `Authorization: Bearer <access_token>` (resolves the caller's organization automatically; pass `X-Organization-Id` to target a specific workspace if the user belongs to more than one)

**Headers:**
```
Authorization: Bearer <access_token>
```

**Response Body** (`200`):
```json
[
  {
    "city": "Pune",
    "country": "India",
    "leads": 1
  }
]
```

**Example curl:**
```bash
curl -X GET \
  "http://localhost:8001/api/v1/analytics/top-cities" \
  -H "Authorization: Bearer $ACCESS_TOKEN"
```

### `GET /api/v1/analytics/lead-quality`

**Get Lead Quality**

- **Method:** `GET`
- **URL:** `http://localhost:8001/api/v1/analytics/lead-quality`
- **Authentication:** **Required.** `Authorization: Bearer <access_token>` (resolves the caller's organization automatically; pass `X-Organization-Id` to target a specific workspace if the user belongs to more than one)

**Headers:**
```
Authorization: Bearer <access_token>
```

**Response Body** (`200`):
```json
[
  {
    "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "label": "Manual backup",
    "min_score": 1,
    "max_score": 1,
    "count": 1,
    "percentage": 4.5
  }
]
```

**Example curl:**
```bash
curl -X GET \
  "http://localhost:8001/api/v1/analytics/lead-quality" \
  -H "Authorization: Bearer $ACCESS_TOKEN"
```

### `GET /api/v1/analytics/provider-performance`

**Get Provider Performance**

- **Method:** `GET`
- **URL:** `http://localhost:8001/api/v1/analytics/provider-performance`
- **Authentication:** **Required.** `Authorization: Bearer <access_token>` (resolves the caller's organization automatically; pass `X-Organization-Id` to target a specific workspace if the user belongs to more than one)

**Headers:**
```
Authorization: Bearer <access_token>
```

**Response Body** (`200`):
```json
[
  {
    "provider_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "name": "string",
    "category": "string",
    "status": "string",
    "usage": 1,
    "usage_limit": 1,
    "leads_contributed": 1
  }
]
```

**Example curl:**
```bash
curl -X GET \
  "http://localhost:8001/api/v1/analytics/provider-performance" \
  -H "Authorization: Bearer $ACCESS_TOKEN"
```

### `GET /api/v1/analytics/business-summary`

**Get Business Summary**

- **Method:** `GET`
- **URL:** `http://localhost:8001/api/v1/analytics/business-summary`
- **Authentication:** **Required.** `Authorization: Bearer <access_token>` (resolves the caller's organization automatically; pass `X-Organization-Id` to target a specific workspace if the user belongs to more than one)

**Headers:**
```
Authorization: Bearer <access_token>
```

**Response Body** (`200`):
```json
{
  "top_company_type": "Private Ltd",
  "top_company_type_count": 0,
  "top_provider_name": "string",
  "top_provider_lead_count": 0,
  "total_companies": 0
}
```

**Example curl:**
```bash
curl -X GET \
  "http://localhost:8001/api/v1/analytics/business-summary" \
  -H "Authorization: Bearer $ACCESS_TOKEN"
```

---

## Billing

Stripe-backed subscriptions, checkout, usage, payments/transactions/invoices, and the webhook receiver.


### `GET /api/v1/billing/plans`

**List Plans**

- **Method:** `GET`
- **URL:** `http://localhost:8001/api/v1/billing/plans`
- **Authentication:** **Required.** `Authorization: Bearer <access_token>` (resolves the caller's organization automatically; pass `X-Organization-Id` to target a specific workspace if the user belongs to more than one)

**Headers:**
```
Authorization: Bearer <access_token>
```

**Response Body** (`200`):
```json
[
  {
    "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "name": "string",
    "price_cents": 1,
    "currency": "string",
    "billing_interval": "month",
    "credits_included": 1,
    "seats_included": 1,
    "features": [
      "string"
    ],
    "is_active": true
  }
]
```

**Example curl:**
```bash
curl -X GET \
  "http://localhost:8001/api/v1/billing/plans" \
  -H "Authorization: Bearer $ACCESS_TOKEN"
```

### `GET /api/v1/billing/credit-packs`

**List Credit Packs**

- **Method:** `GET`
- **URL:** `http://localhost:8001/api/v1/billing/credit-packs`
- **Authentication:** **Required.** `Authorization: Bearer <access_token>` (resolves the caller's organization automatically; pass `X-Organization-Id` to target a specific workspace if the user belongs to more than one)

**Headers:**
```
Authorization: Bearer <access_token>
```

**Response Body** (`200`):
```json
[
  {
    "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "credits": 1,
    "amount_cents": 1,
    "currency": "usd"
  }
]
```

**Example curl:**
```bash
curl -X GET \
  "http://localhost:8001/api/v1/billing/credit-packs" \
  -H "Authorization: Bearer $ACCESS_TOKEN"
```

### `GET /api/v1/billing/subscription`

**Get Subscription**

- **Method:** `GET`
- **URL:** `http://localhost:8001/api/v1/billing/subscription`
- **Authentication:** **Required.** `Authorization: Bearer <access_token>` (resolves the caller's organization automatically; pass `X-Organization-Id` to target a specific workspace if the user belongs to more than one)

**Headers:**
```
Authorization: Bearer <access_token>
```

**Response Body** (`200`):
```json
{
  "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "plan": {
    "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "name": "string",
    "price_cents": 1,
    "currency": "string",
    "billing_interval": "month",
    "credits_included": 1,
    "seats_included": 1,
    "features": [
      "string"
    ],
    "is_active": true
  },
  "status": "trialing",
  "current_period_start": "2026-07-30T09:00:00Z",
  "current_period_end": "2026-07-30T09:00:00Z",
  "cancel_at_period_end": true
}
```

**Example curl:**
```bash
curl -X GET \
  "http://localhost:8001/api/v1/billing/subscription" \
  -H "Authorization: Bearer $ACCESS_TOKEN"
```

### `GET /api/v1/billing/usage`

**Get Usage**

- **Method:** `GET`
- **URL:** `http://localhost:8001/api/v1/billing/usage`
- **Authentication:** **Required.** `Authorization: Bearer <access_token>` (resolves the caller's organization automatically; pass `X-Organization-Id` to target a specific workspace if the user belongs to more than one)

**Headers:**
```
Authorization: Bearer <access_token>
```

**Response Body** (`200`):
```json
{
  "credits_used": 1,
  "credits_limit": 1,
  "seats_used": 1,
  "seats_limit": 1,
  "searches_this_month": 1,
  "exports_this_month": 1
}
```

**Example curl:**
```bash
curl -X GET \
  "http://localhost:8001/api/v1/billing/usage" \
  -H "Authorization: Bearer $ACCESS_TOKEN"
```

### `POST /api/v1/billing/checkout`

**Create Checkout**

- **Method:** `POST`
- **URL:** `http://localhost:8001/api/v1/billing/checkout`
- **Authentication:** **Required.** `Authorization: Bearer <access_token>` (resolves the caller's organization automatically; pass `X-Organization-Id` to target a specific workspace if the user belongs to more than one)

**Headers:**
```
Authorization: Bearer <access_token>
Content-Type: application/json
```

**Request Body:**
```json
{
  "plan_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6"
}
```

**Response Body** (`200`):
```json
{
  "checkout_url": "https://acmesupplies.com"
}
```

**Example curl:**
```bash
curl -X POST \
  "http://localhost:8001/api/v1/billing/checkout" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
  "plan_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6"
}'
```

### `POST /api/v1/billing/credits/checkout`

**Create Credit Topup Checkout**

- **Method:** `POST`
- **URL:** `http://localhost:8001/api/v1/billing/credits/checkout`
- **Authentication:** **Required.** `Authorization: Bearer <access_token>` (resolves the caller's organization automatically; pass `X-Organization-Id` to target a specific workspace if the user belongs to more than one)

**Headers:**
```
Authorization: Bearer <access_token>
Content-Type: application/json
```

**Request Body:**
```json
{
  "amount_cents": 100.0,
  "pack_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6"
}
```

**Response Body** (`200`):
```json
{
  "checkout_url": "https://acmesupplies.com"
}
```

**Example curl:**
```bash
curl -X POST \
  "http://localhost:8001/api/v1/billing/credits/checkout" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
  "amount_cents": 100.0,
  "pack_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6"
}'
```

### `GET /api/v1/billing/payments`

**List Payments**

- **Method:** `GET`
- **URL:** `http://localhost:8001/api/v1/billing/payments`
- **Authentication:** **Required.** `Authorization: Bearer <access_token>` (resolves the caller's organization automatically; pass `X-Organization-Id` to target a specific workspace if the user belongs to more than one)
- **Query parameters:**
  - `page` (integer, default: `1`)
  - `page_size` (integer, default: `20`)

**Headers:**
```
Authorization: Bearer <access_token>
```

**Response Body** (`200`):
```json
{
  "items": [
    {
      "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
      "amount_cents": 1,
      "currency": "string",
      "status": "pending",
      "payment_method_type": "string",
      "failure_reason": "string",
      "created_at": "2026-07-30T09:00:00Z"
    }
  ],
  "meta": {
    "page": 1,
    "page_size": 1,
    "total_items": 1,
    "total_pages": 1,
    "has_next": true,
    "has_previous": true
  }
}
```

**Example curl:**
```bash
curl -X GET \
  "http://localhost:8001/api/v1/billing/payments" \
  -H "Authorization: Bearer $ACCESS_TOKEN"
```

### `GET /api/v1/billing/transactions`

**List Transactions**

- **Method:** `GET`
- **URL:** `http://localhost:8001/api/v1/billing/transactions`
- **Authentication:** **Required.** `Authorization: Bearer <access_token>` (resolves the caller's organization automatically; pass `X-Organization-Id` to target a specific workspace if the user belongs to more than one)
- **Query parameters:**
  - `page` (integer, default: `1`)
  - `page_size` (integer, default: `20`)

**Headers:**
```
Authorization: Bearer <access_token>
```

**Response Body** (`200`):
```json
{
  "items": [
    {
      "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
      "type": "subscription_charge",
      "amount_cents": 1,
      "credits_delta": 1,
      "balance_after": 1,
      "description": "string",
      "created_at": "2026-07-30T09:00:00Z"
    }
  ],
  "meta": {
    "page": 1,
    "page_size": 1,
    "total_items": 1,
    "total_pages": 1,
    "has_next": true,
    "has_previous": true
  }
}
```

**Example curl:**
```bash
curl -X GET \
  "http://localhost:8001/api/v1/billing/transactions" \
  -H "Authorization: Bearer $ACCESS_TOKEN"
```

### `GET /api/v1/billing/invoices`

**List Invoices**

- **Method:** `GET`
- **URL:** `http://localhost:8001/api/v1/billing/invoices`
- **Authentication:** **Required.** `Authorization: Bearer <access_token>` (resolves the caller's organization automatically; pass `X-Organization-Id` to target a specific workspace if the user belongs to more than one)
- **Query parameters:**
  - `page` (integer, default: `1`)
  - `page_size` (integer, default: `20`)

**Headers:**
```
Authorization: Bearer <access_token>
```

**Response Body** (`200`):
```json
{
  "items": [
    {
      "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
      "invoice_number": "string",
      "amount_cents": 1,
      "currency": "string",
      "status": "paid",
      "invoice_pdf_url": "https://acmesupplies.com",
      "period_start": "2026-07-30T09:00:00Z",
      "period_end": "2026-07-30T09:00:00Z",
      "created_at": "2026-07-30T09:00:00Z"
    }
  ],
  "meta": {
    "page": 1,
    "page_size": 1,
    "total_items": 1,
    "total_pages": 1,
    "has_next": true,
    "has_previous": true
  }
}
```

**Example curl:**
```bash
curl -X GET \
  "http://localhost:8001/api/v1/billing/invoices" \
  -H "Authorization: Bearer $ACCESS_TOKEN"
```

### `POST /api/v1/billing/payments/{payment_id}/refund`

**Refund Payment**

- **Method:** `POST`
- **URL:** `http://localhost:8001/api/v1/billing/payments/{payment_id}/refund`
- **Authentication:** **Required.** `Authorization: Bearer <access_token>` (resolves the caller's organization automatically; pass `X-Organization-Id` to target a specific workspace if the user belongs to more than one)
- **Path parameters:**
  - `payment_id` (string) — required

**Headers:**
```
Authorization: Bearer <access_token>
```

**Response Body** (`200`):
```json
{
  "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "amount_cents": 1,
  "currency": "string",
  "status": "pending",
  "payment_method_type": "string",
  "failure_reason": "string",
  "created_at": "2026-07-30T09:00:00Z"
}
```

**Example curl:**
```bash
curl -X POST \
  "http://localhost:8001/api/v1/billing/payments/{payment_id}/refund" \
  -H "Authorization: Bearer $ACCESS_TOKEN"
```

### `POST /api/v1/billing/webhook`

**Stripe Webhook**

- **Method:** `POST`
- **URL:** `http://localhost:8001/api/v1/billing/webhook`
- **Authentication:** None — public endpoint. (trust established via Stripe-Signature header verification instead)

**Headers:**
```
(none required)
```

**Response Body** (`200`):
```json
{
  "success": true,
  "message": "string"
}
```

**Example curl:**
```bash
curl -X POST \
  "http://localhost:8001/api/v1/billing/webhook"
```

---

## Files

Upload/download/delete documents (avatars, exports, attachments) via the pluggable storage backend.


### `POST /api/v1/files/upload`

**Upload File**

- **Method:** `POST`
- **URL:** `http://localhost:8001/api/v1/files/upload`
- **Authentication:** **Required.** `Authorization: Bearer <access_token>` (resolves the caller's organization automatically; pass `X-Organization-Id` to target a specific workspace if the user belongs to more than one)

**Headers:**
```
Authorization: Bearer <access_token>
Content-Type: multipart/form-data
```

**Request Body** (`multipart/form-data`):

| Field | Value | Required |
|---|---|---|
| `file` | file upload — @/path/to/file.pdf | yes |
| `kind` | document | no |
| `entity_type` | string | no |
| `entity_id` | 3fa85f64-5717-4562-b3fc-2c963f66afa6 | no |

**Response Body** (`201`):
```json
{
  "success": true,
  "document": {
    "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "file_name": "string",
    "original_name": "string",
    "mime_type": "string",
    "size_bytes": 1,
    "entity_type": "string",
    "entity_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "created_at": "2026-07-30T09:00:00Z",
    "download_url": "https://acmesupplies.com"
  }
}
```

**Example curl:**
```bash
curl -X POST \
  "http://localhost:8001/api/v1/files/upload" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -F "file=@/path/to/file.pdf" \
  -F "kind=document" \
  -F "entity_type=string" \
  -F "entity_id=3fa85f64-5717-4562-b3fc-2c963f66afa6"
```

### `GET /api/v1/files`

**List Files**

- **Method:** `GET`
- **URL:** `http://localhost:8001/api/v1/files`
- **Authentication:** **Required.** `Authorization: Bearer <access_token>` (resolves the caller's organization automatically; pass `X-Organization-Id` to target a specific workspace if the user belongs to more than one)
- **Query parameters:**
  - `entity_type` (string)
  - `page` (integer, default: `1`)
  - `page_size` (integer, default: `20`)

**Headers:**
```
Authorization: Bearer <access_token>
```

**Response Body** (`200`):
```json
{
  "items": [
    {
      "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
      "file_name": "string",
      "original_name": "string",
      "mime_type": "string",
      "size_bytes": 1,
      "entity_type": "string",
      "entity_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
      "created_at": "2026-07-30T09:00:00Z",
      "download_url": "https://acmesupplies.com"
    }
  ],
  "meta": {
    "page": 1,
    "page_size": 1,
    "total_items": 1,
    "total_pages": 1,
    "has_next": true,
    "has_previous": true
  }
}
```

**Example curl:**
```bash
curl -X GET \
  "http://localhost:8001/api/v1/files" \
  -H "Authorization: Bearer $ACCESS_TOKEN"
```

### `GET /api/v1/files/{document_id}`

**Get File Metadata**

- **Method:** `GET`
- **URL:** `http://localhost:8001/api/v1/files/{document_id}`
- **Authentication:** **Required.** `Authorization: Bearer <access_token>` (resolves the caller's organization automatically; pass `X-Organization-Id` to target a specific workspace if the user belongs to more than one)
- **Path parameters:**
  - `document_id` (string) — required

**Headers:**
```
Authorization: Bearer <access_token>
```

**Response Body** (`200`):
```json
{
  "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "file_name": "string",
  "original_name": "string",
  "mime_type": "string",
  "size_bytes": 1,
  "entity_type": "string",
  "entity_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "created_at": "2026-07-30T09:00:00Z",
  "download_url": "https://acmesupplies.com"
}
```

**Example curl:**
```bash
curl -X GET \
  "http://localhost:8001/api/v1/files/{document_id}" \
  -H "Authorization: Bearer $ACCESS_TOKEN"
```

### `DELETE /api/v1/files/{document_id}`

**Delete File**

- **Method:** `DELETE`
- **URL:** `http://localhost:8001/api/v1/files/{document_id}`
- **Authentication:** **Required.** `Authorization: Bearer <access_token>` (resolves the caller's organization automatically; pass `X-Organization-Id` to target a specific workspace if the user belongs to more than one)
- **Path parameters:**
  - `document_id` (string) — required

**Headers:**
```
Authorization: Bearer <access_token>
```

**Response Body** (`200`):
```json
{
  "success": true,
  "message": "string"
}
```

**Example curl:**
```bash
curl -X DELETE \
  "http://localhost:8001/api/v1/files/{document_id}" \
  -H "Authorization: Bearer $ACCESS_TOKEN"
```

### `GET /api/v1/files/{document_id}/download`

**Download File**

- **Method:** `GET`
- **URL:** `http://localhost:8001/api/v1/files/{document_id}/download`
- **Authentication:** **Required.** `Authorization: Bearer <access_token>` (resolves the caller's organization automatically; pass `X-Organization-Id` to target a specific workspace if the user belongs to more than one)
- **Path parameters:**
  - `document_id` (string) — required

**Headers:**
```
Authorization: Bearer <access_token>
```

**Response Body** (`200`):
```json
{}
```

**Example curl:**
```bash
curl -X GET \
  "http://localhost:8001/api/v1/files/{document_id}/download" \
  -H "Authorization: Bearer $ACCESS_TOKEN"
```

---

## Notifications

In-app notifications, read/unread state, per-category preferences, and push subscriptions.


### `GET /api/v1/notifications`

**List Notifications**

- **Method:** `GET`
- **URL:** `http://localhost:8001/api/v1/notifications`
- **Authentication:** **Required.** `Authorization: Bearer <access_token>`
- **Query parameters:**
  - `unread_only` (boolean, default: `False`)
  - `page` (integer, default: `1`)
  - `page_size` (integer, default: `20`)

**Headers:**
```
Authorization: Bearer <access_token>
```

**Response Body** (`200`):
```json
{
  "items": [
    {
      "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
      "type": "search",
      "title": "string",
      "description": "string",
      "created_at": "2026-07-30T09:00:00Z",
      "read": true
    }
  ],
  "meta": {
    "page": 1,
    "page_size": 1,
    "total_items": 1,
    "total_pages": 1,
    "has_next": true,
    "has_previous": true
  }
}
```

**Example curl:**
```bash
curl -X GET \
  "http://localhost:8001/api/v1/notifications" \
  -H "Authorization: Bearer $ACCESS_TOKEN"
```

### `GET /api/v1/notifications/unread-count`

**Unread Count**

- **Method:** `GET`
- **URL:** `http://localhost:8001/api/v1/notifications/unread-count`
- **Authentication:** **Required.** `Authorization: Bearer <access_token>`

**Headers:**
```
Authorization: Bearer <access_token>
```

**Response Body** (`200`):
```json
{
  "success": true,
  "data": 1
}
```

**Example curl:**
```bash
curl -X GET \
  "http://localhost:8001/api/v1/notifications/unread-count" \
  -H "Authorization: Bearer $ACCESS_TOKEN"
```

### `POST /api/v1/notifications/{notification_id}/read`

**Mark Read**

- **Method:** `POST`
- **URL:** `http://localhost:8001/api/v1/notifications/{notification_id}/read`
- **Authentication:** **Required.** `Authorization: Bearer <access_token>`
- **Path parameters:**
  - `notification_id` (string) — required

**Headers:**
```
Authorization: Bearer <access_token>
```

**Response Body** (`200`):
```json
{
  "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "type": "search",
  "title": "string",
  "description": "string",
  "created_at": "2026-07-30T09:00:00Z",
  "read": true
}
```

**Example curl:**
```bash
curl -X POST \
  "http://localhost:8001/api/v1/notifications/{notification_id}/read" \
  -H "Authorization: Bearer $ACCESS_TOKEN"
```

### `POST /api/v1/notifications/read-all`

**Mark All Read**

- **Method:** `POST`
- **URL:** `http://localhost:8001/api/v1/notifications/read-all`
- **Authentication:** **Required.** `Authorization: Bearer <access_token>`

**Headers:**
```
Authorization: Bearer <access_token>
```

**Response Body** (`200`):
```json
{
  "success": true,
  "message": "string"
}
```

**Example curl:**
```bash
curl -X POST \
  "http://localhost:8001/api/v1/notifications/read-all" \
  -H "Authorization: Bearer $ACCESS_TOKEN"
```

### `GET /api/v1/notifications/preferences`

**Get Preferences**

- **Method:** `GET`
- **URL:** `http://localhost:8001/api/v1/notifications/preferences`
- **Authentication:** **Required.** `Authorization: Bearer <access_token>`

**Headers:**
```
Authorization: Bearer <access_token>
```

**Response Body** (`200`):
```json
[
  {
    "category": "search",
    "email_enabled": true,
    "push_enabled": true,
    "in_app_enabled": true
  }
]
```

**Example curl:**
```bash
curl -X GET \
  "http://localhost:8001/api/v1/notifications/preferences" \
  -H "Authorization: Bearer $ACCESS_TOKEN"
```

### `PATCH /api/v1/notifications/preferences/{category}`

**Update Preference**

- **Method:** `PATCH`
- **URL:** `http://localhost:8001/api/v1/notifications/preferences/{category}`
- **Authentication:** **Required.** `Authorization: Bearer <access_token>`
- **Path parameters:**
  - `category` (string) — required

**Headers:**
```
Authorization: Bearer <access_token>
Content-Type: application/json
```

**Request Body:**
```json
{
  "email_enabled": true,
  "push_enabled": true,
  "in_app_enabled": true
}
```

**Response Body** (`200`):
```json
{
  "category": "search",
  "email_enabled": true,
  "push_enabled": true,
  "in_app_enabled": true
}
```

**Example curl:**
```bash
curl -X PATCH \
  "http://localhost:8001/api/v1/notifications/preferences/{category}" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
  "email_enabled": true,
  "push_enabled": true,
  "in_app_enabled": true
}'
```

### `POST /api/v1/notifications/push-subscriptions`

**Register Push Subscription**

- **Method:** `POST`
- **URL:** `http://localhost:8001/api/v1/notifications/push-subscriptions`
- **Authentication:** **Required.** `Authorization: Bearer <access_token>`

**Headers:**
```
Authorization: Bearer <access_token>
Content-Type: application/json
```

**Request Body:**
```json
{
  "endpoint": "string",
  "p256dh_key": "theme",
  "auth_key": "theme"
}
```

**Response Body** (`201`):
```json
{
  "success": true,
  "message": "string"
}
```

**Example curl:**
```bash
curl -X POST \
  "http://localhost:8001/api/v1/notifications/push-subscriptions" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
  "endpoint": "string",
  "p256dh_key": "theme",
  "auth_key": "theme"
}'
```

---

## Map

Geocoding, nearby-place search, and distance calculation. `/map/nearby-leads` works with no API key.


### `POST /api/v1/map/geocode`

**Geocode**

- **Method:** `POST`
- **URL:** `http://localhost:8001/api/v1/map/geocode`
- **Authentication:** **Required.** `Authorization: Bearer <access_token>` (resolves the caller's organization automatically; pass `X-Organization-Id` to target a specific workspace if the user belongs to more than one)

**Headers:**
```
Authorization: Bearer <access_token>
Content-Type: application/json
```

**Request Body:**
```json
{
  "address": "MG Road, Pune, Maharashtra"
}
```

**Response Body** (`200`):
```json
{
  "lat": 18.5204,
  "lng": 73.8567,
  "formatted_address": "MG Road, Pune, Maharashtra"
}
```

**Example curl:**
```bash
curl -X POST \
  "http://localhost:8001/api/v1/map/geocode" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
  "address": "MG Road, Pune, Maharashtra"
}'
```

### `GET /api/v1/map/reverse-geocode`

**Reverse Geocode**

- **Method:** `GET`
- **URL:** `http://localhost:8001/api/v1/map/reverse-geocode`
- **Authentication:** **Required.** `Authorization: Bearer <access_token>` (resolves the caller's organization automatically; pass `X-Organization-Id` to target a specific workspace if the user belongs to more than one)
- **Query parameters:**
  - `lat` (number) *(required)*
  - `lng` (number) *(required)*

**Headers:**
```
Authorization: Bearer <access_token>
```

**Response Body** (`200`):
```json
{
  "lat": 18.5204,
  "lng": 73.8567,
  "formatted_address": "MG Road, Pune, Maharashtra"
}
```

**Example curl:**
```bash
curl -X GET \
  "http://localhost:8001/api/v1/map/reverse-geocode" \
  -H "Authorization: Bearer $ACCESS_TOKEN"
```

### `GET /api/v1/map/autocomplete`

**Autocomplete**

- **Method:** `GET`
- **URL:** `http://localhost:8001/api/v1/map/autocomplete`
- **Authentication:** **Required.** `Authorization: Bearer <access_token>` (resolves the caller's organization automatically; pass `X-Organization-Id` to target a specific workspace if the user belongs to more than one)
- **Query parameters:**
  - `query` (string) *(required)*
  - `lat` (number)
  - `lng` (number)

**Headers:**
```
Authorization: Bearer <access_token>
```

**Response Body** (`200`):
```json
{}
```

**Example curl:**
```bash
curl -X GET \
  "http://localhost:8001/api/v1/map/autocomplete" \
  -H "Authorization: Bearer $ACCESS_TOKEN"
```

### `POST /api/v1/map/nearby-leads`

**Nearby Leads**

- **Method:** `POST`
- **URL:** `http://localhost:8001/api/v1/map/nearby-leads`
- **Authentication:** **Required.** `Authorization: Bearer <access_token>` (resolves the caller's organization automatically; pass `X-Organization-Id` to target a specific workspace if the user belongs to more than one)

**Headers:**
```
Authorization: Bearer <access_token>
Content-Type: application/json
```

**Request Body:**
```json
{
  "lat": 18.5204,
  "lng": 73.8567,
  "radius_km": 50,
  "industry": "Panel Builders"
}
```

**Response Body** (`200`):
```json
[
  {
    "lead_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "company_name": "Acme Corp",
    "lat": 18.5204,
    "lng": 73.8567,
    "distance_km": 4.5,
    "lead_score": 1,
    "industry": "Panel Builders",
    "city": "Pune"
  }
]
```

**Example curl:**
```bash
curl -X POST \
  "http://localhost:8001/api/v1/map/nearby-leads" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
  "lat": 18.5204,
  "lng": 73.8567,
  "radius_km": 50,
  "industry": "Panel Builders"
}'
```

### `GET /api/v1/map/nearby-places`

**Nearby Places**

- **Method:** `GET`
- **URL:** `http://localhost:8001/api/v1/map/nearby-places`
- **Authentication:** **Required.** `Authorization: Bearer <access_token>` (resolves the caller's organization automatically; pass `X-Organization-Id` to target a specific workspace if the user belongs to more than one)
- **Query parameters:**
  - `lat` (number) *(required)*
  - `lng` (number) *(required)*
  - `radius_meters` (integer, default: `1500`)
  - `keyword` (string)

**Headers:**
```
Authorization: Bearer <access_token>
```

**Response Body** (`200`):
```json
{}
```

**Example curl:**
```bash
curl -X GET \
  "http://localhost:8001/api/v1/map/nearby-places" \
  -H "Authorization: Bearer $ACCESS_TOKEN"
```

### `POST /api/v1/map/distance-matrix`

**Distance Matrix**

- **Method:** `POST`
- **URL:** `http://localhost:8001/api/v1/map/distance-matrix`
- **Authentication:** **Required.** `Authorization: Bearer <access_token>` (resolves the caller's organization automatically; pass `X-Organization-Id` to target a specific workspace if the user belongs to more than one)
- **Query parameters:**
  - `origin_lat` (number) *(required)*
  - `origin_lng` (number) *(required)*
  - `destinations` (array) *(required)*

**Headers:**
```
Authorization: Bearer <access_token>
```

**Response Body** (`200`):
```json
{}
```

**Example curl:**
```bash
curl -X POST \
  "http://localhost:8001/api/v1/map/distance-matrix" \
  -H "Authorization: Bearer $ACCESS_TOKEN"
```

---

## Admin

Platform-wide superadmin endpoints — every route requires `is_superadmin=true` on the caller.


### `GET /api/v1/admin/stats`

**Get Stats**

- **Method:** `GET`
- **URL:** `http://localhost:8001/api/v1/admin/stats`
- **Authentication:** **Required — superadmin only.** `Authorization: Bearer <access_token>` for a user with `is_superadmin=true`.

**Headers:**
```
Authorization: Bearer <access_token>
```

**Response Body** (`200`):
```json
{
  "total_users": 1,
  "total_organizations": 1,
  "total_leads_platform_wide": 1,
  "mrr_cents": 1,
  "active_subscriptions_count": 1,
  "total_searches_platform_wide": 1
}
```

**Example curl:**
```bash
curl -X GET \
  "http://localhost:8001/api/v1/admin/stats" \
  -H "Authorization: Bearer $ACCESS_TOKEN"
```

### `GET /api/v1/admin/users`

**List Users**

- **Method:** `GET`
- **URL:** `http://localhost:8001/api/v1/admin/users`
- **Authentication:** **Required — superadmin only.** `Authorization: Bearer <access_token>` for a user with `is_superadmin=true`.
- **Query parameters:**
  - `search` (string)
  - `is_active` (boolean)
  - `page` (integer, default: `1`)
  - `page_size` (integer, default: `20`)

**Headers:**
```
Authorization: Bearer <access_token>
```

**Response Body** (`200`):
```json
{
  "items": [
    {
      "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
      "email": "founder@acmecorp.com",
      "is_active": true,
      "is_superadmin": true,
      "role": "owner",
      "organizations": [],
      "created_at": "2026-07-30T09:00:00Z",
      "last_login_at": "2026-07-30T09:00:00Z"
    }
  ],
  "meta": {
    "page": 1,
    "page_size": 1,
    "total_items": 1,
    "total_pages": 1,
    "has_next": true,
    "has_previous": true
  }
}
```

**Example curl:**
```bash
curl -X GET \
  "http://localhost:8001/api/v1/admin/users" \
  -H "Authorization: Bearer $ACCESS_TOKEN"
```

### `PATCH /api/v1/admin/users/{user_id}/status`

**Set User Status**

- **Method:** `PATCH`
- **URL:** `http://localhost:8001/api/v1/admin/users/{user_id}/status`
- **Authentication:** **Required — superadmin only.** `Authorization: Bearer <access_token>` for a user with `is_superadmin=true`.
- **Path parameters:**
  - `user_id` (string) — required

**Headers:**
```
Authorization: Bearer <access_token>
Content-Type: application/json
```

**Request Body:**
```json
{
  "is_active": true
}
```

**Response Body** (`200`):
```json
{
  "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "email": "founder@acmecorp.com",
  "is_active": true,
  "is_superadmin": true,
  "role": "owner",
  "organizations": [],
  "created_at": "2026-07-30T09:00:00Z",
  "last_login_at": "2026-07-30T09:00:00Z"
}
```

**Example curl:**
```bash
curl -X PATCH \
  "http://localhost:8001/api/v1/admin/users/{user_id}/status" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
  "is_active": true
}'
```

### `GET /api/v1/admin/organizations`

**List Organizations**

- **Method:** `GET`
- **URL:** `http://localhost:8001/api/v1/admin/organizations`
- **Authentication:** **Required — superadmin only.** `Authorization: Bearer <access_token>` for a user with `is_superadmin=true`.
- **Query parameters:**
  - `search` (string)
  - `page` (integer, default: `1`)
  - `page_size` (integer, default: `20`)

**Headers:**
```
Authorization: Bearer <access_token>
```

**Response Body** (`200`):
```json
{
  "items": [
    {
      "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
      "name": "string",
      "owner_email": "founder@acmecorp.com",
      "member_count": 1,
      "plan_name": "string",
      "subscription_status": "trialing",
      "created_at": "2026-07-30T09:00:00Z"
    }
  ],
  "meta": {
    "page": 1,
    "page_size": 1,
    "total_items": 1,
    "total_pages": 1,
    "has_next": true,
    "has_previous": true
  }
}
```

**Example curl:**
```bash
curl -X GET \
  "http://localhost:8001/api/v1/admin/organizations" \
  -H "Authorization: Bearer $ACCESS_TOKEN"
```

### `GET /api/v1/admin/organizations/{org_id}`

**Get Organization**

- **Method:** `GET`
- **URL:** `http://localhost:8001/api/v1/admin/organizations/{org_id}`
- **Authentication:** **Required — superadmin only.** `Authorization: Bearer <access_token>` for a user with `is_superadmin=true`.
- **Path parameters:**
  - `org_id` (string) — required

**Headers:**
```
Authorization: Bearer <access_token>
```

**Response Body** (`200`):
```json
{
  "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "name": "string",
  "owner_email": "founder@acmecorp.com",
  "member_count": 1,
  "plan_name": "string",
  "subscription_status": "trialing",
  "created_at": "2026-07-30T09:00:00Z"
}
```

**Example curl:**
```bash
curl -X GET \
  "http://localhost:8001/api/v1/admin/organizations/{org_id}" \
  -H "Authorization: Bearer $ACCESS_TOKEN"
```

### `GET /api/v1/admin/subscriptions`

**List Subscriptions**

- **Method:** `GET`
- **URL:** `http://localhost:8001/api/v1/admin/subscriptions`
- **Authentication:** **Required — superadmin only.** `Authorization: Bearer <access_token>` for a user with `is_superadmin=true`.
- **Query parameters:**
  - `status` (string)
  - `page` (integer, default: `1`)
  - `page_size` (integer, default: `20`)

**Headers:**
```
Authorization: Bearer <access_token>
```

**Response Body** (`200`):
```json
{
  "items": [
    {
      "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
      "organization_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
      "organization_name": "string",
      "plan_name": "string",
      "price_cents": 1,
      "status": "trialing",
      "current_period_start": "2026-07-30T09:00:00Z",
      "current_period_end": "2026-07-30T09:00:00Z",
      "cancel_at_period_end": true,
      "created_at": "2026-07-30T09:00:00Z"
    }
  ],
  "meta": {
    "page": 1,
    "page_size": 1,
    "total_items": 1,
    "total_pages": 1,
    "has_next": true,
    "has_previous": true
  }
}
```

**Example curl:**
```bash
curl -X GET \
  "http://localhost:8001/api/v1/admin/subscriptions" \
  -H "Authorization: Bearer $ACCESS_TOKEN"
```

### `GET /api/v1/admin/payments`

**List Payments**

- **Method:** `GET`
- **URL:** `http://localhost:8001/api/v1/admin/payments`
- **Authentication:** **Required — superadmin only.** `Authorization: Bearer <access_token>` for a user with `is_superadmin=true`.
- **Query parameters:**
  - `status` (string)
  - `page` (integer, default: `1`)
  - `page_size` (integer, default: `20`)

**Headers:**
```
Authorization: Bearer <access_token>
```

**Response Body** (`200`):
```json
{
  "items": [
    {
      "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
      "organization_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
      "organization_name": "string",
      "amount_cents": 1,
      "currency": "string",
      "status": "pending",
      "payment_method_type": "string",
      "failure_reason": "string",
      "created_at": "2026-07-30T09:00:00Z"
    }
  ],
  "meta": {
    "page": 1,
    "page_size": 1,
    "total_items": 1,
    "total_pages": 1,
    "has_next": true,
    "has_previous": true
  }
}
```

**Example curl:**
```bash
curl -X GET \
  "http://localhost:8001/api/v1/admin/payments" \
  -H "Authorization: Bearer $ACCESS_TOKEN"
```

### `GET /api/v1/admin/leads`

**List Leads**

- **Method:** `GET`
- **URL:** `http://localhost:8001/api/v1/admin/leads`
- **Authentication:** **Required — superadmin only.** `Authorization: Bearer <access_token>` for a user with `is_superadmin=true`.
- **Query parameters:**
  - `page` (integer, default: `1`)
  - `page_size` (integer, default: `20`)

**Headers:**
```
Authorization: Bearer <access_token>
```

**Response Body** (`200`):
```json
{
  "items": [
    {
      "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
      "company_name": "Acme Corp",
      "organization_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
      "organization_name": "string",
      "status": "new",
      "created_at": "2026-07-30T09:00:00Z"
    }
  ],
  "meta": {
    "page": 1,
    "page_size": 1,
    "total_items": 1,
    "total_pages": 1,
    "has_next": true,
    "has_previous": true
  }
}
```

**Example curl:**
```bash
curl -X GET \
  "http://localhost:8001/api/v1/admin/leads" \
  -H "Authorization: Bearer $ACCESS_TOKEN"
```

### `DELETE /api/v1/admin/leads/{lead_id}`

**Delete Lead**

- **Method:** `DELETE`
- **URL:** `http://localhost:8001/api/v1/admin/leads/{lead_id}`
- **Authentication:** **Required — superadmin only.** `Authorization: Bearer <access_token>` for a user with `is_superadmin=true`.
- **Path parameters:**
  - `lead_id` (string) — required

**Headers:**
```
Authorization: Bearer <access_token>
```

**Response Body** (`200`):
```json
{
  "success": true,
  "message": "string"
}
```

**Example curl:**
```bash
curl -X DELETE \
  "http://localhost:8001/api/v1/admin/leads/{lead_id}" \
  -H "Authorization: Bearer $ACCESS_TOKEN"
```

### `GET /api/v1/admin/activity-logs`

**List Activity Logs**

- **Method:** `GET`
- **URL:** `http://localhost:8001/api/v1/admin/activity-logs`
- **Authentication:** **Required — superadmin only.** `Authorization: Bearer <access_token>` for a user with `is_superadmin=true`.
- **Query parameters:**
  - `user_id` (string)
  - `organization_id` (string)
  - `action` (string)
  - `page` (integer, default: `1`)
  - `page_size` (integer, default: `20`)

**Headers:**
```
Authorization: Bearer <access_token>
```

**Response Body** (`200`):
```json
{
  "items": [
    {
      "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
      "user_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
      "user_email": "founder@acmecorp.com",
      "organization_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
      "organization_name": "string",
      "action": "string",
      "entity_type": "string",
      "entity_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
      "ip_address": "MG Road, Pune, Maharashtra",
      "created_at": "2026-07-30T09:00:00Z"
    }
  ],
  "meta": {
    "page": 1,
    "page_size": 1,
    "total_items": 1,
    "total_pages": 1,
    "has_next": true,
    "has_previous": true
  }
}
```

**Example curl:**
```bash
curl -X GET \
  "http://localhost:8001/api/v1/admin/activity-logs" \
  -H "Authorization: Bearer $ACCESS_TOKEN"
```

---

## Settings

Profile, organization, personal API keys, generic settings store, and backup snapshots.


### `GET /api/v1/settings/profile`

**Get Profile**

- **Method:** `GET`
- **URL:** `http://localhost:8001/api/v1/settings/profile`
- **Authentication:** **Required.** `Authorization: Bearer <access_token>` (resolves the caller's organization automatically; pass `X-Organization-Id` to target a specific workspace if the user belongs to more than one)

**Headers:**
```
Authorization: Bearer <access_token>
```

**Response Body** (`200`):
```json
{
  "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "email": "founder@acmecorp.com",
  "phone": "+91 98765 43210",
  "full_name": "Ada Founder",
  "avatar_url": "https://acmesupplies.com",
  "job_title": "VP of Sales",
  "timezone": "Asia/Kolkata",
  "locale": "en-IN"
}
```

**Example curl:**
```bash
curl -X GET \
  "http://localhost:8001/api/v1/settings/profile" \
  -H "Authorization: Bearer $ACCESS_TOKEN"
```

### `PATCH /api/v1/settings/profile`

**Update Profile**

- **Method:** `PATCH`
- **URL:** `http://localhost:8001/api/v1/settings/profile`
- **Authentication:** **Required.** `Authorization: Bearer <access_token>` (resolves the caller's organization automatically; pass `X-Organization-Id` to target a specific workspace if the user belongs to more than one)

**Headers:**
```
Authorization: Bearer <access_token>
Content-Type: application/json
```

**Request Body:**
```json
{
  "full_name": "Ada Founder",
  "job_title": "VP of Sales",
  "phone": "+91 98765 43210",
  "timezone": "Asia/Kolkata",
  "locale": "en-IN"
}
```

**Response Body** (`200`):
```json
{
  "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "email": "founder@acmecorp.com",
  "phone": "+91 98765 43210",
  "full_name": "Ada Founder",
  "avatar_url": "https://acmesupplies.com",
  "job_title": "VP of Sales",
  "timezone": "Asia/Kolkata",
  "locale": "en-IN"
}
```

**Example curl:**
```bash
curl -X PATCH \
  "http://localhost:8001/api/v1/settings/profile" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
  "full_name": "Ada Founder",
  "job_title": "VP of Sales",
  "phone": "+91 98765 43210",
  "timezone": "Asia/Kolkata",
  "locale": "en-IN"
}'
```

### `GET /api/v1/settings/organization`

**Get Organization**

- **Method:** `GET`
- **URL:** `http://localhost:8001/api/v1/settings/organization`
- **Authentication:** **Required.** `Authorization: Bearer <access_token>` (resolves the caller's organization automatically; pass `X-Organization-Id` to target a specific workspace if the user belongs to more than one)

**Headers:**
```
Authorization: Bearer <access_token>
```

**Response Body** (`200`):
```json
{
  "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "name": "string",
  "industry": "Panel Builders",
  "company_size": "Acme Switchgear",
  "website": "https://acmecorp.com",
  "logo_url": "https://acmesupplies.com",
  "timezone": "Asia/Kolkata",
  "locale": "en-IN",
  "created_at": "2026-07-30T09:00:00Z"
}
```

**Example curl:**
```bash
curl -X GET \
  "http://localhost:8001/api/v1/settings/organization" \
  -H "Authorization: Bearer $ACCESS_TOKEN"
```

### `PATCH /api/v1/settings/organization`

**Update Organization**

- **Method:** `PATCH`
- **URL:** `http://localhost:8001/api/v1/settings/organization`
- **Authentication:** **Required.** `Authorization: Bearer <access_token>` (resolves the caller's organization automatically; pass `X-Organization-Id` to target a specific workspace if the user belongs to more than one)

**Headers:**
```
Authorization: Bearer <access_token>
Content-Type: application/json
```

**Request Body:**
```json
{
  "name": "string",
  "industry": "Panel Builders",
  "company_size": "Acme Switchgear",
  "website": "https://acmecorp.com",
  "timezone": "Asia/Kolkata",
  "locale": "en-IN"
}
```

**Response Body** (`200`):
```json
{
  "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "name": "string",
  "industry": "Panel Builders",
  "company_size": "Acme Switchgear",
  "website": "https://acmecorp.com",
  "logo_url": "https://acmesupplies.com",
  "timezone": "Asia/Kolkata",
  "locale": "en-IN",
  "created_at": "2026-07-30T09:00:00Z"
}
```

**Example curl:**
```bash
curl -X PATCH \
  "http://localhost:8001/api/v1/settings/organization" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
  "name": "string",
  "industry": "Panel Builders",
  "company_size": "Acme Switchgear",
  "website": "https://acmecorp.com",
  "timezone": "Asia/Kolkata",
  "locale": "en-IN"
}'
```

### `GET /api/v1/settings/api-keys`

**List Api Keys**

- **Method:** `GET`
- **URL:** `http://localhost:8001/api/v1/settings/api-keys`
- **Authentication:** **Required.** `Authorization: Bearer <access_token>` (resolves the caller's organization automatically; pass `X-Organization-Id` to target a specific workspace if the user belongs to more than one)

**Headers:**
```
Authorization: Bearer <access_token>
```

**Response Body** (`200`):
```json
[
  {
    "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "name": "string",
    "key_prefix": "theme",
    "masked": "string",
    "last_used_at": "2026-07-30T09:00:00Z",
    "created_at": "2026-07-30T09:00:00Z"
  }
]
```

**Example curl:**
```bash
curl -X GET \
  "http://localhost:8001/api/v1/settings/api-keys" \
  -H "Authorization: Bearer $ACCESS_TOKEN"
```

### `POST /api/v1/settings/api-keys`

**Create Api Key**

- **Method:** `POST`
- **URL:** `http://localhost:8001/api/v1/settings/api-keys`
- **Authentication:** **Required.** `Authorization: Bearer <access_token>` (resolves the caller's organization automatically; pass `X-Organization-Id` to target a specific workspace if the user belongs to more than one)

**Headers:**
```
Authorization: Bearer <access_token>
Content-Type: application/json
```

**Request Body:**
```json
{
  "name": "string"
}
```

**Response Body** (`201`):
```json
{
  "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "name": "string",
  "key_prefix": "theme",
  "masked": "string",
  "last_used_at": "2026-07-30T09:00:00Z",
  "created_at": "2026-07-30T09:00:00Z",
  "key": "theme"
}
```

**Example curl:**
```bash
curl -X POST \
  "http://localhost:8001/api/v1/settings/api-keys" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
  "name": "string"
}'
```

### `DELETE /api/v1/settings/api-keys/{key_id}`

**Revoke Api Key**

- **Method:** `DELETE`
- **URL:** `http://localhost:8001/api/v1/settings/api-keys/{key_id}`
- **Authentication:** **Required.** `Authorization: Bearer <access_token>` (resolves the caller's organization automatically; pass `X-Organization-Id` to target a specific workspace if the user belongs to more than one)
- **Path parameters:**
  - `key_id` (string) — required

**Headers:**
```
Authorization: Bearer <access_token>
```

**Response Body** (`200`):
```json
{
  "success": true,
  "message": "string"
}
```

**Example curl:**
```bash
curl -X DELETE \
  "http://localhost:8001/api/v1/settings/api-keys/{key_id}" \
  -H "Authorization: Bearer $ACCESS_TOKEN"
```

### `GET /api/v1/settings/backups`

**List Backups**

- **Method:** `GET`
- **URL:** `http://localhost:8001/api/v1/settings/backups`
- **Authentication:** **Required.** `Authorization: Bearer <access_token>` (resolves the caller's organization automatically; pass `X-Organization-Id` to target a specific workspace if the user belongs to more than one)

**Headers:**
```
Authorization: Bearer <access_token>
```

**Response Body** (`200`):
```json
[
  {
    "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "label": "Manual backup",
    "size_bytes": 1,
    "status": "string",
    "created_at": "2026-07-30T09:00:00Z"
  }
]
```

**Example curl:**
```bash
curl -X GET \
  "http://localhost:8001/api/v1/settings/backups" \
  -H "Authorization: Bearer $ACCESS_TOKEN"
```

### `POST /api/v1/settings/backups`

**Create Backup**

- **Method:** `POST`
- **URL:** `http://localhost:8001/api/v1/settings/backups`
- **Authentication:** **Required.** `Authorization: Bearer <access_token>` (resolves the caller's organization automatically; pass `X-Organization-Id` to target a specific workspace if the user belongs to more than one)

**Headers:**
```
Authorization: Bearer <access_token>
Content-Type: application/json
```

**Request Body:**
```json
{
  "label": "Manual backup"
}
```

**Response Body** (`201`):
```json
{
  "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "label": "Manual backup",
  "size_bytes": 1,
  "status": "string",
  "created_at": "2026-07-30T09:00:00Z"
}
```

**Example curl:**
```bash
curl -X POST \
  "http://localhost:8001/api/v1/settings/backups" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
  "label": "Manual backup"
}'
```

### `GET /api/v1/settings/{scope}/{key}`

**Get Setting**

- **Method:** `GET`
- **URL:** `http://localhost:8001/api/v1/settings/{scope}/{key}`
- **Authentication:** **Required.** `Authorization: Bearer <access_token>` (resolves the caller's organization automatically; pass `X-Organization-Id` to target a specific workspace if the user belongs to more than one)
- **Path parameters:**
  - `scope` (string) — required
  - `key` (string) — required

**Headers:**
```
Authorization: Bearer <access_token>
```

**Response Body** (`200`):
```json
{
  "scope": "string",
  "key": "theme",
  "value": {}
}
```

**Example curl:**
```bash
curl -X GET \
  "http://localhost:8001/api/v1/settings/{scope}/{key}" \
  -H "Authorization: Bearer $ACCESS_TOKEN"
```

### `PUT /api/v1/settings/{scope}/{key}`

**Put Setting**

- **Method:** `PUT`
- **URL:** `http://localhost:8001/api/v1/settings/{scope}/{key}`
- **Authentication:** **Required.** `Authorization: Bearer <access_token>` (resolves the caller's organization automatically; pass `X-Organization-Id` to target a specific workspace if the user belongs to more than one)
- **Path parameters:**
  - `scope` (string) — required
  - `key` (string) — required

**Headers:**
```
Authorization: Bearer <access_token>
Content-Type: application/json
```

**Request Body:**
```json
{
  "key": "theme",
  "value": {}
}
```

**Response Body** (`200`):
```json
{
  "scope": "string",
  "key": "theme",
  "value": {}
}
```

**Example curl:**
```bash
curl -X PUT \
  "http://localhost:8001/api/v1/settings/{scope}/{key}" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
  "key": "theme",
  "value": {}
}'
```

---

## Team

Workspace membership, invitations, and role management.


### `GET /api/v1/team/members`

**List Members**

- **Method:** `GET`
- **URL:** `http://localhost:8001/api/v1/team/members`
- **Authentication:** **Required.** `Authorization: Bearer <access_token>` (resolves the caller's organization automatically; pass `X-Organization-Id` to target a specific workspace if the user belongs to more than one)

**Headers:**
```
Authorization: Bearer <access_token>
```

**Response Body** (`200`):
```json
[
  {
    "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "user_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "name": "string",
    "email": "founder@acmecorp.com",
    "avatar_url": "https://acmesupplies.com",
    "role": "member",
    "status": "string",
    "joined_at": "2026-07-30T09:00:00Z",
    "last_active": "2026-07-30T09:00:00Z"
  }
]
```

**Example curl:**
```bash
curl -X GET \
  "http://localhost:8001/api/v1/team/members" \
  -H "Authorization: Bearer $ACCESS_TOKEN"
```

### `GET /api/v1/team/roles`

**List Roles**

- **Method:** `GET`
- **URL:** `http://localhost:8001/api/v1/team/roles`
- **Authentication:** **Required.** `Authorization: Bearer <access_token>` (resolves the caller's organization automatically; pass `X-Organization-Id` to target a specific workspace if the user belongs to more than one)

**Headers:**
```
Authorization: Bearer <access_token>
```

**Response Body** (`200`):
```json
[
  {
    "role": "member",
    "permissions": [
      "string"
    ]
  }
]
```

**Example curl:**
```bash
curl -X GET \
  "http://localhost:8001/api/v1/team/roles" \
  -H "Authorization: Bearer $ACCESS_TOKEN"
```

### `GET /api/v1/team/permissions`

**List Permissions**

- **Method:** `GET`
- **URL:** `http://localhost:8001/api/v1/team/permissions`
- **Authentication:** **Required.** `Authorization: Bearer <access_token>` (resolves the caller's organization automatically; pass `X-Organization-Id` to target a specific workspace if the user belongs to more than one)

**Headers:**
```
Authorization: Bearer <access_token>
```

**Response Body** (`200`):
```json
[
  {
    "code": "482913",
    "description": "string"
  }
]
```

**Example curl:**
```bash
curl -X GET \
  "http://localhost:8001/api/v1/team/permissions" \
  -H "Authorization: Bearer $ACCESS_TOKEN"
```

### `POST /api/v1/team/invite`

**Invite Member**

- **Method:** `POST`
- **URL:** `http://localhost:8001/api/v1/team/invite`
- **Authentication:** **Required.** `Authorization: Bearer <access_token>` (resolves the caller's organization automatically; pass `X-Organization-Id` to target a specific workspace if the user belongs to more than one)

**Headers:**
```
Authorization: Bearer <access_token>
Content-Type: application/json
```

**Request Body:**
```json
{
  "email": "founder@acmecorp.com",
  "role": "member"
}
```

**Response Body** (`201`):
```json
{
  "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "email": "founder@acmecorp.com",
  "role": "member",
  "invited_by": "founder@acmecorp.com",
  "status": "string",
  "created_at": "2026-07-30T09:00:00Z",
  "expires_at": "2026-07-30T09:00:00Z"
}
```

**Example curl:**
```bash
curl -X POST \
  "http://localhost:8001/api/v1/team/invite" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
  "email": "founder@acmecorp.com",
  "role": "member"
}'
```

### `GET /api/v1/team/invitations`

**List Invitations**

- **Method:** `GET`
- **URL:** `http://localhost:8001/api/v1/team/invitations`
- **Authentication:** **Required.** `Authorization: Bearer <access_token>` (resolves the caller's organization automatically; pass `X-Organization-Id` to target a specific workspace if the user belongs to more than one)

**Headers:**
```
Authorization: Bearer <access_token>
```

**Response Body** (`200`):
```json
[
  {
    "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "email": "founder@acmecorp.com",
    "role": "member",
    "invited_by": "founder@acmecorp.com",
    "status": "string",
    "created_at": "2026-07-30T09:00:00Z",
    "expires_at": "2026-07-30T09:00:00Z"
  }
]
```

**Example curl:**
```bash
curl -X GET \
  "http://localhost:8001/api/v1/team/invitations" \
  -H "Authorization: Bearer $ACCESS_TOKEN"
```

### `POST /api/v1/team/invitations/{invitation_id}/resend`

**Resend Invitation**

- **Method:** `POST`
- **URL:** `http://localhost:8001/api/v1/team/invitations/{invitation_id}/resend`
- **Authentication:** **Required.** `Authorization: Bearer <access_token>` (resolves the caller's organization automatically; pass `X-Organization-Id` to target a specific workspace if the user belongs to more than one)
- **Path parameters:**
  - `invitation_id` (string) — required

**Headers:**
```
Authorization: Bearer <access_token>
```

**Response Body** (`200`):
```json
{
  "success": true,
  "message": "string"
}
```

**Example curl:**
```bash
curl -X POST \
  "http://localhost:8001/api/v1/team/invitations/{invitation_id}/resend" \
  -H "Authorization: Bearer $ACCESS_TOKEN"
```

### `DELETE /api/v1/team/invitations/{invitation_id}`

**Cancel Invitation**

- **Method:** `DELETE`
- **URL:** `http://localhost:8001/api/v1/team/invitations/{invitation_id}`
- **Authentication:** **Required.** `Authorization: Bearer <access_token>` (resolves the caller's organization automatically; pass `X-Organization-Id` to target a specific workspace if the user belongs to more than one)
- **Path parameters:**
  - `invitation_id` (string) — required

**Headers:**
```
Authorization: Bearer <access_token>
```

**Response Body** (`200`):
```json
{
  "success": true,
  "message": "string"
}
```

**Example curl:**
```bash
curl -X DELETE \
  "http://localhost:8001/api/v1/team/invitations/{invitation_id}" \
  -H "Authorization: Bearer $ACCESS_TOKEN"
```

### `PATCH /api/v1/team/members/{member_user_id}/role`

**Update Member Role**

- **Method:** `PATCH`
- **URL:** `http://localhost:8001/api/v1/team/members/{member_user_id}/role`
- **Authentication:** **Required.** `Authorization: Bearer <access_token>` (resolves the caller's organization automatically; pass `X-Organization-Id` to target a specific workspace if the user belongs to more than one)
- **Path parameters:**
  - `member_user_id` (string) — required

**Headers:**
```
Authorization: Bearer <access_token>
Content-Type: application/json
```

**Request Body:**
```json
{
  "role": "admin"
}
```

**Response Body** (`200`):
```json
{
  "success": true,
  "message": "string"
}
```

**Example curl:**
```bash
curl -X PATCH \
  "http://localhost:8001/api/v1/team/members/{member_user_id}/role" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
  "role": "admin"
}'
```

### `DELETE /api/v1/team/members/{member_user_id}`

**Remove Member**

- **Method:** `DELETE`
- **URL:** `http://localhost:8001/api/v1/team/members/{member_user_id}`
- **Authentication:** **Required.** `Authorization: Bearer <access_token>` (resolves the caller's organization automatically; pass `X-Organization-Id` to target a specific workspace if the user belongs to more than one)
- **Path parameters:**
  - `member_user_id` (string) — required

**Headers:**
```
Authorization: Bearer <access_token>
```

**Response Body** (`200`):
```json
{
  "success": true,
  "message": "string"
}
```

**Example curl:**
```bash
curl -X DELETE \
  "http://localhost:8001/api/v1/team/members/{member_user_id}" \
  -H "Authorization: Bearer $ACCESS_TOKEN"
```

### `POST /api/v1/team/invitations/accept`

**Accept Invitation**

- **Method:** `POST`
- **URL:** `http://localhost:8001/api/v1/team/invitations/accept`
- **Authentication:** None — public endpoint.

**Headers:**
```
Content-Type: application/json
```

**Request Body:**
```json
{
  "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

**Response Body** (`200`):
```json
{
  "success": true,
  "message": "string"
}
```

**Example curl:**
```bash
curl -X POST \
  "http://localhost:8001/api/v1/team/invitations/accept" \
  -H "Content-Type: application/json" \
  -d '{
  "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}'
```

---

## Exports

Export Center — generate CSV/Excel/PDF/JSON exports of leads, search results, and reports, then download them via a signed URL.


### `POST /api/v1/exports`

**Create an export**

- **Method:** `POST`
- **URL:** `http://localhost:8001/api/v1/exports`
- **Authentication:** **Required.** `Authorization: Bearer <access_token>`

**Headers:**
```
Authorization: Bearer <access_token>
Content-Type: application/json
```

**Request Body:**
```json
{
  "resource": "leads",
  "format": "csv",
  "scope": "all",
  "lead_ids": [
    "3fa85f64-5717-4562-b3fc-2c963f66afa6"
  ],
  "filters": {
    "search": "string",
    "industry": "Panel Builders",
    "status": "string",
    "country": "India",
    "min_score": 0.0,
    "max_score": 0.0,
    "sort_by": "created_at",
    "sort_order": "desc"
  },
  "search_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "columns": [
    "string"
  ],
  "file_name": "string"
}
```

**Response Body** (`201`):
```json
{
  "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "file_name": "string",
  "format": "csv",
  "resource": "leads",
  "row_count": 1,
  "size_bytes": 1,
  "size_label": "Manual backup",
  "status": "processing",
  "download_count": 1,
  "created_at": "2026-07-30T09:00:00Z",
  "expires_at": "2026-07-30T09:00:00Z",
  "error_message": "string",
  "download_url": "https://acmesupplies.com",
  "ignored_columns": [
    "string"
  ]
}
```

**Example curl:**
```bash
curl -X POST \
  "http://localhost:8001/api/v1/exports" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
  "resource": "leads",
  "format": "csv",
  "scope": "all",
  "lead_ids": [
    "3fa85f64-5717-4562-b3fc-2c963f66afa6"
  ],
  "filters": {
    "search": "string",
    "industry": "Panel Builders",
    "status": "string",
    "country": "India",
    "min_score": 0.0,
    "max_score": 0.0,
    "sort_by": "created_at",
    "sort_order": "desc"
  },
  "search_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "columns": [
    "string"
  ],
  "file_name": "string"
}'
```

### `GET /api/v1/exports`

**List export history**

- **Method:** `GET`
- **URL:** `http://localhost:8001/api/v1/exports`
- **Authentication:** **Required.** `Authorization: Bearer <access_token>`
- **Query parameters:**
  - `resource` (string)
  - `status` (string)
  - `page` (integer, default: `1`)
  - `page_size` (integer, default: `20`)

**Headers:**
```
Authorization: Bearer <access_token>
```

**Response Body** (`200`):
```json
{
  "items": [
    {
      "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
      "file_name": "string",
      "format": "csv",
      "resource": "leads",
      "row_count": 1,
      "size_bytes": 1,
      "size_label": "Manual backup",
      "status": "processing",
      "download_count": 1,
      "created_at": "2026-07-30T09:00:00Z",
      "expires_at": "2026-07-30T09:00:00Z",
      "error_message": "string",
      "download_url": "https://acmesupplies.com",
      "ignored_columns": [
        "string"
      ]
    }
  ],
  "meta": {
    "page": 1,
    "page_size": 1,
    "total_items": 1,
    "total_pages": 1,
    "has_next": true,
    "has_previous": true
  }
}
```

**Example curl:**
```bash
curl -X GET \
  "http://localhost:8001/api/v1/exports" \
  -H "Authorization: Bearer $ACCESS_TOKEN"
```

### `GET /api/v1/exports/formats`

**List supported export formats and lead columns**

- **Method:** `GET`
- **URL:** `http://localhost:8001/api/v1/exports/formats`
- **Authentication:** **Required.** `Authorization: Bearer <access_token>`

**Headers:**
```
Authorization: Bearer <access_token>
```

**Response Body** (`200`):
```json
{}
```

**Example curl:**
```bash
curl -X GET \
  "http://localhost:8001/api/v1/exports/formats" \
  -H "Authorization: Bearer $ACCESS_TOKEN"
```

### `GET /api/v1/exports/{export_id}`

**Get one export's status**

- **Method:** `GET`
- **URL:** `http://localhost:8001/api/v1/exports/{export_id}`
- **Authentication:** **Required.** `Authorization: Bearer <access_token>`
- **Path parameters:**
  - `export_id` (string) — required

**Headers:**
```
Authorization: Bearer <access_token>
```

**Response Body** (`200`):
```json
{
  "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "file_name": "string",
  "format": "csv",
  "resource": "leads",
  "row_count": 1,
  "size_bytes": 1,
  "size_label": "Manual backup",
  "status": "processing",
  "download_count": 1,
  "created_at": "2026-07-30T09:00:00Z",
  "expires_at": "2026-07-30T09:00:00Z",
  "error_message": "string",
  "download_url": "https://acmesupplies.com",
  "ignored_columns": [
    "string"
  ]
}
```

**Example curl:**
```bash
curl -X GET \
  "http://localhost:8001/api/v1/exports/{export_id}" \
  -H "Authorization: Bearer $ACCESS_TOKEN"
```

### `DELETE /api/v1/exports/{export_id}`

**Delete an export and its file**

- **Method:** `DELETE`
- **URL:** `http://localhost:8001/api/v1/exports/{export_id}`
- **Authentication:** **Required.** `Authorization: Bearer <access_token>`
- **Path parameters:**
  - `export_id` (string) — required

**Headers:**
```
Authorization: Bearer <access_token>
```

**Response Body** (`200`):
```json
{
  "success": true,
  "message": "string"
}
```

**Example curl:**
```bash
curl -X DELETE \
  "http://localhost:8001/api/v1/exports/{export_id}" \
  -H "Authorization: Bearer $ACCESS_TOKEN"
```

### `POST /api/v1/exports/{export_id}/download-token`

**Mint a short-lived download token**

- **Method:** `POST`
- **URL:** `http://localhost:8001/api/v1/exports/{export_id}/download-token`
- **Authentication:** **Required.** `Authorization: Bearer <access_token>`
- **Path parameters:**
  - `export_id` (string) — required

**Headers:**
```
Authorization: Bearer <access_token>
```

**Response Body** (`200`):
```json
{
  "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "expires_in": 1,
  "download_url": "https://acmesupplies.com"
}
```

**Example curl:**
```bash
curl -X POST \
  "http://localhost:8001/api/v1/exports/{export_id}/download-token" \
  -H "Authorization: Bearer $ACCESS_TOKEN"
```

### `GET /api/v1/exports/{export_id}/download`

**Download an export file**

- **Method:** `GET`
- **URL:** `http://localhost:8001/api/v1/exports/{export_id}/download`
- **Authentication:** None — public endpoint.
- **Path parameters:**
  - `export_id` (string) — required
- **Query parameters:**
  - `token` (string)

**Headers:**
```
(none required)
```

**Response Body** (`200`):
```json
{}
```

**Example curl:**
```bash
curl -X GET \
  "http://localhost:8001/api/v1/exports/{export_id}/download"
```

---

## Imports

Lead imports — the Google Maps Search workflow (build a Maps URL, then import the CSV the user's own extractor extension exported) plus generic CSV import, with per-run history. Nothing here contacts Google Maps.


### `POST /api/v1/imports/google-maps/search-url`

**Google Maps Search Url**

- **Method:** `POST`
- **URL:** `http://localhost:8001/api/v1/imports/google-maps/search-url`
- **Authentication:** **Required.** `Authorization: Bearer <access_token>`

**Headers:**
```
Authorization: Bearer <access_token>
Content-Type: application/json
```

**Request Body:**
```json
{
  "keyword": "theme",
  "location": "Pune, India"
}
```

**Response Body** (`200`):
```json
{
  "url": "https://acmesupplies.com",
  "keyword": "theme",
  "location": "Pune, India"
}
```

**Example curl:**
```bash
curl -X POST \
  "http://localhost:8001/api/v1/imports/google-maps/search-url" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
  "keyword": "theme",
  "location": "Pune, India"
}'
```

### `POST /api/v1/imports/google-maps`

**Import Google Maps Export**

- **Method:** `POST`
- **URL:** `http://localhost:8001/api/v1/imports/google-maps`
- **Authentication:** **Required.** `Authorization: Bearer <access_token>`

**Headers:**
```
Authorization: Bearer <access_token>
Content-Type: multipart/form-data
```

**Request Body** (`multipart/form-data`):

| Field | Value | Required |
|---|---|---|
| `file` | file upload — @/path/to/file.pdf | yes |
| `keyword` | theme | no |
| `location` | Pune, India | no |
| `enrich` | False | no |

**Response Body** (`201`):
```json
{
  "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "source": "csv_upload",
  "status": "processing",
  "file_name": "string",
  "file_size_bytes": 1,
  "keyword": "theme",
  "location": "Pune, India",
  "total_rows": 1,
  "imported": 1,
  "duplicates_skipped": 1,
  "invalid_rows": 1,
  "enriched": 1,
  "row_errors": [
    {
      "line": 1,
      "message": "string",
      "company": "Acme Switchgear"
    }
  ],
  "dedup_signals": {},
  "error_message": "string",
  "created_at": "2026-07-30T09:00:00Z",
  "completed_at": "2026-07-30T09:00:00Z"
}
```

**Example curl:**
```bash
curl -X POST \
  "http://localhost:8001/api/v1/imports/google-maps" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -F "file=@/path/to/file.pdf" \
  -F "keyword=theme" \
  -F "location=Pune, India" \
  -F "enrich=False"
```

### `POST /api/v1/imports`

**Import Csv**

- **Method:** `POST`
- **URL:** `http://localhost:8001/api/v1/imports`
- **Authentication:** **Required.** `Authorization: Bearer <access_token>`

**Headers:**
```
Authorization: Bearer <access_token>
Content-Type: multipart/form-data
```

**Request Body** (`multipart/form-data`):

| Field | Value | Required |
|---|---|---|
| `file` | file upload — @/path/to/file.pdf | yes |
| `enrich` | False | no |

**Response Body** (`201`):
```json
{
  "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "source": "csv_upload",
  "status": "processing",
  "file_name": "string",
  "file_size_bytes": 1,
  "keyword": "theme",
  "location": "Pune, India",
  "total_rows": 1,
  "imported": 1,
  "duplicates_skipped": 1,
  "invalid_rows": 1,
  "enriched": 1,
  "row_errors": [
    {
      "line": 1,
      "message": "string",
      "company": "Acme Switchgear"
    }
  ],
  "dedup_signals": {},
  "error_message": "string",
  "created_at": "2026-07-30T09:00:00Z",
  "completed_at": "2026-07-30T09:00:00Z"
}
```

**Example curl:**
```bash
curl -X POST \
  "http://localhost:8001/api/v1/imports" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -F "file=@/path/to/file.pdf" \
  -F "enrich=False"
```

### `GET /api/v1/imports`

**List Imports**

- **Method:** `GET`
- **URL:** `http://localhost:8001/api/v1/imports`
- **Authentication:** **Required.** `Authorization: Bearer <access_token>`
- **Query parameters:**
  - `source` (string)
  - `page` (integer, default: `1`)
  - `page_size` (integer, default: `20`)

**Headers:**
```
Authorization: Bearer <access_token>
```

**Response Body** (`200`):
```json
{
  "items": [
    {
      "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
      "source": "csv_upload",
      "status": "processing",
      "file_name": "string",
      "file_size_bytes": 1,
      "keyword": "theme",
      "location": "Pune, India",
      "total_rows": 1,
      "imported": 1,
      "duplicates_skipped": 1,
      "invalid_rows": 1,
      "enriched": 1,
      "row_errors": [
        {
          "line": 1,
          "message": "string",
          "company": "Acme Switchgear"
        }
      ],
      "dedup_signals": {},
      "error_message": "string",
      "created_at": "2026-07-30T09:00:00Z",
      "completed_at": "2026-07-30T09:00:00Z"
    }
  ],
  "meta": {
    "page": 1,
    "page_size": 1,
    "total_items": 1,
    "total_pages": 1,
    "has_next": true,
    "has_previous": true
  }
}
```

**Example curl:**
```bash
curl -X GET \
  "http://localhost:8001/api/v1/imports" \
  -H "Authorization: Bearer $ACCESS_TOKEN"
```

### `GET /api/v1/imports/{import_id}`

**Get Import**

- **Method:** `GET`
- **URL:** `http://localhost:8001/api/v1/imports/{import_id}`
- **Authentication:** **Required.** `Authorization: Bearer <access_token>`
- **Path parameters:**
  - `import_id` (string) — required

**Headers:**
```
Authorization: Bearer <access_token>
```

**Response Body** (`200`):
```json
{
  "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "source": "csv_upload",
  "status": "processing",
  "file_name": "string",
  "file_size_bytes": 1,
  "keyword": "theme",
  "location": "Pune, India",
  "total_rows": 1,
  "imported": 1,
  "duplicates_skipped": 1,
  "invalid_rows": 1,
  "enriched": 1,
  "row_errors": [
    {
      "line": 1,
      "message": "string",
      "company": "Acme Switchgear"
    }
  ],
  "dedup_signals": {},
  "error_message": "string",
  "created_at": "2026-07-30T09:00:00Z",
  "completed_at": "2026-07-30T09:00:00Z"
}
```

**Example curl:**
```bash
curl -X GET \
  "http://localhost:8001/api/v1/imports/{import_id}" \
  -H "Authorization: Bearer $ACCESS_TOKEN"
```