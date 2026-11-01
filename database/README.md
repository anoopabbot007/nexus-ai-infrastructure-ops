# Database

PostgreSQL 16 is provisioned by Compose with the named volume `nexus-postgres-data`.
Flyway creates the `incidents` and `investigations` tables at backend startup from
`backend/src/main/resources/db/migration/V1__create_incident_tables.sql`. Investigation
evidence, logs, recommendations and workflow trace are stored as JSONB. Keep credentials
in `.env`; the defaults are only for a local demonstration.
