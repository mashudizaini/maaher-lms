ALTER TABLE submissions ADD CONSTRAINT grading_submission_parent UNIQUE(tenant_id,course_id,id);
-- statement
CREATE TABLE grading_entries (
 submission_id uuid PRIMARY KEY,tenant_id uuid NOT NULL,course_id uuid NOT NULL,
 version integer NOT NULL DEFAULT 0 CHECK(version BETWEEN 0 AND 300),draft_revision_id uuid,last_revision_id uuid,
 last_action text NOT NULL DEFAULT 'initial' CHECK(last_action IN ('initial','draft_saved','released','withdrawn')),
 last_reason text NOT NULL DEFAULT '' CHECK(length(last_reason)<=1000),last_actor_id uuid REFERENCES users(id),
 created_at timestamptz NOT NULL DEFAULT now(),updated_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE(tenant_id,course_id,submission_id),
 FOREIGN KEY(tenant_id,course_id,submission_id) REFERENCES submissions(tenant_id,course_id,id),
 CHECK((version=0 AND draft_revision_id IS NULL AND last_action='initial') OR (version>0 AND draft_revision_id IS NOT NULL AND last_action<>'initial'))
);
-- statement
CREATE TABLE grade_revisions (
 id uuid PRIMARY KEY,tenant_id uuid NOT NULL,course_id uuid NOT NULL,submission_id uuid NOT NULL,
 entry_version integer NOT NULL CHECK(entry_version BETWEEN 1 AND 300),revision_no integer NOT NULL CHECK(revision_no BETWEEN 1 AND 100),
 scores jsonb NOT NULL CHECK(jsonb_typeof(scores)='array' AND jsonb_array_length(scores) BETWEEN 1 AND 10),
 total integer NOT NULL CHECK(total BETWEEN 0 AND 100),feedback text NOT NULL DEFAULT '' CHECK(length(feedback)<=6000),
 reason text NOT NULL CHECK(length(btrim(reason)) BETWEEN 1 AND 1000),reviewer_id uuid NOT NULL REFERENCES users(id),
 created_at timestamptz NOT NULL DEFAULT now(),UNIQUE(submission_id,entry_version),UNIQUE(submission_id,revision_no),
 UNIQUE(tenant_id,course_id,submission_id,id),
 FOREIGN KEY(tenant_id,course_id,submission_id) REFERENCES grading_entries(tenant_id,course_id,submission_id)
);
-- statement
ALTER TABLE grading_entries ADD CONSTRAINT grading_draft_revision FOREIGN KEY(tenant_id,course_id,submission_id,draft_revision_id) REFERENCES grade_revisions(tenant_id,course_id,submission_id,id);
-- statement
ALTER TABLE grading_entries ADD CONSTRAINT grading_last_revision FOREIGN KEY(tenant_id,course_id,submission_id,last_revision_id) REFERENCES grade_revisions(tenant_id,course_id,submission_id,id);
-- statement
CREATE TABLE grade_publications (
 submission_id uuid PRIMARY KEY,tenant_id uuid NOT NULL,course_id uuid NOT NULL,version integer NOT NULL CHECK(version BETWEEN 1 AND 300),
 state text NOT NULL CHECK(state IN ('released','withdrawn')),revision_id uuid,
 revision_no integer,total integer,scores jsonb,feedback text,changed_at timestamptz NOT NULL DEFAULT now(),
 FOREIGN KEY(tenant_id,course_id,submission_id) REFERENCES grading_entries(tenant_id,course_id,submission_id),
 FOREIGN KEY(tenant_id,course_id,submission_id,revision_id) REFERENCES grade_revisions(tenant_id,course_id,submission_id,id),
 CHECK((state='withdrawn' AND revision_id IS NULL AND revision_no IS NULL AND total IS NULL AND scores IS NULL AND feedback IS NULL)
 OR (state='released' AND revision_id IS NOT NULL AND revision_no IS NOT NULL AND total IS NOT NULL AND total BETWEEN 0 AND 100 AND scores IS NOT NULL AND feedback IS NOT NULL))
);
-- statement
CREATE TABLE grading_events (
 id uuid PRIMARY KEY,tenant_id uuid NOT NULL,course_id uuid NOT NULL,submission_id uuid NOT NULL,
 version integer NOT NULL CHECK(version BETWEEN 1 AND 300),action text NOT NULL CHECK(action IN ('draft_saved','released','withdrawn')),
 revision_id uuid NOT NULL,reason text NOT NULL CHECK(length(btrim(reason)) BETWEEN 1 AND 1000),actor_id uuid NOT NULL REFERENCES users(id),
 created_at timestamptz NOT NULL DEFAULT now(),UNIQUE(submission_id,version),
 FOREIGN KEY(tenant_id,course_id,submission_id) REFERENCES grading_entries(tenant_id,course_id,submission_id),
 FOREIGN KEY(tenant_id,course_id,submission_id,revision_id) REFERENCES grade_revisions(tenant_id,course_id,submission_id,id)
);
-- statement
CREATE INDEX grading_entries_course ON grading_entries(tenant_id,course_id,submission_id);
-- statement
CREATE INDEX grade_publications_course ON grade_publications(tenant_id,course_id,submission_id);
-- statement
CREATE FUNCTION grading_authority(tid uuid,cid uuid,sid uuid) RETURNS boolean LANGUAGE plpgsql VOLATILE SET search_path=pg_catalog,public,pg_temp AS $$
BEGIN
 RETURN COALESCE(tid::text=(public.access_context()->>'tenant')
 AND (public.access_context()->>'role') IN ('admin','teacher') AND cid=ANY(public.access_course_ids())
 AND EXISTS(SELECT 1 FROM public.courses c WHERE c.tenant_id=tid AND c.id=cid AND c.state<>'archived')
 AND EXISTS(SELECT 1 FROM public.submissions s WHERE s.tenant_id=tid AND s.course_id=cid AND s.id=sid),false);
