import re
import time
from datetime import datetime, time as day_time, timedelta
from zoneinfo import ZoneInfo

from fastapi import Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from .hub_orchestrator import connection_is_fresh
from .models import (
    AgentCommission,
    Audit,
    FinancialEvent,
    ManagedDevice,
    RouterChange,
    RouterDevice,
    RouterPlan,
    Site,
    SiteIncident,
    Tenant,
    TenantSubscription,
)


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


class ExplainLineIn(BaseModel):
    line: str = Field(min_length=1, max_length=4000)


class TerminalCommandIn(BaseModel):
    router_id: str = Field(min_length=1, max_length=64)
    command: str = Field(min_length=1, max_length=4000)


class ScriptProposalIn(BaseModel):
    router_id: str = Field(min_length=1, max_length=64)
    script_id: str = Field(min_length=1, max_length=120)


class AdvisorIn(BaseModel):
    question: str = Field(min_length=1, max_length=4000)


class AdvisorProposalIn(BaseModel):
    router_id: str = Field(min_length=1, max_length=64)
    recommendation: str = Field(min_length=1, max_length=4000)


class ConfirmDeleteIn(BaseModel):
    confirm: bool = False


class UpgradeIn(BaseModel):
    tenant_id: str = Field(min_length=1, max_length=64)
    plan: str = Field(min_length=1, max_length=80)


class TestLabIn(BaseModel):
    router_id: str = Field(min_length=1, max_length=64)


def _platform_admin(u):
    if u.role != 'platform' or not u.platform_owner:
        raise HTTPException(403, 'Platform administrator permission required')


def _visible_router(s, u, router_id):
    router = s.scalar(select(RouterDevice).where(
        RouterDevice.id == router_id,
        RouterDevice.tenant_id == u.tenant_id,
    ))
    if not router:
        raise HTTPException(404, 'Router not found')
    return router


def _coming_soon(capability):
    return {'status': 'coming_soon', 'capability': capability}


def _audit(s, u, action, target):
    s.add(Audit(actor_id=u.id, tenant_id=u.tenant_id, action=action, target=target, created=int(time.time())))
    s.commit()


