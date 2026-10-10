# TraceShop

An OctoScript shopping decision app: research products from catalog facts, obtain host approval before saving, then independently read back the local purchase draft.

The main program is [`bundle/main.splash`](bundle/main.splash). Six declared app tools share the same research, proposal and save business core as the UI. The Agent can read status, research candidates, create/read a proposal, request host-approved saving, and independently read the draft back. Candidates and proposals show raw catalog fields, separating "documented by this catalog" from "not documented yet"; the latter is not evidence that a product lacks a feature.

The catalog contains **14 synthetic USD products**. Saving writes a local draft into the host's private storage; there are **no real orders, payments or shipping**.

## Verified evidence (real MiniMax-M3, run 196923)

On unmodified official OctoSense Linux 0.1.0-rc.1 (real Store Get→Install→Open), a real CN MiniMax-M3 completed `status.read → catalog.research → proposal.create → draft.save → draft.read → final` in a CPU job (196923 COMPLETED 0:0, 7m32s): 6 model requests, 5 tool calls, `readback_ok=true`, and 8 saved draft fields matched the proposal after explicit host approval. It selected item4 VicTsing Wireless Mouse at 12.99 USD (budget 30). This covers a single quiet-mouse case; it is not a claim that 100% of the app is Agent-operable.

## Known limitations

- The host has a **60-second callback timeout**; the reply was recovered by manually syncing this task's history (verbatim identical to the upstream final), but history carries no turn terminal state and the user still had to end the task explicitly.
- The retry-immediately-after-first-authorization issue is **not root-caused**.
- The original final text contains one incorrect comparative price statement; the raw reply is preserved, and field readback passing does not prove every natural-language sentence is correct. A later instruction change has **not been retested with a model**.
- Six tools are declared, five were actually called (`proposal.read` was not called separately).

## Demo video (manual UI automation)

[Native UI recording 98.96 s](evidence/native-ui-196958.mp4) · [Chinese subtitles](evidence/native-ui-196958.zh-CN.srt) · [recording summary](evidence/native-ui-196958.json).

282 continuous frames, VFR H.264, no cuts, no audio. This video is **automation of the manual UI with zero model calls**; the real-model evidence above is the separate, earlier 196923 text snapshot. The official `hub stamp/check --allow-unsigned` passed, but the preview remains unsigned and is **not a GitHub proof or App Hub admission**.

## Status

- Public repository: [prettygirlisnotme/TraceShop](https://github.com/prettygirlisnotme/TraceShop); released versions on the [Releases page](https://github.com/prettygirlisnotme/TraceShop/releases).
- App Hub submission: [OctoSense-App-Hub #71](https://github.com/OctoSense-org/OctoSense-App-Hub/issues/71). Listing, review and award status are per those pages.
- This repository contains the editable development bundle. Sealed packages, GitHub proof and release receipts are provided as Release assets; App Hub admission remains a separate review.

See the [Chinese README](README.md), [validation](docs/VALIDATION.md), [privacy policy](PRIVACY.md) and [license](LICENSE).
