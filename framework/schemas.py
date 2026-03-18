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
    lon: float

class RouteRequest(BaseModel):
    model_config = ConfigDict(
        # example for Gardens By the Bay route
        json_schema_extra={
            "example": {
                "origin": {"lat": 1.3009, "lon": 103.9122},
                "destination": {"lat": 1.3038, "lon": 103.9385},
                "waypoints": [],
                "preferences": {},
            }
        }
    )

    origin: Point
    destination: Point
    waypoints: list[Point] = []
    preferences: dict | None = None

class RouteResponse(BaseModel):
    # To visualize a gpx, you can use https://gpx.studio/app.
    # However, we are only returning a list of points. Can consider adding gpx export later
    path: list[Point]
    # not implemented yet
    distance: float
    duration: float
