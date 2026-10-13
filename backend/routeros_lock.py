"""Serialize all RouterOS REST traffic to one router across API workers.

RouterOS processes REST one request at a time per router; aborted sockets do
not free the queue (see docs/ROUTEROS-REST-API-NOTES.md). Hold one lock for the
whole client session so monitoring, collect and Safe Change never interleave.
"""
from __future__ import annotations

import hashlib
import os
import threading
import time
from contextlib import contextmanager

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from .routeros_adapter import RouterOSError

# In-process gate so a single worker does not open many DB lock connections.
_LOCAL = threading.Lock()
_LOCAL_LOCKS: dict[str, threading.Lock] = {}
_ENGINE: Engine | None = None
DEFAULT_TIMEOUT_SECONDS = 90


def configure_routeros_lock(engine: Engine | None):
    """Register the app/worker engine used for cross-process advisory locks."""
    global _ENGINE
    _ENGINE = engine


def _engine() -> Engine | None:
    if _ENGINE is not None:
        return _ENGINE
    url = os.environ.get('DATABASE_URL')
    if not url:
        return None
    engine = create_engine(url, pool_pre_ping=True, pool_size=1, max_overflow=0)
    configure_routeros_lock(engine)
    return engine


def _keys(router_id: str) -> tuple[int, int]:
    digest = hashlib.sha256(f'mikromagic-routeros-rest-v1:{router_id}'.encode()).digest()
    return int.from_bytes(digest[:4], 'big') & 0x7FFFFFFF, int.from_bytes(digest[4:8], 'big') & 0x7FFFFFFF


def _local_lock(router_id: str) -> threading.Lock:
    with _LOCAL:
        lock = _LOCAL_LOCKS.get(router_id)
        if lock is None:
            lock = threading.Lock()
            _LOCAL_LOCKS[router_id] = lock
        return lock


def _dialect(engine: Engine) -> str:
    return engine.dialect.name


@contextmanager
def hold_router_rest_lock(router_id: str, timeout_seconds: float | None = None):
    """Exclusive lock for one router for the duration of a REST client session."""
    if not isinstance(router_id, str) or not router_id.strip():
        raise RouterOSError('resource_invalid', 'Router identifier is required for REST serialization', 500)
    timeout = float(timeout_seconds if timeout_seconds is not None else os.environ.get('MIKROMAGIC_ROUTEROS_LOCK_TIMEOUT_SECONDS', DEFAULT_TIMEOUT_SECONDS))
    if timeout <= 0:
        timeout = DEFAULT_TIMEOUT_SECONDS
    local = _local_lock(router_id)
    deadline = time.monotonic() + timeout
    if not local.acquire(timeout=timeout):
        raise RouterOSError('router_busy', 'Another MikroMagic operation is already talking to this router; try again shortly', 409)
    conn = None
    try:
        engine = _engine()
        if engine is not None and _dialect(engine) == 'postgresql':
            k1, k2 = _keys(router_id)
            conn = engine.connect()
            # Session-scoped advisory lock; SET lock_timeout bounds the wait.
            ms = max(1, int((deadline - time.monotonic()) * 1000))
            conn.execute(text(f"SET lock_timeout = '{ms}ms'"))
            try:
                conn.execute(text('SELECT pg_advisory_lock(:k1, :k2)'), {'k1': k1, 'k2': k2})
            except Exception as error:
                conn.close()
                conn = None
                raise RouterOSError(
                    'router_busy',
                    'Another MikroMagic operation is already talking to this router; try again shortly',
                    409,
                ) from error
        elif engine is not None and _dialect(engine) == 'sqlite':
            # SQLite tests / single-process: the threading lock is sufficient.
            pass
        yield
    finally:
        if conn is not None:
            try:
                k1, k2 = _keys(router_id)
                conn.execute(text('SELECT pg_advisory_unlock(:k1, :k2)'), {'k1': k1, 'k2': k2})
            except Exception:
                pass
            try:
                conn.close()
            except Exception:
                pass
        local.release()
