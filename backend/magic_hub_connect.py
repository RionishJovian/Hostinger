"""One-paste Magic Hub connect: owner click creates a tokenized RouterOS script.

The visible script never contains Hub-admin secrets or router passwords. The
router redeems the token over HTTPS, receives peer config + a temporary
enrollment login (response only, never shown in the UI), and the app finishes
management identities after handshake — Connected only with fresh verified read.
"""
from __future__ import annotations
import hashlib,ipaddress,os,re,secrets,time
from fastapi import Depends,HTTPException,Request,Response
from pydantic import Field
from sqlalchemy import select,update
from sqlalchemy.exc import IntegrityError
from .models import (
 MagicConnectAttempt,MagicConnectEnrollment,MagicConnectEvent,MagicHub,HubAssignment,
 MagicHubConnectToken,RouterDevice,RouterPlan,RouterPlanRetirement,Site,
)
from .hubs import public_key,router_interface,hub_json,conflict_portals
from .hub_orchestrator import HubPeerOrchestrator,HostOperationPolicy,HubOrchestrationError,connection_is_fresh
from .wireguard_hub import hub_adapter_from_environment
from .management_enrollment import (
 CERTIFICATE_PREFIX,ENROLL_PREFIX,GROUPS,USER_PREFIX,ManagementSetupError,
 enrollment_password,serial_digest,provision_management_identities,TECHNICIAN_SETUP_SECONDS,
)
from .enrollment import sync_enrollment_state
from .schemas import Strict
from . import magic_hub_script as script_mod

TOKEN_LIFETIME_SECONDS = 1800
TOKEN_BYTES = 24

PROGRESS_STEPS = (
 'waiting', 'reported', 'peer_added', 'awaiting_handshake',
 'management_applied', 'finishing', 'connected',
)


class ConnectStart(Strict):
 hub_id: str | None = Field(default=None, min_length=1, max_length=36)
 replace_existing: bool = False
 reason: str | None = Field(default=None, max_length=500)


def _digest(value: str) -> str:
 return hashlib.sha256(value.encode('utf-8')).hexdigest()


def _owner(u):
 if u.role != 'sme' or getattr(u, 'staff_profile', None):
  raise HTTPException(403, 'SME Owner/Admin permission required')


def _public_base(request: Request) -> str:
 configured = (os.environ.get('MIKROMAGIC_PUBLIC_BASE_URL') or '').rstrip('/')
 if configured:
  return configured
 origin = (request.headers.get('origin') or '').rstrip('/')
 if origin.startswith('https://') or origin.startswith('http://localhost') or origin.startswith('http://127.'):
  return origin
 # Prefer forwarded host from the public reverse proxy
 host = request.headers.get('x-forwarded-host') or request.headers.get('host') or 'megamagic.tech'
 proto = request.headers.get('x-forwarded-proto') or 'https'
 return f'{proto}://{host}'.rstrip('/')


def _token_plain() -> str:
 # URL-safe, RouterOS-friendly (no padding)
 return secrets.token_urlsafe(TOKEN_BYTES)


def _setup_enabled(app) -> bool:
 return bool(app.state.magic_connect_pairing_enabled and getattr(app.state, 'magic_connect_router_setup_enabled', False))


def _orchestrator(app):
 existing = getattr(app.state, 'magic_hub_orchestrator', None)
 if existing:
  return existing
 policy = HostOperationPolicy(
  environment=os.environ.get('MIKROMAGIC_ENVIRONMENT', ''),
  peer_writes_enabled=os.environ.get('MIKROMAGIC_HUB_PEER_WRITES_ENABLED', '').lower() == 'true',
  peer_reads_enabled=os.environ.get('MIKROMAGIC_HUB_PEER_READS_ENABLED', '').lower() == 'true',
  dedicated_interface=os.environ.get('MIKROMAGIC_HUB_DEDICATED_INTERFACE'),
  deployment_mode=os.environ.get('MIKROMAGIC_HUB_MODE', ''),
 )
 return HubPeerOrchestrator(hub_adapter_from_environment(), policy)


def _event(s, attempt, actor_kind, event, actor_id=None, now=None):
 s.add(MagicConnectEvent(
  tenant_id=attempt.tenant_id, attempt_id=attempt.id, actor_kind=actor_kind,
  actor_id=actor_id, event=event, created=int(now or time.time()),
 ))


