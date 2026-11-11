CREATE FUNCTION valid_rubric(value jsonb) RETURNS boolean LANGUAGE plpgsql IMMUTABLE SET search_path=pg_catalog,public,pg_temp AS $$
DECLARE item jsonb; total numeric:=0;
BEGIN
 IF jsonb_typeof(value)<>'array' OR jsonb_array_length(value) NOT BETWEEN 1 AND 10 THEN RETURN false; END IF;
 FOR item IN SELECT * FROM jsonb_array_elements(value) LOOP
   IF jsonb_typeof(item)<>'object' OR NOT(item ? 'criterion' AND item ? 'max_points') OR (item-'criterion'-'max_points')<>'{}'::jsonb
      OR jsonb_typeof(item->'criterion')<>'string' OR length(btrim(item->>'criterion')) NOT BETWEEN 1 AND 200
      OR jsonb_typeof(item->'max_points')<>'number' OR (item->>'max_points') !~ '^[0-9]{1,3}$' THEN RETURN false; END IF;
   IF (item->>'max_points')::integer NOT BETWEEN 1 AND 100 THEN RETURN false; END IF;
   total:=total+(item->>'max_points')::integer;
 END LOOP;
 RETURN total=100;
END $$;
-- statement
REVOKE ALL ON FUNCTION valid_rubric(jsonb) FROM PUBLIC;
-- statement
GRANT EXECUTE ON FUNCTION valid_rubric(jsonb) TO maaher_runtime;
-- statement
CREATE TABLE assignments (
 id uuid PRIMARY KEY,tenant_id uuid NOT NULL,course_id uuid NOT NULL,lesson_id uuid NOT NULL,
 state text NOT NULL DEFAULT 'draft' CHECK(state IN ('draft','published','archived')),
 version integer NOT NULL DEFAULT 1 CHECK(version>0), draft_version_id uuid, published_version_id uuid,
 created_at timestamptz NOT NULL DEFAULT now(),updated_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE(tenant_id,course_id,id),
 FOREIGN KEY(tenant_id,course_id,lesson_id) REFERENCES course_lessons(tenant_id,course_id,id),
 CHECK(state<>'published' OR published_version_id IS NOT NULL)
);
-- statement
CREATE TABLE assignment_versions (
 id uuid PRIMARY KEY,tenant_id uuid NOT NULL,course_id uuid NOT NULL,assignment_id uuid NOT NULL,
 version_no integer NOT NULL CHECK(version_no BETWEEN 1 AND 100),title text NOT NULL CHECK(length(btrim(title)) BETWEEN 1 AND 160),
 instructions text NOT NULL CHECK(length(instructions) BETWEEN 1 AND 30000),
 language text NOT NULL CHECK(language IN ('python','javascript','text')),
 starter_code text NOT NULL DEFAULT '' CHECK(length(starter_code)<=30000),rubric jsonb NOT NULL CHECK(valid_rubric(rubric)),
 due_at timestamptz,max_attempts integer NOT NULL CHECK(max_attempts BETWEEN 1 AND 20),allow_late boolean NOT NULL,
 content_attestation text NOT NULL CHECK(length(content_attestation)<=1024),created_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE(tenant_id,course_id,assignment_id,id),UNIQUE(assignment_id,version_no),
 FOREIGN KEY(tenant_id,course_id,assignment_id) REFERENCES assignments(tenant_id,course_id,id)
);
-- statement
ALTER TABLE assignments ADD CONSTRAINT assignment_draft_version FOREIGN KEY(tenant_id,course_id,id,draft_version_id) REFERENCES assignment_versions(tenant_id,course_id,assignment_id,id);
-- statement
ALTER TABLE assignments ADD CONSTRAINT assignment_published_version FOREIGN KEY(tenant_id,course_id,id,published_version_id) REFERENCES assignment_versions(tenant_id,course_id,assignment_id,id);
-- statement
CREATE TABLE submission_drafts (
 tenant_id uuid NOT NULL,course_id uuid NOT NULL,assignment_id uuid NOT NULL,enrollment_id uuid NOT NULL,student_id uuid NOT NULL,
 version_id uuid NOT NULL,revision integer NOT NULL DEFAULT 1 CHECK(revision>0),
 source_code text NOT NULL DEFAULT '' CHECK(length(source_code)<=30000),note text NOT NULL DEFAULT '' CHECK(length(note)<=2000),
 updated_at timestamptz NOT NULL DEFAULT now(),PRIMARY KEY(assignment_id,enrollment_id),
 FOREIGN KEY(tenant_id,course_id,assignment_id,version_id) REFERENCES assignment_versions(tenant_id,course_id,assignment_id,id),
 FOREIGN KEY(tenant_id,course_id,enrollment_id,student_id) REFERENCES enrollments(tenant_id,course_id,id,student_id)
);
-- statement
CREATE TABLE submissions (
 id uuid PRIMARY KEY,tenant_id uuid NOT NULL,course_id uuid NOT NULL,assignment_id uuid NOT NULL,enrollment_id uuid NOT NULL,student_id uuid NOT NULL,
 version_id uuid NOT NULL,attempt_no integer NOT NULL CHECK(attempt_no BETWEEN 1 AND 20),draft_revision integer NOT NULL CHECK(draft_revision>0),request_id uuid NOT NULL,
 source_code text NOT NULL CHECK(length(source_code)<=30000),note text NOT NULL CHECK(length(note)<=2000),
 submitted_at timestamptz NOT NULL,status text NOT NULL CHECK(status IN ('submitted','late')),
 UNIQUE(assignment_id,enrollment_id,attempt_no),UNIQUE(assignment_id,enrollment_id,request_id),
 FOREIGN KEY(tenant_id,course_id,assignment_id,version_id) REFERENCES assignment_versions(tenant_id,course_id,assignment_id,id),
 FOREIGN KEY(tenant_id,course_id,enrollment_id,student_id) REFERENCES enrollments(tenant_id,course_id,id,student_id)
);
-- statement
CREATE INDEX assignments_course ON assignments(tenant_id,course_id,id);
-- statement
CREATE INDEX submissions_student ON submissions(tenant_id,student_id,course_id,id);
-- statement
CREATE INDEX submissions_version ON submissions(version_id,enrollment_id);
-- statement
CREATE INDEX drafts_version ON submission_drafts(version_id,enrollment_id);
-- statement
CREATE FUNCTION assignment_write_lock() RETURNS trigger LANGUAGE plpgsql SET search_path=pg_catalog,public,pg_temp AS $$
BEGIN
 PERFORM pg_advisory_xact_lock(hashtextextended('maaher-assignment:'||NEW.id::text,0));
 IF TG_OP='UPDATE' AND (NEW.id,NEW.tenant_id,NEW.course_id,NEW.lesson_id) IS DISTINCT FROM (OLD.id,OLD.tenant_id,OLD.course_id,OLD.lesson_id) THEN
  RAISE EXCEPTION 'Assignment parent is immutable' USING ERRCODE='23514';
 END IF;
 RETURN NEW;
