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
            _stage('site_details', 'Shop details', True,
                   f'{site.name} · {site.timezone}'),
            _stage('router_registered', 'Add your MikroTik', bool(router),
                   (f'{router.name}' + (f' · {router.model}' if router.model else '')).strip(' ·') if router else
                   ('Choose which router this shop uses.' if routers else 'Add a MikroTik router for this shop.')),
            _stage('connection_verified', 'Connect the router to MikroMagic', connected,
                   'This router is connected and ready for remote checks.' if connected else
                   'Connect the router with Magic Hub so MikroMagic can manage it remotely. This needs a real router online.',
                   blocked=not router),
            _stage('preflight_verified', 'Check what the router can do', preflight_verified,
                   'MikroMagic read the live router and checked that guest Wi-Fi setup is safe to continue.' if preflight_verified else
                   'After the router is connected, run a quick check so MikroMagic can see the real model and guest Wi-Fi setup. Typing the model yourself is not enough.',
                   blocked=not connected),
            _stage('portal_published', 'Save guest Wi-Fi page in MikroMagic', portal_prepared,
                   f'Guest Wi-Fi page revision {portal.published_revision} is saved in MikroMagic and ready for the router.' if portal_prepared else
                   'On Guest Wi-Fi page, finish and save the login page design for this shop. This stores it in MikroMagic — it does not change the router yet.'),
            _stage('hotspot_change_prepared', 'Choose guest Wi-Fi for the page', hotspot_plan_prepared,
                   'The guest Wi-Fi target on the router is chosen and ready for your review.' if hotspot_plan_prepared else
                   'After the router check, choose which guest Wi-Fi HotSpot should show your login page.',
                   blocked=not (preflight_verified and portal_prepared)),
            _stage('owner_review', 'Review before sending to the router', owner_reviewed,
                   'You confirmed what will change on the router, including backup and undo.' if owner_reviewed else
                   'Review the planned guest-page change, backup, and undo steps before MikroMagic touches the router.', blocked=not hotspot_plan_prepared),
            _stage('router_apply_verified', 'Send guest page to the router', router_apply_verified,
                   ('The guest Wi-Fi page was sent to the router with backup and verify. A real phone test is still required before the shop is ready.'
                    if router_apply_verified else
                    'Send the saved guest Wi-Fi page to the router safely: backup first, install, switch the guest page, verify, and undo if needed.'),
                   blocked=not owner_reviewed),
            _stage('temporary_test_voucher', 'Create a test voucher', test_voucher_issued,
                   'Available after the guest page works on the real router. Test vouchers are not counted as normal sales.', blocked=True),
            _stage('first_customer_test', 'Test with a real phone', customer_test_verified,
                   'Join the shop Wi-Fi on a real phone, open the guest page, use a voucher, and confirm internet works.', blocked=True),
            _stage('site_ready', 'Shop ready', site_ready,
                   'Opens only after the router is connected, the guest page is on the router, and a real phone test succeeds.', blocked=True),
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
