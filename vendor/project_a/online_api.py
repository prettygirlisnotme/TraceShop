#!/usr/bin/env python3
"""Local HTTP API for the evidence-grounded Shopping Research pipeline.

This is deliberately a thin serving layer over the repository's verified CPU
components.  It keeps QueryState across turns, applies hard constraints before
ranking, exposes the ranking trace, and passes the final structured decision
through the reusable evidence guard.  It does not pretend to call an LLM.

The text path uses only the Python standard library. Optional image and learned
reranking adapters lazily import the existing ML stack on first use. The server
binds to loopback by default. It is a demo/research service, not an
internet-facing production server: sessions are in memory and there is no
authentication or rate limit.
"""

import argparse
import base64
import binascii
import hashlib
import io
import json
import os
import sys
import threading
import time
import uuid
import warnings
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, unquote, urlparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import evidence_guard as eg  # noqa: E402
import querystate_session as qs  # noqa: E402
import search_mvp as sm  # noqa: E402


API_SCHEMA_VERSION = 1
MAX_BODY_BYTES = 8_000_000
MAX_IMAGE_BYTES = 5_000_000
MAX_IMAGE_PIXELS = 25_000_000
DEFAULT_CATALOG = "data/shopping/office_catalog.jsonl"
UI_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "shopping_research_ui.html")


class ApiError(Exception):
    def __init__(self, status, code, message):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message


