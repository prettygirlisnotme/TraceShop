#!/usr/bin/env python3
"""Multi-turn query-state refinement + constraint negotiation (shopping track).

Deterministic, evidence-grounded companion to shopping/search_mvp.py.

Implements, on top of the existing single-turn search MVP:

  1. an explicit, auditable QueryState — hard constraints (price, must_include,
     must_exclude), soft preferences (term + weight + source turn), the persistent
     lexical query-words from turn 1, per-turn history, and every update delta;
  2. follow-up update semantics — a NEW turn only touches the slots its utterance
     explicitly names (via a restricted rule parser); the rest of the state is
     preserved.  What changed is stamped in history and is fully auditable;
  3. a rank/filter pipeline — hard constraints are a boolean filter applied to the
     whole catalog BEFORE any scoring; ranking (BM25 lexical + soft-preference
     boost) only reorders what survives the filter, so a high-scoring item that
     violates a hard constraint can never appear in the ranked list;
  4. constraint negotiation — when zero items satisfy the full hard set, compute
     single-dimension MINIMAL relaxations from REAL candidate statistics (actual
     prices / term membership in the catalog), each with the number of candidates
     it would recover and real example items.  No attribute is guessed;
     "unknown evidence" (e.g. items with no price) is counted and flagged
     separately, never assumed recoverable.

Intent understanding is deliberately NOT a general LLM/IR engine: it is a
restricted, documented rule-subset parser (price mentions reused from
search_mvp.intent_price, plus a small closed set of markers: require/must,
prefer/like, exclude/not, raise/drop price).  Any part of an utterance the
parser does not understand is recorded in `unresolved_tokens` and is never
silently applied.

English + a small Chinese subset.  stdlib only.
"""
import math
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import search_mvp as sm  # noqa: E402  (reuse price parser + BM25 + field helpers)

PARSE_MODE = "restricted-rule-subset v1 (NOT general natural-language understanding)"
STATE_SCHEMA_VERSION = 1

DEFAULT_PREF_WEIGHT = 0.6
STRONG_PREF_WEIGHT = 0.9

TOP_K = 5
CANDIDATE_K = 100

# tokens that end a marker-noun chunk or are pure grammar/junk for `unresolved`
NOUN_STOP = frozenset(
    "under over below above at most least no more than min max within between budget "
    "until with without up to into from until dollar dollars usd us cents cent yuan rmb "
    "a an the and or of it is this that than".split())

REMOVE_JUNK = frozenset(NOUN_STOP | set(
    "raise increase relax bump drop remove price cap require must have need be "
    "prefer like want exclude except not strongly x喜欢 偏好 要求 必须 排除 不要 以内 "
    "以上 以下 至少 不超过 预算 美元 人民币 元".split()))
REMOVE_JUNK |= {"as", "one", "items", "item", "maybe", "also", "too"}


# --------------------------------------------------------------------------- core state

def new_query_state(query_tokens, hard_price=None, must_include=None,
                    must_exclude=None, turn=1):
    """Initial QueryState shell.  `query_tokens` persist across turns (never
    removed by a follow-up); they only affect ranking, never feasibility."""
    return {
        "schema_version": STATE_SCHEMA_VERSION,
        "source": PARSE_MODE,
        "query_tokens": [t for t in (query_tokens or []) if t],
        "hard": {
            "price": {"upper": (hard_price or {}).get("upper"),
                      "lower": (hard_price or {}).get("lower")},
            "must_include": sorted(must_include or []),
            "must_exclude": sorted(must_exclude or []),
            "brands": [],
        },
        "soft_preferences": [],
        "unresolved_tokens": [],
        "history": [],
        "turn": turn,
    }


# --------------------------------------------------------------------------- restricted follow-up parser

_RE_PREF_KW = re.compile(r"(?:(?P<strong>strongly\s+)?(?:prefer|like|want))|(?P<cn_strong>强烈)?偏好|喜欢",
                         re.I)
_RE_REQUIRE_KW = re.compile(r"\b(?:require|must)\b|\bneed\b|要求|必须", re.I)
_RE_EXCLUDE_KW = re.compile(r"\b(?:exclude|except)\b|\bnot\b|\bno\b|排除|不要|除了", re.I)
_RE_RAISE = re.compile(
    r"\b(?:raise|increase|relax|bump|raise\s+budget)\b.{0,60}?\b(?:to|到)\s+\$?\s*(\d[\d,]*(?:\.\d+)?)",
    re.I)
_RE_DROP_PRICE = re.compile(r"\b(?:drop|remove)\s+(?:the\s+)?(?:price|budget|cap)\b|不限制价格", re.I)
_RE_PREF_REMOVE = re.compile(r"\b(?:no\s+longer|stop)\s+(?:preferring|wanting)\s+(\w+)", re.I)


def _noun_chunk(text):
    """Leading run of content nouns, cut at the first NOUN_STOP token."""
    out = []
    for t in sm.tokenize(text):
        if t in NOUN_STOP or re.search(r"^\d[\d,.]*$", t):
            break
        out.append(t)
    return out


