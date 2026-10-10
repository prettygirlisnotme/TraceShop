# TraceShop

An OctoScript shopping decision app: research products from catalog facts, obtain host approval before saving, then independently read back the local purchase draft.

The main program is [`bundle/main.splash`](bundle/main.splash). Six declared app tools share the same research, proposal and save business core as the UI. The Agent can read status, research candidates, create/read a proposal, request host-approved saving, and independently read the draft back. Candidates and proposals show raw catalog fields, separating "documented by this catalog" from "not documented yet"; the latter is not evidence that a product lacks a feature.

The catalog contains **14 synthetic USD products**. Saving writes a local draft into the host's private storage; there are **no real orders, payments or shipping**.

## Verified evidence (real MiniMax-M3, run 196923)

On unmodified official OctoSense Linux 0.1.0-rc.1 (real Store Get→Install→Open), a real CN MiniMax-M3 completed `status.read → catalog.research → proposal.create → draft.save → draft.read → final` in a CPU job (196923 COMPLETED 0:0, 7m32s): 6 model requests, 5 tool calls, `readback_ok=true`, and 8 saved draft fields matched the proposal after explicit host approval. It selected item4 VicTsing Wireless Mouse at 12.99 USD (budget 30). This covers a single quiet-mouse case; it is not a claim that 100% of the app is Agent-operable. The real-M3 evidence is an earlier text snapshot (tested main.splash `ed412c2c` / AGENT.md `b6f28f03`); the current business-text fix and compact UI were made afterwards and have **not been re-tested with a model**.

## Known limitations

- The host has a **60-second callback timeout**; the reply was recovered by manually syncing this task's history (verbatim identical to the upstream final), but history carries no turn terminal state and the user still had to end the task explicitly.
- The retry-immediately-after-first-authorization issue is **not root-caused**.
- The original final text contains one incorrect comparative price statement; the raw reply is preserved, and field readback passing does not prove every natural-language sentence is correct. A later instruction change has **not been retested with a model**.
- Six tools are declared, five were actually called (`proposal.read` was not called separately).

## Demo video (manual UI automation)

[Compact native UI recording 78.24 s](evidence/native-ui-197066.mp4) · [Chinese subtitles](evidence/native-ui-197066.zh-CN.srt) · [current candidate screenshot](evidence/native-candidates-197066.png) · [recording summary](evidence/native-ui-197066.json).

217 continuous frames, VFR H.264, no cuts, no audio. This video is **automation of the manual UI with zero application model calls**; the real-model evidence above is the separate, earlier 196923 text snapshot. This revision compacts the header and arranges three candidate cards side by side with independently scrolling text: within the same 990×613 window the candidate container grows from 257px to 445px (about +73%), the three selection buttons need no scrolling, and the full proposal plus its confirm button fit on one screen (current main.splash `e344068d`; business functions, six tools and AGENT instructions unchanged).

The run completed the manual UI flow (select the documented quiet product, save and read back independently, simulate a +15% requote and reject the stale confirmation without overwriting the draft) with 16 of 16 record items true. The final development bundle passed official `stamp/check --allow-unsigned` ([check](evidence/bundle-check-compact.txt), [file hashes](evidence/bundle-check-compact.json)). It is **not a GitHub proof or App Hub admission**. All four bundled screenshots and the recording come from run 197066.

[Candidates](bundle/screenshots/01-main.png) · [Full proposal and confirmation](bundle/screenshots/02-proposal.png) · [Saved draft](bundle/screenshots/03-readback.png) · [Stale proposal rejected](bundle/screenshots/04-requote.png).

## Status

- Public repository: [prettygirlisnotme/TraceShop](https://github.com/prettygirlisnotme/TraceShop); released versions on the [Releases page](https://github.com/prettygirlisnotme/TraceShop/releases).
- App Hub submission: [OctoSense-App-Hub #71](https://github.com/OctoSense-org/OctoSense-App-Hub/issues/71). Listing, review and award status are per those pages.
- This repository contains the editable development bundle. Sealed packages, GitHub proof and release receipts are provided as Release assets; App Hub admission remains a separate review.

See the [Chinese README](README.md), [validation](docs/VALIDATION.md), [privacy policy](PRIVACY.md) and [license](LICENSE).
