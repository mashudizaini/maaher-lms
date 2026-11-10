CREATE TABLE courses (
    id uuid PRIMARY KEY, tenant_id uuid NOT NULL REFERENCES tenants(id),
    owner_id uuid NOT NULL REFERENCES users(id),
    title text NOT NULL CHECK(length(btrim(title)) BETWEEN 1 AND 160),
    description text NOT NULL DEFAULT '' CHECK(length(description)<=2000),
    state text NOT NULL DEFAULT 'draft' CHECK(state IN ('draft','published','archived')),
    version integer NOT NULL DEFAULT 1 CHECK(version>0),
    created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE(tenant_id,id), FOREIGN KEY(tenant_id,owner_id) REFERENCES memberships(tenant_id,user_id)
);
-- statement
CREATE TABLE courses_teachers (
    tenant_id uuid NOT NULL, course_id uuid NOT NULL, user_id uuid NOT NULL,
    PRIMARY KEY(tenant_id,course_id,user_id),
    FOREIGN KEY(tenant_id,course_id) REFERENCES courses(tenant_id,id) ON DELETE CASCADE,
    FOREIGN KEY(tenant_id,user_id) REFERENCES memberships(tenant_id,user_id)
);
-- statement
CREATE TABLE course_modules (
    id uuid PRIMARY KEY, tenant_id uuid NOT NULL, course_id uuid NOT NULL,
    title text NOT NULL CHECK(length(btrim(title)) BETWEEN 1 AND 160),
    position integer NOT NULL CHECK(position BETWEEN 1 AND 10000),
    UNIQUE(tenant_id,course_id,id),
    UNIQUE(tenant_id,course_id,position) DEFERRABLE INITIALLY DEFERRED,
    FOREIGN KEY(tenant_id,course_id) REFERENCES courses(tenant_id,id) ON DELETE CASCADE
);
-- statement
CREATE TABLE course_lessons (
    id uuid PRIMARY KEY, tenant_id uuid NOT NULL, course_id uuid NOT NULL, module_id uuid NOT NULL,
    title text NOT NULL CHECK(length(btrim(title)) BETWEEN 1 AND 160),
    content text NOT NULL DEFAULT '' CHECK(length(content)<=30000),
    resources jsonb NOT NULL DEFAULT '[]' CHECK(jsonb_typeof(resources)='array' AND jsonb_array_length(resources)<=10),
    position integer NOT NULL CHECK(position BETWEEN 1 AND 10000),
    UNIQUE(tenant_id,course_id,module_id,position) DEFERRABLE INITIALLY DEFERRED,
    FOREIGN KEY(tenant_id,course_id,module_id) REFERENCES course_modules(tenant_id,course_id,id) ON DELETE CASCADE
);
-- statement
CREATE FUNCTION course_member_role(p_tenant uuid,p_user uuid) RETURNS text
LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path=pg_catalog,public,pg_temp AS $$
DECLARE actor uuid; actor_role text;
BEGIN
    IF p_tenant::text IS DISTINCT FROM current_setting('app.tenant_id',true) THEN RETURN NULL; END IF;
    actor:=public.runtime_identity();
    SELECT m.role INTO actor_role FROM public.memberships m JOIN public.tenants t ON t.id=m.tenant_id
      WHERE m.tenant_id=p_tenant AND m.user_id=actor AND m.status='active' AND t.status='active';
    IF actor_role IS NULL OR (p_user<>actor AND actor_role<>'admin') THEN RETURN NULL; END IF;
    RETURN (SELECT m.role FROM public.memberships m JOIN public.users u ON u.id=m.user_id
            WHERE m.tenant_id=p_tenant AND m.user_id=p_user AND m.status='active' AND u.status='active');
END $$;
-- statement
ALTER FUNCTION course_member_role(uuid,uuid) OWNER TO maaher_definer;
-- statement
REVOKE ALL ON FUNCTION course_member_role(uuid,uuid) FROM PUBLIC;
-- statement
GRANT EXECUTE ON FUNCTION course_member_role(uuid,uuid) TO maaher_runtime;
-- statement
CREATE FUNCTION course_can_manage(p_tenant uuid,p_course uuid) RETURNS boolean
LANGUAGE sql STABLE SECURITY INVOKER SET search_path=pg_catalog,public,pg_temp AS $$
    SELECT coalesce(public.course_member_role(p_tenant,public.runtime_identity())='admin'
      OR (public.course_member_role(p_tenant,public.runtime_identity())='teacher' AND EXISTS(
          SELECT 1 FROM public.courses_teachers a WHERE a.tenant_id=p_tenant AND a.course_id=p_course
          AND a.user_id=public.runtime_identity())),false)