def _clean_unresolved(text):
    toks = []
    for t in sm.tokenize(text):
        if t in REMOVE_JUNK or re.search(r"^\d[\d,.]*$", t):
            continue
        toks.append(t)
    return toks


def parse_followup(utterance, cny_to_usd_rate=None):
    """Restricted, deterministic follow-up parser.

    Returns {"parse_mode", "delta", "unresolved_tokens", "notes"}.
    delta keys: price {upper?/lower?} (OVERWRITE), must_add, must_remove,
    exclude_add, prefer_add [{"term","weight"}].  Tokens matching no rule go to
    unresolved_tokens.
    """
    u = str(utterance or "")
    delta = {}
    notes = []
    t_work = u

    # 1) price (reuse MVP deterministic parser; en/zh)
    intent = sm.intent_price(u, cny_to_usd_rate=cny_to_usd_rate)
    if intent["applied"]:
        eff = intent["effective"]
        pd = {}
        if eff["upper"] is not None:
            pd["upper"] = eff["upper"]
        if eff["lower"] is not None:
            pd["lower"] = eff["lower"]
        if pd:
            delta["price"] = pd
            t_work = re.sub(r"\b(?:under|below|over|above|between|at least|at most|"
                            r"up to|no more than|no less than|min|max|budget|within)\b", " ", t_work)
            t_work = re.sub(r"(?:\$?\s*\d[\d,]*(?:\.\d+)?)", " ", t_work)
        if intent.get("currency_mismatch"):
            notes.append("CNY mention without conversion rate -> price NOT applied "
                         "(catalog prices are USD); never silently converted")
    # 2) raise / drop price specialisations
    m = _RE_RAISE.search(u)
    if m and "price" not in delta:
        v = float(m.group(1).replace(",", ""))
        delta["price"] = {"upper": v}
        t_work = re.sub(r"\$?\s*\d[\d,]*(?:\.\d+)?", " ", t_work)
    if _RE_DROP_PRICE.search(u):
        d = dict(delta.get("price", {}))
        d["upper"] = None
        delta["price"] = d

    # 3) closed marker set (require / exclude / prefer)
    def mark(marker_re, key, weight_of=None):
        for m in marker_re.finditer(u):
            chunk = _noun_chunk(u[m.end():])
            for t in chunk:
                if weight_of is None:
                    delta.setdefault(key, []).append(t)
                else:
                    delta.setdefault(key, []).append(
                        {"term": t, "weight": weight_of(m)})

    def w_strong(m):
        g = m.groupdict()
        return STRONG_PREF_WEIGHT if (g.get("strong") or g.get("cn_strong")) \
            else DEFAULT_PREF_WEIGHT

    for m in _RE_REQUIRE_KW.finditer(u):
        for t in _noun_chunk(u[m.end():]):
            delta.setdefault("must_add", []).append(t)
    for m in _RE_EXCLUDE_KW.finditer(u):
        for t in _noun_chunk(u[m.end():]):
            delta.setdefault("exclude_add", []).append(t)
    for m in _RE_PREF_KW.finditer(u):
        strong = bool(m.groupdict().get("strong") or m.groupdict().get("cn_strong"))
        for t in _noun_chunk(u[m.end():].split(",")[0]):
            delta.setdefault("prefer_add", []).append(
                {"term": t, "weight": STRONG_PREF_WEIGHT if strong else DEFAULT_PREF_WEIGHT})
    for m in _RE_PREF_REMOVE.finditer(u):
        g = m.group(1)
        if g:
            delta.setdefault("prefer_remove", []).append(g.casefold())

    # 4) everything not understood -> unresolved (never silently applied)
    stripped = t_work
    for k in ("must_add", "must_remove", "exclude_add", "prefer_remove"):
        for t in delta.get(k, []):
            stripped = re.sub(r"\b" + re.escape(t) + r"\b", " ", stripped)
    for p in delta.get("prefer_add", []):
        stripped = re.sub(r"\b" + re.escape(p["term"]) + r"\b", " ", stripped)
    # marker words themselves
    stripped = re.sub(r"\b(?:prefer|like|want|require|must|need|exclude|except|not|no|"
                      r"strongly|raise|increase|relax|bump|drop|remove|budget|cap|the)\b",
                      " ", stripped)
    stripped = re.sub(r"偏好|喜欢|要求|必须|排除|不要|除了|以内|以下|以上|至少|不超过", " ", stripped)
    unresolved = _clean_unresolved(stripped)

    # deterministic dedupe
    for k in ("must_add", "must_remove", "exclude_add", "prefer_remove"):
        if k in delta:
            seen, kept = set(), []
            for t in delta[k]:
                if t not in seen:
                    seen.add(t)
                    kept.append(t)
            delta[k] = kept
    if "prefer_add" in delta:
        seen, kept = set(), []
        for p in delta["prefer_add"]:
            if p["term"] not in seen:
                seen.add(p["term"])
                kept.append(p)
        delta["prefer_add"] = kept

    return {"parse_mode": PARSE_MODE, "delta": delta,
            "unresolved_tokens": unresolved, "notes": notes}


