"""Versioned assignments, private drafts and append-only submission snapshots."""
from pathlib import Path
from alembic import context,op
revision='0012_assignments'
down_revision='0011_content_validation'
branch_labels=None
depends_on=None


def upgrade():
    for statement in (Path(__file__).parent.parent/'assignments.sql').read_text().split('\n-- statement\n'):
        op.execute(statement)


def downgrade():
    op.execute('LOCK TABLE assignments,assignment_versions,submission_drafts,submissions IN ACCESS EXCLUSIVE MODE')
    if context.get_x_argument(as_dictionary=True).get('allow_assignment_data_loss')!='yes':
        op.execute("DO $$ BEGIN IF EXISTS(SELECT 1 FROM assignments) OR EXISTS(SELECT 1 FROM submissions) THEN RAISE EXCEPTION 'Downgrade would delete assignment history; back up and pass -x allow_assignment_data_loss=yes'; END IF; END $$")
    op.execute('ALTER TABLE assignments DROP CONSTRAINT assignment_draft_version, DROP CONSTRAINT assignment_published_version')
    op.execute('DROP TABLE submissions,submission_drafts,assignment_versions,assignments')
    for name in ('assignment_write_lock','immutable_assignment_row','draft_before_write','submission_before_insert','valid_rubric'):
        args='jsonb' if name=='valid_rubric' else ''
        op.execute(f'DROP FUNCTION {name}({args})')