$$;
-- statement
REVOKE ALL ON FUNCTION course_can_manage(uuid,uuid) FROM PUBLIC;
-- statement
GRANT EXECUTE ON FUNCTION course_can_manage(uuid,uuid) TO maaher_runtime;
-- statement
ALTER TABLE courses ENABLE ROW LEVEL SECURITY;
-- statement
ALTER TABLE courses FORCE ROW LEVEL SECURITY;
-- statement
ALTER TABLE courses_teachers ENABLE ROW LEVEL SECURITY;
-- statement
ALTER TABLE courses_teachers FORCE ROW LEVEL SECURITY;
-- statement
ALTER TABLE course_modules ENABLE ROW LEVEL SECURITY;
-- statement
ALTER TABLE course_modules FORCE ROW LEVEL SECURITY;
-- statement
ALTER TABLE course_lessons ENABLE ROW LEVEL SECURITY;
-- statement
ALTER TABLE course_lessons FORCE ROW LEVEL SECURITY;
-- statement
CREATE POLICY course_read ON courses FOR SELECT TO maaher_runtime USING(course_can_manage(tenant_id,id));
-- statement
CREATE POLICY course_create ON courses FOR INSERT TO maaher_runtime
WITH CHECK(course_member_role(tenant_id,runtime_identity())='admin' AND owner_id=runtime_identity() AND state='draft' AND version=1);
-- statement
CREATE POLICY course_update ON courses FOR UPDATE TO maaher_runtime
USING(course_can_manage(tenant_id,id) AND (state<>'archived' OR course_member_role(tenant_id,runtime_identity())='admin'))
WITH CHECK(course_can_manage(tenant_id,id) AND (state<>'archived' OR course_member_role(tenant_id,runtime_identity())='admin'));
-- statement
CREATE POLICY assignment_read ON courses_teachers FOR SELECT TO maaher_runtime USING(
    course_member_role(tenant_id,runtime_identity())='admin' OR
    (user_id=runtime_identity() AND course_member_role(tenant_id,runtime_identity())='teacher'));
-- statement
CREATE POLICY assignment_add ON courses_teachers FOR INSERT TO maaher_runtime WITH CHECK(
    course_member_role(tenant_id,runtime_identity())='admin' AND course_member_role(tenant_id,user_id)='teacher');
-- statement
CREATE POLICY assignment_remove ON courses_teachers FOR DELETE TO maaher_runtime USING(course_member_role(tenant_id,runtime_identity())='admin');
-- statement
CREATE POLICY module_read ON course_modules FOR SELECT TO maaher_runtime USING(course_can_manage(tenant_id,course_id));
-- statement
CREATE POLICY module_write ON course_modules FOR ALL TO maaher_runtime
USING(course_can_manage(tenant_id,course_id) AND EXISTS(SELECT 1 FROM courses c WHERE c.tenant_id=course_modules.tenant_id AND c.id=course_modules.course_id AND c.state='draft'))
WITH CHECK(course_can_manage(tenant_id,course_id) AND EXISTS(SELECT 1 FROM courses c WHERE c.tenant_id=course_modules.tenant_id AND c.id=course_modules.course_id AND c.state='draft'));
-- statement
CREATE POLICY lesson_read ON course_lessons FOR SELECT TO maaher_runtime USING(course_can_manage(tenant_id,course_id));
-- statement
CREATE POLICY lesson_write ON course_lessons FOR ALL TO maaher_runtime
USING(course_can_manage(tenant_id,course_id) AND EXISTS(SELECT 1 FROM courses c WHERE c.tenant_id=course_lessons.tenant_id AND c.id=course_lessons.course_id AND c.state='draft'))
WITH CHECK(course_can_manage(tenant_id,course_id) AND EXISTS(SELECT 1 FROM courses c WHERE c.tenant_id=course_lessons.tenant_id AND c.id=course_lessons.course_id AND c.state='draft'));
-- statement
REVOKE ALL ON courses,courses_teachers,course_modules,course_lessons FROM PUBLIC,maaher_auth;
-- statement
GRANT SELECT,INSERT ON courses TO maaher_runtime;
-- statement
GRANT UPDATE(title,description,state,version,updated_at) ON courses TO maaher_runtime;
-- statement
GRANT SELECT,INSERT,DELETE ON courses_teachers TO maaher_runtime;
-- statement
GRANT SELECT,INSERT,DELETE ON course_modules,course_lessons TO maaher_runtime;
-- statement
GRANT UPDATE(title,position) ON course_modules TO maaher_runtime;
-- statement
GRANT UPDATE(title,content,resources,position) ON course_lessons TO maaher_runtime;
