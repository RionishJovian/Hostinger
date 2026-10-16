"""Pure, advisory recovery decisions with no execution side effects."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RecoveryState:
    state: str
    attempts: int = 0
    max_attempts: int = 3
    reprobe_state: str | None = None
    safe_change_status: str | None = None
    rollback_available: bool = False
    rollback_verified: bool = False


@dataclass(frozen=True)
class RecoveryRecommendation:
    action: str
    reason: str
    automatic: bool = False


_STATES = {"up", "stale", "offline", "drift", "failed", "recovery_required", "unknown"}
_CHANGE_STATES = {None, "previewed", "applying", "verifying", "applied", "failed", "rolled_back", "recovery_required", "conflict"}


def recommend_recovery(state: RecoveryState) -> RecoveryRecommendation:
    if not isinstance(state, RecoveryState):
        raise TypeError("state must be RecoveryState")
    if state.state not in _STATES or state.reprobe_state not in _STATES | {None}:
        raise ValueError("unsupported recovery state")
    if state.safe_change_status not in _CHANGE_STATES:
        raise ValueError("unsupported Safe Change state")
    if not isinstance(state.attempts, int) or isinstance(state.attempts, bool) or state.attempts < 0:
        raise ValueError("attempts must be a non-negative integer")
    if not isinstance(state.max_attempts, int) or isinstance(state.max_attempts, bool) or state.max_attempts < 1:
        raise ValueError("max_attempts must be a positive integer")
    if state.reprobe_state == "up" or state.state == "up":
        return RecoveryRecommendation("no_action", "peer is reachable")
    if state.safe_change_status == "rolled_back" and state.rollback_verified:
        return RecoveryRecommendation("no_action", "Safe Change rollback is already verified")
    if state.safe_change_status in {"recovery_required", "failed", "conflict"}:
        if state.rollback_available and not state.rollback_verified:
            return RecoveryRecommendation("propose_safe_change_rollback", "failed or conflicting change has a reviewed rollback candidate")
        return RecoveryRecommendation("alert_owner", "Safe Change cannot be recovered from verified state")
    if state.attempts >= state.max_attempts:
        return RecoveryRecommendation("alert_owner", "recovery backoff limit reached")
    if state.reprobe_state in {"offline", "drift", "failed", "recovery_required"}:
        if state.rollback_available:
            return RecoveryRecommendation("propose_safe_change_rollback", "reprobe did not recover the peer and a rollback candidate exists")
        return RecoveryRecommendation("alert_owner", "reprobe failed and no verified rollback candidate exists")
    return RecoveryRecommendation("reprobe", "fresh evaluation may clear a transient stale or offline state")


def recommend_recovery_action(state: RecoveryState) -> str:
    return recommend_recovery(state).action