END $$;
-- statement
REVOKE ALL ON FUNCTION grading_authority(uuid,uuid,uuid) FROM PUBLIC;
-- statement
GRANT EXECUTE ON FUNCTION grading_authority(uuid,uuid,uuid) TO maaher_runtime;
-- statement
CREATE FUNCTION grading_entry_before() RETURNS trigger LANGUAGE plpgsql SET search_path=pg_catalog,public,pg_temp AS $$
DECLARE actor uuid; r public.grade_revisions%ROWTYPE; p public.grade_publications%ROWTYPE;
BEGIN
 IF NOT public.grading_authority(NEW.tenant_id,NEW.course_id,NEW.submission_id) THEN RAISE EXCEPTION 'Authorized active course required' USING ERRCODE='42501'; END IF;
 actor:=(public.access_context()->>'user')::uuid;
 IF TG_OP='INSERT' THEN
  IF NEW.version<>0 OR NEW.draft_revision_id IS NOT NULL OR NEW.last_revision_id IS NOT NULL OR NEW.last_action<>'initial' THEN RAISE EXCEPTION 'Invalid initial grading entry' USING ERRCODE='23514'; END IF;
  NEW.created_at:=clock_timestamp();NEW.last_actor_id:=NULL;NEW.last_reason:='';NEW.updated_at:=NEW.created_at;RETURN NEW;
 END IF;
 IF (NEW.tenant_id,NEW.course_id,NEW.submission_id,NEW.created_at) IS DISTINCT FROM (OLD.tenant_id,OLD.course_id,OLD.submission_id,OLD.created_at)
 OR NEW.version<>OLD.version+1 OR NEW.version>300 THEN RAISE EXCEPTION 'Grading version conflict' USING ERRCODE='23514'; END IF;
 SELECT * INTO p FROM public.grade_publications WHERE submission_id=OLD.submission_id;
 IF NEW.last_action='draft_saved' THEN
  SELECT * INTO r FROM public.grade_revisions WHERE id=NEW.draft_revision_id AND submission_id=NEW.submission_id AND entry_version=NEW.version;
  IF r.id IS NULL OR r.reviewer_id<>actor THEN RAISE EXCEPTION 'Fresh own grading revision required' USING ERRCODE='23514'; END IF;
  NEW.last_revision_id:=r.id;NEW.last_reason:=r.reason;
 ELSIF NEW.last_action='released' THEN
  IF OLD.draft_revision_id IS NULL OR NEW.draft_revision_id IS DISTINCT FROM OLD.draft_revision_id OR p.revision_id=OLD.draft_revision_id THEN RAISE EXCEPTION 'Current draft already released or missing' USING ERRCODE='23514'; END IF;
  IF p.state='released' AND length(btrim(NEW.last_reason))=0 THEN RAISE EXCEPTION 'Correction reason required' USING ERRCODE='23514'; END IF;
  NEW.last_reason:=COALESCE(NULLIF(btrim(NEW.last_reason),''),'Nilai dibagikan');NEW.last_revision_id:=OLD.draft_revision_id;
 ELSIF NEW.last_action='withdrawn' THEN
  IF p.state IS DISTINCT FROM 'released' OR NEW.draft_revision_id IS DISTINCT FROM OLD.draft_revision_id OR length(btrim(NEW.last_reason))=0 THEN RAISE EXCEPTION 'Released grade and withdrawal reason required' USING ERRCODE='23514'; END IF;
  NEW.last_reason:=btrim(NEW.last_reason);NEW.last_revision_id:=p.revision_id;
 ELSE RAISE EXCEPTION 'Invalid grading action' USING ERRCODE='23514'; END IF;
 NEW.last_actor_id:=actor;NEW.updated_at:=clock_timestamp();RETURN NEW;
