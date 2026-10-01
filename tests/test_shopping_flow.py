#!/usr/bin/env python3
"""Stdlib unittest acceptance tests for the Shopping Decision Agent.

Run on a CPU node:
    python3 -m unittest discover -s tests -v
    # or: python3 tests/test_shopping_flow.py

Covers the five fixed cases in demo/cases.json with assertions on real side
effects (SQLite rows), plus input validation and owner/session binding.  Expiry
is tested with an injected clock, so there are no sleeps.
"""

import json
import os
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from shop_agent.engine import DEFAULT_CATALOG, AgentError, ShopAgentEngine  # noqa: E402
from shop_agent.server import build_server  # noqa: E402

DEFAULT_QUERY = "wireless mouse under 30 dollars"


class Clock:
    def __init__(self, now=1000.0):
        self.now = now

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


class EngineCase(unittest.TestCase):
    ttl = 60.0

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = os.path.join(self.tmp.name, "agent.sqlite3")
        self.clock = Clock()
        self.owner = "tester"
        self.engine = ShopAgentEngine(catalog_path=DEFAULT_CATALOG, db_path=self.db,
                                      ttl_seconds=self.ttl, clock=self.clock)

    def tearDown(self):
        self.engine.store.close()
        self.tmp.cleanup()

    def _research(self, query=DEFAULT_QUERY):
        return self.engine.research(self.owner, query)

    # -- case 1: normal confirm + idempotent + durable reopen ------------
    def test_normal_confirm_idempotent_and_reopen(self):
        result = self._research()
        self.assertTrue(result["feasible"])
        self.assertEqual(result["session"]["turn"], 1)
        proposal = result["proposal"]
        self.assertEqual(proposal["status"], "PROPOSED")
        self.assertEqual(self.engine.store.count_reservations(self.owner), 0)
        sid = result["session"]["session_id"]

        first = self.engine.approve(self.owner, sid, proposal["proposal_id"])
        self.assertTrue(first["verified"])
        self.assertFalse(first["idempotent"])
        self.assertTrue(all(first["verification_checks"].values()))
        self.assertEqual(first["reservation"]["status"], "draft_reserved")
        self.assertEqual(self.engine.store.count_reservations(self.owner, sid), 1)

        second = self.engine.approve(self.owner, sid, proposal["proposal_id"])
        self.assertTrue(second["idempotent"])
        self.assertEqual(second["reservation"]["reservation_id"],
                         first["reservation"]["reservation_id"])
        self.assertEqual(self.engine.store.count_reservations(self.owner, sid), 1)

        # durable readback after closing and reopening the database
        self.engine.store.close()
        self.engine = ShopAgentEngine(catalog_path=DEFAULT_CATALOG, db_path=self.db,
                                      ttl_seconds=self.ttl, clock=self.clock)
        readback = self.engine.get_session(self.owner, sid)
        self.assertEqual(len(readback["reservations"]), 1)
        self.assertEqual(readback["reservations"][0]["reservation_id"],
                         first["reservation"]["reservation_id"])
        self.assertEqual(readback["proposals"][0]["status"], "APPROVED")
        self.assertTrue(any(e["kind"] == "reservation_created" for e in readback["events"]))

    # -- case 2: reject creates no reservation --------------------------
    def test_reject_creates_no_reservation(self):
        result = self._research()
        sid = result["session"]["session_id"]
        proposal = result["proposal"]

        rejected = self.engine.reject(self.owner, sid, proposal["proposal_id"])
        self.assertEqual(rejected["proposal"]["status"], "REJECTED")
        self.assertEqual(self.engine.store.count_reservations(self.owner, sid), 0)

        with self.assertRaises(AgentError) as ctx:
            self.engine.approve(self.owner, sid, proposal["proposal_id"])
        self.assertEqual(ctx.exception.status, 409)
        self.assertEqual(ctx.exception.code, "proposal_rejected")
        self.assertEqual(self.engine.store.count_reservations(self.owner, sid), 0)

    # -- case 3: no feasible budget -------------------------------------
    def test_no_feasible_budget(self):
        result = self._research("wireless mouse under 3 dollars")
        self.assertFalse(result["feasible"])
        self.assertIsNone(result["proposal"])
        self.assertTrue(result["negotiation"]["needed"])
        self.assertEqual(result["negotiation"]["feasible_count"], 0)
        self.assertEqual(self.engine.store.count_reservations(self.owner), 0)

    # -- case 4: price changed after proposal is blocked ----------------
    def test_price_changed_after_proposal_is_blocked(self):
        result = self._research()
        sid = result["session"]["session_id"]
        proposal = result["proposal"]

        sim = self.engine.simulate_quote(self.owner, sid, proposal_id=proposal["proposal_id"],
                                         price_usd=proposal["price_usd"] + 5.0)
        self.assertTrue(sim["replan_required"])
        self.assertTrue(sim["never_auto_buy"])
        self.assertEqual(sim["proposal"]["status"], "NEEDS_REVIEW")
        self.assertGreater(sim["merchant_version"], proposal["merchant_version"])

        with self.assertRaises(AgentError) as ctx:
            self.engine.approve(self.owner, sid, proposal["proposal_id"])
        self.assertEqual(ctx.exception.status, 409)
        self.assertEqual(ctx.exception.code, "quote_changed")
        self.assertEqual(self.engine.store.count_reservations(self.owner, sid), 0)

    # -- case 5: expired proposal is blocked ----------------------------
    def test_expired_proposal_is_blocked(self):
        result = self._research()
        sid = result["session"]["session_id"]
        proposal = result["proposal"]
        self.clock.advance(self.ttl + 1)

        with self.assertRaises(AgentError) as ctx:
            self.engine.approve(self.owner, sid, proposal["proposal_id"])
        self.assertEqual(ctx.exception.status, 409)
        self.assertEqual(ctx.exception.code, "proposal_expired")
        self.assertEqual(self.engine.store.count_reservations(self.owner, sid), 0)
        self.assertEqual(self.engine.store.get_proposal(proposal["proposal_id"])["status"], "EXPIRED")

    # -- refinement supersedes the previous proposal --------------------
    def test_refine_supersedes_and_advances_revision(self):
        result = self._research()
        sid = result["session"]["session_id"]
        first_id = result["proposal"]["proposal_id"]

        refined = self.engine.refine(self.owner, sid, "prefer gaming", top_k=3)
        self.assertEqual(refined["session"]["revision"], 2)
        self.assertNotEqual(refined["proposal"]["proposal_id"], first_id)
        self.assertEqual(self.engine.store.get_proposal(first_id)["status"], "SUPERSEDED")
        self.assertEqual(self.engine.store.count_reservations(self.owner, sid), 0)

    # -- validation + binding -------------------------------------------
    def test_validation_and_owner_binding(self):
        with self.assertRaises(AgentError) as ctx:
            self.engine.research(self.owner, "   ")
        self.assertEqual(ctx.exception.code, "missing_query")

        result = self._research()
        sid = result["session"]["session_id"]

        with self.assertRaises(AgentError) as ctx:
            self.engine.simulate_quote(self.owner, sid, price_usd=-1.0)
        self.assertEqual(ctx.exception.code, "invalid_price")

        with self.assertRaises(AgentError) as ctx:
            self.engine.simulate_quote(self.owner, sid, item_id="999999", price_usd=5.0)
        self.assertEqual(ctx.exception.code, "unknown_item")

        with self.assertRaises(AgentError) as ctx:
            self.engine.approve("someone-else", sid, result["proposal"]["proposal_id"])
        self.assertEqual(ctx.exception.status, 403)
        self.assertEqual(ctx.exception.code, "owner_mismatch")

    def test_replan_uses_current_quote_and_keeps_budget(self):
        result = self._research()
        sid = result["session"]["session_id"]
        old = result["proposal"]
        self.engine.simulate_quote(self.owner, sid, proposal_id=old["proposal_id"], price_usd=1000)
        replanned = self.engine.refine(self.owner, sid, "prefer ergonomic")
        self.assertNotIn(old["item_id"], [c["item_id"] for c in replanned["candidates"]])
        self.assertTrue(all(c["price_usd"] <= 30 for c in replanned["candidates"]))
        self.assertEqual(self.engine.store.count_reservations(self.owner), 0)

    def test_replan_excludes_out_of_stock(self):
        result = self._research()
        sid = result["session"]["session_id"]
        old = result["proposal"]
        self.engine.simulate_quote(self.owner, sid, proposal_id=old["proposal_id"], availability="out_of_stock")
        replanned = self.engine.refine(self.owner, sid, "prefer ergonomic")
        self.assertNotIn(old["item_id"], [c["item_id"] for c in replanned["candidates"]])

    def test_catalog_health(self):
        health = self.engine.health()
        self.assertIn(health["status"], ("ok", "degraded"))
        self.assertGreater(health["catalog"]["records"], 0)
        self.assertTrue(health["capabilities"]["single_turn_text_search"])
        self.assertFalse(health["agent"]["real_merchant_integrated"])


class HttpCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.owner = "http-tester"
        self.engine = ShopAgentEngine(
            catalog_path=DEFAULT_CATALOG,
            db_path=os.path.join(self.tmp.name, "http.sqlite3"),
            ttl_seconds=60.0, clock=Clock())
        self.server = build_server(self.engine, "127.0.0.1", 0)
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(5)
        self.engine.store.close()
        self.tmp.cleanup()

    def _url(self, path):
        return "http://127.0.0.1:%d%s" % (self.port, path)

    def _get(self, path):
        with urllib.request.urlopen(self._url(path), timeout=10) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))

    def _post(self, path, body):
        data = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(self._url(path), data=data,
                                     headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))

    def test_http_research_approve_and_error_shape(self):
        status, health = self._get("/api/health")
        self.assertEqual(status, 200)
        self.assertIn("agent", health)

        status, result = self._post("/api/research",
                                    {"owner": self.owner, "query": DEFAULT_QUERY, "top_k": 3})
        self.assertEqual(status, 200)
        self.assertTrue(result["feasible"])
        sid = result["session"]["session_id"]
        proposal = result["proposal"]

        status, approved = self._post("/api/approve",
                                      {"owner": self.owner, "session_id": sid,
                                       "proposal_id": proposal["proposal_id"]})
        self.assertEqual(status, 200)
        self.assertTrue(approved["verified"])

        status, readback = self._get("/api/session/%s?owner=%s" % (sid, self.owner))
        self.assertEqual(status, 200)
        self.assertEqual(len(readback["reservations"]), 1)

        with self.assertRaises(urllib.error.HTTPError) as ctx:
            self._post("/api/research", {"owner": self.owner, "query": ""})
        self.assertEqual(ctx.exception.code, 400)
        payload = json.loads(ctx.exception.read().decode("utf-8"))
        self.assertEqual(payload["error"]["code"], "missing_query")


if __name__ == "__main__":
    unittest.main(verbosity=2)
