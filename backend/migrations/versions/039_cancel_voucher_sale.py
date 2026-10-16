"""Cancel Sale: keep cancelled counter sales as history and allow one active sale per voucher."""
from alembic import op, context
import sqlalchemy as sa

revision = '039'
down_revision = '038'
branch_labels = None
depends_on = None

NAMING = {'uq': 'uq_%(table_name)s_%(column_0_name)s', 'fk': 'fk_%(table_name)s_%(column_0_name)s'}
ACTIVE = sa.text('cancelled_at IS NULL')


def rebuild(sqlite):
    # SQLite rebuilds the table and would drop the original unnamed amount check.
    return {'recreate': 'always', 'naming_convention': NAMING, 'table_args': (sa.CheckConstraint('amount > 0'),)} if sqlite else {'naming_convention': NAMING}


def upgrade():
    bind = op.get_bind()
    sqlite = bind.dialect.name == 'sqlite'
    unique = [c['name'] for c in sa.inspect(bind).get_unique_constraints('voucher_sales') if c['column_names'] == ['voucher_id']]
    if len(unique) != 1:
        raise RuntimeError(f'Expected one unique constraint on voucher_sales.voucher_id, found {len(unique)}')
    with op.batch_alter_table('voucher_sales', **rebuild(sqlite)) as batch:
        batch.add_column(sa.Column('cancelled_at', sa.BigInteger(), nullable=True))
        batch.add_column(sa.Column('cancelled_by', sa.String(36), nullable=True))
        batch.add_column(sa.Column('cancel_reason', sa.String(500), nullable=True))
        batch.create_foreign_key('fk_voucher_sales_cancelled_by', 'users', ['cancelled_by'], ['id'])
        batch.drop_constraint(unique[0] or 'uq_voucher_sales_voucher_id', type_='unique')
    op.create_index('uq_voucher_sales_active_voucher', 'voucher_sales', ['voucher_id'], unique=True,
                    sqlite_where=ACTIVE, postgresql_where=ACTIVE)


def downgrade():
    bind = op.get_bind()
    if context.is_offline_mode() or bind.execute(sa.text('SELECT count(*) FROM voucher_sales WHERE cancelled_at IS NOT NULL')).scalar():
        raise RuntimeError('Cancelled voucher sales are accounting history; roll forward')
    sqlite = bind.dialect.name == 'sqlite'
    op.drop_index('uq_voucher_sales_active_voucher', table_name='voucher_sales')
    with op.batch_alter_table('voucher_sales', **rebuild(sqlite)) as batch:
        batch.drop_constraint('fk_voucher_sales_cancelled_by', type_='foreignkey')
        batch.drop_column('cancel_reason')
        batch.drop_column('cancelled_by')
        batch.drop_column('cancelled_at')
        batch.create_unique_constraint('uq_voucher_sales_voucher_id' if sqlite else 'voucher_sales_voucher_id_key', ['voucher_id'])
