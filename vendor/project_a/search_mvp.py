#!/usr/bin/env python3
"""Deterministic, evidence-grounded multimodal shopping search MVP.

Reads the schema_version=1 catalog written by prepare_catalog.py
(staging/shopping/prepare_catalog.py): item_id, asin, title, brand,
price_usd, categories, features, description, technical_details, ...

Python 3.10+, stdlib only. numpy is imported lazily and is only required
when a visual route is requested (any option below that mentions an .npy
file or a visual weight > 0).

Pipeline (exact formulas documented in SHOPPING_MVP.md):
  1. intent parse   -> deterministic EN/ZH price-constraint parser
  2. hard filter    -> price constraints applied to the whole catalog
  3. lexical route  -> field-weighted BM25 -> top candidate_k
  4. visual route   -> cosine vs precomputed item embeddings (optional)
  5. fusion         -> min-max normalised lexical + visual -> top_k

Every claim in the output is backed by an exact catalog value. No
attributes are ever invented. The output is deterministic given the same
inputs.
"""
import argparse
import json
import math
import os
import re
import sys

SCHEMA_VERSION = 1

BM25_K1 = 1.5
BM25_B = 0.75

FIELD_WEIGHTS = {
    "title": 3.0,
    "brand": 1.5,
    "categories": 1.5,
    "features": 1.2,
    "description": 1.0,
    "technical_details": 1.0,
}
SEARCHABLE_FIELDS = tuple(FIELD_WEIGHTS)

TOKEN_RE = re.compile(r"[\w]+", re.UNICODE)

_NUM = r"(?:\d[\d,]*(?:\.\d+)?)"
_CURW = r"(?:¥|人民币|元|美元|美金|RMB|CNY|USD|\$|dollars?|yuan|us\s*dollars?)"

_EN_LE = r"\b(?:under|below|within|at\s+most|no\s+more\s+than|up\s+to|budget\s+(?:of\s+)?|max)\b"
_EN_GE = r"\b(?:over|above|at\s+least|no\s+less\s+than|min)\b"
_CN_LE = r"(?:不超过|以内|预算)"
_CN_GE = r"(?:至少)"
_OP = rf"(?:(?P<le>{_EN_LE}|{_CN_LE}|<=|≤)|(?P<ge>{_EN_GE}|{_CN_GE}|>=|≥))"

# Range: "between A and B", "from A to B", "A to B", "A到B", "A至B", "A-B"
RE_EN_RANGE = re.compile(
    rf"(?:from\s+|between\s*)?(?P<lo>{_NUM})\s*(?:and|,|to)\s*(?P<hi>{_NUM})\s*(?P<cur>{_CURW})?", re.I
)
RE_CN_RANGE = re.compile(
    rf"(?P<lo>{_NUM})\s*(?P<curlo>{_CURW})?\s*(?:到|至|~|-)\s*(?P<hi>{_NUM})\s*(?P<cur>{_CURW})?", re.I
)
# Single bound, operator first: "under 30 dollars", "100元以内" handled below
RE_LEAD = re.compile(
    rf"(?P<op>{_OP})\s*(?P<cur1>{_CURW})?\s*(?P<num>{_NUM})\s*(?P<cur2>{_CURW})?", re.I
)
# Single bound, amount first: "100元以内", "30 dollars or less", "至少50元"
RE_AFTER_LE = re.compile(
    rf"(?P<num>{_NUM})\s*(?P<cur>{_CURW})?\s*(?P<kw>or\s+less|or\s+under|or\s+below|以下|以内)", re.I
)
RE_AFTER_GE = re.compile(
    rf"(?P<num>{_NUM})\s*(?P<cur>{_CURW})?\s*(?P<kw>or\s+more|or\s+above|至少|以上)", re.I
)


def tokenize(text):
    if not text:
        return []
    text = re.sub(r",", "", text)
    return [t for t in TOKEN_RE.findall(text.casefold()) if t]


