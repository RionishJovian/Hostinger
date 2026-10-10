"""Bind owner-approved pairing to a single reviewed enrollment plan."""
from alembic import op, context
import sqlalchemy as sa

revision = '032'
down_revision = '031'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'magic_connect_enrollments',
        sa.Column('plan_id', sa.String(36), sa.ForeignKey('router_plans.id'), primary_key=True),
        sa.Column('attempt_id', sa.String(36), sa.ForeignKey('magic_connect_attempts.id'), nullable=False, unique=True),
        sa.Column('tenant_id', sa.String(36), sa.ForeignKey('tenants.id'), nullable=False),
        sa.Column('site_id', sa.String(36), sa.ForeignKey('sites.id'), nullable=False),
        sa.Column('owner_id', sa.String(36), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('expected_identity_digest', sa.String(64), nullable=True),
        sa.Column('created', sa.BigInteger(), nullable=False),
        sa.Column('consumed_at', sa.BigInteger(), nullable=True),
        sa.Column('peer_provisioned_at', sa.BigInteger(), nullable=True),
    )
    op.create_index('ix_magic_connect_enrollments_tenant_id', 'magic_connect_enrollments', ['tenant_id'])


def downgrade():
    if context.is_offline_mode() or op.get_bind().execute(sa.text('SELECT count(*) FROM magic_connect_enrollments')).scalar():
        raise RuntimeError('Enrollment authorization is security evidence; preserve and roll forward')
    op.drop_index('ix_magic_connect_enrollments_tenant_id', table_name='magic_connect_enrollments')
    op.drop_table('magic_connect_enrollments')