# --------------------------------------------------------------------------- update semantics

def apply_update(state, utterance, turn=None, cny_to_usd_rate=None):
    """Apply a follow-up to a QueryState -> NEW state (state not mutated).

    Overwrite semantics: only slots present in the parsed delta are touched;
    everything else (query_tokens, other constraints, other preferences,
    history) is preserved.  `history` records exactly which slots changed.
    """
    import copy
    new = copy.deepcopy(state)
    parsed = parse_followup(utterance, cny_to_usd_rate=cny_to_usd_rate)
    delta = parsed["delta"]
    turn = turn if turn is not None else new["turn"] + 1
    new["turn"] = turn
    changed = []

    if "price" in delta:
        before = dict(new["hard"]["price"])
        new["hard"]["price"] = {
            "upper": delta["price"].get("upper", before["upper"]),
            "lower": delta["price"].get("lower", before["lower"]),
        }
        changed.append(("hard.price", before, dict(new["hard"]["price"])))

    if "must_add" in delta:
        for t in delta["must_add"]:
            if t not in new["hard"]["must_include"]:
                new["hard"]["must_include"].append(t)
            new["soft_preferences"] = [p for p in new["soft_preferences"] if p["term"] != t]
        new["hard"]["must_include"] = sorted(new["hard"]["must_include"])
        changed.append(("hard.must_include", "<turn %d>" % (turn - 1),
                        list(new["hard"]["must_include"])))

    if "must_remove" in delta:
        for t in delta["must_remove"]:
            new["hard"]["must_include"] = [x for x in new["hard"]["must_include"] if x != t]
        changed.append(("hard.must_include", "<turn %d>" % (turn - 1),
                        list(new["hard"]["must_include"])))

    if "exclude_add" in delta:
        for t in delta["exclude_add"]:
            if t not in new["hard"]["must_exclude"]:
                new["hard"]["must_exclude"].append(t)
            new["soft_preferences"] = [p for p in new["soft_preferences"] if p["term"] != t]
        new["hard"]["must_exclude"] = sorted(new["hard"]["must_exclude"])
        changed.append(("hard.must_exclude", "<turn %d>" % (turn - 1),
                        list(new["hard"]["must_exclude"])))

    if "prefer_add" in delta:
        for p in delta["prefer_add"]:
            hit = False
            for idx, old in enumerate(new["soft_preferences"]):
                if old["term"] == p["term"]:
                    new["soft_preferences"][idx] = {
                        "term": p["term"], "weight": p["weight"],
                        "source_turn": turn, "source_text": utterance.strip()}
                    hit = True
            if not hit:
                new["soft_preferences"].append({
                    "term": p["term"], "weight": p["weight"],
                    "source_turn": turn, "source_text": utterance.strip()})
        new["soft_preferences"].sort(key=lambda x: (x["term"], x["source_turn"]))
        changed.append(("soft_preferences", "<turn %d>" % (turn - 1),
                        list(new["soft_preferences"])))

    if "prefer_remove" in delta:
        for t in delta["prefer_remove"]:
            new["soft_preferences"] = [p for p in new["soft_preferences"] if p["term"] != t]
        changed.append(("soft_preferences", "<turn %d>" % (turn - 1),
                        list(new["soft_preferences"])))

    for t in parsed["unresolved_tokens"]:
        if t not in new["unresolved_tokens"]:
            new["unresolved_tokens"].append(t)

    new["history"].append({
        "turn": turn,
        "utterance": utterance.strip(),
        "parse": {k: parsed[k] for k in ("parse_mode", "delta", "unresolved_tokens", "notes")},
        "changed_slots": [c[0] for c in changed],
        "change_detail": changed,
    })
    return new


# --------------------------------------------------------------------------- turn-1 interpretation

