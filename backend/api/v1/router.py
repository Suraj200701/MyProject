"""Aggregates every v1 route module under a single APIRouter."""

from fastapi import APIRouter

from api.v1 import (
    admin,
    analytics,
    auth,
    dashboard,
    exports,
    files,
    health,
    imports,
    leads,
    map as map_routes,
    notifications,
    payments,
    search,
    settings as settings_routes,
    team,
)

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(leads.router)
api_router.include_router(search.router)
api_router.include_router(dashboard.router)
api_router.include_router(analytics.router)
api_router.include_router(payments.router)
api_router.include_router(exports.router)
api_router.include_router(imports.router)
api_router.include_router(files.router)
api_router.include_router(notifications.router)
api_router.include_router(map_routes.router)
api_router.include_router(admin.router)
api_router.include_router(settings_routes.router)
api_router.include_router(team.router)
