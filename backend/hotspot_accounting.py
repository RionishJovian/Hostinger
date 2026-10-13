"""HotSpot session and accounting reads for Connected routers (step 6).

Collects active guests and MikroMagic HotSpot user counters over the monitoring
credential, applies first-login activation and usage updates, and stores a
fail-closed observation. Stale or unreachable reads become Unable to Verify —
never an invented live zero. Real-router acceptance remains external.
"""
from __future__ import annotations

import time

from fastapi import Depends, HTTPException
from sqlalchemy import select

from .hotspot_sync import USER_COMMENT, managed_router
from .models import Entitlement, HotspotSessionObservation, RouterDevice, StaffGrant, Voucher
from .routeros_adapter import (
    RouterOSClient,
    RouterOSError,
    list_hotspot_active,
    list_mikromagic_hotspot_users,
    load_routeros_monitoring_credential,
)
from .voucher_codes import find_voucher, normalize

FRESH_SECONDS = 180
TRANSPORT_ERRORS = {
    'unreachable', 'timeout', 'transport_error', 'tls_verification_failed',
    'authentication_failed', 'relay_unavailable', 'relay_invalid',
    'credential_missing', 'credential_invalid', 'credential_permissions',
    'credential_identity', 'transport_policy',
}


def _has_exp_marker(comment: str) -> bool:
    return '|exp=' in (comment or '')


def _apply_router_usage(target, policy, *, bytes_total, uptime=None, now=None, activate=True):
    """Monotonic first-login activation and usage on an entitlement or voucher row."""
    activations = 0
    usage_updates = 0
    service = (policy or {}).get('service')
    if activate and service in ('internet', 'combined') and target.activated is None:
        target.activated = now
        activations = 1
    if bytes_total > (target.used_bytes or 0):
        target.used_bytes = bytes_total
        usage_updates += 1
    if uptime is not None and (policy or {}).get('clock') == 'connected':
        if uptime > (target.connected_seconds or 0):
            target.connected_seconds = uptime
            usage_updates += 1
    return activations, usage_updates


def _freshness(observed_at: int | None, now: int) -> str:
    if not observed_at:
        return 'none'
    age = now - observed_at
    if age < 0:
        return 'none'
    if age <= FRESH_SECONDS:
        return 'fresh'
    return 'stale'


def _sanitize_guest(session: dict, voucher: Voucher | None) -> dict:
    return {
        'voucher_id': voucher.id if voucher else None,
        'code_hint': voucher.code_hint if voucher else None,
        'user_present': True,
        'mac': session.get('mac'),
        'address': session.get('address'),
        'server': session.get('server'),
        'uptime_seconds': int(session.get('uptime_seconds') or 0),
        'bytes_in': int(session.get('bytes_in') or 0),
        'bytes_out': int(session.get('bytes_out') or 0),
        'mikromagic_owned': bool(voucher),
    }


def observation_json(row: HotspotSessionObservation | None, now: int | None = None) -> dict:
    now = int(time.time() if now is None else now)
    if not row:
        return {
            'managed': False,
            'status': 'unable_to_verify',
            'freshness': 'none',
            'observed_at': None,
            'active_count': None,
            'active_guests': [],
            'activations_applied': 0,
            'usage_updated': 0,
            'last_error': None,
            'detail': 'No HotSpot session observation has been collected for this router.',
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
        'active_count': row.active_count if verified else None,
        'active_guests': list(row.guests or []) if verified else [],
        'activations_applied': row.activations_applied,
        'usage_updated': row.usage_updated,
        'last_error': row.last_error,
        'detail': (
            f'{row.active_count} active MikroMagic guest session(s) verified at the last collect.'
            if verified else
            ('The last session read is stale; connected customers cannot be shown as live.'
             if freshness == 'stale' else
             (row.last_error and f'Unable to Verify ({row.last_error}).') or
             'Unable to Verify HotSpot sessions; no invented live count is shown.')
        ),
        'real_device_acceptance': 'not_yet_performed',
    }


