"""Aggregates every v1 route module under a single APIRouter.

Feature routers are imported lazily-safe (each module is independent) so
that a single missing module never breaks the whole API surface during
incremental development.
"""

from fastapi import APIRouter

from api.v1 import health

api_router = APIRouter()
api_router.include_router(health.router)

# Additional routers are registered here as they're implemented:
#   from api.v1 import auth, users, leads, companies, search, dashboard,
#       analytics, payments, subscriptions, notifications, settings as settings_routes,
#       files, admin, map as map_routes
# api_router.include_router(auth.router, prefix="/auth", tags=["Auth"])
# ... etc — see individual task commits for the full set.
