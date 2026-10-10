"""Voucher Disable / Re-enable / Delete-unused lifecycle with pending router synchronization."""
from alembic import op
import sqlalchemy as sa

revision = '036'
down_revision = '035'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('vouchers') as batch:
        batch.add_column(sa.Column('disabled_at', sa.BigInteger(), nullable=True))
        batch.add_column(sa.Column('disabled_reason', sa.String(1000), nullable=True))
        batch.add_column(sa.Column('deleted_at', sa.BigInteger(), nullable=True))
        batch.add_column(sa.Column('router_sync', sa.String(20), nullable=True))


def downgrade():
    bind = op.get_bind()
    if bind.execute(sa.text('SELECT COUNT(*) FROM vouchers WHERE disabled_at IS NOT NULL OR deleted_at IS NOT NULL')).scalar():
        raise RuntimeError('Disabled or deleted vouchers exist; downgrading would silently re-activate them')
    with op.batch_alter_table('vouchers') as batch:
        batch.drop_column('router_sync')
        batch.drop_column('deleted_at')
        batch.drop_column('disabled_reason')
        batch.drop_column('disabled_at')
