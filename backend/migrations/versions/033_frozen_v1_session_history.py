"""Collect privacy-minimized signed-in device and owner login history."""
from alembic import op
import sqlalchemy as sa

revision = '033'
down_revision = '032'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('sessions', sa.Column('login_at', sa.BigInteger(), nullable=True))
    op.add_column('sessions', sa.Column('last_active', sa.BigInteger(), nullable=True))
    op.add_column('sessions', sa.Column('device', sa.String(length=40), nullable=True))
    op.add_column('sessions', sa.Column('browser', sa.String(length=40), nullable=True))
    op.add_column('sessions', sa.Column('source', sa.String(length=64), nullable=True))
    op.create_table(
        'login_history',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('user_id', sa.String(length=36), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('tenant_id', sa.String(length=36), sa.ForeignKey('tenants.id'), nullable=True),
        sa.Column('outcome', sa.String(length=12), nullable=False),
        sa.Column('created', sa.BigInteger(), nullable=False),
        sa.Column('device', sa.String(length=40), nullable=False),
        sa.Column('browser', sa.String(length=40), nullable=False),
        sa.Column('source', sa.String(length=64), nullable=False),
        sa.CheckConstraint("outcome in ('success','failure')"),
    )
    op.create_index('ix_login_history_user_id', 'login_history', ['user_id'])
    op.create_index('ix_login_history_user_created', 'login_history', ['user_id', 'created'])


def downgrade():
    op.drop_index('ix_login_history_user_created', table_name='login_history')
    op.drop_index('ix_login_history_user_id', table_name='login_history')
    op.drop_table('login_history')
    op.drop_column('sessions', 'source')
    op.drop_column('sessions', 'browser')
    op.drop_column('sessions', 'device')
    op.drop_column('sessions', 'last_active')
    op.drop_column('sessions', 'login_at')
