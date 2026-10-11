# TraceShop

> Evidence-based personal purchasing decisions that handle changing conditions: research → evidence → constraints → approval → execution → readback.

TraceShop is an **OctoScript / Splash** app whose single canonical entry point is [`bundle/`](bundle/). It breaks one purchasing decision into checkable, traceable steps: the Agent reads status, researches candidates and creates a proposal; **Agent-initiated saving requires host approval**, writes a local draft into the host's private storage, and then the Agent independently reads it back with `draft.read`. The UI buttons and the seven declared app tools share one research/proposal/save core; there are no two parallel flows.

The catalog is demo data, the draft is written to host-private storage, and there are **no real orders, payments or shipping**.

## Why shopping

Shopping carries three threads naturally: **retrieval** (find candidates under constraints), **recommendation/evidence** (why a candidate fits) and **confirmable execution** (a person must approve before anything is written). TraceShop covers exactly this narrow, complete chain and leaves verifiable evidence at every step:

- budget and hard keywords are hard constraints, **not automatically relaxed, deleted or replaced by a soft preference, and they update only when the user explicitly changes them**;
- soft preferences (quiet/gaming/portable) count only literal catalog-field evidence; `not_documented` means "this catalog has not verified it", not that the item lacks the feature;
- candidates and read-only alternatives are strictly separate; alternatives can never become proposals;
- saving is a consequential action: a model calling a tool is **not** user approval.

This "retrieval → evidence → constraints → approval → execution → readback" flow transfers directly to other cases that need "traceable automated decisions + human sign-off". This app does **not** implement generative search/advertising recommendation, is **not** a full-duplex Agent, and is **not** connected to AgenticOS or Jev recommendation/vector retrieval; it demonstrates only the verifiable loop above.

## Single entry point and catalog sources

- Entry: [`bundle/main.splash`](bundle/main.splash) · [`bundle/tools.json`](bundle/tools.json) · [`bundle/AGENT.md`](bundle/AGENT.md) · [`bundle/manifest.json`](bundle/manifest.json) (version **0.5.2**).
- Catalog sources (switched in-session via `shopping.catalog.select`):
  - `synthetic_demo` (default): 14 purely fictional USD demo items.
  - `official_snapshot`: 3 manually checked official-page price snapshots (US/USD). They are a **curated summary, not verbatim page text**; **not real-time**; **item price only**, with **shipping, tax and delivery unverified** and stock not guaranteed. The snapshots are embedded in the script and the program **does no network fetching at runtime**; `net` only discloses the existing source URLs per official rules.
- Historical/reusable code: [`shop_agent/`](shop_agent/) (v0.3.0 web prototype), [`native/agent-review/`](native/agent-review/) (old Rinx review package), [`vendor/project_a/`](vendor/project_a/). They are **not** this app's entry point; they are kept for learning and reuse.

## Core loop (seven app tools)

1. `shopping.status.read`: read state, catalog source and the local task-binding summary.
2. `shopping.catalog.select`: switch between the two fixed sources; a switch increments `merchant_version` and clears prior research/selection/simulation, while an old pending proposal stays displayed but is rejected by the version guard on save.
3. `shopping.catalog.research`: rule-based retrieval, up to 3 candidates with raw field evidence; **every result (including failures)** carries a deterministic `decision` (`state`/`request`/`alternatives`/`clarification_required`/`question`), and read-only alternatives have `currently_eligible=false` and cannot be turned into proposals.
4. `shopping.proposal.create`: create a pending proposal for one candidate, binding research revision, merchant version and request snapshot, and store the structured `selection_record` (selection-basis snapshot).
5. `shopping.proposal.read`: read the current pending proposal.
6. `shopping.draft.save`: `risk=destructive`, `confirm=host`, not auto-approvable; after host approval it writes the draft and **immediately reads it back** (`readback_ok`).
7. `shopping.draft.read`: independently read the draft and report `read_ok`, `current_proposal_present`, `matches_current_proposal` and `verification_scope` separately.

Capabilities inherited from 0.5.1: when the app launches a task it binds the starting conditions (`task_id` + need/budget/hard keywords/catalog source/merchant version/start research revision) to this process; write tools must carry a matching `task_id` or the call is rejected. **This binding is an app-local snapshot, not host identity authentication, and does not promise arbitrary turn isolation.** The research reply is compressed (`decision` no longer duplicates candidate checks). The UI provides a full-reply original-text page, a selection summary up front, first-screen confirmation, and independent titles that separate "Agent turn status" from "proposal business status".

