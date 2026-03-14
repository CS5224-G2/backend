# backend

## Database 

### Installation (Local)

1. Install the requirements as stated in requirements.txt

2. Ensure you have the .geojson files in `./data`:
    - Hawker Centres https://data.gov.sg/datasets/d_4a086da0a5553be1d89383cd90d07ecd/view
    - Historic Sites https://data.gov.sg/collections/1460/view
    - Parks https://data.gov.sg/datasets/d_0542d48f0991541706b58059381a6eca/view
    - Tourist Attractions https://data.gov.sg/collections/1621/view

3. In pgadmin, create a database called `CycleLink`

4. Create the tables using schema.sql

5. To fill up the tables, run the import_geojson.py script from project root. 
    - Enter your pgAdmin password when prompted
    - Ensure that your database is set up as per `DB_CONFIG`.

### Example Command

Select the nearest 5 hawker centres to Choa Chu Kang MRT Station:

```
SELECT name,
       ST_Distance(
           geom,
           ST_SetSRID(ST_MakePoint(103.7443,1.3854),4326)::geography
       ) AS distance_m
FROM hawker_centres
ORDER BY distance_m
LIMIT 5;
```
