import json
import secrets
import unittest
import httpx
from backend.bootstrap_security import inspect_security_prerequisites,validate_identity_delivery,dispatch_identity_provisioning,BootstrapSecurityError,POLICIES,provisioning_review
from backend.routeros_adapter import RouterOSCredential,RouterOSClient
from test_hub_orchestrator import HubOrchestratorTests as Fixture


class BootstrapReviewTests(unittest.TestCase):
    setUp=Fixture.setUp
    tearDown=Fixture.tearDown
    # Reuse synthetic fixture setup only, not inherited unrelated tests.
    def test_review_exact_authority_and_non_dispatchable(self):
        review=provisioning_review(self.session,'plan-a','owner-a',now=1100)
        self.assertFalse(review['credential_delivery_enabled']);self.assertFalse(review['router_writes_enabled'])
        self.assertEqual(review['identities']['monitoring']['candidate_policies'],['read','api','rest-api'])
        self.assertEqual(review['identities']['safe_change']['candidate_policies'],['read','write','api','rest-api'])
        self.assertNotIn('write',review['identities']['monitoring']['candidate_policies'])
        with self.assertRaises(BootstrapSecurityError):provisioning_review(self.session,'plan-a','wrong-owner',now=1100)
        with self.assertRaises(BootstrapSecurityError):provisioning_review(self.session,'plan-a','owner-a',now=4102444800)
        with self.assertRaisesRegex(BootstrapSecurityError,'hardware_acceptance'):dispatch_identity_provisioning(review)
        original=review['binding_digest'];self.plan.snapshot={'changed':'review'};self.session.flush()
        self.assertNotEqual(provisioning_review(self.session,'plan-a','owner-a',now=1100)['binding_digest'],original)


class DeliveryTests(unittest.TestCase):
    def setUp(self):
        self.review={'binding_digest':'a'*64,'identities':{r:{'username':r,'candidate_policies':list(p)} for r,p in POLICIES.items()}}
        self.payload={'version':1,'binding_digest':'a'*64,'identities':{r:{'username':r,'policies':list(p),'password':secrets.token_urlsafe(32)} for r,p in POLICIES.items()}}
    def test_strict_secret_envelope_and_redacted_representations(self):
        parsed=validate_identity_delivery(json.dumps(self.payload).encode(),self.review)
        self.assertNotIn(parsed.monitoring_password,repr(parsed));self.assertNotIn(parsed.safe_change_password,repr(parsed))
        self.assertNotIn(parsed.monitoring_password,repr(RouterOSCredential('https://router','mm-monitor-x',parsed.monitoring_password)))
    def test_wrong_binding_extra_fields_reused_credentials_or_role_escalation_fail(self):
        modifications=[lambda p:p.update(binding_digest='b'*64),lambda p:p.update(script='untrusted'),lambda p:p['identities']['safe_change'].update(password=p['identities']['monitoring']['password']),lambda p:p['identities']['monitoring'].update(policies=['read','write','policy']),lambda p:p.update(version=True)]
        for edit in modifications:
            p=json.loads(json.dumps(self.payload));edit(p)
            with self.assertRaisesRegex(BootstrapSecurityError,'invalid_delivery_envelope'):validate_identity_delivery(json.dumps(p).encode(),self.review)
    def test_truncation_oversize_duplicate_keys_invalid_utf8_fail(self):
        for raw in [b'{',b'x'*4097,b'\xff',b'{"version":1,"version":1}',b'[]']:
            with self.assertRaises(BootstrapSecurityError):validate_identity_delivery(raw,self.review)


class MetadataTests(unittest.TestCase):
    def test_fixed_gets_redacted_metadata_never_prove_S1_or_connection(self):
        paths=[]
        def respond(request):
            self.assertEqual(request.method,'GET');paths.append(request.url.path)
            self.assertIn('.proplist',request.url.params)
            path=request.url.path
            rows=[]
            if path.endswith('system/resource'):rows=[{'version':'7.24.2','architecture-name':'arm64','serial-number':'MUST_NOT_LEAK'}]
            elif path.endswith('ip/service'):rows=[{'disabled':'false','certificate':'PRIVATE_NAME','address':'192.0.2.1','password':'MUST_NOT_LEAK'}]
            elif path.endswith('user'):rows=[{'group':'custom','disabled':'false','address':'10.0.0.1/32'}]
            elif path.endswith('user/group'):rows=[{'name':'custom','policy':'read,api,rest-api'}]
            return httpx.Response(200,json=rows)
        with RouterOSClient(RouterOSCredential('https://router','mm-monitor-router01','synthetic-only'),transport=httpx.MockTransport(respond)) as client:
            result=inspect_security_prerequisites(client,'router01')
        self.assertNotIn('MUST_NOT_LEAK',json.dumps(result));self.assertNotIn('PRIVATE_NAME',json.dumps(result))
        self.assertEqual(result['S1'],'INCONCLUSIVE');self.assertFalse(result['connection_verified']);self.assertEqual(len(paths),8)
    def test_HTTP_false_TLS_and_owner_credentials_rejected_before_requests(self):
        for credential in [RouterOSCredential('http://router','mm-monitor-router01','x'),RouterOSCredential('https://router','mm-monitor-router01','x',False),RouterOSCredential('https://router','admin','x')]:
            with RouterOSClient(credential,transport=httpx.MockTransport(lambda r:self.fail('No request allowed'))) as client:
                with self.assertRaises(BootstrapSecurityError):inspect_security_prerequisites(client,'router01')


# Avoid collecting the imported fixture's inherited test methods a second time.
del Fixture
