import base64
import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from backend.hub_orchestrator import HubOrchestrationError, HubPeerOrchestrator, HostOperationPolicy
from backend.models import Base, Tenant, User, Site, RouterDevice, MagicHub, HubAssignment, RouterPlan, MagicConnectAttempt, MagicConnectEnrollment


def key(n):
    return base64.b64encode(bytes([n]) * 32).decode()


class FakeHubAdapter:
    def verify_hub_identity(self, interface, expected_public_key):
        return True
    def __init__(self):
        self.provisions = []
        self.revocations = []
        self.handshake = False
        self.fail_provision = False
        self.peer_present = False

    def provision_peer(self, interface, public_key, address, pool):
        self.provisions.append((interface, public_key, address, pool))
        if self.fail_provision:
            from backend.wireguard_hub import HubWireGuardError
            raise HubWireGuardError("simulated sanitized failure")
        self.peer_present = True
        return {"result": "provisioned", "peer_present": True, "allowed_address": address, "configuration_modified": True}

    def observe_peer(self, interface, public_key, address, pool, recent_seconds=180):
        return {"evidence_source": "fixture_only", "peer_found": self.peer_present,
                "allowed_address_match": self.peer_present,
                "fresh_handshake": self.handshake, "last_handshake_at": 1000 if self.handshake else None}

    def revoke_peer(self, interface, public_key, address, pool):
        self.revocations.append(public_key)
        self.peer_present = False
        return {"result": "revoked", "peer_present": False, "configuration_modified": True}


class HubOrchestratorTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.session = Session(self.engine, expire_on_commit=False)
        tenant = Tenant(id="tenant-a", name="Test SME")
        user = User(id="owner-a", username="owner-a", password_hash="test", role="sme", tenant_id=tenant.id, active=True)
        site = Site(id="site-a", tenant_id=tenant.id, name="Test site", timezone="Asia/Yangon", created=1)
        router = RouterDevice(id="router-a", tenant_id=tenant.id, site_id=site.id, name="Gateway", model="hAP test", reported_routeros="7.x", registered_by=user.id, created=1)
        hub = MagicHub(id="hub-a", name="Hub A", endpoint="hub.example.com", port=51820, pool="10.90.1.0/24", public_key=key(1), interface_name="wg-mm", next_host=3, created=1)
        plan = RouterPlan(id="plan-a", tenant_id=tenant.id, router_id=router.id, hub_id=hub.id, router_public_key=key(2), address="10.90.1.2", snapshot={}, created=1, reviewed_at=900, lifecycle_state="awaiting_bootstrap")
        self.session.add_all([tenant, user, site, router, hub, HubAssignment(hub_id=hub.id, tenant_id=tenant.id, created=1), plan])
        self.session.commit()
        attempt = MagicConnectAttempt(id='attempt-a', tenant_id=tenant.id, site_id=site.id, owner_id=user.id, router_name='Synthetic gateway', code_hash='a'*64, comparison_code='123456', status='approved', approved_at=900, created=1, expires=4102444800)
        enrollment = MagicConnectEnrollment(plan_id=plan.id, attempt_id=attempt.id, tenant_id=tenant.id, site_id=site.id, owner_id=user.id, created=900)
        self.session.add_all([attempt, enrollment]); self.session.commit()
        self.plan, self.hub = plan, hub
        self.adapter = FakeHubAdapter()

    def tearDown(self):
        self.session.close()
        self.engine.dispose()

    def test_host_write_default_is_disabled_and_does_not_call_adapter(self):
        service = HubPeerOrchestrator(self.adapter, HostOperationPolicy())
        with self.assertRaisesRegex(HubOrchestrationError, "host_peer_writes_disabled"):
            service.provision(self.session, self.plan, self.hub, "tenant-a", confirmed=True, idempotency_key="operation-12345")
        self.assertEqual(self.adapter.provisions, [])
        self.assertEqual(self.plan.lifecycle_state, "awaiting_bootstrap")

    def test_public_peer_control_requires_dedicated_agent_mode_and_never_claims_connection(self):
        disabled = HubPeerOrchestrator(self.adapter, HostOperationPolicy("hostinger-public-test", True, True, "wg-mm"))
        self.assertEqual(disabled.readiness(self.hub), {"operational_state":"identity_verified","peer_control_ready":False,"connection_verified":False})
        enabled = HubPeerOrchestrator(self.adapter, HostOperationPolicy("hostinger-public-test", True, True, "wg-mm", "dedicated-agent"))
        self.assertEqual(enabled.readiness(self.hub), {"operational_state":"peer_control_ready","peer_control_ready":True,"connection_verified":False})

    def test_provision_is_tenant_scoped_idempotent_and_waits_for_handshake(self):
        service = HubPeerOrchestrator(self.adapter, HostOperationPolicy("isolated-magic-connect-test", True, True, "wg-mm"))
        with self.assertRaisesRegex(HubOrchestrationError, "tenant_or_hub_assignment_mismatch"):
            service.provision(self.session, self.plan, self.hub, "tenant-b", confirmed=True, idempotency_key="operation-12345")
        first = service.provision(self.session, self.plan, self.hub, "tenant-a", confirmed=True, idempotency_key="operation-12345")
        self.assertEqual(first["state"], "awaiting_handshake")
        self.assertFalse(first["connection_verified"])
        second = service.provision(self.session, self.plan, self.hub, "tenant-a", confirmed=True, idempotency_key="operation-12345")
        self.assertTrue(second["replayed"])
        self.assertEqual(len(self.adapter.provisions), 1)
        with self.assertRaisesRegex(HubOrchestrationError, "different_operation_already_recorded"):
            service.provision(self.session, self.plan, self.hub, "tenant-a", confirmed=True, idempotency_key="operation-other-123")

    def test_replay_after_hub_peer_loss_requires_recovery_without_readding(self):
        service = HubPeerOrchestrator(self.adapter, HostOperationPolicy("isolated-magic-connect-test", True, True, "wg-mm"))
        service.provision(self.session, self.plan, self.hub, "tenant-a", confirmed=True, idempotency_key="operation-12345")
        self.adapter.peer_present = False  # Synthetic Hub restart loses kernel peer state.
        with self.assertRaisesRegex(HubOrchestrationError, "hub_peer_missing_or_conflicting_on_replay"):
            service.provision(self.session, self.plan, self.hub, "tenant-a", confirmed=True, idempotency_key="operation-12345")
        self.assertEqual(len(self.adapter.provisions), 1)
        self.assertEqual(self.plan.lifecycle_state, "failed_recovery_required")
        self.assertEqual(service.recover(self.session, self.plan, self.hub, "tenant-a", confirmed=True)["recovery_readback"], "peer_absent")

    def test_replay_cannot_claim_success_when_host_readback_is_disabled(self):
        service = HubPeerOrchestrator(self.adapter, HostOperationPolicy("isolated-magic-connect-test", True, True, "wg-mm"))
        service.provision(self.session, self.plan, self.hub, "tenant-a", confirmed=True, idempotency_key="operation-12345")
        no_read = HubPeerOrchestrator(self.adapter, HostOperationPolicy("isolated-magic-connect-test", True, False, "wg-mm"))
        with self.assertRaisesRegex(HubOrchestrationError, "host_peer_readback_required_for_replay"):
            no_read.provision(self.session, self.plan, self.hub, "tenant-a", confirmed=True, idempotency_key="operation-12345")
        self.assertEqual(len(self.adapter.provisions), 1)
        self.assertEqual(self.plan.lifecycle_state, "awaiting_handshake")

    def test_connected_requires_fresh_handshake_then_authenticated_management_read(self):
        service = HubPeerOrchestrator(self.adapter, HostOperationPolicy("isolated-magic-connect-test", True, True, "wg-mm"), clock=lambda: 1100)
        service.provision(self.session, self.plan, self.hub, "tenant-a", confirmed=True, idempotency_key="operation-12345")
        not_yet = service.observe(self.session, self.plan, self.hub, "tenant-a")
        self.assertEqual(not_yet["state"], "awaiting_handshake")
        self.assertFalse(not_yet["connection_verified"])
        self.adapter.handshake = True
        observed = service.observe(self.session, self.plan, self.hub, "tenant-a")
        self.assertEqual(observed["state"], "verifying_management")
        self.assertFalse(observed["connection_verified"])
        bad = service.confirm_management_read(self.plan, {"evidence_source":"fixture_only", "authenticated":True, "identity_verified":False, "tenant_id":"tenant-a", "router_id":"router-a", "observed_at":1001}, tenant_id="tenant-a", router_id="router-a")
        self.assertEqual(bad["state"], "verifying_management")
        good = service.confirm_management_read(self.plan, {"evidence_source":"authenticated_routeros_read", "authenticated":True, "identity_verified":True, "tenant_id":"tenant-a", "router_id":"router-a", "observed_at":1001}, tenant_id="tenant-a", router_id="router-a")
        self.assertEqual(good["state"], "connected")
        self.assertTrue(good["connection_verified"])
        wrong_tenant = service.confirm_management_read(self.plan, {"evidence_source":"authenticated_routeros_read", "authenticated":True, "identity_verified":True, "tenant_id":"tenant-b", "router_id":"router-a", "observed_at":1002}, tenant_id="tenant-b", router_id="router-a")
        self.assertFalse(wrong_tenant["connection_verified"])

    def test_adapter_failure_requires_recovery_and_emergency_lock_is_auditable(self):
        service = HubPeerOrchestrator(self.adapter, HostOperationPolicy("isolated-magic-connect-test", True, True, "wg-mm"), clock=lambda: 1200)
        self.adapter.fail_provision = True
        with self.assertRaisesRegex(HubOrchestrationError, "hub_peer_provision_or_readback_failed"):
            service.provision(self.session, self.plan, self.hub, "tenant-a", confirmed=True, idempotency_key="operation-12345")
        self.assertEqual(self.plan.lifecycle_state, "failed_recovery_required")
        self.adapter.fail_provision = False
        with self.assertRaisesRegex(HubOrchestrationError, "recovery_check_required_before_retry"):
            service.provision(self.session, self.plan, self.hub, "tenant-a", confirmed=True, idempotency_key="operation-12345")
        recovered = service.recover(self.session, self.plan, self.hub, "tenant-a", confirmed=True)
        self.assertEqual(recovered["state"], "awaiting_bootstrap")
        self.assertTrue(recovered["retry_allowed"])
        self.assertEqual(self.plan.peer_operation_key, 'operation-12345')
        self.plan.lifecycle_state = "awaiting_handshake"
        locked = service.emergency_lock(self.session, self.plan, self.hub, "tenant-a", actor_id="owner-a", reason="Suspected unauthorized access", confirmed=True)
        self.assertEqual(locked["state"], "management_locked")
        self.assertFalse(locked["on_router_cleanup_verified"])
        self.assertFalse(locked["local_hotspot_affected"])
        self.assertEqual(self.plan.management_lock_reason, "Suspected unauthorized access")
        self.assertEqual(len(self.adapter.revocations), 1)

    def test_enabled_host_operations_still_require_exact_dedicated_interface(self):
        service = HubPeerOrchestrator(self.adapter, HostOperationPolicy("isolated-magic-connect-test", True, True))
        with self.assertRaisesRegex(HubOrchestrationError, "host_peer_interface_not_allowlisted"):
            service.provision(self.session, self.plan, self.hub, "tenant-a", confirmed=True, idempotency_key="operation-12345")
        self.assertEqual(self.adapter.provisions, [])
        self.assertEqual(self.plan.lifecycle_state, "awaiting_bootstrap")

        service = HubPeerOrchestrator(self.adapter, HostOperationPolicy("isolated-magic-connect-test", True, True, "wg-other"))
        with self.assertRaisesRegex(HubOrchestrationError, "host_peer_interface_not_allowlisted"):
            service.provision(self.session, self.plan, self.hub, "tenant-a", confirmed=True, idempotency_key="operation-12345")
        self.assertEqual(self.adapter.provisions, [])

    def test_unapproved_expired_or_cross_site_enrollment_cannot_write(self):
        service = HubPeerOrchestrator(self.adapter, HostOperationPolicy('isolated-magic-connect-test', True, True, 'wg-mm'), clock=lambda:1100)
        attempt = self.session.get(MagicConnectAttempt, 'attempt-a')
        for field, value in [('status', 'denied'), ('expires', 1099), ('site_id', 'wrong-site')]:
            old = getattr(attempt, field); setattr(attempt, field, value)
            with self.assertRaisesRegex(HubOrchestrationError, 'valid_owner_approved_enrollment_required'):
                service.provision(self.session,self.plan,self.hub,'tenant-a',confirmed=True,idempotency_key='op-bound')
            setattr(attempt, field, old)
        self.assertEqual(self.adapter.provisions, [])

    def test_interrupted_claim_has_durable_authority_and_needs_readback(self):
        service = HubPeerOrchestrator(self.adapter, HostOperationPolicy('isolated-magic-connect-test', True, True, 'wg-mm'), clock=lambda:1100)
        def interrupted(*args): raise RuntimeError('process interrupted fixture')
        self.adapter.provision_peer = interrupted
        with self.assertRaises(RuntimeError): service.provision(self.session,self.plan,self.hub,'tenant-a',confirmed=True,idempotency_key='op-bound')
        self.session.rollback(); self.session.refresh(self.plan)
        self.assertEqual(self.plan.lifecycle_state,'provisioning_peer')
        self.assertEqual(self.session.get(MagicConnectEnrollment,self.plan.id).consumed_at,1100)
        with self.assertRaisesRegex(HubOrchestrationError,'same_peer_operation_in_progress'):
            service.provision(self.session,self.plan,self.hub,'tenant-a',confirmed=True,idempotency_key='op-bound')
        self.assertEqual(service.recover(self.session,self.plan,self.hub,'tenant-a',confirmed=True)['recovery_readback'],'peer_absent')
        self.assertEqual(self.plan.peer_operation_key,'op-bound')

    def test_stale_and_future_evidence_never_connects(self):
        service = HubPeerOrchestrator(self.adapter,HostOperationPolicy(),clock=lambda:1100)
        for handshake, observed in [(800,1000),(1000,1200),(1200,1200)]:
            self.plan.lifecycle_state='verifying_management';self.plan.handshake_verified_at=handshake
            result=service.confirm_management_read(self.plan,{'evidence_source':'authenticated_routeros_read','authenticated':True,'identity_verified':True,'tenant_id':'tenant-a','router_id':'router-a','observed_at':observed},tenant_id='tenant-a',router_id='router-a')
            self.assertFalse(result['connection_verified'])

    def test_failed_emergency_lock_never_recovers_to_peer_reprovision(self):
        from backend.wireguard_hub import HubWireGuardError
        service=HubPeerOrchestrator(self.adapter,HostOperationPolicy('isolated-magic-connect-test',True,True,'wg-mm'),clock=lambda:1100)
        service.provision(self.session,self.plan,self.hub,'tenant-a',confirmed=True,idempotency_key='op-bound')
        def failed(*args): raise HubWireGuardError('fixture revoke interruption')
        self.adapter.revoke_peer=failed
        with self.assertRaises(HubOrchestrationError):service.emergency_lock(self.session,self.plan,self.hub,'tenant-a',actor_id='owner-a',reason='Synthetic security incident',confirmed=True)
        recovered=service.recover(self.session,self.plan,self.hub,'tenant-a',confirmed=True)
        self.assertFalse(recovered['retry_allowed']);self.assertEqual(recovered['state'],'management_lock_pending')
        with self.assertRaisesRegex(HubOrchestrationError,'management_peer_locked'):
            service.provision(self.session,self.plan,self.hub,'tenant-a',confirmed=True,idempotency_key='op-bound')


if __name__ == "__main__":
    unittest.main()
