from geoalchemy2 import Geography
from sqlalchemy import BigInteger, Double, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column
from .database import Base


class HawkerCentre(Base):
    __tablename__ = "hawker_centres"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    objectid: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)

    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str | None] = mapped_column(Text)

    address_block_house_number: Mapped[str | None] = mapped_column(Text)
    address_street_name: Mapped[str | None] = mapped_column(Text)
    address_building_name: Mapped[str | None] = mapped_column(Text)
    address_postal_code: Mapped[str | None] = mapped_column(Text)
    address_myenv: Mapped[str | None] = mapped_column(Text)

    photo_url: Mapped[str | None] = mapped_column(Text)
    number_of_cooked_food_stalls: Mapped[int | None] = mapped_column(Integer)

    awarded_date: Mapped[str | None] = mapped_column(Text)
    implementation_date: Mapped[str | None] = mapped_column(Text)
    est_original_completion_date: Mapped[str | None] = mapped_column(Text)
    hup_completion_date: Mapped[str | None] = mapped_column(Text)
    info_on_co_locators: Mapped[str | None] = mapped_column(Text)

    landxaddresspoint: Mapped[float | None] = mapped_column(Double)
    landyaddresspoint: Mapped[float | None] = mapped_column(Double)

    longitude: Mapped[float] = mapped_column(Double, nullable=False)
    latitude: Mapped[float] = mapped_column(Double, nullable=False)

    geom = mapped_column(Geography(geometry_type="POINT", srid=4326), nullable=False)

    inc_crc: Mapped[str | None] = mapped_column(Text)
    fmel_upd_d: Mapped[str | None] = mapped_column(Text)


class HistoricSite(Base):
    __tablename__ = "historic_sites"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    objectid: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)

    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)

    hyperlink: Mapped[str | None] = mapped_column(Text)
    photo_url: Mapped[str | None] = mapped_column(Text)

    address_block_house_number: Mapped[str | None] = mapped_column(Text)
    address_unit_number: Mapped[str | None] = mapped_column(Text)
    address_floor_number: Mapped[str | None] = mapped_column(Text)
    address_street_name: Mapped[str | None] = mapped_column(Text)
    address_building_name: Mapped[str | None] = mapped_column(Text)
    address_postal_code: Mapped[str | None] = mapped_column(Text)
    address_type: Mapped[str | None] = mapped_column(Text)

    landxaddresspoint: Mapped[float | None] = mapped_column(Double)
    landyaddresspoint: Mapped[float | None] = mapped_column(Double)

    longitude: Mapped[float] = mapped_column(Double, nullable=False)
    latitude: Mapped[float] = mapped_column(Double, nullable=False)

    geom = mapped_column(Geography(geometry_type="POINT", srid=4326), nullable=False)

    inc_crc: Mapped[str | None] = mapped_column(Text)
    fmel_upd_d: Mapped[str | None] = mapped_column(Text)


class Park(Base):
    __tablename__ = "parks"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    objectid: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)

    name: Mapped[str] = mapped_column(Text, nullable=False)

    x: Mapped[float | None] = mapped_column(Double)
    y: Mapped[float | None] = mapped_column(Double)

    longitude: Mapped[float] = mapped_column(Double, nullable=False)
    latitude: Mapped[float] = mapped_column(Double, nullable=False)

    geom = mapped_column(Geography(geometry_type="POINT", srid=4326), nullable=False)

    inc_crc: Mapped[str | None] = mapped_column(Text)
    fmel_upd_d: Mapped[str | None] = mapped_column(Text)


class TouristAttraction(Base):
    __tablename__ = "tourist_attractions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    objectid: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)

    page_title: Mapped[str] = mapped_column(Text, nullable=False)
    overview: Mapped[str | None] = mapped_column(Text)
    meta_description: Mapped[str | None] = mapped_column(Text)

    url_path: Mapped[str | None] = mapped_column(Text)
    image_path: Mapped[str | None] = mapped_column(Text)
    image_alt_text: Mapped[str | None] = mapped_column(Text)
    photo_credits: Mapped[str | None] = mapped_column(Text)
    external_link: Mapped[str | None] = mapped_column(Text)

    address: Mapped[str | None] = mapped_column(Text)
    postal_code: Mapped[str | None] = mapped_column(Text)
    opening_hours: Mapped[str | None] = mapped_column(Text)

    last_modified: Mapped[str | None] = mapped_column(Text)

    latitude: Mapped[float] = mapped_column(Double, nullable=False)
    longitude: Mapped[float] = mapped_column(Double, nullable=False)

    geom = mapped_column(Geography(geometry_type="POINT", srid=4326), nullable=False)

    inc_crc: Mapped[str | None] = mapped_column(Text)
    fmel_upd_d: Mapped[str | None] = mapped_column(Text)
