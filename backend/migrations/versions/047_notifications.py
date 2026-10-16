"""Smart Notification Center: per-owner notification preferences and read markers."""
from alembic import op
import sqlalchemy as sa

revision = '047'
down_revision = '046'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('notification_preferences',
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id'), primary_key=True),
        sa.Column('tenant_id', sa.String(36), sa.ForeignKey('tenants.id'), nullable=False),
        sa.Column('level', sa.String(12), nullable=False),
        sa.Column('daily_summary', sa.String(12), nullable=False),
        sa.Column('revision', sa.Integer(), nullable=False),
        sa.Column('updated', sa.BigInteger(), nullable=False),
        sa.CheckConstraint("level in ('critical','attention','all')", name='ck_notification_preferences_level'),
        sa.CheckConstraint("daily_summary in ('daily','important','off')", name='ck_notification_preferences_summary'))
    op.create_index('ix_notification_preferences_tenant_id', 'notification_preferences', ['tenant_id'])
    op.create_table('notification_reads',
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id'), primary_key=True),
        sa.Column('key', sa.String(120), primary_key=True),
        sa.Column('version', sa.String(32), nullable=False),
        sa.Column('read_at', sa.BigInteger(), nullable=False))


def downgrade():
    op.drop_table('notification_reads')
    op.drop_index('ix_notification_preferences_tenant_id', table_name='notification_preferences')
    op.drop_table('notification_preferences')
