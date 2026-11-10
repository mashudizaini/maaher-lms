ALTER TABLE sessions ADD COLUMN mfa_verified boolean NOT NULL DEFAULT false;
-- statement
ALTER TABLE audit_events ADD COLUMN target_type text, ADD COLUMN target_id uuid;
-- statement
CREATE TABLE invitations (
    id uuid PRIMARY KEY,
    tenant_id uuid NOT NULL REFERENCES tenants(id),
    invited_by uuid NOT NULL REFERENCES users(id),
    email text NOT NULL CHECK (email=lower(email)),
    role text NOT NULL CHECK (role IN ('student','teacher','admin')),
    token_hash text NOT NULL UNIQUE,
    expires_at timestamptz NOT NULL,
    consumed_at timestamptz,
    revoked_at timestamptz
);
-- statement
CREATE INDEX invitations_tenant ON invitations(tenant_id,email);
-- statement
ALTER TABLE invitations ENABLE ROW LEVEL SECURITY;
-- statement
ALTER TABLE invitations FORCE ROW LEVEL SECURITY;
-- statement
CREATE POLICY admin_invitations ON invitations TO maaher_runtime
USING (tenant_id::text=current_setting('app.tenant_id',true) AND EXISTS (
    SELECT 1 FROM memberships m JOIN tenants t ON t.id=m.tenant_id
    WHERE m.tenant_id=invitations.tenant_id AND m.role='admin'
      AND m.user_id::text=current_setting('app.user_id',true)))
WITH CHECK (tenant_id::text=current_setting('app.tenant_id',true)
    AND invited_by::text=current_setting('app.user_id',true) AND EXISTS (
    SELECT 1 FROM memberships m JOIN tenants t ON t.id=m.tenant_id
    WHERE m.tenant_id=invitations.tenant_id AND m.role='admin'
      AND m.user_id::text=current_setting('app.user_id',true)));
-- statement
GRANT SELECT,INSERT,UPDATE ON invitations TO maaher_runtime;
-- statement
CREATE TABLE password_resets (
    token_hash text PRIMARY KEY,
    user_id uuid NOT NULL REFERENCES users(id),
    expires_at timestamptz NOT NULL,
    consumed_at timestamptz
);
-- statement
CREATE INDEX password_resets_user ON password_resets(user_id);
-- statement
GRANT SELECT,INSERT,UPDATE,DELETE ON password_resets TO maaher_runtime;
-- statement
CREATE TABLE mfa_factors (
    user_id uuid PRIMARY KEY REFERENCES users(id),
    encrypted_secret text NOT NULL,
    confirmed boolean NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL DEFAULT now(),
    last_counter bigint NOT NULL DEFAULT -1
);
-- statement
ALTER TABLE mfa_factors ENABLE ROW LEVEL SECURITY;
-- statement
ALTER TABLE mfa_factors FORCE ROW LEVEL SECURITY;
-- statement
CREATE POLICY own_factor ON mfa_factors TO maaher_runtime
USING (user_id::text=current_setting('app.user_id',true))
WITH CHECK (user_id::text=current_setting('app.user_id',true));
-- statement
GRANT SELECT,INSERT,UPDATE ON mfa_factors TO maaher_runtime;
-- statement
CREATE TABLE auth_events (
    id uuid PRIMARY KEY,
    user_id uuid REFERENCES users(id),
    action text NOT NULL CHECK (action IN ('login.succeeded','login.failed','login.throttled',
      'logout','reset.requested','password.reset','mfa.enrollment_started','mfa.verified','mfa.failed')),
    created_at timestamptz NOT NULL DEFAULT now()
);
-- statement
CREATE INDEX auth_events_user ON auth_events(user_id,created_at);
-- statement
ALTER TABLE auth_events ENABLE ROW LEVEL SECURITY;
-- statement
ALTER TABLE auth_events FORCE ROW LEVEL SECURITY;
-- statement
CREATE POLICY own_auth_events ON auth_events FOR SELECT TO maaher_runtime
USING (user_id::text=current_setting('app.user_id',true));
-- statement
CREATE POLICY append_auth_events ON auth_events FOR INSERT TO maaher_runtime WITH CHECK (true);
-- statement
GRANT SELECT,INSERT ON auth_events TO maaher_runtime;
-- statement
CREATE TABLE auth_mail_outbox (
    id uuid PRIMARY KEY,
    recipient text NOT NULL,
    kind text NOT NULL CHECK (kind IN ('invitation','password-reset')),
    encrypted_token text,
    expires_at timestamptz NOT NULL,
    sent_at timestamptz,
    next_attempt_at timestamptz NOT NULL DEFAULT now(),
    attempts integer NOT NULL DEFAULT 0
);
-- statement
GRANT USAGE ON SCHEMA public TO maaher_mailer;
-- statement
GRANT SELECT,UPDATE ON auth_mail_outbox TO maaher_mailer;
-- statement
GRANT INSERT ON auth_mail_outbox TO maaher_runtime;
-- statement
CREATE FUNCTION accept_invitation(p_token text, p_password text, p_user uuid)
RETURNS uuid LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public AS $$
DECLARE i public.invitations%ROWTYPE; u public.users%ROWTYPE;
BEGIN
    SELECT * INTO i FROM public.invitations WHERE token_hash=p_token FOR UPDATE;
    IF NOT FOUND OR i.consumed_at IS NOT NULL OR i.revoked_at IS NOT NULL OR i.expires_at<=now()
       OR NOT EXISTS (SELECT 1 FROM public.tenants WHERE id=i.tenant_id AND status='active') THEN
        RAISE EXCEPTION 'invalid invitation' USING ERRCODE='P0001';
    END IF;
    -- Serialize accepts for the same email, including invitations from other tenants.
    PERFORM pg_advisory_xact_lock(hashtextextended('auth-email:'||i.email,0));
    PERFORM 1 FROM public.memberships WHERE tenant_id=i.tenant_id AND user_id=i.invited_by
        AND role='admin' AND status='active' FOR SHARE;
    IF NOT FOUND THEN RAISE EXCEPTION 'invalid invitation' USING ERRCODE='P0001'; END IF;
    SELECT * INTO u FROM public.users WHERE email=i.email FOR UPDATE;
    IF FOUND THEN
        IF u.status<>'active' OR p_user IS DISTINCT FROM u.id
           OR current_setting('app.user_id',true) IS DISTINCT FROM u.id::text THEN
            RAISE EXCEPTION 'sign in required' USING ERRCODE='P0001';
        END IF;
    ELSE
        IF p_user IS NOT NULL OR p_password IS NULL THEN
            RAISE EXCEPTION 'invalid invitation' USING ERRCODE='P0001';
        END IF;
        u.id := gen_random_uuid();
        INSERT INTO public.users(id,email,password_hash) VALUES (u.id,i.email,p_password);
    END IF;
    -- An invitation cannot overwrite an existing role or reactivate revoked access.
    IF EXISTS (SELECT 1 FROM public.memberships WHERE tenant_id=i.tenant_id AND user_id=u.id) THEN
        RAISE EXCEPTION 'membership already exists' USING ERRCODE='P0001';
    END IF;
    INSERT INTO public.memberships(id,tenant_id,user_id,role)
        VALUES (gen_random_uuid(),i.tenant_id,u.id,i.role);
    UPDATE public.invitations SET consumed_at=now() WHERE id=i.id;
    INSERT INTO public.audit_events(id,tenant_id,actor_id,action,target_type,target_id)
        VALUES (gen_random_uuid(),i.tenant_id,u.id,'invitation.accepted','invitation',i.id);
    RETURN i.tenant_id;
