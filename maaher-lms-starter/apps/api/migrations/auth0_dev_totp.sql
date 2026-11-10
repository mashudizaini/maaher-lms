ALTER TABLE oidc_sessions DROP CONSTRAINT oidc_sessions_assurance_check;
-- statement
ALTER TABLE oidc_sessions ADD CONSTRAINT oidc_sessions_assurance_check
    CHECK (assurance IN ('maaher-fido2-uv-v1','maaher-dev-totp-v1'));
-- statement
ALTER TABLE oidc_sessions ADD CONSTRAINT oidc_sessions_dev_database_check
    CHECK (assurance<>'maaher-dev-totp-v1' OR starts_with(current_database(),'maaher_test_'));
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
                    WHERE o.token_hash=s.token_hash AND i.user_id=u.id AND i.status='active'
                      AND o.assurance=coalesce(current_setting('app.oidc_assurance',true),'maaher-fido2-uv-v1')
                      AND (o.assurance='maaher-fido2-uv-v1'
                           OR (o.assurance='maaher-dev-totp-v1' AND starts_with(current_database(),'maaher_test_'))))
        ELSE EXISTS(SELECT 1 FROM public.mfa_factors f WHERE f.user_id=u.id AND f.confirmed AND f.trust_verified)
      END
    FROM public.sessions s JOIN public.users u ON u.id=s.user_id
    WHERE s.token_hash=p_hash AND s.expires_at>now() AND u.status='active'
      AND (NOT EXISTS(SELECT 1 FROM public.oidc_identities i WHERE i.user_id=u.id)
           OR EXISTS(SELECT 1 FROM public.oidc_sessions o JOIN public.oidc_identities i ON i.id=o.identity_id
                     WHERE o.token_hash=s.token_hash AND i.user_id=u.id AND i.status='active'
                       AND o.assurance=coalesce(current_setting('app.oidc_assurance',true),'maaher-fido2-uv-v1')
                       AND (o.assurance='maaher-fido2-uv-v1'
                            OR (o.assurance='maaher-dev-totp-v1' AND starts_with(current_database(),'maaher_test_')))))
$$;
