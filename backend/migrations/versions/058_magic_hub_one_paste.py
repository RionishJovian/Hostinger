"""One-paste Magic Hub connect tokens and plan retirement archive for re-runs."""
from alembic import op
import sqlalchemy as sa

revision = '058'
down_revision = '057'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'magic_hub_connect_tokens',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('tenant_id', sa.String(36), sa.ForeignKey('tenants.id'), nullable=False),
        sa.Column('router_id', sa.String(36), sa.ForeignKey('router_devices.id'), nullable=False),
        sa.Column('owner_id', sa.String(36), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('attempt_id', sa.String(36), sa.ForeignKey('magic_connect_attempts.id'), nullable=False),
        sa.Column('token_hash', sa.String(64), nullable=False, unique=True),
        sa.Column('status', sa.String(32), nullable=False, server_default='waiting'),
        sa.Column('failure_code', sa.String(60), nullable=True),
        sa.Column('failure_message', sa.String(500), nullable=True),
        sa.Column('detection_facts', sa.JSON(), nullable=True),
        sa.Column('model_mismatch', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('version_mismatch', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('created', sa.BigInteger(), nullable=False),
        sa.Column('expires', sa.BigInteger(), nullable=False),
        sa.Column('consumed_at', sa.BigInteger(), nullable=True),
        sa.Column('peer_provisioned_at', sa.BigInteger(), nullable=True),
        sa.Column('management_applied_at', sa.BigInteger(), nullable=True),
        sa.Column('connected_at', sa.BigInteger(), nullable=True),
        sa.CheckConstraint(
            "status in ('waiting','reported','peer_added','awaiting_handshake',"
            "'management_applied','finishing','connected','failed','expired','revoked')",
            name='ck_magic_hub_connect_tokens_status',
        ),
        sa.CheckConstraint('expires > created', name='ck_magic_hub_connect_tokens_expires'),
    )
    op.create_index('ix_magic_hub_connect_tokens_tenant_id', 'magic_hub_connect_tokens', ['tenant_id'])
    op.create_index('ix_magic_hub_connect_tokens_router_id', 'magic_hub_connect_tokens', ['router_id'])
    op.create_index('ix_magic_hub_connect_tokens_attempt_id', 'magic_hub_connect_tokens', ['attempt_id'])

    op.create_table(
        'router_plan_retirements',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('tenant_id', sa.String(36), sa.ForeignKey('tenants.id'), nullable=False),
        sa.Column('router_id', sa.String(36), sa.ForeignKey('router_devices.id'), nullable=False),
        sa.Column('plan_id', sa.String(36), nullable=False),
        sa.Column('hub_id', sa.String(36), nullable=False),
        sa.Column('router_public_key', sa.String(44), nullable=False),
        sa.Column('address', sa.String(15), nullable=False),
        sa.Column('snapshot', sa.JSON(), nullable=False),
        sa.Column('lifecycle_state', sa.String(32), nullable=False),
        sa.Column('lock_reason', sa.String(500), nullable=True),
        sa.Column('attempt_id', sa.String(36), nullable=True),
        sa.Column('retired_by', sa.String(36), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('retired_at', sa.BigInteger(), nullable=False),
        sa.Column('reason', sa.String(500), nullable=False),
    )
    op.create_index('ix_router_plan_retirements_tenant_id', 'router_plan_retirements', ['tenant_id'])
    op.create_index('ix_router_plan_retirements_router_id', 'router_plan_retirements', ['router_id'])


def downgrade():
    bind = op.get_bind()
    if bind.execute(sa.text('SELECT count(*) FROM magic_hub_connect_tokens')).scalar():
        raise RuntimeError('Magic Hub connect tokens exist; refusing to discard enrollment evidence')
    if bind.execute(sa.text('SELECT count(*) FROM router_plan_retirements')).scalar():
        raise RuntimeError('Retired router plan archive exists; refusing to discard audit history')
    op.drop_index('ix_router_plan_retirements_router_id', table_name='router_plan_retirements')
    op.drop_index('ix_router_plan_retirements_tenant_id', table_name='router_plan_retirements')
    op.drop_table('router_plan_retirements')
    op.drop_index('ix_magic_hub_connect_tokens_attempt_id', table_name='magic_hub_connect_tokens')
    op.drop_index('ix_magic_hub_connect_tokens_router_id', table_name='magic_hub_connect_tokens')
    op.drop_index('ix_magic_hub_connect_tokens_tenant_id', table_name='magic_hub_connect_tokens')
    op.drop_table('magic_hub_connect_tokens')
