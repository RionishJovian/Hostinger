"""Owner-managed dealers, physical stock movements and the dealer settlement ledger."""
from alembic import op, context
import sqlalchemy as sa

revision = '038'
down_revision = '037'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'dealers',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('tenant_id', sa.String(36), sa.ForeignKey('tenants.id'), nullable=False),
        sa.Column('name', sa.String(120), nullable=False),
        sa.Column('location', sa.String(160), nullable=True),
        sa.Column('phone', sa.String(40), nullable=True),
        sa.Column('short_code', sa.String(6), nullable=True),
        sa.Column('settlement', sa.String(10), nullable=False),
        sa.Column('credit_limit', sa.BigInteger(), nullable=True),
        sa.Column('created_by', sa.String(36), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('created', sa.BigInteger(), nullable=False),
        sa.Column('archived_at', sa.BigInteger(), nullable=True),
        sa.CheckConstraint("settlement in ('prepaid','credit')", name='ck_dealers_settlement'),
        sa.CheckConstraint('credit_limit IS NULL OR credit_limit >= 0', name='ck_dealers_credit_limit'),
    )
    op.create_index('ix_dealers_tenant_id', 'dealers', ['tenant_id'])
    op.create_table(
        'dealer_movements',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('tenant_id', sa.String(36), sa.ForeignKey('tenants.id'), nullable=False),
        sa.Column('dealer_id', sa.String(36), sa.ForeignKey('dealers.id'), nullable=False),
        sa.Column('kind', sa.String(16), nullable=False),
        sa.Column('voucher_ids', sa.JSON(), nullable=False),
        sa.Column('count', sa.Integer(), nullable=False),
        sa.Column('unit_price', sa.BigInteger(), nullable=True),
        sa.Column('production_job_id', sa.String(36), sa.ForeignKey('voucher_production_jobs.id'), nullable=True),
        sa.Column('counterpart_dealer_id', sa.String(36), sa.ForeignKey('dealers.id'), nullable=True),
        sa.Column('reason', sa.String(24), nullable=True),
        sa.Column('note', sa.String(500), nullable=True),
        sa.Column('details', sa.JSON(), nullable=False),
        sa.Column('seq', sa.Integer(), nullable=False),
        sa.Column('request_key', sa.String(80), nullable=False),
        sa.Column('actor_id', sa.String(36), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('created', sa.BigInteger(), nullable=False),
        sa.UniqueConstraint('tenant_id', 'request_key', name='uq_dealer_movements_request'),
        sa.UniqueConstraint('dealer_id', 'seq', name='uq_dealer_movements_seq'),
        sa.CheckConstraint("kind in ('assign','return','reassign_out','reassign_in','stock_check')", name='ck_dealer_movements_kind'),
        sa.CheckConstraint("reason IS NULL OR reason in ('lost','damaged','counting_difference','other')", name='ck_dealer_movements_reason'),
    )
    op.create_index('ix_dealer_movements_tenant_id', 'dealer_movements', ['tenant_id'])
    op.create_index('ix_dealer_movements_dealer_id', 'dealer_movements', ['dealer_id'])
    op.create_table(
        'dealer_ledger',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('tenant_id', sa.String(36), sa.ForeignKey('tenants.id'), nullable=False),
        sa.Column('dealer_id', sa.String(36), sa.ForeignKey('dealers.id'), nullable=False),
        sa.Column('kind', sa.String(16), nullable=False),
        sa.Column('delta', sa.BigInteger(), nullable=False),
        sa.Column('method', sa.String(20), nullable=True),
        sa.Column('reference', sa.String(160), nullable=True),
        sa.Column('note', sa.String(500), nullable=True),
        sa.Column('movement_id', sa.String(36), sa.ForeignKey('dealer_movements.id'), nullable=True),
        sa.Column('reverses_id', sa.String(36), sa.ForeignKey('dealer_ledger.id'), nullable=True, unique=True),
        sa.Column('seq', sa.Integer(), nullable=False),
        sa.Column('request_key', sa.String(80), nullable=False),
        sa.Column('actor_id', sa.String(36), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('created', sa.BigInteger(), nullable=False),
        sa.UniqueConstraint('tenant_id', 'request_key', name='uq_dealer_ledger_request'),
        sa.UniqueConstraint('dealer_id', 'seq', name='uq_dealer_ledger_seq'),
        sa.CheckConstraint('delta <> 0', name='ck_dealer_ledger_delta'),
        sa.CheckConstraint("kind in ('charge','payment','return_credit','adjustment','reversal')", name='ck_dealer_ledger_kind'),
    )
    op.create_index('ix_dealer_ledger_tenant_id', 'dealer_ledger', ['tenant_id'])
    op.create_index('ix_dealer_ledger_dealer_id', 'dealer_ledger', ['dealer_id'])
    with op.batch_alter_table('vouchers') as batch:
        batch.add_column(sa.Column('dealer_id', sa.String(36), nullable=True))
        batch.add_column(sa.Column('dealer_price', sa.BigInteger(), nullable=True))
    # SQLite cannot add a foreign key without rebuilding the vouchers table; PostgreSQL enforces it.
    if op.get_bind().dialect.name != 'sqlite':
        op.create_foreign_key('fk_vouchers_dealer', 'vouchers', 'dealers', ['dealer_id'], ['id'])
    op.create_index('ix_vouchers_dealer_id', 'vouchers', ['dealer_id'])


def downgrade():
    bind = op.get_bind()
    if context.is_offline_mode() or bind.execute(sa.text('SELECT (SELECT count(*) FROM dealers) + (SELECT count(*) FROM dealer_movements) + (SELECT count(*) FROM dealer_ledger)')).scalar():
        raise RuntimeError('Dealer stock and settlement history must be preserved; roll forward')
    op.drop_index('ix_vouchers_dealer_id', table_name='vouchers')
    if bind.dialect.name != 'sqlite':
        op.drop_constraint('fk_vouchers_dealer', 'vouchers', type_='foreignkey')
    with op.batch_alter_table('vouchers') as batch:
        batch.drop_column('dealer_price')
        batch.drop_column('dealer_id')
    op.drop_index('ix_dealer_ledger_dealer_id', table_name='dealer_ledger')
    op.drop_index('ix_dealer_ledger_tenant_id', table_name='dealer_ledger')
    op.drop_table('dealer_ledger')
    op.drop_index('ix_dealer_movements_dealer_id', table_name='dealer_movements')
    op.drop_index('ix_dealer_movements_tenant_id', table_name='dealer_movements')
    op.drop_table('dealer_movements')
    op.drop_index('ix_dealers_tenant_id', table_name='dealers')
    op.drop_table('dealers')
