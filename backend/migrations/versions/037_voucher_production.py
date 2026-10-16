"""Voucher production jobs, saved templates, serial numbers and sheet identity."""
from alembic import op, context
import sqlalchemy as sa

revision = '037'
down_revision = '036'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'voucher_production_jobs',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('tenant_id', sa.String(36), sa.ForeignKey('tenants.id'), nullable=False),
        sa.Column('number', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(80), nullable=True),
        sa.Column('site_id', sa.String(36), sa.ForeignKey('sites.id'), nullable=True),
        sa.Column('package_id', sa.String(36), sa.ForeignKey('packages.id'), nullable=False),
        sa.Column('quantity', sa.Integer(), nullable=False),
        sa.Column('settings', sa.JSON(), nullable=False),
        sa.Column('status', sa.String(16), nullable=False, server_default='draft'),
        sa.Column('sheets', sa.JSON(), nullable=False),
        sa.Column('serial_start', sa.Integer(), nullable=True),
        sa.Column('serial_end', sa.Integer(), nullable=True),
        sa.Column('created_by', sa.String(36), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('created', sa.BigInteger(), nullable=False),
        sa.Column('generated_at', sa.BigInteger(), nullable=True),
        sa.Column('calibrated_at', sa.BigInteger(), nullable=True),
        sa.Column('verified_at', sa.BigInteger(), nullable=True),
        sa.Column('distributed_at', sa.BigInteger(), nullable=True),
        sa.Column('distributed_note', sa.String(200), nullable=True),
        sa.Column('cancelled_at', sa.BigInteger(), nullable=True),
        sa.UniqueConstraint('tenant_id', 'number', name='uq_voucher_jobs_tenant_number'),
        sa.CheckConstraint("status in ('draft','generated','verified','distributed','cancelled')", name='ck_voucher_jobs_status'),
        sa.CheckConstraint('quantity > 0', name='ck_voucher_jobs_quantity'),
    )
    op.create_index('ix_voucher_production_jobs_tenant_id', 'voucher_production_jobs', ['tenant_id'])
    op.create_table(
        'voucher_templates',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('tenant_id', sa.String(36), sa.ForeignKey('tenants.id'), nullable=False),
        sa.Column('name', sa.String(80), nullable=False),
        sa.Column('settings', sa.JSON(), nullable=False),
        sa.Column('created_by', sa.String(36), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('created', sa.BigInteger(), nullable=False),
        sa.Column('archived_at', sa.BigInteger(), nullable=True),
    )
    op.create_index('ix_voucher_templates_tenant_id', 'voucher_templates', ['tenant_id'])
    with op.batch_alter_table('vouchers') as batch:
        batch.add_column(sa.Column('serial_no', sa.Integer(), nullable=True))
        batch.add_column(sa.Column('production_job_id', sa.String(36), nullable=True))
        batch.add_column(sa.Column('sheet_no', sa.Integer(), nullable=True))
    # SQLite cannot add a foreign key without rebuilding the vouchers table; PostgreSQL enforces it.
    if op.get_bind().dialect.name != 'sqlite':
        op.create_foreign_key('fk_vouchers_production_job', 'vouchers', 'voucher_production_jobs', ['production_job_id'], ['id'])
    op.create_index('ix_vouchers_production_job_id', 'vouchers', ['production_job_id'])
    op.create_index('uq_vouchers_tenant_serial', 'vouchers', ['tenant_id', 'serial_no'], unique=True)


def downgrade():
    bind = op.get_bind()
    if context.is_offline_mode() or bind.execute(sa.text('SELECT (SELECT count(*) FROM voucher_production_jobs) + (SELECT count(*) FROM voucher_templates) + (SELECT count(*) FROM vouchers WHERE serial_no IS NOT NULL)')).scalar():
        raise RuntimeError('Voucher production history and serial numbers must be preserved; roll forward')
    op.drop_index('uq_vouchers_tenant_serial', table_name='vouchers')
    op.drop_index('ix_vouchers_production_job_id', table_name='vouchers')
    if bind.dialect.name != 'sqlite':
        op.drop_constraint('fk_vouchers_production_job', 'vouchers', type_='foreignkey')
    with op.batch_alter_table('vouchers') as batch:
        batch.drop_column('sheet_no')
        batch.drop_column('production_job_id')
        batch.drop_column('serial_no')
    op.drop_index('ix_voucher_templates_tenant_id', table_name='voucher_templates')
    op.drop_table('voucher_templates')
    op.drop_index('ix_voucher_production_jobs_tenant_id', table_name='voucher_production_jobs')
    op.drop_table('voucher_production_jobs')
