# OpenMetadata ERD Viewer Local Operations Runbook

## Scope and safety

This runbook operates the local OpenMetadata 2.0.5 stack and the ERD Viewer on Windows with PowerShell. Run commands from the repository root unless a step says otherwise.

This is a laptop/demo environment, not a production deployment. The viewer is read-only and both of its development servers bind to loopback.

The normal shutdown commands preserve Docker volumes and catalog data. A command that deletes volumes appears only in the clean-reset procedure and is marked **destructive**.

Never paste the OpenMetadata bot JWT into a URL, screenshot, source file, `VITE_*` variable, or commit. Keep it in the ignored root `.env` file or the backend process environment.

### Required software

- Windows PowerShell 5.1 or newer
- Python 3.12.10 with `venv` and pip
- Node.js 24 LTS with npm (verified with Node 24.18.0)
- Docker Desktop with Docker Compose
- A bot JWT authorized to read the OpenMetadata catalog

### Required local ports

| Port | Process | Required for normal operation |
| --- | --- | --- |
| 5432 | PostgreSQL | Yes |
| 8080 | OpenMetadata ingestion/Airflow | Yes |
| 8585 | OpenMetadata UI and API | Yes |
| 8586 | OpenMetadata admin health endpoint | Yes |
| 9200, 9300 | Elasticsearch | Yes |
| 8000 | ERD Viewer FastAPI adapter | Yes |
| 5173 | ERD Viewer Vite frontend | Yes |

## Service map and startup sequence

Use Docker Compose to start the complete OpenMetadata stack. Do not manually start the containers one at a time; Compose applies the dependency conditions declared in `docker-compose-postgres.yml`.

The effective sequence is:

1. `postgresql` and `elasticsearch` start and pass their health checks.
2. `execute-migrate-all` runs the one-time OpenMetadata database migration after both dependencies are healthy.
3. `openmetadata-server` starts after PostgreSQL and Elasticsearch are healthy and the migration exits successfully.
4. `ingestion` starts after PostgreSQL is healthy and its declared OpenMetadata and Elasticsearch dependencies have started.
5. `scripts/dev.ps1` starts the local adapter on port 8000, waits for it to accept connections, then starts the frontend on port 5173.

`execute-migrate-all` showing `Exited (0)` is a successful state. It is a one-shot job, not a server that should remain running.

## First-time setup

### 1. Create the Python environment

```powershell
py -3.12 -m venv .venv
.venv\Scripts\python.exe --version
.venv\Scripts\python.exe -m pip install -e "./backend[test]"
```

Confirm that the version command reports Python 3.12.10.

### 2. Install frontend and browser-test dependencies

```powershell
npm.cmd ci --prefix frontend
npx.cmd --prefix frontend playwright install chromium
```

Chromium is needed for the browser test suite, not for ordinary interactive use in an installed browser.

### 3. Create the local configuration

```powershell
Copy-Item -LiteralPath .env.example -Destination .env
```

Edit `.env` and set the bot JWT:

```dotenv
OMD_HOST=http://localhost:8585/api
OMD_TOKEN=replace-with-a-bot-jwt
OMD_REQUEST_TIMEOUT_SECONDS=10
OMD_CACHE_TTL_SECONDS=60
```

Replace the example token before starting the viewer. Process environment values take precedence over `.env`. Keep values simple and use either no quotes or matching single/double quotes; do not add inline comments.

## Start the application

### Normal startup

1. Start Docker Desktop and wait until its engine is ready.
2. Start the complete OpenMetadata stack:

   ```powershell
   docker compose -f docker-compose-postgres.yml up -d
   ```

3. Watch the service states:

   ```powershell
   docker compose -f docker-compose-postgres.yml ps -a
   ```

   Continue when PostgreSQL, Elasticsearch, and the OpenMetadata server are healthy; ingestion is running; and `execute-migrate-all` has exited with code 0. Initial image downloads and first startup can take several minutes.

4. Confirm OpenMetadata is ready:

   ```powershell
   Invoke-WebRequest -UseBasicParsing http://localhost:8586/healthcheck
   ```

   Expect an HTTP 200 response. You can also open <http://localhost:8585> and confirm the catalog UI loads.

5. Start the ERD Viewer in a dedicated PowerShell terminal:

   ```powershell
   powershell -NoProfile -ExecutionPolicy Bypass -File scripts/dev.ps1
   ```

   The launcher validates `.env`, dependencies, the API URL, and ports 8000/5173. Cold OpenMetadata SDK imports can make adapter startup take about a minute. Leave this terminal open while using the viewer.

