CREATE TABLE cohorts (
 id uuid PRIMARY KEY, tenant_id uuid NOT NULL, course_id uuid NOT NULL,
 title text NOT NULL CHECK(length(btrim(title)) BETWEEN 1 AND 160),
 state text NOT NULL DEFAULT 'active' CHECK(state IN ('active','archived')),
 version integer NOT NULL DEFAULT 1 CHECK(version>0),
 created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE(tenant_id,course_id,id), FOREIGN KEY(tenant_id,course_id) REFERENCES courses(tenant_id,id)
);
-- statement
CREATE TABLE enrollments (
 id uuid PRIMARY KEY, tenant_id uuid NOT NULL, course_id uuid NOT NULL, cohort_id uuid NOT NULL, student_id uuid NOT NULL,
 status text NOT NULL DEFAULT 'active' CHECK(status IN ('active','revoked')),
 version integer NOT NULL DEFAULT 1 CHECK(version>0),
 created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE(tenant_id,course_id,student_id),
 FOREIGN KEY(tenant_id,course_id,cohort_id) REFERENCES cohorts(tenant_id,course_id,id),
 FOREIGN KEY(tenant_id,student_id) REFERENCES memberships(tenant_id,user_id)
);
-- statement
CREATE INDEX enrollment_roster ON enrollments(tenant_id,course_id,cohort_id,status,id);
-- statement
GRANT SELECT ON courses,cohorts,enrollments TO maaher_definer;
-- statement
GRANT UPDATE(version) ON courses,cohorts TO maaher_definer;
-- statement
GRANT UPDATE(status,version,updated_at) ON enrollments TO maaher_definer;
-- statement
CREATE FUNCTION course_student_access(p_tenant uuid,p_course uuid,p_cohort uuid) RETURNS boolean
LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path=pg_catalog,public,pg_temp AS $$
DECLARE actor uuid;
BEGIN
 actor:=public.runtime_identity();
 IF p_tenant::text IS DISTINCT FROM current_setting('app.tenant_id',true)
    OR public.course_member_role(p_tenant,actor) IS DISTINCT FROM 'student' THEN RETURN false; END IF;
 RETURN EXISTS(SELECT 1 FROM public.enrollments e
   JOIN public.cohorts h ON h.tenant_id=e.tenant_id AND h.course_id=e.course_id AND h.id=e.cohort_id
   JOIN public.courses c ON c.tenant_id=e.tenant_id AND c.id=e.course_id
   WHERE e.tenant_id=p_tenant AND e.course_id=p_course AND e.student_id=actor AND e.status='active'
     AND (p_cohort IS NULL OR e.cohort_id=p_cohort) AND h.state='active' AND c.state='published');
END $$;
-- statement
ALTER FUNCTION course_student_access(uuid,uuid,uuid) OWNER TO maaher_definer;
-- statement
REVOKE ALL ON FUNCTION course_student_access(uuid,uuid,uuid) FROM PUBLIC;
-- statement
GRANT EXECUTE ON FUNCTION course_student_access(uuid,uuid,uuid) TO maaher_runtime;
-- statement
CREATE FUNCTION enrollment_lock_student(p_tenant uuid,p_student uuid) RETURNS boolean
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public,pg_temp AS $$
DECLARE r text; s text;
BEGIN
 IF public.course_member_role(p_tenant,public.runtime_identity()) IS DISTINCT FROM 'admin' THEN RETURN false; END IF;
 -- Scope the target before taking any global user lock. Recheck under lock below.
 IF NOT EXISTS(SELECT 1 FROM public.memberships WHERE tenant_id=p_tenant AND user_id=p_student AND role='student' AND status='active') THEN RETURN false; END IF;
 PERFORM 1 FROM public.users WHERE id=p_student AND status='active' FOR SHARE;
 IF NOT FOUND THEN RETURN false; END IF;
 SELECT role,status INTO r,s FROM public.memberships WHERE tenant_id=p_tenant AND user_id=p_student FOR SHARE;
 RETURN FOUND AND r='student' AND s='active';
