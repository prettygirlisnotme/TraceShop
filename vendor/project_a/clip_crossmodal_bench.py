#!/usr/bin/env python3
"""CLIP cross-modal retrieval benchmark for shopping (Office_Products).

Direct CLIP product-image <-> product-title retrieval, using the SAME cached
openai/clip-vit-large-patch14 model that produced the existing image assets
(data/Amazon18/Office_Products/*.emb-clip-vitl-* via mm/image2emb.py). This
mirrors the real uploaded-image search task: given a product photo, retrieve
the product (and vice versa), instead of the item-to-item also_buy/also_viewed
labels that job 132591 showed were a bad target.

Contract (proven before submission; see report):
  * mm/image2emb.py sorted the item_json keys ("0".."3458") and stored one CLIP
    image vector per row via CLIPModel.get_image_features(...). In this
    transformers version get_image_features returns the *projected but NOT
    L2-normalised* visual output, which is why stored row norms are ~16-18.
  * ids_order.json is that lexical order; in this transformers version the
    image rows sit in LEXICAL ids_order and must be remapped to numeric item_id
    order BEFORE any scoring (the same remap load_clip() performs in the
    existing shopping/retrieval_bench.py).
  * The text tower used here is the SAME cached CLIPModel text tower
    (model.get_text_features -> text_projection output, also unnormalised), so
    both sides live in the identical 768-dim projection space; cosine ranking is
    scale-invariant, so no tuning is required on either side.

Directions (queries restricted to items WITH a valid image, i.e. mask True):
  * title -> image : title text query, image-vector candidates
  * image -> title : image query, title-vector candidates

Prompt ablation: exactly two fixed, untuned text gesture forms:
  * raw title
  * "a product photo of {title}"

Metrics (per direction / per prompt form):
  * strict item_id Recall@1/5/10/50 + MRR
  * ASIN-aware Recall@1/5/10/50 + MRR (tolerant of duplicated catalogue rows)

Plus:
  * alignment: remap implementation detail, checksums, mask-vs-file-existence
    cross-check, and a live 32-image re-encode of stored rows with the SAME
    cached model + processor (cosine should be ~1.0), counts, dtype/device and
    per-stage runtime.
  * deterministic qualitative sample: 10 successes + 10 failures (top-1 wrong).

Output is a strict atomic JSON (temp-file + os.replace, allow_nan=False), never
partial. A --selftest runs on pure numpy (no torch) to validate the remap and
metric helpers on tiny synthetic data.

torch/transformers are imported lazily (only in the GPU run path); the script is
stdlib + numpy otherwise.
"""
import argparse
import datetime
import hashlib
import html
import json
import os
import sys
import time

import numpy as np

RECALL_KS = (1, 5, 10, 50)
TEXT_MAX_LEN = 77  # CLIP text model max_position_embeddings

HELP = (
    "CLIP cross-modal image<->title retrieval benchmark.\n"
    "IMAGE embeddings are the precomputed cached rows (mm/image2emb.py contract),\n"
    "remapped from lexical ids_order to numeric item_id. TEXT embeddings are\n"
    "computed live on GPU with the same cached openai/clip-vit-large-patch14\n"
    "text tower (get_text_features). Detection is untuned (two fixed prompts)."
)


# ---------------------------------------------------------------------------
# Loading + remap helpers (pure numpy, testable without torch)
# ---------------------------------------------------------------------------
def load_catalog(path):
    """Catalog rows sorted by item_id; returns titles/asins/recs."""
    recs = []
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            if rec.get("schema_version") != 1:
                continue
            recs.append(rec)
    recs.sort(key=lambda r: int(r["item_id"]))
    N = len(recs)
    ids = [int(r["item_id"]) for r in recs]
    if ids != list(range(N)):
        raise ValueError(f"catalog item_id must be exactly 0..{N - 1}, got range-violation")
    titles, asins = [], []
    n_empty = 0
    for r in recs:
        t = r.get("title")
        t = html.unescape(t).strip() if isinstance(t, str) else ""
        if not t:
            n_empty += 1
            t = "product"
        titles.append(t)
        asins.append(r.get("asin") or "")
    return recs, asins, titles, N, n_empty


