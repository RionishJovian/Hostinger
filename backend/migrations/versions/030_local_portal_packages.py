"""Store owner-published local HotSpot package artifacts by tenant/site revision."""
from alembic import op, context
import sqlalchemy as sa

revision = '030'
down_revision = '029'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'local_portal_packages',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('tenant_id', sa.String(length=36), sa.ForeignKey('tenants.id'), nullable=False),
        sa.Column('site_id', sa.String(length=36), sa.ForeignKey('sites.id'), nullable=True),
        sa.Column('scope_key', sa.String(length=120), nullable=False),
        sa.Column('published_revision', sa.Integer(), nullable=False),
        sa.Column('package_sha256', sa.String(length=64), nullable=False),
        sa.Column('package_bytes', sa.LargeBinary(), nullable=False),
        sa.Column('created', sa.BigInteger(), nullable=False),
        sa.UniqueConstraint('scope_key', 'published_revision', name='uq_local_portal_package_scope_revision'),
        sa.CheckConstraint('published_revision > 0', name='ck_local_portal_package_revision'),
    )
    op.create_index('ix_local_portal_packages_tenant_id', 'local_portal_packages', ['tenant_id'])
    op.create_index('ix_local_portal_packages_scope_key', 'local_portal_packages', ['scope_key'])


def downgrade():
    if context.is_offline_mode():
        raise RuntimeError('Local portal package downgrade requires preservation checks')
    if op.get_bind().execute(sa.text('SELECT count(*) FROM local_portal_packages')).scalar():
        raise RuntimeError('Local portal package artifacts exist; preserve them')
    op.drop_index('ix_local_portal_packages_scope_key', table_name='local_portal_packages')
    op.drop_index('ix_local_portal_packages_tenant_id', table_name='local_portal_packages')
    op.drop_table('local_portal_packages')
