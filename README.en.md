# TraceShop

> Evidence-based personal purchasing decisions that handle changing conditions: research → evidence → constraints → approval → execution → readback.

TraceShop is an **OctoScript / Splash** app whose single canonical entry point is [`bundle/`](bundle/). It breaks one purchasing decision into checkable, traceable steps: the Agent reads status, researches candidates and creates a proposal; **saving requires host approval**, writes a local draft into the host's private storage, and then the Agent independently reads it back with `draft.read`. The UI buttons and the seven declared app tools share one research/proposal/save core; there are no two parallel flows.

The catalog is demo data, the draft is written to host-private storage, and there are **no real orders, payments or shipping**.

## Why shopping

Shopping carries three threads naturally: **retrieval** (find candidates under constraints), **recommendation/evidence** (why a candidate fits) and **confirmable execution** (a person must approve before anything is written). TraceShop covers exactly this narrow, complete chain and leaves verifiable evidence at every step:

- budget and hard keywords are hard constraints, **not automatically relaxed, deleted or replaced by a soft preference, and they update only when the user explicitly changes them**;
- soft preferences (quiet/gaming/portable) count only literal catalog-field evidence; `not_documented` means "this catalog has not verified it", not that the item lacks the feature;
- candidates and read-only alternatives are strictly separate; alternatives can never become proposals;
- saving is a consequential action: a model calling a tool is **not** user approval.

This "retrieval → evidence → constraints → approval → execution → readback" flow transfers directly to other cases that need "traceable automated decisions + human sign-off". This app does **not** implement generative search/advertising recommendation, is **not** a full-duplex Agent, and is **not** connected to AgenticOS or Jev recommendation/vector retrieval; it demonstrates only the verifiable loop above.

## Single entry point and catalog sources

- Entry: [`bundle/main.splash`](bundle/main.splash) · [`bundle/tools.json`](bundle/tools.json) · [`bundle/AGENT.md`](bundle/AGENT.md) · [`bundle/manifest.json`](bundle/manifest.json) (version **0.5.1**).
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

Capabilities integrated in 0.5.1: when the app launches a task it binds the starting conditions (`task_id` + need/budget/hard keywords/catalog source/merchant version/start research revision) to this process; write tools must carry a matching `task_id` or the call is rejected. **This binding is an app-local snapshot, not host identity authentication, and does not promise arbitrary turn isolation.** The research reply is compressed (`decision` no longer duplicates candidate checks). The UI provides a full-reply original-text page, a selection summary up front, first-screen confirmation, and independent titles that separate "Agent turn status" from "proposal business status".

## Evidence status (versions must be read separately)

