# Local Operations Runbook Design

## Purpose

Create a concise, copy-paste-friendly runbook for a Windows operator who needs to start, verify, use, and stop the complete local OpenMetadata ERD Viewer environment safely.

## Audience and scope

The primary reader is a local operator using PowerShell, Docker Desktop, and this repository. The runbook covers:

- preflight checks and one-time configuration;
- the supported Docker Compose startup command and the service dependency sequence it drives;
- readiness checks for the OpenMetadata stack;
- startup and verification of the FastAPI adapter and Vite frontend;
- log locations and first-response troubleshooting;
- graceful shutdown, restart, and clean-reset procedures;
- preservation and deliberate removal of persistent Docker volumes.

It does not define a production deployment, catalog ingestion workflow, backup policy, application authentication model, or non-Windows operating procedure.

## Document structure

The runbook will use a lifecycle sequence:

1. Environment and service map
2. First-time setup
3. Normal startup
4. Health and functional checks
5. Routine operation and logs
6. Graceful shutdown
7. Restart and recovery
8. Troubleshooting and command reference

The normal path will be short and prominent. Destructive or exceptional procedures will be separated and clearly labeled.

## Operational model

Docker Compose remains responsible for dependency ordering. Operators will run the full stack with one `docker compose ... up -d` command rather than manually starting individual containers. The runbook will explain the effective sequence observed in `docker-compose-postgres.yml`: PostgreSQL and Elasticsearch become ready first; the one-shot migration service runs after both are healthy; the OpenMetadata server starts after the databases are healthy and migration completes; ingestion starts after its declared dependencies. The ERD viewer starts only after the OpenMetadata health endpoint and UI are available.

For the viewer, `scripts/dev.ps1` is the supported launcher. It starts the adapter on port 8000, waits for it, then starts the frontend on port 5173. `Ctrl+C` in the launcher terminal is the supported graceful stop for both local processes.

## Safety and correctness rules

- Never print or embed the OpenMetadata bot JWT in the runbook, logs, URLs, or screenshots.
- Use `docker compose down` for an ordinary stack shutdown so named volumes remain intact.
- Present `docker compose down -v` only as an explicitly destructive reset that deletes local catalog, search, and ingestion state.
- Distinguish the one-shot migration container exiting successfully from a failed long-running service.
- Base health checks and troubleshooting commands on repository files rather than assumptions.
- Avoid claiming production readiness; the application binds its local servers to loopback and is documented as a laptop/demo tool.

## Acceptance criteria

The completed runbook enables a new local operator to:

1. identify required software, configuration, ports, and credentials;
2. start services in the supported order without manually managing container dependencies;
3. verify Docker, OpenMetadata, adapter, and frontend readiness;
4. find the relevant logs when startup fails;
5. stop only the viewer or the entire stack without losing persistent data;
6. distinguish an ordinary restart from a destructive clean reset.

