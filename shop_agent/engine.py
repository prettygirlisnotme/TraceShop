#!/usr/bin/env python3
"""Standalone Shopping Decision Agent engine.

A *decision layer* on top of the vendored, verified CPU research pipeline.  It
imports the real ``online_api.ResearchService`` from ``vendor/project_a`` through
a controlled ``sys.path`` entry and never modifies it.  The engine adds,
deterministically and without any LLM:

  READ STATE -> propose a choice + rationale from catalog evidence
  -> explicit user approve / reject -> execute a demo draft reservation in
  SQLite -> read it back and verify the outcome.

There is no real merchant integration.  Approvals create local draft rows only
("本地采购草稿，不下单、不扣款").  Simulated quote changes force NEEDS_REVIEW and can
never auto-buy or auto-re-approve.  stdlib only.
"""

import hashlib
import math
import os
import sys
import time
import uuid

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VENDOR_DIR = os.path.join(ROOT, "vendor", "project_a")
if VENDOR_DIR not in sys.path:
    sys.path.insert(0, VENDOR_DIR)

import online_api  # noqa: E402  (real vendored ResearchService)
import querystate_session as qs  # noqa: E402  (hard-constraint recheck)

from .store import Store  # noqa: E402

DEFAULT_CATALOG = os.path.join(ROOT, "demo", "catalog.jsonl")
DEFAULT_DB = os.path.join(ROOT, "shop_agent_runs", "agent.sqlite3")
DISCLAIMER_ZH = "本地采购草稿，不下单、不扣款 / 商品来源见需求简报；库存与变更为演示服务"
DISCLAIMER_EN = ("Local draft only. No order is placed and no payment is taken. "
                 "Catalog source is shown in the brief; stock and changes are simulated.")
DEFAULT_TTL_SECONDS = 900.0
AVAILABILITIES = ("in_stock", "out_of_stock")
SOURCE_LABEL = "vendor/project_a/online_api.py ResearchService (Cluster A V1.2)"


class AgentError(Exception):
    def __init__(self, status, code, message):
        super().__init__(message)
        self.status, self.code, self.message = int(status), code, message


def _iso(ts):
    try:
        return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(float(ts)))
    except (TypeError, ValueError, OSError):
        return None


def _positive(value):
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise AgentError(400, "invalid_price", "price_usd must be a number") from exc
    if not math.isfinite(number) or number <= 0:
        raise AgentError(400, "invalid_price", "price_usd must be a finite positive number")
    return round(number, 6)


def _price_equal(a, b):
    if a is None or b is None:
        return a is None and b is None
    try:
        return abs(float(a) - float(b)) < 1e-6
    except (TypeError, ValueError):
        return False


def make_visual_adapter(clip_emb, clip_mask, clip_ids, clip_model, device):
    if not any((clip_emb, clip_mask, clip_ids)):
        return None
    return online_api.VisualSearchAdapter(clip_emb, clip_mask, clip_ids,
                                          model_name=clip_model, device=device)


def make_reranker_adapter(checkpoint, model_name, device):
    if not checkpoint:
        return None
    return online_api.CrossEncoderRerankAdapter(checkpoint, model_name=model_name, device=device)


