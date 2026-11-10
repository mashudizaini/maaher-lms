DROP POLICY own_memberships ON memberships;
-- statement
CREATE POLICY own_memberships ON memberships FOR SELECT TO maaher_runtime
    USING (user_id::text = current_setting('app.user_id',true) AND status='active');
-- statement
DROP POLICY member_tenants ON tenants;
-- statement
CREATE POLICY member_tenants ON tenants FOR SELECT TO maaher_runtime
    USING (status='active' AND EXISTS (
        SELECT 1 FROM memberships m WHERE m.tenant_id=tenants.id
        AND m.user_id::text=current_setting('app.user_id',true) AND m.status='active'
    ));
-- statement
DROP POLICY tenant_audit ON audit_events;
-- statement
CREATE POLICY tenant_audit ON audit_events FOR SELECT TO maaher_runtime
    USING (tenant_id::text=current_setting('app.tenant_id',true) AND EXISTS (
        SELECT 1 FROM memberships m JOIN tenants t ON t.id=m.tenant_id
        WHERE m.tenant_id=audit_events.tenant_id AND m.status='active'
        AND m.user_id::text=current_setting('app.user_id',true) AND m.role='admin'
    ));
-- statement
DROP POLICY append_audit ON audit_events;
-- statement
CREATE POLICY append_audit ON audit_events FOR INSERT TO maaher_runtime
    WITH CHECK (tenant_id::text=current_setting('app.tenant_id',true)
        AND actor_id::text=current_setting('app.user_id',true) AND EXISTS (
            SELECT 1 FROM memberships m JOIN tenants t ON t.id=m.tenant_id
            WHERE m.tenant_id=audit_events.tenant_id AND m.status='active'
            AND m.user_id::text=current_setting('app.user_id',true)
        ));
-- statement
DROP POLICY admin_invitations ON invitations;
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
DROP POLICY auth_tenant_audit ON audit_events;
-- statement
DROP POLICY auth_invitations ON invitations;
-- statement
DROP FUNCTION runtime_identity();
-- statement
GRANT SELECT ON auth_events TO maaher_runtime;
-- statement
DROP FUNCTION resolve_session(text),authorize_mfa_request(uuid,text,text),list_members(text,uuid,uuid),change_member(text,uuid,uuid,text),accept_invitation(text,text,text),retain_auth_data();
-- statement
DROP FUNCTION tenant_admin(text,uuid);
-- statement
DO $$ BEGIN EXECUTE format('ALTER FUNCTION reset_password(text,text) OWNER TO %I',current_user); END $$;
-- statement
DROP FUNCTION reset_password(text,text);
-- statement
DROP POLICY auth_memberships ON memberships;
-- statement
DROP POLICY auth_tenants ON tenants;
-- statement
DROP POLICY auth_factor ON mfa_factors;
-- statement
DROP POLICY auth_history ON auth_events;
-- statement
DROP POLICY auth_append ON auth_events;
-- statement
ALTER POLICY admin_invitations ON invitations TO maaher_runtime;
-- statement
ALTER POLICY append_audit ON audit_events TO maaher_runtime;
-- statement
REVOKE ALL ON users,tenants,memberships,sessions,invitations,password_resets,mfa_factors,mfa_requests,mfa_enrollments,auth_rate_buckets,login_attempts,auth_mail_outbox,auth_events,audit_events FROM maaher_auth,maaher_definer;
-- statement
REVOKE UPDATE(password_hash) ON users FROM maaher_auth,maaher_definer;
-- statement
REVOKE SELECT(id,email,status) ON users FROM maaher_definer;
-- statement
REVOKE SELECT(user_id,confirmed,trust_verified) ON mfa_factors FROM maaher_definer;
-- statement
DROP TABLE mfa_enrollments,mfa_requests,auth_rate_buckets,mfa_operator_audit;
-- statement
ALTER TABLE auth_mail_outbox DROP COLUMN dead_at,DROP COLUMN error_code,DROP COLUMN created_at;
-- statement
ALTER TABLE mfa_factors DROP COLUMN trust_verified;
-- statement
GRANT SELECT ON users TO maaher_runtime;
-- statement
GRANT SELECT,INSERT,DELETE ON sessions TO maaher_runtime;
-- statement
GRANT SELECT,INSERT,UPDATE,DELETE ON password_resets TO maaher_runtime;
-- statement
GRANT SELECT,INSERT,UPDATE ON mfa_factors,login_attempts TO maaher_runtime;
-- statement
GRANT INSERT ON auth_mail_outbox TO maaher_runtime;
