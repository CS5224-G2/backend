import enum
import uuid
from datetime import datetime, timezone

from geoalchemy2 import Geography
from sqlalchemy import BigInteger, Boolean, DateTime, Double, Enum as SAEnum, ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .database import Base


class UserRole(str, enum.Enum):
    user = "user"
    admin = "admin"
    business = "business"


class CyclingPreference(str, enum.Enum):
    leisure = "Leisure"
    commuter = "Commuter"
    performance = "Performance"


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(Text, nullable=False)
    first_name: Mapped[str] = mapped_column(Text, nullable=False)
    last_name: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[UserRole] = mapped_column(
        SAEnum(UserRole, name="user_role"), nullable=False, default=UserRole.user
    )
    onboarding_complete: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    city_name: Mapped[str | None] = mapped_column(Text)
    cycling_preference: Mapped[CyclingPreference | None] = mapped_column(
        SAEnum(CyclingPreference, name="cycling_pref", values_callable=lambda x: [e.value for e in x])
    )
    weekly_goal_km: Mapped[float | None] = mapped_column(Double)
    bio_text: Mapped[str | None] = mapped_column(Text)
    avatar_url: Mapped[str | None] = mapped_column(Text)
    avatar_color: Mapped[str | None] = mapped_column(Text, default="#1D4ED8")

    third_party_ads_opt_out: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    data_improvement_opt_out: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    refresh_tokens: Mapped[list["RefreshToken"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    saved_routes: Mapped[list["UserSavedRoute"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    token_hash: Mapped[str] = mapped_column(Text, nullable=False)
    client: Mapped[str] = mapped_column(Text, nullable=False)
    remember_me: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    user: Mapped["User"] = relationship(back_populates="refresh_tokens")


class UserSavedRoute(Base):
    __tablename__ = "user_saved_routes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    route_id: Mapped[str] = mapped_column(Text, nullable=False)  # MongoDB ObjectId string
    saved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    user: Mapped["User"] = relationship(back_populates="saved_routes")

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