_TERMINAL_BLOCK = re.compile(
    r'(?:^|[\s/])(reboot|shutdown|reset-configuration)(?:$|[\s;])|'
    r'wireguard.{0,40}private[-_ ]?key|hub[-_ ]?key|(?:udp\s*)?51820|listen[-_ ]?port',
    re.IGNORECASE,
)


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

    @app.get('/v1/owner/fleet')
    def fleet(u=Depends(current), s=Depends(db)):
        owner(u)
        now = int(time.time())
        plans = {row.router_id: row for row in s.scalars(select(RouterPlan).where(RouterPlan.tenant_id == u.tenant_id))}
        rows = []
        for router in s.scalars(select(RouterDevice).where(RouterDevice.tenant_id == u.tenant_id).order_by(RouterDevice.created, RouterDevice.id)):
            plan = plans.get(router.id)
            rows.append({
                'id': router.id,
                'site_id': router.site_id,
                'name': router.name,
                'model': router.model,
                'routeros': router.reported_routeros,
                'connected': bool(plan and connection_is_fresh(plan, now)),
                'last_seen': max((value for value in (
                    plan.handshake_verified_at if plan else None,
                    plan.management_read_verified_at if plan else None,
                ) if value is not None), default=None),
                'router_path': f'/app/routers?router={router.id}',
            })
        return redact_sensitive_keys(rows)

    @app.get('/v1/owner/devices')
    def devices(u=Depends(current), s=Depends(db)):
        owner(u)
        rows = [{
            'id': row.id,
            'site_id': row.site_id,
            'kind': row.kind,
            'name': row.name,
            'vendor': row.vendor,
            'model': row.model,
            'location': row.location,
            'firmware': row.firmware,
            'last_seen': row.last_seen,
            'ports': _coming_soon('device_ports'),
        } for row in s.scalars(select(ManagedDevice).where(ManagedDevice.tenant_id == u.tenant_id).order_by(ManagedDevice.created, ManagedDevice.id))]
        return redact_sensitive_keys(rows)

    @app.get('/v1/owner/topology')
    def topology(u=Depends(current), s=Depends(db)):
        owner(u)
        sites = list(s.scalars(select(Site).where(Site.tenant_id == u.tenant_id).order_by(Site.created, Site.id)))
        routers = list(s.scalars(select(RouterDevice).where(RouterDevice.tenant_id == u.tenant_id).order_by(RouterDevice.created, RouterDevice.id)))
        devices = list(s.scalars(select(ManagedDevice).where(ManagedDevice.tenant_id == u.tenant_id).order_by(ManagedDevice.created, ManagedDevice.id)))
        result = {'sites': []}
        for site in sites:
            result['sites'].append({
                'id': site.id,
                'name': site.name,
                'routers': [{'id': row.id, 'name': row.name, 'model': row.model} for row in routers if row.site_id == site.id],
                'devices': [{'id': row.id, 'name': row.name, 'kind': row.kind, 'vendor': row.vendor, 'model': row.model} for row in devices if row.site_id == site.id],
            })
        return redact_sensitive_keys(result)

    @app.get('/v1/owner/syslog')
    def syslog(u=Depends(current)):
        owner(u)
        return _coming_soon('router_syslog') | {'lines': []}

    @app.post('/v1/owner/syslog/explain')
    def explain_syslog(body: ExplainLineIn, u=Depends(current)):
        owner(u)
        return _coming_soon('syslog_explanation') | {'line': body.line}

    @app.get('/v1/owner/deployments')
    def deployments(u=Depends(current), s=Depends(db)):
        owner(u)
        rows = s.scalars(select(RouterChange).where(RouterChange.tenant_id == u.tenant_id).order_by(RouterChange.created.desc()).limit(100))
        return redact_sensitive_keys([{
            'id': row.id,
            'router_id': row.router_id,
            'operation': row.operation,
            'status': row.status,
            'risk': row.risk,
            'backup_verified': row.safety_backup_verified,
            'rollback_attempted': row.rollback_attempted,
            'created': row.created,
            'updated': row.updated,
        } for row in rows])

    @app.get('/v1/owner/services/plan')
    def services_plan(u=Depends(current), s=Depends(db)):
        owner(u)
        row = s.get(TenantSubscription, u.tenant_id)
        if not row:
            return _coming_soon('subscription_plan')
        return redact_sensitive_keys({
            'state': row.state,
            'period_start': row.period_start,
            'period_end': row.period_end,
            'plan': row.plan_snapshot,
        })

    @app.post('/v1/owner/services/upgrade')
    def upgrade_service(body: UpgradeIn, u=Depends(current)):
        _platform_admin(u)
        return _coming_soon('platform_plan_upgrade') | {'tenant_id': body.tenant_id, 'plan': body.plan}

    @app.get('/v1/owner/readiness')
    def readiness(u=Depends(current), s=Depends(db)):
        owner(u)
        now = int(time.time())
        routers = list(s.scalars(select(RouterDevice).where(RouterDevice.tenant_id == u.tenant_id).order_by(RouterDevice.created, RouterDevice.id)))
        plans = {row.router_id: row for row in s.scalars(select(RouterPlan).where(RouterPlan.tenant_id == u.tenant_id))}
        items = []
        for router in routers:
            plan = plans.get(router.id)
            connected = bool(plan and connection_is_fresh(plan, now))
            items.append({
                'router_id': router.id,
                'router_name': router.name,
                'hub': bool(plan and plan.handshake_verified_at and now - plan.handshake_verified_at < 180),
                'management': bool(plan and plan.management_read_verified_at and now - plan.management_read_verified_at < 180),
                'connected': connected,
                'fix_path': None if connected else f'/app/routers?router={router.id}',
            })
        return {'items': items, 'ready': bool(items) and all(item['connected'] for item in items)}

    @app.get('/v1/owner/connectors')
    def connectors(u=Depends(current)):
        owner(u)
        return _coming_soon('on_site_connectors') | {'connectors': []}

    @app.get('/v1/agent/coins')
    def agent_coins(u=Depends(current), s=Depends(db)):
        if u.role != 'agent':
            raise HTTPException(403, 'Agent permission required')
        rows = list(s.scalars(select(AgentCommission).where(AgentCommission.agent_id == u.id).order_by(AgentCommission.created.desc())))
        balances = {}
        for row in rows:
            balances.setdefault(row.currency, 0)
            if row.state == 'earned':
                balances[row.currency] += row.amount
        return {'balances': balances, 'ledger': [{
            'id': row.id,
            'amount': row.amount,
            'currency': row.currency,
            'state': row.state,
            'created': row.created,
            'reversed_at': row.reversed_at,
        } for row in rows]}

    @app.get('/v1/owner/tenants')
    def owner_tenants(u=Depends(current), s=Depends(db)):
        _platform_admin(u)
        return [{'id': row.id, 'name': row.name} for row in s.scalars(select(Tenant).order_by(Tenant.name, Tenant.id))]

    @app.post('/v1/owner/tenants/{tenant_id}/delete')
    def delete_tenant(tenant_id: str, body: ConfirmDeleteIn, u=Depends(current), s=Depends(db)):
        _platform_admin(u)
        if not body.confirm:
            raise HTTPException(422, 'Explicit tenant deletion confirmation is required')
        if not s.get(Tenant, tenant_id):
            raise HTTPException(404, 'Tenant not found')
        return _coming_soon('tenant_deletion') | {'tenant_id': tenant_id}

    @app.get('/v1/owner/test-lab')
    def test_lab(u=Depends(current)):
        _platform_admin(u)
        return _coming_soon('test_lab') | {'routers': []}

    @app.post('/v1/owner/test-lab')
    def test_lab_router(body: TestLabIn, u=Depends(current), s=Depends(db)):
        _platform_admin(u)
        router = s.get(RouterDevice, body.router_id)
        if not router:
            raise HTTPException(404, 'Router not found')
        raise HTTPException(409, 'Router is not explicitly marked as a test router')

    @app.post('/v1/owner/terminal')
    def terminal(body: TerminalCommandIn, u=Depends(current), s=Depends(db)):
        owner(u)
        _visible_router(s, u, body.router_id)
        blocked = bool(_TERMINAL_BLOCK.search(body.command))
        _audit(s, u, 'owner_terminal_blocked' if blocked else 'owner_terminal_requested', body.router_id)
        if blocked:
            raise HTTPException(422, 'This command is blocked by MikroMagic safety policy')
        return _coming_soon('owner_terminal_executor') | {'router_id': body.router_id, 'audited': True}

    @app.post('/v1/owner/scripts/run')
    def run_script(body: ScriptProposalIn, u=Depends(current), s=Depends(db)):
        owner(u)
        _visible_router(s, u, body.router_id)
        _audit(s, u, 'safe_change_script_proposal_requested', body.router_id)
        return _coming_soon('safe_change_script_proposal') | {'router_id': body.router_id, 'script_id': body.script_id}

    @app.post('/v1/owner/magic-dude/explain')
    def magic_dude_explain(body: AdvisorIn, u=Depends(current)):
        owner(u)
        return _coming_soon('advisor_explanation') | {'question': body.question}

    @app.post('/v1/owner/magic-dude/propose')
    def magic_dude_propose(body: AdvisorProposalIn, u=Depends(current), s=Depends(db)):
        owner(u)
        _visible_router(s, u, body.router_id)
        _audit(s, u, 'advisor_safe_change_proposal_requested', body.router_id)
        return _coming_soon('advisor_safe_change_proposal') | {'router_id': body.router_id, 'requires_owner_confirmation': True}
