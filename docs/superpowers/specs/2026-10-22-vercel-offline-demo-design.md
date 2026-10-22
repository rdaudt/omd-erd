# Vercel Full Offline Demo Design

## Status

Parked for possible future implementation. This document records the agreed direction; it does not authorize or include implementation work.

## Purpose

Make the ERD viewer fully demonstrable when OpenMetadata is unavailable, including on a self-contained Vercel deployment. The deployed application should prefer live OpenMetadata when it is configured and reachable, but provide the complete selector and ERD experience from clearly identified bundled demo data when it is not.

The feature extends the existing graph-only fallback. Today, service, database, and schema discovery require OpenMetadata, so a fresh session cannot reach the sample graph during an outage.

## Goals

- Deploy the React frontend and FastAPI adapter together on Vercel.
- Preserve live OpenMetadata as the preferred data source.
- Provide a complete bundled catalog path when live discovery cannot run.
- Clearly and persistently identify demo data.
- Keep the OpenMetadata host and token server-side.
- Never mix identifiers or entities from live and demo catalogs in one session.
- Allow the user to retry the live catalog without reloading the page.
- Preserve all existing read-only ERD interactions in both modes.

## Non-goals

- Persisting a user's selected mode across browser sessions.
- Synchronizing catalog mode across users or browser tabs.
- Supporting multiple demo services, databases, or schemas.
- Editing either live or demo metadata.
- Treating demo data as a cache of the user's live catalog.
- Providing production availability guarantees for OpenMetadata access.
- Replacing the OpenMetadata SDK with a custom REST client as part of this feature.

## Selected approach

Use two interchangeable catalog providers behind the existing FastAPI API boundary:

- `OpenMetadataCatalogProvider` reads the configured OpenMetadata instance.
- `DemoCatalogProvider` reads a bundled, internally consistent demo catalog.

The browser owns the current catalog mode for its session. API responses identify their source, and requests made after entering demo mode explicitly select the demo provider. This works with stateless Vercel functions and avoids relying on server-side session affinity.

The selected approach retains the current Python mapping and test investment. Before feature implementation begins, a time-boxed deployment feasibility check must prove that the current OpenMetadata SDK and its dependencies fit within the Vercel Python function's supported bundle, memory, startup, and execution limits. Failure of that check stops implementation and triggers a separate design decision about a lightweight live provider; it must not silently create two backend implementations.

## Catalog contract

The four existing workflows remain:

- list database services;
- list databases for a service;
- list schemas for a database;
- load a schema graph.

Catalog-list responses change from a bare array to an envelope:

```json
{
  "source": "live",
  "reason": null,
  "items": [
    {
      "id": "service-id",
      "name": "Service name",
      "fullyQualifiedName": "Service name"
    }
  ]
}
```

`source` is `live` or `demo`. `reason` is absent or null for live responses. Demo responses use one safe reason code:

- `not_configured`: required OpenMetadata server configuration is absent;
- `unreachable`: connection, DNS, timeout, invalid upstream response, or retry exhaustion;
- `unauthorized`: OpenMetadata rejected the configured credentials;
- `upstream_error`: another handled OpenMetadata API failure.

The graph response retains its existing shape and changes its source vocabulary from `sample` to `demo` for consistency. It also gains the same optional `reason` field. The API never sends raw exception messages, upstream response bodies, URLs containing credentials, or tokens to the browser.

Requests accept an explicit mode parameter:

- `mode=auto` attempts the live provider and falls back to demo data on handled availability failures;
- `mode=demo` uses the demo provider without contacting OpenMetadata;
- `mode=live` attempts only the live provider and returns a controlled error if it cannot respond.

Normal startup uses `auto`. Once the frontend enters demo mode, it uses `demo`. The retry action uses `live` for its probe.

## Demo catalog

The bundled catalog contains one polished path:

```text
Demo SQL
└── AdventureWorks
    └── Sales
```

The `Sales` graph reuses and refines the existing AdventureWorks sample entities. It includes representative tables, a view, primary and foreign keys, descriptions, ownership, tiers, and relationships. The hierarchy and graph live in one fixture or one validated fixture family so their IDs cannot drift apart.

The demo provider applies the same parent validation as the live provider. Unknown service, database, and schema IDs return the same not-found behavior as their live equivalents. Demo mode therefore exercises the real cascading selector flow rather than inserting selections directly in the frontend.

## Mode and transition behavior

The frontend has three catalog states:

- `connecting`: determining whether live discovery is available;
- `live`: all catalog requests use live OpenMetadata;
- `demo`: all catalog requests use bundled demo data.

### Initial load

1. Request services with `mode=auto`.
2. If the response source is `live`, populate services and enter live mode.
3. If the response source is `demo`, populate demo services and enter demo mode.
4. All child and graph requests use the selected mode explicitly.

### Failure during a live session

If any service, database, schema, or graph request made in live mode returns a handled fallback response:

1. discard the current live graph and all live selections;
2. enter demo mode;
3. load demo services from the start of the hierarchy;
4. show an explanatory persistent banner.

The application must not attach demo children to a selected live parent or render the demo graph under a live schema label.

### Retry live catalog

The demo banner includes `Retry live catalog`. Activating it requests live services with `mode=live`:

- on success, clear demo selections and graph, enter live mode, and populate live services;
- on failure, retain the complete demo state and update the accessible status message without blanking the canvas.

A browser reload starts a new automatic attempt. Demo mode is not persisted in local storage.

## User interface

Demo mode always displays a persistent status banner. Recommended primary copy:

> Demo catalog — OpenMetadata is unavailable. You’re exploring bundled sample data.

When configuration is absent, use:

> Demo catalog — Live OpenMetadata is not configured. You’re exploring bundled sample data.