END $$;
-- statement
CREATE TRIGGER assignment_write_lock BEFORE INSERT OR UPDATE ON assignments FOR EACH ROW EXECUTE FUNCTION assignment_write_lock();
-- statement
CREATE FUNCTION immutable_assignment_row() RETURNS trigger LANGUAGE plpgsql SET search_path=pg_catalog,public,pg_temp AS $$
BEGIN RAISE EXCEPTION 'Assignment versions and submissions are immutable' USING ERRCODE='23514'; END $$;
-- statement
CREATE TRIGGER immutable_version BEFORE UPDATE OR DELETE ON assignment_versions FOR EACH ROW EXECUTE FUNCTION immutable_assignment_row();
-- statement
CREATE TRIGGER immutable_submission BEFORE UPDATE OR DELETE ON submissions FOR EACH ROW EXECUTE FUNCTION immutable_assignment_row();
-- statement
CREATE FUNCTION draft_before_write() RETURNS trigger LANGUAGE plpgsql SET search_path=pg_catalog,public,pg_temp AS $$
DECLARE aid uuid;
BEGIN
 SELECT a.id INTO aid FROM public.assignments a WHERE a.tenant_id=NEW.tenant_id AND a.course_id=NEW.course_id AND a.id=NEW.assignment_id AND a.state='published' AND a.published_version_id=NEW.version_id;
 IF aid IS NULL OR NOT(NEW.enrollment_id=ANY(public.access_student_enrollments())) OR NEW.student_id IS DISTINCT FROM (public.access_context()->>'user')::uuid THEN
  RAISE EXCEPTION 'Current published assignment and own active enrollment required' USING ERRCODE='23514';
 END IF;
 IF TG_OP='UPDATE' THEN
  IF (NEW.tenant_id,NEW.course_id,NEW.assignment_id,NEW.enrollment_id,NEW.student_id) IS DISTINCT FROM (OLD.tenant_id,OLD.course_id,OLD.assignment_id,OLD.enrollment_id,OLD.student_id) THEN RAISE EXCEPTION 'Draft parent is immutable' USING ERRCODE='23514'; END IF;
  NEW.revision:=OLD.revision+1;
 ELSE NEW.revision:=1; END IF;
 NEW.updated_at:=clock_timestamp();RETURN NEW;
