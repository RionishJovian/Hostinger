"""Router management identities: the owner-confirmed serial digest and when MikroMagic created the monitoring and Safe Change logins."""
from alembic import op
import sqlalchemy as sa

revision = '051'
down_revision = '050'
branch_labels = None
depends_on = None

TABLE = 'magic_connect_enrollments'


def upgrade():
    # Plain ADD COLUMN: a SQLite batch rebuild would drop the table's unnamed CHECK constraints.
    op.add_column(TABLE, sa.Column('expected_serial_digest', sa.String(64), nullable=True))
    op.add_column(TABLE, sa.Column('management_identities_at', sa.BigInteger(), nullable=True))


def downgrade():
    bind = op.get_bind()
    if bind.execute(sa.text(f'SELECT count(*) FROM {TABLE} WHERE expected_serial_digest IS NOT NULL OR management_identities_at IS NOT NULL')).scalar():
        raise RuntimeError('Router management identity records exist; refusing to discard them')
    for name in ('management_identities_at', 'expected_serial_digest'):
        op.drop_column(TABLE, name)
