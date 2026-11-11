"""Persistent signed content validation; publish never starts parser work."""
from alembic import op
revision='0011_content_validation'
down_revision='0010_learning_progress'
branch_labels=None
depends_on=None


def upgrade():
    op.execute('ALTER TABLE course_lessons ADD COLUMN content_attestation text CHECK(length(content_attestation)<=1024)')
    op.execute('GRANT UPDATE(content_attestation) ON course_lessons TO maaher_runtime')
    op.execute("""CREATE FUNCTION invalidate_content_attestation() RETURNS trigger LANGUAGE plpgsql
      SET search_path=pg_catalog,public,pg_temp AS $$ BEGIN
      IF OLD.content IS DISTINCT FROM NEW.content OR OLD.resources IS DISTINCT FROM NEW.resources THEN NEW.content_attestation:=NULL; END IF;
      RETURN NEW; END $$""")
    op.execute('REVOKE ALL ON FUNCTION invalidate_content_attestation() FROM PUBLIC')
    op.execute('CREATE TRIGGER validation_content_changed BEFORE UPDATE OF content,resources ON course_lessons FOR EACH ROW EXECUTE FUNCTION invalidate_content_attestation()')


def downgrade():
    op.execute('DROP TRIGGER validation_content_changed ON course_lessons')
    op.execute('DROP FUNCTION invalidate_content_attestation()')
    op.execute('ALTER TABLE course_lessons DROP COLUMN content_attestation')
