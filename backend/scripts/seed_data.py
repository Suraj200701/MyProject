"""Idempotent seed data: roles, permissions, subscription plans, and the
default API provider catalogue (mirrors the frontend's mock-data.ts so the
UI and a freshly-seeded backend agree on names/categories).

Usage:
    python -m scripts.seed_data
"""

import asyncio

from sqlalchemy import select

from database.session import AsyncSessionLocal
from models.billing import SubscriptionPlan
from models.enums import BillingInterval, ProviderCategory, ProviderStatus, RoleName
from models.search import ApiProvider
from models.user import Permission, Role

PERMISSIONS = [
    ("leads.search", "Run lead searches"),
    ("leads.export", "Export lead data"),
    ("leads.manage", "Edit/delete leads"),
    ("api_keys.manage", "Create/revoke API keys and provider connections"),
    ("billing.manage", "Manage subscription and payment methods"),
    ("team.manage", "Invite/remove team members and change roles"),
    ("settings.manage", "Change organization-wide settings"),
]

ROLE_PERMISSIONS = {
    RoleName.OWNER: [p[0] for p in PERMISSIONS],
    RoleName.ADMIN: ["leads.search", "leads.export", "leads.manage", "api_keys.manage", "team.manage"],
    RoleName.MEMBER: ["leads.search", "leads.export"],
    RoleName.VIEWER: ["leads.search"],
    RoleName.SUPERADMIN: [p[0] for p in PERMISSIONS],
}

PLANS = [
    {
        "name": "Free",
        "price_cents": 0,
        "billing_interval": BillingInterval.MONTH,
        "credits_included": 100,
        "seats_included": 1,
        "features": ["100 credits/mo", "1 seat", "Basic search"],
    },
    {
        "name": "Pro",
        "price_cents": 24900,
        "billing_interval": BillingInterval.MONTH,
        "credits_included": 10000,
        "seats_included": 5,
        "features": ["10,000 credits/mo", "5 seats", "AI lead scoring", "Website scanner"],
    },
    {
        "name": "Business",
        "price_cents": 69900,
        "billing_interval": BillingInterval.MONTH,
        "credits_included": 50000,
        "seats_included": 20,
        "features": ["50,000 credits/mo", "20 seats", "API Manager", "Priority support"],
    },
    {
        "name": "Enterprise",
        "price_cents": 0,
        "billing_interval": BillingInterval.MONTH,
        "credits_included": 1000000,
        "seats_included": 1000,
        "features": ["Unlimited credits", "Unlimited seats", "SSO & SLA", "Dedicated CSM"],
    },
]

# (name, category, logo, description, usage_limit, credit_cost)
# `credit_cost` = credits charged per result sourced from this provider.
# Rough proxy for what each provider costs us: Google Places Text Search is
# billed per request at a premium, the Indian B2B directories are cheaper
# per lead, and enrichment-only providers don't source leads at all.
PROVIDERS = [
    # --- Implemented lead sources (have a real adapter in services/providers/) ---
    ("Google Places", ProviderCategory.MAPS, "🗺️", "Business discovery & place details", 10000, 2),
    ("Mappls (MapmyIndia)", ProviderCategory.MAPS, "📍", "India-focused maps & POI search", 5000, 1),
    ("Bing Search", ProviderCategory.SEARCH, "🔎", "Company website discovery via web search", 3000, 1),
    # No paid dependency — crawls the company's own site, so it costs 1 credit
    # for the bandwidth/compute rather than for third-party API usage.
    ("Company Website Search", ProviderCategory.SEARCH, "🌐", "Crawls a company website for contact details", 100000, 1),
    # --- Catalogue-only: no adapter yet, needs a partner agreement ---
    ("IndiaMART", ProviderCategory.BUSINESS, "🏭", "B2B supplier & manufacturer directory", 2000, 1),
    ("TradeIndia", ProviderCategory.BUSINESS, "🤝", "Trade leads and supplier network", 2000, 1),
    ("LinkedIn Sales Navigator", ProviderCategory.CRM, "💼", "Contact enrichment & company data", 1000, 3),
    ("JustDial", ProviderCategory.SEARCH, "🔍", "Local business search India", 5000, 1),
    # --- Enrichment only, never sources leads ---
    ("OpenAI GPT", ProviderCategory.AI, "✨", "AI summaries & lead scoring", 25000, 0),
]


async def seed() -> None:
    async with AsyncSessionLocal() as session:
        existing_roles = {r.name for r in (await session.execute(select(Role))).scalars().all()}
        role_by_name: dict[RoleName, Role] = {}
        for role_name in RoleName:
            if role_name in existing_roles:
                continue
            role = Role(name=role_name, description=f"{role_name.value.title()} role")
            session.add(role)
            role_by_name[role_name] = role
        await session.flush()

        if not role_by_name:
            all_roles = (await session.execute(select(Role))).scalars().all()
            role_by_name = {r.name: r for r in all_roles}

        existing_perms = {p.code for p in (await session.execute(select(Permission))).scalars().all()}
        perm_by_code: dict[str, Permission] = {}
        for code, desc in PERMISSIONS:
            if code in existing_perms:
                continue
            perm = Permission(code=code, description=desc)
            session.add(perm)
            perm_by_code[code] = perm
        await session.flush()

        if not perm_by_code:
            all_perms = (await session.execute(select(Permission))).scalars().all()
            perm_by_code = {p.code: p for p in all_perms}

        all_roles = (await session.execute(select(Role))).scalars().all()
        role_by_name = {r.name: r for r in all_roles}
        all_perms = (await session.execute(select(Permission))).scalars().all()
        perm_by_code = {p.code: p for p in all_perms}

        for role_name, codes in ROLE_PERMISSIONS.items():
            role = role_by_name.get(role_name)
            if role is None:
                continue
            await session.refresh(role, attribute_names=["permissions"])
            current_codes = {p.code for p in role.permissions}
            for code in codes:
                if code not in current_codes and code in perm_by_code:
                    role.permissions.append(perm_by_code[code])

        existing_plans = {p.name for p in (await session.execute(select(SubscriptionPlan))).scalars().all()}
        for plan in PLANS:
            if plan["name"] in existing_plans:
                continue
            session.add(SubscriptionPlan(**plan))

        existing_provider_rows = {p.name: p for p in (await session.execute(select(ApiProvider))).scalars().all()}
        for name, category, logo, description, usage_limit, credit_cost in PROVIDERS:
            existing = existing_provider_rows.get(name)
            if existing is not None:
                # Backfill the metering cost on rows seeded before the
                # credit_cost column existed (they default to 1).
                if existing.credit_cost is None:
                    existing.credit_cost = credit_cost
                continue
            session.add(
                ApiProvider(
                    name=name,
                    category=category,
                    status=ProviderStatus.HEALTHY,
                    logo=logo,
                    description=description,
                    usage_limit=usage_limit,
                    connected=False,
                    credit_cost=credit_cost,
                )
            )

        await session.commit()
        print("Seed complete.")


if __name__ == "__main__":
    asyncio.run(seed())
