"""Cohorts, explicit enrollment lifecycle and published student access."""
from pathlib import Path
from alembic import context,op

revision='0008_enrollment'
down_revision='0007_course_review'
branch_labels=None
depends_on=None


def upgrade():
    for statement in (Path(__file__).parent.parent/'enrollment.sql').read_text().split('\n-- statement\n'):
        op.execute(statement)


def downgrade():
    guard="""DO $$ BEGIN IF EXISTS(SELECT 1 FROM cohorts) OR EXISTS(SELECT 1 FROM enrollments) THEN
      RAISE EXCEPTION 'Downgrade would delete enrollment data; back up and pass -x allow_enrollment_data_loss=yes';
      END IF; END $$"""
    if context.get_x_argument(as_dictionary=True).get('allow_enrollment_data_loss')!='yes': op.execute(guard)
    op.execute("ALTER POLICY course_read ON courses USING(course_can_manage(tenant_id,id) AND (state<>'archived' OR course_member_role(tenant_id,runtime_identity())='admin'))")
    op.execute("ALTER POLICY module_read ON course_modules USING(course_can_manage(tenant_id,course_id) AND EXISTS(SELECT 1 FROM courses c WHERE c.tenant_id=course_modules.tenant_id AND c.id=course_modules.course_id))")
    op.execute("ALTER POLICY lesson_read ON course_lessons USING(course_can_manage(tenant_id,course_id) AND EXISTS(SELECT 1 FROM courses c WHERE c.tenant_id=course_lessons.tenant_id AND c.id=course_lessons.course_id))")
    for table,name in [('memberships','enrollment_membership_changed'),('users','enrollment_user_changed'),('courses','enrollment_course_archived'),('cohorts','enrollment_cohort_archived')]:
        op.execute(f'DROP TRIGGER {name} ON {table}')
    op.execute('DROP TABLE enrollments,cohorts')
    op.execute('DROP FUNCTION enrollment_guard(),enrollment_lock_student(uuid,uuid),course_student_access(uuid,uuid,uuid)')
    op.execute('REVOKE SELECT,UPDATE(version) ON courses FROM maaher_definer')
