"""Auditable WireGuard peer lifecycle with explicit non-production gates.

Host peer writes remain disabled by default. The class accepts an adapter so
tests can exercise orchestration without invoking host WireGuard or a router.
"""
from __future__ import annotations

import hashlib
import hmac
import re
import time
from dataclasses import dataclass
from sqlalchemy import update

from .models import HubAssignment, MagicHub, RouterDevice, RouterPlan, MagicConnectAttempt, MagicConnectEnrollment, MagicConnectEvent, User
from .enrollment import sync_enrollment_state
from .wireguard_hub import HubWireGuardError, WireGuardHubAdapter


class HubOrchestrationError(RuntimeError):
    def __init__(self, code: str, status: int = 409):
        super().__init__(code)
        self.code = code
        self.status = status


@dataclass(frozen=True)
class HostOperationPolicy:
    environment: str = ""
    peer_writes_enabled: bool = False
    peer_reads_enabled: bool = False
    dedicated_interface: str | None = None
    deployment_mode: str = ""

    @property
    def can_write(self) -> bool:
        return self.peer_writes_enabled and (self.environment == "isolated-magic-connect-test" or (self.environment == "hostinger-public-test" and self.deployment_mode == "dedicated-agent"))

    @property
    def can_read(self) -> bool:
        return self.peer_reads_enabled and (self.environment == "isolated-magic-connect-test" or (self.environment == "hostinger-public-test" and self.deployment_mode == "dedicated-agent"))

    def allows_interface(self, interface_name: str | None) -> bool:
        """Pin host WireGuard operations to one explicitly dedicated interface."""
        return bool(
            self.dedicated_interface
            and re.fullmatch(r"[A-Za-z0-9_.-]{1,15}", self.dedicated_interface)
            and interface_name == self.dedicated_interface
        )

def connection_is_fresh(plan, now=None):
    now = int(time.time() if now is None else now)
    return bool(plan.lifecycle_state == 'connected' and
                plan.handshake_verified_at is not None and plan.management_read_verified_at is not None and
                0 <= now - plan.handshake_verified_at <= 180 and
                0 <= now - plan.management_read_verified_at <= 180)


def confirm_management_read(plan: RouterPlan, evidence: dict, *, tenant_id: str, router_id: str, now=None):
    now = int(time.time() if now is None else now)
    handshake = plan.handshake_verified_at
    valid = (
        plan.tenant_id == tenant_id and plan.router_id == router_id and
        plan.lifecycle_state == "verifying_management" and handshake is not None and 0 <= now - handshake <= 180 and
        evidence.get("evidence_source") == "authenticated_routeros_read" and
        evidence.get("authenticated") is True and evidence.get("identity_verified") is True and
        evidence.get("tenant_id") == tenant_id and evidence.get("router_id") == router_id and
        isinstance(evidence.get("observed_at"), int) and evidence["observed_at"] >= handshake and
        0 <= now - evidence["observed_at"] <= 180
    )
    if not valid:
        plan.lifecycle_state = "verifying_management" if handshake else "awaiting_handshake"
        return {"state": plan.lifecycle_state, "connection_verified": False, "management_read_verified": False}
    plan.management_read_verified_at = evidence["observed_at"]
    plan.lifecycle_state = "connected"
    return {"state": "connected", "connection_verified": True, "management_read_verified": True,
            "handshake_at": handshake, "management_read_at": evidence["observed_at"]}