def _currency_of(text):
    if text and re.search(r"美元|美金|\$|\bdollars?\b|usd|\bus\s*dollars?\b", text, re.I):
        return "USD"  # 美元 = "US dollar"; must win over the trailing 元 in CNY check below
    if text and re.search(r"¥|人民币|\byuan\b|元|rmb", text, re.I):
        return "CNY"
    return None


def _num_value(raw):
    return float(raw.replace(",", ""))


def parse_price_constraints(query):
    """Deterministic EN/ZH price-intent parser.

    Returns a list of mentions; duplicate mentions that express the same
    bound are collapsed to the first occurrence.
    """
    mentions = []
    work = str(query or "")

    for rx in (RE_EN_RANGE, RE_CN_RANGE):
        for m in rx.finditer(work):
            grp = m.groupdict()
            cur = _currency_of((grp.get("curlo") or "") + " " + (grp.get("cur") or ""))
            mentions.append({
                "type": "range", "raw": m.group(0).strip(),
                "lo": _num_value(m.group("lo")), "hi": _num_value(m.group("hi")),
                "currency": cur or "USD",
            })
        work = rx.sub(" ", work)

    for rx, kind in ((RE_LEAD, None), (RE_AFTER_LE, "le"), (RE_AFTER_GE, "ge")):
        for m in rx.finditer(work):
            if kind is None:
                kind = "le" if m.group("le") else "ge"
            if not m.group("num"):
                continue
            grp = m.groupdict()
            cur = _currency_of((grp.get("cur1") or "") + " " + (grp.get("cur2") or grp.get("cur") or ""))
            mentions.append({
                "type": kind, "raw": m.group(0).strip(),
                "amount": _num_value(m.group("num")), "currency": cur or "USD",
            })

    # collapse duplicates that express the same numeric bound
    out, seen = [], set()
    for m in mentions:
        key = (m["type"],
               ("range", round(m["lo"], 6), round(m["hi"], 6))
               if m["type"] == "range" else ("bound", round(m["amount"], 6)),
               m["currency"])
        if key in seen:
            continue
        seen.add(key)
        out.append(m)
    return out


def intent_price(query, cny_to_usd_rate=None):
    mentions = parse_price_constraints(query)
    if not mentions:
        return {"detected_mentions": [], "applied": False,
                "effective": {"lower": None, "upper": None},
                "currency_mismatch": False,
                "conversion": {"cny_to_usd_rate": None, "converted": False},
                "warning": None}
    cny_mentions = [m for m in mentions if m["currency"] == "CNY"]
    if cny_mentions and not cny_to_usd_rate:
        return {
            "detected_mentions": mentions,
            "applied": False,
            "effective": {"lower": None, "upper": None},
            "currency_mismatch": True,
            "conversion": {"cny_to_usd_rate": None, "converted": False},
            "warning": (
                "query contains CNY-denominated price constraint(s) "
                + "({}) but no --cny-to-usd-rate was given; price constraint NOT applied "
                + "(catalog prices are USD, never silently compared to RMB)"
            ).format("; ".join(m["raw"] for m in cny_mentions)),
        }

    conv = None
    converted = False
    converted_mentions = []
    lowers, uppers = [], []
    for m in mentions:
        usd = m.get("amount") if m["type"] in ("le", "ge") else (m.get("lo"), m.get("hi"))
        if isinstance(usd, tuple):
            lo, hi = (v * cny_to_usd_rate for v in usd) if m["currency"] == "CNY" else usd
            if m["currency"] == "CNY":
                converted = True
            lowers.append(lo)
            uppers.append(hi)
            converted_mentions.append({**m, "lo_usd": lo, "hi_usd": hi})
        else:
            v = usd * cny_to_usd_rate if m["currency"] == "CNY" else usd
            if m["currency"] == "CNY":
                converted = True
            (uppers if m["type"] == "le" else lowers).append(v)
            converted_mentions.append({**m, "amount_usd": v})
    if converted:
        conv = cny_to_usd_rate
    return {
        "detected_mentions": converted_mentions,
        "applied": True,
        "effective": {"lower": max(lowers) if lowers else None,
                      "upper": min(uppers) if uppers else None},
        "currency_mismatch": bool(cny_mentions),
        "conversion": {"cny_to_usd_rate": conv, "converted": converted},
        "warning": None,
    }


