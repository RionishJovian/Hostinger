"""Staged firmware rollout plans."""
from alembic import op,context
import sqlalchemy as sa
revision='025';down_revision='024';branch_labels=None;depends_on=None
def upgrade():
 op.create_table('firmware_plans',sa.Column('id',sa.String(36),primary_key=True),sa.Column('tenant_id',sa.String(36),sa.ForeignKey('tenants.id'),nullable=False),sa.Column('site_id',sa.String(36),sa.ForeignKey('sites.id'),nullable=False),sa.Column('device_id',sa.String(36),nullable=False),sa.Column('current_version',sa.String(80),nullable=False),sa.Column('target_version',sa.String(80),nullable=False),sa.Column('minimum_safe_version',sa.String(80),nullable=False),sa.Column('window_start',sa.BigInteger(),nullable=False),sa.Column('window_end',sa.BigInteger(),nullable=False),sa.Column('status',sa.String(20),nullable=False),sa.Column('attempts',sa.Integer(),nullable=False),sa.Column('rollback_version',sa.String(80),nullable=True),sa.Column('notes',sa.String(1000),nullable=False),sa.Column('created_by',sa.String(36),sa.ForeignKey('users.id'),nullable=False),sa.Column('created',sa.BigInteger(),nullable=False),sa.CheckConstraint("status in ('scheduled','running','succeeded','partial','rolled_back','manual_recovery')"),sa.CheckConstraint('window_end >= window_start'),sa.CheckConstraint('attempts >= 0'))
 op.create_index('ix_firmware_plans_tenant_id','firmware_plans',['tenant_id'])
def downgrade():
 if context.is_offline_mode():raise RuntimeError('Firmware downgrade requires preservation checks')
 if op.get_bind().execute(sa.text('SELECT count(*) FROM firmware_plans')).scalar():raise RuntimeError('Firmware plans exist; preserve rollout history')
 op.drop_index('ix_firmware_plans_tenant_id',table_name='firmware_plans');op.drop_table('firmware_plans')
