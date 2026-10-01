#!/usr/bin/env python3
"""Post-generation verified-output guard policy on evidence-compare records.

Input is a RAW generated+verified records run (default: V3 job 138019; pass
--run-dir/--protocol/--job/--model to target another run, e.g. V4 job 139270) -
the raw files (records/mode_{A,B,C}.jsonl 140x3 = 420) and the fixed scenario set
are never modified. This script derives a GUARDED (audited) output where every
element must be backed by verifier evidence, and reports how much of the raw
output survives.

  1. CLAIM GUARD
     - mode B/C: keep a claim only if verifier status == "supported" AND a
       supporting citation (item_id/field that grounded it) exists. Trim its
       citations to the supporting one(s). Drop unsupported / contradicted /
       hard-constraint-violating claims and record the dropped reason.
     - mode A  : free-form baseline; keep a claim only if status == "supported"
       (verified against any candidate evidence). Cite what exists.
     After the guard, unsupported == 0 and contradicted == 0 BY CONSTRUCTION -
     this is a property of the filtering mechanism, NOT a model-quality gain.

  2. RECOMMENDATION GUARD
     - Office must satisfy the REAL hard price bound (price_usd <= query price_upper):
       the original recommendation is kept only if feasible and not violating.
     - mode C must align with the supplied deterministic trace when possible
       (recommended == trace.best_of_candidates); otherwise only a real, feasible
       AND evidence-backed candidate may be chosen.
     - If no such candidate exists -> ABSTAIN (recommended_item_id null).
     - recommendation_text is rebuilt from real catalog fields via a deterministic
       template (never free-form model prose) so the LLM gets no new place to invent facts.

  Determinism: fixed inputs, fixed order, no RNG - rerunning yields byte-identical
  JSON modulo generated_ts. CPU-only, no GPU, no Slurm, no new generation, no downloads.

Outputs:
  docs/results/shopping_evidence_guard.json   compact reserved evidence (committed)
  artifacts/shopping/evidence_guard/<outdir>/guard_{A,B,C}.jsonl   audited per-record guards
  artifacts/shopping/shopping_evidence_guard.html                  single-file page (cluster-only)
"""
import argparse
import hashlib
import json
import os
import sys
import time

_DROP_REASONS = ("unsupported", "contradicted", "hard_constraint_violation")


def sha12(path):
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()[:12]


def _rate(num, den):
    return round(num / den, 4) if den else None


def load_scenarios(path):
    payload = json.load(open(path, encoding="utf-8"))
    return {s["scenario_id"]: s for s in payload["scenarios"]}


def load_verified_records(records_dir):
    out = []
    for mode in ("A", "B", "C"):
        path = os.path.join(records_dir, "mode_%s.jsonl" % mode)
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                line = line.rstrip("\n")
                if not line:
                    continue
                rec = json.loads(line)
                ver = rec.get("verified") or {}
                out.append({"scenario_id": rec["scenario_id"], "mode": rec["mode"],
                            "raw": rec.get("record") or {}, "verified": ver})
    return out


# --------------------------------------------------------------------------- #
# Guarded claims
# --------------------------------------------------------------------------- #
def guard_claims(claims, mode):
    """Return (retained, dropped). Retained claims are trimmed to evidence that exists."""
    retained, dropped = [], []
    for c in claims:
        st = c.get("status")
        hc = bool(c.get("hard_constraint_violation"))
        if mode in ("B", "C"):
            ok = (st == "supported" and c.get("supporting_citation") is not None and not hc)
        else:
            ok = (st == "supported" and not hc)
        if ok:
            entry = {"i": c.get("i"), "text": c.get("text")}
            if mode in ("B", "C"):
                parts = c["supporting_citation"].split("/", 1)
                entry["citation"] = {"item_id": parts[0],
                                     "field": parts[1] if len(parts) > 1 else None}
                entry["supporting_citation"] = c["supporting_citation"]
            else:
                valid = [x for x in (c.get("citations") or [])
                         if x.get("item_exists") and x.get("field_valid")]
                if c.get("supporting_evidence") is not None:
                    entry["supporting_evidence_item"] = c["supporting_evidence"]
                entry["citations"] = valid
            retained.append(entry)
        else:
            dropped.append({
                "i": c.get("i"), "text": c.get("text"), "status": st,
                "reason": c.get("reason"), "contradiction": c.get("contradiction"),
                "hard_constraint_violation": hc,
            })
    return retained, dropped


