"""Separate local synthetic TOTP assurance from the production FIDO2 policy."""
from pathlib import Path
from alembic import op

revision = "0005_dev_totp"
down_revision = "0004_auth0_oidc"
branch_labels = None
depends_on = None


def upgrade():
    source = Path(__file__).parent.parent / "auth0_dev_totp.sql"
    for statement in source.read_text().split("\n-- statement\n"):
        op.execute(statement)


def downgrade():
    # Never turn a dev session into a FIDO2 or local trusted session.
    op.execute("DELETE FROM sessions WHERE token_hash IN (SELECT token_hash FROM oidc_sessions WHERE assurance='maaher-dev-totp-v1')")
    op.execute("DELETE FROM oidc_login_flows")
    op.execute("ALTER TABLE oidc_sessions DROP CONSTRAINT oidc_sessions_dev_database_check")
    op.execute("ALTER TABLE oidc_sessions DROP CONSTRAINT oidc_sessions_assurance_check")
    op.execute("ALTER TABLE oidc_sessions ADD CONSTRAINT oidc_sessions_assurance_check CHECK (assurance='maaher-fido2-uv-v1')")
    prior = (Path(__file__).parent.parent / "auth0_oidc.sql").read_text()
    for statement in prior.split("\n-- statement\n"):
        if statement.startswith("CREATE OR REPLACE FUNCTION resolve_session"):
            op.execute(statement)
