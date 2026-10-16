"""Name-only router registration: nullable model/RouterOS; store script-reported facts."""
from alembic import op
import sqlalchemy as sa

revision = '059'
down_revision = '058'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('router_devices') as batch:
        batch.alter_column('model', existing_type=sa.String(120), nullable=True)
        batch.alter_column('reported_routeros', existing_type=sa.String(40), nullable=True)
        batch.add_column(sa.Column('architecture', sa.String(40), nullable=True))
        batch.add_column(sa.Column('reported_serial', sa.String(80), nullable=True))


def downgrade():
    bind = op.get_bind()
    if bind.dialect.name == 'postgresql':
        bind.execute(sa.text(
            "UPDATE router_devices SET model = COALESCE(model, ''), "
            "reported_routeros = COALESCE(reported_routeros, '')"
        ))
    else:
        bind.execute(sa.text(
            "UPDATE router_devices SET model = COALESCE(model, ''), "
            "reported_routeros = COALESCE(reported_routeros, '')"
        ))
    with op.batch_alter_table('router_devices') as batch:
        batch.drop_column('reported_serial')
        batch.drop_column('architecture')
        batch.alter_column('model', existing_type=sa.String(120), nullable=False)
        batch.alter_column('reported_routeros', existing_type=sa.String(40), nullable=False)