def collect(s, router_id, client_factory=RouterOSClient, now=None):
    """Read active sessions and user accounting; update entitlements when evidence is fresh."""
    router, plan = managed_router(s, router_id)
    if not router:
        raise HTTPException(404, 'Router not found')
    if not plan:
        raise HTTPException(409, {'code': 'router_not_managed', 'message': 'Session reads start after MikroMagic logins exist and the router was verified Connected'})
    now = int(time.time() if now is None else now)
    row = s.get(HotspotSessionObservation, router.id) or HotspotSessionObservation(
        router_id=router.id, tenant_id=router.tenant_id, site_id=router.site_id,
        observed_at=0, status='unable_to_verify', active_count=0, guests=[],
        activations_applied=0, usage_updated=0, updated=now,
    )
    if row not in s:
        s.add(row)
    try:
        credential = load_routeros_monitoring_credential(router.id)
        with client_factory(credential, router_id=router.id) as client:
            active = list_hotspot_active(client)
            users = list_mikromagic_hotspot_users(client, USER_COMMENT)
    except RouterOSError as error:
        row.status = 'unable_to_verify'
        row.last_error = error.code[:60]
        row.updated = now
        # Keep prior guests/count but do not present them as live when collect fails.
        s.flush()
        return observation_json(row, now) | {'collected': False, 'aborted': error.code}

    users_by_name = {item['name']: item for item in users}
    guests = []
    activations = 0
    usage_updates = 0
    seen_codes = set()

    for session in active:
        code = normalize(session['user'])
        if not code or code in seen_codes:
            continue
        voucher = find_voucher(s, router.tenant_id, code)
        user = users_by_name.get(session['user']) or users_by_name.get(code)
        owned = bool(voucher and user)
        if not owned:
            # Foreign HotSpot sessions are ignored for counts and activation.
            continue
        seen_codes.add(code)
        guests.append(_sanitize_guest(session, voucher))
        bytes_total = int(user['bytes_in'] + user['bytes_out']) if user else int(session['bytes_in'] + session['bytes_out'])
        uptime = int(user['uptime_seconds'] if user else session['uptime_seconds'])
        entitlement = s.scalar(select(Entitlement).where(Entitlement.voucher_id == voucher.id))
        if entitlement and not entitlement.revoked:
            # App-redeemed path: keep activation/usage on the entitlement only.
            a, u = _apply_router_usage(
                entitlement, entitlement.policy, bytes_total=bytes_total, uptime=uptime, now=now,
            )
            activations += a
            usage_updates += u
        elif not entitlement:
            # Café / router HotSpot login: no guest redemption, record on the voucher.
            a, u = _apply_router_usage(
                voucher, voucher.policy, bytes_total=bytes_total, uptime=uptime, now=now,
            )
            activations += a
            usage_updates += u

    # Users with |exp= but not currently active still count as first-login activated.
    for user in users:
        code = normalize(user['name'])
        if not code or code in seen_codes or not _has_exp_marker(user['comment']):
            continue
        voucher = find_voucher(s, router.tenant_id, code)
        if not voucher:
            continue
        bytes_total = int(user['bytes_in'] + user['bytes_out'])
        entitlement = s.scalar(select(Entitlement).where(Entitlement.voucher_id == voucher.id))
        if entitlement and not entitlement.revoked:
            a, u = _apply_router_usage(
                entitlement, entitlement.policy, bytes_total=bytes_total, now=now,
            )
            activations += a
            usage_updates += u
        elif not entitlement:
            a, u = _apply_router_usage(
                voucher, voucher.policy, bytes_total=bytes_total, now=now,
            )
            activations += a
            usage_updates += u

    row.tenant_id = router.tenant_id
    row.site_id = router.site_id
    row.observed_at = now
    row.status = 'verified'
    row.active_count = len(guests)
    row.guests = guests
    row.activations_applied = activations
    row.usage_updated = usage_updates
    row.last_error = None
    row.updated = now
    s.flush()
    return observation_json(row, now) | {'collected': True, 'aborted': None}


def tenant_summary(s, tenant_id, now=None):
    """Aggregate verified active guests across managed routers; fail closed when stale."""
    now = int(time.time() if now is None else now)
    rows = list(s.scalars(select(HotspotSessionObservation).where(HotspotSessionObservation.tenant_id == tenant_id)))
    if not rows:
        return {
            'status': 'unable_to_verify',
            'freshness': 'none',
            'active_count': None,
            'routers_observed': 0,
            'detail': 'No HotSpot session observation has been collected yet.',
            'real_device_acceptance': 'not_yet_performed',
        }
    fresh = [row for row in rows if row.status == 'verified' and _freshness(row.observed_at, now) == 'fresh']
    if not fresh:
        newest = max(rows, key=lambda row: row.observed_at or 0)
        return {
            'status': 'unable_to_verify',
            'freshness': _freshness(newest.observed_at, now),
            'active_count': None,
            'routers_observed': len(rows),
            'observed_at': newest.observed_at,
            'detail': 'HotSpot session evidence is missing or stale; connected customers cannot be shown as live.',
            'real_device_acceptance': 'not_yet_performed',
        }
    total = sum(row.active_count for row in fresh)
    return {
        'status': 'verified',
        'freshness': 'fresh',
        'active_count': total,
        'routers_observed': len(fresh),
        'observed_at': max(row.observed_at for row in fresh),
        'detail': f'{total} active MikroMagic guest session(s) across {len(fresh)} router(s).',
        'real_device_acceptance': 'not_yet_performed',
    }