# --------------------------------------------------------------------------- #
# Guarded recommendation
# --------------------------------------------------------------------------- #
def guard_decision(scenario, d, retained, mode):
    """Return guarded-recommendation dict (deterministic). d = verified decision."""
    bound = (scenario.get("query_intent") or {}).get("price_upper")
    items = {c["item_id"]: c["evidence"] for c in scenario["candidates"]}
    cand_order = [c["item_id"] for c in scenario["candidates"]]
    trace = scenario.get("decision_trace") or {}
    trace_best = trace.get("best_of_candidates")
    orig_id = d.get("recommended_item_id")
    orig_id = str(orig_id) if orig_id is not None else None
    orig_hc = bool(d.get("hard_constraint_violation"))
    orig_valid = bool(d.get("recommended_item_valid"))

    def feasible(iid):
        if iid not in items:
            return False
        if bound is not None:
            p = items[iid].get("price_usd")
            if not isinstance(p, (int, float)) or not (float(p) <= float(bound)):
                return False
        return True

    ev_items = set()
    for c in retained:
        ct = c.get("citation")
        if ct and ct.get("item_id") in items:
            ev_items.add(ct["item_id"])
        for x in c.get("citations") or []:
            if x.get("item_id") in items:
                ev_items.add(x["item_id"])
        if c.get("supporting_evidence_item") in items:
            ev_items.add(c["supporting_evidence_item"])

    feasible_count = sum(1 for iid in cand_order if feasible(iid))

    guarded_id = None
    fallback = False
    abstained = False
    reason = None

    if orig_id is not None and feasible(orig_id) and not orig_hc:
        if mode == "C" and trace_best is not None and str(orig_id) != str(trace_best):
            pass  # C prefers trace alignment -> resolved below
        else:
            guarded_id = orig_id

    if guarded_id is None:
        if mode == "C" and trace_best is not None and feasible(str(trace_best)):
            guarded_id = str(trace_best)
            fallback = True
            reason = ("original recommendation infeasible or misaligned; aligned to "
                      "supplied trace best-of-candidates")
        else:
            pool = [iid for iid in cand_order if feasible(iid) and iid in ev_items]
            if pool:
                guarded_id = pool[0]
                fallback = True
                reason = ("original recommendation infeasible or unsupported; fell back to "
                          "first feasible candidate with retained evidence")
            else:
                abstained = True
                reason = ("no feasible candidate with retained evidence "
                          + ("(price bound=%s)" % bound if bound is not None
                             else "(no price bound; no candidate with evidence)"))
                guarded_id = None

    if guarded_id is not None and guarded_id == orig_id:
        fallback = False
        reason = None

    return {
        "recommended_item_id": guarded_id,
        "recommendation_text": rec_text(scenario, guarded_id, bound),
        "abstained": abstained,
        "fallback": fallback,
        "fallback_reason": reason,
        "price_bound": bound,
        "feasible_candidate_count": feasible_count,
        "evidence_backed_candidate_count": len(ev_items),
        "original_decision": {"recommended_item_id": orig_id, "valid": orig_valid,
                              "hard_constraint_violation": orig_hc},
        "trace_best_item_id": trace_best,
        "guarded_hard_constraint_ok": not abstained,
        "guard_decision_consistent": (
            mode == "C" and not abstained and trace_best is not None
            and str(guarded_id) == str(trace_best)),
    }


def rec_text(scenario, iid, bound):
    if iid is None:
        return None
    items = {c["item_id"]: c["evidence"] for c in scenario["candidates"]}
    ev = items.get(iid) or {}
    title = (ev.get("title") or ev.get("brand") or iid)[:180]
    p = ev.get("price_usd") if isinstance(ev.get("price_usd"), (int, float)) else None
    if scenario["source"] == "office" and p is not None:
        if bound is not None:
            return "Recommended: %s - $%.2f (within budget $%.2f)" % (title, p, float(bound))
        return "Recommended: %s - $%.2f" % (title, p)
    return "Recommended: %s" % title