def build_initial_state(utterance, cny_to_usd_rate=None):
    """Turn-1 interpretation (restricted, deterministic).

    Price mentions become a HARD price constraint (search_mvp.intent_price).
    Explicit markers split the other nouns: require/must -> must_include,
    exclude/not -> must_exclude, prefer/like -> soft.  Every remaining content
    noun becomes a persistent lexical query word (BM25 ranking only — never a
    feasibility constraint).  Numeric/currency/grammar tokens are dropped.
    """
    import re as _re
    intent = sm.intent_price(utterance, cny_to_usd_rate=cny_to_usd_rate)
    hard_price = {"upper": intent["effective"]["upper"] if intent["applied"] else None,
                  "lower": intent["effective"]["lower"] if intent["applied"] else None}
    notes = [intent["warning"]] if intent.get("warning") else []

    must_include, must_exclude, prefs, lexical = [], [], [], []
    toks = sm.tokenize(utterance)
    i, n = 0, len(toks)
    MARKERS = frozenset(("require", "must", "need", "prefer", "like", "want",
                         "exclude", "except", "not"))

    def marker(t):
        return t in {"require", "must", "need"} or t in {"exclude", "except"} \
            or t in {"prefer", "like", "want"} or t == "not"

    while i < n:
        t = toks[i]
        if t in ("require", "must", "need"):
            j = i + 1
            while j < n and toks[j] not in MARKERS \
                    and not _re.search(r"^\d[\d,.]*$", toks[j]):
                if toks[j] == "and":
                    j += 1
                    continue
                if toks[j] in NOUN_STOP:
                    break
                must_include.append(toks[j])
                j += 1
            i = j
        elif t in ("exclude", "except", "not"):
            j = i + 1
            while j < n and toks[j] not in MARKERS \
                    and not _re.search(r"^\d[\d,.]*$", toks[j]):
                if toks[j] == "and":
                    j += 1
                    continue
                if toks[j] in NOUN_STOP:
                    break
                must_exclude.append(toks[j])
                j += 1
            i = j
        elif t in ("prefer", "like", "want"):
            strong = bool(i and toks[i - 1] == "strongly")
            j = i + 1
            while j < n and toks[j] not in MARKERS \
                    and not _re.search(r"^\d[\d,.]*$", toks[j]):
                if toks[j] == "and" or toks[j] in NOUN_STOP:
                    j += 1
                    continue
                prefs.append({"term": toks[j],
                              "weight": STRONG_PREF_WEIGHT if strong else DEFAULT_PREF_WEIGHT})
                j += 1
            i = j
        else:
            if t not in NOUN_STOP and not _re.search(r"^\d[\d,.]*$", t) \
                    and t not in MARKERS:
                lexical.append(t)
            i += 1

    state = new_query_state([], hard_price=hard_price)
    state["hard"]["must_include"] = sorted(set(must_include))
    state["hard"]["must_exclude"] = sorted(set(must_exclude))
    state["soft_preferences"] = prefs
    state["query_tokens"] = sorted(set(lexical + must_include + [p["term"] for p in prefs]))
    state["history"].append({
        "turn": 1,
        "utterance": utterance.strip(),
        "parse": {"parse_mode": PARSE_MODE,
                  "price": intent,
                  "notes": notes,
                  "interpretation": {
                      "hard_price": hard_price,
                      "must_include": list(state["hard"]["must_include"]),
                      "must_exclude": list(state["hard"]["must_exclude"]),
                      "soft_preferences": prefs,
                      "lexical_query_tokens": state["query_tokens"],
                  }},
        "changed_slots": ["initialize"],
        "change_detail": [],
    })
    return state


# --------------------------------------------------------------------------- hard filter + ranking

def _token_set(rec):
    """Token set over ALL searchable fields of a record."""
    toks = set()
    for joined in sm._field_texts(rec).values():
        toks.update(sm.tokenize(joined))
    return toks


def _price_verdict(rec, state):
    """Price vs state's hard price bounds.  Missing price is evidence_missing
    (rejected under an active bound), never assumed to pass."""
    eff = state["hard"]["price"]
    up, lo = eff["upper"], eff["lower"]
    p = rec.get("price_usd")
    if up is None and lo is None:
        return {"allowed": True, "reason": "no active price bound"}
    if not isinstance(p, (int, float)):
        return {"allowed": False,
                "reason": "price_usd missing (evidence_missing); cannot verify price bound"}
    ok = (lo is None or p >= lo) and (up is None or p <= up)
    if not ok:
        return {"allowed": False,
                "reason": f"price_usd={p} violates bounds {sm._bounds_str(eff)}"}
    return {"allowed": True, "reason": f"price_usd={p} within bounds {sm._bounds_str(eff)}"}


def hard_filter(catalog, state):
    """Boolean filter over the whole catalog -> (kept, rejected_with_reasons).

    Hard constraints are NEVER bypassed by any score: any failing hard
    constraint rejects the item no matter how well it would rank.
    """
    kept, rejected = [], []
    for rec in catalog:
        reasons = []
        pv = _price_verdict(rec, state)
        if not pv["allowed"]:
            reasons.append(pv["reason"])
        ts = _token_set(rec)
        missing = [t for t in state["hard"]["must_include"] if t not in ts]
        if missing:
            reasons.append("missing required term(s): " + ", ".join(missing))
        hit = [t for t in state["hard"]["must_exclude"] if t in ts]
        if hit:
            reasons.append("contains excluded term(s): " + ", ".join(hit))
        if state["hard"]["brands"]:
            b = str(rec.get("brand") or "").casefold()
            if not any(x in b for x in state["hard"]["brands"]):
                reasons.append("brand not in " + ",".join(state["hard"]["brands"]))
        if reasons:
            rejected.append({"item_id": rec["item_id"], "asin": rec.get("asin"),
                             "title": rec.get("title"), "brand": rec.get("brand"),
                             "price_usd": rec.get("price_usd"), "reasons": reasons})
        else:
            kept.append(rec)
    return kept, rejected


def lexical_scores(catalog, query_tokens):
    docs = [sm._field_texts(r) for r in catalog]
    idx = sm.BM25Index(docs)
    raw, contrib = {}, {}
    for i, rec in enumerate(catalog):
        r, c = idx.score(i, query_tokens)
        raw[rec["item_id"]] = r
        contrib[rec["item_id"]] = c
    return raw, contrib, idx


