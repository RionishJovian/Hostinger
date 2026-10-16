"""Allow Safe Change operation guest_vlan_external_ap."""
from alembic import op
import sqlalchemy as sa

revision = '057'
down_revision = '056'
branch_labels = None
depends_on = None

OPERATION_OLD = (
    "operation in ('wireguard_peer_keepalive','hotspot_portal_publish',"
    "'guest_wifi_settings','guest_network_addressing')"
)
OPERATION_NEW = (
    "operation in ('wireguard_peer_keepalive','hotspot_portal_publish',"
    "'guest_wifi_settings','guest_network_addressing','guest_vlan_external_ap')"
)
RISK = "risk in ('low','medium','high')"
STATUS = (
    "status in ('previewed','applying','verifying','applied','conflict',"
    "'rolling_back','rolled_back','failed','recovery_required')"
)
REVISION = 'revision > 0'
VLAN_OP = 'guest_vlan_external_ap'


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


def _sqlite_rebuild(operation):
    """Rebuild router_changes with exactly the intended CHECKs (no leftover ops)."""
    conn = op.get_bind()
    conn.execute(sa.text('PRAGMA foreign_keys=OFF'))
    conn.execute(sa.text('ALTER TABLE router_changes RENAME TO _router_changes_old'))
    conn.execute(sa.text(f'''
        CREATE TABLE router_changes (
            id VARCHAR(36) NOT NULL,
            tenant_id VARCHAR(36) NOT NULL,
            router_id VARCHAR(36) NOT NULL,
            operation VARCHAR(40) NOT NULL,
            resource_id VARCHAR(80) NOT NULL,
            risk VARCHAR(10) NOT NULL,
            status VARCHAR(24) NOT NULL,
            revision INTEGER NOT NULL,
            "before" JSON NOT NULL,
            desired JSON NOT NULL,
            actual JSON,
            diff JSON NOT NULL,
            before_fingerprint VARCHAR(64) NOT NULL,
            backup_id VARCHAR(36),
            safety_backup_verified BOOLEAN NOT NULL,
            confirmed_at BIGINT,
            created_by VARCHAR(36) NOT NULL,
            created BIGINT NOT NULL,
            updated BIGINT NOT NULL,
            error_code VARCHAR(60),
            expected JSON,
            gateway_deadline BIGINT,
            last_probe_at BIGINT,
            recovery_evidence JSON,
            conflict_detected_at BIGINT,
            conflict_history_until BIGINT,
            resolution_choice VARCHAR(24),
            rollback_attempted BOOLEAN NOT NULL,
            PRIMARY KEY (id),
            FOREIGN KEY(tenant_id) REFERENCES tenants (id),
            FOREIGN KEY(router_id) REFERENCES router_devices (id),
            FOREIGN KEY(backup_id) REFERENCES backup_artifacts (id),
            FOREIGN KEY(created_by) REFERENCES users (id),
            CONSTRAINT ck_router_changes_operation CHECK ({operation}),
            CONSTRAINT ck_router_changes_risk CHECK ({RISK}),
            CONSTRAINT ck_router_changes_status CHECK ({STATUS}),
            CONSTRAINT ck_router_changes_revision CHECK ({REVISION})
        )
    '''))
    cols = (
        'id,tenant_id,router_id,operation,resource_id,risk,status,revision,'
        '"before",desired,actual,diff,before_fingerprint,backup_id,safety_backup_verified,'
        'confirmed_at,created_by,created,updated,error_code,expected,gateway_deadline,'
        'last_probe_at,recovery_evidence,conflict_detected_at,conflict_history_until,'
        'resolution_choice,rollback_attempted'
    )
    conn.execute(sa.text(f'INSERT INTO router_changes ({cols}) SELECT {cols} FROM _router_changes_old'))
    conn.execute(sa.text('DROP TABLE _router_changes_old'))
    conn.execute(sa.text('CREATE INDEX IF NOT EXISTS ix_router_changes_tenant_id ON router_changes (tenant_id)'))
    conn.execute(sa.text('CREATE INDEX IF NOT EXISTS ix_router_changes_router_id ON router_changes (router_id)'))
    conn.execute(sa.text('PRAGMA foreign_keys=ON'))


def _constraints(operation):
    bind = op.get_bind()
    if bind.dialect.name == 'postgresql':
        _drop_operation_checks(bind)
        op.create_check_constraint('ck_router_changes_operation', 'router_changes', operation)
        return
    _sqlite_rebuild(operation)


def upgrade():
    _constraints(OPERATION_NEW)


def downgrade():
    bind = op.get_bind()
    if bind.execute(sa.text(f"SELECT count(*) FROM router_changes WHERE operation = '{VLAN_OP}'")).scalar():
        raise RuntimeError('Guest VLAN change history exists; refusing to discard it')
    _constraints(OPERATION_OLD)