def _progress_payload(token: MagicHubConnectToken, plan: RouterPlan | None, now: int) -> dict:
 step = token.status
 verified = bool(plan and connection_is_fresh(plan, now))
 if verified:
  step = 'connected'
 labels = {
  'waiting': 'Waiting for router',
  'reported': 'Router reported',
  'peer_added': 'Hub peer added',
  'awaiting_handshake': 'Handshake',
  'management_applied': 'Management ready',
  'finishing': 'Management ready',
  'connected': 'Connected',
  'failed': 'Failed',
  'expired': 'Expired',
  'revoked': 'Revoked',
 }
 return {
  'token_id': token.id,
  'router_id': token.router_id,
  'status': step,
  'label': labels.get(step, step),
  'steps': list(PROGRESS_STEPS),
  'failure_code': token.failure_code,
  'failure_message': token.failure_message,
  'model_mismatch': token.model_mismatch,
  'version_mismatch': token.version_mismatch,
  'expires': token.expires,
  'connection_verified': verified,
  'detection': {
   k: (token.detection_facts or {}).get(k)
   for k in ('board', 'version', 'architecture', 'serial', 'interface', 'listen_port')
  } if token.detection_facts else None,
 }


def register_magic_hub_connect(app, current, db, owner, log):
 def require_setup():
  if not _setup_enabled(app):
   raise HTTPException(503, 'Magic Hub one-paste connect is not enabled')

 def visible_router(s, u, router_id):
  _owner(u)
  router = s.get(RouterDevice, router_id)
  if not router or router.tenant_id != u.tenant_id:
   raise HTTPException(404, 'Router not found')
  return router

 def assigned_hub(s, u, hub_id=None):
  q = select(MagicHub).join(HubAssignment).where(HubAssignment.tenant_id == u.tenant_id)
  hubs = list(s.scalars(q.order_by(MagicHub.created)))
  if not hubs:
   raise HTTPException(409, 'No Magic Hub is assigned to this business')
  if hub_id:
   hub = next((h for h in hubs if h.id == hub_id), None)
   if not hub:
    raise HTTPException(404, 'Assigned hub not found')
   return hub
  return hubs[0]

 def retire_plan(s, u, plan: RouterPlan, reason: str, now: int):
  enrollment = s.get(MagicConnectEnrollment, plan.id)
  attempt_id = enrollment.attempt_id if enrollment else None
  archive = RouterPlanRetirement(
   tenant_id=plan.tenant_id, router_id=plan.router_id, plan_id=plan.id, hub_id=plan.hub_id,
   router_public_key=plan.router_public_key, address=plan.address, snapshot=plan.snapshot or {},
   lifecycle_state=plan.lifecycle_state, lock_reason=plan.management_lock_reason,
   attempt_id=attempt_id, retired_by=u.id, retired_at=now, reason=reason,
  )
  s.add(archive)
  if enrollment:
   s.delete(enrollment)
  s.delete(plan)
  log(s, u, 'router_plan_retired_for_repairing', archive.plan_id)
  return archive

 def revoke_active_plan(s, u, router: RouterDevice, reason: str, now: int):
  plan = s.scalar(select(RouterPlan).where(RouterPlan.router_id == router.id, RouterPlan.tenant_id == u.tenant_id))
  if not plan:
   return None
  hub = s.get(MagicHub, plan.hub_id)
  if hub and plan.lifecycle_state not in ('management_locked', 'revoked'):
   try:
    result = _orchestrator(app).emergency_lock(
     s, plan, hub, u.tenant_id, actor_id=u.id, reason=reason, confirmed=True,
    )
    log(s, u, 'hub_management_emergency_lock', plan.id)
    s.commit()
    s.refresh(plan)
   except HubOrchestrationError as error:
    raise HTTPException(error.status, {'code': error.code, 'message': 'Could not revoke the existing Hub peer'}) from error
  return retire_plan(s, u, plan, reason, now)

 @app.post('/v1/routers/{router_id}/magic-hub-connect', status_code=201)
 def start_connect(router_id: str, b: ConnectStart, request: Request, u=Depends(current), s=Depends(db)):
  require_setup()
  router = visible_router(s, u, router_id)
  now = int(time.time())
  existing = s.scalar(select(RouterPlan).where(RouterPlan.router_id == router.id))
  if existing and not b.replace_existing:
   raise HTTPException(409, {
    'code': 'plan_exists',
    'message': 'This router already has a Magic Hub plan. Confirm replace_existing to revoke it and generate a new script.',
    'lifecycle_state': existing.lifecycle_state,
   })
  if existing and b.replace_existing:
   reason = (b.reason or 'Owner re-run one-paste Magic Hub connect').strip()
   if len(reason) < 8:
    reason = 'Owner re-run one-paste Magic Hub connect'
   revoke_active_plan(s, u, router, reason, now)
   s.commit()

  # Revoke any waiting tokens for this router
  for old in s.scalars(select(MagicHubConnectToken).where(
   MagicHubConnectToken.router_id == router.id,
   MagicHubConnectToken.status.in_(['waiting', 'reported', 'peer_added', 'awaiting_handshake', 'management_applied', 'finishing']),
  )):
   old.status = 'revoked'
   old.failure_code = 'superseded'

  hub = assigned_hub(s, u, b.hub_id)
  plain = _token_plain()
  token_hash = _digest('magic-hub-connect:' + plain)
  # Synthetic approved pairing: owner click is the approval (no QR technician).
  code_raw = secrets.token_hex(16)
  attempt = MagicConnectAttempt(
   tenant_id=u.tenant_id, site_id=router.site_id, owner_id=u.id,
   router_name=router.name, code_hash=_digest('magic-connect-code:' + code_raw.upper()),
   comparison_code=f'{secrets.randbelow(1_000_000):06d}', status='approved',
   enrollment_state='pairing_approved', state_changed_at=now, created=now,
   expires=now + TOKEN_LIFETIME_SECONDS, approved_at=now, claimed_at=now,
   router_id=router.id,
  )
  s.add(attempt)
  try:
   s.flush()
  except IntegrityError:
   s.rollback()
   raise HTTPException(409, 'Could not start Magic Hub connect; try again')
  row = MagicHubConnectToken(
   tenant_id=u.tenant_id, router_id=router.id, owner_id=u.id, attempt_id=attempt.id,
   token_hash=token_hash, status='waiting', created=now, expires=now + TOKEN_LIFETIME_SECONDS,
  )
  s.add(row)
  _event(s, attempt, 'owner', 'one_paste_connect_started', u.id, now)
  log(s, u, 'magic_hub_one_paste_started', router.id)
  s.commit()

  base = _public_base(request)
  script = script_mod.generate_enroll_script(
   token=plain, base_url=base, router_id=router.id, hub_endpoint=hub.endpoint,
  )
  rollback = script_mod.rollback_script()
  return {
   'token_id': row.id,
   'router_id': router.id,
   'hub_id': hub.id,
   'expires': row.expires,
   'script': script,
   'rollback_script': rollback,
   'fetch_certificate_mode': script_mod.FETCH_CERT_MODE,
   'fetch_certificate_note': (
    'RouterOS fetch uses check-certificate=yes-without-crl: the TLS chain is verified '
    'against RouterOS built-in public CA anchors (Let\'s Encrypt for megamagic.tech), '
    'but certificate revocation lists are not checked. Prefer this over disabling verification.'
   ),
   'progress': _progress_payload(row, None, now),
  }

 @app.get('/v1/routers/{router_id}/magic-hub-connect/{token_id}')
 def connect_status(router_id: str, token_id: str, u=Depends(current), s=Depends(db)):
  require_setup()
  router = visible_router(s, u, router_id)
  token = s.get(MagicHubConnectToken, token_id)
  if not token or token.router_id != router.id or token.tenant_id != u.tenant_id:
   raise HTTPException(404, 'Connect session not found')
  now = int(time.time())
  if token.status == 'waiting' and now >= token.expires:
   token.status = 'expired'
   s.commit()
  plan = s.scalar(select(RouterPlan).where(RouterPlan.router_id == router.id))
  # Advance: observe handshake and finish management when the script reported ready.
  if token.status in ('peer_added', 'awaiting_handshake', 'management_applied', 'finishing') and plan:
   try:
    _advance_connect(app, s, u, token, plan, now)
    s.commit()
    s.refresh(token)
    s.refresh(plan)
   except Exception:
    s.rollback()
    token = s.get(MagicHubConnectToken, token_id)
    plan = s.scalar(select(RouterPlan).where(RouterPlan.router_id == router.id))
  return _progress_payload(token, plan, now)

 @app.post('/v1/routers/{router_id}/magic-hub-connect/{token_id}/revoke')
 def revoke_connect(router_id: str, token_id: str, u=Depends(current), s=Depends(db)):
  require_setup()
  router = visible_router(s, u, router_id)
  token = s.get(MagicHubConnectToken, token_id)
  if not token or token.router_id != router.id or token.tenant_id != u.tenant_id:
   raise HTTPException(404, 'Connect session not found')
  if token.status in ('connected', 'revoked'):
   return {'revoked': token.status == 'revoked', 'replayed': True}
  token.status = 'revoked'
  token.failure_code = 'owner_revoked'
  attempt = s.get(MagicConnectAttempt, token.attempt_id)
  if attempt and attempt.status == 'approved':
   attempt.status = 'cancelled'
   attempt.enrollment_state = 'revoked'
   attempt.cancelled_at = int(time.time())
  log(s, u, 'magic_hub_one_paste_revoked', router.id)
  s.commit()
  return {'revoked': True, 'replayed': False}

 @app.post('/v1/magic-connect/hub-enroll/{token}')
 async def redeem_enroll(token: str, request: Request, s=Depends(db)):
  """Unauthenticated router callback — authority is the single-use token only."""
  require_setup()
  now = int(time.time())
  token_hash = _digest('magic-hub-connect:' + token)
  row = s.scalar(select(MagicHubConnectToken).where(MagicHubConnectToken.token_hash == token_hash))
  if not row:
   return Response(script_mod.format_enroll_response({'status': 'error', 'error': 'invalid_token'}), media_type='text/plain', status_code=404)
  if row.status in ('revoked', 'failed', 'expired'):
   return Response(script_mod.format_enroll_response({'status': 'error', 'error': row.status}), media_type='text/plain', status_code=409)
  if now >= row.expires and row.status == 'waiting':
   row.status = 'expired'; s.commit()
   return Response(script_mod.format_enroll_response({'status': 'error', 'error': 'expired'}), media_type='text/plain', status_code=410)
  # Replay after peer provision returns the same peer config without the enroll password.
  body = (await request.body()).decode('utf-8', errors='replace')
  fields = script_mod.parse_enroll_request(body)
  if row.consumed_at and row.peer_provisioned_at:
   plan = s.scalar(select(RouterPlan).where(RouterPlan.router_id == row.router_id))
   if plan:
    snap = plan.snapshot
    hub_row = s.get(MagicHub, plan.hub_id)
    return Response(script_mod.format_enroll_response({
     'status': 'ok',
     'hub_public_key': snap['hub']['public_key'],
     'endpoint': snap['hub']['endpoint'],
     'endpoint_port': str(snap['hub']['port']),
     'hub_address': snap['hub']['hub_address'],
     'router_address': snap['router']['address'],
     'hub_pool': hub_row.pool if hub_row else '',
     'keepalive': str(snap['router']['persistent_keepalive_seconds']),
     'interface': snap['router']['interface'],
     'listen_port': str(fields.get('listen_port') or ''),
     'enroll_user': ENROLL_PREFIX + row.router_id[:8],
     'enroll_password': '',  # never re-emit
     'certificate': CERTIFICATE_PREFIX + row.router_id[:8],
    }), media_type='text/plain')

  try:
   pub = public_key(fields.get('public_key', ''))
  except ValueError:
   return Response(script_mod.format_enroll_response({'status': 'error', 'error': 'invalid_public_key'}), media_type='text/plain', status_code=422)

  attempt = s.get(MagicConnectAttempt, row.attempt_id)
  router = s.get(RouterDevice, row.router_id)
  if not attempt or not router or attempt.status != 'approved' or attempt.expires <= now:
   row.status = 'failed'; row.failure_code = 'attempt_closed'
   s.commit()
   return Response(script_mod.format_enroll_response({'status': 'error', 'error': 'attempt_closed'}), media_type='text/plain', status_code=409)

  if s.scalar(select(MagicHub.id).where(MagicHub.public_key == pub)) or s.scalar(select(RouterPlan.id).where(RouterPlan.router_public_key == pub)):
   return Response(script_mod.format_enroll_response({'status': 'error', 'error': 'public_key_in_use'}), media_type='text/plain', status_code=409)

  facts = {
   'board': fields.get('board'), 'version': fields.get('version'),
   'architecture': fields.get('architecture'), 'serial': fields.get('serial'),
   'interface': fields.get('interface') or router_interface(router.id),
   'listen_port': fields.get('listen_port'), 'input_rules': fields.get('input_rules'),
   'interface_count': fields.get('interface_count'),
  }
  # Mismatch flags only when the owner previously typed model/version (legacy rows).
  prior_model = (router.model or '').strip()
  prior_version = (router.reported_routeros or '').strip()
  model_mismatch = bool(
   facts['board'] and prior_model
   and facts['board'].lower() not in prior_model.lower()
   and prior_model.lower() not in facts['board'].lower()
  )
  version_mismatch = bool(
   facts['version'] and prior_version
   and not facts['version'].startswith(prior_version.split()[0])
  )
  # Script-reported facts become the router card identity (name-only registration).
  if facts.get('board'):
   router.model = facts['board'][:120]
  if facts.get('version'):
   router.reported_routeros = facts['version'][:40]
  if facts.get('architecture'):
   router.architecture = facts['architecture'][:40]
  if facts.get('serial'):
   router.reported_serial = facts['serial'][:80]

  iface = facts['interface']
  if not re.fullmatch(r'[A-Za-z0-9_.-]{1,15}', iface or ''):
   iface = router_interface(router.id)

  hub = s.scalar(
   select(MagicHub).join(HubAssignment).where(HubAssignment.tenant_id == row.tenant_id).order_by(MagicHub.created)
  )
  if not hub:
   return Response(script_mod.format_enroll_response({'status': 'error', 'error': 'no_hub'}), media_type='text/plain', status_code=409)

  # Claim token single-use
  claimed = s.execute(update(MagicHubConnectToken).where(
   MagicHubConnectToken.id == row.id, MagicHubConnectToken.status == 'waiting',
   MagicHubConnectToken.consumed_at.is_(None), MagicHubConnectToken.expires > now,
  ).values(
   status='reported', consumed_at=now, detection_facts=facts,
   model_mismatch=model_mismatch, version_mismatch=version_mismatch,
  ).execution_options(synchronize_session=False)).rowcount
  if claimed != 1:
   s.rollback()
   return Response(script_mod.format_enroll_response({'status': 'error', 'error': 'already_used'}), media_type='text/plain', status_code=409)
  s.expire_all()
  row = s.get(MagicHubConnectToken, row.id)
  attempt.router_public_key = pub
  attempt.router_key_submitted_at = now

  # Allocate plan (owner click already approved — auto-review)
  pool = ipaddress.ip_network(hub.pool)
  try:
   conflict_portals(s, router, pool)
  except HTTPException as e:
   row.status = 'failed'; row.failure_code = 'pool_conflict'; row.failure_message = str(e.detail)
   s.commit()
   return Response(script_mod.format_enroll_response({'status': 'error', 'error': 'pool_conflict'}), media_type='text/plain', status_code=409)

  index = s.execute(
   update(MagicHub).where(MagicHub.id == hub.id, MagicHub.next_host < 255)
   .values(next_host=MagicHub.next_host + 1).returning(MagicHub.next_host)
  ).scalar_one_or_none()
  if index is None:
   row.status = 'failed'; row.failure_code = 'pool_exhausted'; s.commit()
   return Response(script_mod.format_enroll_response({'status': 'error', 'error': 'pool_exhausted'}), media_type='text/plain', status_code=409)

  address = str(pool.network_address + index - 1)
  hub_info = hub_json(hub)
  hub_address = hub_info['hub_address']
  snapshot = {
   'version': 1, 'purpose': 'router_management',
   'hub': {k: hub_info[k] for k in ['id', 'name', 'endpoint', 'port', 'public_key', 'hub_address']},
   'router': {
    'id': router.id, 'site_id': router.site_id, 'public_key': pub, 'interface': iface,
    'address': address + '/32', 'peer_allowed_addresses': [hub_address + '/32'],
    'routes': [{'destination': hub_address + '/32', 'interface': iface}],
    'persistent_keepalive_seconds': 25,
   },
   'hub_peer': {'public_key': pub, 'allowed_addresses': [address + '/32']},
   'private_key_location': 'router_only', 'guest_traffic_via_hub': False,
   'bootstrap_scope': {'status': 'one_paste_enroll', 'source': 'magic_hub_connect_token'},
  }
  plan = RouterPlan(
   tenant_id=row.tenant_id, router_id=router.id, hub_id=hub.id, router_public_key=pub,
   address=address, snapshot=snapshot, created=now, reviewed_at=now,
   lifecycle_state='awaiting_bootstrap',
  )
  s.add(plan)
  try:
   s.flush()
  except IntegrityError:
   s.rollback()
   return Response(script_mod.format_enroll_response({'status': 'error', 'error': 'plan_conflict'}), media_type='text/plain', status_code=409)

  serial = serial_digest(facts.get('serial') or '')
  if not serial:
   # Allow enroll without serial only if routerboard missing; management setup will fail later with clear code.
   serial = None
  enrollment = MagicConnectEnrollment(
   plan_id=plan.id, attempt_id=attempt.id, tenant_id=row.tenant_id, site_id=router.site_id,
   owner_id=row.owner_id, expected_serial_digest=serial, created=now,
  )
  s.add(enrollment)
  _event(s, attempt, 'technician', 'one_paste_router_reported', now=now)
  s.commit()

  # Provision Hub peer (owner button click is the confirmation)
  try:
   orch = _orchestrator(app)
   # Re-load in orchestrator session context
   s.refresh(plan); s.refresh(hub); s.refresh(enrollment); s.refresh(attempt)
   result = orch.provision(
    s, plan, hub, row.tenant_id, confirmed=True,
    idempotency_key='one-paste-' + row.id,
   )
   s.refresh(plan)
   enrollment.peer_provisioned_at = now
   row.status = 'peer_added'
   row.peer_provisioned_at = now
   row.status = 'awaiting_handshake'
   # Extend attempt so management finish fits within the window
   attempt.expires = max(attempt.expires, now + TECHNICIAN_SETUP_SECONDS)
   _event(s, attempt, 'system', 'one_paste_peer_provisioned', now=now)
   s.commit()
  except HubOrchestrationError as error:
   row = s.get(MagicHubConnectToken, row.id)
   if row:
    row.status = 'failed'
    row.failure_code = error.code
    row.failure_message = 'Hub peer could not be added'
    s.commit()
   return Response(script_mod.format_enroll_response({'status': 'error', 'error': error.code}), media_type='text/plain', status_code=503)

  try:
   password = enrollment_password(router.id, create=True)
  except ManagementSetupError as e:
   return Response(script_mod.format_enroll_response({'status': 'error', 'error': e.code}), media_type='text/plain', status_code=503)

  enroll_user = ENROLL_PREFIX + router.id[:8]
  body_out = script_mod.format_enroll_response({
   'status': 'ok',
   'hub_public_key': hub.public_key,
   'endpoint': hub.endpoint,
   'endpoint_port': str(hub.port),
   'hub_address': hub_address,
   'router_address': address + '/32',
   'hub_pool': hub.pool,
   'keepalive': '25',
   'interface': iface,
   'listen_port': str(facts.get('listen_port') or ''),
   'enroll_user': enroll_user,
   'enroll_password': password,
   'certificate': CERTIFICATE_PREFIX + router.id[:8],
  })
  return Response(body_out, media_type='text/plain')

 @app.get('/v1/magic-connect/hub-enroll/{token}/progress')
 def router_progress(token: str, phase: str = '', message: str = '', s=Depends(db)):
  """Router-side progress ping (no auth beyond token). Never returns secrets."""
  require_setup()
  now = int(time.time())
  token_hash = _digest('magic-hub-connect:' + token)
  row = s.scalar(select(MagicHubConnectToken).where(MagicHubConnectToken.token_hash == token_hash))
  if not row:
   return Response('status=error\n', media_type='text/plain', status_code=404)
  phase = (phase or '').strip().lower()
  if phase == 'failed':
   row.status = 'failed'
   row.failure_code = 'router_script_failed'
   row.failure_message = (message or 'script failed')[:500]
  elif phase == 'handshake' and row.status in ('peer_added', 'awaiting_handshake'):
   row.status = 'awaiting_handshake'
  elif phase == 'management_applied' and row.status in ('awaiting_handshake', 'peer_added', 'management_applied'):
   row.management_applied_at = now
   row.status = 'management_applied'
  s.commit()
  return Response('status=ok\n', media_type='text/plain')