class HubPeerOrchestrator:
    def __init__(self, adapter: WireGuardHubAdapter, policy: HostOperationPolicy, clock=time.time):
        self.adapter = adapter
        self.policy = policy
        self.clock = clock

    def _verify_hub(self, hub):
        try:
            self.adapter.verify_hub_identity(hub.interface_name, hub.public_key)
        except HubWireGuardError:
            raise HubOrchestrationError('assigned_hub_identity_unverified', 503)

    def readiness(self, hub):
        if not hub.interface_name or not self.policy.allows_interface(hub.interface_name):
            return {"operational_state":"unverified","peer_control_ready":False,"connection_verified":False}
        try:self._verify_hub(hub)
        except HubOrchestrationError:return {"operational_state":"unverified","peer_control_ready":False,"connection_verified":False}
        enabled=self.policy.can_read and self.policy.can_write
        return {"operational_state":"peer_control_ready" if enabled else "identity_verified","peer_control_ready":enabled,"connection_verified":False}

    @staticmethod
    def _serialize_plan(session, plan):
        # PostgreSQL row locking spans the actual host side effect and the
        # caller's final commit. Refresh defeats a stale ORM identity map.
        # SQLite remains a software fixture, not concurrency certification.
        if session.bind.dialect.name == 'postgresql':
            session.refresh(plan, with_for_update=True)

    @staticmethod
    def _scope(session, plan: RouterPlan, hub: MagicHub, tenant_id: str):
        if plan.tenant_id != tenant_id or not session.get(HubAssignment, (hub.id, tenant_id)):
            raise HubOrchestrationError("tenant_or_hub_assignment_mismatch", 404)
        router = session.get(RouterDevice, plan.router_id)
        if not router or router.tenant_id != tenant_id:
            raise HubOrchestrationError("router_tenant_mismatch", 404)
        if plan.hub_id != hub.id:
            raise HubOrchestrationError("plan_hub_mismatch", 409)
        if not hub.interface_name:
            raise HubOrchestrationError("dedicated_hub_interface_not_configured", 409)
        return router

    def provision(self, session, plan: RouterPlan, hub: MagicHub, tenant_id: str, *, confirmed: bool, idempotency_key: str):
        self._scope(session, plan, hub, tenant_id)
        self._serialize_plan(session, plan)
        if not confirmed or not plan.reviewed_at:
            raise HubOrchestrationError("owner_review_required", 403)
        if not idempotency_key or len(idempotency_key) > 80:
            raise HubOrchestrationError("valid_idempotency_key_required", 422)
        if plan.lifecycle_state in ("management_locked", "management_lock_pending", "revoked") or plan.management_lock_reason:
            raise HubOrchestrationError("management_peer_locked", 409)
        if plan.lifecycle_state == "failed_recovery_required":
            raise HubOrchestrationError("recovery_check_required_before_retry", 409)
        if plan.peer_operation_key:
            if not hmac.compare_digest(plan.peer_operation_key, idempotency_key):
                raise HubOrchestrationError("different_operation_already_recorded", 409)
            if plan.lifecycle_state == "provisioning_peer":
                raise HubOrchestrationError("same_peer_operation_in_progress", 409)
            if plan.lifecycle_state in ("awaiting_handshake", "verifying_management", "connected"):
                # The database survives a Hub restart, but an in-kernel peer
                # may not. A replay is not proof that the peer still exists.
                if not self.policy.can_read or not self.policy.allows_interface(hub.interface_name):
                    raise HubOrchestrationError("host_peer_readback_required_for_replay", 503)
                self._verify_hub(hub)
                try:
                    observed = self.adapter.observe_peer(
                        hub.interface_name, plan.router_public_key, plan.address + "/32", hub.pool
                    )
                except HubWireGuardError:
                    observed = None
                if not observed or not observed.get("peer_found") or not observed.get("allowed_address_match"):
                    plan.lifecycle_state = "failed_recovery_required"
                    plan.last_failure_code = ("hub_peer_readback_unavailable_on_replay" if observed is None
                                              else "hub_peer_missing_or_conflicting_on_replay")
                    plan.handshake_verified_at = None
                    plan.management_read_verified_at = None
                    sync_enrollment_state(session, plan, int(self.clock()))
                    raise HubOrchestrationError(plan.last_failure_code, 503)
                return {"state": plan.lifecycle_state, "replayed": True, "connection_verified": connection_is_fresh(plan, self.clock())}
            if plan.lifecycle_state != "awaiting_bootstrap":
                raise HubOrchestrationError("recovery_check_required_before_retry", 409)
        if not self.policy.can_write:
            raise HubOrchestrationError("host_peer_writes_disabled_pending_isolated_test_approval", 503)
        if not self.policy.allows_interface(hub.interface_name):
            raise HubOrchestrationError("host_peer_interface_not_allowlisted", 503)
        self._verify_hub(hub)
        enrollment = session.get(MagicConnectEnrollment, plan.id)
        attempt = session.get(MagicConnectAttempt, enrollment.attempt_id) if enrollment else None
        router = session.get(RouterDevice, plan.router_id)
        owner = session.get(User, enrollment.owner_id) if enrollment else None
        now = int(self.clock())
        if not enrollment or not attempt or not owner or not owner.active or owner.role != 'sme' or owner.tenant_id != tenant_id or enrollment.tenant_id != tenant_id or enrollment.site_id != router.site_id or attempt.site_id != router.site_id or attempt.tenant_id != tenant_id or attempt.owner_id != owner.id or attempt.status != 'approved' or not attempt.approved_at or attempt.expires <= now:
            raise HubOrchestrationError('valid_owner_approved_enrollment_required', 403)
        previous_key = plan.peer_operation_key
        authorization = session.execute(update(MagicConnectAttempt).where(
            MagicConnectAttempt.id == attempt.id, MagicConnectAttempt.status == 'approved',
            MagicConnectAttempt.expires > now, MagicConnectAttempt.owner_id == owner.id,
            MagicConnectAttempt.tenant_id == tenant_id, MagicConnectAttempt.site_id == router.site_id,
        ).values(state_changed_at=now).execution_options(synchronize_session=False)).rowcount
        if authorization != 1:
            raise HubOrchestrationError('valid_owner_approved_enrollment_required', 403)
        claimed = session.execute(update(RouterPlan).where(
            RouterPlan.id == plan.id,
            RouterPlan.tenant_id == tenant_id,
            RouterPlan.peer_operation_key == previous_key if previous_key else RouterPlan.peer_operation_key.is_(None),
            RouterPlan.lifecycle_state == "awaiting_bootstrap",
            RouterPlan.reviewed_at.is_not(None),
        ).values(lifecycle_state="provisioning_peer", peer_operation_key=idempotency_key).execution_options(synchronize_session=False)).rowcount
        if claimed != 1:
            session.refresh(plan)
            if plan.peer_operation_key and hmac.compare_digest(plan.peer_operation_key, idempotency_key) and plan.lifecycle_state in ("awaiting_handshake", "verifying_management", "connected"):
                return {"state": plan.lifecycle_state, "replayed": True, "connection_verified": connection_is_fresh(plan, self.clock())}
            raise HubOrchestrationError("peer_operation_claim_lost_or_plan_state_changed", 409)
        session.refresh(plan)
        enrollment.consumed_at = enrollment.consumed_at or now
        session.add(MagicConnectEvent(tenant_id=tenant_id, attempt_id=attempt.id, actor_kind='owner', actor_id=owner.id, event='peer_operation_claimed', created=now))
        sync_enrollment_state(session, plan, now)
        # Commit the single-use claim BEFORE the non-transactional host mutation.
        # An interrupted process must require readback, not silently repeat a write.
        session.commit()
        # The durable claim intentionally releases its transaction. Emergency
        # lock may win in that gap: reacquire and recheck before touching wg.
        self._serialize_plan(session, plan)
        if plan.management_lock_reason or plan.lifecycle_state != 'provisioning_peer':
            raise HubOrchestrationError('management_peer_locked_or_claim_changed', 409)
        try:
            result = self.adapter.provision_peer(
                hub.interface_name, plan.router_public_key, plan.address + "/32", hub.pool
            )
        except HubWireGuardError:
            plan.lifecycle_state = "failed_recovery_required"
            plan.last_failure_code = "hub_peer_provision_or_readback_failed"
            sync_enrollment_state(session, plan, now)
            session.flush()
            raise HubOrchestrationError(plan.last_failure_code, 503)
        plan.last_failure_code = None
        plan.lifecycle_state = "awaiting_handshake"
        enrollment.peer_provisioned_at = now
        sync_enrollment_state(session, plan, now)
        session.flush()
        return {"state": plan.lifecycle_state, "replayed": False, "peer_result": result["result"],
                "connection_verified": False, "management_read_verified": False}

    def recover(self, session, plan: RouterPlan, hub: MagicHub, tenant_id: str, *, confirmed: bool):
        self._scope(session, plan, hub, tenant_id)
        self._serialize_plan(session, plan)
        if not confirmed or plan.lifecycle_state not in ("failed_recovery_required", "provisioning_peer"):
            raise HubOrchestrationError("explicit_recovery_check_required", 409)
        if not self.policy.can_read:
            raise HubOrchestrationError("host_peer_reads_disabled_pending_isolated_test_approval", 503)
        if not self.policy.allows_interface(hub.interface_name):
            raise HubOrchestrationError("host_peer_interface_not_allowlisted", 503)
        self._verify_hub(hub)
        try:
            observed = self.adapter.observe_peer(hub.interface_name, plan.router_public_key, plan.address + "/32", hub.pool)
        except HubWireGuardError:
            raise HubOrchestrationError("recovery_peer_state_unavailable", 503)
        if plan.management_lock_reason:
            plan.lifecycle_state = 'management_lock_pending' if observed.get('peer_found') else 'management_locked'
            sync_enrollment_state(session, plan, int(self.clock()))
            return {'state':plan.lifecycle_state, 'recovery_readback':'lock_intent_preserved', 'retry_allowed':False}
        if observed.get("peer_found"):
            if not observed.get('allowed_address_match'):
                raise HubOrchestrationError("peer_state_conflict_inspect_before_retry", 409)
            plan.lifecycle_state = 'awaiting_handshake'
            plan.last_failure_code = None
            enrollment = session.get(MagicConnectEnrollment, plan.id)
            if enrollment: enrollment.peer_provisioned_at = int(self.clock())
            sync_enrollment_state(session, plan, int(self.clock()))
            return {'state': plan.lifecycle_state, 'recovery_readback': 'recorded_peer_present', 'retry_allowed': False}
        plan.lifecycle_state = "awaiting_bootstrap"
        plan.last_failure_code = None
        # Keep the consumed operation key: recovery cannot mint fresh authority.
        plan.handshake_verified_at = None
        plan.management_read_verified_at = None
        sync_enrollment_state(session, plan, int(self.clock()))
        enrollment = session.get(MagicConnectEnrollment,plan.id)
        attempt = session.get(MagicConnectAttempt,enrollment.attempt_id) if enrollment else None
        retry_allowed = bool(attempt and attempt.status=='approved' and attempt.expires>int(self.clock()))
        return {"state": plan.lifecycle_state, "recovery_readback": "peer_absent", "retry_allowed": retry_allowed}

    def observe(self, session, plan: RouterPlan, hub: MagicHub, tenant_id: str, *, recent_seconds=180):
        self._scope(session, plan, hub, tenant_id)
        self._serialize_plan(session, plan)
        if not self.policy.can_read:
            raise HubOrchestrationError("host_peer_reads_disabled_pending_isolated_test_approval", 503)
        if not self.policy.allows_interface(hub.interface_name):
            raise HubOrchestrationError("host_peer_interface_not_allowlisted", 503)
        self._verify_hub(hub)
        if plan.lifecycle_state not in ("awaiting_handshake", "verifying_management", "connected"):
            raise HubOrchestrationError("peer_not_in_handshake_phase", 409)
        try:
            evidence = self.adapter.observe_peer(hub.interface_name, plan.router_public_key, plan.address + "/32", hub.pool, recent_seconds)
        except HubWireGuardError:
            plan.lifecycle_state = "failed_recovery_required"
            plan.last_failure_code = "hub_peer_observation_failed"
            sync_enrollment_state(session, plan, int(self.clock()))
            raise HubOrchestrationError(plan.last_failure_code, 503)
        if not evidence["fresh_handshake"] or not evidence["allowed_address_match"]:
            plan.lifecycle_state = "awaiting_handshake"
            plan.handshake_verified_at = None
            plan.management_read_verified_at = None
            sync_enrollment_state(session, plan, int(self.clock()))
            return {"state": plan.lifecycle_state, "connection_verified": False, "evidence": evidence}
        plan.lifecycle_state = "verifying_management"
        plan.handshake_verified_at = evidence["last_handshake_at"]
        plan.management_read_verified_at = None
        sync_enrollment_state(session, plan, int(self.clock()))
        return {"state": plan.lifecycle_state, "connection_verified": False, "evidence": evidence}

    def confirm_management_read(self, plan: RouterPlan, evidence: dict, *, tenant_id: str, router_id: str):
        return confirm_management_read(plan, evidence, tenant_id=tenant_id, router_id=router_id,
                                       now=int(self.clock()))


    def emergency_lock(self, session, plan: RouterPlan, hub: MagicHub, tenant_id: str, *, actor_id: str,
                       reason: str, confirmed: bool):
        self._scope(session, plan, hub, tenant_id)
        self._serialize_plan(session, plan)
        if not confirmed or not reason.strip() or len(reason.strip()) > 500:
            raise HubOrchestrationError("explicit_lock_confirmation_and_reason_required", 422)
        if not self.policy.can_write:
            raise HubOrchestrationError("host_peer_writes_disabled_lock_not_applied", 503)
        if not self.policy.allows_interface(hub.interface_name):
            raise HubOrchestrationError("host_peer_interface_not_allowlisted", 503)
        self._verify_hub(hub)
        if plan.lifecycle_state in ("management_locked", "revoked"):
            return {"state": plan.lifecycle_state, "replayed": True}
        plan.lifecycle_state = "management_lock_pending"
        plan.management_lock_reason = reason.strip()
        plan.management_locked_at = int(self.clock())
        sync_enrollment_state(session, plan, int(self.clock()))
        session.commit()
        self._serialize_plan(session, plan)
        try:
            result = self.adapter.revoke_peer(hub.interface_name, plan.router_public_key, plan.address + "/32", hub.pool)
        except HubWireGuardError:
            plan.lifecycle_state = "failed_recovery_required"
            plan.last_failure_code = "hub_peer_revocation_or_readback_failed"
            sync_enrollment_state(session, plan, int(self.clock()))
            raise HubOrchestrationError(plan.last_failure_code, 503)
        plan.lifecycle_state = "management_locked"
        plan.management_lock_reason = reason.strip()
        plan.management_locked_at = int(self.clock())
        plan.management_read_verified_at = None
        sync_enrollment_state(session, plan, int(self.clock()))
        return {"state": plan.lifecycle_state, "replayed": False, "peer_result": result["result"],
                "on_router_cleanup_verified": False, "local_hotspot_affected": False, "actor_id": actor_id}

    @staticmethod
    def evidence_digest(payload: dict) -> str:
        """Stable digest for sanitized evidence; callers must not pass credentials."""
        import json
        return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