class ShopAgentEngine:
    """Deterministic decision policy + durable demo reservations."""

    def __init__(self, catalog_path=None, db_path=None, ttl_seconds=DEFAULT_TTL_SECONDS,
                 clock=time.time, visual_adapter=None, reranker_adapter=None,
                 default_owner="local-demo"):
        self.catalog_path = os.path.abspath(catalog_path or DEFAULT_CATALOG)
        self.db_path = db_path or DEFAULT_DB
        self.ttl_seconds = float(ttl_seconds)
        self.clock = clock or time.time
        self.default_owner = default_owner
        self.store = Store(self.db_path)
        self.service = online_api.ResearchService(
            self.catalog_path, visual_adapter=visual_adapter, reranker_adapter=reranker_adapter)
        self.catalog_by_id = {str(r["item_id"]): r for r in (self.service.catalog or [])}

    # -- generic helpers -------------------------------------------------
    def _owner(self, owner):
        owner = (owner or "").strip() or self.default_owner
        if len(owner) > 128:
            raise AgentError(400, "invalid_owner", "owner must be at most 128 characters")
        return owner

    def _topk(self, top_k):
        try:
            value = int(3 if top_k is None else top_k)
        except (TypeError, ValueError) as exc:
            raise AgentError(400, "invalid_top_k", "top_k must be an integer") from exc
        if not 1 <= value <= 10:
            raise AgentError(400, "invalid_top_k", "top_k must be in [1, 10]")
        return value

    def _call(self, fn):
        try:
            return fn()
        except online_api.ApiError as exc:
            raise AgentError(exc.status, exc.code, exc.message) from exc

    @staticmethod
    def _service_sid(owner, session_id):
        return "sa-" + hashlib.sha1((owner + "|" + session_id).encode("utf-8")).hexdigest()[:24]

    def _live_quote(self, owner, session_id, item_id):
        rec = self.catalog_by_id.get(str(item_id), {})
        price, availability = rec.get("price_usd"), "in_stock"
        override = self.store.get_quote(owner, session_id, item_id)
        if override:
            if override.get("price_usd") is not None:
                price = override["price_usd"]
            if override.get("availability"):
                availability = override["availability"]
        return {"price_usd": price, "availability": availability}

    @staticmethod
    def _bind(proposal, owner, session_id):
        if proposal is None:
            raise AgentError(404, "proposal_not_found", "unknown proposal_id")
        if proposal["owner"] != owner:
            raise AgentError(403, "owner_mismatch", "proposal belongs to another owner")
        if session_id and proposal["session_id"] != session_id:
            raise AgentError(403, "session_mismatch", "proposal belongs to another session")

    def _public_proposal(self, p):
        evidence = p.get("evidence") or {}
        return {"proposal_id": p["proposal_id"], "session_id": p["session_id"],
                "item_id": p["item_id"], "title": p["title"], "brand": p["brand"],
                "price_usd": p["price_usd"], "availability": p["availability"],
                "eligible_item_ids": p["eligible_item_ids"], "rationale": p["rationale"],
                "evidence": evidence, "status": p["status"], "revision": p["revision"],
                "merchant_version": p["merchant_version"], "expires_at": p["expires_at"],
                "expires_at_iso": _iso(p["expires_at"]), "created_at": p["created_at"],
                "selection": evidence.get("selection")}

    # -- health ----------------------------------------------------------
    def health(self):
        base = self.service.health()
        base["agent"] = {
            "source_label": SOURCE_LABEL, "disclaimer_zh": DISCLAIMER_ZH,
            "disclaimer_en": DISCLAIMER_EN,
            "decision_policy": "deterministic rule policy; no LLM, no external API",
            "catalog_path": self.catalog_path,
            "catalog_is_demo_fixture": self.catalog_path == os.path.abspath(DEFAULT_CATALOG),
            "db_path": self.db_path, "persistence": "sqlite3 (stdlib)",
            "proposal_ttl_seconds": self.ttl_seconds, "real_merchant_integrated": False,
            "capabilities": {"propose": True, "approve": True, "reject": True,
                             "select_candidate": True, "select_candidate_creates_reservation": False,
                             "simulate_quote_change": True, "idempotent_approve": True,
                             "durable_readback": True,
                             "visual_online": self.service.visual_adapter is not None,
                             "reranker_online": self.service.reranker_adapter is not None}}
        return base

    # -- research / refine ----------------------------------------------
    def research(self, owner, query, session_id=None, top_k=None, image_base64=None):
        owner = self._owner(owner)
        query = (query or "").strip()
        if not query and not image_base64:
            raise AgentError(400, "missing_query", "provide a text query, an image, or both")
        top_k = self._topk(top_k)
        sid = (session_id or "").strip() or uuid.uuid4().hex
        if session_id and self.store.get_session(owner, sid):
            raise AgentError(409, "session_exists", "session_id already exists; use /api/refine")
        with self.store.lock:
            payload = {"query": query, "session_id": self._service_sid(owner, sid), "top_k": top_k}
            if image_base64:
                payload["image_base64"] = image_base64
            result = self._call(lambda: self.service.research(payload))
            return self._persist(owner, sid, result, [query], top_k, previous=None)

    def refine(self, owner, session_id, utterance, top_k=None):
        owner = self._owner(owner)
        sid, utterance = (session_id or "").strip(), (utterance or "").strip()
        if not sid or not utterance:
            raise AgentError(400, "missing_refine_input", "session_id and utterance are required")
        with self.store.lock:
            session = self.store.get_session(owner, sid)
            if session is None:
                raise AgentError(404, "session_not_found", "unknown session_id")
            top_k = self._topk(top_k if top_k is not None else session["top_k"])
            utterances = list(session["utterances"]) + [utterance]
            service_sid = self._service_sid(owner, sid)
            try:
                result = self._with_quotes(owner, sid, lambda: self._call(lambda: self.service.refine(
                    {"session_id": service_sid, "utterance": utterance, "top_k": top_k})))
            except AgentError as exc:
                if exc.status != 404:
                    raise
                if session["state"].get("_image_required"):
                    raise AgentError(409, "image_reupload_required", "重启后图片上下文已清除；请重新上传图片发起研究")
                result = self._with_quotes(owner, sid, lambda: self._replay(service_sid, utterances, top_k))
            return self._persist(owner, sid, result, utterances, top_k, previous=session)

    def _with_quotes(self, owner, sid, operation):
        """Replan against this session's current demo quotes, not stale prices."""
        original = self.service.catalog
        current = []
        for rec in original or []:
            quote = self.store.get_quote(owner, sid, str(rec["item_id"]))
            if quote and quote["availability"] == "out_of_stock":
                continue
            current.append(dict(rec, price_usd=quote["price_usd"]) if quote else rec)
        self.service.catalog = current
        try:
            return operation()
        finally:
            self.service.catalog = original

    def _replay(self, service_sid, utterances, top_k):
        """In-memory research sessions can be lost on restart; replay deterministically."""
        result = self._call(lambda: self.service.research(
            {"query": utterances[0], "session_id": service_sid, "top_k": top_k}))
        for utterance in utterances[1:]:
            payload = {"session_id": service_sid, "utterance": utterance, "top_k": top_k}
            result = self._call(lambda payload=payload: self.service.refine(payload))
        return result

    def _persist(self, owner, sid, result, utterances, top_k, previous):
        now = self.clock()
        revision = 1 if previous is None else previous["revision"] + 1
        merchant_version = 1 if previous is None else previous["merchant_version"]
        state = dict(result.get("state") or {})
        state["_image_required"] = bool((result.get("trace", {}).get("image") or {}).get("used"))
        self.store.upsert_session(owner, sid, revision, state, utterances, top_k,
                                  merchant_version, state.get("source"), self.catalog_path, now=now)
        self.store.supersede_open_proposals(owner, sid, now=now)
        decision = (result.get("recommendation") or {}).get("decision") or {}
        recommended = decision.get("recommended_item_id")
        proposal = None
        if recommended is not None and not decision.get("abstained"):
            proposal = self._create_proposal(owner, sid, result, str(recommended),
                                             revision, merchant_version, now)
            self.store.add_event(owner, sid, "proposal_created",
                                 {"proposal_id": proposal["proposal_id"],
                                  "item_id": proposal["item_id"], "status": proposal["status"]}, now=now)
        else:
            self.store.add_event(owner, sid, "no_feasible_plan",
                                 {"reason": decision.get("fallback_reason") or "no feasible candidate"},
                                 now=now)
        return self._public_result(result, self.store.get_session(owner, sid), proposal, utterances[-1])

    def _ranked_entry(self, result, item_id):
        for entry in (result.get("ranking") or {}).get("ranked") or []:
            if str(entry.get("item_id")) == str(item_id):
                return entry
        return None

    @staticmethod
    def _candidate_snapshot(entry):
        """Server-stored, evidence-only copy of a top-3 candidate.

        The client must never be trusted to describe an item: the selection
        endpoint re-checks price/stock/constraints and rebuilds the new
        proposal's evidence from THIS snapshot, not from the old proposal and
        not from any client-supplied product attribute.
        """
        if not entry:
            return None
        return {"rank": entry.get("rank"), "item_id": str(entry.get("item_id")),
                "title": entry.get("title"), "brand": entry.get("brand"),
                "price_usd": entry.get("price_usd"), "score": entry.get("score"),
                "visual_cosine": entry.get("visual_cosine"),
                "reranker_logit": entry.get("reranker_logit"),
                "hard_constraint_ok": entry.get("hard_constraint_ok"),
                "matched_preferences": entry.get("matched_preferences") or [],
                "evidence": entry.get("evidence") or {}}

    def _create_proposal(self, owner, sid, result, item_id, revision, merchant_version, now):
        comparison = result.get("comparison") or []
        top = comparison[:3]
        eligible = [str(c["item_id"]) for c in top]
        entry = next((c for c in comparison if str(c["item_id"]) == item_id), None)
        if entry is None and top:
            entry = top[0]
            item_id = str(entry["item_id"])
        live = self._live_quote(owner, sid, item_id)
        ranked = self._ranked_entry(result, item_id) or {}
        evidence = {"catalog_fields": (entry or {}).get("evidence") or {},
                    "supported_claims": (result.get("recommendation") or {}).get("retained_claims") or [],
                    "why_ranked_here": ranked.get("why_ranked_here"),
                    "route_scores": ranked.get("route_scores"),
                    "candidates": [self._candidate_snapshot(c) for c in top]}
        return self.store.insert_proposal({
            "proposal_id": uuid.uuid4().hex, "owner": owner, "session_id": sid,
            "revision": revision, "merchant_version": merchant_version, "item_id": item_id,
            "title": (entry or {}).get("title"), "brand": (entry or {}).get("brand"),
            "price_usd": live["price_usd"], "availability": live["availability"],
            "eligible_item_ids": eligible,
            "rationale": self._rationale(result, entry or {}, live),
            "evidence_json": evidence, "state_json": result.get("state") or {},
            "status": "PROPOSED", "expires_at": now + self.ttl_seconds}, now=now)

    def _rationale(self, result, entry, live):
        price = ((result.get("state") or {}).get("hard") or {}).get("price") or {}
        lower, upper = price.get("lower"), price.get("upper")
        title = entry.get("title") or "(unknown title)"
        brand = entry.get("brand") or "(no brand field)"
        parts = []
        if isinstance(live["price_usd"], (int, float)):
            bounds = ([("下限 $%.2f" % lower)] if lower is not None else []) + \
                     ([("上限 $%.2f" % upper)] if upper is not None else [])
            clause = "目录价 $%.2f" % live["price_usd"]
            if bounds:
                clause += "，处于硬约束预算（%s）内" % "、".join(bounds)
            parts.append(clause)
        else:
            parts.append("目录未提供价格字段，未作任何预算推断")
        matched = entry.get("matched_preferences") or []
        if matched:
            parts.append("命中软偏好：" + "、".join(str(m.get("term")) for m in matched))
        parts.append("证据仅取自目录字段 title/brand/price_usd")
        parts.append("未包含配送时效、库存承诺等目录未提供的信息")
        return "%s（%s）：%s。" % (title, brand, "；".join(parts))

    @staticmethod
    def _candidate(c):
        return {"rank": c.get("rank"), "item_id": str(c.get("item_id")), "title": c.get("title"),
                "brand": c.get("brand"), "price_usd": c.get("price_usd"), "score": c.get("score"),
                "visual_cosine": c.get("visual_cosine"), "reranker_logit": c.get("reranker_logit"),
                "hard_constraint_ok": c.get("hard_constraint_ok"),
                "matched_preferences": c.get("matched_preferences") or [],
                "evidence": c.get("evidence") or {}}

    def _public_result(self, result, session, proposal, query_text):
        state = result.get("state") or {}
        comparison = result.get("comparison") or []
        label = ("手写演示目录" if self.catalog_path == os.path.abspath(DEFAULT_CATALOG)
                 else "Office 历史商品目录")
        return {
            "disclaimer": DISCLAIMER_ZH, "disclaimer_en": DISCLAIMER_EN, "source_label": SOURCE_LABEL,
            "session": {"owner": session["owner"], "session_id": session["session_id"],
                        "revision": session["revision"],
                        "merchant_version": session["merchant_version"],
                        "turn": state.get("turn"), "state": state},
            "brief": {"query": query_text, "parser": state.get("source"),
                      "hard_constraints": state.get("hard"),
                      "soft_preferences": state.get("soft_preferences"),
                      "unresolved_tokens": state.get("unresolved_tokens"),
                      "catalog": {"path": self.catalog_path,
                                  "records": len(self.service.catalog or []), "label": label},
                      "policy": "确定性规则策略，非 LLM；证据只取目录字段"},
            "candidates": [self._candidate(c) for c in comparison[:3]],
            "proposal": self._public_proposal(proposal) if proposal else None,
            "feasible": proposal is not None,
            "recommendation": (result.get("recommendation") or {}).get("decision"),
            "negotiation": result.get("negotiation"), "trace": result.get("trace"),
            "limitations": result.get("limitations") or []}

    # -- approve / reject ------------------------------------------------
    def approve(self, owner, session_id, proposal_id):
        owner = self._owner(owner)
        proposal_id = (proposal_id or "").strip()
        if not proposal_id:
            raise AgentError(400, "missing_proposal_id", "proposal_id is required")
        with self.store.lock:
            proposal = self.store.get_proposal(proposal_id)
            self._bind(proposal, owner, session_id)
            existing = self.store.get_reservation_by_proposal(proposal_id)
            if proposal["status"] == "APPROVED" and existing:
                return self._approve_response(proposal, existing, idempotent=True)
            if proposal["status"] == "REJECTED":
                raise AgentError(409, "proposal_rejected", "提案已被拒绝；请重新研究 (replan)")
            if proposal["status"] == "SUPERSEDED":
                raise AgentError(409, "proposal_superseded", "提案已被新的研究结果取代；请重新确认")
            if proposal["status"] in ("NEEDS_REVIEW", "EXPIRED"):
                raise AgentError(409, "quote_changed" if proposal["status"] == "NEEDS_REVIEW"
                                 else "proposal_expired", "提案需要重新研究 (replan)")
            now = self.clock()
            if now >= (proposal.get("expires_at") or 0):
                self.store.update_proposal_status(proposal_id, "EXPIRED", now=now)
                self.store.add_event(owner, proposal["session_id"], "proposal_expired",
                                     {"proposal_id": proposal_id}, now=now)
                raise AgentError(409, "proposal_expired", "该提案已过期；请重新研究 (replan)")
            session = self.store.get_session(owner, proposal["session_id"])
            if session is None:
                raise AgentError(409, "session_lost", "会话状态缺失；请重新研究 (replan)")
            if session["revision"] != proposal["revision"]:
                raise AgentError(409, "revision_conflict", "研究结果已更新；请重新确认 (replan)")
            if session["merchant_version"] != proposal["merchant_version"]:
                raise AgentError(409, "quote_changed", "报价版本已变化；请重新研究 (replan)")
            if proposal["item_id"] not in (proposal["eligible_item_ids"] or []):
                raise AgentError(409, "not_eligible", "候选不在当前 top-3 之内；请重新确认")
            live = self._live_quote(owner, proposal["session_id"], proposal["item_id"])
            if live["availability"] != "in_stock":
                self.store.update_proposal_status(proposal_id, "NEEDS_REVIEW", now=now)
                raise AgentError(409, "out_of_stock", "该商品当前不可供应；请重新研究 (replan)")
            if not _price_equal(live["price_usd"], proposal["price_usd"]):
                self.store.update_proposal_status(proposal_id, "NEEDS_REVIEW", now=now)
                raise AgentError(409, "quote_changed", "报价已变化；请重新研究 (replan)")
            if not self._recheck_constraints(proposal, live):
                raise AgentError(409, "constraint_violation", "硬约束在当前报价下不再满足；请重新研究 (replan)")
            reservation = self.store.insert_reservation({
                "reservation_id": uuid.uuid4().hex, "proposal_id": proposal_id, "owner": owner,
                "session_id": proposal["session_id"], "item_id": proposal["item_id"],
                "title": proposal["title"], "brand": proposal["brand"],
                "price_usd": proposal["price_usd"], "quantity": 1, "status": "draft_reserved",
                "note": DISCLAIMER_ZH, "created_at": now})
            self.store.update_proposal_status(proposal_id, "APPROVED", now=now)
            self.store.add_event(owner, proposal["session_id"], "reservation_created",
                                 {"proposal_id": proposal_id,
                                  "reservation_id": reservation["reservation_id"],
                                  "item_id": proposal["item_id"]}, now=now)
            return self._approve_response(proposal, reservation, idempotent=False)

    def _recheck_constraints(self, proposal, live):
        rec = dict(self.catalog_by_id.get(str(proposal["item_id"]), {}))
        if not rec:
            return False
        rec["price_usd"] = live["price_usd"]
        state = dict(proposal.get("constraints_state") or {})
        hard = dict(state.get("hard") or {})
        if not hard:
            return True
        hard.setdefault("price", {"upper": None, "lower": None})
        hard.setdefault("must_include", [])
        hard.setdefault("must_exclude", [])
        hard.setdefault("brands", [])
        state["hard"] = hard
        kept, _ = qs.hard_filter([rec], state)
        return bool(kept)

    def _verify(self, proposal, readback):
        checks = {"reservation_exists": readback is not None}
        if readback is None:
            return False, checks
        checks["same_proposal"] = readback.get("proposal_id") == proposal["proposal_id"]
        checks["same_item"] = str(readback.get("item_id")) == str(proposal["item_id"])
        checks["same_price"] = _price_equal(readback.get("price_usd"), proposal["price_usd"])
        checks["draft_status"] = readback.get("status") == "draft_reserved"
        return all(checks.values()), checks

    def _approve_response(self, proposal, reservation, idempotent):
        readback = self.store.get_reservation(reservation["reservation_id"])
        verified, checks = self._verify(proposal, readback)
        shown = dict(proposal, status="APPROVED")
        return {"disclaimer": DISCLAIMER_ZH, "disclaimer_en": DISCLAIMER_EN,
                "idempotent": idempotent, "proposal": self._public_proposal(shown),
                "reservation": readback, "readback": readback, "verified": verified,
                "verification_checks": checks,
                "outcome": {"kind": "local_draft_reservation", "ordered": False, "charged": False,
                            "note": "本地采购草稿，不下单、不扣款"}}

    def reject(self, owner, session_id, proposal_id):
        owner = self._owner(owner)
        proposal_id = (proposal_id or "").strip()
        if not proposal_id:
            raise AgentError(400, "missing_proposal_id", "proposal_id is required")
        with self.store.lock:
            proposal = self.store.get_proposal(proposal_id)
            self._bind(proposal, owner, session_id)
            if proposal["status"] == "REJECTED":
                return {"disclaimer": DISCLAIMER_ZH, "disclaimer_en": DISCLAIMER_EN,
                        "idempotent": True, "proposal": self._public_proposal(proposal),
                        "reservation": None}
            if proposal["status"] == "APPROVED":
                raise AgentError(409, "already_approved", "提案已确认，无法改为拒绝")
            now = self.clock()
            proposal = self.store.update_proposal_status(proposal_id, "REJECTED", now=now)
            self.store.add_event(owner, proposal["session_id"], "proposal_rejected",
                                 {"proposal_id": proposal_id}, now=now)
            return {"disclaimer": DISCLAIMER_ZH, "disclaimer_en": DISCLAIMER_EN,
                    "idempotent": False, "proposal": self._public_proposal(proposal),
                    "reservation": None,
                    "outcome": {"kind": "rejected", "ordered": False, "charged": False,
                                "note": "已拒绝，没有任何本地预订"}}

    # -- candidate selection (propose only, never a reservation) --------
    SELECTION_SOURCES = ("human", "agent_review")

    def select_candidate(self, owner, session_id, proposal_id, item_id,
                         selection_source="human", reason=None, review_revision=None,
                         review_merchant_version=None):
        """Turn one of the top-3 candidates into a NEW pending proposal.

        This creates no reservation and never approves anything; the user still
        has to click confirm.  Every product attribute used for the new
        proposal comes from the server-stored candidate snapshot, and the new
        proposal replaces the old one (its approval is then refused by the
        existing approve logic because it is SUPERSEDED).
        """
        owner = self._owner(owner)
        session_id = (session_id or "").strip()
        proposal_id = (proposal_id or "").strip()
        item_id = str(item_id or "").strip()
        if not proposal_id:
            raise AgentError(400, "missing_proposal_id", "proposal_id is required")
        if not item_id:
            raise AgentError(400, "missing_item_id", "item_id is required")
        source = (selection_source or "human").strip() or "human"
        if source not in self.SELECTION_SOURCES:
            raise AgentError(400, "invalid_selection_source",
                             "selection_source must be human or agent_review")
        reason = (reason or "").strip()[:600]

        def _as_int(value, label):
            if value is None:
                return None
            try:
                return int(value)
            except (TypeError, ValueError) as exc:
                raise AgentError(400, "invalid_" + label, "%s must be an integer" % label) from exc

        review_revision = _as_int(review_revision, "review_revision")
        review_merchant_version = _as_int(review_merchant_version, "review_merchant_version")
        if source == "agent_review" and (review_revision is None or review_merchant_version is None or not reason):
            raise AgentError(400, "review_context_required", "采纳 Agent 建议须提供来源版本和选择理由")
        with self.store.lock:
            proposal = self.store.get_proposal(proposal_id)
            self._bind(proposal, owner, session_id)
            if proposal["status"] != "PROPOSED":
                raise AgentError(409, "proposal_not_selectable",
                                 "只有待确认（PROPOSED）的提案可以选择候选；请重新研究 (replan)")
            now = self.clock()
            if now >= (proposal.get("expires_at") or 0):
                self.store.update_proposal_status(proposal_id, "EXPIRED", now=now)
                self.store.add_event(owner, proposal["session_id"], "proposal_expired",
                                     {"proposal_id": proposal_id}, now=now)
                raise AgentError(409, "proposal_expired", "该提案已过期；请重新研究 (replan)")
            session = self.store.get_session(owner, proposal["session_id"])
            if session is None:
                raise AgentError(409, "session_lost", "会话状态缺失；请重新研究 (replan)")
            if session["revision"] != proposal["revision"]:
                raise AgentError(409, "revision_conflict", "研究结果已更新；请重新确认 (replan)")
            if session["merchant_version"] != proposal["merchant_version"]:
                raise AgentError(409, "quote_changed", "报价版本已变化；请重新研究 (replan)")
            if review_revision is not None and review_revision != proposal["revision"]:
                raise AgentError(409, "review_stale",
                                 "Agent 建议针对的 revision 已过期；请重新审阅")
            if (review_merchant_version is not None
                    and review_merchant_version != proposal["merchant_version"]):
                raise AgentError(409, "review_stale",
                                 "Agent 建议针对的报价版本已过期；请重新审阅")
            if item_id not in (proposal["eligible_item_ids"] or []):
                raise AgentError(409, "not_eligible", "候选不在当前 top-3 之内；请重新确认")
            snapshot = None
            for slot in (proposal.get("evidence") or {}).get("candidates") or []:
                if slot and str(slot.get("item_id")) == item_id:
                    snapshot = slot
                    break
            if snapshot is None:
                raise AgentError(409, "candidate_snapshot_missing",
                                 "服务端未保存该候选的证据快照；请重新研究 (replan)")
            live = self._live_quote(owner, proposal["session_id"], item_id)
            if live["availability"] != "in_stock":
                raise AgentError(409, "out_of_stock", "该候选当前不可供应；请重新研究 (replan)")
            if not _price_equal(live["price_usd"], snapshot.get("price_usd")):
                raise AgentError(409, "quote_changed", "候选报价与审阅快照不符；请重新研究 (replan)")
            if not self._recheck_constraints_for(proposal, item_id, live):
                raise AgentError(409, "constraint_violation",
                                 "硬约束在当前报价下不再满足；请重新研究 (replan)")
            self.store.supersede_open_proposals(owner, proposal["session_id"], now=now)
            new_revision = self.store.bump_revision(owner, proposal["session_id"], now=now)
            evidence = {"catalog_fields": snapshot.get("evidence") or {},
                        "supported_claims": [],
                        "why_ranked_here": None,
                        "candidate_snapshot": snapshot,
                        "selection": {"selection_source": source, "reason": reason or None,
                                      "from_proposal_id": proposal_id,
                                      "selected_item_id": item_id},
                        "candidates": (proposal.get("evidence") or {}).get("candidates")}
            new_proposal = self.store.insert_proposal({
                "proposal_id": uuid.uuid4().hex, "owner": owner,
                "session_id": proposal["session_id"],
                "revision": new_revision or proposal["revision"],
                "merchant_version": proposal["merchant_version"], "item_id": item_id,
                "title": snapshot.get("title"), "brand": snapshot.get("brand"),
                "price_usd": live["price_usd"], "availability": live["availability"],
                "eligible_item_ids": list(proposal["eligible_item_ids"]),
                "rationale": self._selection_rationale(snapshot, live, source, reason),
                "evidence_json": evidence,
                "state_json": proposal.get("constraints_state") or {},
                "status": "PROPOSED",
                "expires_at": proposal["expires_at"]}, now=now)
            self.store.add_event(owner, proposal["session_id"], "candidate_selected",
                                 {"proposal_id": new_proposal["proposal_id"],
                                  "superseded_proposal_id": proposal_id,
                                  "item_id": item_id, "selection_source": source}, now=now)
            return {"disclaimer": DISCLAIMER_ZH, "disclaimer_en": DISCLAIMER_EN,
                    "selected_item_id": item_id, "selection_source": source,
                    "reason": reason or None, "creates_reservation": False,
                    "proposal": self._public_proposal(new_proposal),
                    "note": ("已按候选快照生成新的待确认提案，取代原提案；"
                             "不会创建草稿，仍需你点击确认。")}

    def _recheck_constraints_for(self, proposal, item_id, live):
        rec = dict(self.catalog_by_id.get(str(item_id), {}))
        if not rec:
            return False
        rec["price_usd"] = live["price_usd"]
        state = dict(proposal.get("constraints_state") or {})
        hard = dict(state.get("hard") or {})
        if not hard:
            return True
        hard.setdefault("price", {"upper": None, "lower": None})
        hard.setdefault("must_include", [])
        hard.setdefault("must_exclude", [])
        hard.setdefault("brands", [])
        state["hard"] = hard
        kept, _ = qs.hard_filter([rec], state)
        return bool(kept)

    def _recheck_constraints(self, proposal, live):
        return self._recheck_constraints_for(proposal, proposal["item_id"], live)

    def _selection_rationale(self, snapshot, live, source, reason):
        title = snapshot.get("title") or "(unknown title)"
        brand = snapshot.get("brand") or "(no brand field)"
        parts = []
        if isinstance(live["price_usd"], (int, float)):
            parts.append("当前演示报价 $%.2f" % live["price_usd"])
        else:
            parts.append("目录未提供价格字段")
        parts.append("证据快照来自研究阶段服务端保存的候选字段")
        parts.append("未新增目录未提供的商品特征")
        if source == "agent_review" and reason:
            parts.append("理由来自 Agent 建议（非目录事实）：%s" % reason)
        elif source == "agent_review":
            parts.append("由 Agent 审阅建议选中（建议非目录事实）")
        else:
            parts.append("由用户直接选择候选")
        return "%s（%s）：%s。" % (title, brand, "；".join(parts))

    # -- simulated quote change -----------------------------------------
    def simulate_quote(self, owner, session_id, proposal_id=None, item_id=None,
                       price_usd=None, availability=None):
        with self.store.lock:
            return self._simulate_quote(owner, session_id, proposal_id, item_id, price_usd, availability)

    def _simulate_quote(self, owner, session_id, proposal_id=None, item_id=None,
                        price_usd=None, availability=None):
        owner = self._owner(owner)
        session_id = (session_id or "").strip()
        if not session_id:
            raise AgentError(400, "missing_session_id", "session_id is required")
        if self.store.get_session(owner, session_id) is None:
            raise AgentError(404, "session_not_found", "unknown session_id")
        proposal = None
        if proposal_id:
            proposal = self.store.get_proposal(proposal_id)
            self._bind(proposal, owner, session_id)
        if price_usd is None and availability is None:
            raise AgentError(400, "missing_quote_change", "provide price_usd and/or availability")
        if price_usd is not None:
            price_usd = _positive(price_usd)
        if availability is not None and availability not in AVAILABILITIES:
            raise AgentError(400, "invalid_availability", "availability must be in_stock or out_of_stock")
        target = str(item_id if item_id is not None else (proposal or {}).get("item_id") or "").strip()
        if not target:
            raise AgentError(400, "missing_item_id", "item_id is required")
        if target not in self.catalog_by_id:
            raise AgentError(404, "unknown_item", "item_id is not in the catalog")
        now = self.clock()
        current = self._live_quote(owner, session_id, target)
        new_price = price_usd if price_usd is not None else current["price_usd"]
        new_availability = availability if availability is not None else current["availability"]
        self.store.set_quote(owner, session_id, target, new_price, new_availability)
        merchant_version = self.store.bump_merchant_version(owner, session_id, now=now)
        if proposal:
            proposal = self.store.update_proposal_status(proposal["proposal_id"], "NEEDS_REVIEW", now=now)
        else:
            for open_proposal in self.store.list_proposals(owner, session_id):
                if open_proposal["status"] in ("PROPOSED", "NEEDS_REVIEW"):
                    self.store.update_proposal_status(open_proposal["proposal_id"], "NEEDS_REVIEW", now=now)
        self.store.add_event(owner, session_id, "quote_simulated",
                             {"item_id": target, "price_usd": new_price,
                              "availability": new_availability, "merchant_version": merchant_version,
                              "proposal_id": proposal["proposal_id"] if proposal else None}, now=now)
        return {"disclaimer": DISCLAIMER_ZH, "disclaimer_en": DISCLAIMER_EN,
                "replan_required": True, "never_auto_buy": True, "merchant_version": merchant_version,
                "quote": {"item_id": target, "price_usd": new_price, "availability": new_availability},
                "proposal": self._public_proposal(proposal) if proposal else None,
                "note": "报价仅在此演示会话内生效；提案进入 NEEDS_REVIEW，必须重新研究后才能确认。"}

    # -- readback --------------------------------------------------------
    def get_session(self, owner, session_id):
        owner = self._owner(owner)
        session = self.store.get_session(owner, (session_id or "").strip())
        if session is None:
            raise AgentError(404, "session_not_found", "unknown session_id")
        proposals = self.store.list_proposals(owner, session["session_id"])
        return {"disclaimer": DISCLAIMER_ZH, "disclaimer_en": DISCLAIMER_EN,
                "session": {"owner": session["owner"], "session_id": session["session_id"],
                            "revision": session["revision"],
                            "merchant_version": session["merchant_version"],
                            "turn": (session["state"] or {}).get("turn"), "state": session["state"]},
                "proposal": self._public_proposal(proposals[0]) if proposals else None,
                "proposals": [self._public_proposal(p) for p in proposals],
                "reservations": self.store.list_reservations(owner, session["session_id"]),
                "events": self.store.list_events(owner, session["session_id"])}

    def history(self, owner):
        owner = self._owner(owner)
        return {"disclaimer": DISCLAIMER_ZH, "disclaimer_en": DISCLAIMER_EN,
                "sessions": [{"session_id": s["session_id"], "revision": s["revision"],
                              "merchant_version": s["merchant_version"],
                              "turn": (s["state"] or {}).get("turn"), "updated_at": s["updated_at"]}
                             for s in self.store.list_sessions(owner)],
                "proposals": [self._public_proposal(p) for p in self.store.list_proposals(owner)],
                "reservations": self.store.list_reservations(owner),
                "events": self.store.list_events(owner, limit=100)}
