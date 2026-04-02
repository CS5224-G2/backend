CREATE EXTENSION IF NOT EXISTS postgis;

CREATE TABLE hawker_centres (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    objectid BIGINT UNIQUE NOT NULL,

    name TEXT NOT NULL,
    description TEXT,
    status TEXT,

    address_block_house_number TEXT,
    address_street_name TEXT,
    address_building_name TEXT,
    address_postal_code TEXT,
    address_myenv TEXT,

    photo_url TEXT,

    number_of_cooked_food_stalls INTEGER,

    -- Dates formats are inconsistent in source, so stored as text for now
    awarded_date TEXT,
    implementation_date TEXT,
    est_original_completion_date TEXT,
    hup_completion_date TEXT,

    info_on_co_locators TEXT,

    landxaddresspoint DOUBLE PRECISION,
    landyaddresspoint DOUBLE PRECISION,

    longitude DOUBLE PRECISION NOT NULL,
    latitude DOUBLE PRECISION NOT NULL,

    geom GEOGRAPHY(POINT, 4326) NOT NULL,

    inc_crc TEXT,
    fmel_upd_d TEXT
);

CREATE TABLE historic_sites (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    objectid BIGINT UNIQUE NOT NULL,

    name TEXT NOT NULL,
    description TEXT,

    hyperlink TEXT,
    photo_url TEXT,

    address_block_house_number TEXT,
    address_unit_number TEXT,
    address_floor_number TEXT,
    address_street_name TEXT,
    address_building_name TEXT,
    address_postal_code TEXT,
    address_type TEXT,

    landxaddresspoint DOUBLE PRECISION,
    landyaddresspoint DOUBLE PRECISION,

    longitude DOUBLE PRECISION NOT NULL,
    latitude DOUBLE PRECISION NOT NULL,

    geom GEOGRAPHY(POINT, 4326) NOT NULL,

    inc_crc TEXT,
    fmel_upd_d TEXT
);

CREATE TABLE parks (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    objectid BIGINT UNIQUE NOT NULL,
    name TEXT NOT NULL,

    x DOUBLE PRECISION,
    y DOUBLE PRECISION,

    longitude DOUBLE PRECISION NOT NULL,
    latitude DOUBLE PRECISION NOT NULL,

    geom GEOGRAPHY(POINT, 4326) NOT NULL,

    inc_crc TEXT,
    fmel_upd_d TEXT
);

CREATE TABLE tourist_attractions (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    objectid BIGINT UNIQUE NOT NULL,

    page_title TEXT NOT NULL,
    overview TEXT,
    meta_description TEXT,

    url_path TEXT,
    image_path TEXT,
    image_alt_text TEXT,
    photo_credits TEXT,
    external_link TEXT,

    address TEXT,
    postal_code TEXT,
    opening_hours TEXT,

    last_modified TEXT,

    latitude DOUBLE PRECISION NOT NULL,
    longitude DOUBLE PRECISION NOT NULL,

    geom GEOGRAPHY(POINT, 4326) NOT NULL,

    inc_crc TEXT,
    fmel_upd_d TEXT
);

-- ============================================================
-- Auth / User tables
-- ============================================================

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TYPE user_role AS ENUM ('user', 'admin', 'business');
CREATE TYPE cycling_pref AS ENUM ('Leisure', 'Commuter', 'Performance');

CREATE TABLE users (
    id                       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email                    TEXT UNIQUE NOT NULL,
    hashed_password          TEXT NOT NULL,
    first_name               TEXT NOT NULL,
    last_name                TEXT NOT NULL,
    role                     user_role NOT NULL DEFAULT 'user',
    onboarding_complete      BOOLEAN NOT NULL DEFAULT FALSE,

    -- Profile fields
    city_name                TEXT,
    cycling_preference       cycling_pref,
    weekly_goal_km           DOUBLE PRECISION,
    bio_text                 TEXT,
    avatar_url               TEXT,
    avatar_color             TEXT DEFAULT '#1D4ED8',

    -- Privacy settings (backend-controlled only; OS permissions managed client-side)
    third_party_ads_opt_out  BOOLEAN NOT NULL DEFAULT FALSE,
    data_improvement_opt_out BOOLEAN NOT NULL DEFAULT FALSE,

    is_active                BOOLEAN NOT NULL DEFAULT TRUE,
    created_at               TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at               TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX users_email_idx ON users(email);

-- user_saved_routes links a user to a MongoDB route document.
-- route_id is the MongoDB ObjectId string (from precomputed-routes or generated-routes collections).
-- favorite_trails_count in GET /user/profile = COUNT(*) WHERE user_id = current_user.id
CREATE TABLE user_saved_routes (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id    UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    route_id   TEXT NOT NULL,   -- MongoDB ObjectId string
    saved_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (user_id, route_id)  -- prevents duplicate saves (409 check)
);

CREATE INDEX user_saved_routes_user_id_idx ON user_saved_routes(user_id);

CREATE TABLE refresh_tokens (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash  TEXT NOT NULL,   -- SHA-256 hex of the token
    client      TEXT NOT NULL,   -- 'mobile_app' | 'web_app'
    remember_me BOOLEAN NOT NULL DEFAULT FALSE,
    expires_at  TIMESTAMPTZ NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    revoked_at  TIMESTAMPTZ      -- NULL = still valid; set on rotation or account deletion
);

CREATE INDEX refresh_tokens_user_id_idx    ON refresh_tokens(user_id);
CREATE INDEX refresh_tokens_token_hash_idx ON refresh_tokens(token_hash);

CREATE TABLE user_route_ratings (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    route_id    TEXT NOT NULL,   -- MongoDB ObjectId string
    rating      INTEGER NOT NULL CHECK (rating BETWEEN 1 AND 5),
    review_text TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_user_route_rating UNIQUE (user_id, route_id)
);

CREATE INDEX user_route_ratings_route_id_idx ON user_route_ratings(route_id);