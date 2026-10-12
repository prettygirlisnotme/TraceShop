# TraceShop — private 0.5.4 candidate

[简体中文](README.md) · English

TraceShop is an OctoScript/Splash purchasing decision app. Its canonical entry is
[bundle/](bundle/). The Agent researches a small catalog, creates a proposal,
requests native host approval, saves a local purchasing draft and independently
reads it back. No actual order, payment or shipping takes place.

If the original budget yields no eligible candidate, the Agent can request
shopping.task.budget.set. Native approval changes only the task budget, retains
the initial budget and invalidates prior research. The Agent must research again;
saving needs separate native approval. A tool request is never user approval.
The one-request limit is Agent policy, not a hard counter limit in the handler.

## Eight application tools

- shopping.status.read — current state and local task binding.
- shopping.catalog.select — select one of two embedded catalog sources.
- shopping.catalog.research — rules-based research with evidence and separate alternatives.
- shopping.proposal.create — propose only from fresh research.
- shopping.proposal.read — inspect the current proposal.
- shopping.draft.save — host-confirmed local write and immediate readback.
- shopping.draft.read — independently inspect the stored draft.
- shopping.task.budget.set — host-confirmed budget revision and forced fresh research.

The app binds task ID, inputs, catalog and merchant/research versions. This is a
local application snapshot, not host identity authentication. Stale inputs,
old budgets and proposals without fresh research are rejected.

## Sources and evidence

The default source has 14 synthetic USD demo products. The alternative has
3 curated official-page snapshots: historical US item prices only, not live
inventory, tax, shipping or delivery guarantees. Literal matching is not
general semantic understanding. not_documented means unverified in this catalog.

The main script, tools and Agent instructions exactly match the tested budget
candidate. [RC5 real M3 run 199314](evidence/rc5-budget-199314/README.md)
completed 20→22.99 budget approval, new research, separate save approval and
independent readback: 8 provider requests, 7 tool calls using 6 distinct tools.
[RC6 run 199373](evidence/rc6-budget-199373/README.md) checked native compatibility
using deterministic protocol input and zero real-model calls; it did not save.

This candidate changes release metadata to 0.5.4 and matches the tested iteration
budget of 8. The final ten-file package has not been reinstalled or checked with
the current publishing toolchain. Existing screenshots and video show an
older version. No new formal media or public release has been produced.

The host's default 60-second service callback issue remains. The RC5 success
recovered the real final reply through explicit history sync and explicitly ended
the turn.

## Development and handoff

See [validation scope](docs/VALIDATION.md), [Chinese handoff](docs/HANDOFF.md)
and [development](docs/DEVELOPMENT.md). Runtime, tests and model calls stay on the
NTU cluster in CPU Slurm jobs; WSL is for editing and small results.
Project A remains read-only. Its separate research consumer, generative retrieval,
Jev, Agentic OS and full-duplex ideas are not competition dependencies.

Public pushes, tags, releases and submissions need a concrete preview and fresh
approval. This candidate remains private.
