from enum import StrEnum
from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict


class _ORMBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)


T = TypeVar("T")
class Paginated(BaseModel, Generic[T]):
    items: list[T]
    total: int
    limit: int
    offset: int

class HawkerCentreResponse(_ORMBase):
    id: int
    name: str
    description: str | None
    status: str | None
    address_block_house_number: str | None
    address_street_name: str | None
    address_building_name: str | None
    address_postal_code: str | None
    photo_url: str | None
    number_of_cooked_food_stalls: int | None
    longitude: float
    latitude: float
    # Populated by /nearby queries; None on plain list/get responses
    distance_m: float | None = None

class HistoricSiteResponse(_ORMBase):
    id: int
    name: str
    description: str | None
    hyperlink: str | None
    photo_url: str | None
    address_block_house_number: str | None
    address_street_name: str | None
    address_building_name: str | None
    address_postal_code: str | None
    longitude: float
    latitude: float
    distance_m: float | None = None

class ParkResponse(_ORMBase):
    id: int
    name: str
    longitude: float
    latitude: float
    distance_m: float | None = None

class TouristAttractionResponse(_ORMBase):
    id: int
    page_title: str
    overview: str | None
    address: str | None
    postal_code: str | None
    opening_hours: str | None
    image_path: str | None
    external_link: str | None
    longitude: float
    latitude: float
    distance_m: float | None = None

class Point(BaseModel):
    lat: float
    lng: float


class POICategory(StrEnum):
    HAWKER_CENTRE = "hawker_centre"
    PARK = "park"
    HISTORIC_SITE = "historic_site"
    TOURIST_ATTRACTION = "tourist_attraction"


class POIWaypoint(BaseModel):
    name: str
    category: POICategory
    point: Point

class RoutePreferences(BaseModel):
    include_hawker_centres: bool = True
    include_parks: bool = True
    include_historic_sites: bool = True
    include_tourist_attractions: bool = True

class RouteRequest(BaseModel):
    model_config = ConfigDict(
        # example for Gardens By the Bay route
        json_schema_extra={
            # Example: East Coast Park coastal ride (~20km)
            # Changi Beach Park to Marina Barrage (reminds me of NS...)
            "example": {
                "origin": {"lat": 1.3889, "lng": 103.9874},
                "destination": {"lat": 1.2806, "lng": 103.8713},
                "waypoints": [],
                "preferences": {
                    "include_hawker_centres": True,
                    "include_parks": True,
                    "include_historic_sites": True,
                    "include_tourist_attractions": True,
                },
            }
        }
    )

    origin: Point
    destination: Point
    waypoints: list[Point] = []
    preferences: RoutePreferences = RoutePreferences()

class RouteResponse(BaseModel):
    # To visualize a gpx, you can use https://gpx.studio/app.
    # However, we are only returning a list of points. Can consider adding gpx export later
    path: list[Point]
    poi_waypoints: list[POIWaypoint] = []
    # not implemented yet
    distance: float
    duration: float


# ------------------------------------------------------------------
# Contract-facing models (used in /routes API responses)
# ------------------------------------------------------------------

class LatLng(BaseModel):
    """Bare coordinate pair for route_path entries."""
    lat: float
    lng: float


class NamedLatLng(BaseModel):
    """Coordinate pair with an optional display name, used for start_point / end_point."""
    lat: float
    lng: float
    name: str | None = None


class POIVisited(BaseModel):
    """A point of interest visited along a route, as returned to the frontend."""
    name: str
    description: str | None = None
    lat: float
    lng: float


class Checkpoint(BaseModel):
    """A named checkpoint along a route."""
    checkpoint_id: str
    checkpoint_name: str
    description: str | None = None
    lat: float
    lng: float


# ------------------------------------------------------------------
# Enums for route properties and preferences
# ------------------------------------------------------------------

class CyclistType(StrEnum):
    RECREATIONAL = "recreational"
    COMMUTER = "commuter"
    FITNESS = "fitness"
    GENERAL = "general"


class ElevationPreference(StrEnum):
    LOWER = "lower"
    DONT_CARE = "dont-care"
    HIGHER = "higher"


class ShadePreference(StrEnum):
    REDUCE_SHADE = "reduce-shade"
    DONT_CARE = "dont-care"


