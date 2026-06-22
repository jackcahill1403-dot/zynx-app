"""Zynx DB layer: one thin connect() that targets Turso/libSQL on the cloud
(when TURSO_DATABASE_URL + TURSO_AUTH_TOKEN are set) or local SQLite for dev.

No streamlit import here — config is read from os.environ only (Streamlit pushes
secrets.toml into the environment on the cloud). Rows are wrapped so existing
app code keeps using row["col"] even though libSQL returns bare tuples.
"""

import os
import sqlite3
import tempfile

TURSO_URL = os.getenv("TURSO_DATABASE_URL", "").strip()
TURSO_TOKEN = os.getenv("TURSO_AUTH_TOKEN", "").strip()

# Set True once we successfully open an embedded replica (local file that syncs
# to the remote Turso primary). Reads then hit the local copy; writes are pushed
# to the primary after each commit so they survive a server restart.
_IS_REPLICA = False

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
        self._raw.commit()
        # Push local writes to the remote primary so they persist across server
        # restarts (the local replica file is ephemeral on the cloud host).
        if _IS_REPLICA:
            try:
                self._raw.sync()
            except Exception:
                pass

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

        # Preferred: an embedded replica. A local SQLite file is kept in sync
        # with the remote Turso primary, so every read is served locally (~1ms)
        # instead of a transatlantic round-trip (~100ms). Writes go to the
        # primary and are pushed on commit (see _Conn.commit).
        try:
            local_path = os.getenv("ZYNX_REPLICA_PATH") or os.path.join(
                tempfile.gettempdir(), "zynx_replica.db"
            )
            conn = libsql.connect(
                local_path, sync_url=TURSO_URL, auth_token=TURSO_TOKEN
            )
            conn.sync()  # pull current remote state into the fresh local replica
            _IS_REPLICA = True
            return conn
        except Exception:
            # Replica unsupported/unavailable — fall back to a direct remote
            # connection (the previous behaviour) so the app still works.
            _IS_REPLICA = False
            try:
                return libsql.connect(TURSO_URL, auth_token=TURSO_TOKEN)
            except Exception as e:
                raise RuntimeError(f"Zynx database unavailable (Turso): {e}") from e
    return sqlite3.connect(APP_DB, check_same_thread=False)


def connect():
    global _CONN
    if _CONN is None:
        _CONN = _wrap(_make_raw())
    return _CONN


def reset_connection_for_tests():
    global _CONN
    _CONN = None
