"""Map / geocoding endpoints.

IMPORTANT — read this before touching anything below:

  * `POST /map/nearby-leads` works RIGHT NOW with zero configuration. It's
    pure database query (the org's own Lead + Company rows that already have
    lat/lng) plus `services.maps_service.haversine_distance_km` — no external
    API call, no API key needed. This is the endpoint the frontend's Map
    Search page radius slider should call.

  * `POST /map/geocode`, `GET /map/reverse-geocode` and `GET /map/nearby-places`
    call a real geocoding provider: Google Maps when `GOOGLE_MAPS_API_KEY` is
    set, otherwise Mappls when `MAPPLS_CLIENT_ID`/`MAPPLS_CLIENT_SECRET` are.
    With neither configured they raise a 400 naming both options.

  * `GET /map/autocomplete` is Mappls-only (Google's Places Autocomplete is a
    separately billed product this deployment does not integrate), and
    `POST /map/distance-matrix` is Google-only for the mirror-image reason.
    Each raises a 400 saying which credential it needs.

All routes require an authenticated user with an active organization.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_current_organization, get_current_user
from database.session import get_db
from models.lead import Company, Lead
from models.organization import Organization
from schemas.map import GeocodeRequest, GeocodeResult, NearbyLeadOut, NearbySearchRequest
from services import maps_service
from utils.exceptions import NotFoundError

router = APIRouter(
    prefix="/map",
    tags=["Map"],
    dependencies=[Depends(get_current_user), Depends(get_current_organization)],
)


@router.post("/geocode", response_model=GeocodeResult)
async def geocode(payload: GeocodeRequest):
    """Resolves a free-text address/city into lat/lng via Google or Mappls."""
    result = await maps_service.geocode_address(payload.address)
    if result is None:
        raise NotFoundError("No results found for that address")
    return GeocodeResult(**result)


@router.get("/reverse-geocode", response_model=GeocodeResult)
async def reverse_geocode(
    lat: float = Query(..., ge=-90, le=90),
    lng: float = Query(..., ge=-180, le=180),
):
    """Resolves lat/lng into a formatted address via Google or Mappls."""
    result = await maps_service.reverse_geocode(lat, lng)
    if result is None:
        raise NotFoundError("No address found for those coordinates")
    return GeocodeResult(**result)


@router.get("/autocomplete")
async def autocomplete(
    query: str = Query(..., min_length=1, max_length=200),
    lat: float | None = Query(default=None, ge=-90, le=90),
    lng: float | None = Query(default=None, ge=-180, le=180),
):
    """Type-ahead place suggestions from Mappls, optionally biased to a point.

    Requires MAPPLS_CLIENT_ID / MAPPLS_CLIENT_SECRET.
    """
    return await maps_service.autocomplete(query, lat, lng)


@router.post("/nearby-leads", response_model=list[NearbyLeadOut])
async def nearby_leads(
    payload: NearbySearchRequest,
    organization: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
):
    """Finds the org's own leads within `radius_km` of (lat, lng).

    Pure database + haversine math — works today with zero Google Maps
    configuration. Queries Lead+Company rows for this organization that have
    non-null coordinates, computes great-circle distance from the given
    center in Python, filters to the requested radius, and sorts nearest
    first.
    """
    stmt = (
        select(Lead, Company)
        .join(Company, Lead.company_id == Company.id)
        .where(
            Lead.organization_id == organization.id,
            Company.lat.is_not(None),
            Company.lng.is_not(None),
        )
    )
    if payload.industry:
        stmt = stmt.where(Company.industry == payload.industry)

    rows = (await db.execute(stmt)).all()

    nearby: list[NearbyLeadOut] = []
    for lead, company in rows:
        company_lat = float(company.lat)
        company_lng = float(company.lng)
        distance_km = maps_service.haversine_distance_km(payload.lat, payload.lng, company_lat, company_lng)
        if distance_km <= payload.radius_km:
            nearby.append(
                NearbyLeadOut(
                    lead_id=lead.id,
                    company_name=company.name,
                    lat=company_lat,
                    lng=company_lng,
                    distance_km=round(distance_km, 3),
                    lead_score=lead.lead_score,
                    industry=company.industry,
                    city=company.city,
                )
            )

    nearby.sort(key=lambda item: item.distance_km)
    return nearby


@router.get("/nearby-places")
async def nearby_places(
    lat: float = Query(..., ge=-90, le=90),
    lng: float = Query(..., ge=-180, le=180),
    radius_meters: int = Query(1500, gt=0, le=50000),
    keyword: str | None = Query(default=None),
):
    """Places near a point, from Google or Mappls.

    Both providers are normalized to `{name, address, lat, lng, source}`.
    `lat`/`lng` are null for Mappls projects without coordinate delivery.
    """
    return await maps_service.nearby_search(lat, lng, radius_meters, keyword)


@router.post("/distance-matrix")
async def distance_matrix(
    origin_lat: float = Query(..., ge=-90, le=90),
    origin_lng: float = Query(..., ge=-180, le=180),
    destinations: list[str] = Query(
        ..., description='Each item is "lat,lng", e.g. destinations=19.07,72.87&destinations=18.52,73.85'
    ),
):
    """Proxies Google's Distance Matrix API for batch true-road distances.
    Real API call — requires GOOGLE_MAPS_API_KEY."""
    parsed_destinations: list[tuple[float, float]] = []
    for item in destinations:
        d_lat_str, _, d_lng_str = item.partition(",")
        parsed_destinations.append((float(d_lat_str), float(d_lng_str)))

    return await maps_service.distance_matrix((origin_lat, origin_lng), parsed_destinations)
