"""Identity, opaque sessions and fail-closed tenant policies.

The NOLOGIN group maaher_runtime must be provisioned before migration.
Only a separately provisioned LOGIN role should inherit this group.
"""
from pathlib import Path
from alembic import op

revision = "0001_identity"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    sql = (Path(__file__).parent.parent / "identity.sql").read_text()
    for statement in sql.split(";"):
        if statement.strip():
            op.execute(statement)


def downgrade():
    # Remove the cross-table policy dependency before dropping memberships.
    op.execute("DROP POLICY member_tenants ON tenants")
    for table in ("audit_events", "memberships", "sessions", "login_attempts", "tenants", "users"):
        op.execute(f"DROP TABLE {table}")
