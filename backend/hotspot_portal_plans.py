"""RouterOS HotSpot portal plans for guided Safe Change publish.

These endpoints turn trusted read-only inventory and a published local content
package into an exact, reviewable intent. Preparing or reviewing a plan does
not upload files or change a profile; Publish to MikroTik uses Safe Change.
"""
import hashlib
import json
import re
import time

from fastapi import Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from .models import HotspotPortalPlan, LocalPortalPackage, RouterDevice, RouterEvidence, RouterPlan, SitePortal, StaffGrant
from .schemas import HotspotPortalProposalIn, HotspotPortalReviewIn

MAX_EVIDENCE_AGE_SECONDS = 15 * 60


def _json(plan):
    return {key: getattr(plan, key) for key in [
        'id', 'site_id', 'router_id', 'evidence_id', 'portal_package_id',
        'selected_server_id', 'selected_server_name', 'selected_profile_name',
        'status', 'revision', 'before', 'desired', 'diff', 'impact', 'rollback',
        'created', 'reviewed_at',
    ]} | {
        'risk': 'high',
        'proposal_only': True,
        'commands_generated': False,
        'router_contacted': False,
        'configuration_modified': False,
        'requires_verified_backup_before_apply': True,
    }


def _owner(u, s):
    if u.role != 'sme' or s.get(StaffGrant, u.id):
        raise HTTPException(403, 'Only the business Owner/Admin can prepare or review this change')


def _router(s, u, router_id):
    router = s.get(RouterDevice, router_id)
    if not router or router.tenant_id != u.tenant_id:
        raise HTTPException(404, 'Router not found')
    return router


