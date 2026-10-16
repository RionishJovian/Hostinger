"""Add proposal-only HotSpot portal plans."""
from alembic import op, context
import sqlalchemy as sa

revision = '034'
down_revision = '033'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'hotspot_portal_plans',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('tenant_id', sa.String(36), sa.ForeignKey('tenants.id'), nullable=False),
        sa.Column('site_id', sa.String(36), sa.ForeignKey('sites.id'), nullable=False),
        sa.Column('router_id', sa.String(36), sa.ForeignKey('router_devices.id'), nullable=False),
        sa.Column('evidence_id', sa.String(36), sa.ForeignKey('router_evidence.id'), nullable=False),
        sa.Column('portal_package_id', sa.String(36), sa.ForeignKey('local_portal_packages.id'), nullable=False),
        sa.Column('selected_server_id', sa.String(80), nullable=False),
        sa.Column('selected_server_name', sa.String(120), nullable=False),
        sa.Column('selected_profile_name', sa.String(120), nullable=False),
        sa.Column('status', sa.String(20), nullable=False, server_default='prepared'),
        sa.Column('revision', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('before', sa.JSON(), nullable=False),
        sa.Column('desired', sa.JSON(), nullable=False),
        sa.Column('diff', sa.JSON(), nullable=False),
        sa.Column('impact', sa.JSON(), nullable=False),
        sa.Column('rollback', sa.JSON(), nullable=False),
        sa.Column('created_by', sa.String(36), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('created', sa.BigInteger(), nullable=False),
        sa.Column('reviewed_at', sa.BigInteger(), nullable=True),
        sa.CheckConstraint("status in ('prepared','reviewed')"),
        sa.CheckConstraint('revision > 0'),
        sa.UniqueConstraint('router_id', 'portal_package_id', 'selected_server_id'),
    )
    op.create_index('ix_hotspot_portal_plans_tenant_id', 'hotspot_portal_plans', ['tenant_id'])
    op.create_index('ix_hotspot_portal_plans_site_id', 'hotspot_portal_plans', ['site_id'])
    op.create_index('ix_hotspot_portal_plans_router_id', 'hotspot_portal_plans', ['router_id'])


def downgrade():
    if context.is_offline_mode() or op.get_bind().execute(sa.text('SELECT count(*) FROM hotspot_portal_plans')).scalar():
        raise RuntimeError('HotSpot owner-review evidence must be preserved; roll forward')
    op.drop_index('ix_hotspot_portal_plans_router_id', table_name='hotspot_portal_plans')
    op.drop_index('ix_hotspot_portal_plans_site_id', table_name='hotspot_portal_plans')
    op.drop_index('ix_hotspot_portal_plans_tenant_id', table_name='hotspot_portal_plans')
    op.drop_table('hotspot_portal_plans')
