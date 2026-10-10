"""Controlled RouterOS changes and encrypted backup integrity metadata."""
from alembic import op,context
import sqlalchemy as sa
revision='027';down_revision='026';branch_labels=None;depends_on=None
def upgrade():
 checks=(sa.CheckConstraint("kind in ('control_plane','router_export','device_config')",name='ck_backup_artifacts_kind'),sa.CheckConstraint("status in ('created','healthy','failed','expired')",name='ck_backup_artifacts_status'))
 with op.batch_alter_table('backup_artifacts',table_args=checks) as batch:
  batch.add_column(sa.Column('router_id',sa.String(36),sa.ForeignKey('router_devices.id',name='fk_backup_artifacts_router_id'),nullable=True))
  batch.add_column(sa.Column('integrity_verified',sa.Boolean(),nullable=False,server_default=sa.false()))
 op.create_index('ix_backup_artifacts_router_id','backup_artifacts',['router_id'])
 op.create_table('router_changes',sa.Column('id',sa.String(36),primary_key=True),sa.Column('tenant_id',sa.String(36),sa.ForeignKey('tenants.id'),nullable=False),sa.Column('router_id',sa.String(36),sa.ForeignKey('router_devices.id'),nullable=False),sa.Column('operation',sa.String(40),nullable=False),sa.Column('resource_id',sa.String(80),nullable=False),sa.Column('risk',sa.String(10),nullable=False),sa.Column('status',sa.String(24),nullable=False),sa.Column('revision',sa.Integer(),nullable=False),sa.Column('before',sa.JSON(),nullable=False),sa.Column('desired',sa.JSON(),nullable=False),sa.Column('actual',sa.JSON(),nullable=True),sa.Column('diff',sa.JSON(),nullable=False),sa.Column('before_fingerprint',sa.String(64),nullable=False),sa.Column('backup_id',sa.String(36),sa.ForeignKey('backup_artifacts.id'),nullable=True),sa.Column('safety_backup_verified',sa.Boolean(),nullable=False),sa.Column('confirmed_at',sa.BigInteger(),nullable=True),sa.Column('created_by',sa.String(36),sa.ForeignKey('users.id'),nullable=False),sa.Column('created',sa.BigInteger(),nullable=False),sa.Column('updated',sa.BigInteger(),nullable=False),sa.Column('error_code',sa.String(60),nullable=True),sa.CheckConstraint("operation='wireguard_peer_keepalive'"),sa.CheckConstraint("risk in ('low','medium','high')"),sa.CheckConstraint("status in ('previewed','applying','verifying','applied','conflict','rolling_back','rolled_back','failed','recovery_required')"),sa.CheckConstraint('revision > 0'))
 op.create_index('ix_router_changes_tenant_id','router_changes',['tenant_id']);op.create_index('ix_router_changes_router_id','router_changes',['router_id'])
def downgrade():
 if context.is_offline_mode():raise RuntimeError('Safe-change downgrade requires preservation checks')
 if op.get_bind().execute(sa.text('SELECT count(*) FROM router_changes')).scalar():raise RuntimeError('Router change history exists; preserve it')
 op.drop_index('ix_router_changes_router_id',table_name='router_changes');op.drop_index('ix_router_changes_tenant_id',table_name='router_changes');op.drop_table('router_changes')
 op.drop_index('ix_backup_artifacts_router_id',table_name='backup_artifacts')
 checks=(sa.CheckConstraint("kind in ('control_plane','router_export','device_config')",name='ck_backup_artifacts_kind'),sa.CheckConstraint("status in ('created','healthy','failed','expired')",name='ck_backup_artifacts_status'))
 with op.batch_alter_table('backup_artifacts',table_args=checks) as batch:
  batch.drop_column('integrity_verified');batch.drop_column('router_id')
