"""Technician-guided router setup: link a pairing to a registered router and record the router's own WireGuard public key."""
from alembic import op
import sqlalchemy as sa

revision = '050'
down_revision = '049'
branch_labels = None
depends_on = None

TABLE = 'magic_connect_attempts'
KEY_INDEX = 'uq_magic_connect_attempts_router_public_key'
ROUTER_FK = 'fk_magic_connect_attempts_router_id'


def upgrade():
    # Plain ADD COLUMN: a SQLite batch rebuild would drop the table's unnamed CHECK constraints.
    op.add_column(TABLE, sa.Column('router_id', sa.String(36), nullable=True))
    op.add_column(TABLE, sa.Column('router_public_key', sa.String(44), nullable=True))
    op.add_column(TABLE, sa.Column('router_key_submitted_at', sa.BigInteger(), nullable=True))
    op.create_index(KEY_INDEX, TABLE, ['router_public_key'], unique=True)
    if op.get_bind().dialect.name != 'sqlite':
        op.create_foreign_key(ROUTER_FK, TABLE, 'router_devices', ['router_id'], ['id'])


def downgrade():
    bind = op.get_bind()
    if bind.execute(sa.text(f'SELECT count(*) FROM {TABLE} WHERE router_id IS NOT NULL OR router_public_key IS NOT NULL')).scalar():
        raise RuntimeError('Router setup records exist on Magic Connect pairings; refusing to discard them')
    if bind.dialect.name != 'sqlite':
        op.drop_constraint(ROUTER_FK, TABLE, type_='foreignkey')
    op.drop_index(KEY_INDEX, table_name=TABLE)
    for name in ('router_key_submitted_at', 'router_public_key', 'router_id'):
        op.drop_column(TABLE, name)