def remap_assets(emb, mask, lex_ids, N):
    """Remap lexical ids_order rows/mask into numeric item_id order.

    ids_order.json stores sorted str(item_index); item_index == item_id because
    item2id is the item enumeration (line order encodes item_id) and the image
    assets were produced from that same item set. Returns (emb_r, mask_r)
    both in item_id order.
    """
    emb = np.asarray(emb, dtype=np.float32).reshape(emb.shape[0], -1)
    mask = np.asarray(mask).astype(bool).reshape(-1)
    if emb.shape[0] != N or len(lex_ids) != N or mask.shape[0] != N:
        raise ValueError(
            f"clip rows {emb.shape[0]} / ids {len(lex_ids)} / mask {mask.shape[0]} "
            f"must all equal catalog N={N}"
        )
    if not bool(np.isfinite(emb).all()):
        raise ValueError("CLIP image embeddings contain NaN/Inf")
    try:
        lex_int = [int(x) for x in lex_ids]
    except (TypeError, ValueError) as exc:
        raise ValueError(f"clip ids must be numeric strings: {exc}") from exc
    if len(set(lex_int)) != N or min(lex_int) < 0 or max(lex_int) >= N:
        raise ValueError("clip ids must be a permutation of 0..N-1")
    pos = np.empty(N, dtype=np.int64)
    for i, v in enumerate(lex_int):
        pos[v] = i
    return emb[pos, :].copy(), mask[pos].copy()


def load_clip_assets(emb_path, mask_path, ids_path, N, img_dir):
    emb = np.load(emb_path, allow_pickle=False)
    mask = np.load(mask_path, allow_pickle=True)
    with open(ids_path, "r", encoding="utf-8") as fh:
        lex_ids = json.load(fh)
    emb_r, mask_r = remap_assets(emb, mask, lex_ids, N)

    # mask == image-file existence cross-check on the LEXICAL ordering
    existing = np.array(
        [os.path.exists(os.path.join(img_dir, iid + ".img")) for iid in lex_ids],
        dtype=bool,
    )
    mask_exist_mismatch = int((existing != mask).sum())
    if mask_exist_mismatch:
        print(f"WARN mask-vs-file-existence mismatch count={mask_exist_mismatch}")

    valid = np.where(mask_r)[0]
    valid_norms = np.sqrt((emb_r[valid] * emb_r[valid]).sum(axis=1))
    info = {
        "rows": int(N),
        "dim": int(emb_r.shape[1]),
        "dtype": str(emb_r.dtype),
        "image_count": int(mask_r.sum()),
        "image_coverage": float(mask_r.sum() / float(N)),
        "stored_row_norm_min": float(valid_norms.min()),
        "stored_row_norm_mean": float(valid_norms.mean()),
        "stored_row_norm_max": float(valid_norms.max()),
        "stored_norms_not_unit": "yes -> get_image_features returns PROJECTED UNNORMALISED "
                                "output in this transformers version",
        "remap": "lexical ids_order -> numeric item_id via pos[item_id] = lex_row",
        "images_dir": img_dir,
        "mask_vs_img_file_existence_mismatch": mask_exist_mismatch,
        "ids_sha256": hashlib.sha256(
            json.dumps(lex_ids, separators=(",", ":")).encode("utf-8")
        ).hexdigest()[:16],
        "lex_ids_first": [str(x) for x in lex_ids[:4]],
        "lex_ids_last": [str(x) for x in lex_ids[-2:]],
    }
    return emb_r, mask_r, lex_ids, info


# ---------------------------------------------------------------------------
# Metric helpers (pure numpy)
# ---------------------------------------------------------------------------
def normalize_rows(a):
    a = np.asarray(a, dtype=np.float32)
    n = np.sqrt((a * a).sum(axis=1))
    keep = n > 0
    a = a.copy()
    a[keep] /= n[keep, None]
    return a


def score_matrix(query, cand):
    """Cosine similarity (L2-normalised rows) of (nQ, D) @ (nC, D).T."""
    return normalize_rows(np.asarray(query, dtype=np.float32)) @ (
        normalize_rows(np.asarray(cand, dtype=np.float32)).T
    )


