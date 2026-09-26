# Operations

Use the current [README](../README.md) for environment settings, standalone Alembic, management commands, Docker, durable uploads, PostgreSQL, Redis, email APIs and proxy trust. No Flask CLI or Render configuration is required.

Back up the database and uploads together; restore into an isolated environment before production cutover. Health probes are /health/live and /health/ready. Keep secrets outside the package. See [migration report](MIGRATION-REPORT.md) for verified checks and operational limitations.
