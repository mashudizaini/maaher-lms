"""Private grading history and explicitly released student snapshots."""
from pathlib import Path
from alembic import context,op
revision='0013_grading'
down_revision='0012_assignments'
branch_labels=None
depends_on=None


def upgrade():
    for statement in (Path(__file__).parent.parent/'grading.sql').read_text().split('\n-- statement\n'):
        op.execute(statement)


def downgrade():
    op.execute('LOCK TABLE grading_entries,grade_revisions,grade_publications,grading_events,grading_read_limits IN ACCESS EXCLUSIVE MODE')
    if context.get_x_argument(as_dictionary=True).get('allow_grading_data_loss')!='yes':
        op.execute("DO $$ BEGIN IF EXISTS(SELECT 1 FROM grading_entries) OR EXISTS(SELECT 1 FROM grading_events) THEN RAISE EXCEPTION 'Downgrade would delete grades and feedback; back up and pass -x allow_grading_data_loss=yes'; END IF; END $$")
    op.execute('ALTER TABLE grading_entries DROP CONSTRAINT grading_draft_revision, DROP CONSTRAINT grading_last_revision')
    op.execute('DROP TABLE grade_publications,grading_events,grade_revisions,grading_entries,grading_read_limits')
    for name,args in [('grading_authority','uuid,uuid,uuid'),('grading_entry_before',''),('grade_revision_before',''),('grade_revision_after',''),('grading_entry_after',''),('grade_publication_before',''),('grading_event_before',''),('immutable_grade_row','')]:
        op.execute(f'DROP FUNCTION {name}({args})')
    op.execute('ALTER TABLE submissions DROP CONSTRAINT grading_submission_parent')
