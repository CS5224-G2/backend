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