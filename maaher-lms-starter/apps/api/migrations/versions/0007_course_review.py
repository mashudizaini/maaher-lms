"""Course access revocation, archived visibility and authenticated write budget."""
from pathlib import Path
from alembic import op

revision = "0007_course_review"
down_revision = "0006_courses"
branch_labels = None
depends_on = None


def retention_statement():
    source = (Path(__file__).parent.parent / "auth0_oidc.sql").read_text()
    return next(s for s in source.split("\n-- statement\n") if s.startswith("CREATE OR REPLACE FUNCTION retain_auth_data"))


def upgrade():
    for statement in (Path(__file__).parent.parent / "course_review.sql").read_text().split("\n-- statement\n"):
        op.execute(statement)
    op.execute(retention_statement().replace("BEGIN\n", "BEGIN\n    DELETE FROM public.course_write_limits WHERE window_start<now()-interval '1 day';\n", 1))


def downgrade():
    op.execute(retention_statement())
    op.execute("DROP TRIGGER course_assignment_insert_guard ON courses_teachers")
    op.execute("DROP TRIGGER course_membership_changed ON memberships")
    op.execute("DROP TRIGGER course_user_status_changed ON users")
    op.execute("DROP FUNCTION course_assignment_guard()")
    op.execute("REVOKE SELECT,DELETE ON courses_teachers FROM maaher_definer")
    op.execute("ALTER POLICY course_read ON courses USING(course_can_manage(tenant_id,id))")
    op.execute("ALTER POLICY module_read ON course_modules USING(course_can_manage(tenant_id,course_id))")
    op.execute("ALTER POLICY lesson_read ON course_lessons USING(course_can_manage(tenant_id,course_id))")
    op.execute("DROP TABLE course_write_limits")
