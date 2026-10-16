"""Allow Safe Change operation hotspot_portal_publish alongside WireGuard keepalive."""
from alembic import op
import sqlalchemy as sa

revision = '053'
down_revision = '052'
branch_labels = None
depends_on = None

OPERATION_OLD = "operation='wireguard_peer_keepalive'"
OPERATION_NEW = "operation in ('wireguard_peer_keepalive','hotspot_portal_publish')"
RISK = "risk in ('low','medium','high')"
STATUS = "status in ('previewed','applying','verifying','applied','conflict','rolling_back','rolled_back','failed','recovery_required')"
REVISION = 'revision > 0'


def _drop_operation_checks(bind):
    if bind.dialect.name != 'postgresql':
        return
    rows = bind.execute(sa.text(
        "SELECT conname FROM pg_constraint "
        "WHERE conrelid = 'router_changes'::regclass AND contype = 'c' "
        "AND pg_get_constraintdef(oid) ILIKE '%operation%'"
    ))
    for (name,) in rows:
        op.drop_constraint(name, 'router_changes', type_='check')


def _constraints(operation):
    bind = op.get_bind()
    if bind.dialect.name == 'postgresql':
        _drop_operation_checks(bind)
        op.create_check_constraint('ck_router_changes_operation', 'router_changes', operation)
        return
    # SQLite batch rebuilds drop unnamed CHECKs from migration 027, so restate every one.
    with op.batch_alter_table(
        'router_changes',
        recreate='always',
        table_args=[
            sa.CheckConstraint(operation, name='ck_router_changes_operation'),
            sa.CheckConstraint(RISK, name='ck_router_changes_risk'),
            sa.CheckConstraint(STATUS, name='ck_router_changes_status'),
            sa.CheckConstraint(REVISION, name='ck_router_changes_revision'),
        ],
    ):
        pass


def upgrade():
    _constraints(OPERATION_NEW)


def downgrade():
    bind = op.get_bind()
    if bind.execute(sa.text("SELECT count(*) FROM router_changes WHERE operation='hotspot_portal_publish'")).scalar():
        raise RuntimeError('HotSpot portal publish change history exists; refusing to discard it')
    _constraints(OPERATION_OLD)
