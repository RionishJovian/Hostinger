"""Per-router HotSpot session/accounting observation snapshots for step 6 reads."""
from alembic import op
import sqlalchemy as sa

revision = '054'
down_revision = '053'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'hotspot_session_observations',
        sa.Column('router_id', sa.String(36), sa.ForeignKey('router_devices.id'), primary_key=True),
        sa.Column('tenant_id', sa.String(36), sa.ForeignKey('tenants.id'), nullable=False),
        sa.Column('site_id', sa.String(36), sa.ForeignKey('sites.id'), nullable=False),
        sa.Column('observed_at', sa.BigInteger(), nullable=False),
        sa.Column('status', sa.String(24), nullable=False),
        sa.Column('active_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('guests', sa.JSON(), nullable=False),
        sa.Column('activations_applied', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('usage_updated', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('last_error', sa.String(60), nullable=True),
        sa.Column('updated', sa.BigInteger(), nullable=False),
        sa.CheckConstraint("status in ('verified','unable_to_verify')", name='ck_hotspot_session_obs_status'),
        sa.CheckConstraint('active_count >= 0', name='ck_hotspot_session_obs_count'),
    )
    op.create_index('ix_hotspot_session_observations_tenant_id', 'hotspot_session_observations', ['tenant_id'])
    op.create_index('ix_hotspot_session_observations_site_id', 'hotspot_session_observations', ['site_id'])


def downgrade():
    bind = op.get_bind()
    if bind.execute(sa.text('SELECT count(*) FROM hotspot_session_observations')).scalar():
        raise RuntimeError('HotSpot session observations exist; refusing to discard them')
    op.drop_index('ix_hotspot_session_observations_site_id', table_name='hotspot_session_observations')
    op.drop_index('ix_hotspot_session_observations_tenant_id', table_name='hotspot_session_observations')
    op.drop_table('hotspot_session_observations')
