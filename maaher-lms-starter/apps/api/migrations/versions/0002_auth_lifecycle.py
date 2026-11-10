"""One-use invitations/reset, encrypted MFA and durable email queue."""
from pathlib import Path
from alembic import op

revision = "0002_auth_lifecycle"
down_revision = "0001_identity"
branch_labels = None
depends_on = None


def upgrade():
    source = Path(__file__).parent.parent / "auth_lifecycle.sql"
    for statement in source.read_text().split("\n-- statement\n"):
        op.execute(statement)


def downgrade():
    for signature in ("accept_invitation(text,text,uuid)", "reset_password(text,text)",
                      "revoke_membership(uuid,uuid)"):
        op.execute(f"DROP FUNCTION {signature}")
    for table in ("auth_mail_outbox", "auth_events", "mfa_factors", "password_resets", "invitations"):
        op.execute(f"DROP TABLE {table}")
    op.execute("ALTER TABLE sessions DROP COLUMN mfa_verified")
    op.execute("ALTER TABLE audit_events DROP COLUMN target_type, DROP COLUMN target_id")
