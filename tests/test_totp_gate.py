import unittest

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from backend.models import AccountMFA, Base, User
from backend.totp_gate import DatabaseReplayGuard


class DatabaseReplayGuardTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine('sqlite:///:memory:')
        Base.metadata.create_all(self.engine)
        with Session(self.engine) as session:
            user = User(
                username='totp-owner@example.test',
                password_hash='test-hash',
                role='platform',
                active=True,
            )
            session.add(user)
            session.flush()
            session.add(AccountMFA(user_id=user.id, enabled=True, last_step=10, updated=0))
            session.commit()
            self.user_id = user.id

    def tearDown(self):
        self.engine.dispose()

    def test_consumes_steps_monotonically_and_rejects_replay(self):
        with Session(self.engine) as session:
            guard = DatabaseReplayGuard(session)
            self.assertTrue(guard.consume(self.user_id, 11))
            session.commit()
            self.assertFalse(guard.consume(self.user_id, 11))
            self.assertFalse(guard.consume(self.user_id, 10))
            self.assertTrue(guard.consume(self.user_id, 12))
            session.commit()
            row = session.scalar(select(AccountMFA).where(AccountMFA.user_id == self.user_id))
            self.assertEqual(row.last_step, 12)

    def test_requires_enabled_mfa_row_for_consumption(self):
        with Session(self.engine) as session:
            session.execute(
                AccountMFA.__table__.update()
                .where(AccountMFA.user_id == self.user_id)
                .values(enabled=False)
            )
            session.commit()
            self.assertFalse(DatabaseReplayGuard(session).consume(self.user_id, 11))


if __name__ == '__main__':
    unittest.main()