def _advance_connect(app, s, u, token: MagicHubConnectToken, plan: RouterPlan, now: int):
 """Observe handshake; when management_applied, create identities and preflight."""
 from .routeros_adapter import RouterOSClient, RouterOSError, discover_routeros, load_routeros_monitoring_credential
 from .enrollment import router_identity_digest
 from .hub_orchestrator import confirm_management_read
 import hmac

 hub = s.get(MagicHub, plan.hub_id)
 if not hub:
  return
 orch = _orchestrator(app)
 try:
  observed = orch.observe(s, plan, hub, token.tenant_id)
 except HubOrchestrationError:
  return
 s.refresh(plan)
 if plan.lifecycle_state in ('awaiting_handshake',) and not plan.handshake_verified_at:
  return
 if token.status == 'awaiting_handshake' and plan.handshake_verified_at:
  token.status = 'awaiting_handshake'
 if token.status != 'management_applied' and not token.management_applied_at:
  return
 if not plan.handshake_verified_at or not 0 <= now - plan.handshake_verified_at <= 180:
  # Nudge observe again soon; popup keeps polling
  return

 enrollment = s.get(MagicConnectEnrollment, plan.id)
 if not enrollment:
  return
 if enrollment.management_identities_at:
  # Run preflight toward Connected
  _finish_preflight(app, s, u, token, plan, enrollment, now)
  return

 token.status = 'finishing'
 provision = getattr(app.state, 'management_provisioner', provision_management_identities)
 try:
  evidence = provision(token.router_id, plan.snapshot, enrollment.expected_serial_digest)
 except (ManagementSetupError, RouterOSError) as e:
  token.status = 'failed'
  token.failure_code = getattr(e, 'code', 'management_setup_failed')
  token.failure_message = str(e)[:500]
  return
 enrollment.expected_identity_digest = evidence['identity_digest']
 enrollment.management_identities_at = now
 attempt = s.get(MagicConnectAttempt, token.attempt_id)
 if attempt:
  _event(s, attempt, 'system', 'management_identities_created', now=now)
 _finish_preflight(app, s, u, token, plan, enrollment, now)


