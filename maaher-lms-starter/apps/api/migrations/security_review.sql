REVOKE CREATE ON SCHEMA public FROM PUBLIC;
-- statement
CREATE TABLE mfa_requests (
    id uuid PRIMARY KEY, user_id uuid NOT NULL REFERENCES users(id),
    session_hash text NOT NULL REFERENCES sessions(token_hash) ON DELETE CASCADE,
    purpose text NOT NULL CHECK (purpose IN ('bootstrap','recovery')),
    created_at timestamptz NOT NULL DEFAULT now(), expires_at timestamptz NOT NULL,
    token_hash text UNIQUE, approved_at timestamptz, consumed_at timestamptz,
    operator_reference text CHECK (length(operator_reference) BETWEEN 8 AND 120),
    UNIQUE(session_hash,purpose)
);
-- statement
CREATE TABLE mfa_enrollments (
    session_hash text PRIMARY KEY REFERENCES sessions(token_hash) ON DELETE CASCADE,
    user_id uuid NOT NULL REFERENCES users(id), encrypted_secret text NOT NULL,
    password_hash text, purpose text NOT NULL CHECK (purpose IN ('bootstrap','recovery')),
    created_at timestamptz NOT NULL DEFAULT now(), expires_at timestamptz NOT NULL
);
-- statement
CREATE TABLE auth_rate_buckets (
    kind text NOT NULL CHECK (kind IN ('global','client','account','reset','mfa')),
    bucket integer NOT NULL CHECK (bucket BETWEEN 0 AND 4095),
    attempts integer NOT NULL, window_start timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY(kind,bucket)
);
-- statement
CREATE TABLE mfa_operator_audit (
    id uuid PRIMARY KEY, user_id uuid NOT NULL REFERENCES users(id), request_id uuid NOT NULL,
    operator_login text NOT NULL, reference text NOT NULL, purpose text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);
-- statement
ALTER TABLE auth_mail_outbox ADD COLUMN dead_at timestamptz, ADD COLUMN error_code text,
    ADD COLUMN created_at timestamptz NOT NULL DEFAULT now();
-- statement
ALTER TABLE auth_events DROP CONSTRAINT IF EXISTS auth_events_action_check;
-- statement
ALTER TABLE auth_events ADD CONSTRAINT auth_events_action_check CHECK(action IN
 ('login.succeeded','login.failed','login.throttled','logout','reset.requested','password.reset',
  'mfa.enrollment_started','mfa.verified','mfa.failed','mfa.operator_authorized','mfa.recovered'));
-- statement
ALTER TABLE mfa_factors ADD COLUMN trust_verified boolean NOT NULL DEFAULT false;
-- statement
UPDATE sessions SET mfa_verified=false;
-- statement
REVOKE ALL ON users,sessions,password_resets,mfa_factors,login_attempts FROM maaher_runtime;
-- statement
REVOKE INSERT ON auth_mail_outbox FROM maaher_runtime;
-- statement
GRANT USAGE ON SCHEMA public TO maaher_auth,maaher_definer,maaher_mfa_operator,maaher_maintenance;
-- statement
GRANT SELECT ON users,tenants,memberships TO maaher_auth;
-- statement
GRANT UPDATE(password_hash) ON users TO maaher_auth;
-- statement
GRANT SELECT,INSERT,UPDATE,DELETE ON sessions,password_resets,mfa_requests,mfa_enrollments TO maaher_auth;
-- statement
GRANT SELECT,INSERT,UPDATE ON mfa_factors,auth_rate_buckets TO maaher_auth;
-- statement
GRANT INSERT ON auth_mail_outbox,auth_events TO maaher_auth;
-- statement
GRANT SELECT,INSERT,UPDATE ON invitations TO maaher_auth;
-- statement
GRANT INSERT ON audit_events TO maaher_auth;
-- statement
ALTER POLICY admin_invitations ON invitations TO maaher_runtime,maaher_auth;
-- statement
ALTER POLICY append_audit ON audit_events TO maaher_runtime,maaher_auth;
-- statement
GRANT SELECT ON auth_events TO maaher_auth;
-- statement
CREATE POLICY auth_memberships ON memberships FOR SELECT TO maaher_auth
USING (user_id::text=current_setting('app.user_id',true));
-- statement
CREATE POLICY auth_tenants ON tenants FOR SELECT TO maaher_auth USING (EXISTS (
    SELECT 1 FROM memberships WHERE memberships.tenant_id=tenants.id
    AND user_id::text=current_setting('app.user_id',true) AND status='active'));
