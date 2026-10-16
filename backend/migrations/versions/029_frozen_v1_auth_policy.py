"""Per-session temporary-password gates and frozen-v1 login throttles."""
import hashlib,time
from alembic import op
import sqlalchemy as sa

revision='029'
down_revision='028'
branch_labels=None
depends_on=None

def upgrade():
 op.add_column('sessions',sa.Column('must_change_password',sa.Boolean(),nullable=False,server_default=sa.false()))
 op.execute(sa.text("""
  UPDATE sessions
  SET must_change_password=(SELECT users.must_change_password FROM users WHERE users.id=sessions.user_id)
 """))
 op.add_column('login_attempts',sa.Column('scope',sa.String(length=16),nullable=False,server_default='other'))
 op.add_column('login_attempts',sa.Column('locked_until',sa.BigInteger(),nullable=True))
 bind=op.get_bind()
 # Existing rows predate scope metadata. Start them as IP buckets, then identify
 # account and other per-user keys from the users table without storing raw keys.
 bind.execute(sa.text("UPDATE login_attempts SET scope='ip'"))
 users=bind.execute(sa.text('SELECT id, username FROM users')).mappings()
 for user in users:
  normalized=user['username'].strip().lower()
  account_key=hashlib.sha256(('account:'+normalized).encode()).hexdigest()
  bind.execute(sa.text("UPDATE login_attempts SET scope='account' WHERE key=:key"),{'key':account_key})
  for prefix in ('password-change:','voucher-attempt:','mfa-operation:'):
   other_key=hashlib.sha256((prefix+user['id']).encode()).hexdigest()
   bind.execute(sa.text("UPDATE login_attempts SET scope='other' WHERE key=:key"),{'key':other_key})
 # Revision 028 did not store bucket type. Unrecognized historical buckets remain
 # IP-derived; known per-user non-login buckets were marked above.
 # Preserve old IP counts as history, but never carry a low-threshold shared-IP lock forward.
 bind.execute(sa.text("UPDATE login_attempts SET locked_until=NULL WHERE scope='ip'"))
 now=int(time.time())
 bind.execute(sa.text("""
  UPDATE login_attempts
  SET failures=5, window_start=:now, locked_until=:locked_until
  WHERE scope='account' AND failures>=5
 """),{'now':now,'locked_until':now+300})

def downgrade():
 op.drop_column('login_attempts','locked_until')
 op.drop_column('login_attempts','scope')
 op.drop_column('sessions','must_change_password')
