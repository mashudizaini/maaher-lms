ALTER POLICY course_read ON courses USING(course_can_manage(tenant_id,id)
    AND (state<>'archived' OR course_member_role(tenant_id,runtime_identity())='admin'));
-- statement
ALTER POLICY module_read ON course_modules USING(course_can_manage(tenant_id,course_id)
    AND EXISTS(SELECT 1 FROM courses c WHERE c.tenant_id=course_modules.tenant_id AND c.id=course_modules.course_id));
-- statement
ALTER POLICY lesson_read ON course_lessons USING(course_can_manage(tenant_id,course_id)
    AND EXISTS(SELECT 1 FROM courses c WHERE c.tenant_id=course_lessons.tenant_id AND c.id=course_lessons.course_id));
-- statement
GRANT SELECT,DELETE ON courses_teachers TO maaher_definer;
-- statement
CREATE FUNCTION course_assignment_guard() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public,pg_temp AS $$
DECLARE actor uuid; target_user uuid; target_tenant uuid; member_role text; member_status text; removed record;
BEGIN
    IF TG_RELID='public.courses_teachers'::regclass AND TG_OP='INSERT' THEN
        -- Serialize assignment with user/membership changes. FK key-share locks
        -- alone do not conflict with updates to role/status.
        PERFORM 1 FROM public.users WHERE id=NEW.user_id AND status='active' FOR SHARE;
        IF NOT FOUND THEN RAISE EXCEPTION 'active teacher required' USING ERRCODE='23514'; END IF;
        SELECT role,status INTO member_role,member_status FROM public.memberships
          WHERE tenant_id=NEW.tenant_id AND user_id=NEW.user_id FOR SHARE;
        IF NOT FOUND OR member_role<>'teacher' OR member_status<>'active' THEN
            RAISE EXCEPTION 'active teacher required' USING ERRCODE='23514';
        END IF;
        RETURN NEW;
    ELSIF TG_RELID='public.memberships'::regclass AND TG_OP='UPDATE' THEN
        target_user:=NEW.user_id; target_tenant:=NEW.tenant_id;
    ELSIF TG_RELID='public.users'::regclass AND TG_OP='UPDATE' THEN
        target_user:=NEW.id;
    ELSE
        RAISE EXCEPTION 'unsupported assignment trigger';
    END IF;
    actor:=public.runtime_identity();
    FOR removed IN DELETE FROM public.courses_teachers
      WHERE user_id=target_user AND (target_tenant IS NULL OR tenant_id=target_tenant)
      RETURNING tenant_id,course_id LOOP
        IF actor IS NOT NULL AND public.course_member_role(removed.tenant_id,actor)='admin' THEN
            INSERT INTO public.audit_events(id,tenant_id,actor_id,action,target_type,target_id)
              VALUES(gen_random_uuid(),removed.tenant_id,actor,'course.teacher_access_revoked','course',removed.course_id);
        END IF;
    END LOOP;
    -- Do not lock courses here: assignment writes lock course before membership,
    -- so acquiring course locks during a role update would invert that order.
    RETURN NEW;
END $$;
-- statement
ALTER FUNCTION course_assignment_guard() OWNER TO maaher_definer;
-- statement
REVOKE ALL ON FUNCTION course_assignment_guard() FROM PUBLIC;
-- statement
CREATE TRIGGER course_assignment_insert_guard BEFORE INSERT ON courses_teachers
FOR EACH ROW EXECUTE FUNCTION course_assignment_guard();
-- statement
CREATE TRIGGER course_membership_changed AFTER UPDATE OF role,status ON memberships
FOR EACH ROW WHEN (OLD.role IS DISTINCT FROM NEW.role OR OLD.status IS DISTINCT FROM NEW.status)
EXECUTE FUNCTION course_assignment_guard();
-- statement
CREATE TRIGGER course_user_status_changed AFTER UPDATE OF status ON users
FOR EACH ROW WHEN (OLD.status IS DISTINCT FROM NEW.status) EXECUTE FUNCTION course_assignment_guard();
-- statement
DELETE FROM courses_teachers a WHERE NOT EXISTS(
    SELECT 1 FROM memberships m JOIN users u ON u.id=m.user_id
    WHERE m.tenant_id=a.tenant_id AND m.user_id=a.user_id AND m.role='teacher'
      AND m.status='active' AND u.status='active');
-- statement
CREATE TABLE course_write_limits (
    tenant_id uuid NOT NULL, user_id uuid NOT NULL,
    attempts integer NOT NULL CHECK(attempts BETWEEN 1 AND 61),
    window_start timestamptz NOT NULL DEFAULT now(), PRIMARY KEY(tenant_id,user_id),
    FOREIGN KEY(tenant_id,user_id) REFERENCES memberships(tenant_id,user_id) ON DELETE CASCADE
);
-- statement
ALTER TABLE course_write_limits ENABLE ROW LEVEL SECURITY;
-- statement
ALTER TABLE course_write_limits FORCE ROW LEVEL SECURITY;
-- statement
CREATE POLICY own_course_budget ON course_write_limits TO maaher_runtime
USING(tenant_id::text=current_setting('app.tenant_id',true) AND user_id=runtime_identity()
      AND course_member_role(tenant_id,user_id) IN ('admin','teacher'))
WITH CHECK(tenant_id::text=current_setting('app.tenant_id',true) AND user_id=runtime_identity()
      AND course_member_role(tenant_id,user_id) IN ('admin','teacher'));
-- statement
REVOKE ALL ON course_write_limits FROM PUBLIC,maaher_auth;
-- statement
GRANT SELECT,INSERT,UPDATE ON course_write_limits TO maaher_runtime;
-- statement
GRANT DELETE ON course_write_limits TO maaher_definer;
-- statement
GRANT SELECT(window_start) ON course_write_limits TO maaher_definer;
