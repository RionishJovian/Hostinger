"""Backup and restore verification metadata."""
from alembic import op,context
import sqlalchemy as sa
revision='024';down_revision='023';branch_labels=None;depends_on=None
def upgrade():
 op.create_table('backup_artifacts',sa.Column('id',sa.String(36),primary_key=True),sa.Column('tenant_id',sa.String(36),sa.ForeignKey('tenants.id'),nullable=False),sa.Column('site_id',sa.String(36),sa.ForeignKey('sites.id'),nullable=True),sa.Column('kind',sa.String(24),nullable=False),sa.Column('version',sa.String(80),nullable=False),sa.Column('checksum',sa.String(128),nullable=False),sa.Column('encrypted',sa.Boolean(),nullable=False),sa.Column('status',sa.String(16),nullable=False),sa.Column('restore_verified',sa.Boolean(),nullable=False),sa.Column('storage_ref',sa.String(400),nullable=False),sa.Column('created',sa.BigInteger(),nullable=False),sa.Column('retention_until',sa.BigInteger(),nullable=True),sa.CheckConstraint("kind in ('control_plane','router_export','device_config')"),sa.CheckConstraint("status in ('created','healthy','failed','expired')"))
 op.create_index('ix_backup_artifacts_tenant_id','backup_artifacts',['tenant_id'])
def downgrade():
 if context.is_offline_mode():raise RuntimeError('Backup downgrade requires preservation checks')
 if op.get_bind().execute(sa.text('SELECT count(*) FROM backup_artifacts')).scalar():raise RuntimeError('Backup records exist; preserve restore history')
 op.drop_index('ix_backup_artifacts_tenant_id',table_name='backup_artifacts');op.drop_table('backup_artifacts')
