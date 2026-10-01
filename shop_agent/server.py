#!/usr/bin/env python3
"""Stdlib HTTP server for the standalone Shopping Decision Agent.

Run:  python -m shop_agent.server --catalog demo/catalog.jsonl --db shop_agent_runs/agent.sqlite3

Routes
  GET  /                       static UI
  GET  /static/<file>          static assets (no CDN)
  GET  /api/health             liveness + which optional backends are online
  GET  /api/cases              demo/cases.json (the five fixed acceptance cases)
  GET  /api/session/<sid>      durable readback: session/proposals/reservations/events
  GET  /api/history            owner-scoped history
  POST /api/research           {owner, query, session_id?, top_k?, image_base64?}
  POST /api/refine             {owner, session_id, utterance, top_k?}
  POST /api/approve            {owner, session_id, proposal_id}
  POST /api/reject             {owner, session_id, proposal_id}
  POST /api/simulate-quote     {owner, session_id, proposal_id?, item_id?, price_usd?, availability?}

Only loopback is intended.  This is a local demo with owner/session binding, not a
public multi-user service (no authentication).
"""

import argparse
import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, unquote, urlparse

try:
    from .engine import (DEFAULT_CATALOG, DEFAULT_DB, DISCLAIMER_ZH, AgentError,
                         ShopAgentEngine, make_reranker_adapter, make_visual_adapter)
except ImportError:  # allow `python shop_agent/server.py`
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from shop_agent.engine import (DEFAULT_CATALOG, DEFAULT_DB, DISCLAIMER_ZH, AgentError,
                                   ShopAgentEngine, make_reranker_adapter, make_visual_adapter)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
CASES_PATH = os.path.join(ROOT, "demo", "cases.json")
MAX_BODY_BYTES = 8_000_000
CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".svg": "image/svg+xml",
    ".json": "application/json; charset=utf-8",
}


def _read_json(path, default):
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return default