END $$;
-- statement
ALTER FUNCTION enrollment_lock_student(uuid,uuid) OWNER TO maaher_definer;
-- statement
REVOKE ALL ON FUNCTION enrollment_lock_student(uuid,uuid) FROM PUBLIC;
-- statement
GRANT EXECUTE ON FUNCTION enrollment_lock_student(uuid,uuid) TO maaher_runtime;
-- statement
CREATE FUNCTION enrollment_guard() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public,pg_temp AS $$
DECLARE target_student uuid; target_tenant uuid; target_course uuid; target_cohort uuid; actor uuid; removed record; r text; s text;
BEGIN
 IF TG_RELID='public.enrollments'::regclass THEN
   -- BEFORE triggers run before the RLS WITH CHECK. Reject runtime callers
   -- outside their validated admin tenant before touching any parent/user row.
   -- Migration/DB owners already control these tables independently of RLS.
   IF NOT pg_has_role(session_user,(SELECT relowner FROM pg_class WHERE oid=TG_RELID),'USAGE')
      AND pg_has_role(session_user,'maaher_runtime','MEMBER')
      AND public.course_member_role(NEW.tenant_id,public.runtime_identity()) IS DISTINCT FROM 'admin' THEN
     RAISE EXCEPTION 'admin enrollment mutation required' USING ERRCODE='42501';
   END IF;
   IF NEW.status='active' THEN
     IF NOT EXISTS(SELECT 1 FROM public.memberships WHERE tenant_id=NEW.tenant_id AND user_id=NEW.student_id AND role='student' AND status='active') THEN
       RAISE EXCEPTION 'active student required' USING ERRCODE='23514';
     END IF;
     PERFORM 1 FROM public.courses WHERE tenant_id=NEW.tenant_id AND id=NEW.course_id AND state<>'archived' FOR SHARE;
     IF NOT FOUND THEN RAISE EXCEPTION 'active course required' USING ERRCODE='23514'; END IF;
     PERFORM 1 FROM public.cohorts WHERE tenant_id=NEW.tenant_id AND course_id=NEW.course_id AND id=NEW.cohort_id AND state='active' FOR SHARE;
     IF NOT FOUND THEN RAISE EXCEPTION 'active matching cohort required' USING ERRCODE='23514'; END IF;
     PERFORM 1 FROM public.users WHERE id=NEW.student_id AND status='active' FOR SHARE;
     IF NOT FOUND THEN RAISE EXCEPTION 'active student required' USING ERRCODE='23514'; END IF;
     SELECT role,status INTO r,s FROM public.memberships WHERE tenant_id=NEW.tenant_id AND user_id=NEW.student_id FOR SHARE;
     IF NOT FOUND OR r<>'student' OR s<>'active' THEN RAISE EXCEPTION 'active student required' USING ERRCODE='23514'; END IF;
   END IF;
   RETURN NEW;
 ELSIF TG_RELID='public.memberships'::regclass THEN
   target_student:=NEW.user_id; target_tenant:=NEW.tenant_id;
 ELSIF TG_RELID='public.users'::regclass THEN target_student:=NEW.id;
 ELSIF TG_RELID='public.courses'::regclass THEN target_tenant:=NEW.tenant_id; target_course:=NEW.id;
 ELSIF TG_RELID='public.cohorts'::regclass THEN target_tenant:=NEW.tenant_id; target_cohort:=NEW.id;
 ELSE RAISE EXCEPTION 'unsupported enrollment trigger';
 END IF;
 actor:=public.runtime_identity();
 FOR removed IN UPDATE public.enrollments SET status='revoked',version=version+1,updated_at=now()
   WHERE status='active' AND (target_student IS NULL OR student_id=target_student)
     AND (target_tenant IS NULL OR tenant_id=target_tenant) AND (target_course IS NULL OR course_id=target_course)
     AND (target_cohort IS NULL OR cohort_id=target_cohort) RETURNING id,tenant_id LOOP
   IF actor IS NOT NULL AND public.course_member_role(removed.tenant_id,actor)='admin' THEN
     INSERT INTO public.audit_events(id,tenant_id,actor_id,action,target_type,target_id)
       VALUES(gen_random_uuid(),removed.tenant_id,actor,'enrollment.access_revoked','enrollment',removed.id);
   END IF;
 END LOOP;
 RETURN NEW;
END $$;
-- statement
ALTER FUNCTION enrollment_guard() OWNER TO maaher_definer;
-- statement
REVOKE ALL ON FUNCTION enrollment_guard() FROM PUBLIC;
-- statement
CREATE TRIGGER enrollment_validate BEFORE INSERT OR UPDATE OF cohort_id,status ON enrollments FOR EACH ROW EXECUTE FUNCTION enrollment_guard();
-- statement
CREATE TRIGGER enrollment_membership_changed AFTER UPDATE OF role,status ON memberships
 FOR EACH ROW WHEN(OLD.role IS DISTINCT FROM NEW.role OR OLD.status IS DISTINCT FROM NEW.status) EXECUTE FUNCTION enrollment_guard();