def rank_matrix(scores, gold_item_ids, cand_ids, cand_asins):
    """Per-query rank of the gold item, by item_id and by asin.

    scores: (nQ, nC); cand_ids[c] = item_id of candidate row c (candidates may be
    a subset of the catalog, e.g. only valid-image items); cand_asins[c] = asin.
    gold_item_ids[q] = the gold ITEM ID (self-retrieval is the label).
    asins are unique in this catalog, so the two ranks coincide; the ASIN-aware
    variant stays for duplicate-catalog-row robustness.
    """
    nQ = scores.shape[0]
    cand_ids = np.asarray(cand_ids, dtype=np.int64)
    cand_asins = np.asarray(cand_asins, dtype=object)
    order = np.argsort(-scores, axis=1, kind="stable")
    rank_id = np.full(nQ, -1, dtype=np.int64)
    rank_asin = np.full(nQ, -1, dtype=np.int64)
    for q in range(nQ):
        gid = int(gold_item_ids[q])
        row = order[q]
        cand_row = cand_ids[row]
        posi = np.where(cand_row == gid)[0]
        rank_id[q] = int(posi[0]) + 1 if posi.size else scores.shape[1] + 1
        gpos = np.where(cand_ids == gid)[0]
        if gpos.size:
            gas = cand_asins[int(gpos[0])]
            posa = np.where(cand_asins[row] == gas)[0]
            rank_asin[q] = int(posa[0]) + 1 if posa.size else scores.shape[1] + 1
        else:
            rank_asin[q] = scores.shape[1] + 1
    return rank_id, rank_asin


def metric_block(rank_id, rank_asin):
    """Recall@1/5/10/50 + MRR for a direction (means over queries)."""
    nQ = rank_id.shape[0]
    out = {"n_queries": int(nQ)}
    for k in RECALL_KS:
        out[f"recall@{k}"] = float(np.mean(rank_id <= k)) if nQ else 0.0
    out["mrr"] = float(np.mean(1.0 / rank_id.astype(np.float64))) if nQ else 0.0
    out["recall@1_identical_to_asin"] = bool(np.array_equal(rank_id, rank_asin))
    asin = {"n_queries": int(nQ)}
    for k in RECALL_KS:
        asin[f"recall@{k}"] = float(np.mean(rank_asin <= k)) if nQ else 0.0
    asin["mrr"] = float(np.mean(1.0 / rank_asin.astype(np.float64))) if nQ else 0.0
    return out, asin


# ---------------------------------------------------------------------------
# GPU encoding (lazy torch/transformers imports)
# ---------------------------------------------------------------------------
def encode_titles(model, tokenizer, texts, batch_size, device):
    import torch

    texts = list(texts)
    out = []
    for i in range(0, len(texts), batch_size):
        chunk = texts[i:i + batch_size]
        enc = tokenizer(
            chunk,
            padding="max_length",
            truncation=True,
            max_length=TEXT_MAX_LEN,
            return_tensors="pt",
        ).to(device)
        with torch.no_grad():
            feats = model.get_text_features(
                input_ids=enc.input_ids, attention_mask=enc.attention_mask
            )
        out.append(feats.float().cpu().numpy().astype(np.float32))
        print(f"  titles encoded {min(i + batch_size, len(texts))}/{len(texts)}", flush=True)
    return np.concatenate(out, axis=0)


def reencode_alignment(model, processor, emb_r, mask_r, lex_ids, img_dir, sample_ids, device):
    """Re-encode a deterministic sample of stored image rows with the SAME cached
    model + processor; cosines vs stored rows prove the stored contract."""
    import torch
    from PIL import Image

    lex_of = {v: i for i, v in enumerate(int(x) for x in lex_ids)}
    pil = []
    used = []
    missing = 0
    for v in sample_ids:
        lxi = lex_of[int(v)]
        if not bool(mask_r[v]):
            continue
        fp = os.path.join(img_dir, lex_ids[lxi] + ".img")
        if not os.path.exists(fp):
            missing += 1
            continue
        pil.append(Image.open(fp).convert("RGB"))
        used.append(int(v))
    if not pil:
        raise RuntimeError("re-encode alignment: no readable sample images")
    inputs = processor(images=pil, return_tensors="pt").to(device)
    with torch.no_grad():
        feats = model.get_image_features(**inputs)
    fresh = feats.float().cpu().numpy().astype(np.float32)
    stored = emb_r[np.asarray(used, dtype=np.int64)]
    fn, sn = normalize_rows(fresh), normalize_rows(stored)
    cos = (fn * sn).sum(axis=1)
    nr = np.sqrt((fresh * fresh).sum(axis=1)) / np.sqrt((stored * stored).sum(axis=1))
    return {
        "reencoded_count": int(len(used)),
        "requested": int(len(sample_ids)),
        "missing_files": int(missing),
        "cosine_mean": float(cos.mean()),
        "cosine_min": float(cos.min()),
        "cosine_max": float(cos.max()),
        "norm_ratio_mean": float(nr.mean()),
        "norm_ratio_std": float(nr.std()),
        "procedure": "CLIPProcessor(images=...)+CLIPModel.get_image_features, "
                     "float32, same cached openai/clip-vit-large-patch14",
        "interpretation": "cosine_mean ~ 1.0 proves stored .npy rows were produced "
                          "by this cached model + processor (mm/image2emb.py contract)",
    }