def register_hotspot_portal_plans(app, current, db, log):
    @app.get('/v1/routers/{router_id}/hotspot-portal-plans')
    def list_plans(router_id: str, u=Depends(current), s=Depends(db)):
        _owner(u, s); _router(s, u, router_id)
        rows = s.scalars(select(HotspotPortalPlan).where(
            HotspotPortalPlan.tenant_id == u.tenant_id,
            HotspotPortalPlan.router_id == router_id,
        ).order_by(HotspotPortalPlan.created.desc()))
        return [_json(row) for row in rows]

    @app.post('/v1/routers/{router_id}/hotspot-portal-plans', status_code=201)
    def prepare(router_id: str, body: HotspotPortalProposalIn, u=Depends(current), s=Depends(db)):
        _owner(u, s); router = _router(s, u, router_id); now = int(time.time())
        connection = s.scalar(select(RouterPlan).where(
            RouterPlan.tenant_id == u.tenant_id,
            RouterPlan.router_id == router.id,
        ))
        if not connection or connection.lifecycle_state != 'connected' or not connection.management_read_verified_at or connection.management_locked_at:
            raise HTTPException(409, 'A verified Magic Connect management path is required before preparing a HotSpot change')
        evidence = s.get(RouterEvidence, body.evidence_id)
        if not evidence or evidence.tenant_id != u.tenant_id or evidence.router_id != router.id or evidence.kind != 'preflight':
            raise HTTPException(404, 'Pre-flight evidence not found')
        if evidence.observed_at < connection.management_read_verified_at or evidence.observed_at > now + 30 or now - evidence.observed_at > MAX_EVIDENCE_AGE_SECONDS:
            raise HTTPException(409, 'Use a fresh post-connection pre-flight before preparing this change')
        payload = evidence.payload if isinstance(evidence.payload, dict) else {}
        compatibility = payload.get('compatibility') if isinstance(payload.get('compatibility'), dict) else {}
        management = payload.get('management_read') if isinstance(payload.get('management_read'), dict) else {}
        if payload.get('preflight_stage') != 'post_connection' or compatibility.get('status') != 'compatible_for_safe_change' or management.get('authenticated') is not True or management.get('identity_verified') is not True:
            raise HTTPException(409, 'Compatible identity-bound RouterOS evidence is required')
        inventory = payload.get('hotspot_portal_inventory') if isinstance(payload.get('hotspot_portal_inventory'), dict) else {}
        if inventory.get('write_operations_enabled') is not False:
            raise HTTPException(409, 'HotSpot inventory evidence is incomplete')
        server = next((item for item in inventory.get('servers', []) if isinstance(item, dict) and item.get('.id') == body.server_id), None)
        if not server:
            raise HTTPException(409, 'Select a HotSpot server present in the trusted pre-flight')
        profile_name = server.get('profile')
        profile = next((item for item in inventory.get('profiles', []) if isinstance(item, dict) and item.get('name') == profile_name), None)
        if not profile or not isinstance(profile_name, str) or not profile_name:
            raise HTTPException(409, 'The selected HotSpot profile was not fully observed')
        login_by = {part.strip().lower() for part in str(profile.get('login-by', '')).split(',') if part.strip()}
        if 'http-chap' not in login_by or 'http-pap' in login_by:
            raise HTTPException(409, 'The selected profile must already support HTTP-CHAP without HTTP-PAP')
        portal = s.get(SitePortal, router.site_id)
        if not portal or not portal.published_revision:
            raise HTTPException(409, 'Publish this site portal before preparing a router change')
        package = s.scalar(select(LocalPortalPackage).where(
            LocalPortalPackage.tenant_id == u.tenant_id,
            LocalPortalPackage.site_id == router.site_id,
            LocalPortalPackage.published_revision == portal.published_revision,
        ))
        if not package:
            raise HTTPException(409, 'The published portal does not have a deterministic local package')
        flash = (inventory.get('storage') or {}).get('flash_directory_present') is True
        destination = ('flash/' if flash else '') + f'mm-b21-{router.site_id[:8]}-r{portal.published_revision}'
        old_directory = profile.get('html-directory-override') or profile.get('html-override-directory') or profile.get('html-directory') or 'hotspot'
        before = {
            'server_id': body.server_id, 'server_name': server.get('name'), 'interface': server.get('interface'),
            'profile': profile_name, 'profile_server_count': int(profile.get('server_count') or 0),
            'html_directory': old_directory, 'login_by': sorted(login_by),
            'evidence_id': evidence.id, 'observed_at': evidence.observed_at,
        }
        desired = {
            'content_package_id': package.id, 'content_sha256': package.package_sha256,
            'published_revision': package.published_revision, 'new_unique_directory': destination,
            'selected_profile': profile_name, 'authentication_unchanged': True,
            'voucher_backend_unchanged': True, 'command_generation': 'safe_change',
            'safe_change_operation': 'hotspot_portal_publish',
        }
        fingerprint = hashlib.sha256(json.dumps({'before': before, 'desired': desired}, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
        diff = {
            'content': {'before': 'existing files remain untouched', 'after': f'create-only package in {destination}'},
            'profile_html_directory': {'before': old_directory, 'after': destination},
            'fingerprint': fingerprint,
        }
        shared_count = int(profile.get('server_count') or 0)
        impact = {
            'level': 'high', 'selected_server_only': shared_count <= 1,
            'shared_profile_server_count': shared_count,
            'warning': 'Changing this profile affects every HotSpot server that shares it.' if shared_count > 1 else 'The observed profile is used by only the selected HotSpot server.',
            'pre_apply_checks': [
                'Reread the selected server/profile and reject any fingerprint drift.',
                'Prove the destination directory does not already exist; never overwrite files.',
                'Capture and verify an encrypted RouterOS export before any write.',
                'Verify storage persistence and sufficient space on the actual device.',
            ],
            'excluded': ['HotSpot users and vouchers', 'RADIUS', 'firewall', 'DHCP and DNS', 'Wi-Fi', 'WireGuard and other VPNs', 'unrelated files and profiles'],
        }
        rollback = {
            'sequence': ['restore only the selected profile directory value', 'verify guest serving', 'remove only the newly created directory after ownership and profile detachment are verified'],
            'automatic': False, 'full_device_restore': False,
        }
        existing = s.scalar(select(HotspotPortalPlan).where(
            HotspotPortalPlan.router_id == router.id,
            HotspotPortalPlan.portal_package_id == package.id,
            HotspotPortalPlan.selected_server_id == body.server_id,
        ))
        if existing:
            if existing.before != before or existing.desired != desired:
                raise HTTPException(409, 'The same package/server plan exists with different evidence; publish a new revision or review the existing plan')
            return _json(existing)
        plan = HotspotPortalPlan(
            tenant_id=u.tenant_id, site_id=router.site_id, router_id=router.id,
            evidence_id=evidence.id, portal_package_id=package.id,
            selected_server_id=body.server_id, selected_server_name=str(server.get('name') or body.server_id),
            selected_profile_name=profile_name, before=before, desired=desired, diff=diff,
            impact=impact, rollback=rollback, created_by=u.id, created=now,
        )
        s.add(plan)
        try:
            s.flush(); log(s, u, 'hotspot_portal_plan_prepared', plan.id); s.commit()
        except IntegrityError:
            s.rollback(); raise HTTPException(409, 'A proposal for this package and HotSpot server already exists')
        return _json(plan)

    @app.post('/v1/hotspot-portal-plans/{plan_id}/review')
    def review(plan_id: str, body: HotspotPortalReviewIn, u=Depends(current), s=Depends(db)):
        _owner(u, s); plan = s.get(HotspotPortalPlan, plan_id)
        if not plan or plan.tenant_id != u.tenant_id:
            raise HTTPException(404, 'HotSpot portal plan not found')
        if plan.status == 'reviewed' and body.expected_revision == plan.revision - 1:
            return _json(plan)
        if plan.status != 'prepared' or plan.revision != body.expected_revision:
            raise HTTPException(409, 'Plan changed or was already reviewed; refresh before confirming')
        plan.status = 'reviewed'; plan.reviewed_at = int(time.time()); plan.revision += 1
        log(s, u, 'hotspot_portal_plan_reviewed', plan.id); s.commit()
        return _json(plan)