def pref_score(rec, prefs):
    """Soft-preference contribution: weighted boolean presence of each term."""
    ts = _token_set(rec)
    s = 0.0
    detail = []
    for p in prefs:
        if p["term"] in ts:
            s += p["weight"]
            detail.append({"term": p["term"], "weight": p["weight"], "matched": True})
    return s, detail


def rank_turn(catalog, state, top_k=TOP_K, candidate_k=CANDIDATE_K,
              visual_scores=None, visual_weight=0.5,
              reranker_scores=None, reranker_weight=0.7):
    """Filter, fuse retrieval routes, then optionally rerank a candidate pool.

    The boolean hard filter always runs first. Visual similarity can therefore
    reorder only feasible items; it can never admit an item that violates a
    price, required/excluded-term, or brand constraint. When reranker scores
    are supplied, only items with such a score form the final candidate pool.
    """
    try:
        visual_weight = float(visual_weight)
    except (TypeError, ValueError) as exc:
        raise ValueError("visual_weight must be a number in [0, 1]") from exc
    if not math.isfinite(visual_weight) or not 0.0 <= visual_weight <= 1.0:
        raise ValueError("visual_weight must be a finite number in [0, 1]")
    try:
        reranker_weight = float(reranker_weight)
    except (TypeError, ValueError) as exc:
        raise ValueError("reranker_weight must be a number in [0, 1]") from exc
    if not math.isfinite(reranker_weight) or not 0.0 <= reranker_weight <= 1.0:
        raise ValueError("reranker_weight must be a finite number in [0, 1]")
    warnings = []
    kept, rejected = hard_filter(catalog, state)
    qt = state["query_tokens"]
    if not qt:
        warnings.append("no lexical query tokens; text route is uniform")

    lex_raw, lex_contrib, _ = lexical_scores(catalog, qt)
    scope = [r for r in kept]
    by_id = {r["item_id"]: r for r in catalog}
    norm_lex = sm._minmax_norm({r["item_id"]: lex_raw.get(r["item_id"], 0.0) for r in scope})

    pref_raw = {r["item_id"]: 0.0 for r in scope}
    pref_detail = {r["item_id"]: [] for r in scope}
    if state["soft_preferences"]:
        for r in scope:
            s, parts = pref_score(r, state["soft_preferences"])
            pref_raw[r["item_id"]] = s
            pref_detail[r["item_id"]] = parts
    norm_pref = sm._minmax_norm(pref_raw) if state["soft_preferences"] \
        else {r["item_id"]: 0.0 for r in scope}

    text_score = {
        r["item_id"]: norm_lex[r["item_id"]] + norm_pref[r["item_id"]]
        for r in scope
    }
    text_norm = sm._minmax_norm(text_score)

    visual_used = visual_scores is not None
    visual_raw = {}
    if visual_scores is not None:
        for r in scope:
            iid = r["item_id"]
            raw = visual_scores.get(iid, visual_scores.get(str(iid)))
            if raw is None:
                continue
            raw = float(raw)
            if math.isfinite(raw):
                visual_raw[iid] = raw
    visual_norm_present = sm._minmax_norm(visual_raw) if visual_raw else {}
    norm_visual = {
        r["item_id"]: visual_norm_present.get(r["item_id"], 0.0)
        for r in scope
    }

    if visual_used:
        fused = {
            r["item_id"]: ((1.0 - visual_weight) * text_norm[r["item_id"]]
                           + visual_weight * norm_visual[r["item_id"]])
            for r in scope
        }
        fused_formula = (
            "(1-visual_weight)*text_normalized + "
            "visual_weight*image_cosine_normalized (after hard filter)"
        )
    else:
        # Preserve the pre-image API ranking exactly for text-only requests.
        fused = dict(text_score)
        fused_formula = "lexical_normalized + preference_normalized (after hard filter)"

    text_order = sorted(scope, key=lambda r: (-text_score[r["item_id"]],
                                               -lex_raw.get(r["item_id"], 0.0),
                                               r["item_id"]))
    text_rank = {r["item_id"]: i for i, r in enumerate(text_order, 1)}
    full_fused_order = sorted(scope, key=lambda r: (-fused[r["item_id"]],
                                                     -lex_raw.get(r["item_id"], 0.0),
                                                     r["item_id"]))
    fused_rank = {r["item_id"]: i for i, r in enumerate(full_fused_order, 1)}

    reranker_raw = {}
    if reranker_scores is not None:
        for r in full_fused_order:
            iid = r["item_id"]
            raw = reranker_scores.get(iid, reranker_scores.get(str(iid)))
            if raw is None:
                continue
            raw = float(raw)
            if math.isfinite(raw):
                reranker_raw[iid] = raw
    reranker_used = bool(reranker_raw)
    if reranker_used:
        rerank_scope = [
            r for r in full_fused_order if r["item_id"] in reranker_raw
        ]
        base_candidate_norm = sm._minmax_norm({
            r["item_id"]: fused[r["item_id"]] for r in rerank_scope
        })
        norm_reranker = sm._minmax_norm(reranker_raw)
        final_score = {
            r["item_id"]: (
                (1.0 - reranker_weight) * base_candidate_norm[r["item_id"]]
                + reranker_weight * norm_reranker[r["item_id"]]
            )
            for r in rerank_scope
        }
        final_order = sorted(
            rerank_scope,
            key=lambda r: (
                -final_score[r["item_id"]],
                -fused[r["item_id"]],
                r["item_id"],
            ),
        )
        final_formula = (
            "reranker_weight*xenc_normalized + "
            "(1-reranker_weight)*multimodal_candidate_score_normalized"
        )
    else:
        rerank_scope = []
        norm_reranker = {}
        final_score = dict(fused)
        final_order = full_fused_order
        final_formula = fused_formula
    final_rank = {r["item_id"]: i for i, r in enumerate(final_order, 1)}
    ranked_ids = final_order[:max(0, top_k)]

    ranked = []
    for rank, rec in enumerate(ranked_ids, 1):
        iid = rec["item_id"]
        pv = _price_verdict(rec, state)
        snips = {}
        for f in sm.SEARCHABLE_FIELDS:
            if rec.get(f):
                snips[f] = sm._snip(f, rec, set(qt))
        snips["price_usd"] = {"value": rec.get("price_usd"),
                              "satisfies": pv["allowed"]}
        ranked.append({
            "rank": rank, "item_id": iid, "asin": rec.get("asin"),
            "title": rec.get("title"), "brand": rec.get("brand"),
            "price_usd": rec.get("price_usd"),
            "hard_verdicts": [pv["reason"]],
            "route_scores": {
                "lexical_raw": round(lex_raw.get(iid, 0.0), 6),
                "lexical_normalized": norm_lex[iid],
                "preference_normalized": norm_pref[iid],
                "preference_detail": pref_detail[iid],
                "text_normalized": text_norm[iid],
                "visual_available": iid in visual_raw,
                "visual_cosine": round(visual_raw[iid], 6) if iid in visual_raw else None,
                "visual_normalized": norm_visual[iid],
                "visual_weight": visual_weight if visual_used else 0.0,
                "multimodal_candidate_score": round(fused[iid], 6),
                "reranker_available": iid in reranker_raw,
                "reranker_logit": (
                    round(reranker_raw[iid], 6) if iid in reranker_raw else None
                ),
                "reranker_normalized": norm_reranker.get(iid, 0.0),
                "reranker_weight": reranker_weight if reranker_used else 0.0,
            },
            "rank_without_image": text_rank[iid],
            "rank_after_multimodal": fused_rank[iid],
            "visual_rank_delta": fused_rank[iid] - text_rank[iid],
            "rank_before_reranker": fused_rank[iid],
            "rerank_delta": rank - fused_rank[iid] if reranker_used else 0,
            "rank_delta": rank - text_rank[iid],
            "fused_score": round(final_score[iid], 6),
            "fused_formula": final_formula,
            "evidence_snippets": snips,
        })

    rejected_sorted = sorted(rejected,
                             key=lambda r: (-lex_raw.get(r["item_id"], 0.0), r["item_id"]))[:5]
    for r in rejected_sorted:
        r["would_rank_lexical_raw"] = round(lex_raw.get(r["item_id"], 0.0), 6)

    rank_changes = [{
        "item_id": r["item_id"],
        "text_rank": text_rank[r["item_id"]],
        "fused_rank": fused_rank[r["item_id"]],
        "delta": fused_rank[r["item_id"]] - text_rank[r["item_id"]],
    } for r in scope if fused_rank[r["item_id"]] != text_rank[r["item_id"]]]
    rank_changes.sort(key=lambda x: (-abs(x["delta"]), x["fused_rank"], x["item_id"]))
    rerank_changes = [{
        "item_id": r["item_id"],
        "candidate_rank": fused_rank[r["item_id"]],
        "reranked_rank": final_rank[r["item_id"]],
        "delta": final_rank[r["item_id"]] - fused_rank[r["item_id"]],
    } for r in rerank_scope
        if final_rank[r["item_id"]] != fused_rank[r["item_id"]]]
    rerank_changes.sort(
        key=lambda x: (-abs(x["delta"]), x["reranked_rank"], x["item_id"])
    )

    return {
        "turn": state["turn"],
        "query_tokens": qt,
        "hard": {
            "price": dict(state["hard"]["price"]),
            "must_include": list(state["hard"]["must_include"]),
            "must_exclude": list(state["hard"]["must_exclude"]),
        },
        "soft_preferences": list(state["soft_preferences"]),
        "warnings": warnings,
        "stage_counts": {
            "catalog": len(catalog),
            "hard_filter": {"kept": len(kept), "rejected": len(rejected)},
            "rerank_candidates": len(rerank_scope),
            "ranked": len(ranked),
        },
        "ranked": ranked,
        "visual": {
            "used": visual_used,
            "weight": visual_weight if visual_used else 0.0,
            "scored_feasible_items": len(visual_raw),
            "changed_item_count": len(rank_changes),
            "rank_changes": rank_changes[:10],
            "rank_delta_definition": "fused_rank - text_rank; negative means moved up",
        },
        "reranker": {
            "used": reranker_used,
            "weight": reranker_weight if reranker_used else 0.0,
            "candidate_count": len(rerank_scope),
            "changed_item_count": len(rerank_changes),
            "rank_changes": rerank_changes[:10],
            "rank_delta_definition": "reranked_rank - candidate_rank; negative means moved up",
        },
        "rejected_top_by_lexical": rejected_sorted,
        "uncertainty": {
            "evidence_missing": {
                "price_usd_missing_in_catalog": sum(
                    1 for r in catalog if not isinstance(r.get("price_usd"), (int, float))),
                "unresolved_tokens_in_state": list(state["unresolved_tokens"]),
            },
        },
    }


