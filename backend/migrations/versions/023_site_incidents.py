"""Site outage and incident history."""
from alembic import op,context
import sqlalchemy as sa
revision='023';down_revision='022';branch_labels=None;depends_on=None
def upgrade():
 op.create_table('site_incidents',sa.Column('id',sa.String(36),primary_key=True),sa.Column('tenant_id',sa.String(36),sa.ForeignKey('tenants.id'),nullable=False),sa.Column('site_id',sa.String(36),sa.ForeignKey('sites.id'),nullable=False),sa.Column('scope',sa.String(24),nullable=False),sa.Column('status',sa.String(16),nullable=False),sa.Column('started',sa.BigInteger(),nullable=False),sa.Column('ended',sa.BigInteger(),nullable=True),sa.Column('detection_source',sa.String(80),nullable=False),sa.Column('symptoms',sa.String(2000),nullable=False),sa.Column('suspected_root_cause',sa.String(1000),nullable=True),sa.Column('confirmed_root_cause',sa.String(1000),nullable=True),sa.Column('remediation',sa.String(2000),nullable=True),sa.Column('notes',sa.String(2000),nullable=False),sa.Column('created_by',sa.String(36),sa.ForeignKey('users.id'),nullable=False),sa.Column('created',sa.BigInteger(),nullable=False),sa.CheckConstraint("scope in ('control_plane','gateway','wan','switch','access_point','dns_portal','dependency')"),sa.CheckConstraint("status in ('open','resolved','unknown')"))
 op.create_index('ix_site_incidents_tenant_id','site_incidents',['tenant_id'])
def downgrade():
 if context.is_offline_mode():raise RuntimeError('Incident downgrade requires preservation checks')
 if op.get_bind().execute(sa.text('SELECT count(*) FROM site_incidents')).scalar():raise RuntimeError('Incident history exists; preserve outage records')
 op.drop_index('ix_site_incidents_tenant_id',table_name='site_incidents');op.drop_table('site_incidents')