def _field_texts(rec):
    out = {}
    if isinstance(rec.get("title"), str) and rec["title"].strip():
        out["title"] = rec["title"]
    if isinstance(rec.get("brand"), str) and rec["brand"].strip():
        out["brand"] = rec["brand"]
    for k in ("categories", "features", "description"):
        vals = rec.get(k)
        if isinstance(vals, list):
            joined = " ".join(str(x) for x in vals if isinstance(x, str) and x.strip())
            if joined:
                out[k] = joined
    tech = rec.get("technical_details")
    if isinstance(tech, dict) and tech:
        joined = " ".join(f"{k}: {v}" for k, v in tech.items()
                          if isinstance(v, str) and v.strip())
        if joined:
            out["technical_details"] = joined
    return out


class BM25Index:
    def __init__(self, docs, fields=SEARCHABLE_FIELDS):
        self.fields = list(fields)
        self.N = len(docs)
        self.df = {f: {} for f in self.fields}
        self.dl = {f: 0 for f in self.fields}
        self.tf = []
        for doc in docs:
            tf = {}
            for f in self.fields:
                toks = tokenize(doc.get(f, ""))
                cnt = {}
                for t in toks:
                    cnt[t] = cnt.get(t, 0) + 1
                self.dl[f] += len(toks)
                tf[f] = cnt
                for t in set(toks):
                    self.df[f][t] = self.df[f].get(t, 0) + 1
            self.tf.append(tf)
        self.avgdl = {f: (self.dl[f] / self.N if self.N else 0.0) for f in self.fields}

    def idf(self, field, term):
        df = self.df[field].get(term, 0)
        return math.log(1.0 + (self.N - df + 0.5) / (df + 0.5))

    def score(self, idx, qtokens):
        contrib = {}
        total = 0.0
        for f in self.fields:
            tf = self.tf[idx][f]
            s = 0.0
            dl = sum(tf.values())
            avgdl = self.avgdl[f] or 1.0
            for t in qtokens:
                fq = tf.get(t, 0)
                if not fq:
                    continue
                denom = BM25_K1 * (1 - BM25_B + BM25_B * dl / avgdl) + fq
                s += self.idf(f, t) * fq / denom
            c = FIELD_WEIGHTS.get(f, 1.0) * s
            contrib[f] = c
            total += c
        return total, contrib


def _minmax_norm(scores):
    vals = [v for v in scores.values() if v is not None]
    if not vals:
        return {k: 0.0 for k in scores}
    lo, hi = min(vals), max(vals)
    if hi == lo:
        return {k: (1.0 if v is not None else 0.0) for k, v in scores.items()}
    return {k: (round((v - lo) / (hi - lo), 6) if v is not None else 0.0)
            for k, v in scores.items()}


def load_visual(emb_path, id_path, vec_path):
    """Lazy numpy load. Returns (emb_by_item, D, query_vec, error|None)."""
    np = None
    def _np():
        nonlocal np
        if np is None:
            import numpy  # lazy: numpy only required for the visual route
            np = numpy
        return np

    def _load_npy(p):
        return _np().load(p, allow_pickle=False)

    if not (emb_path and vec_path):
        return None, None, None, None
    try:
        emb = _load_npy(emb_path)
        vec = _load_npy(vec_path).reshape(-1)
    except Exception as exc:  # corrupt/missing arrays -> disable route, do not crash
        return None, None, None, f"visual array load failed: {exc}"
    emb = emb.reshape(emb.shape[0], -1)
    if emb.shape[0] == 0:
        return None, None, None, "visual embeddings empty"
    if emb.shape[1] != vec.shape[0]:
        return None, None, None, (
            f"dimension mismatch: embeddings D={emb.shape[1]} vs query D={vec.shape[0]}"
        )
    if id_path:
        try:
            if id_path.endswith(".npy"):
                ids = _load_npy(id_path).reshape(-1).tolist()
            else:
                with open(id_path, "r", encoding="utf-8") as fh:
                    raw = json.load(fh)
                ids = [int(x) for x in raw] if isinstance(raw, list) else None
        except Exception as exc:
            return None, None, None, f"visual item ids load failed: {exc}"
        if not ids or len(ids) != emb.shape[0]:
            return None, None, None, (
                f"item id count {len(ids) if ids else 0} != embedding rows {emb.shape[0]}"
            )
    else:
        ids = list(range(emb.shape[0]))
    return {iid: emb[i] for iid, i in zip(ids, range(emb.shape[0]))}, emb.shape[1], vec, None