-- statement
CREATE POLICY auth_factor ON mfa_factors TO maaher_auth
USING (user_id::text=current_setting('app.user_id',true))
WITH CHECK (user_id::text=current_setting('app.user_id',true));
-- statement
CREATE POLICY auth_history ON auth_events FOR SELECT TO maaher_auth
USING (user_id::text=current_setting('app.user_id',true));
-- statement
CREATE POLICY auth_append ON auth_events FOR INSERT TO maaher_auth WITH CHECK (true);
-- statement
GRANT INSERT ON users TO maaher_definer;
-- statement
GRANT SELECT(id,email,status) ON users TO maaher_definer;
-- statement
GRANT UPDATE(password_hash) ON users TO maaher_definer;
-- statement
GRANT SELECT,DELETE ON sessions,mfa_enrollments TO maaher_definer;
-- statement
GRANT SELECT,UPDATE,DELETE ON invitations,password_resets,mfa_requests TO maaher_definer;
-- statement
GRANT SELECT,INSERT,UPDATE ON memberships TO maaher_definer;
-- statement
GRANT SELECT ON tenants TO maaher_definer;
-- statement
GRANT SELECT(user_id,confirmed,trust_verified) ON mfa_factors TO maaher_definer;
-- statement
GRANT INSERT ON audit_events,auth_events TO maaher_definer;
-- statement
GRANT INSERT,SELECT,DELETE ON mfa_operator_audit TO maaher_definer;
-- statement
GRANT SELECT,DELETE ON auth_rate_buckets,login_attempts,auth_mail_outbox,auth_events,audit_events TO maaher_definer;
-- statement
DROP FUNCTION accept_invitation(text,text,uuid);
-- statement
DROP FUNCTION revoke_membership(uuid,uuid);
-- statement
CREATE FUNCTION resolve_session(p_hash text)
RETURNS TABLE(id uuid,mfa_verified boolean,mfa_required boolean,factor_confirmed boolean)
LANGUAGE sql STABLE SECURITY DEFINER SET search_path=pg_catalog,public,pg_temp AS $$
    SELECT u.id,s.mfa_verified,
      EXISTS(SELECT 1 FROM public.mfa_factors f WHERE f.user_id=u.id AND f.confirmed)
      OR EXISTS(SELECT 1 FROM public.memberships m JOIN public.tenants t ON t.id=m.tenant_id
                WHERE m.user_id=u.id AND m.role='admin' AND m.status='active' AND t.status='active'),
      EXISTS(SELECT 1 FROM public.mfa_factors f WHERE f.user_id=u.id AND f.confirmed AND f.trust_verified)
    FROM public.sessions s JOIN public.users u ON u.id=s.user_id
    WHERE s.token_hash=p_hash AND s.expires_at>now() AND u.status='active'
$$;
-- statement
CREATE FUNCTION authorize_mfa_request(p_request uuid,p_token text,p_reference text)
RETURNS boolean LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public,pg_temp AS $$
BEGIN
    -- No production bootstrap provider has been approved. A boolean environment
    -- flag or access to the compromised email cannot enable this test adapter.
    IF current_database() !~ '^maaher_test_' THEN RETURN false; END IF;
    IF length(p_reference)<8 OR length(p_reference)>120 THEN RETURN false; END IF;
    UPDATE public.mfa_requests r SET token_hash=p_token,approved_at=now(),operator_reference=p_reference
      WHERE r.id=p_request AND r.expires_at>now() AND r.approved_at IS NULL AND r.consumed_at IS NULL
      AND EXISTS(SELECT 1 FROM public.sessions s JOIN public.users u ON u.id=s.user_id
                 WHERE s.token_hash=r.session_hash AND s.expires_at>now() AND u.status='active');
    IF NOT FOUND THEN RETURN false; END IF;
    INSERT INTO public.auth_events(id,user_id,action)
      SELECT gen_random_uuid(),user_id,'mfa.operator_authorized' FROM public.mfa_requests WHERE id=p_request;
    INSERT INTO public.mfa_operator_audit(id,user_id,request_id,operator_login,reference,purpose)
      SELECT gen_random_uuid(),user_id,id,session_user::text,p_reference,purpose FROM public.mfa_requests WHERE id=p_request;
    RETURN true;
