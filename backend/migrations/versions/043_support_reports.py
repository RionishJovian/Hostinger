"""Magic Support Mode: stored, redacted diagnostic reports an owner can share with support."""
from alembic import op
import sqlalchemy as sa

revision = '043'
down_revision = '042'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'support_reports',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('tenant_id', sa.String(36), sa.ForeignKey('tenants.id'), nullable=False, index=True),
        sa.Column('site_id', sa.String(36), sa.ForeignKey('sites.id'), nullable=False, index=True),
        sa.Column('created', sa.BigInteger(), nullable=False),
        sa.Column('created_by', sa.String(36), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('report', sa.JSON(), nullable=False),
        sa.Column('shared_at', sa.BigInteger(), nullable=True),
        sa.Column('shared_by', sa.String(36), sa.ForeignKey('users.id'), nullable=True),
    )


def downgrade():
    if op.get_bind().scalar(sa.text('SELECT COUNT(*) FROM support_reports')):
        raise RuntimeError('Refusing to downgrade: support reports exist')
    op.drop_table('support_reports')
