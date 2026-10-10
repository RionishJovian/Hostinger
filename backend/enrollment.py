"""Enrollment binding and sanitized state; no RouterOS or host operations."""
import hashlib
import json
import time
from .models import MagicConnectAttempt, MagicConnectEnrollment


def router_identity_digest(identity):
    """Compare an independently reviewed identity, never infer it from username.

    This is an identity consistency check, not device attestation. Missing stable
    hardware identity fails closed (including unsupported virtual devices).
    """
    values = [identity.get(k) for k in ('serial_number', 'model', 'architecture-name')]
    if not all(isinstance(v, str) and v.strip() for v in values):
        return None
    return hashlib.sha256(('mikromagic-router-identity-v1:' + json.dumps(
        [v.strip() for v in values], separators=(',', ':'), ensure_ascii=False
    )).encode()).hexdigest()


def sync_enrollment_state(session, plan, now=None):
    enrollment = session.get(MagicConnectEnrollment, plan.id)
    if enrollment:
        attempt = session.get(MagicConnectAttempt, enrollment.attempt_id)
        if attempt:
            attempt.enrollment_state = ('awaiting_bootstrap' if plan.lifecycle_state == 'provisioning_peer' else plan.lifecycle_state)
            attempt.failure_code = plan.last_failure_code
            attempt.state_changed_at = int(time.time() if now is None else now)


def enrollment_milestones(session, plan):
    enrollment = session.get(MagicConnectEnrollment, plan.id)
    return {
        'pairing_bound': enrollment is not None,
        'peer_provisioned': bool(enrollment and enrollment.peer_provisioned_at),
        'peer_provisioned_at': enrollment.peer_provisioned_at if enrollment else None,
        'router_identity_bound': bool(enrollment and enrollment.expected_identity_digest),
    }
