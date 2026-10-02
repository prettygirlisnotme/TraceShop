# Privacy Notes · Shopping Decision Agent (local prototype)

This document describes what the **local web prototype** actually does with data.
It is a factual description of the shipped source, not a legal policy and not a
claim that the app is publicly hosted or certified.

## What this app is

- A loopback-only prototype. It binds `127.0.0.1` by default and is meant to be
  run on the same machine as the reviewer/host. It has no authentication and is
  **not** a public multi-user service.
- It performs no outbound network calls, no telemetry, no analytics, no account
  sign-up and no real payment. "Owner" is just a local label used to scope rows in
  the local database; it is not an identity or a login. (The separate, opt-in
  native review bundle is described below.)

## Data stored locally (SQLite)

All durable state lives in a single local SQLite file. The default path is
`shop_agent_runs/agent.sqlite3` under the project root, overridable with
`--db PATH` (for example `.local-state/demo.sqlite3`). The tables are:

- `sessions` — owner label, session id, revision, parsed requirement/state JSON,
  the user's utterance history text, `top_k`, simulated merchant version, source
  label and catalog path, and an updated timestamp.
- `proposals` — proposed item fields (title, brand, price, availability), the
  evidence and rationale used, status and expiry.
- `merchant_quotes` — **simulated** demo price/availability overrides. These are
  demo events, not real merchant facts.
- `reservations` — the "local purchase draft" rows created only after an explicit
  user confirmation (item, quantity, note, status). No order is placed.
- `events` — an append-only local action/audit log.

The browser also stores one preference key, `sdagent_owner`, in `localStorage` so
the owner label persists between page loads.

## Reference images

If the optional image path is enabled, an uploaded reference image is decoded
**in memory** for that request. Raw bytes and base64 are **not persisted**; only
the derived embedding and a SHA-256 digest are kept for the request/session. Image
context is not durable: after a server restart the session requires the image to be
re-uploaded. This is enforced in the vendored pipeline
(`vendor/project_a/online_api.py`, `raw_images_persisted: false`).

## Optional real catalog / models

- The default catalog is a small hand-authored demo fixture
  (`demo/catalog.jsonl`). It contains no real customer or catalog data.
- An optional CLIP image encoder and a learned re-ranker are only wired in when
  their local asset paths and checkpoints are supplied at launch. They are **not**
  bundled, and no real catalog data or trained weights are distributed. When
  disabled, the image-upload control stays off and text search uses the fixture.

## Optional native Agent review (separate from the web app)

The repository also contains an optional Rinx mini-app bundle,
[`native/agent-review/`](native/agent-review/). It is **not part of the local web
prototype** and the web server never loads or calls it. The distinction matters:

- **The web app makes zero outbound calls.** It does not contact any model or
  provider. The web app only ever writes the local draft after an explicit user
  confirmation.
- **The native bundle only does something when you opt in.** You must copy the
  review export out of the web app, paste it into the bundle in a Rinx host, and
  click to start a review. Only then does the host send the pasted evidence and
  query to the **provider configured inside that host**. The bundle itself stores
  no data and never contacts a provider on its own.
- The native bundle is **advisory only**: it returns text suggestions. It does not
  approve proposals, edit the catalog, relax constraints, write drafts, place
  orders, or send messages. There is no automatic approval path.
- Provider credentials and the model profile are managed by the **host profile,
  outside this app**. This app does not receive, store, or forward the key.

## No real transactions

Confirming a proposal writes a **local draft row only**. No order is created, no
payment is taken, and no merchant is contacted. "Stock" and "price changes" are
simulated demo events.

## How to delete your local data

1. Stop the server (Ctrl-C).
2. Delete the SQLite database file, e.g. `shop_agent_runs/agent.sqlite3` (also
   remove any `-wal` / `-shm` sidecar files), or delete the whole
   `shop_agent_runs/` directory.
3. Optionally clear the `sdagent_owner` key from your browser's local storage.

Deleting the database removes all sessions, proposals, simulated quotes, drafts and
events. It cannot be recovered by the app.
