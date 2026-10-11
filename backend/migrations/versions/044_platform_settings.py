"""Platform-wide settings owned by the platform owner, starting with subscription payment details."""
from alembic import op
import sqlalchemy as sa

revision = '044'
down_revision = '043'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'platform_settings',
        sa.Column('key', sa.String(80), primary_key=True),
        sa.Column('value', sa.JSON(), nullable=False),
        sa.Column('revision', sa.Integer(), nullable=False),
        sa.Column('updated', sa.BigInteger(), nullable=False),
        sa.Column('updated_by', sa.String(36), sa.ForeignKey('users.id'), nullable=False),
    )


def downgrade():
    if op.get_bind().scalar(sa.text('SELECT COUNT(*) FROM platform_settings')):
        raise RuntimeError('Refusing to downgrade: platform settings exist')
    op.drop_table('platform_settings')