class VisualSearchAdapter:
    """Lazy CLIP image encoder over the already-validated Office image cache.

    Request images are decoded in memory. Only the embedding and a SHA-256
    digest are kept in a session; raw bytes/base64 are never persisted.
    """

    def __init__(self, clip_emb, clip_mask, clip_ids,
                 model_name="openai/clip-vit-large-patch14", device=None):
        self.clip_emb = os.path.abspath(clip_emb) if clip_emb else None
        self.clip_mask = os.path.abspath(clip_mask) if clip_mask else None
        self.clip_ids = os.path.abspath(clip_ids) if clip_ids else None
        self.model_name = model_name
        self.requested_device = device
        self.lock = threading.RLock()
        self.loaded = False
        self.load_error = None
        self.model = None
        self.processor = None
        self.device = None
        self.item_embeddings = None
        self.item_ids = None
        self.n_catalog = None

    @property
    def configured(self):
        return bool(self.clip_emb and self.clip_mask and self.clip_ids and self.model_name)

    def health(self):
        return {
            "configured": self.configured,
            "loaded": self.loaded,
            "load_error": self.load_error,
            "model": self.model_name,
            "device": self.device,
            "visual_candidates": len(self.item_ids) if self.item_ids is not None else None,
            "raw_images_persisted": False,
        }

    @staticmethod
    def _decode_image(image_base64):
        if not isinstance(image_base64, str) or not image_base64.strip():
            raise ApiError(400, "invalid_image", "image_base64 must be a non-empty string")
        encoded = image_base64.strip()
        mime = None
        if encoded.startswith("data:"):
            try:
                header, encoded = encoded.split(",", 1)
            except ValueError as exc:
                raise ApiError(400, "invalid_image", "invalid image data URL") from exc
            if not header.casefold().startswith("data:image/") or ";base64" not in header.casefold():
                raise ApiError(400, "invalid_image", "data URL must contain a base64 image")
            mime = header[5:].split(";", 1)[0].casefold()
        try:
            raw = base64.b64decode(encoded, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise ApiError(400, "invalid_image", "image_base64 is not valid base64") from exc
        if not raw or len(raw) > MAX_IMAGE_BYTES:
            raise ApiError(
                400, "invalid_image_size",
                "decoded image must be 1..%d bytes" % MAX_IMAGE_BYTES,
            )

        try:
            from PIL import Image, UnidentifiedImageError
        except ImportError as exc:
            raise ApiError(503, "image_backend_unavailable", "Pillow is not installed") from exc
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("error", Image.DecompressionBombWarning)
                pil = Image.open(io.BytesIO(raw))
                pil.load()
            width, height = pil.size
            if width <= 0 or height <= 0 or width * height > MAX_IMAGE_PIXELS:
                raise ApiError(
                    400, "invalid_image_dimensions",
                    "image must contain at most %d pixels" % MAX_IMAGE_PIXELS,
                )
            pil = pil.convert("RGB")
        except ApiError:
            raise
        except (Image.DecompressionBombError, Image.DecompressionBombWarning,
                UnidentifiedImageError, OSError, ValueError) as exc:
            raise ApiError(400, "invalid_image", "decoded payload is not a safe image") from exc
        return pil, {
            "sha256": hashlib.sha256(raw).hexdigest(),
            "decoded_bytes": len(raw),
            "width": width,
            "height": height,
            "mime": mime or "detected_by_pillow",
        }

    def _ensure_loaded(self, catalog_size):
        if self.loaded:
            if self.n_catalog != catalog_size:
                raise ApiError(503, "image_backend_unavailable", "visual assets/catalog size mismatch")
            return
        if not self.configured:
            raise ApiError(503, "image_not_configured", "CLIP assets are not configured")
        try:
            import numpy as np
            import torch
            from transformers import CLIPModel, CLIPProcessor
            from clip_crossmodal_bench import remap_assets

            emb = np.load(self.clip_emb, allow_pickle=False)
            mask = np.load(self.clip_mask, allow_pickle=True)
            with open(self.clip_ids, "r", encoding="utf-8") as fh:
                ids_order = json.load(fh)
            emb_r, mask_r = remap_assets(emb, mask, ids_order, catalog_size)
            valid = np.where(mask_r)[0].astype(np.int64)
            rows = np.asarray(emb_r[valid], dtype=np.float32)
            norms = np.sqrt((rows * rows).sum(axis=1))
            if not len(valid) or bool((norms <= 0).any()):
                raise ValueError("visual cache contains no valid non-zero rows")
            rows /= norms[:, None]

            if self.requested_device:
                device = self.requested_device
            else:
                device = "cuda:0" if torch.cuda.is_available() else "cpu"
            t0 = time.time()
            model = CLIPModel.from_pretrained(
                self.model_name, torch_dtype=torch.float32, local_files_only=True
            ).to(device).eval()
            processor = CLIPProcessor.from_pretrained(
                self.model_name, local_files_only=True
            )

            self.item_embeddings = rows
            self.item_ids = valid.tolist()
            self.n_catalog = catalog_size
            self.device = device
            self.model = model
            self.processor = processor
            self.loaded = True
            self.load_error = None
            self.load_seconds = round(time.time() - t0, 4)
        except ApiError:
            raise
        except Exception as exc:
            self.load_error = "%s: %s" % (type(exc).__name__, exc)
            raise ApiError(503, "image_backend_unavailable", self.load_error) from exc

    def encode_base64(self, image_base64, catalog_size):
        pil, metadata = self._decode_image(image_base64)
        with self.lock:
            self._ensure_loaded(catalog_size)
            try:
                import numpy as np
                import torch

                t0 = time.time()
                inputs = self.processor(images=[pil], return_tensors="pt").to(self.device)
                with torch.no_grad():
                    features = self.model.get_image_features(**inputs)
                vector = features.float().cpu().numpy().astype(np.float32).reshape(-1)
                norm = float(np.sqrt((vector * vector).sum()))
                if not norm or not bool(np.isfinite(vector).all()):
                    raise ValueError("CLIP returned a non-finite or zero vector")
                vector /= norm
                if vector.shape[0] != self.item_embeddings.shape[1]:
                    raise ValueError("query/cache embedding dimensions differ")
                metadata.update({
                    "dim": int(vector.shape[0]),
                    "encode_seconds": round(time.time() - t0, 4),
                    "model": self.model_name,
                    "device": self.device,
                    "raw_image_persisted": False,
                })
                return vector, metadata
            except ApiError:
                raise
            except Exception as exc:
                raise ApiError(
                    503, "image_backend_unavailable",
                    "%s: %s" % (type(exc).__name__, exc),
                ) from exc

    def score_vector(self, vector):
        with self.lock:
            if not self.loaded:
                raise ApiError(503, "image_backend_unavailable", "visual backend is not loaded")
            similarities = self.item_embeddings @ vector
            return {
                int(iid): float(score)
                for iid, score in zip(self.item_ids, similarities.tolist())
            }


class CrossEncoderRerankAdapter:
    """Lazy ESCI-trained cross-encoder for a bounded feasible candidate pool."""

    def __init__(self, checkpoint, model_name="cross-encoder/ms-marco-MiniLM-L-6-v2",
                 device=None, max_len=256, batch_size=64):
        self.checkpoint = os.path.abspath(checkpoint) if checkpoint else None
        self.model_name = model_name
        self.requested_device = device
        self.max_len = int(max_len)
        self.batch_size = int(batch_size)
        self.lock = threading.RLock()
        self.loaded = False
        self.load_error = None
        self.model = None
        self.tokenizer = None
        self.device = None
        self.checkpoint_epoch = None
        self.checkpoint_size_bytes = None
        self.load_seconds = None

    @property
    def configured(self):
        return bool(self.checkpoint and self.model_name)

    def health(self):
        return {
            "configured": self.configured,
            "loaded": self.loaded,
            "load_error": self.load_error,
            "model": self.model_name,
            "checkpoint": self.checkpoint,
            "checkpoint_loaded": self.loaded,
            "checkpoint_epoch": self.checkpoint_epoch,
            "checkpoint_size_bytes": self.checkpoint_size_bytes,
            "device": self.device,
            "max_len": self.max_len,
            "batch_size": self.batch_size,
            "load_seconds": self.load_seconds,
        }

    @staticmethod
    def product_text(rec):
        """Map Office fields to the ESCI training-time text layout."""
        parts = []
        for field in ("title", "brand", "color"):
            value = rec.get(field)
            if value:
                parts.append(str(value))
        for field in ("features", "description"):
            value = rec.get(field)
            if isinstance(value, list):
                parts.extend(str(x) for x in value if x)
            elif value:
                parts.append(str(value))
        return " ".join(parts)

    def _ensure_loaded(self):
        if self.loaded:
            return
        if not self.configured:
            raise ApiError(503, "reranker_not_configured", "cross-encoder is not configured")
        if self.max_len <= 0 or self.batch_size <= 0:
            raise ApiError(503, "reranker_backend_unavailable", "max_len and batch_size must be positive")
        try:
            import torch
            from transformers import AutoModelForSequenceClassification, AutoTokenizer

            if not os.path.isfile(self.checkpoint):
                raise FileNotFoundError(self.checkpoint)
            device = self.requested_device or ("cuda:0" if torch.cuda.is_available() else "cpu")
            t0 = time.time()
            tokenizer = AutoTokenizer.from_pretrained(
                self.model_name, local_files_only=True
            )
            model = AutoModelForSequenceClassification.from_pretrained(
                self.model_name, local_files_only=True, num_labels=1,
                torch_dtype=torch.float32,
            )
            state = torch.load(self.checkpoint, map_location="cpu")
            model.load_state_dict(state["model"])
            model.to(device).eval()

            self.tokenizer = tokenizer
            self.model = model
            self.device = device
            self.checkpoint_epoch = state.get("epoch")
            self.checkpoint_size_bytes = os.path.getsize(self.checkpoint)
            self.load_seconds = round(time.time() - t0, 4)
            self.loaded = True
            self.load_error = None
        except ApiError:
            raise
        except Exception as exc:
            self.load_error = "%s: %s" % (type(exc).__name__, exc)
            raise ApiError(503, "reranker_backend_unavailable", self.load_error) from exc

    def score(self, query_text, candidates):
        if not query_text or not candidates:
            return {}, {"scored_candidates": 0, "score_seconds": 0.0}
        with self.lock:
            self._ensure_loaded()
            try:
                import math
                import torch

                pairs = [(query_text, self.product_text(rec)) for rec in candidates]
                values = []
                t0 = time.time()
                with torch.no_grad():
                    for start in range(0, len(pairs), self.batch_size):
                        encoded = self.tokenizer(
                            pairs[start:start + self.batch_size], truncation=True,
                            max_length=self.max_len, padding="max_length",
                            return_tensors="pt",
                        ).to(self.device)
                        logits = self.model(**encoded).logits[:, 0]
                        values.extend(float(x) for x in logits.float().cpu().tolist())
                if not all(math.isfinite(x) for x in values):
                    raise ValueError("cross-encoder returned non-finite logits")
                scores = {
                    rec["item_id"]: value for rec, value in zip(candidates, values)
                }
                return scores, {
                    "scored_candidates": len(scores),
                    "candidate_item_ids": [rec["item_id"] for rec in candidates],
                    "score_seconds": round(time.time() - t0, 4),
                    "logits_finite": True,
                    "model": self.model_name,
                    "checkpoint": self.checkpoint,
                    "checkpoint_loaded": True,
                    "checkpoint_epoch": self.checkpoint_epoch,
                    "device": self.device,
                    "max_len": self.max_len,
                    "batch_size": self.batch_size,
                }
            except ApiError:
                raise
            except Exception as exc:
                raise ApiError(
                    503, "reranker_backend_unavailable",
                    "%s: %s" % (type(exc).__name__, exc),
                ) from exc


def _state_query_text(state):
    """Deterministic positive query projection from the persistent QueryState."""
    terms = []
    for value in (
        list(state.get("query_tokens") or [])
        + list(state.get("hard", {}).get("must_include") or [])
        + list(state.get("hard", {}).get("brands") or [])
        + [p.get("term") for p in state.get("soft_preferences") or []]
    ):
        text = str(value or "").strip()
        if text and text.casefold() not in {x.casefold() for x in terms}:
            terms.append(text)
    return " ".join(terms)


def load_catalog(path):
    """Load the canonical catalog once; invalid schema rows are ignored."""
    records = []
    with open(path, "r", encoding="utf-8") as fh:
        for line_no, line in enumerate(fh, 1):
            if not line.strip():
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError("invalid catalog JSON at line %d: %s" % (line_no, exc))
            if rec.get("schema_version") == sm.SCHEMA_VERSION:
                records.append(rec)
    records.sort(key=lambda r: r["item_id"])
    if not records:
        raise ValueError("catalog has no schema_version=%s records" % sm.SCHEMA_VERSION)
    return records


def _supported_claims(ranked):
    """Create only literal catalog claims, then run the same mode-C claim guard."""
    claims = []
    idx = 0
    for rec in ranked[:3]:
        iid = str(rec["item_id"])
        for field, value in (
            ("title", rec.get("title")),
            ("brand", rec.get("brand")),
            ("price_usd", rec.get("price_usd")),
        ):
            if value is None or value == "":
                continue
            idx += 1
            if field == "price_usd":
                text = "%s has catalog price $%.2f." % (rec.get("title") or iid, float(value))
            else:
                text = "%s: %s." % (field, value)
            claims.append({
                "i": idx,
                "text": text,
                "status": "supported",
                "supporting_citation": "%s/%s" % (iid, field),
                "hard_constraint_violation": False,
            })
    return claims


def _guarded_output(state, turn_result):
    """Adapt live ranked records to the already-evaluated evidence_guard contract."""
    ranked = turn_result["ranked"]
    candidates = []
    for rec in ranked:
        candidates.append({
            "item_id": str(rec["item_id"]),
            "evidence": {
                "title": rec.get("title"),
                "brand": rec.get("brand"),
                "price_usd": rec.get("price_usd"),
                "evidence_snippets": rec.get("evidence_snippets") or {},
            },
        })
    best = str(ranked[0]["item_id"]) if ranked else None
    scenario = {
        "source": "office",
        "query_intent": {"price_upper": state["hard"]["price"].get("upper")},
        "candidates": candidates,
        "decision_trace": {"best_of_candidates": best},
    }
    raw_claims = _supported_claims(ranked)
    retained, dropped = eg.guard_claims(raw_claims, "C")
    raw_decision = {
        "recommended_item_id": best,
        "recommended_item_valid": best is not None,
        "hard_constraint_violation": False,
    }
    decision = eg.guard_decision(scenario, raw_decision, retained, "C")
    return {
        "policy": "evidence_guard mode-C adapter; exact structured catalog claims only",
        "generator_mode": "deterministic_template_no_llm",
        "decision": decision,
        "retained_claims": retained,
        "dropped_claims": dropped,
        "construction_note": (
            "Unsupported free-form generation is outside this live CPU path. "
            "Every returned claim is copied from a ranked catalog field and guarded."
        ),
    }


def _comparison(ranked):
    """Structured, evidence-only comparison suitable for a UI table."""
    return [{
        "rank": r["rank"],
        "item_id": r["item_id"],
        "title": r.get("title"),
        "brand": r.get("brand"),
        "price_usd": r.get("price_usd"),
        "score": r.get("fused_score"),
        "visual_cosine": r.get("route_scores", {}).get("visual_cosine"),
        "reranker_logit": r.get("route_scores", {}).get("reranker_logit"),
        "rank_without_image": r.get("rank_without_image"),
        "rank_before_reranker": r.get("rank_before_reranker"),
        "rerank_delta": r.get("rerank_delta"),
        "rank_delta": r.get("rank_delta"),
        "hard_constraint_ok": True,
        "matched_preferences": [
            x for x in r.get("route_scores", {}).get("preference_detail", [])
            if x.get("matched")
        ],
        "evidence": r.get("evidence_snippets") or {},
    } for r in ranked]


def _public_trace(state, turn_result, negotiation, guarded):
    return {
        "turn": state["turn"],
        "parser": state["source"],
        "hard_constraints": state["hard"],
        "soft_preferences": state["soft_preferences"],
        "unresolved_tokens": state["unresolved_tokens"],
        "stage_counts": turn_result["stage_counts"],
        "ranked_item_ids": [r["item_id"] for r in turn_result["ranked"]],
        "image": turn_result.get("visual", {"used": False}),
        "reranker": turn_result.get("reranker", {"used": False}),
        "rejected_near_misses": turn_result["rejected_top_by_lexical"],
        "negotiation_needed": negotiation["needed"],
        "guard": {
            "recommended_item_id": guarded["decision"]["recommended_item_id"],
            "fallback": guarded["decision"]["fallback"],
            "abstained": guarded["decision"]["abstained"],
            "retained_claims": len(guarded["retained_claims"]),
            "dropped_claims": len(guarded["dropped_claims"]),
        },
    }


class ResearchService:
    """Thread-safe in-memory session facade over QueryState + ranking + guard."""

    def __init__(self, catalog_path=DEFAULT_CATALOG, visual_adapter=None,
                 visual_weight=0.5, reranker_adapter=None, reranker_weight=0.7):
        self.catalog_path = os.path.abspath(catalog_path)
        self.catalog = None
        self.catalog_error = None
        self.visual_adapter = visual_adapter
        self.visual_weight = float(visual_weight)
        self.reranker_adapter = reranker_adapter
        self.reranker_weight = float(reranker_weight)
        self.sessions = {}
        self.lock = threading.RLock()
        try:
            self.catalog = load_catalog(self.catalog_path)
        except (OSError, ValueError) as exc:
            self.catalog_error = str(exc)

    def health(self):
        visual_health = (
            self.visual_adapter.health()
            if self.visual_adapter is not None
            else {
                "configured": False,
                "loaded": False,
                "load_error": None,
                "raw_images_persisted": False,
            }
        )
        reranker_health = (
            self.reranker_adapter.health()
            if self.reranker_adapter is not None
            else {
                "configured": False,
                "loaded": False,
                "load_error": None,
            }
        )
        return {
            "status": "ok" if self.catalog is not None else "degraded",
            "schema_version": API_SCHEMA_VERSION,
            "catalog": {
                "path": self.catalog_path,
                "loaded": self.catalog is not None,
                "records": len(self.catalog or []),
                "error": self.catalog_error,
            },
            "sessions": len(self.sessions),
            "capabilities": {
                "single_turn_text_search": True,
                "multi_turn_refinement": True,
                "hard_constraint_filtering": True,
                "constraint_negotiation": True,
                "evidence_guard": True,
                "image_query_online": bool(visual_health["configured"]),
                "learned_reranker_online": bool(reranker_health["configured"]),
                "llm_generation_online": False,
            },
            "visual_backend": visual_health,
            "reranker_backend": reranker_health,
        }

    def _ready(self):
        if self.catalog is None:
            raise ApiError(503, "catalog_unavailable", self.catalog_error or "catalog unavailable")

    def _options(self, payload):
        try:
            top_k = max(1, min(20, int(payload.get("top_k", 5))))
            candidate_k = max(top_k, min(1000, int(payload.get("candidate_k", 100))))
            rate = payload.get("cny_to_usd_rate")
            rate = float(rate) if rate is not None else None
            visual_weight = float(payload.get("visual_weight", self.visual_weight))
            reranker_weight = float(payload.get("reranker_weight", self.reranker_weight))
        except (TypeError, ValueError):
            raise ApiError(
                400, "invalid_options",
                "top_k, candidate_k, CNY rate, visual_weight, or reranker_weight is invalid",
            )
        if rate is not None and rate <= 0:
            raise ApiError(400, "invalid_options", "cny_to_usd_rate must be positive")
        if not 0.0 <= visual_weight <= 1.0:
            raise ApiError(400, "invalid_options", "visual_weight must be in [0, 1]")
        if not 0.0 <= reranker_weight <= 1.0:
            raise ApiError(400, "invalid_options", "reranker_weight must be in [0, 1]")
        return top_k, candidate_k, rate, visual_weight, reranker_weight

    def _resolve_image(self, payload, previous=None):
        clear_image = payload.get("clear_image") is True
        has_image = payload.get("image_base64") is not None
        if clear_image and has_image:
            raise ApiError(400, "invalid_image_update", "cannot set and clear an image together")
        if clear_image:
            return None, "cleared"
        if has_image:
            if self.visual_adapter is None:
                raise ApiError(503, "image_not_configured", "CLIP assets are not configured")
            vector, metadata = self.visual_adapter.encode_base64(
                payload["image_base64"], len(self.catalog)
            )
            return {"vector": vector, "metadata": metadata}, (
                "replaced" if previous is not None else "new"
            )
        if previous is not None:
            return previous, "reused"
        return None, "none"

    def _run(self, session_id, state, top_k, candidate_k, event,
             cny_to_usd_rate=None, image_context=None, image_action="none",
             visual_weight=None, reranker_weight=None):
        visual_weight = self.visual_weight if visual_weight is None else visual_weight
        reranker_weight = (
            self.reranker_weight if reranker_weight is None else reranker_weight
        )
        visual_scores = None
        if image_context is not None:
            if self.visual_adapter is None:
                raise ApiError(503, "image_not_configured", "CLIP assets are not configured")
            visual_scores = self.visual_adapter.score_vector(image_context["vector"])
        base_result = qs.rank_turn(
            self.catalog, state, top_k=candidate_k, candidate_k=candidate_k,
            visual_scores=visual_scores, visual_weight=visual_weight,
        )
        query_projection = _state_query_text(state)
        reranker_scores = None
        reranker_metadata = {
            "action": "not_configured" if self.reranker_adapter is None else "skipped",
            "query_projection": query_projection,
            "scored_candidates": 0,
        }
        if self.reranker_adapter is not None and query_projection and base_result["ranked"]:
            catalog_by_id = {r["item_id"]: r for r in self.catalog}
            candidates = [catalog_by_id[r["item_id"]] for r in base_result["ranked"]]
            reranker_scores, scored = self.reranker_adapter.score(
                query_projection, candidates
            )
            reranker_metadata.update(scored)
            reranker_metadata["action"] = "scored"
        elif self.reranker_adapter is not None and not query_projection:
            reranker_metadata["reason"] = "no positive text query after QueryState parsing"
        elif self.reranker_adapter is not None:
            reranker_metadata["reason"] = "no feasible candidates after hard filtering"

        turn_result = qs.rank_turn(
            self.catalog, state, top_k=top_k, candidate_k=candidate_k,
            visual_scores=visual_scores, visual_weight=visual_weight,
            reranker_scores=reranker_scores, reranker_weight=reranker_weight,
        )
        turn_result["visual"].update({
            "action": image_action,
            "sha256": (
                image_context["metadata"]["sha256"] if image_context is not None else None
            ),
            "dim": (
                image_context["metadata"]["dim"] if image_context is not None else None
            ),
            "encode_seconds": (
                image_context["metadata"].get("encode_seconds")
                if image_context is not None else None
            ),
            "raw_image_persisted": False,
            "cache_visual_candidates": len(visual_scores or {}),
        })
        turn_result["reranker"].update(reranker_metadata)
        negotiation = qs.negotiate(self.catalog, state) if not turn_result["ranked"] else {
            "needed": False,
            "feasible_count": turn_result["stage_counts"]["hard_filter"]["kept"],
            "options": [],
            "unknown_evidence": {},
        }
        guarded = _guarded_output(state, turn_result)
        trace = _public_trace(state, turn_result, negotiation, guarded)
        result = {
            "schema_version": API_SCHEMA_VERSION,
            "session_id": session_id,
            "event": event,
            "state": state,
            "recommendation": guarded,
            "comparison": _comparison(turn_result["ranked"]),
            "negotiation": negotiation,
            "ranking": turn_result,
            "trace": trace,
            "limitations": [
                "restricted rule parser, not general language understanding",
                "in-memory session state is lost when the process restarts",
                "CLIP fusion weight is a fixed demo setting, not a tuned quality claim",
                (
                    "cross-encoder was trained on ESCI; Office use is an uncalibrated "
                    "cross-domain adapter, not an Office quality claim"
                ),
                "reranker weight 0.7 is inherited from ESCI selection, not tuned on Office",
            ],
        }
        self.sessions[session_id] = {
            "state": state,
            "top_k": top_k,
            "candidate_k": candidate_k,
            "cny_to_usd_rate": cny_to_usd_rate,
            "visual_weight": visual_weight,
            "reranker_weight": reranker_weight,
            "image_context": image_context,
            "turns": self.sessions.get(session_id, {}).get("turns", []) + [trace],
        }
        return result

    def research(self, payload):
        self._ready()
        query = str(payload.get("query") or "").strip()
        if not query and payload.get("image_base64") is None:
            raise ApiError(400, "missing_query", "provide query text, an image, or both")
        top_k, candidate_k, rate, visual_weight, reranker_weight = self._options(payload)
        session_id = str(payload.get("session_id") or uuid.uuid4())
        with self.lock:
            if session_id in self.sessions:
                raise ApiError(409, "session_exists", "session_id already exists; use /v1/refine")
            image_context, image_action = self._resolve_image(payload)
            state = qs.build_initial_state(query, cny_to_usd_rate=rate)
            return self._run(
                session_id, state, top_k, candidate_k, "research", rate,
                image_context, image_action, visual_weight, reranker_weight,
            )

    def refine(self, payload):
        self._ready()
        session_id = str(payload.get("session_id") or "").strip()
        utterance = str(payload.get("utterance") or "").strip()
        if not session_id or not utterance:
            raise ApiError(400, "missing_refine_input", "session_id and utterance are required")
        with self.lock:
            old = self.sessions.get(session_id)
            if old is None:
                raise ApiError(404, "session_not_found", "unknown session_id")
            top_k, candidate_k, rate, visual_weight, reranker_weight = self._options({
                "top_k": payload.get("top_k", old["top_k"]),
                "candidate_k": payload.get("candidate_k", old["candidate_k"]),
                "cny_to_usd_rate": payload.get("cny_to_usd_rate", old.get("cny_to_usd_rate")),
                "visual_weight": payload.get("visual_weight", old.get("visual_weight")),
                "reranker_weight": payload.get(
                    "reranker_weight", old.get("reranker_weight")
                ),
            })
            image_context, image_action = self._resolve_image(
                payload, old.get("image_context")
            )
            state = qs.apply_update(old["state"], utterance, cny_to_usd_rate=rate)
            return self._run(
                session_id, state, top_k, candidate_k, "refine", rate,
                image_context, image_action, visual_weight, reranker_weight,
            )

    def trace(self, session_id):
        with self.lock:
            item = self.sessions.get(session_id)
            if item is None:
                raise ApiError(404, "session_not_found", "unknown session_id")
            return {
                "schema_version": API_SCHEMA_VERSION,
                "session_id": session_id,
                "state": item["state"],
                "turns": item["turns"],
            }


def make_handler(service, fashion_service=None, circo_service=None):
    class Handler(BaseHTTPRequestHandler):
        server_version = "ShoppingResearch/1"

        def _send(self, status, payload):
            body = json.dumps(payload, ensure_ascii=False, allow_nan=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _send_ui(self, ui_path=UI_PATH):
            try:
                with open(ui_path, "rb") as fh:
                    body = fh.read()
            except OSError:
                raise ApiError(404, "ui_unavailable", "shopping_research_ui.html is missing")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _json(self):
            try:
                size = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                raise ApiError(400, "invalid_content_length", "invalid Content-Length")
            if size <= 0 or size > MAX_BODY_BYTES:
                raise ApiError(400, "invalid_body_size", "JSON body must be 1..%d bytes" % MAX_BODY_BYTES)
            try:
                value = json.loads(self.rfile.read(size).decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise ApiError(400, "invalid_json", str(exc))
            if not isinstance(value, dict):
                raise ApiError(400, "invalid_json", "JSON body must be an object")
            return value

        def do_GET(self):  # noqa: N802
            path = urlparse(self.path).path
            try:
                if path == "/health":
                    self._send(200, service.health())
                elif path == "/circo":
                    self._send_ui(os.path.join(os.path.dirname(UI_PATH), "circo_replay_ui.html"))
                elif path.startswith("/v1/circo/"):
                    if circo_service is None:
                        raise ApiError(503, "circo_not_configured", "服务启动时需配置 --circo-run（已完成精排目录）")
                    params = parse_qs(urlparse(self.path).query)
                    if path == "/v1/circo/config":
                        self._send(200, circo_service.config())
                    elif path == "/v1/circo/query":
                        self._send(200, circo_service.query(params.get("id", [""])[0]))
                    elif path == "/v1/circo/image":
                        body = circo_service.image(params.get("id", [""])[0])
                        self.send_response(200)
                        self.send_header("Content-Type", "image/jpeg")
                        self.send_header("Content-Length", str(len(body)))
                        self.end_headers()
                        self.wfile.write(body)
                    else:
                        raise ApiError(404, "not_found", "unknown CIRCO endpoint")
                elif path == "/fashion":
                    self._send_ui(os.path.join(os.path.dirname(UI_PATH), "fashioniq_live_ui.html"))
                elif path == "/v1/fashion/config":
                    if fashion_service is None:
                        raise ApiError(503, "fashion_not_configured", "服务启动时需配置 --fashion-run")
                    self._send(200, fashion_service.config())
                elif path == "/v1/fashion/image":
                    if fashion_service is None:
                        raise ApiError(503, "fashion_not_configured", "FashionIQ 未配置")
                    params = parse_qs(urlparse(self.path).query)
                    body = fashion_service.product_image(params.get("category", [""])[0], params.get("id", [""])[0])
                    self.send_response(200)
                    self.send_header("Content-Type", "image/jpeg")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                elif path == "/ui":
                    self._send_ui()
                elif path == "/":
                    self._send(200, {
                        "service": "Shopping Research API",
                        "schema_version": API_SCHEMA_VERSION,
                        "ui": "/ui",
                        "endpoints": ["GET /health", "GET /ui", "POST /v1/research", "POST /v1/refine",
                                      "GET /v1/sessions/{session_id}/trace"],
                    })
                elif path.startswith("/v1/sessions/") and path.endswith("/trace"):
                    session_id = unquote(path[len("/v1/sessions/"):-len("/trace")].strip("/"))
                    self._send(200, service.trace(session_id))
                else:
                    raise ApiError(404, "not_found", "unknown endpoint")
            except ApiError as exc:
                self._send(exc.status, {"error": {"code": exc.code, "message": exc.message}})

        def do_POST(self):  # noqa: N802
            path = urlparse(self.path).path
            try:
                payload = self._json()
                if path == "/v1/fashion/query":
                    if fashion_service is None:
                        raise ApiError(503, "fashion_not_configured", "FashionIQ 未配置")
                    result = fashion_service.query(payload)
                elif path == "/v1/research":
                    result = service.research(payload)
                elif path == "/v1/refine":
                    result = service.refine(payload)
                else:
                    raise ApiError(404, "not_found", "unknown endpoint")
                self._send(200, result)
            except ApiError as exc:
                self._send(exc.status, {"error": {"code": exc.code, "message": exc.message}})
            except Exception as exc:  # keep internal details out of the HTTP response
                self.log_error("unhandled error: %s", exc)
                self._send(500, {"error": {"code": "internal_error", "message": "internal error"}})

        def log_message(self, fmt, *args):
            sys.stderr.write("shopping-api %s - %s\n" % (self.address_string(), fmt % args))

    return Handler


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    ap.add_argument("--catalog", default=DEFAULT_CATALOG)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8080)
    ap.add_argument("--clip-emb", default=None)
    ap.add_argument("--clip-mask", default=None)
    ap.add_argument("--clip-ids", default=None)
    ap.add_argument("--clip-model", default="openai/clip-vit-large-patch14")
    ap.add_argument("--device", default=None)
    ap.add_argument("--fashion-run", default=None, help="optional completed FashionIQ text-adaptation run")
    ap.add_argument("--circo-run", default=None, help="optional completed CIRCO VL rerank run, read-only CPU replay")
    ap.add_argument("--circo-data", default="data/circo_transfer")
    ap.add_argument("--fashion-data", default="data/fashioniq")
    ap.add_argument("--fashion-cache", default="artifacts/shopping/fashioniq_emb")
    ap.add_argument("--visual-weight", type=float, default=0.5)
    ap.add_argument("--xenc-checkpoint", default=None)
    ap.add_argument("--xenc-model", default="cross-encoder/ms-marco-MiniLM-L-6-v2")
    ap.add_argument("--xenc-weight", type=float, default=0.7)
    ap.add_argument("--xenc-max-len", type=int, default=256)
    ap.add_argument("--xenc-batch-size", type=int, default=64)
    ap.add_argument("--check", action="store_true", help="load catalog and run one request without serving")
    ap.add_argument("--check-query", default="wireless mouse under 30 dollars")
    ap.add_argument("--check-image", default=None,
                    help="optional local image path for the one-shot check")
    args = ap.parse_args(argv)

    visual_adapter = None
    if any((args.clip_emb, args.clip_mask, args.clip_ids)):
        visual_adapter = VisualSearchAdapter(
            args.clip_emb, args.clip_mask, args.clip_ids,
            model_name=args.clip_model, device=args.device,
        )
    reranker_adapter = None
    if args.xenc_checkpoint:
        reranker_adapter = CrossEncoderRerankAdapter(
            args.xenc_checkpoint, model_name=args.xenc_model,
            device=args.device, max_len=args.xenc_max_len,
            batch_size=args.xenc_batch_size,
        )
    service = ResearchService(
        args.catalog, visual_adapter=visual_adapter,
        visual_weight=args.visual_weight,
        reranker_adapter=reranker_adapter,
        reranker_weight=args.xenc_weight,
    )
    if args.check:
        if service.catalog is None:
            print(json.dumps(service.health(), indent=2, ensure_ascii=False))
            return 2
        payload = {
            "query": args.check_query,
            "session_id": "check",
            "top_k": 5,
            "visual_weight": args.visual_weight,
            "reranker_weight": args.xenc_weight,
        }
        if args.check_image:
            with open(args.check_image, "rb") as fh:
                payload["image_base64"] = base64.b64encode(fh.read()).decode("ascii")
        result = service.research(payload)
        print(json.dumps({
            "health": service.health(),
            "trace": result["trace"],
            "comparison": result["comparison"],
        },
                         indent=2, ensure_ascii=False, allow_nan=False))
        return 0

    fashion_service = None
    if args.fashion_run:
        from fashioniq_live import FashionService
        fashion_service = FashionService(args.fashion_run, ApiError, VisualSearchAdapter._decode_image,
                                         data_root=args.fashion_data, cache=args.fashion_cache,
                                         device=args.device or "cuda")
    circo_service = None
    if args.circo_run:
        from circo_replay import CircoReplay
        circo_service = CircoReplay(args.circo_run, ApiError, data=args.circo_data)
    server = ThreadingHTTPServer((args.host, args.port), make_handler(service, fashion_service, circo_service))
    print("Shopping Research API on http://%s:%d (catalog=%s, status=%s)" %
          (args.host, args.port, service.catalog_path, service.health()["status"]), file=sys.stderr)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        if circo_service is not None:
            circo_service.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
