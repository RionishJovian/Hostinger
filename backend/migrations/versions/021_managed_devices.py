"""Site-scoped managed switch and access-point inventory."""
from alembic import op,context
import sqlalchemy as sa
revision='021';down_revision='020';branch_labels=None;depends_on=None
def upgrade():
 op.create_table('managed_devices',sa.Column('id',sa.String(36),primary_key=True),sa.Column('tenant_id',sa.String(36),sa.ForeignKey('tenants.id'),nullable=False),sa.Column('site_id',sa.String(36),sa.ForeignKey('sites.id'),nullable=False),sa.Column('kind',sa.String(20),nullable=False),sa.Column('name',sa.String(120),nullable=False),sa.Column('vendor',sa.String(120),nullable=False),sa.Column('model',sa.String(120),nullable=False),sa.Column('serial_or_mac',sa.String(120),nullable=True),sa.Column('location',sa.String(160),nullable=False),sa.Column('firmware',sa.String(80),nullable=False),sa.Column('image_asset',sa.String(400),nullable=True),sa.Column('created',sa.BigInteger(),nullable=False),sa.Column('last_seen',sa.BigInteger(),nullable=True),sa.UniqueConstraint('site_id','name'),sa.CheckConstraint("kind in ('switch','access_point')"))
 op.create_index('ix_managed_devices_tenant_id','managed_devices',['tenant_id'])
def downgrade():
 if context.is_offline_mode():raise RuntimeError('Managed-device downgrade requires preservation checks')
 if op.get_bind().execute(sa.text('SELECT count(*) FROM managed_devices')).scalar():raise RuntimeError('Managed devices exist; preserve inventory history')
 op.drop_index('ix_managed_devices_tenant_id',table_name='managed_devices');op.drop_table('managed_devices')
