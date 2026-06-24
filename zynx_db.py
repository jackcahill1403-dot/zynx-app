"""Zynx DB layer: one thin connect() that targets Turso/libSQL on the cloud
(when TURSO_DATABASE_URL + TURSO_AUTH_TOKEN are set) or local SQLite for dev.

No streamlit import here — config is read from os.environ only (Streamlit pushes
secrets.toml into the environment on the cloud). Rows are wrapped so existing
app code keeps using row["col"] even though libSQL returns bare tuples.
"""

import os
import sys
import time
import sqlite3
import tempfile

TURSO_URL = os.getenv("TURSO_DATABASE_URL", "").strip()
TURSO_TOKEN = os.getenv("TURSO_AUTH_TOKEN", "").strip()

# Set True once we successfully open an embedded replica (local file that syncs
# to the remote Turso primary). Reads then hit the local copy; writes are pushed
# to the primary after each commit so they survive a server restart.
_IS_REPLICA = False

# Bump on each deploy so /dbstatus confirms which code the live app is running.
DB_BUILD = "2026-06-24-batched-writes"

# Diagnostics (Phase-1 evidence). Filled in by _make_raw(); read via db_status().
_DIAG = {
    "build": DB_BUILD,
    "mode": "uninitialized",   # "replica" | "remote-direct" | "local-sqlite"
    "libsql_version": None,
    "replica_error": None,     # why the embedded replica fell back, if it did
    "primary_host": None,      # Turso primary host (region lives in the name)
    "connect_ms": None,        # time to open the connection
    "initial_sync_ms": None,   # time for the first replica sync()
}


def _log(msg):
    """Print to stderr so it shows in Streamlit Cloud's 'Manage app' logs."""
    print(f"[zynx-db] {msg}", file=sys.stderr, flush=True)


def db_status():
    """Snapshot of how the DB connection resolved. Safe to render in-app."""
    return dict(_DIAG)

# Local DB path: env override (tests) else the app's existing file location.
APP_DB = os.getenv("ZYNX_DB_PATH") or os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "zynx_v2.db"
)

_CONN = None  # process-wide singleton; persists across Streamlit reruns


class Row:
    """Result row supporting both name and index access, like sqlite3.Row."""
    __slots__ = ("_cols", "_vals", "_map")

    def __init__(self, columns, values):
        self._cols = list(columns)
        self._vals = tuple(values)
        self._map = {c: v for c, v in zip(self._cols, self._vals)}

    def __getitem__(self, key):
        if isinstance(key, int):
            return self._vals[key]
        return self._map[key]

    def keys(self):
        return list(self._cols)

    def get(self, key, default=None):
        return self._map.get(key, default)

    def __iter__(self):
        return iter(self._vals)

    def __len__(self):
        return len(self._vals)

    def __contains__(self, key):
        return key in self._map


class _Cursor:
    def __init__(self, raw_cursor):
        self._cur = raw_cursor

    def _cols(self):
        d = self._cur.description
        return [c[0] for c in d] if d else []

    def execute(self, sql, params=()):
        self._cur.execute(sql, params)
        return self

    def executemany(self, sql, seq):
        self._cur.executemany(sql, seq)
        return self

    def fetchone(self):
        r = self._cur.fetchone()
        return None if r is None else Row(self._cols(), r)

    def fetchall(self):
        cols = self._cols()
        return [Row(cols, r) for r in self._cur.fetchall()]

    def fetchmany(self, size=None):
        cols = self._cols()
        rows = self._cur.fetchmany(size) if size else self._cur.fetchmany()
        return [Row(cols, r) for r in rows]

    @property
    def rowcount(self):
        return self._cur.rowcount

    @property
    def lastrowid(self):
        return self._cur.lastrowid

    @property
    def description(self):
        return self._cur.description

    def close(self):
        pass  # no-op: connection is a shared singleton


