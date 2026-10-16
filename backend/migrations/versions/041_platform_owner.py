"""Platform owner flag: unlocks the Platform console for the owner's own platform account."""
from alembic import op
import sqlalchemy as sa

revision = '041'
down_revision = '040'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('users', sa.Column('platform_owner', sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade():
    with op.batch_alter_table('users') as batch:
        batch.drop_column('platform_owner')
