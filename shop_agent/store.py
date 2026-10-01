#!/usr/bin/env python3
"""SQLite persistence for the standalone Shopping Decision Agent.

Only durable, demo-relevant state lives here: sessions, proposals, simulated
merchant quotes, draft reservations and an append-only event log.  The vendor
research sessions stay in memory inside online_api.ResearchService and may be
lost on restart; everything needed to *read back* a decision survives here.

stdlib only.  A single connection guarded by an RLock is enough for a local
loopback demo (and keeps ``:memory:`` usable in tests).
"""

import json
import os
import sqlite3
import threading
import time

SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    owner TEXT NOT NULL, session_id TEXT NOT NULL, revision INTEGER NOT NULL,
    state_json TEXT NOT NULL, utterances_json TEXT NOT NULL, top_k INTEGER NOT NULL,
    merchant_version INTEGER NOT NULL, source TEXT, catalog_path TEXT, updated_at REAL,
    PRIMARY KEY (owner, session_id));
CREATE TABLE IF NOT EXISTS proposals (
    proposal_id TEXT PRIMARY KEY, owner TEXT NOT NULL, session_id TEXT NOT NULL,
    revision INTEGER NOT NULL, merchant_version INTEGER NOT NULL, item_id TEXT,
    title TEXT, brand TEXT, price_usd REAL, availability TEXT, eligible_item_ids TEXT,
    rationale TEXT, evidence_json TEXT, state_json TEXT, status TEXT NOT NULL,
    expires_at REAL NOT NULL, created_at REAL, updated_at REAL);
CREATE TABLE IF NOT EXISTS merchant_quotes (
    owner TEXT NOT NULL, session_id TEXT NOT NULL, item_id TEXT NOT NULL,
    price_usd REAL, availability TEXT, PRIMARY KEY (owner, session_id, item_id));
CREATE TABLE IF NOT EXISTS reservations (
    reservation_id TEXT PRIMARY KEY, proposal_id TEXT NOT NULL, owner TEXT NOT NULL,
    session_id TEXT NOT NULL, item_id TEXT, title TEXT, brand TEXT, price_usd REAL,
    quantity INTEGER, status TEXT, note TEXT, created_at REAL);
CREATE TABLE IF NOT EXISTS events (
    event_id INTEGER PRIMARY KEY AUTOINCREMENT, owner TEXT NOT NULL, session_id TEXT,
    kind TEXT NOT NULL, detail_json TEXT, created_at REAL);
