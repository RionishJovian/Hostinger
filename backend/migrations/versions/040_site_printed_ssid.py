"""Shop Settings: optional default Wi-Fi name printed on voucher cards."""
from alembic import op
import sqlalchemy as sa

revision = '040'
down_revision = '039'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('sites', sa.Column('printed_ssid', sa.String(32), nullable=True))


def downgrade():
    if op.get_bind().scalar(sa.text('SELECT COUNT(*) FROM sites WHERE printed_ssid IS NOT NULL')):
        raise RuntimeError('Refusing to downgrade: shops have a printed Wi-Fi name set')
    with op.batch_alter_table('sites') as batch:
        batch.drop_column('printed_ssid')
