# Mailpit and OpenMetadata Integration Design

## Goal

Add a persistent local email-capture service to the existing Docker Compose deployment so OpenMetadata notification, invitation, and password-reset workflows can be tested without delivering email externally.

## Architecture

Mailpit will run as another service in `docker-compose-postgres.yml` on the existing `app_net` Docker network. OpenMetadata will send plain SMTP traffic to `mailpit:1025`. Mailpit will store captured messages in a SQLite database at `/data/mailpit.db`, backed by a Docker-managed named volume.

The Mailpit web interface will be available to the local machine at `http://localhost:8025`. Its published port will bind only to `127.0.0.1`. SMTP port 1025 will be exposed to other Compose services but will not be published to the host.

## Components and Configuration

### Mailpit service

- Image: `axllent/mailpit:v1.27`, using a stable minor release tag that receives patch updates.
- Container name: `mailpit`.
- Restart policy: `unless-stopped`.
- Persistent database: `MP_DATABASE=/data/mailpit.db`.
- Named volume: `mailpit-data:/data`.
- Web UI: `127.0.0.1:8025:8025`.
- Internal SMTP endpoint: port 1025 on `app_net`.
- Health check: Mailpit's HTTP readiness endpoint on port 8025.

### OpenMetadata server

The existing email configuration will retain environment-variable overrides while gaining local-development defaults:

- SMTP enabled by default.
- Public OpenMetadata URL: `http://localhost:8585`.
- Sender: `openmetadata@example.test`.
- SMTP endpoint: `mailpit`.
- SMTP port: `1025`.
- Username and password: empty.
- SMTP strategy: plain `SMTP`, because transport remains inside the local Docker network.

`openmetadata-server` will depend on Mailpit reaching a healthy state before it starts.

## Data Flow

1. An OpenMetadata workflow creates an email addressed to a test user.
2. OpenMetadata connects to `mailpit:1025` over the private Compose network.
3. Mailpit accepts the message without authentication and writes it to `/data/mailpit.db`.
4. The tester opens `http://localhost:8025` and inspects the message.
5. The named volume preserves captured messages when containers are recreated or restarted.

## Safety and Scope

- Mailpit will not relay captured mail to external SMTP servers.
- The UI is accessible only through the local loopback interface.
- Test recipients should use reserved addresses such as `alice@example.test`.
- This change does not create OpenMetadata users or trigger notification workflows.
- This change does not add authentication to Mailpit because the UI is loopback-only and intended for one local developer.

## Verification

1. Run `docker compose -f docker-compose-postgres.yml config` to validate interpolation and structure.
2. Pull and start Mailpit and restart OpenMetadata with the new configuration.
3. Verify Mailpit is healthy and its UI responds on `http://localhost:8025`.
4. Verify OpenMetadata is healthy on its existing health endpoint.
5. Inspect the running OpenMetadata container configuration to confirm it resolves the expected Mailpit SMTP settings.

End-to-end notification delivery is left for the user workflow test, because creating users or triggering notifications changes application data beyond this infrastructure integration.