END $$;
-- statement
CREATE TRIGGER grading_entry_before BEFORE INSERT OR UPDATE ON grading_entries FOR EACH ROW EXECUTE FUNCTION grading_entry_before();
-- statement
CREATE FUNCTION grade_revision_before() RETURNS trigger LANGUAGE plpgsql SET search_path=pg_catalog,public,pg_temp AS $$
DECLARE g public.grading_entries%ROWTYPE; rubric jsonb; item jsonb; result jsonb:='[]'; total_points integer:=0; idx integer:=0; pts integer;
BEGIN
 IF NOT public.grading_authority(NEW.tenant_id,NEW.course_id,NEW.submission_id) THEN RAISE EXCEPTION 'Authorized grading scope required' USING ERRCODE='42501'; END IF;
 SELECT * INTO g FROM public.grading_entries WHERE tenant_id=NEW.tenant_id AND course_id=NEW.course_id AND submission_id=NEW.submission_id FOR UPDATE;
 IF NOT public.grading_authority(NEW.tenant_id,NEW.course_id,NEW.submission_id) THEN RAISE EXCEPTION 'Grading authority changed while waiting' USING ERRCODE='42501'; END IF;
 IF g.submission_id IS NULL OR NEW.entry_version<>g.version+1 OR g.version>=300 THEN RAISE EXCEPTION 'Grading version conflict' USING ERRCODE='23514'; END IF;
 SELECT a.rubric INTO rubric FROM public.submissions s JOIN public.assignment_versions a ON a.tenant_id=s.tenant_id AND a.course_id=s.course_id AND a.assignment_id=s.assignment_id AND a.id=s.version_id WHERE s.tenant_id=NEW.tenant_id AND s.id=NEW.submission_id;
 IF rubric IS NULL OR jsonb_typeof(NEW.scores)<>'array' OR jsonb_array_length(NEW.scores)<>jsonb_array_length(rubric) THEN RAISE EXCEPTION 'Original submission rubric required' USING ERRCODE='23514'; END IF;
 FOR item IN SELECT * FROM jsonb_array_elements(NEW.scores) LOOP
  IF jsonb_typeof(item)<>'object' OR NOT(item ? 'criterion_index' AND item ? 'points') OR (item-'criterion_index'-'points'-'comment')<>'{}'
   OR jsonb_typeof(item->'criterion_index')<>'number' OR (item->>'criterion_index')<>idx::text
   OR jsonb_typeof(item->'points')<>'number' OR (item->>'points')!~'^(0|[1-9][0-9]{0,2})$'
   OR (item ? 'comment' AND (jsonb_typeof(item->'comment')<>'string' OR length(item->>'comment')>1000)) THEN RAISE EXCEPTION 'Invalid criterion score' USING ERRCODE='23514'; END IF;
  pts:=(item->>'points')::integer;
  IF pts>(rubric->idx->>'max_points')::integer THEN RAISE EXCEPTION 'Score exceeds original rubric maximum' USING ERRCODE='23514'; END IF;
  result:=result||jsonb_build_array(jsonb_build_object('criterion_index',idx,'points',pts,'comment',COALESCE(item->>'comment','')));
  total_points:=total_points+pts;idx:=idx+1;
 END LOOP;
 IF length(btrim(NEW.reason))=0 THEN
  IF EXISTS(SELECT 1 FROM public.grade_publications WHERE submission_id=NEW.submission_id AND state='released') THEN RAISE EXCEPTION 'Correction reason required' USING ERRCODE='23514'; END IF;
  NEW.reason:=CASE WHEN g.version=0 THEN 'Penilaian awal' ELSE 'Perbaikan draf' END;
 ELSE NEW.reason:=btrim(NEW.reason);END IF;
 SELECT COALESCE(max(revision_no),0)+1 INTO NEW.revision_no FROM public.grade_revisions WHERE submission_id=NEW.submission_id;
 NEW.scores:=result;NEW.total:=total_points;NEW.reviewer_id:=(public.access_context()->>'user')::uuid;NEW.created_at:=clock_timestamp();RETURN NEW;