END $$;
-- statement
CREATE TRIGGER draft_before_write BEFORE INSERT OR UPDATE ON submission_drafts FOR EACH ROW EXECUTE FUNCTION draft_before_write();
-- statement
CREATE FUNCTION submission_before_insert() RETURNS trigger LANGUAGE plpgsql SET search_path=pg_catalog,public,pg_temp AS $$
DECLARE a public.assignments%ROWTYPE; v public.assignment_versions%ROWTYPE; d public.submission_drafts%ROWTYPE; attempts integer; submitted timestamptz;
BEGIN
 IF NEW.tenant_id::text IS DISTINCT FROM (public.access_context()->>'tenant') OR NEW.student_id IS DISTINCT FROM (public.access_context()->>'user')::uuid OR NOT(NEW.enrollment_id=ANY(public.access_student_enrollments())) THEN
  RAISE EXCEPTION 'Own active enrollment required' USING ERRCODE='23514';
 END IF;
 PERFORM pg_advisory_xact_lock(hashtextextended('maaher-assignment:'||NEW.assignment_id::text,0));
 PERFORM pg_advisory_xact_lock(hashtextextended('maaher-submit:'||NEW.assignment_id::text||':'||NEW.enrollment_id::text,0));
 SELECT * INTO a FROM public.assignments WHERE tenant_id=NEW.tenant_id AND course_id=NEW.course_id AND id=NEW.assignment_id AND state='published';
 IF a.id IS NULL OR a.published_version_id IS DISTINCT FROM NEW.version_id THEN RAISE EXCEPTION 'Published version changed' USING ERRCODE='23514'; END IF;
 SELECT * INTO v FROM public.assignment_versions WHERE id=NEW.version_id AND assignment_id=a.id;
 SELECT * INTO d FROM public.submission_drafts WHERE assignment_id=a.id AND enrollment_id=NEW.enrollment_id FOR UPDATE;
 IF d.version_id IS DISTINCT FROM v.id OR d.revision IS DISTINCT FROM NEW.draft_revision THEN RAISE EXCEPTION 'Save the current draft before submitting' USING ERRCODE='23514'; END IF;
 SELECT count(*) INTO attempts FROM public.submissions WHERE assignment_id=a.id AND enrollment_id=NEW.enrollment_id;
 submitted:=clock_timestamp();
 IF attempts>=v.max_attempts THEN RAISE EXCEPTION 'Attempt limit reached' USING ERRCODE='23514'; END IF;
 IF v.due_at IS NOT NULL AND submitted>v.due_at AND NOT v.allow_late THEN RAISE EXCEPTION 'Deadline passed' USING ERRCODE='23514'; END IF;
 NEW.attempt_no:=attempts+1;NEW.submitted_at:=submitted;
 NEW.status:=CASE WHEN v.due_at IS NOT NULL AND submitted>v.due_at THEN 'late' ELSE 'submitted' END;
 NEW.source_code:=d.source_code;NEW.note:=d.note;RETURN NEW;
END $$;
-- statement
CREATE TRIGGER submission_before_insert BEFORE INSERT ON submissions FOR EACH ROW EXECUTE FUNCTION submission_before_insert();
-- statement
REVOKE ALL ON FUNCTION assignment_write_lock(),immutable_assignment_row(),draft_before_write(),submission_before_insert() FROM PUBLIC;