def guest_network_evidence(s, guest_id, tenant_id, now=None):
    """Match a guest's vouchers to the newest relevant router observation."""
    now = int(time.time() if now is None else now)
    passes = list(s.scalars(select(Entitlement).where(Entitlement.tenant_id == tenant_id, Entitlement.guest_id == guest_id)))
    voucher_ids = [item.voucher_id for item in passes if item.voucher_id]
    if not voucher_ids:
        return {
            'status': 'unavailable',
            'freshness': 'none',
            'detail': 'No pass is linked for live HotSpot session matching.',
            'observed_at': None,
        }
    vouchers = {item.id: item for item in s.scalars(select(Voucher).where(Voucher.id.in_(voucher_ids)))}
    site_ids = {vouchers[vid].site_id for vid in voucher_ids if vouchers.get(vid) and vouchers[vid].site_id}
    query = select(HotspotSessionObservation).where(HotspotSessionObservation.tenant_id == tenant_id)
    if site_ids:
        query = query.where(HotspotSessionObservation.site_id.in_(site_ids))
    rows = list(s.scalars(query.order_by(HotspotSessionObservation.observed_at.desc())))
    if not rows:
        return {
            'status': 'unavailable',
            'freshness': 'none',
            'detail': 'No live RouterOS session or accounting evidence is available for this guest.',
            'observed_at': None,
        }
    row = rows[0]
    freshness = _freshness(row.observed_at, now)
    hints = {vouchers[vid].code_hint for vid in voucher_ids if vouchers.get(vid)}
    matched = [guest for guest in (row.guests or []) if guest.get('code_hint') in hints]
    if row.status == 'verified' and freshness == 'fresh':
        return {
            'status': 'verified' if matched else 'verified_absent',
            'freshness': 'fresh',
            'observed_at': row.observed_at,
            'active_for_guest': len(matched),
            'detail': (
                f'{len(matched)} active HotSpot session(s) match this guest’s pass hint(s).'
                if matched else
                'Router observation is fresh; no active HotSpot session matches this guest’s pass.'
            ),
        }
    return {
        'status': 'unable_to_verify',
        'freshness': freshness,
        'observed_at': row.observed_at,
        'detail': 'HotSpot session evidence is missing or stale for this guest.',
    }


def register_hotspot_accounting(app, current, db, log):
    def owner(u, s):
        if u.role != 'sme' or s.get(StaffGrant, u.id):
            raise HTTPException(403, 'Only the business Owner/Admin can review HotSpot sessions')

    def owner_router(s, u, id):
        owner(u, s)
        router = s.get(RouterDevice, id)
        if not router or router.tenant_id != u.tenant_id:
            raise HTTPException(404, 'Router not found')
        return router

    @app.get('/v1/routers/{id}/hotspot-sessions')
    def status(id: str, u=Depends(current), s=Depends(db)):
        owner_router(s, u, id)
        router, plan = managed_router(s, id, u.tenant_id)
        if not plan:
            return observation_json(None) | {'managed': False, 'detail': 'Session reads require a Connected managed router.'}
        return observation_json(s.get(HotspotSessionObservation, id))

    @app.post('/v1/routers/{id}/hotspot-sessions/collect')
    def collect_now(id: str, u=Depends(current), s=Depends(db)):
        owner_router(s, u, id)
        factory = getattr(app.state, 'hotspot_accounting_client_factory', None) or getattr(app.state, 'hotspot_client_factory', RouterOSClient)
        result = collect(s, id, factory)
        log(s, u, 'router_hotspot_sessions_collected', id)
        s.commit()
        return result

    @app.get('/v1/hotspot-sessions/summary')
    def summary(u=Depends(current), s=Depends(db)):
        owner(u, s)
        return tenant_summary(s, u.tenant_id)