END $$;
-- statement
CREATE TRIGGER grade_revision_before BEFORE INSERT ON grade_revisions FOR EACH ROW EXECUTE FUNCTION grade_revision_before();
-- statement
CREATE FUNCTION grade_revision_after() RETURNS trigger LANGUAGE plpgsql SET search_path=pg_catalog,public,pg_temp AS $$
BEGIN
 UPDATE public.grading_entries SET version=NEW.entry_version,draft_revision_id=NEW.id,last_action='draft_saved',last_reason=NEW.reason WHERE tenant_id=NEW.tenant_id AND submission_id=NEW.submission_id;
 RETURN NEW;
END $$;
-- statement
CREATE TRIGGER grade_revision_after AFTER INSERT ON grade_revisions FOR EACH ROW EXECUTE FUNCTION grade_revision_after();
-- statement
CREATE FUNCTION grade_publication_before() RETURNS trigger LANGUAGE plpgsql SET search_path=pg_catalog,public,pg_temp AS $$
DECLARE g public.grading_entries%ROWTYPE;r public.grade_revisions%ROWTYPE;
BEGIN
 IF NOT public.grading_authority(NEW.tenant_id,NEW.course_id,NEW.submission_id) THEN RAISE EXCEPTION 'Authorized grading scope required' USING ERRCODE='42501'; END IF;
 SELECT * INTO g FROM public.grading_entries WHERE tenant_id=NEW.tenant_id AND course_id=NEW.course_id AND submission_id=NEW.submission_id;
 IF g.submission_id IS NULL OR g.version<>NEW.version OR g.last_action NOT IN ('released','withdrawn') OR NEW.state<>g.last_action THEN RAISE EXCEPTION 'Publication requires grading transition' USING ERRCODE='23514'; END IF;
 IF TG_OP='UPDATE' AND ((NEW.tenant_id,NEW.course_id,NEW.submission_id) IS DISTINCT FROM (OLD.tenant_id,OLD.course_id,OLD.submission_id) OR NEW.version<=OLD.version) THEN RAISE EXCEPTION 'Publication version conflict' USING ERRCODE='23514'; END IF;
 IF NEW.state='released' THEN
  SELECT * INTO r FROM public.grade_revisions WHERE id=g.draft_revision_id AND submission_id=NEW.submission_id;
  IF r.id IS NULL THEN RAISE EXCEPTION 'Released revision missing' USING ERRCODE='23514'; END IF;
  NEW.revision_id:=r.id;NEW.revision_no:=r.revision_no;NEW.total:=r.total;NEW.scores:=r.scores;NEW.feedback:=r.feedback;
 ELSE NEW.revision_id:=NULL;NEW.revision_no:=NULL;NEW.total:=NULL;NEW.scores:=NULL;NEW.feedback:=NULL;END IF;
 NEW.changed_at:=g.updated_at;RETURN NEW;
