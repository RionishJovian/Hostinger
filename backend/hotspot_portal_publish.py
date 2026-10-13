"""HotSpot portal package install helpers used by Safe Change.

Creates files only in a new unique directory and switches only the selected
HotSpot profile's html-directory. Real-router acceptance remains external.
"""
from __future__ import annotations

import hashlib
import json

from fastapi import HTTPException
from sqlalchemy import select

from .local_portal_package import FILES as PACKAGE_FILES, package_install_files
from .models import HotspotPortalPlan, LocalPortalPackage, RouterChange
from .routeros_adapter import (
    RouterOSError,
    hotspot_portal_publish_state,
    install_hotspot_portal_files,
    remove_hotspot_portal_files,
    set_hotspot_profile_html_directory,
)

# RouterOS REST refuses to create .json files; api.json only serves the optional RFC 8908 captive-portal API.
FILES = tuple(name for name in PACKAGE_FILES if not name.endswith('.json'))


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def load_reviewed_plan(s, tenant_id, router_id, plan_id):
    plan = s.get(HotspotPortalPlan, plan_id)
    if not plan or plan.tenant_id != tenant_id or plan.router_id != router_id:
        raise HTTPException(404, 'HotSpot portal plan not found')
    if plan.status != 'reviewed':
        raise HTTPException(409, 'Owner review of the exact HotSpot portal proposal is required first')
    package = s.get(LocalPortalPackage, plan.portal_package_id)
    if not package or package.tenant_id != tenant_id:
        raise HTTPException(409, 'The published local portal package is missing')
    desired = plan.desired if isinstance(plan.desired, dict) else {}
    if desired.get('content_sha256') != package.package_sha256 or desired.get('content_package_id') != package.id:
        raise HTTPException(409, 'The reviewed plan no longer matches the stored portal package')
    destination = desired.get('new_unique_directory')
    profile_name = plan.selected_profile_name
    if not isinstance(destination, str) or not isinstance(profile_name, str):
        raise HTTPException(409, 'The reviewed plan is missing the destination directory or profile')
    return plan, package, destination, profile_name


def _state(*, resource_id, profile_name, html_directory, destination, destination_present, installed_names,
           content_package_id, content_sha256, published_revision, plan_id):
    return {
        'resource_id': resource_id,
        'profile_name': profile_name,
        'html_directory': html_directory,
        'destination': destination,
        'destination_present': bool(destination_present),
        'installed_file_names': sorted(installed_names),
        'content_package_id': content_package_id,
        'content_sha256': content_sha256,
        'published_revision': published_revision,
        'hotspot_portal_plan_id': plan_id,
    }


def preview_state(client, plan, package, destination, profile_name):
    live = hotspot_portal_publish_state(client, profile_name=profile_name, destination=destination, expected_files=list(FILES))
    before_directory = (plan.before or {}).get('html_directory')
    if before_directory is not None and live['html_directory'] != before_directory:
        raise RouterOSError('stale_router_state', 'Live HotSpot profile directory differs from the reviewed proposal', 409)
    if live['destination_present']:
        raise RouterOSError('file_collision', 'Destination portal directory already exists; refusing to overwrite', 409)
    files = package_install_files(package.package_bytes)
    common = dict(
        resource_id=live['resource_id'], profile_name=profile_name, destination=destination,
        content_package_id=package.id, content_sha256=package.package_sha256,
        published_revision=package.published_revision, plan_id=plan.id,
    )
    before = _state(html_directory=live['html_directory'], destination_present=False, installed_names=[], **common)
    desired = _state(html_directory=destination, destination_present=True, installed_names=list(FILES), **common)
    diff = {
        'content': {'before': 'existing files remain untouched', 'after': f'create-only package in {destination}'},
        'profile_html_directory': {'before': live['html_directory'], 'after': destination},
        'impact': 'Guest captive-portal pages for HotSpot servers using this profile change; vouchers, RADIUS, firewall, DHCP, DNS, Wi-Fi and WireGuard stay out of scope.',
        'fingerprint': fingerprint({'before': before, 'desired': desired}),
        'hotspot_portal_plan_id': plan.id,
    }
    return before, desired, diff, files


def read_actual(client, expected):
    live = hotspot_portal_publish_state(
        client,
        profile_name=expected['profile_name'],
        destination=expected['destination'],
        expected_files=list(FILES),
    )
    names = sorted(item['name'] for item in live['installed_files'])
    complete = set(names) >= set(FILES)
    return _state(
        resource_id=live['resource_id'],
        profile_name=live['profile_name'],
        html_directory=live['html_directory'],
        destination=live['destination'],
        destination_present=complete,
        installed_names=names if complete else names,
        content_package_id=expected['content_package_id'],
        content_sha256=expected['content_sha256'],
        published_revision=expected['published_revision'],
        plan_id=expected['hotspot_portal_plan_id'],
    )


def apply_install(client, before, desired, files):
    install_hotspot_portal_files(client, desired['destination'], {name: files[name] for name in FILES})
    set_hotspot_profile_html_directory(client, before['resource_id'], desired['destination'])
    return read_actual(client, desired)


def rollback_portal(client, before, desired):
    set_hotspot_profile_html_directory(client, before['resource_id'], before['html_directory'])
    actual = read_actual(client, {**desired, 'html_directory': before['html_directory']})
    if actual['html_directory'] != before['html_directory']:
        raise RouterOSError('rollback_mismatch', 'HotSpot profile directory did not return to the rollback snapshot')
    if actual['destination_present'] or actual['installed_file_names']:
        remove_hotspot_portal_files(client, desired['destination'], list(FILES))
        actual = read_actual(client, before)
    if actual['destination_present'] or actual['installed_file_names']:
        raise RouterOSError('rollback_mismatch', 'Newly created portal directory remains after rollback')
    return _state(
        resource_id=before['resource_id'], profile_name=before['profile_name'],
        html_directory=before['html_directory'], destination=desired['destination'],
        destination_present=False, installed_names=[],
        content_package_id=before['content_package_id'], content_sha256=before['content_sha256'],
        published_revision=before['published_revision'], plan_id=before['hotspot_portal_plan_id'],
    )


def latest_applied_for_package(s, tenant_id, router_id, package_id):
    rows = s.scalars(select(RouterChange).where(
        RouterChange.tenant_id == tenant_id,
        RouterChange.router_id == router_id,
        RouterChange.operation == 'hotspot_portal_publish',
        RouterChange.status == 'applied',
    ).order_by(RouterChange.updated.desc(), RouterChange.id.desc()))
    for row in rows:
        desired = row.desired if isinstance(row.desired, dict) else {}
        if desired.get('content_package_id') == package_id:
            return row
    return None