-- statement
CREATE TRIGGER enrollment_user_changed AFTER UPDATE OF status ON users
 FOR EACH ROW WHEN(OLD.status IS DISTINCT FROM NEW.status) EXECUTE FUNCTION enrollment_guard();
-- statement
CREATE TRIGGER enrollment_course_archived AFTER UPDATE OF state ON courses
 FOR EACH ROW WHEN(OLD.state IS DISTINCT FROM NEW.state AND NEW.state='archived') EXECUTE FUNCTION enrollment_guard();
-- statement
CREATE TRIGGER enrollment_cohort_archived AFTER UPDATE OF state ON cohorts
 FOR EACH ROW WHEN(OLD.state IS DISTINCT FROM NEW.state AND NEW.state='archived') EXECUTE FUNCTION enrollment_guard();
-- statement
ALTER TABLE cohorts ENABLE ROW LEVEL SECURITY;
-- statement
ALTER TABLE cohorts FORCE ROW LEVEL SECURITY;
-- statement
ALTER TABLE enrollments ENABLE ROW LEVEL SECURITY;
-- statement
ALTER TABLE enrollments FORCE ROW LEVEL SECURITY;
-- statement
CREATE POLICY cohort_read ON cohorts FOR SELECT TO maaher_runtime USING(
 course_member_role(tenant_id,runtime_identity())='admin'
 OR (course_can_manage(tenant_id,course_id) AND state='active' AND EXISTS(SELECT 1 FROM courses c WHERE c.tenant_id=cohorts.tenant_id AND c.id=cohorts.course_id))
 OR course_student_access(tenant_id,course_id,id));
-- statement
CREATE POLICY cohort_create ON cohorts FOR INSERT TO maaher_runtime WITH CHECK(
 course_member_role(tenant_id,runtime_identity())='admin' AND state='active' AND version=1);
-- statement
CREATE POLICY cohort_update ON cohorts FOR UPDATE TO maaher_runtime
 USING(course_member_role(tenant_id,runtime_identity())='admin') WITH CHECK(course_member_role(tenant_id,runtime_identity())='admin');
-- statement
CREATE POLICY enrollment_read ON enrollments FOR SELECT TO maaher_runtime USING(
 course_member_role(tenant_id,runtime_identity())='admin'
 OR (status='active' AND course_can_manage(tenant_id,course_id)
     AND EXISTS(SELECT 1 FROM cohorts h WHERE h.tenant_id=enrollments.tenant_id AND h.id=enrollments.cohort_id AND h.state='active'))
 OR (student_id=runtime_identity() AND status='active' AND course_student_access(tenant_id,course_id,cohort_id)));
-- statement
CREATE POLICY enrollment_create ON enrollments FOR INSERT TO maaher_runtime WITH CHECK(
 course_member_role(tenant_id,runtime_identity())='admin' AND status='active' AND version=1
 AND course_member_role(tenant_id,student_id)='student');
-- statement
CREATE POLICY enrollment_update ON enrollments FOR UPDATE TO maaher_runtime
 USING(course_member_role(tenant_id,runtime_identity())='admin') WITH CHECK(course_member_role(tenant_id,runtime_identity())='admin');
-- statement
REVOKE ALL ON cohorts,enrollments FROM PUBLIC,maaher_auth;
-- statement
GRANT SELECT,INSERT ON cohorts,enrollments TO maaher_runtime;
-- statement
GRANT UPDATE(title,state,version,updated_at) ON cohorts TO maaher_runtime;
-- statement
GRANT UPDATE(cohort_id,status,version,updated_at) ON enrollments TO maaher_runtime;
-- statement
ALTER POLICY course_read ON courses USING(
 (course_can_manage(tenant_id,id) AND (state<>'archived' OR course_member_role(tenant_id,runtime_identity())='admin'))
 OR course_student_access(tenant_id,id,NULL));
-- statement
ALTER POLICY module_read ON course_modules USING(
 (course_can_manage(tenant_id,course_id) OR course_student_access(tenant_id,course_id,NULL))
 AND EXISTS(SELECT 1 FROM courses c WHERE c.tenant_id=course_modules.tenant_id AND c.id=course_modules.course_id));
-- statement
ALTER POLICY lesson_read ON course_lessons USING(
 (course_can_manage(tenant_id,course_id) OR course_student_access(tenant_id,course_id,NULL))
 AND EXISTS(SELECT 1 FROM courses c WHERE c.tenant_id=course_lessons.tenant_id AND c.id=course_lessons.course_id));
