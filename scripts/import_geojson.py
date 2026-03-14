import json
import psycopg2
from getpass import getpass

DB_CONFIG = {
    "dbname": "CycleLink",
    "user": "postgres",
    # "password": "...",
    "host": "localhost",
    "port": 5432
}

def import_hawker_centres(conn, file_path):
    cur = conn.cursor()

    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    for feature in data["features"]:
        props = feature["properties"]
        coords = feature["geometry"]["coordinates"]

        longitude = coords[0]
        latitude = coords[1]

        cur.execute("""
        INSERT INTO hawker_centres (
            objectid,
            name,
            description,
            status,
            address_block_house_number,
            address_street_name,
            address_building_name,
            address_postal_code,
            address_myenv,
            photo_url,
            number_of_cooked_food_stalls,
            awarded_date,
            implementation_date,
            est_original_completion_date,
            hup_completion_date,
            info_on_co_locators,
            landxaddresspoint,
            landyaddresspoint,
            longitude,
            latitude,
            geom,
            inc_crc,
            fmel_upd_d
        )
        VALUES (
            %s,%s,%s,%s,
            %s,%s,%s,%s,%s,
            %s,
            %s,
            %s,%s,%s,%s,
            %s,
            %s,%s,
            %s,%s,
            ST_SetSRID(ST_MakePoint(%s,%s),4326)::geography,
            %s,%s
        )
        ON CONFLICT (objectid) DO NOTHING
        """,
        (
            props["OBJECTID"],
            props["NAME"],
            props["DESCRIPTION"],
            props["STATUS"],
            props["ADDRESSBLOCKHOUSENUMBER"],
            props["ADDRESSSTREETNAME"],
            props["ADDRESSBUILDINGNAME"],
            props["ADDRESSPOSTALCODE"],
            props["ADDRESS_MYENV"],
            props["PHOTOURL"],
            props["NUMBER_OF_COOKED_FOOD_STALLS"],
            props["AWARDED_DATE"],
            props["IMPLEMENTATION_DATE"],
            props["EST_ORIGINAL_COMPLETION_DATE"],
            props["HUP_COMPLETION_DATE"],
            props["INFO_ON_CO_LOCATORS"],
            props["LANDXADDRESSPOINT"],
            props["LANDYADDRESSPOINT"],
            longitude,
            latitude,
            longitude,
            latitude,
            props["INC_CRC"],
            props["FMEL_UPD_D"]
        ))

    conn.commit()
    cur.close()

def import_historic_sites(conn, filepath):
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)

    cur = conn.cursor()

    for feature in data["features"]:
        props = feature["properties"]
        coords = feature["geometry"]["coordinates"]

        longitude = coords[0]
        latitude = coords[1]

        cur.execute("""
        INSERT INTO historic_sites (
            objectid,
            name,
            description,
            hyperlink,
            photo_url,
            address_block_house_number,
            address_unit_number,
            address_floor_number,
            address_street_name,
            address_building_name,
            address_postal_code,
            address_type,
            landxaddresspoint,
            landyaddresspoint,
            longitude,
            latitude,
            geom,
            inc_crc,
            fmel_upd_d
        )
        VALUES (
            %s,%s,%s,%s,%s,
            %s,%s,%s,%s,%s,%s,%s,
            %s,%s,
            %s,%s,
            ST_SetSRID(ST_MakePoint(%s,%s),4326)::geography,
            %s,%s
        )
        ON CONFLICT (objectid) DO NOTHING
        """,
        (
            props["OBJECTID_1"],
            props["NAME"],
            props["DESCRIPTION"],
            props["HYPERLINK"],
            props["PHOTOURL"],
            props["ADDRESSBLOCKHOUSENUMBER"],
            props["ADDRESSUNITNUMBER"],
            props["ADDRESSFLOORNUMBER"],
            props["ADDRESSSTREETNAME"],
            props["ADDRESSBUILDINGNAME"],
            props["ADDRESSPOSTALCODE"],
            props["ADDRESSTYPE"],
            props["LANDXADDRESSPOINT"],
            props["LANDYADDRESSPOINT"],
            longitude,
            latitude,
            longitude,
            latitude,
            props["INC_CRC"],
            props["FMEL_UPD_D"]
        ))

    conn.commit()
    cur.close()

def import_parks(conn, filepath):
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)

    cur = conn.cursor()

    for feature in data["features"]:
        props = feature["properties"]
        coords = feature["geometry"]["coordinates"]

        longitude = coords[0]
        latitude = coords[1]

        cur.execute("""
        INSERT INTO parks (
            objectid,
            name,
            x,
            y,
            longitude,
            latitude,
            geom,
            inc_crc,
            fmel_upd_d
        )
        VALUES (
            %s,%s,%s,%s,
            %s,%s,
            ST_SetSRID(ST_MakePoint(%s,%s),4326)::geography,
            %s,%s
        )
        ON CONFLICT (objectid) DO NOTHING
        """, (
            props["OBJECTID"],
            props["NAME"],
            props["X"],
            props["Y"],
            longitude,
            latitude,
            longitude,
            latitude,
            props["INC_CRC"],
            props["FMEL_UPD_D"]
        ))

    conn.commit()
    cur.close()

def import_tourist_attractions(conn, filepath):
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)

    cur = conn.cursor()

    for feature in data["features"]:
        props = feature["properties"]
        coords = feature["geometry"]["coordinates"]

        longitude = coords[0]
        latitude = coords[1]

        cur.execute("""
        INSERT INTO tourist_attractions (
            objectid,
            page_title,
            overview,
            meta_description,
            url_path,
            image_path,
            image_alt_text,
            photo_credits,
            external_link,
            address,
            postal_code,
            opening_hours,
            last_modified,
            latitude,
            longitude,
            geom,
            inc_crc,
            fmel_upd_d
        )
        VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s, %s,
            ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography,
            %s, %s
        )
        ON CONFLICT (objectid) DO NOTHING
        """, (
            props["OBJECTID_1"],
            props["PAGETITLE"],
            props["OVERVIEW"],
            props["META_DESCRIPTION"],
            props["URL_PATH"],
            props["IMAGE_PATH"],
            props["IMAGE_ALT_TEXT"],
            props["PHOTOCREDITS"],
            props["EXTERNAL_LINK"],
            props["ADDRESS"],
            props["POSTALCODE"],
            props["OPENING_HOURS"],
            props["LASTMODIFIED"],
            latitude,
            longitude,
            longitude,
            latitude,
            props["INC_CRC"],
            props["FMEL_UPD_D"]
        ))

    conn.commit()
    cur.close()

def main():
    # For local use
    DB_CONFIG["password"] = getpass("Enter database password: ")

    conn = psycopg2.connect(**DB_CONFIG)

    import_hawker_centres(conn, "./data/HawkerCentresGEOJSON.geojson")
    import_historic_sites(conn, "./data/Historic Sites (GEOJSON).geojson")
    import_parks(conn, "./data/Parks.geojson")
    import_tourist_attractions(conn, "./data/Tourist Attractions.geojson")

if __name__ == "__main__":
    main()