def _finish_preflight(app, s, u, token, plan, enrollment, now):
 from .routeros_adapter import RouterOSClient, RouterOSError, discover_routeros, load_routeros_monitoring_credential
 from .enrollment import router_identity_digest
 from .hub_orchestrator import confirm_management_read
 from .models import RouterEvidence
 import hmac

 if plan.lifecycle_state not in ('verifying_management', 'connected') or not plan.handshake_verified_at:
  return
 if now - plan.handshake_verified_at > 180:
  return
 try:
  credential = load_routeros_monitoring_credential(token.router_id)
  with RouterOSClient(credential, router_id=token.router_id) as client:
   evidence = discover_routeros(client)
 except RouterOSError as e:
  token.failure_code = getattr(e, 'code', 'preflight_failed')
  token.failure_message = str(e)[:500]
  return
 observed = evidence.get('checked_at') or now
 expected = enrollment.expected_identity_digest
 actual = router_identity_digest(evidence.get('identity') or {})
 transport = evidence.get('transport') or {}
 identity_verified = bool(
  expected and actual and hmac.compare_digest(expected, actual)
  and credential.username == 'mm-monitor-' + token.router_id[:8]
  and transport.get('scheme') == 'https' and transport.get('tls_verified') is True
 )
 management_read = {
  'evidence_source': 'authenticated_routeros_read', 'authenticated': True,
  'identity_verified': identity_verified, 'tenant_id': token.tenant_id,
  'router_id': token.router_id, 'observed_at': observed,
 }
 evidence['preflight_stage'] = 'post_connection'
 evidence['management_read'] = management_read
 connection = confirm_management_read(plan, management_read, tenant_id=token.tenant_id, router_id=token.router_id, now=now)
 sync_enrollment_state(s, plan)
 s.add(RouterEvidence(
  tenant_id=token.tenant_id, router_id=token.router_id, kind='preflight',
  observed_at=observed, source=evidence.get('evidence_source', 'authenticated_routeros_read'),
  payload=evidence, created_by=token.owner_id, created=now,
 ))
 if connection.get('connection_verified'):
  token.status = 'connected'
  token.connected_at = now
  attempt = s.get(MagicConnectAttempt, token.attempt_id)
  if attempt:
   attempt.enrollment_state = 'connected'
   attempt.state_changed_at = now
   _event(s, attempt, 'system', 'one_paste_connected', now=now)
 else:
  token.status = 'finishing'
  token.failure_code = None
