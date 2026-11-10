"""Tenant-isolated course authoring, assignments and lesson resources."""
from pathlib import Path
from alembic import context, op

revision = "0006_courses"
down_revision = "0005_dev_totp"
branch_labels = None
depends_on = None


def upgrade():
    for statement in (Path(__file__).parent.parent / "courses.sql").read_text().split("\n-- statement\n"):
        op.execute(statement)


def downgrade():
    populated = op.get_bind().exec_driver_sql('SELECT EXISTS(SELECT 1 FROM courses)').scalar()
    if populated and context.get_x_argument(as_dictionary=True).get('allow_course_data_loss') != 'yes':
        raise RuntimeError('Downgrade would delete course data; back up first and explicitly pass -x allow_course_data_loss=yes')
    op.execute("DROP TABLE course_lessons,course_modules,courses_teachers,courses")
    op.execute("DROP FUNCTION course_can_manage(uuid,uuid)")
    op.execute("DROP FUNCTION course_member_role(uuid,uuid)")