class AirQualityPreference(StrEnum):
    CARE = "care"
    DONT_CARE = "dont-care"


# ------------------------------------------------------------------
# Route response shapes
# ------------------------------------------------------------------

class RouteSummary(BaseModel):
    """Summary route object — returned by GET /routes and GET /routes/popular."""
    route_id: str
    name: str
    description: str | None = None
    distance: float                          # km
    estimated_time: int                      # minutes
    elevation: ElevationPreference
    shade: ShadePreference
    air_quality: AirQualityPreference
    cyclist_type: CyclistType
    review_count: int = 0
    rating: float = 0.0
    checkpoints: list[Checkpoint] = []
    points_of_interest_visited: list[POIVisited] = []
    start_point: NamedLatLng
    end_point: NamedLatLng


class RouteDetail(RouteSummary):
    """Full route object — returned by GET /routes/:routeId. Adds the polyline path."""
    route_path: list[LatLng] = []


class RecommendationResult(BaseModel):
    """Route item returned by POST /routes/recommendations (lighter — no checkpoints or start/end points)."""
    route_id: str
    name: str
    description: str | None = None
    distance: float
    estimated_time: int
    elevation: ElevationPreference
    shade: ShadePreference
    air_quality: AirQualityPreference
    cyclist_type: CyclistType
    review_count: int = 0
    rating: float = 0.0
    points_of_interest_visited: list[POIVisited] = []


# ------------------------------------------------------------------
# Request shapes
# ------------------------------------------------------------------

class LocationSource(StrEnum):
    CURRENT_LOCATION = "current-location"
    SEARCH = "search"
    MAP = "map"


class RecommendationPoint(BaseModel):
    """A start or end point in a recommendations request."""
    lat: float
    lng: float
    name: str | None = None
    source: LocationSource


class RecommendationCheckpoint(BaseModel):
    """A waypoint checkpoint in a recommendations request."""
    id: str
    name: str
    lat: float
    lng: float
    source: LocationSource  # only "search" | "map" valid per contract, but we accept all LocationSource values


class POIPreferences(BaseModel):
    allow_hawker_center: bool = True
    allow_park: bool = True
    allow_historic_site: bool = True
    allow_tourist_attraction: bool = True


class RecommendationPreferences(BaseModel):
    cyclist_type: CyclistType = CyclistType.GENERAL
    shade_preference: ShadePreference = ShadePreference.DONT_CARE
    elevation_preference: ElevationPreference = ElevationPreference.DONT_CARE
    air_quality_preference: AirQualityPreference = AirQualityPreference.DONT_CARE
    max_distance: float | None = None           # km
    points_of_interest: POIPreferences = POIPreferences()


class RecommendationsRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "start_point": {"name": "Changi Beach Park", "lat": 1.3889, "lng": 103.9874, "source": "search"},
                "end_point": {"name": "Marina Barrage", "lat": 1.2806, "lng": 103.8713, "source": "search"},
                "checkpoints": [],
                "preferences": {
                    "cyclist_type": "recreational",
                    "shade_preference": "reduce-shade",
                    "elevation_preference": "dont-care",
                    "air_quality_preference": "care",
                    "max_distance": 99,
                    "points_of_interest": {
                        "allow_hawker_center": True,
                        "allow_park": True,
                        "allow_historic_site": True,
                        "allow_tourist_attraction": True,
                    },
                },
                "limit": 3,
            }
        }
    )

    start_point: RecommendationPoint
    end_point: RecommendationPoint
    checkpoints: list[RecommendationCheckpoint] = []
    preferences: RecommendationPreferences = RecommendationPreferences()
    limit: int = 3


class SaveRouteRequest(BaseModel):
    """Snapshot of a route the user wants to save to their favourites."""
    route_id: str
    name: str
    description: str | None = None
    distance: float
    estimated_time: int
    elevation: ElevationPreference
    shade: ShadePreference
    air_quality: AirQualityPreference
    cyclist_type: CyclistType
    checkpoints: list[Checkpoint] = []
    points_of_interest_visited: list[POIVisited] = []
    route_path: list[LatLng] = []


class SaveRouteResponse(BaseModel):
    saved_route_id: str
    route_id: str
    saved_at: str       # ISO 8601 timestamp
    status: str = "saved"
