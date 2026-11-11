"""Revision-aware own lesson completion and bounded learning requests."""
from pathlib import Path
from alembic import context,op
revision='0010_learning_progress'
down_revision='0009_read_scope'
branch_labels=None
depends_on=None


def retention():
    source=(Path(__file__).parent.parent/'auth0_oidc.sql').read_text()
    statement=next(s for s in source.split('\n-- statement\n') if s.startswith('CREATE OR REPLACE FUNCTION retain_auth_data'))
    return statement.replace('BEGIN\n',"BEGIN\n    DELETE FROM public.course_write_limits WHERE window_start<now()-interval '1 day';\n",1)


def upgrade():
    for s in (Path(__file__).parent.parent/'learning_progress.sql').read_text().split('\n-- statement\n'):op.execute(s)
    op.execute(retention().replace('BEGIN\n',"BEGIN\n    DELETE FROM public.learning_request_limits WHERE window_start<now()-interval '1 day';\n",1))


def downgrade():
    # Serialize the check with concurrent completion writes, including offline SQL.
    op.execute('LOCK TABLE lesson_progress IN ACCESS EXCLUSIVE MODE')
    if context.get_x_argument(as_dictionary=True).get('allow_progress_data_loss')!='yes':
        op.execute("DO $$ BEGIN IF EXISTS(SELECT 1 FROM lesson_progress) THEN RAISE EXCEPTION 'Downgrade would delete lesson progress; back up and pass -x allow_progress_data_loss=yes'; END IF; END $$")
    op.execute(retention())
    op.execute('DROP TABLE lesson_progress,learning_request_limits')
    op.execute('DROP TRIGGER lesson_revision_changed ON course_lessons')
    op.execute('DROP FUNCTION lesson_revision_changed()')
    op.execute('ALTER TABLE course_lessons DROP CONSTRAINT lesson_progress_parent, DROP COLUMN revision')
    op.execute('ALTER TABLE enrollments DROP CONSTRAINT enrollment_progress_owner')
