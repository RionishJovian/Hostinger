import re
import time
from datetime import datetime, time as day_time, timedelta
from zoneinfo import ZoneInfo

from fastapi import Depends
from sqlalchemy import func, select

from .hub_orchestrator import connection_is_fresh
from .models import FinancialEvent, RouterDevice, RouterPlan, Site, SiteIncident, TenantSubscription


_SENSITIVE_KEY_PARTS = frozenset({
    'password', 'secret', 'token', 'credential', 'privatekey', 'private_key',
    'apikey', 'api_key', 'wireguardprivatekey', 'wireguard_private_key',
})


def _key_parts(key):
    value = str(key).lower()
    compact = re.sub(r'[^a-z0-9]', '', value)
    return value, compact


def _sensitive_key(key):
    value, compact = _key_parts(key)
    return any(part in value or re.sub(r'[^a-z0-9]', '', part) in compact for part in _SENSITIVE_KEY_PARTS)


def redact_sensitive_keys(value):
    if isinstance(value, dict):
        return {key: redact_sensitive_keys(item) for key, item in value.items() if not _sensitive_key(key)}
    if isinstance(value, (list, tuple)):
        return [redact_sensitive_keys(item) for item in value]
    return value


def _today_bounds(now):
    local = datetime.fromtimestamp(now, ZoneInfo('Asia/Yangon'))
    start = datetime.combine(local.date(), day_time.min, local.tzinfo)
    return int(start.timestamp()), int((start + timedelta(days=1)).timestamp())


def register_owner_api(app, current, db, owner):
    @app.get('/v1/owner/overview')
    def overview(u=Depends(current), s=Depends(db)):
        owner(u)
        now = int(time.time())
        sites = list(s.scalars(select(Site).where(Site.tenant_id == u.tenant_id).order_by(Site.created, Site.id)))
        plans = {plan.router_id: plan for plan in s.scalars(select(RouterPlan).where(RouterPlan.tenant_id == u.tenant_id))}
        routers = []
        for router in s.scalars(select(RouterDevice).where(RouterDevice.tenant_id == u.tenant_id).order_by(RouterDevice.created, RouterDevice.id)):
            plan = plans.get(router.id)
            last_seen = max(
                (stamp for stamp in (
                    plan.handshake_verified_at if plan else None,
                    plan.management_read_verified_at if plan else None,
                ) if stamp is not None),
                default=None,
            )
            routers.append({'id': router.id, 'name': router.name, 'connected': bool(plan and connection_is_fresh(plan, now)), 'last_seen': last_seen})
        open_incidents = s.scalar(
            select(func.count()).select_from(SiteIncident).where(
                SiteIncident.tenant_id == u.tenant_id,
                SiteIncident.status != 'resolved',
            )
        ) or 0
        lower, upper = _today_bounds(now)
        events = s.scalars(select(FinancialEvent).where(
            FinancialEvent.tenant_id == u.tenant_id,
            FinancialEvent.occurred_at >= lower,
            FinancialEvent.occurred_at < upper,
        ))
        today_revenue = sum(event.amount if event.kind == 'collection' else -event.amount for event in events)
        subscription = s.get(TenantSubscription, u.tenant_id)
        result = {
            'shops': [{'id': site.id, 'name': site.name} for site in sites],
            'routers': routers,
            'open_incidents': open_incidents,
            'today_revenue': {'amount': today_revenue, 'currency': 'MMK'},
            'subscription_status': subscription.state if subscription else 'unassigned',
        }
        return redact_sensitive_keys(result)
