"""Referral Agents: applications, SME attribution, commissions, payout wallets and withdrawals; refunded subscription invoices."""
from alembic import op
import sqlalchemy as sa

revision = '046'
down_revision = '045'
branch_labels = None
depends_on = None

ROLE_OLD = "role in ('platform','sme','guest')"
ROLE_NEW = "role in ('platform','sme','guest','agent')"
TENANT_OLD = "role = 'platform' OR tenant_id IS NOT NULL"
TENANT_NEW = "role in ('platform','agent') OR tenant_id IS NOT NULL"
STATUS_OLD = "status in ('unpaid','pending','needs_evidence','paid','rejected','void')"
STATUS_NEW = "status in ('unpaid','pending','needs_evidence','paid','rejected','void','refunded')"


def constraints(role, tenant, status):
    if op.get_bind().dialect.name == 'postgresql':
        for name in ('users_role_check', 'users_check'):
            op.drop_constraint(name, 'users', type_='check')
        op.create_check_constraint('users_role_check', 'users', role)
        op.create_check_constraint('users_check', 'users', tenant)
        op.drop_constraint('subscription_invoices_status_check', 'subscription_invoices', type_='check')
        op.create_check_constraint('subscription_invoices_status_check', 'subscription_invoices', status)
        return
    # SQLite batch rebuilds drop unnamed CHECK constraints, so every one is restated here.
    with op.batch_alter_table('users', recreate='always', table_args=[sa.CheckConstraint(role, name='users_role_check'), sa.CheckConstraint(tenant, name='users_check')]):
        pass
    with op.batch_alter_table('subscription_invoices', recreate='always', table_args=[sa.CheckConstraint('amount > 0'), sa.CheckConstraint('period_end > period_start'), sa.CheckConstraint(status, name='subscription_invoices_status_check')]):
        pass


def upgrade():
    constraints(ROLE_NEW, TENANT_NEW, STATUS_NEW)
    op.create_table(
        'agent_profiles',
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id'), primary_key=True),
        sa.Column('full_name', sa.String(160), nullable=False),
        sa.Column('phone', sa.String(40), nullable=False),
        sa.Column('note', sa.String(1000), nullable=True),
        sa.Column('status', sa.String(20), nullable=False),
        sa.Column('reason', sa.String(1000), nullable=True),
        sa.Column('revision', sa.Integer(), nullable=False),
        sa.Column('ledger_revision', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('applied', sa.BigInteger(), nullable=False),
        sa.Column('decided', sa.BigInteger(), nullable=True),
        sa.Column('decided_by', sa.String(36), sa.ForeignKey('users.id'), nullable=True),
        sa.CheckConstraint("status in ('pending','approved','rejected','suspended')", name='ck_agent_profiles_status'),
    )
    op.create_table(
        'agent_referrals',
        sa.Column('tenant_id', sa.String(36), sa.ForeignKey('tenants.id'), primary_key=True),
        sa.Column('agent_id', sa.String(36), sa.ForeignKey('users.id'), nullable=False, index=True),
        sa.Column('created', sa.BigInteger(), nullable=False),
    )
    op.create_table(
        'agent_commissions',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('agent_id', sa.String(36), sa.ForeignKey('users.id'), nullable=False, index=True),
        sa.Column('tenant_id', sa.String(36), sa.ForeignKey('tenants.id'), nullable=False),
        sa.Column('invoice_id', sa.String(36), sa.ForeignKey('subscription_invoices.id'), nullable=False, unique=True),
        sa.Column('months', sa.Integer(), nullable=False),
        sa.Column('rate_percent', sa.Integer(), nullable=False),
        sa.Column('base_amount', sa.BigInteger(), nullable=False),
        sa.Column('amount', sa.BigInteger(), nullable=False),
        sa.Column('currency', sa.String(3), nullable=False),
        sa.Column('state', sa.String(20), nullable=False),
        sa.Column('created', sa.BigInteger(), nullable=False),
        sa.Column('reversed_at', sa.BigInteger(), nullable=True),
        sa.Column('reversal_reason', sa.String(1000), nullable=True),
        sa.CheckConstraint("state in ('earned','reversed')", name='ck_agent_commissions_state'),
        sa.CheckConstraint('amount >= 0', name='ck_agent_commissions_amount'),
    )
    op.create_table(
        'agent_wallets',
        sa.Column('agent_id', sa.String(36), sa.ForeignKey('users.id'), primary_key=True),
        sa.Column('method', sa.String(20), primary_key=True),
        sa.Column('account_name', sa.String(160), nullable=False),
        sa.Column('account_number', sa.String(40), nullable=False),
        sa.Column('updated', sa.BigInteger(), nullable=False),
        sa.CheckConstraint("method in ('kbzpay','wavepay')", name='ck_agent_wallets_method'),
    )
    op.create_table(
        'agent_withdrawals',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('agent_id', sa.String(36), sa.ForeignKey('users.id'), nullable=False, index=True),
        sa.Column('amount', sa.BigInteger(), nullable=False),
        sa.Column('currency', sa.String(3), nullable=False),
        sa.Column('method', sa.String(20), nullable=False),
        sa.Column('wallet', sa.JSON(), nullable=False),
        sa.Column('status', sa.String(20), nullable=False),
        sa.Column('revision', sa.Integer(), nullable=False),
        sa.Column('reason', sa.String(1000), nullable=True),
        sa.Column('payout_reference', sa.String(160), nullable=True),
        sa.Column('request_key', sa.String(80), nullable=False),
        sa.Column('requested', sa.BigInteger(), nullable=False),
        sa.Column('decided', sa.BigInteger(), nullable=True),
        sa.Column('decided_by', sa.String(36), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('paid_at', sa.BigInteger(), nullable=True),
        sa.UniqueConstraint('agent_id', 'request_key', name='uq_agent_withdrawals_request'),
        sa.CheckConstraint('amount > 0', name='ck_agent_withdrawals_amount'),
        sa.CheckConstraint("method in ('kbzpay','wavepay')", name='ck_agent_withdrawals_method'),
        sa.CheckConstraint("status in ('requested','approved','rejected','paid','cancelled')", name='ck_agent_withdrawals_status'),
    )


def downgrade():
    bind = op.get_bind()
    for table in ('agent_profiles', 'agent_referrals', 'agent_commissions', 'agent_wallets', 'agent_withdrawals'):
        if bind.scalar(sa.text(f'SELECT COUNT(*) FROM {table}')):
            raise RuntimeError(f'Refusing to downgrade: {table} has rows')
    if bind.scalar(sa.text("SELECT COUNT(*) FROM users WHERE role = 'agent'")) or bind.scalar(sa.text("SELECT COUNT(*) FROM subscription_invoices WHERE status = 'refunded'")):
        raise RuntimeError('Refusing to downgrade: agent accounts or refunded invoices exist')
    for table in ('agent_withdrawals', 'agent_wallets', 'agent_commissions', 'agent_referrals', 'agent_profiles'):
        op.drop_table(table)
    constraints(ROLE_OLD, TENANT_OLD, STATUS_OLD)
