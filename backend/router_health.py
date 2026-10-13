"""Connected-router health reads over the monitoring credential.

Stores fail-closed observations for CPU, memory, temperature (when the board
exposes it) and DHCP presence. Stale or unreachable reads become Unable to
Verify — never invented live gauges. Real-router acceptance remains external.
"""
from __future__ import annotations

import time

from fastapi import Depends, HTTPException

from .hotspot_sync import managed_router
from .models import RouterDevice, RouterHealthObservation, StaffGrant
from .routeros_adapter import RouterOSClient, RouterOSError, load_routeros_monitoring_credential, read_router_health

FRESH_SECONDS = 180


def _freshness(observed_at: int | None, now: int) -> str:
    if not observed_at:
        return 'none'
    age = now - observed_at
    if age < 0:
        return 'none'
    if age <= FRESH_SECONDS:
        return 'fresh'
    return 'stale'


def observation_json(row: RouterHealthObservation | None, now: int | None = None) -> dict:
    now = int(time.time() if now is None else now)
    if not row:
        return {
            'managed': False,
            'status': 'unable_to_verify',
            'freshness': 'none',
            'observed_at': None,
            'metrics': None,
            'last_error': None,
            'detail': 'No router health observation has been collected for this router.',
            'real_device_acceptance': 'not_yet_performed',
        }
    freshness = _freshness(row.observed_at, now)
    verified = row.status == 'verified' and freshness == 'fresh'
    return {
        'managed': True,
        'router_id': row.router_id,
        'site_id': row.site_id,
        'status': 'verified' if verified else 'unable_to_verify',
        'freshness': freshness,
        'observed_at': row.observed_at,
        'metrics': dict(row.metrics or {}) if verified else None,
        'last_error': row.last_error,
        'detail': (
            'Router health verified at the last collect.'
            if verified else
            ('The last health read is stale; live gauges cannot be shown.'
             if freshness == 'stale' else
             (row.last_error and f'Unable to Verify ({row.last_error}).') or
             'Unable to Verify router health; no invented gauges are shown.')
        ),
        'real_device_acceptance': 'not_yet_performed',
    }


def collect(s, router_id, client_factory=RouterOSClient, now=None):
    router, plan = managed_router(s, router_id)
    if not router:
        raise HTTPException(404, 'Router not found')
    if not plan:
        raise HTTPException(409, {
            'code': 'router_not_managed',
            'message': 'Health reads start after MikroMagic management logins exist and the router was verified Connected',
        })
    now = int(time.time() if now is None else now)
    row = s.get(RouterHealthObservation, router.id) or RouterHealthObservation(
        router_id=router.id, tenant_id=router.tenant_id, site_id=router.site_id,
        observed_at=0, status='unable_to_verify', metrics={}, updated=now,
    )
    if row not in s:
        s.add(row)
    try:
        credential = load_routeros_monitoring_credential(router.id)
        with client_factory(credential, router_id=router.id) as client:
            metrics = read_router_health(client)
    except RouterOSError as error:
        row.status = 'unable_to_verify'
        row.last_error = error.code[:60]
        row.updated = now
        s.flush()
        return observation_json(row, now) | {'collected': False, 'aborted': error.code}

    row.tenant_id = router.tenant_id
    row.site_id = router.site_id
    row.observed_at = now
    row.status = 'verified'
    row.metrics = metrics
    row.last_error = None
    row.updated = now
    s.flush()
    return observation_json(row, now) | {'collected': True, 'aborted': None}


def register_router_health(app, current, db, log):
    def owner(u, s):
        if u.role != 'sme' or s.get(StaffGrant, u.id):
            raise HTTPException(403, 'Only the business Owner/Admin can review router health')

    def owner_router(s, u, id):
        owner(u, s)
        router = s.get(RouterDevice, id)
        if not router or router.tenant_id != u.tenant_id:
            raise HTTPException(404, 'Router not found')
        return router

    @app.get('/v1/routers/{id}/health')
    def status(id: str, u=Depends(current), s=Depends(db)):
        owner_router(s, u, id)
        router, plan = managed_router(s, id, u.tenant_id)
        if not plan:
            return observation_json(None) | {
                'managed': False,
                'detail': 'Health reads require a Connected managed router.',
            }
        row = s.get(RouterHealthObservation, id)
        result = observation_json(row)
        if row is None:
            result = result | {'managed': True}
        return result

    @app.post('/v1/routers/{id}/health/collect')
    def collect_now(id: str, u=Depends(current), s=Depends(db)):
        owner_router(s, u, id)
        factory = getattr(app.state, 'router_health_client_factory', None) or getattr(app.state, 'hotspot_client_factory', RouterOSClient)
        result = collect(s, id, factory)
        log(s, u, 'router_health_collected' if result.get('collected') else 'router_health_collect_failed', id)
        s.commit()
        return result