| Run | Exact source | Type | Conclusion |
| --- | --- | --- | --- |
| **198242** | Candidate 0.5.1 (private test copy of this repo's `bundle/`) | RC5 manual UI, 13 checks, zero model, 2:51, Slurm CPU4 | Official unmodified Linux RC5 real Store Get/Install/Open; all existing 13 manual UI checks pass, no recording; the test copy's manifest carries Linux/test publisher/signature edits and its listing carries private-test notes, so it **does not inherit original-candidate byte acceptance** |
| **198215** | main `18647a97…`, old manifest/listing (earlier candidate) | Manual UI, 13 checks, zero model, 2:05, CPU4 | Historical old package; manifest/listing changed afterwards, so it **does not inherit package byte verification** |
| **197799** | main `fc005b81…`, AGENT `06a058…` (earlier business) | Real CN MiniMax-M3, 6 requests, 5 tools, host Approve once, 4:44, CPU4 | **Earlier-business comparison**; M240 $22.99 (budget 23, quiet) saved and independently read back, after which the AGENT text and UI summary/status changed without a model re-run |
| **198316** | Candidate 0.5.1 (private test copy of this repo's `bundle/`; source digest matches main `18647a97…` / tools `e3f0e0f5…` / AGENT `f02c135f…`) | Real CN MiniMax-M3, 6 requests, 5 tools, native Allow + host Approve once, 7:43, CPU4 | Official unmodified Linux RC5 real Store install; M240 $22.99 (budget 23, wireless, quiet with field evidence) saved and independently read back; `passed=true`, all 10 observed true, `draft.read` `matches_current_proposal=true` `scope=proposal_fields`; the 693-character real final was shown via one explicit history sync and the status was ended after an explicit end; **did not call `catalog.select`/`proposal.read`** |
| **198273** | Candidate 0.5.1 | Real CN MiniMax-M3 (historical failure, material retained) | SSH was lost while the main controller was to perform the first authorization; **no live-result, no relay requests, 0 model requests, not a pass**; the wrapper timeout was incorrectly mapped to exit0 and was corrected in 198316 |
| **197305** | main `4c3a5daa…` | Historical: synthetic-catalog "re-plan after a price change", 94-second excerpt + 4 screenshots | **Historical only**, not this package |
| 197754 / 197860 | Earlier business | Zero-model fixture / manual UI checks | Supporting partial checks |

- The current ten-file digest is in [`package-inputs.json`](package-inputs.json) (a local development digest, not an official signature).
- The official `stamp/check` job 197371 checked an older package (main `4c3a5daa…`) and **does not apply to the current candidate**; the current candidate only went through the old CLI `655114c4` (contract 1.8.0) `stamp/check --allow-unsigned` structural check, **not** the new Hub `38635915` (1.12) toolchain or GitHub attestation validation.

### RC5 compatibility validation: 198242 manual UI and 198316 real model both passed

Official OctoSense desktop RC5 was published on 2026-10-11 (source `83d356c2…`), and App Flow was renamed **OctoSense-App-Flow**. Turning capability/network declarations into **purpose disclosure** was **introduced in RC4 and continued in RC5**; device consent, account scope, manual-write approval and storage isolation remain; RC5 adds charts/Wasm and an HTTPS fix — **this app uses none of the new capabilities and does not claim the 60-second host timeout is fixed**.

- **198242** (COMPLETED 0:0, CPU4, 2:51): official unmodified Linux RC5 real Store Get/Install/Open; all existing 13 manual UI checks pass, zero model requests, no recording; only the old CLI `655114c4` (contract 1.8.0) structural check, **not** the new Hub `38635915` (1.12) toolchain or GitHub attestation validation.
- **198316** (COMPLETED 0:0, CPU4, 7:43): official unmodified Linux RC5 (`octosense_0.1.0-rc.5_amd64.deb`, `unmodified_official=true`) real Store install, real CN MiniMax-M3, unchanged nonstream-to-SSE transport adapter, 6 requests 5 tools (`status`/`research`/`proposal.create`/`draft.save`/`draft.read`); both native Allow and host Approve once were clicked by the main controller on this run's actual screen, the draft did not exist before approval and M240 $22.99 (budget 23, wireless, quiet with field evidence) was saved after approval. `live-result passed=true`, all 10 observed true, research/create/save share one `task_id`, `draft.read` `read_ok=true`/`matches_current_proposal=true`/`verification_scope=proposal_fields`; the 693-character real final was shown via one explicit history sync and the status was ended after an explicit end. **It did not call `catalog.select`/`proposal.read`, so this is not full seven-tool or all-platform coverage.**
- **198273** (historical failure, material retained): the candidate's first real M3 job; SSH was lost while the main controller was to perform the first authorization, so there is **no live-result, no relay request log and 0 model requests — not a pass**; the wrapper timeout was incorrectly mapped to Slurm exit0 and was corrected in 198316. After VPN recovery only the failure material was retrieved; do not blindly resubmit.
- The publishing workflow was updated by the main controller to the official App Flow `45174df…` template with Hub pin `38635915…`; **CI has not run and nothing is published**.

## Boundaries and known limitations

- **Native is still rules + catalog**: retrieval is a deterministic rule over the synthetic catalog plus 3 official snapshots, not full semantic understanding, and it is **not connected to a live product catalog or online retrieval service nor natively integrated with Project A**.
- **No real commerce**: no real orders, payments or shipping; the draft only writes to local private storage.
- **Limited real-model coverage**: the current candidate 198316 called 5 tools (not `catalog.select` / `proposal.read`), so it does not cover all seven tools, all platforms or all rejection paths; 197799 is kept only as an earlier-business comparison.
- **Host limits remain**: the 60-second callback timeout is still present; the real final was recovered by explicitly syncing this task's history, which carries no turn terminal state, so the user still has to end the task explicitly; the timing root cause of retrying immediately after first authorization is not root-caused.
- **Historical media**: the 94-second video (`evidence/native-agent-excerpt-197305.mp4`) and `bundle/screenshots/01–04` in this repo come from the **197305 old synthetic-catalog** flow, **not from the current candidate**; they are kept as history only.

## Usage

1. Enter a need, USD budget and hard keywords, or use a preset.
2. Research/select/confirm manually, or click "hand the purchase draft to the Agent" to delegate to the host Agent.
3. An Agent save triggers host confirmation; the draft is written only after approval.
4. After a price/condition change the old proposal cannot be saved; on the proposal page explicitly click re-plan, and the Agent re-researches, re-approves and re-verifies.

Requires a host supporting `script-tools-v1` / `app_tools.dispatch@1`. The app holds no model API keys; the model service is configured by the host. See [reproducing](docs/REPRODUCING.md).

## Release and compliance status (local, unreleased)

- Public repository: [prettygirlisnotme/TraceShop](https://github.com/prettygirlisnotme/TraceShop); this working tree is **not yet pushed**.
- App Hub submission: [OctoSense-App-Hub #71](https://github.com/OctoSense-org/OctoSense-App-Hub/issues/71); the 86/100 note there is a **historical preliminary-round review**, not for the current version.
- Everything in this directory (including `bundle/`, the historical screenshots and the historical video) **stays local**; no push/tag/Release/comment. This round's formal submission materials are on hold and need separate approval.

## Documents

| File | Purpose |
| --- | --- |
| [main.splash](bundle/main.splash) | UI, shared research/proposal/save core, task binding and restore |
| [tools.json](bundle/tools.json) · [AGENT.md](bundle/AGENT.md) | Seven tool definitions / ordering, evidence, confirmation and failure semantics |
| [VALIDATION.md](docs/VALIDATION.md) | Exact versions, CPU locations, manual UI vs real Agent vs external effect |
| [REPRODUCING.md](docs/REPRODUCING.md) | Reproduction environment and command boundaries |
| [HANDOFF.md](docs/HANDOFF.md) | Developer handoff and release boundaries |
| [DEMO.zh-CN.md](docs/DEMO.zh-CN.md) | Three-minute talk script and FAQ (Chinese) |
| [DEVELOPMENT.md](docs/DEVELOPMENT.md) | Development notes and historical web prototype |
| [SUBMISSION.md](SUBMISSION.md) · [PRIVACY.md](PRIVACY.md) | Submission draft / privacy notice |

[Chinese README](README.md) · [Apache-2.0](LICENSE). Publisher: TraceShop-Felix. Support: [GitHub Issues](https://github.com/prettygirlisnotme/TraceShop/issues).
