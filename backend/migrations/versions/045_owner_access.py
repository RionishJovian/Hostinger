"""SME owner access state (active, suspended, disabled) and its reasoned history."""
from alembic import op
import sqlalchemy as sa

revision = '045'
down_revision = '044'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('users', sa.Column('access_state', sa.String(20), nullable=False, server_default='active'))
    op.add_column('users', sa.Column('access_reason', sa.String(1000), nullable=True))
    op.add_column('users', sa.Column('access_revision', sa.Integer(), nullable=False, server_default='0'))
    op.execute(sa.text("UPDATE users SET access_state = 'disabled' WHERE active = false"))
    op.create_table(
        'owner_access_events',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id'), nullable=False, index=True),
        sa.Column('actor_id', sa.String(36), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('revision', sa.Integer(), nullable=False),
        sa.Column('previous_state', sa.String(20), nullable=False),
        sa.Column('state', sa.String(20), nullable=False),
        sa.Column('reason', sa.String(1000), nullable=False),
        sa.Column('sessions_ended', sa.Integer(), nullable=False),
        sa.Column('created', sa.BigInteger(), nullable=False),
        sa.CheckConstraint("state in ('active','suspended','disabled')", name='ck_owner_access_events_state'),
        sa.UniqueConstraint('user_id', 'revision', name='uq_owner_access_events_revision'),
    )


def downgrade():
    if op.get_bind().scalar(sa.text('SELECT COUNT(*) FROM owner_access_events')):
        raise RuntimeError('Refusing to downgrade: owner access history exists')
    op.drop_table('owner_access_events')
    with op.batch_alter_table('users') as batch:
        batch.drop_column('access_revision')
        batch.drop_column('access_reason')
        batch.drop_column('access_state')
