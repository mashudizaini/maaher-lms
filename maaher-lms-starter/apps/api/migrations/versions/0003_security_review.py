"""Independent MFA authorization, isolated auth credentials and retention."""
from pathlib import Path
from alembic import op

revision = "0003_security_review"
down_revision = "0002_auth_lifecycle"
branch_labels = None
depends_on = None


def upgrade():
    source = Path(__file__).parent.parent / "security_review.sql"
    for statement in source.read_text().split("\n-- statement\n"):
        op.execute(statement)


def downgrade():
    source = Path(__file__).parent.parent / "security_review_rollback.sql"
    for statement in source.read_text().split("\n-- statement\n"):
        op.execute(statement)
    # Restore the previous version's functions only; never replay table creation.
    prior = (Path(__file__).parent.parent / "auth_lifecycle.sql").read_text()
    for statement in prior.split("\n-- statement\n"):
        if any(statement.startswith(prefix) for prefix in ("CREATE FUNCTION", "REVOKE ALL ON FUNCTION", "GRANT EXECUTE ON FUNCTION")):
            op.execute(statement)
