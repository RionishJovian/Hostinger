"""Add one-time Magic Connect pairing state and isolated hub interface metadata."""
from alembic import op,context
import sqlalchemy as sa

revision='031'
down_revision='030'
branch_labels=None
depends_on=None

def upgrade():
 op.add_column('magic_hubs',sa.Column('interface_name',sa.String(15),nullable=True))
 op.add_column('router_plans',sa.Column('lifecycle_state',sa.String(32),nullable=False,server_default='awaiting_review'))
 op.add_column('router_plans',sa.Column('peer_operation_key',sa.String(80),nullable=True))
 op.create_index('uq_router_plans_peer_operation_key','router_plans',['peer_operation_key'],unique=True)
 op.add_column('router_plans',sa.Column('last_failure_code',sa.String(48),nullable=True))
 op.add_column('router_plans',sa.Column('handshake_verified_at',sa.BigInteger(),nullable=True))
 op.add_column('router_plans',sa.Column('management_read_verified_at',sa.BigInteger(),nullable=True))
 op.add_column('router_plans',sa.Column('management_lock_reason',sa.String(500),nullable=True))
 op.add_column('router_plans',sa.Column('management_locked_at',sa.BigInteger(),nullable=True))
 op.create_table(
  'magic_connect_attempts',
  sa.Column('id',sa.String(36),primary_key=True),
  sa.Column('tenant_id',sa.String(36),sa.ForeignKey('tenants.id'),nullable=False),
  sa.Column('site_id',sa.String(36),sa.ForeignKey('sites.id'),nullable=False),
  sa.Column('owner_id',sa.String(36),sa.ForeignKey('users.id'),nullable=False),
  sa.Column('router_name',sa.String(120),nullable=False),
  sa.Column('code_hash',sa.String(64),nullable=False,unique=True),
  sa.Column('comparison_code',sa.String(6),nullable=False),
  sa.Column('status',sa.String(24),nullable=False,server_default='pending'),
  sa.Column('technician_session_hash',sa.String(64),nullable=True,unique=True),
  sa.Column('technician_session_expires',sa.BigInteger(),nullable=True),
  sa.Column('created',sa.BigInteger(),nullable=False),
  sa.Column('expires',sa.BigInteger(),nullable=False),
  sa.Column('claimed_at',sa.BigInteger(),nullable=True),
  sa.Column('approved_at',sa.BigInteger(),nullable=True),
  sa.Column('denied_at',sa.BigInteger(),nullable=True),
  sa.Column('cancelled_at',sa.BigInteger(),nullable=True),
  sa.Column('enrollment_state',sa.String(32),nullable=False,server_default='pairing_pending'),
  sa.Column('failure_code',sa.String(48),nullable=True),
  sa.Column('state_changed_at',sa.BigInteger(),nullable=True),
  sa.CheckConstraint("status in ('pending','claimed','approved','denied','cancelled','expired')"),
  sa.CheckConstraint("enrollment_state in ('pairing_pending','pairing_approved','awaiting_bootstrap','awaiting_handshake','verifying_management','connected','failed_recovery_required','management_lock_pending','management_locked','revoked')"),
  sa.CheckConstraint('expires > created'),
 )
 op.create_index('ix_magic_connect_attempts_tenant_id','magic_connect_attempts',['tenant_id'])
 op.create_index('ix_magic_connect_attempts_site_id','magic_connect_attempts',['site_id'])
 op.create_table(
  'magic_connect_claim_rates',
  sa.Column('source_digest',sa.String(64),primary_key=True),
  sa.Column('window_started',sa.BigInteger(),nullable=False),
  sa.Column('attempts',sa.Integer(),nullable=False),
  sa.CheckConstraint('attempts >= 1'),
 )
 op.create_table(
  'magic_connect_events',
  sa.Column('id',sa.String(36),primary_key=True),
  sa.Column('tenant_id',sa.String(36),sa.ForeignKey('tenants.id'),nullable=False),
  sa.Column('attempt_id',sa.String(36),sa.ForeignKey('magic_connect_attempts.id'),nullable=False),
  sa.Column('actor_kind',sa.String(16),nullable=False),
  sa.Column('actor_id',sa.String(36),sa.ForeignKey('users.id'),nullable=True),
  sa.Column('event',sa.String(40),nullable=False),
  sa.Column('created',sa.BigInteger(),nullable=False),
  sa.CheckConstraint("actor_kind in ('owner','technician','system')"),
 )
 op.create_index('ix_magic_connect_events_tenant_id','magic_connect_events',['tenant_id'])
 op.create_index('ix_magic_connect_events_attempt_id','magic_connect_events',['attempt_id'])

def downgrade():
 if context.is_offline_mode():raise RuntimeError('Magic Connect downgrade requires online preservation checks')
 bind=op.get_bind()
 if bind.execute(sa.text('SELECT count(*) FROM magic_connect_attempts')).scalar():
  raise RuntimeError('Magic Connect attempts are audit/security evidence; preserve and roll forward')
 if bind.execute(sa.text('SELECT count(*) FROM router_plans')).scalar():
  raise RuntimeError('Router plans may contain Magic Hub lifecycle evidence; preserve and roll forward')
 op.drop_index('ix_magic_connect_events_attempt_id',table_name='magic_connect_events')
 op.drop_index('ix_magic_connect_events_tenant_id',table_name='magic_connect_events')
 op.drop_table('magic_connect_events')
 op.drop_table('magic_connect_claim_rates')
 op.drop_index('ix_magic_connect_attempts_site_id',table_name='magic_connect_attempts')
 op.drop_index('ix_magic_connect_attempts_tenant_id',table_name='magic_connect_attempts')
 op.drop_table('magic_connect_attempts')
 op.drop_index('uq_router_plans_peer_operation_key',table_name='router_plans')
 for column in ('management_locked_at','management_lock_reason','management_read_verified_at','handshake_verified_at','last_failure_code','peer_operation_key','lifecycle_state'):
  op.drop_column('router_plans',column)
 op.drop_column('magic_hubs','interface_name')
