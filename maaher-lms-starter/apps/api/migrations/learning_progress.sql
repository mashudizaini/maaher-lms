ALTER TABLE course_lessons ADD COLUMN revision integer NOT NULL DEFAULT 1 CHECK(revision>0);
-- statement
ALTER TABLE course_lessons ADD CONSTRAINT lesson_progress_parent UNIQUE(tenant_id,course_id,id);
-- statement
ALTER TABLE enrollments ADD CONSTRAINT enrollment_progress_owner UNIQUE(tenant_id,course_id,id,student_id);
-- statement
CREATE FUNCTION lesson_revision_changed() RETURNS trigger LANGUAGE plpgsql SET search_path=pg_catalog,public,pg_temp AS $$
BEGIN
 IF OLD.content IS DISTINCT FROM NEW.content OR OLD.resources IS DISTINCT FROM NEW.resources THEN NEW.revision:=OLD.revision+1; END IF;
 RETURN NEW;
END $$;
-- statement
CREATE TRIGGER lesson_revision_changed BEFORE UPDATE OF content,resources ON course_lessons
 FOR EACH ROW EXECUTE FUNCTION lesson_revision_changed();
-- statement
CREATE TABLE lesson_progress (
 tenant_id uuid NOT NULL, course_id uuid NOT NULL, enrollment_id uuid NOT NULL, student_id uuid NOT NULL,
 lesson_id uuid NOT NULL, lesson_revision integer NOT NULL CHECK(lesson_revision>0), completed_at timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY(enrollment_id,lesson_id),
 FOREIGN KEY(tenant_id,course_id,enrollment_id,student_id) REFERENCES enrollments(tenant_id,course_id,id,student_id),
 FOREIGN KEY(tenant_id,course_id,lesson_id) REFERENCES course_lessons(tenant_id,course_id,id) ON DELETE CASCADE
);
-- statement
CREATE INDEX progress_student_course ON lesson_progress(tenant_id,student_id,course_id);
-- statement
ALTER TABLE lesson_progress ENABLE ROW LEVEL SECURITY;
-- statement
ALTER TABLE lesson_progress FORCE ROW LEVEL SECURITY;
-- statement
CREATE POLICY own_progress_read ON lesson_progress FOR SELECT TO maaher_runtime USING(
 tenant_id::text=(SELECT access_context()->>'tenant') AND student_id=(SELECT (access_context()->>'user')::uuid)
 AND enrollment_id=ANY((SELECT access_student_enrollments())::uuid[]));
-- statement
CREATE POLICY own_progress_insert ON lesson_progress FOR INSERT TO maaher_runtime WITH CHECK(
 tenant_id::text=(SELECT access_context()->>'tenant') AND student_id=(SELECT (access_context()->>'user')::uuid)
 AND enrollment_id=ANY((SELECT access_student_enrollments())::uuid[])
 AND EXISTS(SELECT 1 FROM course_lessons l WHERE l.tenant_id=lesson_progress.tenant_id AND l.course_id=lesson_progress.course_id AND l.id=lesson_progress.lesson_id AND l.revision=lesson_progress.lesson_revision));
-- statement
CREATE POLICY own_progress_update ON lesson_progress FOR UPDATE TO maaher_runtime USING(
 tenant_id::text=(SELECT access_context()->>'tenant') AND student_id=(SELECT (access_context()->>'user')::uuid)
 AND enrollment_id=ANY((SELECT access_student_enrollments())::uuid[])) WITH CHECK(
 tenant_id::text=(SELECT access_context()->>'tenant') AND student_id=(SELECT (access_context()->>'user')::uuid)
 AND enrollment_id=ANY((SELECT access_student_enrollments())::uuid[])
 AND EXISTS(SELECT 1 FROM course_lessons l WHERE l.tenant_id=lesson_progress.tenant_id AND l.course_id=lesson_progress.course_id AND l.id=lesson_progress.lesson_id AND l.revision=lesson_progress.lesson_revision));
-- statement
CREATE POLICY own_progress_delete ON lesson_progress FOR DELETE TO maaher_runtime USING(
 tenant_id::text=(SELECT access_context()->>'tenant') AND student_id=(SELECT (access_context()->>'user')::uuid)
 AND enrollment_id=ANY((SELECT access_student_enrollments())::uuid[]));
-- statement
REVOKE ALL ON lesson_progress FROM PUBLIC,maaher_auth,maaher_definer,maaher_access_reader;
-- statement
GRANT SELECT,INSERT,DELETE ON lesson_progress TO maaher_runtime;
-- statement
GRANT UPDATE(lesson_revision,completed_at) ON lesson_progress TO maaher_runtime;
-- statement
CREATE TABLE learning_request_limits (
 tenant_id uuid NOT NULL, user_id uuid NOT NULL, attempts integer NOT NULL CHECK(attempts BETWEEN 1 AND 121),
 window_start timestamptz NOT NULL DEFAULT now(), PRIMARY KEY(tenant_id,user_id),
 FOREIGN KEY(tenant_id,user_id) REFERENCES memberships(tenant_id,user_id) ON DELETE CASCADE
);
-- statement
ALTER TABLE learning_request_limits ENABLE ROW LEVEL SECURITY;
-- statement
ALTER TABLE learning_request_limits FORCE ROW LEVEL SECURITY;
-- statement
CREATE POLICY own_learning_budget ON learning_request_limits TO maaher_runtime USING(
 tenant_id::text=(SELECT access_context()->>'tenant') AND user_id=(SELECT (access_context()->>'user')::uuid)
 AND (SELECT access_context()->>'role')='student') WITH CHECK(
 tenant_id::text=(SELECT access_context()->>'tenant') AND user_id=(SELECT (access_context()->>'user')::uuid)
 AND (SELECT access_context()->>'role')='student');
-- statement
REVOKE ALL ON learning_request_limits FROM PUBLIC,maaher_auth,maaher_access_reader;
-- statement
GRANT SELECT,INSERT,UPDATE ON learning_request_limits TO maaher_runtime;
-- statement
GRANT DELETE,SELECT(window_start) ON learning_request_limits TO maaher_definer;
