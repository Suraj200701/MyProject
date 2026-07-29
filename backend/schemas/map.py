"""Pydantic schemas for the map/geocoding module (see api/v1/map.py and
services/maps_service.py)."""

import uuid

from pydantic import BaseModel, Field


class GeocodeRequest(BaseModel):
    """Free-text address/city to resolve into coordinates. Requires a real
    GOOGLE_MAPS_API_KEY to be configured on the server."""

    address: str = Field(..., min_length=1, max_length=500)


class GeocodeResult(BaseModel):
    lat: float
    lng: float
    formatted_address: str


class NearbySearchRequest(BaseModel):
    """Search center + radius for finding the org's own leads near a point.

    Backed entirely by the database (Company.lat/lng) plus haversine math —
    does NOT require a Google Maps API key.
    """

    lat: float = Field(..., ge=-90, le=90)
    lng: float = Field(..., ge=-180, le=180)
    radius_km: float = Field(50, gt=0, le=20000)
    industry: str | None = None


class NearbyLeadOut(BaseModel):
    lead_id: uuid.UUID
    company_name: str
    lat: float
    lng: float
    distance_km: float
    lead_score: int
    industry: str | None = None
    city: str | None = None

    model_config = {"from_attributes": True}