class _Conn:
    def __init__(self, raw_conn):
        self._raw = raw_conn

    def cursor(self):
        return _Cursor(self._raw.cursor())

    def execute(self, sql, params=()):
        cur = _Cursor(self._raw.cursor())
        return cur.execute(sql, params)

    def commit(self):
        # On a Turso embedded replica, writes are forwarded to the remote
        # primary at write time (durable) and applied to the local file (so
        # reads see them immediately). We intentionally do NOT call sync() here:
        # sync() pulls the whole remote state and was costing ~2.5s PER commit
        # (measured via /dbstatus), making every message painfully slow. The
        # local replica is kept fresh in the background via sync_interval (set
        # in _make_raw), so cross-instance reads still converge.
        self._raw.commit()

    def close(self):
        pass  # no-op: shared singleton, do not tear down


def _wrap(raw_conn):
    return _Conn(raw_conn)


def using_turso():
    return bool(TURSO_URL and TURSO_TOKEN)


def _make_raw():
    global _IS_REPLICA
    if using_turso():
        import libsql  # lazy: only needed on the cloud
        _DIAG["libsql_version"] = getattr(libsql, "__version__", "?")
        # host only (no token) — the region is encoded in the hostname, e.g.
        # ...aws-eu-west-1.turso.io; tells us if the primary is far from the app.
        _DIAG["primary_host"] = TURSO_URL.split("://")[-1].split("/")[0]

        # Preferred: an embedded replica. A local SQLite file is kept in sync
        # with the remote Turso primary, so every read is served locally (~1ms)
        # instead of a transatlantic round-trip (~100ms). Writes go to the
        # primary and are pushed on commit (see _Conn.commit).
        try:
            local_path = os.getenv("ZYNX_REPLICA_PATH") or os.path.join(
                tempfile.gettempdir(), "zynx_replica.db"
            )
            t0 = time.perf_counter()
            # sync_interval = background pull cadence (seconds), so we never
            # block a commit on a sync. Older libsql lacks the kwarg → retry.
            try:
                conn = libsql.connect(
                    local_path, sync_url=TURSO_URL, auth_token=TURSO_TOKEN,
                    sync_interval=60,
                )
            except TypeError:
                conn = libsql.connect(
                    local_path, sync_url=TURSO_URL, auth_token=TURSO_TOKEN,
                )
            t1 = time.perf_counter()
            conn.sync()  # one initial pull of current remote state into the replica
            t2 = time.perf_counter()
            _DIAG["connect_ms"] = round((t1 - t0) * 1000, 1)
            _DIAG["initial_sync_ms"] = round((t2 - t1) * 1000, 1)
            _DIAG["mode"] = "replica"
            _IS_REPLICA = True
            _log(f"embedded replica OK · libsql={_DIAG['libsql_version']} · "
                 f"connect={_DIAG['connect_ms']}ms · sync={_DIAG['initial_sync_ms']}ms")
            return conn
        except Exception as e:
            # Replica unsupported/unavailable — fall back to a direct remote
            # connection (the previous behaviour) so the app still works.
            # Capture WHY: a silent fallback here means every read becomes a
            # transatlantic round-trip, which is the slowness we're chasing.
            _IS_REPLICA = False
            _DIAG["replica_error"] = repr(e)
            _DIAG["mode"] = "remote-direct"
            _log(f"embedded replica FELL BACK to remote-direct · reason: {e!r}")
            try:
                return libsql.connect(TURSO_URL, auth_token=TURSO_TOKEN)
            except Exception as e2:
                raise RuntimeError(f"Zynx database unavailable (Turso): {e2}") from e2
    _DIAG["mode"] = "local-sqlite"
    return sqlite3.connect(APP_DB, check_same_thread=False)


def connect():
    global _CONN
    if _CONN is None:
        _CONN = _wrap(_make_raw())
    return _CONN


def reset_connection_for_tests():
    global _CONN
    _CONN = None