END $$;
-- statement
REVOKE ALL ON FUNCTION accept_invitation(text,text,uuid) FROM PUBLIC;
-- statement
GRANT EXECUTE ON FUNCTION accept_invitation(text,text,uuid) TO maaher_runtime;
-- statement
CREATE FUNCTION reset_password(p_token text,p_password text) RETURNS boolean
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public AS $$
DECLARE uid uuid;
BEGIN
    SELECT user_id INTO uid FROM public.password_resets WHERE token_hash=p_token;
    IF NOT FOUND THEN RETURN false; END IF;
    PERFORM pg_advisory_xact_lock(hashtextextended('auth-email:'||(SELECT email FROM public.users WHERE id=uid),0));
    PERFORM 1 FROM public.users WHERE id=uid AND status='active' FOR UPDATE;
    IF NOT FOUND THEN RETURN false; END IF;
    UPDATE public.password_resets SET consumed_at=now()
        WHERE token_hash=p_token AND consumed_at IS NULL AND expires_at>now();
    IF NOT FOUND THEN RETURN false; END IF;
    UPDATE public.users SET password_hash=p_password WHERE id=uid;
    DELETE FROM public.sessions WHERE user_id=uid;
    DELETE FROM public.password_resets WHERE user_id=uid;
    INSERT INTO public.auth_events(id,user_id,action) VALUES(gen_random_uuid(),uid,'password.reset');
    RETURN true;
END $$;
-- statement
REVOKE ALL ON FUNCTION reset_password(text,text) FROM PUBLIC;
-- statement
GRANT EXECUTE ON FUNCTION reset_password(text,text) TO maaher_runtime;
-- statement
CREATE FUNCTION revoke_membership(p_tenant uuid,p_target uuid) RETURNS boolean
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public AS $$
DECLARE actor uuid;
BEGIN
    actor := nullif(current_setting('app.user_id',true),'')::uuid;
    IF p_tenant::text IS DISTINCT FROM current_setting('app.tenant_id',true)
       OR p_target=actor THEN RETURN false; END IF;
    PERFORM 1 FROM public.memberships m JOIN public.tenants t ON t.id=m.tenant_id
      WHERE m.tenant_id=p_tenant AND m.user_id=actor AND m.role='admin'
        AND m.status='active' AND t.status='active' FOR SHARE OF m,t;
    IF NOT FOUND THEN RETURN false; END IF;
    UPDATE public.memberships SET status='revoked'
      WHERE tenant_id=p_tenant AND user_id=p_target AND status='active';
    IF NOT FOUND THEN RETURN false; END IF;
    UPDATE public.invitations SET revoked_at=now() WHERE tenant_id=p_tenant
      AND email=(SELECT email FROM public.users WHERE id=p_target) AND consumed_at IS NULL;
    INSERT INTO public.audit_events(id,tenant_id,actor_id,action,target_type,target_id)
      VALUES(gen_random_uuid(),p_tenant,actor,'membership.revoked','user',p_target);
    RETURN true;
END $$;
-- statement
REVOKE ALL ON FUNCTION revoke_membership(uuid,uuid) FROM PUBLIC;
-- statement
GRANT EXECUTE ON FUNCTION revoke_membership(uuid,uuid) TO maaher_runtime;