END $$;
-- statement
CREATE TRIGGER grade_publication_before BEFORE INSERT OR UPDATE ON grade_publications FOR EACH ROW EXECUTE FUNCTION grade_publication_before();
-- statement
CREATE FUNCTION grading_event_before() RETURNS trigger LANGUAGE plpgsql SET search_path=pg_catalog,public,pg_temp AS $$
DECLARE g public.grading_entries%ROWTYPE;
BEGIN
 IF NOT public.grading_authority(NEW.tenant_id,NEW.course_id,NEW.submission_id) THEN RAISE EXCEPTION 'Authorized grading scope required' USING ERRCODE='42501'; END IF;
 SELECT * INTO g FROM public.grading_entries WHERE tenant_id=NEW.tenant_id AND course_id=NEW.course_id AND submission_id=NEW.submission_id;
 IF g.version<>NEW.version OR g.last_action<>NEW.action OR g.last_revision_id IS DISTINCT FROM NEW.revision_id THEN RAISE EXCEPTION 'Grading event mismatch' USING ERRCODE='23514'; END IF;
 NEW.actor_id:=g.last_actor_id;NEW.reason:=g.last_reason;NEW.created_at:=g.updated_at;RETURN NEW;
END $$;
-- statement
CREATE TRIGGER grading_event_before BEFORE INSERT ON grading_events FOR EACH ROW EXECUTE FUNCTION grading_event_before();
-- statement
CREATE FUNCTION grading_entry_after() RETURNS trigger LANGUAGE plpgsql SET search_path=pg_catalog,public,pg_temp AS $$
BEGIN
 IF NEW.last_action IN ('released','withdrawn') THEN
  INSERT INTO public.grade_publications(submission_id,tenant_id,course_id,version,state) VALUES(NEW.submission_id,NEW.tenant_id,NEW.course_id,NEW.version,NEW.last_action)
  ON CONFLICT(submission_id) DO UPDATE SET version=excluded.version,state=excluded.state;
 END IF;
 INSERT INTO public.grading_events(id,tenant_id,course_id,submission_id,version,action,revision_id,reason,actor_id,created_at)
 VALUES(gen_random_uuid(),NEW.tenant_id,NEW.course_id,NEW.submission_id,NEW.version,NEW.last_action,NEW.last_revision_id,NEW.last_reason,NEW.last_actor_id,NEW.updated_at);
 INSERT INTO public.audit_events(id,tenant_id,actor_id,action,target_type,target_id)
 VALUES(gen_random_uuid(),NEW.tenant_id,NEW.last_actor_id,'grade.'||NEW.last_action,'submission',NEW.submission_id);
 RETURN NEW;
