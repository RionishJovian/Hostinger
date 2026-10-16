"""Durable site-scoped offline voucher reconciliation events."""
from alembic import op,context
import sqlalchemy as sa
revision='022';down_revision='021';branch_labels=None;depends_on=None
def upgrade():
 op.create_table('offline_voucher_events',sa.Column('id',sa.String(36),primary_key=True),sa.Column('tenant_id',sa.String(36),sa.ForeignKey('tenants.id'),nullable=False),sa.Column('site_id',sa.String(36),sa.ForeignKey('sites.id'),nullable=False),sa.Column('event_key',sa.String(120),nullable=False),sa.Column('voucher_id',sa.String(36),sa.ForeignKey('vouchers.id'),nullable=True),sa.Column('code_hash',sa.String(64),nullable=False),sa.Column('event_type',sa.String(20),nullable=False),sa.Column('local_time',sa.BigInteger(),nullable=False),sa.Column('device_id',sa.String(120),nullable=False),sa.Column('status',sa.String(24),nullable=False),sa.Column('reason',sa.String(1000),nullable=True),sa.Column('created',sa.BigInteger(),nullable=False),sa.UniqueConstraint('tenant_id','event_key'),sa.CheckConstraint("event_type in ('redemption','usage')"),sa.CheckConstraint("status in ('pending_review','accepted','conflict')"))
 op.create_index('ix_offline_voucher_events_tenant_id','offline_voucher_events',['tenant_id'])
def downgrade():
 if context.is_offline_mode():raise RuntimeError('Offline voucher downgrade requires preservation checks')
 if op.get_bind().execute(sa.text('SELECT count(*) FROM offline_voucher_events')).scalar():raise RuntimeError('Offline voucher events exist; preserve reconciliation history')
 op.drop_index('ix_offline_voucher_events_tenant_id',table_name='offline_voucher_events');op.drop_table('offline_voucher_events')