"""

PROPOSAL_FIELDS = ("proposal_id", "owner", "session_id", "revision", "merchant_version",
                   "item_id", "title", "brand", "price_usd", "availability",
                   "eligible_item_ids", "rationale", "evidence_json", "state_json",
                   "status", "expires_at", "created_at", "updated_at")


def _dumps(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _loads(value, default):
    try:
        return json.loads(value) if value is not None else default
    except (TypeError, ValueError):
        return default


def _session_row(row):
    if row is None:
        return None
    item = dict(row)
    item["state"] = _loads(item.pop("state_json"), {})
    item["utterances"] = _loads(item.pop("utterances_json"), [])
    return item


def _proposal_row(row):
    if row is None:
        return None
    item = dict(row)
    item["eligible_item_ids"] = _loads(item.pop("eligible_item_ids"), [])
    item["evidence"] = _loads(item.pop("evidence_json"), {})
    item["constraints_state"] = _loads(item.pop("state_json"), {})
    return item


class Store:
    def __init__(self, path):
        self.path = path
        self.lock = threading.RLock()
        if path != ":memory:":
            os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        with self.lock:
            self.conn.executescript(SCHEMA)
            self.conn.commit()

    def close(self):
        with self.lock:
            self.conn.close()

    def _one(self, sql, args=()):
        with self.lock:
            return self.conn.execute(sql, args).fetchone()

    def _all(self, sql, args=()):
        with self.lock:
            return self.conn.execute(sql, args).fetchall()

    def _run(self, sql, args=()):
        with self.lock:
            self.conn.execute(sql, args)
            self.conn.commit()

    # -- sessions ---------------------------------------------------------
    def upsert_session(self, owner, session_id, revision, state, utterances,
                       top_k, merchant_version, source, catalog_path, now=None):
        self._run(
            "INSERT INTO sessions (owner, session_id, revision, state_json, utterances_json,"
            " top_k, merchant_version, source, catalog_path, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?)"
            " ON CONFLICT(owner, session_id) DO UPDATE SET revision=excluded.revision,"
            " state_json=excluded.state_json, utterances_json=excluded.utterances_json,"
            " top_k=excluded.top_k, merchant_version=excluded.merchant_version,"
            " source=excluded.source, catalog_path=excluded.catalog_path, updated_at=excluded.updated_at",
            (owner, session_id, int(revision), _dumps(state), _dumps(utterances), int(top_k),
             int(merchant_version), source, catalog_path, time.time() if now is None else now))
        return self.get_session(owner, session_id)

    def get_session(self, owner, session_id):
        return _session_row(self._one(
            "SELECT * FROM sessions WHERE owner=? AND session_id=?", (owner, session_id)))

    def list_sessions(self, owner):
        return [_session_row(r) for r in self._all(
            "SELECT * FROM sessions WHERE owner=? ORDER BY updated_at DESC", (owner,))]

    def bump_merchant_version(self, owner, session_id, now=None):
        self._run("UPDATE sessions SET merchant_version=merchant_version+1, updated_at=?"
                  " WHERE owner=? AND session_id=?",
                  (time.time() if now is None else now, owner, session_id))
        row = self._one("SELECT merchant_version FROM sessions WHERE owner=? AND session_id=?",
                        (owner, session_id))
        return row["merchant_version"] if row else None

    # -- proposals --------------------------------------------------------
    def insert_proposal(self, proposal, now=None):
        now = time.time() if now is None else now
        values = dict(proposal)
        values["created_at"] = now
        values["updated_at"] = now
        values["eligible_item_ids"] = _dumps(values.get("eligible_item_ids") or [])
        values["evidence_json"] = _dumps(values.get("evidence_json") or {})
        values["state_json"] = _dumps(values.get("state_json") or {})
        self._run("INSERT INTO proposals (%s) VALUES (%s)"
                  % (",".join(PROPOSAL_FIELDS), ",".join("?" * len(PROPOSAL_FIELDS))),
                  tuple(values.get(f) for f in PROPOSAL_FIELDS))
        return self.get_proposal(proposal["proposal_id"])

    def get_proposal(self, proposal_id):
        return _proposal_row(self._one("SELECT * FROM proposals WHERE proposal_id=?",
                                       (proposal_id,)))

    def list_proposals(self, owner, session_id=None):
        if session_id is None:
            rows = self._all("SELECT proposal_id FROM proposals WHERE owner=?"
                             " ORDER BY created_at DESC", (owner,))
        else:
            rows = self._all("SELECT proposal_id FROM proposals WHERE owner=? AND session_id=?"
                             " ORDER BY created_at DESC", (owner, session_id))
        return [self.get_proposal(r["proposal_id"]) for r in rows]

    def update_proposal_status(self, proposal_id, status, now=None):
        self._run("UPDATE proposals SET status=?, updated_at=? WHERE proposal_id=?",
                  (status, time.time() if now is None else now, proposal_id))
        return self.get_proposal(proposal_id)

    def supersede_open_proposals(self, owner, session_id, now=None):
        self._run("UPDATE proposals SET status='SUPERSEDED', updated_at=? WHERE owner=?"
                  " AND session_id=? AND status IN ('PROPOSED','NEEDS_REVIEW')",
                  (time.time() if now is None else now, owner, session_id))

    # -- simulated merchant quotes ---------------------------------------
    def set_quote(self, owner, session_id, item_id, price_usd, availability):
        self._run("INSERT INTO merchant_quotes (owner, session_id, item_id, price_usd,"
                  " availability) VALUES (?,?,?,?,?) ON CONFLICT(owner, session_id, item_id)"
                  " DO UPDATE SET price_usd=excluded.price_usd, availability=excluded.availability",
                  (owner, session_id, str(item_id), price_usd, availability))

    def get_quote(self, owner, session_id, item_id):
        row = self._one("SELECT price_usd, availability FROM merchant_quotes WHERE owner=?"
                        " AND session_id=? AND item_id=?",
                        (owner, session_id, str(item_id)))
        return dict(row) if row else None

    # -- reservations -----------------------------------------------------
    def insert_reservation(self, reservation):
        self._run("INSERT INTO reservations (reservation_id, proposal_id, owner, session_id,"
                  " item_id, title, brand, price_usd, quantity, status, note, created_at)"
                  " VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                  (reservation["reservation_id"], reservation["proposal_id"], reservation["owner"],
                   reservation["session_id"], reservation.get("item_id"), reservation.get("title"),
                   reservation.get("brand"), reservation.get("price_usd"),
                   int(reservation.get("quantity", 1)),
                   reservation.get("status", "draft_reserved"), reservation.get("note"),
                   reservation.get("created_at", time.time())))
        return self.get_reservation(reservation["reservation_id"])

    def get_reservation(self, reservation_id):
        row = self._one("SELECT * FROM reservations WHERE reservation_id=?", (reservation_id,))
        return dict(row) if row else None

    def get_reservation_by_proposal(self, proposal_id):
        row = self._one("SELECT * FROM reservations WHERE proposal_id=? ORDER BY created_at LIMIT 1",
                        (proposal_id,))
        return dict(row) if row else None

    def list_reservations(self, owner, session_id=None):
        if session_id is None:
            rows = self._all("SELECT * FROM reservations WHERE owner=? ORDER BY created_at DESC",
                             (owner,))
        else:
            rows = self._all("SELECT * FROM reservations WHERE owner=? AND session_id=?"
                             " ORDER BY created_at DESC", (owner, session_id))
        return [dict(r) for r in rows]

    def count_reservations(self, owner, session_id=None):
        if session_id is None:
            row = self._one("SELECT COUNT(*) AS n FROM reservations WHERE owner=?", (owner,))
        else:
            row = self._one("SELECT COUNT(*) AS n FROM reservations WHERE owner=? AND session_id=?",
                            (owner, session_id))
        return row["n"]

    # -- events -----------------------------------------------------------
    def add_event(self, owner, session_id, kind, detail=None, now=None):
        self._run("INSERT INTO events (owner, session_id, kind, detail_json, created_at)"
                  " VALUES (?,?,?,?,?)",
                  (owner, session_id, kind, _dumps(detail or {}),
                   time.time() if now is None else now))

    def list_events(self, owner, session_id=None, limit=200):
        if session_id is None:
            rows = self._all("SELECT * FROM events WHERE owner=? ORDER BY event_id DESC LIMIT ?",
                             (owner, int(limit)))
        else:
            rows = self._all("SELECT * FROM events WHERE owner=? AND session_id=?"
                             " ORDER BY event_id DESC LIMIT ?", (owner, session_id, int(limit)))
        out = []
        for r in rows:
            item = dict(r)
            item["detail"] = _loads(item.pop("detail_json"), {})
            out.append(item)
        return out
