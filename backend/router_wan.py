"""Connected-router WAN / PPPoE reads over the monitoring credential.

Stores fail-closed observations for DHCP-client and PPPoE-client uplinks and
default routes. Stale or unreachable reads become Unable to Verify — never an
invented online state. This does not change WAN settings. Real-router
acceptance remains external.
"""
from __future__ import annotations

import time

from fastapi import Depends, HTTPException

from .hotspot_sync import managed_router
from .models import RouterDevice, RouterWanObservation, StaffGrant
from .routeros_adapter import RouterOSClient, RouterOSError, load_routeros_monitoring_credential, read_router_wan

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


def observation_json(row: RouterWanObservation | None, now: int | None = None) -> dict:
    now = int(time.time() if now is None else now)
    if not row:
        return {
            'managed': False,
            'status': 'unable_to_verify',
            'freshness': 'none',
            'observed_at': None,
            'metrics': None,
            'last_error': None,
            'detail': 'No router WAN observation has been collected for this router.',
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
            'Router WAN/PPPoE status verified at the last collect.'
            if verified else
            ('The last WAN read is stale; live uplink state cannot be shown.'
             if freshness == 'stale' else
             (row.last_error and f'Unable to Verify ({row.last_error}).') or
             'Unable to Verify router WAN status; no invented online state is shown.')
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
            'message': 'WAN reads start after MikroMagic management logins exist and the router was verified Connected',
        })
    now = int(time.time() if now is None else now)
    row = s.get(RouterWanObservation, router.id) or RouterWanObservation(
        router_id=router.id, tenant_id=router.tenant_id, site_id=router.site_id,
        observed_at=0, status='unable_to_verify', metrics={}, updated=now,
    )
    if row not in s:
        s.add(row)
    try:
        credential = load_routeros_monitoring_credential(router.id)
        with client_factory(credential, router_id=router.id) as client:
            metrics = read_router_wan(client)
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


def register_router_wan(app, current, db, log):
    def owner(u, s):
        if u.role != 'sme' or s.get(StaffGrant, u.id):
            raise HTTPException(403, 'Only the business Owner/Admin can review router WAN status')

    def owner_router(s, u, id):
        owner(u, s)
        router = s.get(RouterDevice, id)
        if not router or router.tenant_id != u.tenant_id:
            raise HTTPException(404, 'Router not found')
        return router

    @app.get('/v1/routers/{id}/wan')
    def status(id: str, u=Depends(current), s=Depends(db)):
        owner_router(s, u, id)
        router, plan = managed_router(s, id, u.tenant_id)
        if not plan:
            return observation_json(None) | {
                'managed': False,
                'detail': 'WAN reads require a Connected managed router.',
            }
        row = s.get(RouterWanObservation, id)
        result = observation_json(row)
        if row is None:
            result = result | {'managed': True}
        return result

    @app.post('/v1/routers/{id}/wan/collect')
    def collect_now(id: str, u=Depends(current), s=Depends(db)):
        owner_router(s, u, id)
        factory = getattr(app.state, 'router_wan_client_factory', None) or getattr(
            app.state, 'router_health_client_factory', None
        ) or getattr(app.state, 'hotspot_client_factory', RouterOSClient)
        result = collect(s, id, factory)
        log(s, u, 'router_wan_collected' if result.get('collected') else 'router_wan_collect_failed', id)
        s.commit()
        return result