END $$;
-- statement
CREATE FUNCTION tenant_admin(p_hash text,p_tenant uuid) RETURNS uuid
LANGUAGE sql STABLE SECURITY DEFINER SET search_path=pg_catalog,public,pg_temp AS $$
    SELECT s.user_id FROM public.sessions s JOIN public.users u ON u.id=s.user_id
      JOIN public.mfa_factors f ON f.user_id=u.id JOIN public.memberships m ON m.user_id=u.id
      JOIN public.tenants t ON t.id=m.tenant_id
    WHERE s.token_hash=p_hash AND s.expires_at>now() AND s.mfa_verified AND f.confirmed AND f.trust_verified
      AND u.status='active' AND m.tenant_id=p_tenant AND m.status='active' AND m.role='admin' AND t.status='active'
$$;
-- statement
CREATE FUNCTION list_members(p_hash text,p_tenant uuid,p_after uuid DEFAULT NULL)
RETURNS TABLE(user_id uuid,email text,role text,status text)
LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path=pg_catalog,public,pg_temp AS $$
BEGIN
    IF public.tenant_admin(p_hash,p_tenant) IS NULL THEN RETURN; END IF;
    RETURN QUERY SELECT u.id,u.email,m.role,m.status FROM public.memberships m JOIN public.users u ON u.id=m.user_id
      WHERE m.tenant_id=p_tenant AND (p_after IS NULL OR u.id>p_after) ORDER BY u.id LIMIT 101;
END $$;
-- statement
CREATE FUNCTION change_member(p_hash text,p_tenant uuid,p_target uuid,p_role text)
RETURNS boolean LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public,pg_temp AS $$
DECLARE actor uuid;
BEGIN
    -- Serialize administrative changes per tenant, including last-admin protection.
    PERFORM pg_advisory_xact_lock(hashtextextended('tenant-admin:'||p_tenant::text,0));
    actor:=public.tenant_admin(p_hash,p_tenant);
    IF actor IS NULL OR p_target=actor OR p_role NOT IN ('student','teacher','admin','revoked') THEN RETURN false; END IF;
    IF p_role='revoked' THEN
      UPDATE public.memberships SET status='revoked' WHERE tenant_id=p_tenant AND user_id=p_target AND status='active';
    ELSE
      UPDATE public.memberships SET role=p_role WHERE tenant_id=p_tenant AND user_id=p_target AND status='active';
    END IF;
    IF NOT FOUND THEN RETURN false; END IF;
    IF p_role='revoked' THEN
      UPDATE public.invitations SET revoked_at=now() WHERE tenant_id=p_tenant AND consumed_at IS NULL
        AND email=(SELECT u.email FROM public.users u WHERE u.id=p_target);
    END IF;
    INSERT INTO public.audit_events(id,tenant_id,actor_id,action,target_type,target_id)
      VALUES(gen_random_uuid(),p_tenant,actor,CASE WHEN p_role='revoked' THEN 'membership.revoked' ELSE 'membership.role_changed' END,'user',p_target);
    RETURN true;
