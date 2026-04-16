> **AI-Use Declaration**: This codebase was developed with the assistance of AI tools, primarily Claude (Anthropic). AI was used across multiple areas of development: generating boilerplate and scaffolding code (FastAPI routers, Pydantic schemas, SQLAlchemy models), suggesting algorithm implementations (route scoring, shortest-path integration, KD-tree shade calculation), drafting infrastructure-as-code configurations (OpenTofu modules for ECS, RDS, ElastiCache, CloudFront), writing utility scripts, and producing documentation. All AI-generated code and content was reviewed, tested, and integrated by team members who took responsibility for correctness. Learning: AI tools are most effective for accelerating well-defined tasks (CRUD endpoints, schema definitions, IaC patterns) but require careful human oversight for domain-specific logic such as geospatial routing constraints, AWS service interactions, and cross-service concurrency.

# CycleLink Backend

Backend services for **CycleLink**, a personalised cycling route platform for Singapore. The backend exposes a REST API that powers a React Native mobile app and a React web dashboard.

## Architecture

Two FastAPI services communicate to handle route requests:

| Service | Entry point | Purpose |
|---|---|---|
| **Core API** | `framework/main.py` | Auth, user profiles, route management, ride logging, POI queries, admin dashboard |
| **Bike Route** | `route/server.py` | On-demand route computation — builds shortest-path routes from an OSM graph with elevation and tree-shade scoring |

Both services are containerised and deployed on AWS ECS Fargate behind an Application Load Balancer, with CloudFront as a CDN layer.

## Features

- **Authentication** — JWT-based login/register with refresh-token rotation, password reset via email (SendGrid), role-based access control (`user` / `admin` / `business`)
- **User profiles** — CRUD profile with avatar upload to S3, cycling preferences, weekly distance goals, privacy controls
- **Route discovery** — Browse pre-computed routes, popular routes (Redis-cached), route detail with full polyline
- **Personalised recommendations** — 5-signal scoring engine ranks routes by cyclist type, elevation preference, shade coverage, air quality, and community rating
- **On-demand route generation** — Bike-route microservice computes shortest-path routes over a Singapore OSM cycling graph (NetworkX/OSMNx); shade score derived from a KD-tree index of ~500 k Singapore tree locations
- **Ride logging** — Record completed rides (distance, speed, checkpoints visited); full ride history and weekly/monthly distance stats
- **Post-ride feedback** — 1–5 star ratings stored in PostgreSQL; scores feed back into the recommendation engine
- **Points of interest** — Geospatial list/nearby/detail endpoints for hawker centres, historic sites, parks, and tourist attractions (PostGIS)
- **Weather** — Live NEA weather data fetched by an AWS Lambda on a schedule, cached in ElastiCache (Redis); served via `GET /v1/weather`
- **Admin dashboard** — User management, platform stats, CloudWatch infrastructure metrics (ECS CPU/memory, ALB latency/error rate), error log aggregation, routing quality analysis

## Tech Stack

| Layer | Technology |
|---|---|
| API framework | FastAPI + uvicorn |
| Relational DB | PostgreSQL 17 + PostGIS (via SQLAlchemy async + asyncpg) |
| Document DB | MongoDB (pymongo) |
| Cache | Redis / AWS ElastiCache |
| Object storage | AWS S3 (avatars, OSM graph) |
| Container infra | AWS ECS Fargate, ECR, ALB, CloudFront, WAF |
| Observability | AWS CloudWatch Logs & Metrics |
| Routing graph | OSMNx + NetworkX |
| Package manager | [uv](https://docs.astral.sh/uv/) |

## Local Setup

### Prerequisites

- [uv](https://docs.astral.sh/uv/getting-started/installation/#standalone-installer)
- PostgreSQL ≥ 17 with PostGIS extension (Homebrew: `brew install postgresql@17 postgis`)
- MongoDB
- Redis

### Install

```bash
# Install the bike_route package as an editable workspace member (one-time)
uv add --editable ./route/bike_route

# Install all dependencies
uv sync
```

### Environment

Copy `.env.example` to `.env` and fill in the required values (database URLs, JWT secret, AWS credentials, etc.).

### Database Setup

1. Install `postgres` and `postgis` locally. (For Homebrew, you will need `postgres@17` or later.)

2. Create a user called `postgres` after installation.

3. Ensure you have the `.geojson` files in `./data`:
   - Hawker Centres — https://data.gov.sg/datasets/d_4a086da0a5553be1d89383cd90d07ecd/view
   - Historic Sites — https://data.gov.sg/collections/1460/view
   - Parks — https://data.gov.sg/datasets/d_0542d48f0991541706b58059381a6eca/view
   - Tourist Attractions — https://data.gov.sg/collections/1621/view

4. In pgAdmin, create a database called `CycleLink`.

5. Create tables using `db/schema.sql`.

6. Seed POI data by running the import script from the project root:
   ```bash
   uv run python scripts/import_geojson.py
   ```
   Enter your pgAdmin password when prompted. Ensure your database is configured as per `DB_CONFIG` in the script.

### Run

Start both services from the project root in separate terminals:

```bash
# Core API (port 8000)
uv run fastapi dev framework/main.py

# Bike Route microservice (port 8001)
uv run uvicorn route.server:app --reload
```

The interactive API docs (Swagger UI) are available at `http://localhost:8000/docs` (HTTP Basic auth required; credentials set via `SWAGGER_USERNAME` / `SWAGGER_PASSWORD` env vars).

## Team Contributions

### Jamie
- Set up the core FastAPI project structure: configuration, database session management, service/router pattern, and package setup with `uv`
- Implemented JWT authentication, user registration, and route-saving endpoints
- Built the user ride endpoints: ride creation, ride history, distance stats, and post-ride feedback
- Added shade scoring as a route recommendation signal; implemented Redis caching for POIs and routes
- Migrated route computation to the bike-route microservice and added route deduplication (favorites)
- Implemented routing quality metrics in the admin dashboard (score-to-rating correlation, computation time tracking)
- Performance improvements to the bike-route service: SCC graph restriction, concurrency caps, subgraph extraction optimisation, cycling path bug fixes

### Zhuo En
- Initial project scaffolding, `.gitignore`, and database schema (`schema.sql`)
- Built the PostGIS GeoJSON import pipeline for hawker centres, historic sites, parks, and tourist attractions
- Implemented the initial bike-route generation API (OSMNx graph, subprocess integration) and migrated it into the framework
- Added POI waypoint insertion to the route suggestion pipeline
- Built the route recommendation scoring system (elevation, weather/air-quality signals) and fingerprint-based route deduplication
- Implemented forgot-password and reset-password endpoints with SendGrid email delivery

### Jared
- Designed and maintained all AWS infrastructure using OpenTofu (IaC): VPC, RDS (PostgreSQL), ElastiCache (Redis), S3, ECS Fargate clusters, ALB, CloudFront CDN, WAF, and CloudMap service discovery
- Provisioned and maintained the AWS Lambda function for scheduled weather data fetching from NEA
- Added CloudWatch metrics and log endpoints to the admin dashboard (ECS CPU/memory, ALB latency/error rates)
- Configured ECS autoscaling, SNS alerting, and load testing (Locust)

### Example PostGIS Query

Select the 5 nearest hawker centres to Choa Chu Kang MRT Station:

```sql
SELECT name,
       ST_Distance(
           geom,
           ST_SetSRID(ST_MakePoint(103.7443, 1.3854), 4326)::geography
       ) AS distance_m
FROM hawker_centres
ORDER BY distance_m
LIMIT 5;
```