# --------------------------------------------------------------------------- negotiation

def negotiate(catalog, state):
    """Constraint relaxation suggestions when NO item satisfies the full hard set.

    Every option is derived from REAL candidate statistics: the actual distinct
    prices among rejected-by-price near-miss items (price relaxations) or real
    term-membership counts (term relaxations).  Nothing is guessed.  "unknown
    evidence" counts are reported separately and never counted as recoverable.
    """
    kept, rejected = hard_filter(catalog, state)
    if kept:
        return {"needed": False, "feasible_count": len(kept), "options": [],
                "unknown_evidence": {}}

    hard = state["hard"]

    def passes_others(rec, ignore_price_upper=False, ignore_price_lower=False,
                      ignore_must=None, ignore_exclude=None):
        fake = {
            "hard": {"price": {
                "upper": None if ignore_price_upper else hard["price"]["upper"],
                "lower": None if ignore_price_lower else hard["price"]["lower"],
            }},
        }
        pv = _price_verdict(rec, fake)
        if not pv["allowed"]:
            return False, [pv["reason"]]
        ts = _token_set(rec)
        reasons = []
        mi = [t for t in hard["must_include"] if t != ignore_must]
        if any(t not in ts for t in mi):
            reasons.append("missing required term")
        ex = [t for t in hard["must_exclude"] if t != ignore_exclude]
        if any(t in ts for t in ex):
            reasons.append("contains excluded term")
        return (len(reasons) == 0), reasons

    options = []

    # ---- price upper: minimal ladder over REAL distinct near-miss prices
    up = hard["price"]["upper"]
    if up is not None:
        near = [rec for rec in catalog
                if isinstance(rec.get("price_usd"), (int, float))
                and rec["price_usd"] > up and passes_others(rec, ignore_price_upper=True)[0]]
        missing = sum(1 for rec in catalog
                      if not isinstance(rec.get("price_usd"), (int, float))
                      and passes_others(rec, ignore_price_upper=True)[0])
        prices = sorted({round(rec["price_usd"], 6) for rec in near})
        steps = []
        for pv in prices[:5]:
            recs = [r for r in near if r["price_usd"] <= pv]
            steps.append({
                "raise_upper_to": pv,
                "recovered_count": len(recs),
                "sample_items": [
                    {"item_id": r["item_id"], "title": r.get("title"),
                     "price_usd": r.get("price_usd")}
                    for r in sorted(recs, key=lambda r: (r["price_usd"], r["item_id"]))[:3]],
            })
        if steps:
            options.append({
                "constraint": "hard.price.upper",
                "current": up,
                "minimal_action": f"raise upper bound {up} -> {steps[0]['raise_upper_to']}",
                "minimal_recovered": steps[0]["recovered_count"],
                "max_recovered": len(near),
                "ladder": steps,
                "unknown_evidence": {"near_miss_items_without_price": missing},
            })

    # ---- price lower: symmetric
    lo = hard["price"]["lower"]
    if lo is not None:
        near = [rec for rec in catalog
                if isinstance(rec.get("price_usd"), (int, float))
                and rec["price_usd"] < lo and passes_others(rec, ignore_price_lower=True)[0]]
        missing = sum(1 for rec in catalog
                      if not isinstance(rec.get("price_usd"), (int, float))
                      and passes_others(rec, ignore_price_lower=True)[0])
        prices = sorted({round(rec["price_usd"], 6) for rec in near}, reverse=True)
        steps = []
        for pv in prices[:5]:
            recs = [r for r in near if r["price_usd"] >= pv]
            steps.append({
                "lower_upper_to": pv,
                "recovered_count": len(recs),
                "sample_items": [
                    {"item_id": r["item_id"], "title": r.get("title"),
                     "price_usd": r.get("price_usd")}
                    for r in sorted(recs, key=lambda r: (-r["price_usd"], r["item_id"]))[:3]],
            })
        if steps:
            options.append({
                "constraint": "hard.price.lower",
                "current": lo,
                "minimal_action": f"lower bound {lo} -> {steps[0]['lower_upper_to']}",
                "minimal_recovered": steps[0]["recovered_count"],
                "max_recovered": len(near),
                "ladder": steps,
                "unknown_evidence": {"near_miss_items_without_price": missing},
            })

    # ---- term relaxations (atomic: drop one required term)
    for t in hard["must_include"]:
        recs = [rec for rec in catalog if passes_others(rec, ignore_must=t)[0]]
        options.append({
            "constraint": "hard.must_include",
            "current": t,
            "minimal_action": f"drop required term '{t}'",
            "minimal_recovered": len(recs),
            "max_recovered": len(recs),
            "ladder": [],
            "recovered_items": [
                {"item_id": r["item_id"], "title": r.get("title"),
                 "price_usd": r.get("price_usd")}
                for r in sorted(recs, key=lambda r: (r.get("price_usd") is None,
                                                     r.get("price_usd") or 0.0,
                                                     r["item_id"]))[:5]],
            "unknown_evidence": {},
        })

    # ---- exclusion relaxations (atomic: drop one excluded term)
    for t in hard["must_exclude"]:
        recs = [rec for rec in catalog if passes_others(rec, ignore_exclude=t)[0]]
        options.append({
            "constraint": "hard.must_exclude",
            "current": t,
            "minimal_action": f"drop excluded term '{t}'",
            "minimal_recovered": len(recs),
            "max_recovered": len(recs),
            "ladder": [],
            "recovered_items": [
                {"item_id": r["item_id"], "title": r.get("title"),
                 "price_usd": r.get("price_usd")}
                for r in sorted(recs, key=lambda r: (r.get("price_usd") is None,
                                                     r.get("price_usd") or 0.0,
                                                     r["item_id"]))[:5]],
            "unknown_evidence": {},
        })

    options.sort(key=lambda o: (-o["minimal_recovered"], o["constraint"], str(o["current"])))
    return {
        "needed": True,
        "feasible_count": 0,
        "rejected_count": len(rejected),
        "options": options,
        "unknown_evidence": {
            "price_usd_missing_in_catalog": sum(
                1 for r in catalog if not isinstance(r.get("price_usd"), (int, float))),
            "note": "items without price evidence are counted but never reported as recoverable",
        },
    }