END $$;
-- statement
CREATE FUNCTION accept_invitation(p_token text,p_password text,p_session text)
RETURNS uuid LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public,pg_temp AS $$
DECLARE i public.invitations%ROWTYPE; u public.users%ROWTYPE; accepted uuid;
BEGIN
    SELECT * INTO i FROM public.invitations WHERE token_hash=p_token FOR UPDATE;
    IF NOT FOUND OR i.consumed_at IS NOT NULL OR i.revoked_at IS NOT NULL OR i.expires_at<=now()
       OR NOT EXISTS(SELECT 1 FROM public.tenants WHERE id=i.tenant_id AND status='active') THEN
      RAISE EXCEPTION 'invalid invitation' USING ERRCODE='P0001';
    END IF;
    PERFORM pg_advisory_xact_lock(hashtextextended('auth-email:'||i.email,0));
    PERFORM 1 FROM public.memberships WHERE tenant_id=i.tenant_id AND user_id=i.invited_by AND role='admin' AND status='active' FOR SHARE;
    IF NOT FOUND THEN RAISE EXCEPTION 'invalid invitation' USING ERRCODE='P0001'; END IF;
    SELECT id,email,NULL::text AS password_hash,status INTO u FROM public.users WHERE email=i.email FOR UPDATE;
    IF FOUND THEN
      SELECT id INTO accepted FROM public.resolve_session(p_session)
        WHERE NOT mfa_required OR (mfa_verified AND factor_confirmed);
      IF u.status<>'active' OR accepted IS DISTINCT FROM u.id THEN
        RAISE EXCEPTION 'sign in required' USING ERRCODE='P0001';
      END IF;
    ELSE
      IF p_password IS NULL THEN RAISE EXCEPTION 'password required' USING ERRCODE='P0001'; END IF;
      u.id:=gen_random_uuid();
      INSERT INTO public.users(id,email,password_hash) VALUES(u.id,i.email,p_password);
    END IF;
    IF EXISTS(SELECT 1 FROM public.memberships WHERE tenant_id=i.tenant_id AND user_id=u.id) THEN
      RAISE EXCEPTION 'membership already exists' USING ERRCODE='P0001';
    END IF;
    INSERT INTO public.memberships(id,tenant_id,user_id,role) VALUES(gen_random_uuid(),i.tenant_id,u.id,i.role);
    UPDATE public.invitations SET consumed_at=now() WHERE id=i.id;
    INSERT INTO public.audit_events(id,tenant_id,actor_id,action,target_type,target_id)
      VALUES(gen_random_uuid(),i.tenant_id,u.id,'invitation.accepted','invitation',i.id);
    RETURN i.tenant_id;
END $$;
-- statement
ALTER FUNCTION reset_password(text,text) SET search_path=pg_catalog,public,pg_temp;
-- statement
REVOKE EXECUTE ON FUNCTION reset_password(text,text) FROM maaher_runtime;
-- statement
GRANT EXECUTE ON FUNCTION reset_password(text,text) TO maaher_auth;
-- statement
CREATE FUNCTION retain_auth_data() RETURNS void
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public,pg_temp AS $$
BEGIN
    DELETE FROM public.sessions WHERE expires_at<=now();
    DELETE FROM public.password_resets WHERE expires_at<=now() OR consumed_at IS NOT NULL;
    DELETE FROM public.mfa_requests WHERE expires_at<=now() OR consumed_at<now()-interval '1 day';
    DELETE FROM public.mfa_enrollments WHERE expires_at<=now();
    DELETE FROM public.login_attempts WHERE window_start<now()-interval '1 day';
    DELETE FROM public.auth_rate_buckets WHERE window_start<now()-interval '1 day';
    DELETE FROM public.auth_events WHERE created_at<now()-interval '30 days';
    DELETE FROM public.audit_events WHERE created_at<now()-interval '365 days';
    DELETE FROM public.mfa_operator_audit WHERE created_at<now()-interval '365 days';
    DELETE FROM public.invitations WHERE expires_at<now()-interval '7 days';
    DELETE FROM public.auth_mail_outbox WHERE sent_at IS NOT NULL OR dead_at IS NOT NULL OR expires_at<=now();
END $$;
-- statement
DO $$
DECLARE fn regprocedure;
BEGIN
  -- No function retains a superuser owner. The NOLOGIN owner has only explicit table grants.
  FOR fn IN SELECT p.oid::regprocedure FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
    WHERE n.nspname='public' AND p.proname IN ('resolve_session','authorize_mfa_request','tenant_admin','list_members',
      'change_member','accept_invitation','reset_password','retain_auth_data') LOOP
    EXECUTE format('ALTER FUNCTION %s OWNER TO maaher_definer',fn);
    EXECUTE format('REVOKE ALL ON FUNCTION %s FROM PUBLIC',fn);
  END LOOP;