def make_handler(engine):
    class Handler(BaseHTTPRequestHandler):
        server_version = "ShoppingDecisionAgent/1"

        def _send_json(self, status, payload):
            body = json.dumps(payload, ensure_ascii=False, allow_nan=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _send_bytes(self, status, body, content_type):
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _send_file(self, path):
            name = os.path.basename(path)
            full = os.path.join(STATIC_DIR, name)
            if not os.path.isfile(full) or os.path.dirname(os.path.abspath(full)) != os.path.abspath(STATIC_DIR):
                raise AgentError(404, "not_found", "static asset not found")
            with open(full, "rb") as fh:
                body = fh.read()
            ctype = CONTENT_TYPES.get(os.path.splitext(name)[1], "application/octet-stream")
            self._send_bytes(200, body, ctype)

        def _json_body(self):
            try:
                size = int(self.headers.get("Content-Length", "0"))
            except ValueError as exc:
                raise AgentError(400, "invalid_content_length", "invalid Content-Length") from exc
            if size <= 0 or size > MAX_BODY_BYTES:
                raise AgentError(400, "invalid_body_size",
                                 "JSON body must be 1..%d bytes" % MAX_BODY_BYTES)
            try:
                value = json.loads(self.rfile.read(size).decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise AgentError(400, "invalid_json", str(exc)) from exc
            if not isinstance(value, dict):
                raise AgentError(400, "invalid_json", "JSON body must be an object")
            return value

        def do_GET(self):  # noqa: N802
            path = urlparse(self.path).path
            query = parse_qs(urlparse(self.path).query)
            try:
                if path == "/":
                    self._send_file("index.html")
                elif path.startswith("/static/"):
                    self._send_file(unquote(path[len("/static/"):]))
                elif path == "/api/health":
                    self._send_json(200, engine.health())
                elif path == "/api/cases":
                    self._send_json(200, _read_json(CASES_PATH, {"cases": []}))
                elif path == "/api/history":
                    self._send_json(200, engine.history(query.get("owner", [""])[0]))
                elif path.startswith("/api/session/"):
                    sid = unquote(path[len("/api/session/"):].strip("/"))
                    self._send_json(200, engine.get_session(query.get("owner", [""])[0], sid))
                else:
                    raise AgentError(404, "not_found", "unknown endpoint")
            except AgentError as exc:
                self._send_json(exc.status, {"error": {"code": exc.code,
                                                       "message": exc.message, "status": exc.status}})
            except Exception as exc:  # noqa: BLE001
                self.log_error("unhandled GET error: %s", exc)
                self._send_json(500, {"error": {"code": "internal_error",
                                                "message": "internal error", "status": 500}})

        def do_POST(self):  # noqa: N802
            path = urlparse(self.path).path
            try:
                payload = self._json_body()
                if path == "/api/research":
                    result = engine.research(
                        payload.get("owner"), payload.get("query"),
                        session_id=payload.get("session_id"), top_k=payload.get("top_k"),
                        image_base64=payload.get("image_base64"))
                elif path == "/api/refine":
                    result = engine.refine(
                        payload.get("owner"), payload.get("session_id"),
                        payload.get("utterance"), top_k=payload.get("top_k"))
                elif path == "/api/approve":
                    result = engine.approve(
                        payload.get("owner"), payload.get("session_id"),
                        payload.get("proposal_id"))
                elif path == "/api/reject":
                    result = engine.reject(
                        payload.get("owner"), payload.get("session_id"),
                        payload.get("proposal_id"))
                elif path == "/api/simulate-quote":
                    result = engine.simulate_quote(
                        payload.get("owner"), payload.get("session_id"),
                        proposal_id=payload.get("proposal_id"), item_id=payload.get("item_id"),
                        price_usd=payload.get("price_usd"), availability=payload.get("availability"))
                else:
                    raise AgentError(404, "not_found", "unknown endpoint")
                self._send_json(200, result)
            except AgentError as exc:
                self._send_json(exc.status, {"error": {"code": exc.code,
                                                       "message": exc.message, "status": exc.status}})
            except Exception as exc:  # noqa: BLE001
                self.log_error("unhandled POST error: %s", exc)
                self._send_json(500, {"error": {"code": "internal_error",
                                                "message": "internal error", "status": 500}})

        def log_message(self, fmt, *args):
            sys.stderr.write("shop-agent %s - %s\n" % (self.address_string(), fmt % args))

    return Handler


def build_server(engine, host="127.0.0.1", port=8088):
    return ThreadingHTTPServer((host, int(port)), make_handler(engine))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("--catalog", default=DEFAULT_CATALOG,
                        help="schema_version=1 catalog JSONL (default: portable demo fixture)")
    parser.add_argument("--db", default=DEFAULT_DB, help="SQLite path for proposals/actions/events")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8088)
    parser.add_argument("--proposal-ttl", type=float, default=900.0,
                        help="proposal expiry in seconds")
    parser.add_argument("--clip-emb", default=None)
    parser.add_argument("--clip-mask", default=None)
    parser.add_argument("--clip-ids", default=None)
    parser.add_argument("--clip-model", default="openai/clip-vit-large-patch14")
    parser.add_argument("--device", default="cpu", help="device for optional adapters")
    parser.add_argument("--xenc-checkpoint", default=None)
    parser.add_argument("--xenc-model", default="cross-encoder/ms-marco-MiniLM-L-6-v2")
    args = parser.parse_args(argv)

    visual_adapter = make_visual_adapter(
        args.clip_emb, args.clip_mask, args.clip_ids, args.clip_model, args.device)
    reranker_adapter = make_reranker_adapter(args.xenc_checkpoint, args.xenc_model, args.device)
    engine = ShopAgentEngine(catalog_path=args.catalog, db_path=args.db,
                             ttl_seconds=args.proposal_ttl,
                             visual_adapter=visual_adapter, reranker_adapter=reranker_adapter)
    health = engine.health()
    is_demo = health["agent"]["catalog_is_demo_fixture"]
    server = build_server(engine, args.host, args.port)
    sys.stderr.write(
        "Shopping Decision Agent on http://%s:%d\n"
        "  catalog: %s (%s, %d records)\n"
        "  db:      %s\n"
        "  backends: visual=%s reranker=%s\n"
        "  %s\n" % (
            args.host, args.port, health["catalog"]["path"],
            "PORTABLE DEMO FIXTURE" if is_demo else "catalog", health["catalog"]["records"],
            args.db, health["capabilities"]["image_query_online"],
            health["capabilities"]["learned_reranker_online"], DISCLAIMER_ZH))
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        engine.store.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
