"""Read-only coordinator for the frozen-v1 first-site acceptance journey.

This module deliberately derives progress only from durable evidence that
already exists.  It cannot create RouterOS evidence, install a portal, issue a
test voucher, accept an owner's phone result, or mark a site ready.
"""
from fastapi import Depends, HTTPException, Query
from sqlalchemy import select

from .models import (
    LocalPortalPackage,
    HotspotPortalPlan,
    RouterChange,
    RouterDevice,
    RouterEvidence,
    RouterPlan,
    SitePortal,
    StaffGrant,
)
from .hotspot_portal_publish import latest_applied_for_package
from .sites import allowed_site


def _stage(key, label, complete, detail, *, blocked=False):
    return {
        "key": key,
        "label": label,
        "status": "complete" if complete else ("blocked" if blocked else "pending"),
        "detail": detail,
        "evidence_verified": bool(complete),
    }


def register_first_site_acceptance(app, current, db):
    @app.get('/v1/sites/{id}/first-site-acceptance')
    def first_site_acceptance(
        id: str,
        router_id: str | None = Query(default=None, max_length=36),
        u=Depends(current),
        s=Depends(db),
    ):
        if u.role != 'sme' or s.get(StaffGrant, u.id):
            raise HTTPException(403, 'Only the business Owner/Admin can review site acceptance')
        site = allowed_site(s, u, id)
        routers = list(s.scalars(select(RouterDevice).where(
            RouterDevice.tenant_id == u.tenant_id,
            RouterDevice.site_id == site.id,
        ).order_by(RouterDevice.created, RouterDevice.id)))
        router = None
        if router_id:
            router = next((item for item in routers if item.id == router_id), None)
            if not router:
                raise HTTPException(404, 'Router not found at this site')
        elif len(routers) == 1:
            router = routers[0]

        plan = None
        preflight = None
        if router:
            plan = s.scalar(select(RouterPlan).where(
                RouterPlan.tenant_id == u.tenant_id,
                RouterPlan.router_id == router.id,
            ))
            preflight = s.scalar(select(RouterEvidence).where(
                RouterEvidence.tenant_id == u.tenant_id,
                RouterEvidence.router_id == router.id,
                RouterEvidence.kind == 'preflight',
            ).order_by(RouterEvidence.observed_at.desc(), RouterEvidence.created.desc()))

        connected = bool(
            plan and plan.lifecycle_state == 'connected' and
            plan.handshake_verified_at and plan.management_read_verified_at and
            plan.management_read_verified_at >= plan.handshake_verified_at and
            not plan.management_locked_at
        )
        payload = preflight.payload if preflight and isinstance(preflight.payload, dict) else {}
        management = payload.get('management_read') if isinstance(payload.get('management_read'), dict) else {}
        compatibility = payload.get('compatibility') if isinstance(payload.get('compatibility'), dict) else {}
        preflight_verified = bool(
            connected and preflight and management.get('authenticated') is True and
            management.get('identity_verified') is True and
            compatibility.get('status') == 'compatible_for_safe_change' and
            preflight.observed_at >= plan.management_read_verified_at
        )

        portal = s.get(SitePortal, site.id)
        package = None
        if portal and portal.published_revision:
            package = s.scalar(select(LocalPortalPackage).where(
                LocalPortalPackage.tenant_id == u.tenant_id,
                LocalPortalPackage.site_id == site.id,
                LocalPortalPackage.published_revision == portal.published_revision,
            ))
        portal_prepared = bool(portal and portal.published_revision and package)

        hotspot_plan = None
        if router and package:
            hotspot_plan = s.scalar(select(HotspotPortalPlan).where(
                HotspotPortalPlan.tenant_id == u.tenant_id,
                HotspotPortalPlan.router_id == router.id,
                HotspotPortalPlan.portal_package_id == package.id,
            ).order_by(HotspotPortalPlan.created.desc()))

        # First Customer Test and Site Ready stay false until real-router evidence
        # exists. Simulated Safe Change apply can complete router_apply_verified
        # for software progress only; it is not hardware acceptance.
        hotspot_plan_prepared = bool(hotspot_plan)
        owner_reviewed = bool(hotspot_plan and hotspot_plan.status == 'reviewed')
        applied = latest_applied_for_package(s, u.tenant_id, router.id, package.id) if router and package else None
        router_apply_verified = bool(applied and owner_reviewed)
        test_voucher_issued = False
        customer_test_verified = False
        site_ready = False
        portal_change = None
        if router and owner_reviewed:
            portal_change = s.scalar(select(RouterChange).where(
                RouterChange.tenant_id == u.tenant_id,
                RouterChange.router_id == router.id,
                RouterChange.operation == 'hotspot_portal_publish',
            ).order_by(RouterChange.created.desc(), RouterChange.id.desc()))

        stages = [
            _stage('site_details', 'Site details', True,
                   f'{site.name} · {site.timezone}'),
            _stage('router_registered', 'Add MikroTik', bool(router),
                   f'{router.name} · owner-reported {router.model}' if router else
                   ('Choose one of the registered routers.' if routers else 'Register a MikroTik for this site.')),
            _stage('connection_verified', 'Verify Magic Connect', connected,
                   'Fresh Hub handshake followed by an authenticated identity-bound management read.' if connected else
                   'Connected requires a real Hub handshake and a newer authenticated RouterOS management read.',
                   blocked=not router),
            _stage('preflight_verified', 'Detect model, RouterOS and capabilities', preflight_verified,
                   'Compatible post-connection evidence from the dedicated Monitoring identity.' if preflight_verified else
                   'Run the read-only post-connection preflight; owner-reported model/version do not count.',
                   blocked=not connected),
            _stage('portal_published', 'Publish portal content to MikroMagic', portal_prepared,
                   f'Published revision {portal.published_revision} has a deterministic local content package.' if portal_prepared else
                   'Publish this site portal to prepare a reviewable local content package.'),
            _stage('hotspot_change_prepared', 'Prepare RouterOS HotSpot change', hotspot_plan_prepared,
                   'An exact content/profile diff is prepared for guided Safe Change publish.' if hotspot_plan_prepared else
                   'Select an observed HotSpot server to prepare an exact diff for Publish to MikroTik.',
                   blocked=not (preflight_verified and portal_prepared)),
            _stage('owner_review', 'Owner review and confirmation', owner_reviewed,
                   'The Owner/Admin confirmed the exact proposal scope before Safe Change backup and apply.' if owner_reviewed else
                   'Review shared-profile impact, exclusions, backup gate and rollback before confirming the proposal.', blocked=not hotspot_plan_prepared),
            _stage('router_apply_verified', 'Apply and verify on the router', router_apply_verified,
                   (f"Safe Change {applied.id} installed the local package and switched the selected profile; real-router acceptance is still pending."
                    if router_apply_verified else
                    'Publish to MikroTik through Safe Change: backup, create-only install, profile switch, verify and rollback.'),
                   blocked=not owner_reviewed),
            _stage('temporary_test_voucher', 'Create temporary test voucher', test_voucher_issued,
                   'Withheld until real-router portal and enforcement verification exists; it must be excluded from revenue and normal voucher statistics.', blocked=True),
            _stage('first_customer_test', 'First Customer Test', customer_test_verified,
                   'Requires a real phone through Wi-Fi, captive portal, voucher and internet plus router session/accounting evidence.', blocked=True),
            _stage('site_ready', 'Site Ready', site_ready,
                   'Fail closed until every earlier technical and owner-confirmation gate is verified on a real router.', blocked=True),
        ]
        return {
            'site': {'id': site.id, 'name': site.name, 'timezone': site.timezone},
            'routers': [{'id': item.id, 'name': item.name, 'model': item.model} for item in routers],
            'selected_router_id': router.id if router else None,
            'status': 'site_ready' if site_ready else 'not_ready',
            'site_ready': site_ready,
            'real_device_acceptance': 'not_yet_performed',
            'hotspot_proposal': _hotspot_summary(hotspot_plan, preflight, payload) if router else None,
            'portal_publish': ({
                'change_id': portal_change.id if portal_change else None,
                'status': portal_change.status if portal_change else None,
                'safety_backup_verified': portal_change.safety_backup_verified if portal_change else False,
                'applied': router_apply_verified,
            } if router else None),
            'stages': stages,
            'next_action': next((stage['detail'] for stage in stages if stage['status'] != 'complete'), 'Site ready'),
        }


def _hotspot_summary(plan, preflight, preflight_payload):
    inventory = preflight_payload.get('hotspot_portal_inventory') if isinstance(preflight_payload, dict) else None
    servers = inventory.get('servers', []) if isinstance(inventory, dict) else []
    return {
        'preflight_evidence_id': preflight.id if preflight else None,
        'plan': ({'id': plan.id, 'status': plan.status, 'revision': plan.revision,
                  'diff': plan.diff, 'impact': plan.impact, 'rollback': plan.rollback} if plan else None),
        'available_servers': [{key: item.get(key) for key in ['.id', 'name', 'interface', 'profile', 'profile_server_count']} for item in servers if isinstance(item, dict)],
    }