# --------------------------------------------------------------------------- demo trace

def run_demo(catalog_path, top_k=TOP_K, candidate_k=CANDIDATE_K):
    """Builds the two deterministic multi-turn cases on the real catalog.

    Case 1: preference change -> same hard constraint, new order.
    Case 2: zero feasible items -> evidence-based minimal relaxation -> user picks one.
    """
    import json as _json
    catalog = []
    with open(catalog_path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            rec = _json.loads(line)
            if rec.get("schema_version") != sm.SCHEMA_VERSION:
                continue
            catalog.append(rec)
    catalog.sort(key=lambda r: r["item_id"])

    c1 = {}
    s1 = build_initial_state("wireless mouse under 30 dollars")
    c1["state_after_turn1"] = s1
    c1["turn1"] = rank_turn(catalog, s1, top_k=top_k, candidate_k=candidate_k)
    s2 = apply_update(s1, "prefer gaming", turn=2)
    c1["state_after_turn2"] = s2
    c1["turn2"] = rank_turn(catalog, s2, top_k=top_k, candidate_k=candidate_k)
    c1["ranking_changed"] = ([r["item_id"] for r in c1["turn1"]["ranked"]] !=
                             [r["item_id"] for r in c1["turn2"]["ranked"]])
    c1["hard_unchanged"] = (c1["turn1"]["hard"] == c1["turn2"]["hard"])

    c2 = {}
    s1b = build_initial_state("require bluetooth and wireless, under 6 dollars")
    c2["state_after_turn1"] = s1b
    c2["turn1"] = rank_turn(catalog, s1b, top_k=top_k, candidate_k=candidate_k)
    c2["negotiation"] = negotiate(catalog, s1b)
    s2b = apply_update(s1b, "raise the budget to 12 dollars", turn=2)
    c2["state_after_turn2"] = s2b
    c2["turn2"] = rank_turn(catalog, s2b, top_k=top_k, candidate_k=candidate_k)
    c2["followup_only_price_change"] = s2b["history"][-1]["changed_slots"]

    parsed_demo = parse_followup("prefer gaming, sturdy mouse and a green one")
    micro = {
        "utterance": "prefer gaming, sturdy mouse and a green one",
        "parsed": parsed_demo,
        "honest_note": ("'gaming' is understood as a soft preference; the bare nouns "
                        "'sturdy', 'mouse', 'green' are outside the restricted "
                        "grammar and are flagged as unresolved instead of being guessed."),
    }

    return {
        "meta": {
            "state_schema_version": STATE_SCHEMA_VERSION,
            "parse_mode": PARSE_MODE,
            "catalog": catalog_path,
            "catalog_records": len(catalog),
            "deterministic": True,
        },
        "case1_preference_change": c1,
        "case2_constraint_negotiation": c2,
        "parser_honesty_microcheck": micro,
    }
