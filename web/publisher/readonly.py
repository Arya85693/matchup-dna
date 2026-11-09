"""Opening a forecast store without any possibility of writing to it.

`Store(path)` (matchup_dna/forecasting/store.py, a protected file) opens a read-write connection, runs its schema script
and creates the file if the path does not exist. The website must never do that to the live store. Instead:

    open_readonly(path)   a Store whose connection is SQLite's read-only URI mode plus PRAGMA query_only; the store's
                          own read methods (settled, predictions, runs, verify, ...) work on it unchanged
    copy_store(path, to)  a consistent copy made with SQLite's online backup API from a read-only connection, so the
                          live file is held for milliseconds and every later query reads the copy

The live store uses SQLite's default rollback journal. A reader holding a shared lock while the scheduled job commits
can make that commit wait and fail, so the publisher copies first, checks that no run is in progress, and never holds
the live file open while it builds the website files.
"""
import sqlite3
from pathlib import Path

from matchup_dna.forecasting.store import Store


class ReadOnlyError(RuntimeError):
    pass


def _connect(path):
    path = Path(path).resolve()
    if not path.is_file():
        raise ReadOnlyError(f"no store at {path.name}: refusing to create one")
    db = sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA query_only = ON")
    return db


def open_readonly(path):
    """A Store bound to a read-only connection. Store.__init__ is bypassed on purpose (it would run DDL)."""
    store = Store.__new__(Store)
    store.path = Path(path)
    store.db = _connect(path)
    store.mode = store.info("mode")
    if store.mode is None:
        store.close()
        raise ReadOnlyError(f"{Path(path).name} is not a forecast store (no mode recorded)")
    return store


def runs_in_progress(store):
    return [r["run_id"] for r in store.db.execute("SELECT run_id FROM runs WHERE status = 'running'")]


def copy_store(source, destination):
    """Copies `source` to `destination` with the backup API, reading the source through a read-only connection."""
    src = _connect(source)
    try:
        dst = sqlite3.connect(str(destination))
        try:
            src.backup(dst)
        finally:
            dst.close()
    finally:
        src.close()
    return Path(destination)
