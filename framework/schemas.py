from enum import StrEnum
from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, EmailStr, field_validator
from typing import Literal


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
    total_ascent_m: float = 0.0


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


# ------------------------------------------------------------------
# Auth schemas
# ------------------------------------------------------------------

UserRoleLiteral = Literal["user", "admin", "business"]
CyclingPreferenceLiteral = Literal["Leisure", "Commuter", "Performance"]
ClientLiteral = Literal["mobile_app", "web_app"]


class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    remember_me: bool = False
    client: ClientLiteral = "mobile_app"


class RegisterRequest(BaseModel):
    first_name: str
    last_name: str
    email: EmailStr
    password: str
    confirm_password: str
    agreed_to_terms: bool
    client: ClientLiteral = "mobile_app"

    @field_validator("confirm_password")
    @classmethod
    def passwords_match(cls, v: str, info) -> str:
        if "password" in info.data and v != info.data["password"]:
            raise ValueError("Passwords do not match")
        return v


class TokenRefreshRequest(BaseModel):
    refresh_token: str


class AuthUserResponse(_ORMBase):
    id: str
    first_name: str
    last_name: str
    email: str
    onboarding_complete: bool
    role: UserRoleLiteral

    @field_validator("id", mode="before")
    @classmethod
    def uuid_to_str(cls, v) -> str:
        return str(v)


class AuthResponse(BaseModel):
    access_token: str
    refresh_token: str
    expires_in: int
    user: AuthUserResponse


# ------------------------------------------------------------------
# User profile schemas
# ------------------------------------------------------------------

class RideStats(BaseModel):
    total_rides: int = 0
    total_distance_km: float = 0.0
    favorite_trails_count: int = 0


class UserProfileResponse(BaseModel):
    user_id: str
    full_name: str
    email_address: str
    city_name: str | None
    member_since: str
    cycling_preference: CyclingPreferenceLiteral | None
    weekly_goal_km: float | None
    bio_text: str | None
    avatar_url: str | None
    avatar_color: str | None
    ride_stats: RideStats


class UpdateProfileRequest(BaseModel):
    full_name: str | None = None
    city_name: str | None = None
    cycling_preference: CyclingPreferenceLiteral | None = None
    weekly_goal_km: float | None = None
    bio_text: str | None = None
    avatar_color: str | None = None


class AvatarUploadResponse(BaseModel):
    avatar_url: str


# ------------------------------------------------------------------
# User settings schemas
# ------------------------------------------------------------------

class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str
    confirm_new_password: str

    @field_validator("confirm_new_password")
    @classmethod
    def passwords_match(cls, v: str, info) -> str:
        if "new_password" in info.data and v != info.data["new_password"]:
            raise ValueError("Passwords do not match")
        return v


class ChangePasswordResponse(BaseModel):
    status: str = "ok"
    message: str = "Password updated successfully."
    updated_at: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str


class MessageResponse(BaseModel):
    message: str


class PrivacyControls(BaseModel):
    third_party_ads_opt_out: bool
    data_improvement_opt_out: bool


class DevicePermissions(BaseModel):
    notifications_managed_in_os: bool = True


class PrivacyResponse(BaseModel):
    privacy_controls: PrivacyControls
    device_permissions: DevicePermissions


class UpdatePrivacyRequest(BaseModel):
    privacy_controls: PrivacyControls


# ------------------------------------------------------------------
# Rides / Feedback schemas
# ------------------------------------------------------------------

class FeedbackRequest(BaseModel):
    route_id: str
    rating: int
    review_text: str = ""

    @field_validator("rating")
    @classmethod
    def rating_in_range(cls, v: int) -> int:
        if not (1 <= v <= 5):
            raise ValueError("rating must be between 1 and 5")
        return v


# ------------------------------------------------------------------
# Admin schemas
# ------------------------------------------------------------------

class AdminUserListItem(BaseModel):
    user_id: str
    email_address: str
    role: UserRoleLiteral
    account_status: Literal["Active", "Inactive"]
    joined_formatted: str
