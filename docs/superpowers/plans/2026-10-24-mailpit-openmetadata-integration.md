# Mailpit and OpenMetadata Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a persistent, loopback-only Mailpit inbox and configure the local OpenMetadata server to deliver notifications to it.

**Architecture:** Mailpit joins the existing `app_net` Compose network and accepts SMTP from OpenMetadata on its un-published port 1025. A named volume persists Mailpit's SQLite database, while the web UI is published only on `127.0.0.1:8025`.

**Tech Stack:** Docker Compose 3.9, Mailpit v1.27, OpenMetadata 2.0.5

## Global Constraints

- Store messages in the `mailpit-data` named Docker volume at `/data/mailpit.db`.
- Bind the Mailpit UI only to `127.0.0.1:8025`.
- Do not publish SMTP port 1025 to the host.
- Use plain SMTP without credentials only on the private `app_net` network.
- Preserve environment-variable overrides for every OpenMetadata email setting.
- Do not create users or trigger notification workflows.

---

### Task 1: Add and verify the Mailpit integration

**Files:**
- Modify: `docker-compose-postgres.yml`

**Interfaces:**
- Consumes: existing `app_net` network and `openmetadata-server` service
- Produces: Mailpit UI at `http://localhost:8025` and SMTP endpoint `mailpit:1025`

- [x] **Step 1: Record the failing configuration checks**

Run:

```powershell
docker compose -f docker-compose-postgres.yml config | Select-String 'mailpit|SMTP_SERVER_ENDPOINT|AUTHORIZER_ENABLE_SMTP'
```

Expected before implementation: no `mailpit` service, and SMTP remains disabled or has an empty endpoint.

- [x] **Step 2: Add the persistent Mailpit service and volume**

Add `mailpit-data` under top-level `volumes`, and add this service on `app_net`:

```yaml
  mailpit:
    image: axllent/mailpit:v1.27
    container_name: mailpit
    restart: unless-stopped
    environment:
      MP_DATABASE: /data/mailpit.db
    volumes:
      - mailpit-data:/data
    ports:
      - "127.0.0.1:8025:8025"
    expose:
      - 1025
    networks:
      - app_net
    healthcheck:
      test: ["CMD", "/mailpit", "readyz"]
      interval: 5s
      timeout: 5s
      retries: 10
```

- [x] **Step 3: Configure OpenMetadata SMTP defaults and dependency**

Set these defaults in `openmetadata-server.environment`:

```yaml
      AUTHORIZER_ENABLE_SMTP: ${AUTHORIZER_ENABLE_SMTP:-true}
      OPENMETADATA_SERVER_URL: ${OPENMETADATA_SERVER_URL:-"http://localhost:8585"}
      OPENMETADATA_SMTP_SENDER_MAIL: ${OPENMETADATA_SMTP_SENDER_MAIL:-"openmetadata@example.test"}
      SMTP_SERVER_ENDPOINT: ${SMTP_SERVER_ENDPOINT:-"mailpit"}
      SMTP_SERVER_PORT: ${SMTP_SERVER_PORT:-"1025"}
      SMTP_SERVER_USERNAME: ${SMTP_SERVER_USERNAME:-""}
      SMTP_SERVER_PWD: ${SMTP_SERVER_PWD:-""}
      SMTP_SERVER_STRATEGY: ${SMTP_SERVER_STRATEGY:-"SMTP"}
```

Add this entry to `openmetadata-server.depends_on`:

```yaml
      mailpit:
        condition: service_healthy
```

- [x] **Step 4: Validate the rendered Compose model**

Run:

```powershell
docker compose -f docker-compose-postgres.yml config --quiet
docker compose -f docker-compose-postgres.yml config | Select-String 'mailpit|SMTP_SERVER_ENDPOINT|SMTP_SERVER_PORT|SMTP_SERVER_STRATEGY|AUTHORIZER_ENABLE_SMTP'
```

Expected: the quiet validation exits 0; rendered configuration contains the Mailpit service, SMTP enabled, endpoint `mailpit`, port `1025`, and strategy `SMTP`.

- [x] **Step 5: Start the integration**

Run:

```powershell
docker compose -f docker-compose-postgres.yml up -d mailpit openmetadata-server
```

Expected: Mailpit is pulled if necessary, becomes healthy, and OpenMetadata starts or is recreated with the new SMTP configuration.

- [x] **Step 6: Verify runtime health and accessibility**

Run:

```powershell
docker compose -f docker-compose-postgres.yml ps mailpit openmetadata-server
curl.exe --fail http://localhost:8025/readyz
curl.exe --fail http://localhost:8586/healthcheck
docker compose -f docker-compose-postgres.yml exec -T openmetadata-server printenv SMTP_SERVER_ENDPOINT SMTP_SERVER_PORT SMTP_SERVER_STRATEGY AUTHORIZER_ENABLE_SMTP
```

Expected: both containers report healthy; both HTTP checks succeed; container values are `mailpit`, `1025`, `SMTP`, and `true`.

- [x] **Step 7: Commit the integration**

```powershell
git add docker-compose-postgres.yml docs/superpowers/plans/2026-10-24-mailpit-openmetadata-integration.md
git commit -m "feat: integrate Mailpit with OpenMetadata"
```
