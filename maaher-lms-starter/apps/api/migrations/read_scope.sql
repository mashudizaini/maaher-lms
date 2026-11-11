DO $$ BEGIN
 IF NOT EXISTS(SELECT 1 FROM pg_roles WHERE rolname='maaher_access_reader') THEN
   CREATE ROLE maaher_access_reader NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS NOINHERIT;
 END IF;
 IF EXISTS(SELECT 1 FROM pg_roles WHERE rolname='maaher_access_reader' AND (rolcanlogin OR rolsuper OR rolbypassrls OR rolcreaterole OR rolcreatedb OR rolreplication OR rolinherit))
    OR EXISTS(SELECT 1 FROM pg_auth_members WHERE member=(SELECT oid FROM pg_roles WHERE rolname='maaher_access_reader') OR roleid=(SELECT oid FROM pg_roles WHERE rolname='maaher_access_reader'))
    OR pg_has_role('maaher_runtime','maaher_access_reader','MEMBER') OR pg_has_role('maaher_auth','maaher_access_reader','MEMBER') THEN
   RAISE EXCEPTION 'unsafe access reader role';
 END IF;
END $$;
-- statement
GRANT USAGE ON SCHEMA public TO maaher_access_reader;
-- statement
GRANT EXECUTE ON FUNCTION runtime_identity() TO maaher_access_reader;
-- statement
GRANT SELECT(tenant_id,user_id,role,status) ON memberships TO maaher_access_reader;
-- statement
GRANT SELECT(id,status) ON tenants TO maaher_access_reader;
-- statement
GRANT SELECT(id,tenant_id,state) ON courses TO maaher_access_reader;
-- statement
GRANT SELECT(tenant_id,course_id,user_id) ON courses_teachers TO maaher_access_reader;
-- statement
GRANT SELECT(id,tenant_id,course_id,state) ON cohorts TO maaher_access_reader;
-- statement
GRANT SELECT(id,tenant_id,course_id,cohort_id,student_id,status) ON enrollments TO maaher_access_reader;
-- statement
CREATE POLICY access_reader ON memberships FOR SELECT TO maaher_access_reader USING(true);
-- statement
CREATE POLICY access_reader ON tenants FOR SELECT TO maaher_access_reader USING(true);
-- statement
CREATE POLICY access_reader ON courses FOR SELECT TO maaher_access_reader USING(true);
-- statement
CREATE POLICY access_reader ON courses_teachers FOR SELECT TO maaher_access_reader USING(true);
-- statement
CREATE POLICY access_reader ON cohorts FOR SELECT TO maaher_access_reader USING(true);
-- statement
CREATE POLICY access_reader ON enrollments FOR SELECT TO maaher_access_reader USING(true);
-- statement
CREATE FUNCTION access_context() RETURNS jsonb LANGUAGE plpgsql STABLE SECURITY DEFINER
SET search_path=pg_catalog,public,pg_temp AS $$
DECLARE actor uuid; row record;
BEGIN
 actor:=public.runtime_identity();
 IF actor IS NULL THEN RETURN NULL; END IF;
 SELECT m.tenant_id,m.role INTO row FROM public.memberships m JOIN public.tenants t ON t.id=m.tenant_id
 WHERE m.user_id=actor AND m.tenant_id::text=current_setting('app.tenant_id',true) AND m.status='active' AND t.status='active';
 IF NOT FOUND THEN RETURN NULL; END IF;
 RETURN jsonb_build_object('tenant',row.tenant_id,'user',actor,'role',row.role);
END $$;
-- statement
CREATE FUNCTION access_course_ids() RETURNS uuid[] LANGUAGE plpgsql STABLE SECURITY DEFINER
SET search_path=pg_catalog,public,pg_temp AS $$
DECLARE ctx jsonb;
BEGIN
 ctx:=public.access_context();
 IF ctx IS NULL THEN RETURN ARRAY[]::uuid[]; END IF;
 RETURN ARRAY(SELECT c.id FROM public.courses c WHERE c.tenant_id=(ctx->>'tenant')::uuid AND (
  ctx->>'role'='admin' OR (ctx->>'role'='teacher' AND c.state<>'archived' AND EXISTS(
    SELECT 1 FROM public.courses_teachers a WHERE a.tenant_id=c.tenant_id AND a.course_id=c.id AND a.user_id=(ctx->>'user')::uuid))
  OR (ctx->>'role'='student' AND c.state='published' AND EXISTS(
    SELECT 1 FROM public.enrollments e JOIN public.cohorts h ON h.tenant_id=e.tenant_id AND h.course_id=e.course_id AND h.id=e.cohort_id
    WHERE e.tenant_id=c.tenant_id AND e.course_id=c.id AND e.student_id=(ctx->>'user')::uuid AND e.status='active' AND h.state='active'))));
