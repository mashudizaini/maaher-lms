CREATE TABLE oidc_identities (
    id uuid PRIMARY KEY, user_id uuid NOT NULL REFERENCES users(id),
    issuer text NOT NULL, subject text NOT NULL CHECK (length(subject) BETWEEN 1 AND 255),
    is_operator boolean NOT NULL DEFAULT false,
    status text NOT NULL DEFAULT 'active' CHECK (status IN ('active','revoked')),
    provision_reference text NOT NULL CHECK (length(provision_reference) BETWEEN 8 AND 120),
    created_at timestamptz NOT NULL DEFAULT now(), UNIQUE(issuer,subject)
);
-- statement
CREATE INDEX oidc_identities_user ON oidc_identities(user_id);
-- statement
CREATE TABLE oidc_login_flows (
    browser_hash text PRIMARY KEY, state_hash text UNIQUE NOT NULL,
    encrypted_state text NOT NULL, config_hash text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(), expires_at timestamptz NOT NULL
);
-- statement
CREATE TABLE oidc_sessions (
    token_hash text PRIMARY KEY REFERENCES sessions(token_hash) ON DELETE CASCADE,
    identity_id uuid NOT NULL REFERENCES oidc_identities(id),
    authenticated_at timestamptz NOT NULL,
    assurance text NOT NULL CHECK (assurance='maaher-fido2-uv-v1')
);
-- statement
REVOKE ALL ON oidc_identities,oidc_login_flows,oidc_sessions FROM PUBLIC,maaher_runtime;
-- statement
GRANT SELECT ON oidc_identities TO maaher_auth,maaher_definer;
-- statement
GRANT SELECT,INSERT,DELETE ON oidc_login_flows TO maaher_auth;
-- statement
GRANT DELETE ON oidc_login_flows TO maaher_definer;
-- statement
GRANT SELECT(expires_at) ON oidc_login_flows TO maaher_definer;
-- statement
GRANT SELECT,INSERT ON oidc_sessions TO maaher_auth;
-- statement
GRANT SELECT ON oidc_sessions TO maaher_definer;
-- statement
CREATE OR REPLACE FUNCTION resolve_session(p_hash text)
RETURNS TABLE(id uuid,mfa_verified boolean,mfa_required boolean,factor_confirmed boolean)
LANGUAGE sql STABLE SECURITY DEFINER SET search_path=pg_catalog,public,pg_temp AS $$
    SELECT u.id,s.mfa_verified,
      EXISTS(SELECT 1 FROM public.oidc_identities i WHERE i.user_id=u.id)
      OR EXISTS(SELECT 1 FROM public.mfa_factors f WHERE f.user_id=u.id AND f.confirmed)
      OR EXISTS(SELECT 1 FROM public.memberships m JOIN public.tenants t ON t.id=m.tenant_id
                WHERE m.user_id=u.id AND m.role='admin' AND m.status='active' AND t.status='active'),
      CASE WHEN EXISTS(SELECT 1 FROM public.oidc_identities i WHERE i.user_id=u.id)
        THEN EXISTS(SELECT 1 FROM public.oidc_sessions o JOIN public.oidc_identities i ON i.id=o.identity_id
                    WHERE o.token_hash=s.token_hash AND i.user_id=u.id AND i.status='active')
        ELSE EXISTS(SELECT 1 FROM public.mfa_factors f WHERE f.user_id=u.id AND f.confirmed AND f.trust_verified)
      END
    FROM public.sessions s JOIN public.users u ON u.id=s.user_id
    WHERE s.token_hash=p_hash AND s.expires_at>now() AND u.status='active'
      AND (NOT EXISTS(SELECT 1 FROM public.oidc_identities i WHERE i.user_id=u.id)
           OR EXISTS(SELECT 1 FROM public.oidc_sessions o JOIN public.oidc_identities i ON i.id=o.identity_id
                     WHERE o.token_hash=s.token_hash AND i.user_id=u.id AND i.status='active'))
$$;
-- statement
CREATE OR REPLACE FUNCTION tenant_admin(p_hash text,p_tenant uuid) RETURNS uuid
LANGUAGE sql STABLE SECURITY DEFINER SET search_path=pg_catalog,public,pg_temp AS $$
    SELECT r.id FROM public.resolve_session(p_hash) r JOIN public.memberships m ON m.user_id=r.id
      JOIN public.tenants t ON t.id=m.tenant_id
    WHERE r.mfa_verified AND r.factor_confirmed
      AND m.tenant_id=p_tenant AND m.status='active' AND m.role='admin' AND t.status='active'
$$;
-- statement
CREATE OR REPLACE FUNCTION reset_password(p_token text,p_password text) RETURNS boolean
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public,pg_temp AS $$
DECLARE uid uuid;
BEGIN
    SELECT user_id INTO uid FROM public.password_resets WHERE token_hash=p_token;
    IF NOT FOUND THEN RETURN false; END IF;
    PERFORM pg_advisory_xact_lock(hashtextextended('auth-email:'||(SELECT email FROM public.users WHERE id=uid),0));
    PERFORM 1 FROM public.users WHERE id=uid AND status='active' FOR UPDATE;
    IF NOT FOUND OR EXISTS(SELECT 1 FROM public.oidc_identities WHERE user_id=uid) THEN RETURN false; END IF;
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
CREATE OR REPLACE FUNCTION retain_auth_data() RETURNS void
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public,pg_temp AS $$
BEGIN
    DELETE FROM public.oidc_login_flows WHERE expires_at<=now();
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
