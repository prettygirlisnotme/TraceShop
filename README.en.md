# TraceShop purchasing assistant

[简体中文](README.md) · English

**Negotiate constraints, approve actions, verify the result.**

TraceShop is an OctoScript / Splash app for OctoSense. An Agent researches products under the user's budget and required conditions, creates a proposal, requests approval, and saves a local purchasing draft. It then reads the stored draft independently to verify what happened.

Team: **TraceShop** · Member: **TraceShop-Felix** · Track: **OctoSense shopping and logistics** · Apache-2.0

[Watch the native demonstration (112.74 seconds)](evidence/rc6-budget-202120/demo.mp4) · [Chinese subtitles](evidence/rc6-budget-202120/demo.zh-CN.srt) · [Source and scope](evidence/rc6-budget-202120/README.md)

## One task, two separate decisions

The demonstration starts with a $20 budget for an office wireless mouse, requiring both wireless and silent evidence. The catalog has no eligible candidate. The Agent requests approval to increase the budget to $22.99, researches again within the same task, and proposes the Logitech M240. Saving requires a separate native approval, followed by an independent readback.

This makes shopping a useful setting for three Agent problems: finding candidates under constraints, asking for a decision when constraints conflict, and producing an observable result. The same separation of research, approval and execution can inform other workflows, but each domain still needs its own data and rules.

See the [current demonstration](docs/DEMO.zh-CN.md), [reproduction guide](docs/REPRODUCING.md) and [validation evidence](docs/VALIDATION.md). Use the sealed assets from a successful GitHub Release for distribution; publication and App Hub status are tracked in [SUBMISSION](SUBMISSION.md).

## Eight application tools

| Tool | Purpose |
| --- | --- |
| `shopping.status.read` | Inspect current task and constraints |
| `shopping.catalog.select` | Select an embedded catalog |
| `shopping.catalog.research` | Research candidates, evidence and alternatives |
| `shopping.proposal.create` | Create a proposal from current research |
| `shopping.proposal.read` | Read the proposal and its supporting fields |
| `shopping.task.budget.set` | Request approval for a task budget change, then require fresh research |
| `shopping.draft.save` | Request separate approval and save a local draft |
| `shopping.draft.read` | Independently read and compare the stored draft |

UI actions and Agent tools share the same business logic. Budget approval does not authorize saving. Changed inputs or versions invalidate the old proposal. A missing catalog fact means unverified, not that the product lacks the feature. The one-budget-request limit is Agent policy, not a hard counter in the handler.

## Scope

- The default catalog contains 14 fictional demo items. The demonstration uses three manually curated Logitech US snapshots instead: historical item prices in USD, without live inventory, tax, shipping or delivery verification.
- Native research uses explicit catalog fields and rules. Project A models, Jev and generative recommendation research are separate and are not integrated into this app version.
- The result is a **local purchasing draft**. No order, payment or shipping takes place.
- The host manages model credentials. Real runs use MiniMax-M3; the documented transport adaptation changes delivery format, not tool arguments or results.
- The host's service callback may time out while work continues. Explicit history sync can recover the final reply; text alone does not establish that the host turn ended.

## Source and publication

The current app is [bundle/](bundle/): [main.splash](bundle/main.splash), [tools.json](bundle/tools.json), [AGENT.md](bundle/AGENT.md) and [manifest.json](bundle/manifest.json). The historical Web prototype is not its runtime entry.

Development follows the [official App Flow](https://github.com/OctoSense-org/OctoSense-App-Flow/blob/main/README.md). As checked on October 13, 2026, the latest desktop release is [RC6](https://github.com/OctoSense-org/OctoSense/releases/tag/desktop-v0.1.0-rc.6). The exact tested scope and known limits are in [VALIDATION](docs/VALIDATION.md).

The official GitHub workflow produces a sealed app and publication receipt. A successful Release does not itself grant App Hub admission. The **86/100 preliminary review** in [App Hub #71](https://github.com/OctoSense-org/OctoSense-App-Hub/issues/71) applies to historical v0.4.0, not this candidate.

[Development](docs/DEVELOPMENT.md) · [Handoff](docs/HANDOFF.md) · [Privacy](PRIVACY.md) · [License](LICENSE)
