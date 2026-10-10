# TraceShop

> After the situation changes, the Agent re-researches and creates a new proposal; the host approves, the app saves a local purchase draft, and the Agent independently reads it back.

TraceShop is an **OctoScript / Splash** app ([`bundle/main.splash`](bundle/main.splash)). It turns shopping decisions grounded in catalog facts into confirmable, checkable steps: the Agent reads status, researches candidates, creates a proposal, then **requests host approval** before saving. Only after approval does it write a local draft into the host's private storage, and the Agent independently reads it back to verify the fields. UI buttons and the six declared app tools share one research/proposal/save core; there are no two parallel flows.

The catalog contains **14 synthetic USD products**; saving writes a local draft into the host's private storage and there are **no real orders, payments or shipping**.

## Quick look for reviewers

- **Problem**: make a purchase suggestion a verifiable action, not just a natural-language conclusion. Candidates and proposals show raw catalog fields, separating "documented by this catalog" from "not documented yet".
- **Agent autonomy scope**: a real MiniMax-M3 autonomously reads status, researches candidates, creates a proposal, requests saving, reads the draft back and writes the final summary. **Saving cannot be auto-approved** — it requires a host `Approve once`.
- **Latest demo**: after a requote from 12.99 to 14.94 USD, the manually created old proposal's confirmation is rejected and **no draft is written**; the user explicitly hands the task back to the Agent, which re-researches, creates a new proposal, and after a new host approval saves and reads back. See [run 197305 evidence](evidence/agent-run-197305.json).
- **Boundaries**: a single verified case only; the callback timeout and authorization-retry root cause are unfixed; not all six tools were individually tested; the synthetic catalog has no real commerce and no native Project A integration.

## Core loop

1. Need + USD budget + hard keywords → deterministic rule-based retrieval, up to 3 candidates with raw field evidence.
2. Select a candidate → a **pending proposal** bound to research revision, merchant version and request snapshot (no draft written).
3. The Agent calls `shopping.draft.save` to request host approval: `risk=destructive`, `confirm=host`, not auto-approvable; calling the tool is not user approval.
4. Only after approval is the draft written, then an independent `shopping.draft.read` verifies the fields.
5. A price, need or version change invalidates the old proposal; saved drafts are restored from private storage after restart.

## Latest verified evidence (MiniMax-M3, run 197305)

On **unmodified** official OctoSense Linux 0.1.0-rc.1 (isolated private Store install), a real CN MiniMax-M3 ran autonomously:

- The scenario starts from a manually created **pending old proposal** (12.99 USD); after the quote changed to **14.94 USD**, the old confirmation was **rejected with no draft written** (`stale_confirmation_rejected_no_draft=true`).
- The user explicitly handed the task back to the Agent, which autonomously ran `status.read → catalog.research → proposal.create`, then after a host **Approve once** ran `draft.save → draft.read → final`.
- 6 model requests, 5 tool calls; `readback_ok=true`, and the **8 saved draft fields matched the proposal**. No draft existed before approval; it was written only after approval.
- Selected item4 **VicTsing Wireless Mouse at 14.94 USD**, budget remaining **15.06**; `draft_id=d-p-1791648896-2`, `proposal_id=p-1791648896-2`, `revision=2`, `research_revision=2`, `merchant_version=2`.
- Quiet evidence comes from raw catalog fields `description="Quiet..."` and `features="Silent click"` (`documented`); the other two candidates are `not_documented`, which only means **not documented by this demo catalog**, not that the products lack quiet operation.
- The final text's prices match the raw catalog prices (`prices_correct_in_this_run=true`); the synced task history text is **verbatim identical** to the upstream provider final, and the task was **explicitly ended**.
- The source and compact UI were both verified in this same 197305 run.

## Demo media

[94-second native recording excerpt](evidence/native-agent-excerpt-197305.mp4) · [Chinese subtitles](evidence/native-agent-excerpt-197305.zh-CN.srt) · [Media provenance](evidence/native-agent-media-197305.json).

All media comes from run 197305. The continuous source (368.169 seconds, 368 frames, zero capture errors) remains in the private cluster report. This repository includes a 94-second excerpt with waits removed and the complete app window cropped, including native permission dialogs. No generated frames or audio.

A test controller automates the initial UI proposal and explicitly clicks native authorization and save approval. MiniMax autonomously performs the new research, selection, proposal, save request and independent readback. Neither the application nor the execution model automatically approves saving.

| Changed conditions | Native Approve once |
| --- | --- |
| ![Changed conditions](bundle/screenshots/01-changed.png) | ![Native approval](bundle/screenshots/02-host-approval.png) |

[Independent readback](bundle/screenshots/03-readback.png) · [Final completion](bundle/screenshots/04-complete.png). All four screenshots are pixel-identical crops of the same run's native captures.

The earlier manual UI recording and model run 196923 remain historical material.


## Known limitations

- **Single case**: verified only on one real-model case (office wireless mouse, quiet, USD budget); this is not a claim that all paths or 100% of the app are Agent-operable.
- **Host limits remain**: the 60-second callback timeout is still present; the real final was recovered by explicitly syncing this task's history, which carries no turn terminal state, so the user still has to **end the task explicitly**. The timing root cause of retrying immediately after first authorization is **not root-caused**.
- **Not all tested**: the budget-13 scenario and all six tools were not individually tested; this sequence called 5 tools, `proposal.read` was not called separately.
- **No real commerce/upstream**: the catalog is 14 synthetic USD products with no real product/retrieval service or native Project A integration, and no real orders, payments or shipping.
- **Development bundle checked**: official job 197371 passed stamp/check --allow-unsigned; all ten bundle files match the [check record](evidence/bundle-check-replan.json). This is unsigned and does not establish production signing, release publication or App Hub admission.

## Usage

1. Enter a need, USD budget and hard keywords, or use an office/gaming/portable preset.
2. Research/select/confirm manually, or click "hand the purchase draft to the Agent" to delegate to the host Agent.
3. An Agent save triggers host confirmation; the draft is written only after approval.
4. Inspect the draft readback; after a price change, research and propose again.

Requires an OctoSense host supporting `script-tools-v1` / `app_tools.dispatch@1`. The app requests no `net` and holds no model API keys; the model service is configured by the host. See [reproducing](docs/REPRODUCING.md).

## Status

- Public repository: [prettygirlisnotme/TraceShop](https://github.com/prettygirlisnotme/TraceShop); this working tree is **not yet pushed**.
- App Hub submission: [OctoSense-App-Hub #71](https://github.com/OctoSense-org/OctoSense-App-Hub/issues/71). Listing, review and award status are per those pages.
- This repository contains the editable development bundle. Sealed packages, GitHub proof and release receipts are provided as Release assets; App Hub admission remains a separate review.

See the [Chinese README](README.md), [validation](docs/VALIDATION.md), [privacy policy](PRIVACY.md) and [license](LICENSE).