END $$;
-- statement
CREATE TRIGGER grading_entry_after AFTER UPDATE ON grading_entries FOR EACH ROW EXECUTE FUNCTION grading_entry_after();
-- statement
CREATE FUNCTION immutable_grade_row() RETURNS trigger LANGUAGE plpgsql SET search_path=pg_catalog,public,pg_temp AS $$
BEGIN RAISE EXCEPTION 'Grade revisions and events are immutable' USING ERRCODE='23514';END $$;
-- statement
CREATE TRIGGER immutable_grade_revision BEFORE UPDATE OR DELETE ON grade_revisions FOR EACH ROW EXECUTE FUNCTION immutable_grade_row();
-- statement
CREATE TRIGGER immutable_grading_event BEFORE UPDATE OR DELETE ON grading_events FOR EACH ROW EXECUTE FUNCTION immutable_grade_row();
-- statement
REVOKE ALL ON FUNCTION grading_entry_before(),grade_revision_before(),grade_revision_after(),grade_publication_before(),grading_event_before(),grading_entry_after(),immutable_grade_row() FROM PUBLIC;
-- statement
CREATE TABLE grading_read_limits (
 tenant_id uuid NOT NULL,user_id uuid NOT NULL,attempts integer NOT NULL CHECK(attempts BETWEEN 1 AND 181),window_start timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY(tenant_id,user_id),FOREIGN KEY(tenant_id,user_id) REFERENCES memberships(tenant_id,user_id) ON DELETE CASCADE
);

