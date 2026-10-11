"""Shop business hours, network operating hours and planned maintenance windows."""
from alembic import op
import sqlalchemy as sa

revision = '042'
down_revision = '041'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('sites', sa.Column('business_hours', sa.JSON(), nullable=True))
    op.add_column('sites', sa.Column('network_hours_mode', sa.String(10), nullable=False, server_default='always'))
    op.add_column('sites', sa.Column('network_hours', sa.JSON(), nullable=True))
    op.add_column('site_incidents', sa.Column('expected_reason', sa.String(24), nullable=True))
    op.create_table(
        'site_maintenance',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('tenant_id', sa.String(36), sa.ForeignKey('tenants.id'), nullable=False, index=True),
        sa.Column('site_id', sa.String(36), sa.ForeignKey('sites.id'), nullable=False, index=True),
        sa.Column('reason', sa.String(300), nullable=False, server_default=''),
        sa.Column('started', sa.BigInteger(), nullable=False),
        sa.Column('planned_end', sa.BigInteger(), nullable=False),
        sa.Column('ended', sa.BigInteger(), nullable=True),
        sa.Column('extensions', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('post_check', sa.JSON(), nullable=True),
        sa.Column('created_by', sa.String(36), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('ended_by', sa.String(36), sa.ForeignKey('users.id'), nullable=True),
        sa.CheckConstraint('planned_end > started', name='ck_site_maintenance_window'),
        sa.CheckConstraint('ended IS NULL OR ended >= started', name='ck_site_maintenance_ended'),
        sa.CheckConstraint('extensions >= 0', name='ck_site_maintenance_extensions'),
    )


def downgrade():
    bind = op.get_bind()
    if bind.scalar(sa.text('SELECT COUNT(*) FROM site_maintenance')) or bind.scalar(sa.text('SELECT COUNT(*) FROM sites WHERE business_hours IS NOT NULL OR network_hours IS NOT NULL')):
        raise RuntimeError('Refusing to downgrade: shops have hours or maintenance history')
    op.drop_table('site_maintenance')
    with op.batch_alter_table('site_incidents') as batch:
        batch.drop_column('expected_reason')
    with op.batch_alter_table('sites') as batch:
        batch.drop_column('network_hours')
        batch.drop_column('network_hours_mode')
        batch.drop_column('business_hours')