def _snip(k, rec, qset):
    val = rec.get(k)
    if k == "price_usd":
        return {"value": val}
    if isinstance(val, list):
        text = " | ".join(str(x) for x in val if isinstance(x, str))
    elif isinstance(val, dict):
        text = " | ".join(f"{kk}: {vv}" for kk, vv in val.items())
    elif isinstance(val, str):
        text = val
    else:
        text = ""
    matched = sorted(set(tokenize(text)) & qset)
    return {"value": val, "matched_terms": matched}


def constraint_verdict(price, intent):
    eff = intent["effective"]
    if not intent["applied"]:
        return {"checked": False, "allowed": True,
                "reason": "no active hard price constraint"}
    if price is None:
        return {"checked": True, "allowed": False,
                "reason": "price_usd missing (evidence_missing);"
                          " cannot verify against " + _bounds_str(eff)}
    allowed = (eff["lower"] is None or price >= eff["lower"]) and \
              (eff["upper"] is None or price <= eff["upper"])
    return {"checked": True, "allowed": allowed,
            "reason": f"price_usd={price} within bounds {_bounds_str(eff)}" if allowed
            else f"price_usd={price} violates bounds {_bounds_str(eff)}"}


def _bounds_str(eff):
    lo = f"lower={eff['lower']}" if eff["lower"] is not None else None
    up = f"upper={eff['upper']}" if eff["upper"] is not None else None
    return " and ".join(x for x in (lo, up) if x) or "none"


def _why_ranked(contrib, fused, verdict, vis):
    parts = []
    top = sorted(((f, c) for f, c in contrib.items() if c is not None),
                 key=lambda kv: (-kv[1], kv[0]))[:2]
    parts.append("lexical " + ", ".join(f"{f}={c:.4f}" for f, c in top) if top else "lexical none")
    if vis is not None:
        parts.append(f"visual cos={vis:.4f}")
    if verdict["checked"]:
        parts.append("price " + ("OK" if verdict["allowed"] else "violates"))
    parts.append(f"fused={fused:.4f}")
    return "; ".join(parts)


