"""Record voucher code format and SME prefix; existing codes stay legacy and keep working."""
from alembic import op
import sqlalchemy as sa

revision = '035'
down_revision = '034'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('vouchers') as batch:
        batch.add_column(sa.Column('code_format', sa.String(16), nullable=False, server_default='legacy'))
        batch.add_column(sa.Column('code_prefix', sa.String(8), nullable=True))


def downgrade():
    with op.batch_alter_table('vouchers') as batch:
        batch.drop_column('code_prefix')
        batch.drop_column('code_format')
