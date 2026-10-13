"""Per-router REST serialization across concurrent callers."""
import threading
import time
import unittest
from unittest.mock import patch

from sqlalchemy import create_engine, text

from backend.routeros_adapter import RouterOSClient, RouterOSCredential, RouterOSError
from backend.routeros_lock import configure_routeros_lock, hold_router_rest_lock, _keys


class RecordingTransport:
    """httpx-compatible transport that records concurrent entry counts."""

    def __init__(self):
        self.active = 0
        self.max_active = 0
        self.lock = threading.Lock()
        self.calls = []

    def handle_request(self, request):
        import httpx
        with self.lock:
            self.active += 1
            self.max_active = max(self.max_active, self.active)
            self.calls.append(str(request.url))
        try:
            time.sleep(0.05)
            return httpx.Response(200, json={'.id': '*1', 'name': 'ok'})
        finally:
            with self.lock:
                self.active -= 1

    def close(self):
        pass


class RouterOSLockTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine('sqlite:///:memory:')
        configure_routeros_lock(self.engine)
        self.addCleanup(lambda: configure_routeros_lock(None))

    def test_hold_blocks_second_caller_until_release(self):
        order = []
        ready = threading.Event()
        release_first = threading.Event()

        def first():
            with hold_router_rest_lock('router-a', timeout_seconds=2):
                order.append('first-in')
                ready.set()
                release_first.wait(2)
                order.append('first-out')

        def second():
            ready.wait(2)
            with hold_router_rest_lock('router-a', timeout_seconds=2):
                order.append('second')

        t1 = threading.Thread(target=first)
        t2 = threading.Thread(target=second)
        t1.start()
        t2.start()
        self.assertTrue(ready.wait(2))
        time.sleep(0.05)
        self.assertEqual(order, ['first-in'])
        release_first.set()
        t1.join(2)
        t2.join(2)
        self.assertEqual(order, ['first-in', 'first-out', 'second'])

    def test_different_routers_do_not_block(self):
        barrier = threading.Barrier(2)
        seen = []

        def worker(name):
            with hold_router_rest_lock(name, timeout_seconds=2):
                seen.append(name + '-in')
                barrier.wait(2)
                seen.append(name + '-out')

        threads = [threading.Thread(target=worker, args=(n,)) for n in ('r1', 'r2')]
        for t in threads:
            t.start()
        for t in threads:
            t.join(2)
        self.assertEqual(set(seen[:2]), {'r1-in', 'r2-in'})

    def test_timeout_raises_router_busy(self):
        gate = threading.Event()

        def holder():
            with hold_router_rest_lock('busy-router', timeout_seconds=2):
                gate.set()
                time.sleep(0.4)

        t = threading.Thread(target=holder)
        t.start()
        self.assertTrue(gate.wait(2))
        with self.assertRaises(RouterOSError) as raised:
            with hold_router_rest_lock('busy-router', timeout_seconds=0.1):
                pass
        self.assertEqual(raised.exception.code, 'router_busy')
        t.join(2)

    def test_client_session_serializes_rest_for_one_router(self):
        transport = RecordingTransport()
        credential = RouterOSCredential('https://10.90.1.2', 'mm-monitor-abcdefgh', 'x')

        def worker():
            with RouterOSClient(credential, transport=transport, router_id='router-serial') as client:
                client.get('system/resource')
                client.get('ip/hotspot/active')

        threads = [threading.Thread(target=worker) for _ in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(3)
        self.assertEqual(transport.max_active, 1)
        self.assertEqual(len(transport.calls), 6)

    def test_advisory_key_stable(self):
        self.assertEqual(_keys('abc'), _keys('abc'))
        self.assertNotEqual(_keys('abc'), _keys('abd'))


class PostgresAdvisoryLockTests(unittest.TestCase):
    """Run only when a real PostgreSQL DATABASE_URL is available."""

    def test_pg_advisory_lock_blocks_other_connection(self):
        import os
        url = os.environ.get('DATABASE_URL', '')
        if not url.startswith('postgresql'):
            self.skipTest('PostgreSQL DATABASE_URL not configured')
        engine = create_engine(url, pool_pre_ping=True)
        configure_routeros_lock(engine)
        self.addCleanup(lambda: configure_routeros_lock(None))
        k1, k2 = _keys('pg-lock-router')
        with engine.connect() as holder:
            holder.execute(text('SELECT pg_advisory_lock(:k1, :k2)'), {'k1': k1, 'k2': k2})
            try:
                with self.assertRaises(RouterOSError) as raised:
                    with hold_router_rest_lock('pg-lock-router', timeout_seconds=0.2):
                        pass
                self.assertEqual(raised.exception.code, 'router_busy')
            finally:
                holder.execute(text('SELECT pg_advisory_unlock(:k1, :k2)'), {'k1': k1, 'k2': k2})


if __name__ == '__main__':
    unittest.main()