The only 0.5.2 increment is a "budget trade-off $20" button (`fill_quote_tradeoff`) on the `bundle/main.splash` first screen: selecting it switches to the 3 official price snapshots and pre-fills "office wireless mouse, quiet / $20 budget / wireless required", making the budget-vs-soft-preference trade-off directly visible. **The button only prepares input — it does not auto-research, launch the Agent, create a proposal or save**, and reuses the existing catalog-switch and research/save core; if an Agent task is running it returns a notice first. Quiet is a soft preference and wireless is a hard keyword; clicking the button is not user approval of an item or of saving. Apart from this button, the tools/schema/AGENT/algorithms/images/video in this version are identical to the 0.5.1 baseline.

## Observed runs

| Source | Evidence | Observed scope |
| --- | --- | --- |
| Main used by 0.5.2: `7e0c08e1…` | [198377](evidence/rc5-onboarding-198377/README.md), official Linux RC5, CPU4, 65 seconds | One first-use flow, 22 checks; budget $20 → explicit user edit to $23 → M240 selection and visible confirmation. Zero model calls, no save, no new video |
| 0.5.1 baseline main `18647a97…` | 198242 manual UI; [198316 real M3](evidence/rc5-agent-198316/) | 13 UI checks; separately, one task with six M3 requests, five tool types, host-approved save and independent readback |
| Historical run 197305 | Existing 94-second video and four screenshots | Earlier synthetic-catalog workflow; historical media |

198377 used the exact business main now included here, with private Linux publisher/signing metadata and manifest version 0.5.1. This integration changes the package metadata to 0.5.2; **the final ten-file package has not undergone an official publishing check**. The old Hub CLI1.8 log belongs to the test copy; the publishing workflow pins Hub1.12 and has not run. See [package-inputs](package-inputs.json) and [VALIDATION](docs/VALIDATION.md) for exact versions and retained failures.

M3 was not re-run on the new main; its evidence remains scoped to 0.5.1. The preset's active-Agent guard has been reviewed but not dynamically exercised. The host's 60-second callback limit remains; a real task may need explicit reply synchronization and an explicit end. Native research currently uses rules over a fixed catalog; Project A integration and recommendation-quality evaluation remain separate work.

## Usage

1. Enter a need, USD budget and hard keywords, or use a preset; you can also click the first-screen "budget trade-off $20" button to pre-fill an official-snapshot example (it only fills conditions — no research, no save).
2. Research/select/confirm manually, or click "hand the purchase draft to the Agent" to delegate to the host Agent.
3. An Agent save triggers host confirmation; the draft is written only after approval.
4. After a price/condition change the old proposal cannot be saved; on the proposal page explicitly click re-plan, and the Agent re-researches, re-approves and re-verifies.

Requires a host supporting `script-tools-v1` / `app_tools.dispatch@1`. The app holds no model API keys; the model service is configured by the host. See [reproducing](docs/REPRODUCING.md).

## Release and compliance status (local, unreleased)

- Public repository: [prettygirlisnotme/TraceShop](https://github.com/prettygirlisnotme/TraceShop); this working tree is **not yet pushed**.
- App Hub submission: [OctoSense-App-Hub #71](https://github.com/OctoSense-org/OctoSense-App-Hub/issues/71); the 86/100 note there is a **historical preliminary-round review**, not for the current version.
- This candidate has not been pushed, tagged, released or submitted to App Hub. Historical media was already public with an older version and retains that scope. New formal recording and talk materials remain deferred; external publishing requires approval for the specific action.

## Documents

| File | Purpose |
| --- | --- |
| [main.splash](bundle/main.splash) | UI, shared research/proposal/save core, task binding and restore |
| [tools.json](bundle/tools.json) · [AGENT.md](bundle/AGENT.md) | Seven tool definitions / ordering, evidence, confirmation and failure semantics |
| [VALIDATION.md](docs/VALIDATION.md) | Exact versions, CPU locations, manual UI vs real Agent vs external effect |
| [REPRODUCING.md](docs/REPRODUCING.md) | Reproduction environment and command boundaries |
| [HANDOFF.md](docs/HANDOFF.md) | Developer handoff and release boundaries |
| [DEMO.zh-CN.md](docs/DEMO.zh-CN.md) | Existing outline and FAQ; no finalized new-version talk |
| [DEVELOPMENT.md](docs/DEVELOPMENT.md) | Development notes and historical web prototype |
| [SUBMISSION.md](SUBMISSION.md) · [PRIVACY.md](PRIVACY.md) | Submission draft / privacy notice |

[Chinese README](README.md) · [Apache-2.0](LICENSE). Publisher: TraceShop-Felix. Support: [GitHub Issues](https://github.com/prettygirlisnotme/TraceShop/issues).