END $$;
-- statement
CREATE FUNCTION access_student_cohorts() RETURNS uuid[] LANGUAGE plpgsql STABLE SECURITY DEFINER
SET search_path=pg_catalog,public,pg_temp AS $$
DECLARE ctx jsonb;
BEGIN
 ctx:=public.access_context();
 IF ctx IS NULL OR ctx->>'role'<>'student' THEN RETURN ARRAY[]::uuid[]; END IF;
 RETURN ARRAY(SELECT e.cohort_id FROM public.enrollments e
  JOIN public.cohorts h ON h.tenant_id=e.tenant_id AND h.course_id=e.course_id AND h.id=e.cohort_id
  JOIN public.courses c ON c.tenant_id=e.tenant_id AND c.id=e.course_id
  WHERE e.tenant_id=(ctx->>'tenant')::uuid AND e.student_id=(ctx->>'user')::uuid
    AND e.status='active' AND h.state='active' AND c.state='published');
END $$;
-- statement
CREATE FUNCTION access_student_enrollments() RETURNS uuid[] LANGUAGE plpgsql STABLE SECURITY DEFINER
SET search_path=pg_catalog,public,pg_temp AS $$
DECLARE ctx jsonb;
BEGIN
 ctx:=public.access_context();
 IF ctx IS NULL OR ctx->>'role'<>'student' THEN RETURN ARRAY[]::uuid[]; END IF;
 RETURN ARRAY(SELECT e.id FROM public.enrollments e
  JOIN public.cohorts h ON h.tenant_id=e.tenant_id AND h.course_id=e.course_id AND h.id=e.cohort_id
  JOIN public.courses c ON c.tenant_id=e.tenant_id AND c.id=e.course_id
  WHERE e.tenant_id=(ctx->>'tenant')::uuid AND e.student_id=(ctx->>'user')::uuid
    AND e.status='active' AND h.state='active' AND c.state='published');
END $$;
-- statement
ALTER FUNCTION access_context() OWNER TO maaher_access_reader;
-- statement
ALTER FUNCTION access_course_ids() OWNER TO maaher_access_reader;
-- statement
ALTER FUNCTION access_student_cohorts() OWNER TO maaher_access_reader;
-- statement
ALTER FUNCTION access_student_enrollments() OWNER TO maaher_access_reader;
-- statement
REVOKE ALL ON FUNCTION access_context(),access_course_ids(),access_student_cohorts(),access_student_enrollments() FROM PUBLIC;
-- statement
GRANT EXECUTE ON FUNCTION access_context(),access_course_ids(),access_student_cohorts(),access_student_enrollments() TO maaher_runtime;
-- statement
ALTER POLICY course_read ON courses USING(tenant_id::text=(SELECT access_context()->>'tenant') AND ((SELECT access_context()->>'role')='admin' OR id=ANY((SELECT access_course_ids())::uuid[])));
-- statement
ALTER POLICY module_read ON course_modules USING(tenant_id::text=current_setting('app.tenant_id',true) AND course_id=ANY((SELECT access_course_ids())::uuid[]));
-- statement
ALTER POLICY lesson_read ON course_lessons USING(tenant_id::text=current_setting('app.tenant_id',true) AND course_id=ANY((SELECT access_course_ids())::uuid[]));
-- statement
ALTER POLICY assignment_read ON courses_teachers USING(
 tenant_id::text=(SELECT access_context()->>'tenant') AND ((SELECT access_context()->>'role')='admin'
 OR ((SELECT access_context()->>'role')='teacher' AND user_id=(SELECT (access_context()->>'user')::uuid))));
-- statement
ALTER POLICY cohort_read ON cohorts USING(tenant_id::text=(SELECT access_context()->>'tenant') AND (
 (SELECT access_context()->>'role')='admin'
 OR ((SELECT access_context()->>'role')='teacher' AND state='active' AND course_id=ANY((SELECT access_course_ids())::uuid[]))
 OR id=ANY((SELECT access_student_cohorts())::uuid[])));
-- statement
ALTER POLICY enrollment_read ON enrollments USING(tenant_id::text=(SELECT access_context()->>'tenant') AND (
 (SELECT access_context()->>'role')='admin'
 OR ((SELECT access_context()->>'role')='teacher' AND status='active' AND course_id=ANY((SELECT access_course_ids())::uuid[])
     AND cohort_id IN(SELECT id FROM cohorts WHERE state='active'))
 OR (student_id=(SELECT (access_context()->>'user')::uuid) AND status='active'
     AND id=ANY((SELECT access_student_enrollments())::uuid[]))));
