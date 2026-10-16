"""Durable, explicitly scoped RouterOS acceptance evidence."""
from alembic import op,context
import sqlalchemy as sa
revision='026';down_revision='025';branch_labels=None;depends_on=None
def upgrade():
 op.create_table('router_evidence',sa.Column('id',sa.String(36),primary_key=True),sa.Column('tenant_id',sa.String(36),sa.ForeignKey('tenants.id'),nullable=False),sa.Column('router_id',sa.String(36),sa.ForeignKey('router_devices.id'),nullable=False),sa.Column('kind',sa.String(30),nullable=False),sa.Column('observed_at',sa.BigInteger(),nullable=False),sa.Column('source',sa.String(50),nullable=False),sa.Column('payload',sa.JSON(),nullable=False),sa.Column('created_by',sa.String(36),sa.ForeignKey('users.id'),nullable=False),sa.Column('created',sa.BigInteger(),nullable=False),sa.CheckConstraint("kind in ('preflight','wireguard_router_peer')"))
 op.create_index('ix_router_evidence_tenant_id','router_evidence',['tenant_id']);op.create_index('ix_router_evidence_router_id','router_evidence',['router_id'])
def downgrade():
 if context.is_offline_mode():raise RuntimeError('Router evidence downgrade requires preservation checks')
 if op.get_bind().execute(sa.text('SELECT count(*) FROM router_evidence')).scalar():raise RuntimeError('Router acceptance evidence exists; preserve it')
 op.drop_index('ix_router_evidence_router_id',table_name='router_evidence');op.drop_index('ix_router_evidence_tenant_id',table_name='router_evidence');op.drop_table('router_evidence')