6. Open <http://127.0.0.1:5173>.

### Optional separate-terminal startup

Use this only when you need to restart or debug one viewer process independently.

Terminal 1, from the repository root:

```powershell
.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
```

Terminal 2, from the repository root:

```powershell
npm.cmd run dev --prefix frontend -- --host 127.0.0.1 --port 5173 --strictPort
```

Start the adapter first. The frontend proxies `/api` calls to it; the browser never receives the OpenMetadata token or contacts OpenMetadata directly.

## Verify the application

### 1. Verify container states

```powershell
docker compose -f docker-compose-postgres.yml ps -a
```

Expected states:

| Service | Expected state |
| --- | --- |
| `postgresql` | Running and healthy |
| `elasticsearch` | Running and healthy |
| `execute-migrate-all` | Exited with code 0 |
| `openmetadata-server` | Running and healthy |
| `ingestion` | Running |

### 2. Verify the OpenMetadata health endpoint

```powershell
(Invoke-WebRequest -UseBasicParsing http://localhost:8586/healthcheck).StatusCode
```

Expected: `200`.

### 3. Verify the adapter without exposing the token

```powershell
(Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8000/openapi.json).StatusCode
```

Expected: `200`. This checks the adapter process without printing the JWT or requiring a catalog request.

### 4. Verify the frontend

```powershell
(Invoke-WebRequest -UseBasicParsing http://127.0.0.1:5173).StatusCode
```

Expected: `200`.

### 5. Perform a functional smoke check

Open <http://127.0.0.1:5173>, then select a database service, database, and schema. A neutral status and a populated diagram indicate live catalog data. A persistent **Sample data — OpenMetadata unavailable** banner means the graph request fell back to bundled sample data; investigate connectivity or authorization before treating the environment as healthy.

## Routine operation and logs

### Check status

```powershell
docker compose -f docker-compose-postgres.yml ps -a
```

The viewer launcher prints its URLs after both local processes accept connections. If either viewer process exits, the launcher stops the other process tree.

### Follow Docker logs

All OpenMetadata services:

```powershell
docker compose -f docker-compose-postgres.yml logs --tail 100 -f
```

One service:

```powershell
docker compose -f docker-compose-postgres.yml logs --tail 100 -f openmetadata-server
```

Replace `openmetadata-server` with `postgresql`, `elasticsearch`, `execute-migrate-all`, or `ingestion` as needed. Press Ctrl+C to stop following logs; this does not stop the containers.

### Inspect viewer logs

The combined launcher redirects process output under `.dev-logs/`:

- `.dev-logs/backend.out.log`
- `.dev-logs/backend.err.log`
- `.dev-logs/frontend.out.log`
- `.dev-logs/frontend.err.log`

Read the latest errors with:

```powershell
Get-Content -Tail 100 .dev-logs\backend.err.log
Get-Content -Tail 100 .dev-logs\frontend.err.log
```

The graph adapter caches successful graph responses for 60 seconds by default. A browser refresh resets UI state but may reuse cached graph data. The graph API supports `refresh=true` when a forced server-side refresh is needed.

## Stop the application

### Stop only the ERD Viewer

In the PowerShell terminal running `scripts/dev.ps1`, press Ctrl+C once. Wait for:

```text
Development servers stopped.
```

The launcher stops both owned process trees. Keep the Docker stack running if you plan to use OpenMetadata or restart the viewer shortly.

If you used the separate-terminal workflow, press Ctrl+C in the frontend terminal and then in the adapter terminal.

### Stop only the OpenMetadata stack

Stop the viewer first, then run:

```powershell
docker compose -f docker-compose-postgres.yml down
```

This removes the Compose containers and network but preserves the named volumes and local catalog data.

### Complete normal shutdown

1. Press Ctrl+C in the viewer launcher terminal and wait for its shutdown message.
2. Stop the Docker stack:

   ```powershell
   docker compose -f docker-compose-postgres.yml down
   ```

3. Optionally quit Docker Desktop after Compose finishes.

Do not close Docker Desktop or force-kill its containers before stopping the viewer and running `down` unless recovering from a failure.

## Restart and recover

### Restart only the viewer

1. Press Ctrl+C in the viewer launcher terminal.
2. Confirm ports 8000 and 5173 are no longer listening if the next launch reports a conflict:

   ```powershell
   Get-NetTCPConnection -State Listen -LocalPort 8000,5173 -ErrorAction SilentlyContinue
   ```