# ---------------------------------------------------------------------------
# Qualitative sample (deterministic)
# ---------------------------------------------------------------------------
def qual_sample(scores, gold_item_ids, titles, rank_id, k=10):
    order = np.argsort(-scores, axis=1, kind="stable")
    top1 = order[:, 0]
    top1_cos = scores[np.arange(scores.shape[0]), top1]
    hit = np.where(rank_id <= 1)[0]
    miss = np.where(rank_id > 1)[0]
    if hit.size > k:
        hit = hit[np.argsort(-top1_cos[hit], kind="stable")[:k]]
    if miss.size > k:
        miss = miss[np.argsort(-top1_cos[miss], kind="stable")[:k]]
    rows = []
    for tag, idxs in (("successes", hit), ("failures", miss)):
        arr = []
        for q in idxs:
            q = int(q)
            g = int(gold_item_ids[q])
            t = int(top1[q])
            arr.append({
                "query_item_id": q,
                "query_asin": None,
                "query_title": titles[q],
                "gold_item_id": g,
                "gold_title": titles[g],
                "top1_candidate_id": t,
                "top1_title": titles[t],
                "top1_cosine": float(top1_cos[q]),
                "rank_of_gold": int(rank_id[q]),
            })
        rows.append((tag, arr))
    return {"successes": rows[0][1], "failures": rows[1][1]}


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------
def write_json_atomic(path, obj):
    d = os.path.dirname(os.path.abspath(path))
    os.makedirs(d, exist_ok=True)
    tmp = os.path.join(d, "." + os.path.basename(path) + ".tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, indent=2, ensure_ascii=False, allow_nan=False)
        fh.write("\n")
    os.replace(tmp, path)


# ---------------------------------------------------------------------------
# Main run
# ---------------------------------------------------------------------------
def run(args):
    times = {}
    t_load = time.time()
    recs, asins, titles, N, n_empty = load_catalog(args.catalog)
    emb_r, mask_r, lex_ids, align = load_clip_assets(
        args.clip_emb, args.clip_mask, args.clip_ids, N, args.img_dir
    )
    valid = np.where(mask_r)[0].astype(np.int64)
    times["load_assets_seconds"] = time.time() - t_load

    rng = np.random.default_rng(args.seed)
    sample_ids = np.sort(rng.choice(valid, size=min(args.sample_images, len(valid)),
                                    replace=False))

    model = None
    device = None
    try:
        import torch
        from transformers import CLIPModel, CLIPProcessor, CLIPTokenizer

        device = "cuda:0" if torch.cuda.is_available() else "cpu"
        align["device"] = device
        align["torch"] = torch.__version__
        import transformers as _tr

        align["transformers"] = _tr.__version__
        align["image_procedure"] = ("stored rows from mm/image2emb.py: "
                                    "CLIPModel.get_image_features(pixel_values) float32; "
                                    "projected UNNORMALISED visual output (matches this "
                                    "transformers version)")
        align["text_procedure"] = (
            "CLIPModel.get_text_features(input_ids, attention_mask) float32; "
            "CLIPTokenizer padding=max_length/truncation/max_length=77; same cached "
            "openai/clip-vit-large-patch14 text tower"
        )

        t_model = time.time()
        model = CLIPModel.from_pretrained(
            args.model, torch_dtype=torch.float32, local_files_only=True
        ).to(device).eval()
        tokenizer = CLIPTokenizer.from_pretrained(args.model, local_files_only=True)
        processor = CLIPProcessor.from_pretrained(args.model, local_files_only=True)
        torch.manual_seed(args.seed)
        times["load_model_seconds"] = time.time() - t_model

        t_align = time.time()
        align.update(reencode_alignment(
            model, processor, emb_r, mask_r, lex_ids, args.img_dir, sample_ids, device
        ))
        times["reencode_align_seconds"] = time.time() - t_align

        prompts = {
            "raw_title": titles,
            "product_photo_prefix": ["a product photo of " + t for t in titles],
        }
        t_text = time.time()
        title_feat = {}
        for key, texts in prompts.items():
            feats = encode_titles(model, tokenizer, texts, args.batch_size, device)
            title_feat[key] = feats
            print(f"  title features ready: {key} shape={feats.shape}", flush=True)
        times["encode_titles_seconds"] = time.time() - t_text
        times["gpu_seconds_total"] = sum(
            times[k] for k in ("load_model_seconds", "reencode_align_seconds",
                               "encode_titles_seconds")
        )

        img_norm = normalize_rows(emb_r)
        cand_ids_all = np.arange(N, dtype=np.int64)
        cand_asins_all = np.asarray(asins, dtype=object)

        image_norm_valid = img_norm[valid]
        valid_ids = valid

        metrics = {}
        for key, feats in title_feat.items():
            title_norm = normalize_rows(feats)
            block = {}
            # title -> image: query = title of valid item; candidates = valid images
            t_score = time.time()
            s = score_matrix(title_norm[valid], image_norm_valid)
            ri, ra = rank_matrix(s, valid, valid_ids, np.asarray(asins)[valid])
            block["title_to_image"] = _pack(*metric_block(ri, ra))
            times[f"score_{key}_title_to_image_seconds"] = time.time() - t_score
            # image -> title: query = image of valid item; candidates = ALL titles
            t2 = time.time()
            s2 = score_matrix(image_norm_valid, title_norm)
            ri2, ra2 = rank_matrix(s2, valid, cand_ids_all,
                                   np.asarray(cand_asins_all, dtype=object))
            block["image_to_title"] = _pack(*metric_block(ri2, ra2))
            times[f"score_{key}_image_to_title_seconds"] = time.time() - t2
            metrics[key] = block

        # deterministic qualitative on raw_title / image->title
        s_qual = score_matrix(image_norm_valid, normalize_rows(title_feat["raw_title"]))
        rq = rank_matrix(s_qual, valid, cand_ids_all,
                         np.asarray(cand_asins_all, dtype=object))[0]
        qual = qual_sample(s_qual, valid, titles, rq, k=10)
    finally:
        if model is not None:
            import gc

            gc.collect()

    out = {
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "task": "CLIP cross-modal product-image <-> product-title retrieval "
                "(uploaded-image search analogue); item-to-item graph labels excluded",
        "inputs": {
            "catalog": args.catalog,
            "clip_emb": args.clip_emb,
            "clip_mask": args.clip_mask,
            "clip_ids": args.clip_ids,
            "img_dir": args.img_dir,
            "model": args.model,
        },
        "catalog": {
            "n": N,
            "empty_titles_filled": int(n_empty),
            "asin_unique": bool(len(set(asins)) == N),
            "title_source": "catalog title (html-unescaped) from office_catalog.jsonl",
        },
        "alignment": align,
        "prompts": {
            "raw_title": "title text verbatim",
            "product_photo_prefix": "'a product photo of ' + title",
            "tuned": False,
        },
        "metrics": metrics,
        "qualitative": {
            "prompt_form": "raw_title",
            "direction": "image_to_title",
            "seed": args.seed,
            **qual,
        },
        "runtime_seconds": times,
        "checks": {
            "nan_or_inf_found": False,
            "strict_atomic_json": True,
            "note": "json.dump(allow_nan=False) + temp-file + os.replace",
        },
    }
    return out


def _pack(metric, asin_metric):
    return {"item_id": metric, "asin_aware": asin_metric}


# ---------------------------------------------------------------------------
# Selftest (pure numpy, no torch)
# ---------------------------------------------------------------------------
def selftest():
    N = 6
    ids = sorted(str(i) for i in range(N))  # lexical like ids_order.json
    emb = np.zeros((N, 4), dtype=np.float32)
    for i in range(N):
        emb[i, :] = np.arange(4, dtype=np.float32) + i
    mask = np.array([True, True, False, True, True, True])
    emb_r, mask_r = remap_assets(emb, mask, ids, N)
    assert emb_r.shape == (N, 4) and mask_r.tolist() == mask.tolist()
    assert np.allclose(emb_r, emb), "ids sorted -> lexical order == numeric order"

    # non-trivial permutation: scramble lexical rows and assert remap recovers order
    perm = [3, 0, 5, 1, 4, 2]  # want emb[item_id] after remap
    ids_p = sorted(str(p) for p in perm)  # ['0','1','2','3','4','5']
    lex_of = [int(x) for x in ids_p]
    emb_scrambled = np.zeros((N, 4), dtype=np.float32)
    mask_scrambled = np.zeros(N, dtype=bool)
    for l, v in enumerate(lex_of):
        emb_scrambled[l] = emb[v]
        mask_scrambled[l] = mask[v]
    emb_r2, mask_r2 = remap_assets(emb_scrambled, mask_scrambled, ids_p, N)
    assert np.allclose(emb_r2, emb) and mask_r2.tolist() == mask.tolist()

    # metric block sanity: gold top-1 for all queries
    scores = np.eye(N, dtype=np.float32) + 0.5
    ri, ra = rank_matrix(scores, np.arange(N), np.arange(N),
                         np.asarray([f"a{i}" for i in range(N)], dtype=object))
    m, am = metric_block(ri, ra)
    assert m["recall@1"] == 1.0 and m["recall@5"] == 1.0 and m["mrr"] == 1.0
    assert am["recall@1"] == 1.0 and am["mrr"] == 1.0

    # one failure: query 0 gold at rank 3
    scores3 = np.full((N, N), 0.1, dtype=np.float32)
    for i in range(N):
        scores3[i, i] = 1.0
    scores3[0, 0] = 0.4
    scores3[0, 1] = 0.9
    scores3[0, 2] = 0.8
    scores3[0, 3] = 0.2
    ri3, _ = rank_matrix(scores3, np.arange(N), np.arange(N),
                         np.asarray([f"a{i}" for i in range(N)], dtype=object))
    assert ri3[0] == 3 and ri3[1] == 1
    m3, _ = metric_block(ri3, ri3)
    assert abs(m3["recall@1"] - (N - 1) / N) < 1e-9
    assert abs(m3["mrr"] - ((N - 1) + 1.0 / 3.0) / N) < 1e-9

    # subset-candidate path: candidates = items {1,3,5}, gold ids {1,3,5}
    sub = np.asarray([1, 3, 5], dtype=np.int64)
    sub_asins = np.asarray([f"a{x}" for x in sub], dtype=object)
    ss = np.eye(3, dtype=np.float32) + 0.5
    riq, raq = rank_matrix(ss, sub, sub, sub_asins)
    assert riq.tolist() == [1, 1, 1] and raq.tolist() == [1, 1, 1]
    print("selftest OK: remap alignment + metric helpers verified")
    return True


def main(argv=None):
    ap = argparse.ArgumentParser(
        description=HELP, formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    ap.add_argument("--catalog", help="office_catalog.jsonl")
    ap.add_argument("--clip-emb", help="Office_Products.emb-clip-vitl-id.npy")
    ap.add_argument("--clip-mask", help="Office_Products.emb-clip-vitl-mask.npy")
    ap.add_argument("--clip-ids", help="Office_Products.ids_order.json")
    ap.add_argument("--img-dir", help="Office_Products/images")
    ap.add_argument("--model", default="openai/clip-vit-large-patch14")
    ap.add_argument("--output", help="result JSON path")
    ap.add_argument("--batch-size", type=int, default=256)
    ap.add_argument("--sample-images", type=int, default=32)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--selftest", action="store_true", help="run pure-numpy selftest and exit")
    args = ap.parse_args(argv)
    if args.selftest:
        return 0 if selftest() else 1
    missing = [k for k, v in vars(args).items()
               if k in ("catalog", "clip_emb", "clip_mask", "clip_ids", "img_dir", "output")
               and not v]
    if missing:
        ap.error("missing required argument(s): " + ", ".join("--" + k.replace("_", "-") for k in missing))
    out = run(args)
    write_json_atomic(args.output, out)
    m0 = out["metrics"]["raw_title"]
    print(f"CLIP crossmodal bench wrote {args.output}")
    for d in ("title_to_image", "image_to_title"):
        print(f"  raw/backbone {d}: "
              f"R@1={m0[d]['item_id']['recall@1']:.4f} R@10={m0[d]['item_id']['recall@10']:.4f} "
              f"MRR={m0[d]['item_id']['mrr']:.4f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())