END $$;
-- statement
GRANT EXECUTE ON FUNCTION resolve_session(text) TO maaher_runtime,maaher_auth;
-- statement
GRANT EXECUTE ON FUNCTION list_members(text,uuid,uuid),change_member(text,uuid,uuid,text) TO maaher_runtime;
-- statement
GRANT EXECUTE ON FUNCTION accept_invitation(text,text,text) TO maaher_auth;
-- statement
GRANT EXECUTE ON FUNCTION authorize_mfa_request(uuid,text,text) TO maaher_mfa_operator;
-- statement
GRANT EXECUTE ON FUNCTION retain_auth_data() TO maaher_maintenance;
-- statement
REVOKE ALL ON FUNCTION tenant_admin(text,uuid) FROM maaher_runtime,maaher_auth;
-- statement
CREATE FUNCTION runtime_identity() RETURNS uuid LANGUAGE sql STABLE SECURITY DEFINER
SET search_path=pg_catalog,public,pg_temp AS $$
  SELECT id FROM public.resolve_session(current_setting('app.session_hash',true))
  WHERE NOT mfa_required OR (mfa_verified AND factor_confirmed)
$$;
-- statement
ALTER FUNCTION runtime_identity() OWNER TO maaher_definer;
-- statement
REVOKE ALL ON FUNCTION runtime_identity() FROM PUBLIC;
-- statement
GRANT EXECUTE ON FUNCTION runtime_identity() TO maaher_runtime;
-- statement
ALTER POLICY own_memberships ON memberships USING (user_id=public.runtime_identity() AND status='active');
-- statement
ALTER POLICY member_tenants ON tenants USING (status='active' AND EXISTS(
  SELECT 1 FROM memberships m WHERE m.tenant_id=tenants.id AND m.user_id=public.runtime_identity() AND m.status='active'));
-- statement
ALTER POLICY tenant_audit ON audit_events USING (tenant_id::text=current_setting('app.tenant_id',true) AND EXISTS(
  SELECT 1 FROM memberships m JOIN tenants t ON t.id=m.tenant_id WHERE m.tenant_id=audit_events.tenant_id
  AND m.user_id=public.runtime_identity() AND m.status='active' AND m.role='admin'));
-- statement
ALTER POLICY append_audit ON audit_events TO maaher_runtime
WITH CHECK (tenant_id::text=current_setting('app.tenant_id',true) AND actor_id=public.runtime_identity() AND EXISTS(
  SELECT 1 FROM memberships m JOIN tenants t ON t.id=m.tenant_id WHERE m.tenant_id=audit_events.tenant_id
  AND m.user_id=public.runtime_identity() AND m.status='active'));
-- statement
CREATE POLICY auth_tenant_audit ON audit_events FOR INSERT TO maaher_auth WITH CHECK(
  tenant_id::text=current_setting('app.tenant_id',true) AND actor_id::text=current_setting('app.user_id',true)
  AND EXISTS(SELECT 1 FROM memberships m JOIN tenants t ON t.id=m.tenant_id
    WHERE m.tenant_id=audit_events.tenant_id AND m.user_id::text=current_setting('app.user_id',true)
    AND m.status='active'));
-- statement
ALTER POLICY admin_invitations ON invitations TO maaher_runtime
USING (tenant_id::text=current_setting('app.tenant_id',true) AND EXISTS(
  SELECT 1 FROM memberships m JOIN tenants t ON t.id=m.tenant_id WHERE m.tenant_id=invitations.tenant_id
  AND m.user_id=public.runtime_identity() AND m.role='admin' AND m.status='active'))
WITH CHECK (tenant_id::text=current_setting('app.tenant_id',true) AND invited_by=public.runtime_identity() AND EXISTS(
  SELECT 1 FROM memberships m JOIN tenants t ON t.id=m.tenant_id WHERE m.tenant_id=invitations.tenant_id
  AND m.user_id=public.runtime_identity() AND m.role='admin' AND m.status='active'));
-- statement
CREATE POLICY auth_invitations ON invitations TO maaher_auth
USING (tenant_id::text=current_setting('app.tenant_id',true) AND EXISTS(
  SELECT 1 FROM memberships m JOIN tenants t ON t.id=m.tenant_id WHERE m.tenant_id=invitations.tenant_id
  AND m.user_id::text=current_setting('app.user_id',true) AND m.role='admin' AND m.status='active'))
WITH CHECK (tenant_id::text=current_setting('app.tenant_id',true) AND invited_by::text=current_setting('app.user_id',true) AND EXISTS(
  SELECT 1 FROM memberships m JOIN tenants t ON t.id=m.tenant_id WHERE m.tenant_id=invitations.tenant_id
  AND m.user_id::text=current_setting('app.user_id',true) AND m.role='admin' AND m.status='active'));
-- statement
REVOKE SELECT ON auth_events FROM maaher_runtime;