The banner contains the retry action and is exposed as an accessible status region. It remains visible while the user manipulates the graph. Demo selectors, filters, layout, pan, zoom, hide/restore, collapse/expand, selection, and inspector behavior are identical to live mode.

Technical failure details belong in server logs. The interface communicates the safe reason and a useful action without exposing credentials or internal endpoints.

## Backend structure

Introduce a provider protocol with the four catalog operations already represented by `CatalogServiceProtocol`. Both concrete providers return the same application models.

Responsibilities are separated as follows:

- The live provider owns SDK calls, pagination, normalization, live graph caching, and classification of handled upstream failures.
- The demo provider owns fixture loading, fixture validation, parent-child filtering, and demo graph responses.
- An orchestration service selects a provider based on request mode and converts handled live availability failures to demo responses only in automatic mode.
- FastAPI routes validate request identifiers and modes, serialize source envelopes, and retain the fixed read-only surface.

Unexpected programming, mapping, and fixture-validation errors propagate as server errors. They are not disguised as OpenMetadata outages. Successful live graphs may retain the current short in-process cache. Demo responses do not need runtime caching because the fixture is local and immutable.

## Vercel deployment

The target is one Vercel project containing the built Vite frontend and a Python function exposing the FastAPI application under `/api`. SPA routes resolve to the frontend, while the four fixed catalog routes resolve to FastAPI. No OpenMetadata credentials are included in the frontend bundle.

Vercel environment variables provide `OMD_HOST`, `OMD_TOKEN`, request timeout, and live graph cache TTL. When either required OpenMetadata variable is absent, automatic mode returns demo data immediately and records `not_configured`; it does not wait for a failing network request.

OpenMetadata must be reachable from Vercel over an approved network path. A private laptop or office-only OpenMetadata instance is not made reachable by this deployment. If no approved public or private connection exists, the deployed site operates as a clearly labeled demo catalog.

Request timeouts must stay below the hosting function's execution deadline and leave time to construct the demo response. The feasibility check records measured cold-start time, deployed bundle size, and first live request duration before the full feature proceeds.

## Security

- The application remains read-only and exposes no generic proxy route.
- The JWT remains in server-side Vercel configuration.
- API logs must not contain the token or authorization headers.
- Browser-visible failure reasons use the fixed safe enumeration.
- Demo data contains no copied corporate catalog metadata or credentials.
- CORS is unnecessary for the deployed same-origin frontend and API; local development retains its narrowly scoped origin configuration.
- Live OpenMetadata exposure and Vercel egress must be approved for the environment in which the deployment is used.

## Error handling

Fallback applies to missing configuration and explicitly classified OpenMetadata availability or authentication failures. Invalid client parameters retain their normal 4xx responses. Missing live catalog parents retain 404 behavior and do not trigger demo mode because a valid empty or missing entity is not an outage.

An empty live service, database, schema, or graph response remains live and empty. It must not be replaced by demo content. Malformed demo fixtures fail application startup or their first validation test rather than producing a partial demo.

If the frontend cannot reach the Vercel API itself, it shows the existing request error. It cannot claim that OpenMetadata is unavailable because no trusted API response established that fact.

## Testing strategy

### Backend unit tests

- Verify the demo hierarchy, IDs, graph, parent validation, and fixture consistency.
- Verify `auto`, `live`, and `demo` provider selection.
- Verify missing configuration enters demo mode without constructing the SDK client.
- Verify each handled upstream failure maps to the correct safe reason.
- Verify not-found and empty live results do not activate fallback.
- Verify unexpected mapping and validation errors remain visible failures.
- Verify live graph caching remains isolated from demo responses.

### API tests

- Verify list envelopes and graph source/reason fields.
- Verify a fresh session can traverse service, database, schema, and graph entirely in demo mode.
- Verify all endpoints remain GET-only and validate IDs and mode values.
- Verify response bodies never expose configured hosts, tokens, or raw upstream errors.

### Frontend tests

- Verify automatic startup into live and demo modes.
- Verify the persistent, accessible demo banner and reason-specific copy.
- Verify all demo selectors cascade through the API rather than being hard-coded.
- Verify a mid-session live failure clears incompatible state and restarts at demo services.
- Verify retry failure preserves the current demo canvas.
- Verify retry success clears demo state and presents live services.

### End-to-end tests

Run two deterministic browser scenarios:

1. a complete live traversal and ERD interaction flow;
2. a fresh load with OpenMetadata unavailable, followed by complete demo traversal, graph interaction, failed retry, and successful retry.

### Deployment verification

Deploy a preview with no OpenMetadata variables and confirm immediate demo operation. Deploy another preview with approved live credentials and confirm live operation plus controlled fallback after making the upstream deliberately unreachable. Record cold-start and request timings from both previews.

## Documentation changes

If implemented, update the README to explain:

- live, automatic, and demo behavior;
- required and optional Vercel environment variables;
- the persistent demo label;
- retry behavior;
- the fact that Vercel cannot reach a private OpenMetadata instance without an approved network path;
- preview-deployment verification and rollback instructions.

## Acceptance criteria

- A fresh Vercel deployment with no OpenMetadata configuration supports the entire selector-to-ERD demonstration.
- A configured deployment uses live OpenMetadata when reachable.
- Any handled availability failure switches the whole browser session to a coherent demo catalog.
- Demo mode is unmistakably labeled on every screen that displays catalog data.
- Retrying live data never destroys a working demo until live service discovery succeeds.
- Live and demo identifiers are never mixed.
- Secrets and raw upstream errors never reach the frontend.
- Existing ERD interactions and read-only guarantees pass in both modes.
- The Vercel feasibility check passes before feature implementation continues.
