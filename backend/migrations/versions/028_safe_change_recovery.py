"""Durable gateway deadlines, recovery evidence and whole-version conflicts."""
from alembic import op,context
import sqlalchemy as sa
revision='028';down_revision='027';branch_labels=None;depends_on=None
def upgrade():
 for column in [sa.Column('expected',sa.JSON(),nullable=True),sa.Column('gateway_deadline',sa.BigInteger(),nullable=True),sa.Column('last_probe_at',sa.BigInteger(),nullable=True),sa.Column('recovery_evidence',sa.JSON(),nullable=True),sa.Column('conflict_detected_at',sa.BigInteger(),nullable=True),sa.Column('conflict_history_until',sa.BigInteger(),nullable=True),sa.Column('resolution_choice',sa.String(24),nullable=True),sa.Column('rollback_attempted',sa.Boolean(),nullable=False,server_default=sa.false())]:op.add_column('router_changes',column)
def downgrade():
 if context.is_offline_mode():raise RuntimeError('Safe-change recovery downgrade requires preservation checks')
 if op.get_bind().execute(sa.text("SELECT count(*) FROM router_changes WHERE gateway_deadline IS NOT NULL OR recovery_evidence IS NOT NULL OR conflict_detected_at IS NOT NULL OR resolution_choice IS NOT NULL OR rollback_attempted = 1")).scalar():raise RuntimeError('Router recovery/conflict history exists; preserve it')
 checks=(sa.CheckConstraint("operation='wireguard_peer_keepalive'",name='ck_router_changes_operation'),sa.CheckConstraint("risk in ('low','medium','high')",name='ck_router_changes_risk'),sa.CheckConstraint("status in ('previewed','applying','verifying','applied','conflict','rolling_back','rolled_back','failed','recovery_required')",name='ck_router_changes_status'),sa.CheckConstraint('revision > 0',name='ck_router_changes_revision'))
 with op.batch_alter_table('router_changes',table_args=checks) as batch:
  for name in ['rollback_attempted','resolution_choice','conflict_history_until','conflict_detected_at','recovery_evidence','last_probe_at','gateway_deadline','expected']:batch.drop_column(name)