3. Start the launcher again:

   ```powershell
   powershell -NoProfile -ExecutionPolicy Bypass -File scripts/dev.ps1
   ```

### Restart the OpenMetadata stack while preserving data

Stop the viewer, then run:

```powershell
docker compose -f docker-compose-postgres.yml down
docker compose -f docker-compose-postgres.yml up -d
docker compose -f docker-compose-postgres.yml ps -a
```

Wait for the OpenMetadata health check before restarting the viewer.

### Restart a single unhealthy container

First inspect its logs. If a restart is appropriate:

```powershell
docker compose -f docker-compose-postgres.yml restart openmetadata-server
docker compose -f docker-compose-postgres.yml ps -a
```

Replace the service name only with one listed by:

```powershell
docker compose -f docker-compose-postgres.yml config --services
```

Restarting one dependency does not replay the full dependency sequence. For database, search, or migration problems, prefer the data-preserving full-stack restart above.

### Clean reset — destructive

**Warning: the following command deletes the named Compose volumes, including the local PostgreSQL catalog, Elasticsearch indexes, and ingestion state. This cannot be undone unless you have a separate backup.**

Stop the viewer, confirm that no local data must be retained, then run:

```powershell
docker compose -f docker-compose-postgres.yml down -v
docker compose -f docker-compose-postgres.yml up -d
```

After a clean reset, wait for migration and health checks, then re-create or re-ingest any catalog content before starting the viewer.

## Troubleshooting

| Symptom | Checks and response |
| --- | --- |
| Docker command cannot connect to the engine | Start Docker Desktop and wait until it reports that the engine is running. Retry `docker compose ... ps -a`. |
| Port is already in use | Run `Get-NetTCPConnection -State Listen -LocalPort 5432,8080,8585,8586,9200,9300,8000,5173 -ErrorAction SilentlyContinue`. Stop the known conflicting process; do not have the launcher replace an unknown listener. |
| `execute-migrate-all` exits nonzero | Read `docker compose -f docker-compose-postgres.yml logs execute-migrate-all`, plus PostgreSQL and Elasticsearch logs. Resolve the dependency or migration error, then perform a data-preserving full-stack restart. |
| OpenMetadata server is unhealthy | Check `openmetadata-server`, PostgreSQL, Elasticsearch, and migration logs. Confirm port 8586 returns HTTP 200. |
| Launcher says dependencies are missing | Repeat the relevant Python editable install or `npm.cmd ci --prefix frontend` command from First-time setup. |
| Launcher rejects `OMD_TOKEN` | Set a real authorized bot JWT in `.env`; do not leave the example value. Restart the launcher after editing the file. |
| Catalog selectors fail to load | Confirm `OMD_HOST` ends in `/api`, OpenMetadata is healthy, and the bot JWT is valid and allowed to read the catalog. Inspect `.dev-logs/backend.err.log`. |
| First viewer startup or graph is slow | Allow up to two minutes for cold SDK imports and the first lazy graph-layout load. Check both viewer error logs if a process exits. |
| Viewer shows sample data | OpenMetadata was unavailable during the graph request. Verify the health endpoint, token, and backend error log; restore connectivity and request the live schema again. |
| A relationship is missing | Confirm OpenMetadata declares the foreign key, both endpoints are in the selected schema, and the active Tables/Views/Both filter includes both entity types. |
| Viewer does not stop cleanly | Press Ctrl+C once and allow the launcher's `finally` cleanup to finish. If ports remain occupied afterward, identify the listener with `Get-NetTCPConnection` before terminating any process. |

## Quick command reference

### Start

```powershell
docker compose -f docker-compose-postgres.yml up -d
docker compose -f docker-compose-postgres.yml ps -a
Invoke-WebRequest -UseBasicParsing http://localhost:8586/healthcheck
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/dev.ps1
```

Open <http://127.0.0.1:5173> after the launcher prints the viewer URL.

### Check

```powershell
docker compose -f docker-compose-postgres.yml ps -a
(Invoke-WebRequest -UseBasicParsing http://localhost:8586/healthcheck).StatusCode
(Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8000/openapi.json).StatusCode
(Invoke-WebRequest -UseBasicParsing http://127.0.0.1:5173).StatusCode
```

### Stop without deleting data

Press Ctrl+C in the viewer launcher terminal, wait for `Development servers stopped.`, then run:

```powershell
docker compose -f docker-compose-postgres.yml down
```

