"""Guest-owned access diagnosis from stored records, never inferred router state."""
import time

from fastapi import Depends, HTTPException
from sqlalchemy import select

from .models import Entitlement, Order, Voucher


def _quota(entitlement, now):
    policy = entitlement.policy
    mode = policy.get('mode')
    service = policy.get('service')
    result = {
        'source': 'mikromagic_record_not_router_verified',
        'observed_at': None,
        'data': None,
        'time': None,
    }
    exhausted = []
    if service in ('internet', 'combined') and mode in ('data', 'both'):
        limit = int(float(policy.get('gb', 0)) * 1_000_000_000)
        used = max(0, entitlement.used_bytes or 0)
        result['data'] = {'used_bytes': used, 'limit_bytes': limit, 'remaining_bytes': max(0, limit - used)}
        if limit and used >= limit:
            exhausted.append('data')
    if mode in ('time', 'both') and service in ('internet', 'combined'):
        limit = int(float(policy.get('hours', 0)) * 3600)
        if policy.get('clock') == 'connected':
            used = max(0, entitlement.connected_seconds or 0)
            basis = 'stored_connected_seconds'
        else:
            used = max(0, now - entitlement.activated) if entitlement.activated else 0
            basis = 'elapsed_since_activation'
        result['time'] = {'used_seconds': used, 'limit_seconds': limit, 'remaining_seconds': max(0, limit - used), 'basis': basis}
        if limit and used >= limit:
            exhausted.append('time')
    return result, exhausted


def _order_item(order):
    messages = {
        'pending': ('awaiting_review', 'Payment evidence is waiting for business review.', 'Wait for the business to review the payment.'),
        'needs_evidence': ('evidence_needed', order.reason or 'The business requested more payment evidence.', 'Open this order and resubmit the requested evidence.'),
        'rejected': ('payment_rejected', order.reason or 'The payment submission was rejected.', 'Review the reason and contact the business before trying again.'),
        'refunded': ('access_stopped', order.reason or 'A refund was recorded and the pass was revoked.', 'Contact the business if this record is unexpected.'),
        'approved': ('provisioning_pending', 'Payment is approved, but network activation is not verified.', 'Keep the order reference and ask the business to check provisioning.'),
    }
    state, detail, action = messages.get(order.status, ('unknown', 'The stored order state is not recognized.', 'Contact the business with this order reference.'))
    return {
        'kind': 'order', 'id': order.id, 'site_id': order.site_id,
        'name': order.snapshot.get('name', 'Access order'), 'state': state,
        'detail': detail, 'safe_action': action, 'recorded_at': order.created,
        'reason': order.reason, 'fulfillment': order.fulfillment,
    }


def _pass_item(entitlement, voucher, now):
    quota, exhausted = _quota(entitlement, now)
    if entitlement.revoked:
        state, detail, action = 'access_stopped', 'This pass is revoked in MikroMagic.', 'Contact the business with this pass reference if the revocation is unexpected.'
    elif voucher and voucher.disabled_at:
        state, detail, action = 'access_paused', 'The business has disabled this voucher. Your activation and usage history are kept.', 'Contact the business; they can re-enable the voucher.'
    elif exhausted:
        state = 'quota_exhausted'
        detail = 'The stored {} allowance is exhausted.'.format(' and '.join(exhausted))
        action = 'Ask the business about a new package. Router enforcement still needs live verification.'
    elif entitlement.activated is None:
        state, detail, action = 'provisioning_pending', 'The pass exists, but no activation is recorded.', 'Ask the business to check provisioning. Do not redeem or pay again unless instructed.'
    else:
        state, detail, action = 'locally_active_unverified', 'MikroMagic has an activation record, but no live router session evidence.', 'Reconnect to the guest network, then contact the business if access still fails.'
    return {
        'kind': 'pass', 'id': entitlement.id, 'site_id': entitlement.site_id,
        'name': entitlement.policy.get('name', 'Access pass'), 'state': state,
        'detail': detail, 'safe_action': action,
        'source': 'voucher' if entitlement.voucher_id else 'order',
        'source_id': entitlement.voucher_id or entitlement.order_id,
        'voucher_code_hint': voucher.code_hint if voucher else None,
        'recorded_at': voucher.redeemed_at if voucher else entitlement.activated,
        'activation': entitlement.activated, 'quota': quota,
    }


def register_access_diagnostics(app, current, db):
    @app.get('/v1/my-access/diagnosis')
    def diagnosis(u=Depends(current), s=Depends(db)):
        if u.role != 'guest':
            raise HTTPException(403, 'Guest account required')
        now = int(time.time())
        orders = list(s.scalars(select(Order).where(Order.tenant_id == u.tenant_id, Order.guest_id == u.id).order_by(Order.created.desc())))
        passes = list(s.scalars(select(Entitlement).where(Entitlement.tenant_id == u.tenant_id, Entitlement.guest_id == u.id)))
        voucher_ids = [item.voucher_id for item in passes if item.voucher_id]
        vouchers = {item.id: item for item in s.scalars(select(Voucher).where(Voucher.id.in_(voucher_ids)))} if voucher_ids else {}
        entitlement_orders = {item.order_id for item in passes if item.order_id}
        items = [_pass_item(item, vouchers.get(item.voucher_id), now) for item in passes]
        items.extend(_order_item(item) for item in orders if item.id not in entitlement_orders)
        items.sort(key=lambda item: (item['recorded_at'] or 0, item['id']), reverse=True)
        return {
            'generated_at': now,
            'network_evidence': {
                'status': 'unavailable',
                'freshness': 'none',
                'detail': 'No live RouterOS session or accounting evidence is available for this guest.',
            },
            'items': items,
        }