# --------------------------------------------------------------------------- #
# Aggregation
# --------------------------------------------------------------------------- #
def _empty_cell(src, mode):
    return {
        "source": src, "mode": mode, "n": 0,
        "raw_claims": 0, "raw_supported": 0, "raw_unsupported": 0, "raw_contradicted": 0,
        "raw_hc_claims": 0, "raw_hc_decisions": 0,
        "g_retained": 0, "g_dropped": 0, "g_dropped_unsupported": 0,
        "g_dropped_contradicted": 0, "g_dropped_hc": 0,
        "decisions_kept_original": 0, "decisions_fallback": 0, "decisions_abstain": 0,
        "guard_hc_ok": 0, "c_consistent": 0, "c_compared": 0, "dropped_reasons": {},
    }


def guard_all_records(records, scenarios_index):
    """Side-attach _guard to each record and return aggregate cells keyed 'src/mode'."""
    cells = {}
    for rec in records:
        scen = scenarios_index[rec["scenario_id"]]
        src = scen["source"]
        key = "%s/%s" % (src, rec["mode"])
        cell = cells.setdefault(key, _empty_cell(src, rec["mode"]))
        cell["n"] += 1
        claims = rec["verified"].get("claims") or []
        d = rec["verified"].get("decision") or {}
        for c in claims:
            st = c.get("status")
            cell["raw_claims"] += 1
            if st == "supported":
                cell["raw_supported"] += 1
            elif st == "contradicted":
                cell["raw_contradicted"] += 1
            else:
                cell["raw_unsupported"] += 1
            if c.get("hard_constraint_violation"):
                cell["raw_hc_claims"] += 1
        if d.get("hard_constraint_violation"):
            cell["raw_hc_decisions"] += 1
        retained, dropped = guard_claims(claims, rec["mode"])
        gd = guard_decision(scen, d, retained, rec["mode"])
        rec["_guard"] = gd
        rec["_retained"] = retained
        rec["_dropped"] = dropped
        cell["g_retained"] += len(retained)
        cell["g_dropped"] += len(dropped)
        for dd in dropped:
            rsn = dd["reason"] or dd.get("contradiction") or "dropped"
            cell["dropped_reasons"][rsn] = cell["dropped_reasons"].get(rsn, 0) + 1
            if dd["status"] == "unsupported":
                cell["g_dropped_unsupported"] += 1
            if dd["status"] == "contradicted":
                cell["g_dropped_contradicted"] += 1
            if dd["hard_constraint_violation"]:
                cell["g_dropped_hc"] += 1
        if gd["abstained"]:
            cell["decisions_abstain"] += 1
        elif gd["fallback"]:
            cell["decisions_fallback"] += 1
        else:
            cell["decisions_kept_original"] += 1
        if gd["guarded_hard_constraint_ok"]:
            cell["guard_hc_ok"] += 1
        if rec["mode"] == "C" and gd["trace_best_item_id"] is not None:
            cell["c_compared"] += 1
            if gd["guard_decision_consistent"]:
                cell["c_consistent"] += 1
    return cells


def cells_to_metrics(cells):
    metrics = {}
    for key in sorted(cells):
        c = cells[key]
        raw = c["raw_claims"] or 0
        metrics[key] = {
            "source": c["source"], "mode": c["mode"], "n_scenarios": c["n"],
            "raw_claims": raw,
            "raw_supported_claim_rate": _rate(c["raw_supported"], raw),
            "raw_unsupported_claim_rate": _rate(c["raw_unsupported"], raw),
            "raw_contradiction_rate": _rate(c["raw_contradicted"], raw),
            "raw_hard_constraint_violations": {
                "claims": c["raw_hc_claims"], "decisions": c["raw_hc_decisions"],
                "total": c["raw_hc_claims"] + c["raw_hc_decisions"]},
            "guarded_retained_claims": c["g_retained"],
            "claim_retention_rate": _rate(c["g_retained"], raw),
            "guarded_claims_per_scenario": round(c["g_retained"] / c["n"], 2) if c["n"] else None,
            "guarded_unsupported_claim_rate": 0.0,
            "guarded_contradiction_rate": 0.0,
            "guarded_dropped": {
                "total": c["g_dropped"],
                "by_unsupported": c["g_dropped_unsupported"],
                "by_contradicted": c["g_dropped_contradicted"],
                "by_hard_constraint": c["g_dropped_hc"]},
            "dropped_reason_histogram": dict(sorted(c["dropped_reasons"].items())),
            "decision": {
                "kept_original": c["decisions_kept_original"],
                "fallback": c["decisions_fallback"],
                "abstain": c["decisions_abstain"],
                "fallback_rate": _rate(c["decisions_fallback"], c["n"]),
                "abstention_rate": _rate(c["decisions_abstain"], c["n"]),
                "guarded_hard_constraint_ok_rate": _rate(c["guard_hc_ok"], c["n"])},
            "guard_decision_consistency": {
                "compared": c["c_compared"], "consistent": c["c_consistent"],
                "rate": _rate(c["c_consistent"], c["c_compared"]) if c["c_compared"] else None},
        }
        metrics[key]["guarded_citation_precision"] = (
            1.0 if c["mode"] in ("B", "C") and raw else None)
    return metrics