-- statement
ALTER TABLE grading_entries ENABLE ROW LEVEL SECURITY;
-- statement
ALTER TABLE grading_entries FORCE ROW LEVEL SECURITY;
-- statement
REVOKE ALL ON grading_entries FROM PUBLIC,maaher_auth,maaher_definer,maaher_access_reader,maaher_maintenance;
-- statement
GRANT SELECT,INSERT ON grading_entries TO maaher_runtime;
-- statement
CREATE POLICY grading_read ON grading_entries FOR SELECT TO maaher_runtime USING(tenant_id::text=(SELECT access_context()->>'tenant') AND ((SELECT access_context()->>'role') IN ('admin','teacher') AND course_id=ANY((SELECT access_course_ids())::uuid[])));
-- statement
CREATE POLICY grading_insert ON grading_entries FOR INSERT TO maaher_runtime WITH CHECK(tenant_id::text=(SELECT access_context()->>'tenant') AND (SELECT access_context()->>'role') IN ('admin','teacher') AND course_id=ANY((SELECT access_course_ids())::uuid[]));
-- statement
CREATE POLICY grading_update ON grading_entries FOR UPDATE TO maaher_runtime USING(tenant_id::text=(SELECT access_context()->>'tenant') AND (SELECT access_context()->>'role') IN ('admin','teacher') AND course_id=ANY((SELECT access_course_ids())::uuid[])) WITH CHECK(tenant_id::text=(SELECT access_context()->>'tenant') AND (SELECT access_context()->>'role') IN ('admin','teacher') AND course_id=ANY((SELECT access_course_ids())::uuid[]));
-- statement
ALTER TABLE grade_revisions ENABLE ROW LEVEL SECURITY;
-- statement
ALTER TABLE grade_revisions FORCE ROW LEVEL SECURITY;
-- statement
REVOKE ALL ON grade_revisions FROM PUBLIC,maaher_auth,maaher_definer,maaher_access_reader,maaher_maintenance;
-- statement
GRANT SELECT,INSERT ON grade_revisions TO maaher_runtime;
-- statement
CREATE POLICY grading_read ON grade_revisions FOR SELECT TO maaher_runtime USING(tenant_id::text=(SELECT access_context()->>'tenant') AND ((SELECT access_context()->>'role') IN ('admin','teacher') AND course_id=ANY((SELECT access_course_ids())::uuid[])));
-- statement
CREATE POLICY grading_insert ON grade_revisions FOR INSERT TO maaher_runtime WITH CHECK(tenant_id::text=(SELECT access_context()->>'tenant') AND (SELECT access_context()->>'role') IN ('admin','teacher') AND course_id=ANY((SELECT access_course_ids())::uuid[]));
-- statement
ALTER TABLE grade_publications ENABLE ROW LEVEL SECURITY;
-- statement
ALTER TABLE grade_publications FORCE ROW LEVEL SECURITY;
-- statement
REVOKE ALL ON grade_publications FROM PUBLIC,maaher_auth,maaher_definer,maaher_access_reader,maaher_maintenance;
-- statement
GRANT SELECT,INSERT ON grade_publications TO maaher_runtime;
-- statement
CREATE POLICY grading_read ON grade_publications FOR SELECT TO maaher_runtime USING(tenant_id::text=(SELECT access_context()->>'tenant') AND (((SELECT access_context()->>'role') IN ('admin','teacher') AND course_id=ANY((SELECT access_course_ids())::uuid[])) OR ((SELECT access_context()->>'role')='student' AND submission_id IN(SELECT id FROM submissions))));
-- statement
CREATE POLICY grading_insert ON grade_publications FOR INSERT TO maaher_runtime WITH CHECK(tenant_id::text=(SELECT access_context()->>'tenant') AND (SELECT access_context()->>'role') IN ('admin','teacher') AND course_id=ANY((SELECT access_course_ids())::uuid[]));
-- statement
CREATE POLICY grading_update ON grade_publications FOR UPDATE TO maaher_runtime USING(tenant_id::text=(SELECT access_context()->>'tenant') AND (SELECT access_context()->>'role') IN ('admin','teacher') AND course_id=ANY((SELECT access_course_ids())::uuid[])) WITH CHECK(tenant_id::text=(SELECT access_context()->>'tenant') AND (SELECT access_context()->>'role') IN ('admin','teacher') AND course_id=ANY((SELECT access_course_ids())::uuid[]));
-- statement
ALTER TABLE grading_events ENABLE ROW LEVEL SECURITY;
-- statement
ALTER TABLE grading_events FORCE ROW LEVEL SECURITY;
-- statement
REVOKE ALL ON grading_events FROM PUBLIC,maaher_auth,maaher_definer,maaher_access_reader,maaher_maintenance;
-- statement
GRANT SELECT,INSERT ON grading_events TO maaher_runtime;
-- statement
CREATE POLICY grading_read ON grading_events FOR SELECT TO maaher_runtime USING(tenant_id::text=(SELECT access_context()->>'tenant') AND ((SELECT access_context()->>'role') IN ('admin','teacher') AND course_id=ANY((SELECT access_course_ids())::uuid[])));
-- statement
CREATE POLICY grading_insert ON grading_events FOR INSERT TO maaher_runtime WITH CHECK(tenant_id::text=(SELECT access_context()->>'tenant') AND (SELECT access_context()->>'role') IN ('admin','teacher') AND course_id=ANY((SELECT access_course_ids())::uuid[]));
-- statement
GRANT UPDATE(version,draft_revision_id,last_revision_id,last_action,last_reason,last_actor_id,updated_at) ON grading_entries TO maaher_runtime;
-- statement
GRANT UPDATE(version,state,revision_id,revision_no,total,scores,feedback,changed_at) ON grade_publications TO maaher_runtime;
-- statement
ALTER TABLE grading_read_limits ENABLE ROW LEVEL SECURITY;
-- statement
ALTER TABLE grading_read_limits FORCE ROW LEVEL SECURITY;
-- statement
REVOKE ALL ON grading_read_limits FROM PUBLIC,maaher_auth,maaher_definer,maaher_access_reader;
-- statement
GRANT SELECT,INSERT,UPDATE ON grading_read_limits TO maaher_runtime;
-- statement
CREATE POLICY own_grading_budget ON grading_read_limits TO maaher_runtime USING(tenant_id::text=(SELECT access_context()->>'tenant') AND user_id=(SELECT (access_context()->>'user')::uuid) AND (SELECT access_context()->>'role') IN ('admin','teacher')) WITH CHECK(tenant_id::text=(SELECT access_context()->>'tenant') AND user_id=(SELECT (access_context()->>'user')::uuid) AND (SELECT access_context()->>'role') IN ('admin','teacher'));
-- statement
GRANT SELECT(window_start),DELETE ON grading_read_limits TO maaher_maintenance;
-- statement
CREATE POLICY maintenance_read ON grading_read_limits FOR SELECT TO maaher_maintenance USING(window_start<now()-interval '1 day');
-- statement
CREATE POLICY maintenance_delete ON grading_read_limits FOR DELETE TO maaher_maintenance USING(window_start<now()-interval '1 day');
