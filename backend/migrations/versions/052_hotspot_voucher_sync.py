"""HotSpot voucher sync: sealed voucher codes and per-router applied state."""
from alembic import op
import sqlalchemy as sa

revision = '052'
down_revision = '051'
branch_labels = None
depends_on = None


def upgrade():
    # Plain ADD COLUMN: a SQLite batch rebuild would drop the vouchers table's unnamed CHECK constraints.
    op.add_column('vouchers', sa.Column('code_sealed', sa.Text(), nullable=True))
    op.create_table(
        'hotspot_voucher_sync',
        sa.Column('voucher_id', sa.String(36), sa.ForeignKey('vouchers.id'), primary_key=True),
        sa.Column('router_id', sa.String(36), sa.ForeignKey('router_devices.id'), primary_key=True),
        sa.Column('tenant_id', sa.String(36), sa.ForeignKey('tenants.id'), nullable=False),
        sa.Column('applied', sa.String(10), nullable=True),
        sa.Column('applied_fingerprint', sa.String(64), nullable=True),
        sa.Column('applied_at', sa.BigInteger(), nullable=True),
        sa.Column('attempts', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('last_error', sa.String(60), nullable=True),
        sa.Column('last_attempt_at', sa.BigInteger(), nullable=True),
        sa.CheckConstraint("applied is null or applied in ('present','disabled','absent')", name='ck_hotspot_voucher_sync_applied'),
    )
    op.create_index('ix_hotspot_voucher_sync_router_id', 'hotspot_voucher_sync', ['router_id'])
    op.create_index('ix_hotspot_voucher_sync_tenant_id', 'hotspot_voucher_sync', ['tenant_id'])


def downgrade():
    bind = op.get_bind()
    if bind.execute(sa.text('SELECT count(*) FROM hotspot_voucher_sync')).scalar() or bind.execute(sa.text('SELECT count(*) FROM vouchers WHERE code_sealed IS NOT NULL')).scalar():
        raise RuntimeError('HotSpot sync records or sealed voucher codes exist; refusing to discard them')
    op.drop_index('ix_hotspot_voucher_sync_tenant_id', table_name='hotspot_voucher_sync')
    op.drop_index('ix_hotspot_voucher_sync_router_id', table_name='hotspot_voucher_sync')
    op.drop_table('hotspot_voucher_sync')
    op.drop_column('vouchers', 'code_sealed')
