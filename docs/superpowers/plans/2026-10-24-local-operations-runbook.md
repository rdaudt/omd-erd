# Local Operations Runbook Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create a verified Windows/PowerShell runbook that lets a local operator safely start, check, use, restart, and stop the complete OpenMetadata ERD Viewer environment.

**Architecture:** Add one lifecycle-oriented Markdown document at `docs/RUNBOOK.md`. Derive its commands, dependency sequence, ports, health checks, logs, and shutdown semantics directly from `docker-compose-postgres.yml`, `scripts/dev.ps1`, `.env.example`, and `README.md`.

**Tech Stack:** Markdown, Windows PowerShell 5.1+, Docker Compose, FastAPI/Uvicorn, React/Vite

## Global Constraints

- Optimize for a local Windows operator using PowerShell and Docker Desktop.
- Keep the normal path short and copy-paste-friendly.
- Treat Docker Compose as responsible for container dependency ordering.
- Use `scripts/dev.ps1` as the supported viewer launcher.
- Never print or embed the OpenMetadata bot JWT.
- Use `docker compose down` for ordinary shutdown and clearly identify `docker compose down -v` as destructive.
- Do not present this laptop/demo application as a production deployment.

---

### Task 1: Create and verify the lifecycle runbook

**Files:**
- Create: `docs/RUNBOOK.md`
- Reference: `docker-compose-postgres.yml`
- Reference: `scripts/dev.ps1`
- Reference: `.env.example`
- Reference: `README.md`

**Interfaces:**
- Consumes: Compose service definitions and health dependencies, launcher process behavior, environment settings, and documented prerequisites.
- Produces: A standalone operator procedure with preflight, startup, verification, routine operation, shutdown, restart/recovery, and troubleshooting sections.

- [ ] **Step 1: Reconfirm the operational facts from source files**

Run:

```powershell
docker compose -f docker-compose-postgres.yml config --services
Select-String -Path docker-compose-postgres.yml -Pattern 'depends_on:','healthcheck:','ports:' -Context 0,6
Get-Content -Raw scripts/dev.ps1
Get-Content -Raw .env.example
```

Expected: the Compose model lists `postgresql`, `elasticsearch`, `execute-migrate-all`, `openmetadata-server`, and `ingestion`; the source files confirm ports 5432, 9200/9300, 8585/8586, 8080, 8000, and 5173 and the launcher's adapter-before-frontend order.

- [ ] **Step 2: Write the runbook**

Create `docs/RUNBOOK.md` with these exact top-level sections:

```markdown
# OpenMetadata ERD Viewer Local Operations Runbook

## Scope and safety
## Service map and startup sequence
## First-time setup
## Start the application
## Verify the application
## Routine operation and logs
## Stop the application
## Restart and recover
## Troubleshooting
## Quick command reference
```

Within those sections, include:

- prerequisites and required ports;
- `.env` creation and secret-handling rules;
- the single full-stack Compose startup command;
- an explanation of dependency-aware startup and the successful one-shot migration container;
- health checks for Compose, OpenMetadata, the adapter, and the browser UI;
- `scripts/dev.ps1` startup and `Ctrl+C` shutdown behavior;
- viewer-only, stack-only, and complete restart procedures;
- ordinary `down` versus explicitly destructive `down -v` behavior;
- targeted logs and symptom-based troubleshooting;
- a compact copy-paste start/check/stop reference.

- [ ] **Step 3: Validate commands and internal consistency**

Run:

```powershell
docker compose -f docker-compose-postgres.yml config --quiet
Select-String -Path docs/RUNBOOK.md -Pattern 'TB[D]|TO[DO]|replace-with-a-bot-jwt|down -v'
git diff --check -- docs/RUNBOOK.md
```

Expected: Compose validation succeeds; the runbook contains no unfinished markers; `replace-with-a-bot-jwt` appears only as a safe example value if shown; `down -v` appears only with a destructive-data-loss warning; and `git diff --check` reports no whitespace errors.

- [ ] **Step 4: Review the runbook against acceptance criteria**

Confirm manually that a new operator can identify requirements, execute normal startup, distinguish healthy and failed states, find logs, stop without losing data, and recognize a destructive reset. Confirm that all commands use the repository's actual paths and service names.

- [ ] **Step 5: Commit the runbook**

Run:

```powershell
git add docs/RUNBOOK.md
git commit -m "docs: add local operations runbook"
```

Expected: the commit includes only `docs/RUNBOOK.md`.