# --------------------------------------------------------------------------- #
# Deterministic case selection + audit dump
# --------------------------------------------------------------------------- #
def pick_cases(records):
    success = mass_drop = hard_fallback = abstain = None
    for rec in records:
        gd = rec["_guard"]
        retained = rec["_retained"]
        dropped = rec["_dropped"]
        scen = None  # filled below via lookup by caller
        raw_total = len(rec["verified"].get("claims") or [])
        if success is None and raw_total >= 2 and len(dropped) == 0 and len(retained) >= 2:
            success = rec
        elif mass_drop is None and len(dropped) >= 3:
            mass_drop = rec
        elif hard_fallback is None and gd["fallback"] and \
                gd["original_decision"]["hard_constraint_violation"]:
            hard_fallback = rec
        elif abstain is None and gd["abstained"]:
            abstain = rec
        if success and mass_drop and hard_fallback and abstain:
            break
    return {"success": success, "mass_drop": mass_drop,
            "hard_fallback": hard_fallback, "abstain": abstain}


def case_to_json(rec, scen, tag):
    items = {c["item_id"]: c["evidence"] for c in scen["candidates"]}
    gd = rec["_guard"]
    gid = gd["recommended_item_id"]
    payload = {
        "case": tag,
        "scenario_id": rec["scenario_id"], "mode": rec["mode"], "source": scen["source"],
        "query": scen.get("query"),
        "price_bound": (scen.get("query_intent") or {}).get("price_upper"),
        "retained_claims": rec["_retained"],
        "dropped_claims": [{"i": x["i"], "text": x["text"], "status": x["status"],
                            "reason": x["reason"], "hard_constraint_violation": x["hard_constraint_violation"]}
                           for x in rec["_dropped"]],
        "guarded_decision": {
            k: gd[k] for k in ("recommended_item_id", "recommendation_text", "abstained",
                               "fallback", "fallback_reason", "price_bound",
                               "guarded_hard_constraint_ok", "guard_decision_consistent",
                               "original_decision")},
        "guarded_item": None,
    }
    if gid is not None and gid in items:
        ev = items[gid]
        payload["guarded_item"] = {
            "item_id": gid, "title": (ev.get("title") or "")[:200],
            "price_usd": ev.get("price_usd"),
        }
    return payload


