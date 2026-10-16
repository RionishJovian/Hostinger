"""Router-only HotSpot first-login activation and usage on vouchers (no entitlement)."""
from alembic import op
import sqlalchemy as sa

revision = '055'
down_revision = '054'
branch_labels = None
depends_on = None


def upgrade():
    # Plain ADD COLUMN: a SQLite batch rebuild would drop the vouchers table's unnamed CHECK constraints.
    op.add_column('vouchers', sa.Column('activated', sa.BigInteger(), nullable=True))
    op.add_column('vouchers', sa.Column('used_bytes', sa.BigInteger(), nullable=False, server_default='0'))
    op.add_column('vouchers', sa.Column('connected_seconds', sa.BigInteger(), nullable=False, server_default='0'))


def downgrade():
    bind = op.get_bind()
    if bind.execute(sa.text(
        'SELECT count(*) FROM vouchers WHERE activated IS NOT NULL OR used_bytes != 0 OR connected_seconds != 0'
    )).scalar():
        raise RuntimeError('Router voucher accounting exists; refusing to discard it')
    op.drop_column('vouchers', 'connected_seconds')
    op.drop_column('vouchers', 'used_bytes')
    op.drop_column('vouchers', 'activated')