def run(catalog_path, query, top_k=5, candidate_k=100, output_path=None,
        visual_embeddings=None, visual_item_ids=None, query_visual_vector=None,
        lexical_weight=1.0, visual_weight=0.0, cny_to_usd_rate=None):
    warnings = []
    query = query or ""
    qtokens = tokenize(query)
    intent = intent_price(query, cny_to_usd_rate)
    if intent["warning"]:
        warnings.append(intent["warning"])
    if not qtokens and not query_visual_vector:
        warnings.append("empty query text and no query visual vector; no ranking possible")

    catalog = []
    with open(catalog_path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            if rec.get("schema_version") != SCHEMA_VERSION:
                continue
            catalog.append(rec)
    catalog.sort(key=lambda r: r["item_id"])
    by_id = {r["item_id"]: r for r in catalog}
    missing_price_total = sum(1 for r in catalog if r.get("price_usd") is None)

    # ---- stage 1: hard price filter over the whole catalog -----------------
    kept, rejected = [], []
    for rec in catalog:
        v = constraint_verdict(rec.get("price_usd"), intent)
        if intent["applied"] and not v["allowed"]:
            rejected.append({"item_id": rec["item_id"], "asin": rec.get("asin"),
                             "title": rec.get("title"), "price_usd": rec.get("price_usd"),
                             "reasons": [v["reason"]]})
        else:
            kept.append(rec)

    # ---- stage 2: lexical BM25 (all kept records, then top candidate_k) ----
    docs = [_field_texts(r) for r in kept]
    index = BM25Index(docs) if docs else None
    lex_raw = {}
    lex_contrib = {}
    if qtokens and index is not None:
        for i, rec in enumerate(kept):
            raw, contrib = index.score(i, qtokens)
            lex_raw[rec["item_id"]] = raw
            lex_contrib[rec["item_id"]] = contrib
    lex_cands = sorted(lex_raw, key=lambda iid: (-lex_raw[iid], iid))[:max(1, candidate_k)]

    # ---- stage 3: visual cosine route --------------------------------------
    kept_ids = {r["item_id"] for r in kept}
    vis_scores = {}
    emb_by_item, D, qvec, visual_error = load_visual(
        visual_embeddings, visual_item_ids, query_visual_vector)
    visual_cands = []
    if emb_by_item is None:
        if visual_embeddings or query_visual_vector:
            warnings.append(visual_error or
                            "visual inputs present but unusable; visual route disabled")
    else:
        qn = math.sqrt(sum(float(x) * float(x) for x in qvec)) or 1.0
        for iid, vec in emb_by_item.items():
            if iid not in kept_ids:
                continue
            vn = math.sqrt(sum(float(x) * float(x) for x in vec)) or 1.0
            cos = sum(float(a) * float(b) for a, b in zip(qvec, vec)) / (qn * vn)
            vis_scores[iid] = max(-1.0, min(1.0, cos))
            visual_cands.append(iid)
        if not visual_cands:
            warnings.append("no overlap between visual item ids and kept catalog items; visual route empty")
    visual_overlap = len(set(by_id) & set(emb_by_item)) if emb_by_item else 0

    # ---- stage 4: fusion of the union of candidates -------------------------
    fused_ids = sorted(set(lex_cands) | set(visual_cands))
    scope = fused_ids  # deterministic canonical scope for per-route normalisation

    lex_all = {iid: lex_raw.get(iid, 0.0) for iid in scope}
    vis_all = {iid: vis_scores.get(iid) for iid in scope}
    norm_lex = _minmax_norm(lex_all)
    norm_vis = _minmax_norm(vis_all)

    fused = {}
    for iid in scope:
        fused[iid] = lexical_weight * norm_lex[iid] + visual_weight * norm_vis[iid]
    ranked_ids = sorted(scope, key=lambda iid: (-fused[iid],
                                                -lex_raw.get(iid, 0.0), iid))[:max(0, top_k)]

    ranked = []
    for rank, iid in enumerate(ranked_ids, 1):
        rec = by_id[iid]
        contrib = lex_contrib.get(iid, {f: None for f in SEARCHABLE_FIELDS})
        contrib_nonnull = {f: (round(v, 6) if v is not None else None) for f, v in contrib.items()}
        vis_raw = vis_scores.get(iid)
        verdict = constraint_verdict(rec.get("price_usd"), intent)
        snips = {}
        for f in SEARCHABLE_FIELDS:
            if rec.get(f):
                snips[f] = _snip(f, rec, set(qtokens))
        if rec.get("price_usd") is not None:
            snips["price_usd"] = {"value": rec["price_usd"],
                                  "satisfies": verdict["allowed"] if verdict["checked"] else None}
        ranked.append({
            "rank": rank,
            "item_id": iid,
            "asin": rec.get("asin"),
            "title": rec.get("title"),
            "brand": rec.get("brand"),
            "price_usd": rec.get("price_usd"),
            "constraint_verdict": verdict,
            "route_scores": {
                "lexical_raw": round(lex_raw.get(iid, 0.0), 6),
                "lexical_normalized": norm_lex[iid],
                "visual_raw": (round(vis_raw, 6) if vis_raw is not None else None),
                "visual_normalized": norm_vis[iid],
            },
            "fused_score": round(fused[iid], 6),
            "fused_formula": f"{lexical_weight}*lex_norm + {visual_weight}*vis_norm",
            "field_contributions": contrib_nonnull,
            "evidence_snippets": snips,
            "why_ranked_here": _why_ranked(contrib_nonnull, fused[iid], verdict, vis_raw),
        })

    out = {
        "query": query,
        "parsed_intent": {"price": intent},
        "warnings": warnings,
        "stage_counts": {
            "catalog": len(catalog),
            "hard_filter": {"kept": len(kept), "rejected": len(rejected)},
            "lexical_candidates": len(lex_cands),
            "visual_candidates": len(visual_cands),
            "fused": len(fused_ids),
        },
        "ranked": ranked,
        "rejected": rejected[:8],
        "uncertainty": {
            "evidence_missing_counts": {
                "price_usd_missing_in_catalog": missing_price_total,
                "items_without_visual_embedding": len(by_id) - visual_overlap,
                "fields_without_evidence_in_top_k": {
                    f: sum(1 for r in ranked if not r["evidence_snippets"].get(f))
                    for f in SEARCHABLE_FIELDS
                },
            },
            "note": "evidence_missing fields are never reported as satisfying any constraint",
        },
        "method": {
            "schema_version": SCHEMA_VERSION,
            "candidate_k": candidate_k,
            "top_k": top_k,
            "lexical_weight": lexical_weight,
            "visual_weight": visual_weight,
            "bm25": {"k1": BM25_K1, "b": BM25_B, "field_weights": FIELD_WEIGHTS},
            "fusion": "fused = lexical_weight*minmax(lex) + visual_weight*minmax(vis); "
                      "minmax over the fused scope per route; missing visual -> 0; "
                      "route weights as passed on the CLI",
            "price": "catalog price_usd is USD; CNY mentions converted only via --cny-to-usd-rate, "
                     "otherwise constraint left unapplied with currency_mismatch warning",
            "tokenizer": r"re.findall(r'[\w]+', text.casefold())",
        },
    }
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    ap.add_argument("--catalog", required=True, help="schema_version=1 catalog JSONL (prepare_catalog.py output)")
    ap.add_argument("--query", required=True, help="search query text")
    ap.add_argument("--top-k", type=int, default=5, help="final ranked results returned")
    ap.add_argument("--candidate-k", type=int, default=100, help="lexical candidates kept before fusion")
    ap.add_argument("--output", default=None, help="optional JSON file (written atomically)")
    ap.add_argument("--visual-embeddings", default=None, help="optional .npy item embeddings (N, D)")
    ap.add_argument("--visual-item-ids", default=None, help="optional JSON list or .npy of item_ids (aligned with embeddings)")
    ap.add_argument("--query-visual-vector", default=None, help="optional .npy query visual vector (D,)")
    ap.add_argument("--lexical-weight", type=float, default=1.0, help="fused lexical weight")
    ap.add_argument("--visual-weight", type=float, default=0.0, help="fused visual weight; set >0 to use visual route")
    ap.add_argument("--cny-to-usd-rate", type=float, default=None,
                    help="explicit CNY->USD conversion rate applied to CNY price mentions")
    args = ap.parse_args(argv)

    result = run(
        args.catalog, args.query, top_k=max(0, args.top_k), candidate_k=max(1, args.candidate_k),
        output_path=args.output, visual_embeddings=args.visual_embeddings,
        visual_item_ids=args.visual_item_ids, query_visual_vector=args.query_visual_vector,
        lexical_weight=args.lexical_weight, visual_weight=args.visual_weight,
        cny_to_usd_rate=args.cny_to_usd_rate,
    )

    if args.output:
        d = os.path.dirname(os.path.abspath(args.output))
        os.makedirs(d, exist_ok=True)
        tmp = os.path.join(d, "." + os.path.basename(args.output) + ".tmp")
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(result, fh, indent=2, ensure_ascii=False, allow_nan=False)
            fh.write("\n")
        os.replace(tmp, args.output)
    else:
        print(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False))
    sc = result["stage_counts"]
    print(f"search: kept {sc['hard_filter']['kept']}/{sc['catalog']} after price filter, "
          f"lex {sc['lexical_candidates']} / vis {sc['visual_candidates']}, "
          f"ranked {len(result['ranked'])}", file=sys.stderr)
    return result


if __name__ == "__main__":
    main()