def write_audit_jsonl(records, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    written = []
    for mode in ("A", "B", "C"):
        path = os.path.join(out_dir, "guard_%s.jsonl" % mode)
        with open(path, "w", encoding="utf-8") as fh:
            n = 0
            for rec in records:
                if rec["mode"] != mode:
                    continue
                fh.write(json.dumps({
                    "scenario_id": rec["scenario_id"], "mode": mode,
                    "raw_claims": rec["verified"].get("n_claims"),
                    "retained_claims": rec["_retained"],
                    "dropped_claims": rec["_dropped"],
                    "decision": {k: rec["_guard"][k] for k in (
                        "recommended_item_id", "recommendation_text", "abstained",
                        "fallback", "fallback_reason", "guarded_hard_constraint_ok",
                        "guard_decision_consistent", "original_decision")},
                }, ensure_ascii=False, separators=(",", ":")) + "\n")
                n += 1
            written.append((path, n))
    return written


# --------------------------------------------------------------------------- #
# Deterministic template summary
# --------------------------------------------------------------------------- #
def build_summary_text(metrics, protocol, job, raw_results_json):
    lines = [
        "# Post-generation verified-output guard (raw -> guarded)",
        "",
        "Raw inputs: job %s %s, 420 generated+verified records (A/B/C x 140) - never "
        "modified. Guarded output keeps only verifier-supported evidence."
        % (job, protocol),
        "",
        "| source/mode | raw claims | raw unsupported rate | raw supported rate | "
        "guarded retained | claim retention | dropped | keep-orig / fallback / abstain |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for key in sorted(metrics):
        c = metrics[key]
        d = c["decision"]
        lines.append("| %s | %d | %.4f | %.4f | %d | %.4f | %d | %d / %d / %d |" % (
            key, c["raw_claims"], c["raw_unsupported_claim_rate"],
            c["raw_supported_claim_rate"], c["guarded_retained_claims"],
            c["claim_retention_rate"], c["guarded_dropped"]["total"],
            d["kept_original"], d["fallback"], d["abstain"]))
    lines.append("")
    lines.append("Decision guard: Office hard price bounds enforced on real prices; mode C "
                 "aligns to the supplied trace where feasible; otherwise the first feasible "
                 "candidate backed by retained evidence, else ABSTAIN.")
    lines.append("")
    lines.append("Construction note: guarded_unsupported=0 and guarded_contradiction=0 are "
                 "properties of the filtering mechanism (only verifier-supported evidence is "
                 "emitted), NOT a model-quality improvement. Raw job-%s numbers are "
                 "unchanged (see %s)." % (job, raw_results_json))
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# HTML page
# --------------------------------------------------------------------------- #
def _esc(x):
    if x is None:
        return ""
    return (str(x).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;"))


def _fmt_price(x):
    return ("$%.2f" % x) if isinstance(x, (int, float)) else "n/a"


def build_html(evidence, out_json):
    cases_html = []
    for c in evidence["cases"]:
        gd = c["guarded_decision"]
        kept = "".join(
            '<li class="kept"><b>%s</b>%s</li>' % (
                _esc(x.get("text", "")),
                (' <code>%s</code>' % _esc(str(x.get("citation", ""))))
                if x.get("citation") else '')
            for x in c["retained_claims"])
        dropped = "".join(
            '<li class="drop"><b>[%s]</b> %s <i>(%s)</i></li>'
            % (_esc(str(x.get("status"))), _esc(str(x.get("text", ""))),
               _esc(str(x.get("reason"))))
            for x in c["dropped_claims"])
        gitem = c.get("guarded_item")
        if gitem:
            gitem_txt = "%s - %s" % (_esc(gitem.get("title")),
                                     _fmt_price(gitem.get("price_usd")))
        else:
            gitem_txt = "ABSTAIN (no guarded candidate)"
        cases_html.append(
            '<div class="case"><h3>%s (%s) - %s</h3>'
            '<p class="q"><b>query:</b> %s</p>'
            '<p class="q"><b>price_bound:</b> %s &middot; '
            '<b>original rec id:</b> %s &middot; '
            '<b>guarded rec id:</b> %s</p>'
            '<p class="q"><b>guarded decision:</b> fallback=%s abstain=%s hc_ok=%s '
            'trace_consistent=%s</p>'
            '<p class="q"><b>recommendation:</b> %s</p>'
            '<p class="q"><b>guarded item:</b> %s</p>'
            '<p><b>retained claims</b> <small>(%d)</small></p><ul>%s</ul>'
            '<p><b>dropped claims</b> <small>(%d)</small></p><ul>%s</ul></div>'
            % (_esc(c["scenario_id"]), _esc(c["mode"]), _esc(c["source"]),
               _esc(c["query"]), _esc(gd.get("price_bound")),
               _esc((gd.get("original_decision") or {}).get("recommended_item_id")),
               _esc(gd.get("recommended_item_id")),
               bool(gd.get("fallback")), bool(gd.get("abstained")),
               bool(gd.get("guarded_hard_constraint_ok")),
               bool(gd.get("guard_decision_consistent")),
               _esc(gd.get("recommendation_text")), gitem_txt,
               len(c["retained_claims"]), kept,
               len(c["dropped_claims"]), dropped))
    table_rows = []
    for key in sorted(evidence["per_source_mode"]):
        c = evidence["per_source_mode"][key]
        d = c["decision"]
        table_rows.append(
            "<tr><td>%s</td><td>%d</td><td>%.4f</td><td>%.4f</td>"
            "<td>%d</td><td>%d</td><td>%.2f%%</td><td>%d</td>"
            "<td>%d / %d / %d</td><td>%s</td></tr>"
            % (key, c["raw_claims"], c["raw_unsupported_claim_rate"],
               c["raw_supported_claim_rate"], c["guarded_retained_claims"],
               c["raw_hard_constraint_violations"]["total"],
               (c["claim_retention_rate"] or 0) * 100.0,
               c["guarded_dropped"]["total"],
               d["kept_original"], d["fallback"], d["abstain"],
               _esc(c["guard_decision_consistency"].get("rate"))))
    html = """<!doctype html>
<html><head><meta charset="utf-8"><title>Shopping evidence guard - raw to guarded</title>
<style>
 body{font-family:ui-monospace,Menlo,Consolas,monospace;font-size:13px;margin:2rem;color:#222}
 h1{font-size:20px} h2{font-size:16px;border-bottom:1px solid #ddd;padding-bottom:4px}
 table{border-collapse:collapse;margin:1rem 0} td,th{border:1px solid #bbb;padding:4px 8px;text-align:center}
 th{background:#f0f0f0} .case{border:1px solid #ccc;border-radius:8px;padding:10px 14px;margin:12px 0}
 .q{color:#444;margin:2px 0} ul{margin:4px 0 8px 18px} .kept{color:#0a7a2f} .drop{color:#a00}
 small{color:#666} pre{background:#f6f8fa;padding:10px;border-radius:6px;white-space:pre-wrap}
</style></head><body>
<h1>Shopping research - post-generation verified-output guard (raw -> guarded)</h1>
<p><b>protocol</b> %s &middot; <b>job</b> %s &middot; <b>model</b> %s &middot;
<b>inputs</b> 140x3 = 420 raw generated+verified records, never modified</p>
<h2>Per source/mode</h2>
<table>
<tr><th>cell</th><th>raw claims</th><th>raw unsupported rate</th><th>raw supported rate</th>
<th>guarded retained</th><th>raw hc violations</th><th>claim retention</th><th>dropped</th>
<th>keep / fallback / abstain</th><th>C consistency (guarded)</th></tr>
%s
</table>
<h2>Summary (deterministic template)</h2>
<pre>%s</pre>
<h2>Cases (real evidence)</h2>
%s
<p><i>Single-file page. JSON evidence: %s (sha256 prefixes embedded).</i></p>
</body></html>""" % (
        "\n".join(table_rows), _esc(evidence["summary_text"]), "\n".join(cases_html),
        _esc(evidence["protocol"]), _esc(evidence["job"]), _esc(evidence["model"]),
        _esc(out_json))
    return html


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--scenarios",
                    default="artifacts/shopping/evidence_compare/preflight/scenarios.json")
    ap.add_argument("--records-dir", default=None,
                    help="dir with mode_{A,B,C}.jsonl (default: V3 run records)")
    ap.add_argument("--run-dir", default=None,
                    help="evidence-compare run dir containing records/; when given it "
                         "presets --records-dir=<run-dir>/records and --audit-dir default")
    ap.add_argument("--protocol", default="V3")
    ap.add_argument("--job", default="138019")
    ap.add_argument("--model", default="Qwen/Qwen2.5-1.5B-Instruct (greedy, cached, offline)")
    ap.add_argument("--raw-results-json", default="docs/results/evidence_compare_v3.json")
    ap.add_argument("--out-json", default="docs/results/shopping_evidence_guard.json")
    ap.add_argument("--out-html", default="artifacts/shopping/shopping_evidence_guard.html")
    ap.add_argument("--audit-dir", default=None)
    args = ap.parse_args(argv)

    if args.run_dir:
        if args.records_dir is None:
            args.records_dir = os.path.join(args.run_dir.rstrip("/"), "records")
        if args.audit_dir is None:
            args.audit_dir = os.path.join(
                "artifacts/shopping/evidence_guard",
                "%s_guard" % os.path.basename(args.run_dir.rstrip("/")))
    if args.records_dir is None:
        args.records_dir = ("artifacts/shopping/evidence_compare/"
                            "run_20260903_165334_2289231/records")
    if args.audit_dir is None:
        args.audit_dir = "artifacts/shopping/evidence_guard/run_v3_guard"

    scenarios_index = load_scenarios(args.scenarios)
    records = load_verified_records(args.records_dir)
    if len(records) != 420:
        print("ERROR: expected 420 records, got %d" % len(records), file=sys.stderr)
        return 1
    per = {}
    for r in records:
        per[r["mode"]] = per.get(r["mode"], 0) + 1
    print("records loaded:", per)

    for rec in records:
        if rec["scenario_id"] not in scenarios_index:
            print("ERROR: missing scenario %s" % rec["scenario_id"], file=sys.stderr)
            return 2

    cells = guard_all_records(records, scenarios_index)
    metrics = cells_to_metrics(cells)

    packed = pick_cases(records)
    cases = []
    for tag in ("success", "mass_drop", "hard_fallback", "abstain"):
        rec = packed[tag]
        if rec is not None:
            cases.append(case_to_json(rec, scenarios_index[rec["scenario_id"]], tag))

    summary = build_summary_text(metrics, args.protocol, args.job, args.raw_results_json)

    evidence = {
        "task": ("post-generation verified-output guard - evidence-guard policy on %s raw "
                 "generated+verified records" % args.protocol),
        "protocol": args.protocol, "job": args.job, "model": args.model,
        "source_records": 420,
        "records_per_mode": per,
        "raw_never_modified": True,
        "inputs_sha256_prefixes": {
            "scenarios": sha12(args.scenarios),
            "records": {m: sha12(os.path.join(args.records_dir, "mode_%s.jsonl" % m))
                        for m in ("A", "B", "C")},
        },
        "policy": {
            "claim": ("keep only verifier-supported claims with an existing supporting citation "
                      "(B/C) or candidate-evidence support (A); drop unsupported/contradicted /"
                      "hard-constraint-violating claims with recorded reason"),
            "recommendation": ("Office: real hard price bound enforced (price_usd <= price_upper); "
                               "mode C aligns to the supplied deterministic trace when feasible; "
                               "otherwise only the first feasible + evidence-backed candidate, "
                               "else ABSTAIN. recommendation_text is template-built from real "
                               "catalog fields (no LLM free-form prose)."),
        },
        "construction_note": ("guarded_unsupported=0 / guarded_contradiction=0 is a property of "
                              "the filtering mechanism (only verifier-supported evidence is "
                              "emitted), NOT a model-quality improvement; raw job-%s numbers "
                              "are unchanged." % args.job),
        "per_source_mode": metrics,
        "cases": cases,
        "summary_text": summary,
        "generated_ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    }

    os.makedirs(os.path.dirname(args.out_json), exist_ok=True)
    with open(args.out_json, "w", encoding="utf-8") as fh:
        json.dump(evidence, fh, ensure_ascii=False, indent=1)

    written = write_audit_jsonl(records, args.audit_dir)

    os.makedirs(os.path.dirname(args.out_html), exist_ok=True)
    with open(args.out_html, "w", encoding="utf-8") as fh:
        fh.write(build_html(evidence, args.out_json))

    print("EVIDENCE_GUARD_OK")
    print("JSON  ->", args.out_json)
    print("HTML  ->", args.out_html)
    for path, n in written:
        print("AUDIT ->", path, n)
    for key in sorted(metrics):
        c = metrics[key]
        d = c["decision"]
        print("  %-8s claims=%d retained=%d (%.2f%%) hc_raw=%d "
              "keep=%d fallback=%d abstain=%d" % (
                  key, c["raw_claims"], c["guarded_retained_claims"],
                  (c["claim_retention_rate"] or 0) * 100.0,
                  c["raw_hard_constraint_violations"]["total"],
                  d["kept_original"], d["fallback"], d["abstain"]))
    found = [t for t in ("success", "mass_drop", "hard_fallback", "abstain")
             if packed[t] is not None]
    print("cases found:", found)
    return 0


if __name__ == "__main__":
    sys.exit(main())