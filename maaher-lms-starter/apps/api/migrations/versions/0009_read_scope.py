"""Statement-scoped validated RLS reads; dedicated non-BYPASS read-only owner."""
from pathlib import Path
from alembic import op
revision='0009_read_scope'
down_revision='0008_enrollment'
branch_labels=None
depends_on=None


def old_write(table):
    return f"course_can_manage(tenant_id,course_id) AND EXISTS(SELECT 1 FROM courses c WHERE c.tenant_id={table}.tenant_id AND c.id={table}.course_id AND c.state='draft')"


def upgrade():
    for s in (Path(__file__).parent.parent/'read_scope.sql').read_text().split('\n-- statement\n'): op.execute(s)
    # FOR ALL policies also run on SELECT. Separate them so old expensive write
    # authorization cannot re-enter each row of a read query via a permissive OR.
    for table,prefix in [('course_modules','module'),('course_lessons','lesson')]:
        expr=old_write(table); op.execute(f'DROP POLICY {prefix}_write ON {table}')
        op.execute(f'CREATE POLICY {prefix}_insert ON {table} FOR INSERT TO maaher_runtime WITH CHECK({expr})')
        op.execute(f'CREATE POLICY {prefix}_update ON {table} FOR UPDATE TO maaher_runtime USING({expr}) WITH CHECK({expr})')
        op.execute(f'CREATE POLICY {prefix}_delete ON {table} FOR DELETE TO maaher_runtime USING({expr})')


def downgrade():
    source=(Path(__file__).parent.parent/'enrollment.sql').read_text().split('\n-- statement\n')
    for s in source:
        if s.startswith(('ALTER POLICY course_read','ALTER POLICY module_read','ALTER POLICY lesson_read')): op.execute(s)
    for name,table in [('cohort_read','cohorts'),('enrollment_read','enrollments')]:
        op.execute(f'DROP POLICY {name} ON {table}')
        op.execute(next(s for s in source if s.startswith(f'CREATE POLICY {name} ')))
    original=(Path(__file__).parent.parent/'courses.sql').read_text().split('\n-- statement\n')
    op.execute(next(s for s in original if s.startswith('CREATE POLICY assignment_read')).replace('CREATE POLICY','ALTER POLICY',1).replace(' FOR SELECT TO maaher_runtime',''))
    for table,prefix in [('course_modules','module'),('course_lessons','lesson')]:
        for action in ('insert','update','delete'): op.execute(f'DROP POLICY {prefix}_{action} ON {table}')
        expr=old_write(table);op.execute(f'CREATE POLICY {prefix}_write ON {table} FOR ALL TO maaher_runtime USING({expr}) WITH CHECK({expr})')
    for fn in ('access_student_enrollments','access_student_cohorts','access_course_ids','access_context'): op.execute(f'DROP FUNCTION {fn}()')
    for table in ('memberships','tenants','courses','courses_teachers','cohorts','enrollments'):
        op.execute(f'DROP POLICY access_reader ON {table}')
    for table,columns in [('memberships','tenant_id,user_id,role,status'),('tenants','id,status'),('courses','id,tenant_id,state'),('courses_teachers','tenant_id,course_id,user_id'),('cohorts','id,tenant_id,course_id,state'),('enrollments','id,tenant_id,course_id,cohort_id,student_id,status')]:
        op.execute(f'REVOKE SELECT({columns}) ON {table} FROM maaher_access_reader')
    op.execute('REVOKE EXECUTE ON FUNCTION runtime_identity() FROM maaher_access_reader')

    op.execute('REVOKE USAGE ON SCHEMA public FROM maaher_access_reader')
