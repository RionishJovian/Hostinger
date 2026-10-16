"""Media Pass rules: featured catalogue titles and the per-business catalogue preview setting."""
from alembic import op
import sqlalchemy as sa

revision = '048'
down_revision = '047'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('media_titles', sa.Column('featured', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.create_table('media_settings',
        sa.Column('tenant_id', sa.String(36), sa.ForeignKey('tenants.id'), primary_key=True),
        sa.Column('catalog_preview', sa.String(12), nullable=False),
        sa.Column('revision', sa.Integer(), nullable=False),
        sa.Column('updated', sa.BigInteger(), nullable=False),
        sa.CheckConstraint("catalog_preview in ('full','featured')", name='ck_media_settings_preview'))


def downgrade():
    op.drop_table('media_settings')
    if op.get_bind().dialect.name == 'postgresql':
        op.drop_column('media_titles', 'featured')
        return
    with op.batch_alter_table('media_titles', recreate='always', table_args=[sa.CheckConstraint('runtime_minutes > 0'), sa.CheckConstraint('revision > 0')]) as batch:
        batch.drop_column('featured')
