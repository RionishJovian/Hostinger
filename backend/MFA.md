# Frozen v1 MFA compatibility note

MFA login, enrollment, recovery-code APIs and UI are disabled in this corrective
copy. The historical `account_mfa` table, model, and migration 019 are retained;
this change does not drop or rewrite stored MFA structures. Future MFA work would
require reopening the frozen scope and explicit approval.
