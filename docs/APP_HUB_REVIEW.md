# TraceShop 0.4.0 — author answers to hub scan

1. **Does the app do what its name, subtitle and description claim?** Yes, within the documented synthetic catalog and local-draft scope. `research` filters by budget and required words; `pick` creates a pending proposal; `confirm_draft` writes `purchase_draft.json` and reads it back; `boot` restores the saved draft. The source explicitly says `本地采购草稿；无真实下单、支付或物流。` (local purchase draft; no real ordering, payment or logistics). The native card-host recording demonstrates these operations.

2. **Do the listing's platforms and category fit?** Category `shopping`; platform `linux`, tested with the official card-host. No macOS, Windows or mobile compatibility claim is made.

3. **Do the granted capabilities match visible actions?** `storage` is used only to save/read the purchase draft. `octos.session.open`, `octos.turn.start` and `octos.turn.interrupt` correspond to requesting and cancelling the optional host review. There is no `net` grant, no requested network host and no API key in the bundle. Optional review sends the user's request and candidate facts through the host's configured provider; this is disclosed in PRIVACY.md.

4. **Is the interface deceptive?** No. It uses TraceShop's own UI and labels the catalog as a demo, prices as USD, and the saved result as a local purchase draft. It does not imitate a system permission prompt, login, payment sheet or merchant checkout.

5. **Does source/data contain instructions to an assistant?** Yes. `review_payload` contains the application-authored read-only shopping review prompt and a requested JSON response shape. User requirements and catalog facts are supplied as input data. `adopt_suggestion` checks the source proposal/revision, merchant version, candidate membership and deadline; adoption creates another pending proposal and does not save a draft. Explicit confirmation remains required. One live MiniMax-M3 response, JSON adoption and explicit confirmation/readback have now been verified on this exact bundle in unmodified standalone Rinx. Official card-host still exercises the honest no-service behavior; the OctoSense shell path is not claimed verified.

6. **Is any wording abusive or aimed at a private individual?** No such wording or feature occurs in the application UI or its 14-item synthetic catalog. There is no identity inference or personal targeting.

7. **Route: pass, human-review or reject?** Human-review for a first unsigned submission. Core native operations and the official gate are verified; one live host review case is verified in standalone Rinx; other shells and mobile platforms remain unverified. Publisher/support/privacy fields are complete. Please assess the actual pinned bundle; this author response is not a maintainer approval.