-- statement
ALTER TABLE assignments ENABLE ROW LEVEL SECURITY;
-- statement
ALTER TABLE assignments FORCE ROW LEVEL SECURITY;
-- statement
REVOKE ALL ON assignments FROM PUBLIC,maaher_auth,maaher_definer,maaher_access_reader;
-- statement
GRANT SELECT,INSERT ON assignments TO maaher_runtime;
-- statement
CREATE POLICY task_read ON assignments FOR SELECT TO maaher_runtime USING(tenant_id::text=(SELECT access_context()->>'tenant') AND course_id=ANY((SELECT access_course_ids())::uuid[]) AND ((SELECT access_context()->>'role') IN ('admin','teacher') OR state='published'));
-- statement
CREATE POLICY task_insert ON assignments FOR INSERT TO maaher_runtime WITH CHECK(tenant_id::text=(SELECT access_context()->>'tenant') AND (SELECT access_context()->>'role') IN ('admin','teacher') AND course_id=ANY((SELECT access_course_ids())::uuid[]));
-- statement
CREATE POLICY task_update ON assignments FOR UPDATE TO maaher_runtime USING(tenant_id::text=(SELECT access_context()->>'tenant') AND (SELECT access_context()->>'role') IN ('admin','teacher') AND course_id=ANY((SELECT access_course_ids())::uuid[])) WITH CHECK(tenant_id::text=(SELECT access_context()->>'tenant') AND (SELECT access_context()->>'role') IN ('admin','teacher') AND course_id=ANY((SELECT access_course_ids())::uuid[]));
-- statement
ALTER TABLE assignment_versions ENABLE ROW LEVEL SECURITY;
-- statement
ALTER TABLE assignment_versions FORCE ROW LEVEL SECURITY;
-- statement
REVOKE ALL ON assignment_versions FROM PUBLIC,maaher_auth,maaher_definer,maaher_access_reader;
-- statement
GRANT SELECT,INSERT ON assignment_versions TO maaher_runtime;
-- statement
CREATE POLICY task_read ON assignment_versions FOR SELECT TO maaher_runtime USING(tenant_id::text=(SELECT access_context()->>'tenant') AND (((SELECT access_context()->>'role') IN ('admin','teacher') AND course_id=ANY((SELECT access_course_ids())::uuid[])) OR id IN (SELECT published_version_id FROM assignments WHERE state='published') OR id IN (SELECT version_id FROM submission_drafts) OR id IN (SELECT version_id FROM submissions)));
-- statement
CREATE POLICY task_insert ON assignment_versions FOR INSERT TO maaher_runtime WITH CHECK(tenant_id::text=(SELECT access_context()->>'tenant') AND (SELECT access_context()->>'role') IN ('admin','teacher') AND course_id=ANY((SELECT access_course_ids())::uuid[]));
-- statement
ALTER TABLE submission_drafts ENABLE ROW LEVEL SECURITY;
-- statement
ALTER TABLE submission_drafts FORCE ROW LEVEL SECURITY;
-- statement
REVOKE ALL ON submission_drafts FROM PUBLIC,maaher_auth,maaher_definer,maaher_access_reader;
-- statement
GRANT SELECT,INSERT ON submission_drafts TO maaher_runtime;
-- statement
CREATE POLICY task_read ON submission_drafts FOR SELECT TO maaher_runtime USING(tenant_id::text=(SELECT access_context()->>'tenant') AND student_id=(SELECT (access_context()->>'user')::uuid) AND enrollment_id=ANY((SELECT access_student_enrollments())::uuid[]));
-- statement
CREATE POLICY task_insert ON submission_drafts FOR INSERT TO maaher_runtime WITH CHECK(tenant_id::text=(SELECT access_context()->>'tenant') AND student_id=(SELECT (access_context()->>'user')::uuid) AND enrollment_id=ANY((SELECT access_student_enrollments())::uuid[]));
-- statement
CREATE POLICY task_update ON submission_drafts FOR UPDATE TO maaher_runtime USING(tenant_id::text=(SELECT access_context()->>'tenant') AND student_id=(SELECT (access_context()->>'user')::uuid) AND enrollment_id=ANY((SELECT access_student_enrollments())::uuid[])) WITH CHECK(tenant_id::text=(SELECT access_context()->>'tenant') AND student_id=(SELECT (access_context()->>'user')::uuid) AND enrollment_id=ANY((SELECT access_student_enrollments())::uuid[]));
-- statement
ALTER TABLE submissions ENABLE ROW LEVEL SECURITY;
-- statement
ALTER TABLE submissions FORCE ROW LEVEL SECURITY;
-- statement
REVOKE ALL ON submissions FROM PUBLIC,maaher_auth,maaher_definer,maaher_access_reader;
-- statement
GRANT SELECT,INSERT ON submissions TO maaher_runtime;
-- statement
CREATE POLICY task_read ON submissions FOR SELECT TO maaher_runtime USING(tenant_id::text=(SELECT access_context()->>'tenant') AND (((SELECT access_context()->>'role') IN ('admin','teacher') AND course_id=ANY((SELECT access_course_ids())::uuid[])) OR (student_id=(SELECT (access_context()->>'user')::uuid) AND enrollment_id=ANY((SELECT access_student_enrollments())::uuid[]))));
-- statement
CREATE POLICY task_insert ON submissions FOR INSERT TO maaher_runtime WITH CHECK(tenant_id::text=(SELECT access_context()->>'tenant') AND student_id=(SELECT (access_context()->>'user')::uuid) AND enrollment_id=ANY((SELECT access_student_enrollments())::uuid[]));
-- statement
GRANT UPDATE(state,version,draft_version_id,published_version_id,updated_at) ON assignments TO maaher_runtime;
-- statement
GRANT UPDATE(version_id,revision,source_code,note,updated_at) ON submission_drafts TO maaher_runtime;
