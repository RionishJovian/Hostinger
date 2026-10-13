"""Per-router WAN / PPPoE observation snapshots (read-only monitoring)."""
from alembic import op
import sqlalchemy as sa

revision = '061'
down_revision = '060'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'router_wan_observations',
        sa.Column('router_id', sa.String(36), sa.ForeignKey('router_devices.id'), primary_key=True),
        sa.Column('tenant_id', sa.String(36), sa.ForeignKey('tenants.id'), nullable=False),
        sa.Column('site_id', sa.String(36), sa.ForeignKey('sites.id'), nullable=False),
        sa.Column('observed_at', sa.BigInteger(), nullable=False),
        sa.Column('status', sa.String(24), nullable=False),
        sa.Column('metrics', sa.JSON(), nullable=False),
        sa.Column('last_error', sa.String(60), nullable=True),
        sa.Column('updated', sa.BigInteger(), nullable=False),
        sa.CheckConstraint("status in ('verified','unable_to_verify')", name='ck_router_wan_obs_status'),
    )
    op.create_index('ix_router_wan_observations_tenant_id', 'router_wan_observations', ['tenant_id'])
    op.create_index('ix_router_wan_observations_site_id', 'router_wan_observations', ['site_id'])


def downgrade():
    bind = op.get_bind()
    if bind.execute(sa.text('SELECT count(*) FROM router_wan_observations')).scalar():
        raise RuntimeError('Router WAN observations exist; refusing to discard them')
    op.drop_index('ix_router_wan_observations_site_id', table_name='router_wan_observations')
    op.drop_index('ix_router_wan_observations_tenant_id', table_name='router_wan_observations')
    op.drop_table('router_wan_observations')
