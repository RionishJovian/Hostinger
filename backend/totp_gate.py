"""Pure RFC 6238 replay protection and high-risk Safe Change gating."""
from __future__ import annotations

import base64
import binascii
import hmac
import re
import threading
import time
from dataclasses import dataclass
from typing import Iterable

from sqlalchemy import update

from .mfa import totp
from .models import AccountMFA


def decode_base32_secret(secret: str) -> str:
    if not isinstance(secret, str):
        raise ValueError("TOTP secret is required")
    clean = re.sub(r"[ -]", "", secret.strip()).upper()
    if not clean or not re.fullmatch(r"[A-Z2-7]+", clean):
        raise ValueError("invalid TOTP secret")
    padded = clean + "=" * ((8 - len(clean) % 8) % 8)
    try:
        raw = base64.b32decode(padded, casefold=False)
    except (binascii.Error, ValueError) as error:
        raise ValueError("invalid TOTP secret") from error
    if not raw:
        raise ValueError("invalid TOTP secret")
    return base64.b32encode(raw).decode()


class ReplayGuard:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._used: dict[str, set[int]] = {}

    def consume(self, subject: str, step: int, minimum_step: int | None = None) -> bool:
        if not isinstance(subject, str) or not subject:
            return False
        with self._lock:
            used = self._used.setdefault(subject, set())
            if step in used:
                return False
            used.add(step)
            if minimum_step is not None:
                self._used[subject] = {value for value in used if value >= minimum_step}
            return True


class DatabaseReplayGuard:
    """Persist consumed TOTP steps in the account MFA row.

    The update is conditional on the previous step, so concurrent workers
    cannot both consume the same step. The caller owns the surrounding
    transaction and commits it with the Safe Change gate decision.
    """

    def __init__(self, session) -> None:
        self.session = session

    def consume(self, subject: str, step: int, minimum_step: int | None = None) -> bool:
        if not isinstance(subject, str) or not subject or not isinstance(step, int):
            return False
        values = {'last_step': step}
        statement = update(AccountMFA).where(
            AccountMFA.user_id == subject,
            AccountMFA.enabled == True,
            AccountMFA.last_step < step,
        ).values(**values)
        return bool(self.session.execute(statement).rowcount)


def matching_totp_step(secret: str, code: str, now: float | None = None, window: int = 1, digits: int = 6, period: int = 30) -> int | None:
    normalized = decode_base32_secret(secret)
    if not isinstance(code, str) or not re.fullmatch(rf"[0-9]{{{digits}}}", code.strip()):
        return None
    if not isinstance(window, int) or isinstance(window, bool) or window < 0 or window > 10:
        raise ValueError("TOTP window must be 0-10")
    if digits < 6 or digits > 8 or period < 1:
        raise ValueError("unsupported TOTP parameters")
    counter = int(time.time() if now is None else now) // period
    matches = []
    for offset in range(-window, window + 1):
        step = counter + offset
        if step >= 0 and hmac.compare_digest(totp(normalized, step, digits), code.strip()):
            matches.append(step)
    return matches[-1] if matches else None


def verify_totp(secret: str, code: str, subject: str, replay_guard, now: float | None = None, window: int = 1, digits: int = 6, period: int = 30) -> bool:
    if not hasattr(replay_guard, 'consume'):
        raise TypeError("a replay guard is required")
    step = matching_totp_step(secret, code, now=now, window=window, digits=digits, period=period)
    if step is None:
        return False
    current = int(time.time() if now is None else now) // period
    return replay_guard.consume(subject, step, current - window)


@dataclass(frozen=True)
class GateResult:
    allowed: bool
    reason: str
    otp_required: bool


HIGH_RISK_ACTIONS = frozenset({"rotate_listen_port", "escalate", "reboot", "safe_change_apply"})


def requires_totp(actions: Iterable[str] = (), risk: str = "low") -> bool:
    return risk == "high" or any(action in HIGH_RISK_ACTIONS for action in actions)


def evaluate_safe_change_gate(*, approved: bool, has_changes: bool, risk: str, actions: Iterable[str] = (), secret: str | None = None, code: str = "", subject: str = "", replay_guard: ReplayGuard | None = None, now: float | None = None, window: int = 1) -> GateResult:
    if risk not in {"low", "medium", "high"}:
        return GateResult(False, "invalid_risk", False)
    required = requires_totp(actions, risk)
    if not has_changes:
        return GateResult(False, "no_changes", required)
    if not approved:
        return GateResult(False, "rejected", required)
    if not required:
        return GateResult(True, "approved", False)
    if not code:
        return GateResult(False, "otp_required", True)
    if not secret or not subject or replay_guard is None:
        return GateResult(False, "otp_unavailable", True)
    try:
        valid = verify_totp(secret, code, subject, replay_guard, now=now, window=window)
    except (TypeError, ValueError):
        valid = False
    return GateResult(valid, "approved" if valid else "otp_invalid", True)
