"""Audited SME cash-close reconciliation records."""
from alembic import op,context
import sqlalchemy as sa
revision='020';down_revision='019';branch_labels=None;depends_on=None
def upgrade():
 op.create_table('revenue_reconciliations',sa.Column('id',sa.String(36),primary_key=True),sa.Column('tenant_id',sa.String(36),sa.ForeignKey('tenants.id'),nullable=False),sa.Column('site_id',sa.String(36),sa.ForeignKey('sites.id'),nullable=True),sa.Column('start_date',sa.String(10),nullable=True),sa.Column('end_date',sa.String(10),nullable=True),sa.Column('timezone',sa.String(80),nullable=False),sa.Column('expected_collections',sa.BigInteger(),nullable=False),sa.Column('expected_refunds',sa.BigInteger(),nullable=False),sa.Column('actual_collections',sa.BigInteger(),nullable=False),sa.Column('actual_refunds',sa.BigInteger(),nullable=False),sa.Column('variance',sa.BigInteger(),nullable=False),sa.Column('notes',sa.String(1000),nullable=False),sa.Column('request_key',sa.String(80),nullable=False),sa.Column('request_hash',sa.String(64),nullable=False),sa.Column('actor_id',sa.String(36),sa.ForeignKey('users.id'),nullable=False),sa.Column('created',sa.BigInteger(),nullable=False),sa.UniqueConstraint('tenant_id','request_key'),sa.CheckConstraint('expected_collections >= 0 AND expected_refunds >= 0'))
 op.create_index('ix_revenue_reconciliations_tenant_id','revenue_reconciliations',['tenant_id'])
def downgrade():
 if context.is_offline_mode():raise RuntimeError('Reconciliation downgrade requires preservation checks')
 if op.get_bind().execute(sa.text('SELECT count(*) FROM revenue_reconciliations')).scalar():raise RuntimeError('Reconciliation records exist; preserve cash-close history')
 op.drop_index('ix_revenue_reconciliations_tenant_id',table_name='revenue_reconciliations');op.drop_table('revenue_reconciliations')
