"""Pre-provisioned Auth0 identities and server-side OIDC login flows."""
from pathlib import Path
from alembic import op

revision = "0004_auth0_oidc"
down_revision = "0003_security_review"
branch_labels = None
depends_on = None


def upgrade():
    source = Path(__file__).parent.parent / "auth0_oidc.sql"
    for statement in source.read_text().split("\n-- statement\n"):
        op.execute(statement)


def downgrade():
    # Remove OIDC sessions rather than turn them into trusted local sessions.
    op.execute("DELETE FROM sessions WHERE token_hash IN (SELECT token_hash FROM oidc_sessions)")
    prior = (Path(__file__).parent.parent / "security_review.sql").read_text()
    for statement in prior.split("\n-- statement\n"):
        if statement.startswith(("CREATE FUNCTION resolve_session", "CREATE FUNCTION tenant_admin", "CREATE FUNCTION retain_auth_data")):
            op.execute(statement.replace("CREATE FUNCTION", "CREATE OR REPLACE FUNCTION", 1))
    lifecycle = (Path(__file__).parent.parent / "auth_lifecycle.sql").read_text()
    for statement in lifecycle.split("\n-- statement\n"):
        if statement.startswith("CREATE FUNCTION reset_password"):
            op.execute(statement.replace("CREATE FUNCTION", "CREATE OR REPLACE FUNCTION", 1)
                       .replace("search_path=pg_catalog,public AS", "search_path=pg_catalog,public,pg_temp AS"))
    op.execute("DROP TABLE oidc_sessions, oidc_login_flows, oidc_identities")
