"""Agent application location (owner decisions Q31–Q32): state/region, city, township and a map pin."""
from alembic import op
import sqlalchemy as sa

revision = '049'
down_revision = '048'
branch_labels = None
depends_on = None

COLUMNS = ('region', 'city', 'township', 'latitude', 'longitude')


def upgrade():
    for name in ('region', 'city', 'township'):
        op.add_column('agent_profiles', sa.Column(name, sa.String(80), nullable=True))
    for name in ('latitude', 'longitude'):
        op.add_column('agent_profiles', sa.Column(name, sa.Float(), nullable=True))


def downgrade():
    if op.get_bind().dialect.name == 'postgresql':
        for name in COLUMNS:
            op.drop_column('agent_profiles', name)
        return
    with op.batch_alter_table('agent_profiles', recreate='always') as batch:
        for name in COLUMNS:
            batch.drop_column(name)
