CREATE TABLE users (
    id uuid PRIMARY KEY,
    email text NOT NULL UNIQUE CHECK (email = lower(email)),
    password_hash text NOT NULL,
    status text NOT NULL DEFAULT 'active' CHECK (status IN ('active','disabled'))
);
CREATE TABLE tenants (
    id uuid PRIMARY KEY,
    slug text NOT NULL UNIQUE,
    name text NOT NULL,
    status text NOT NULL DEFAULT 'active' CHECK (status IN ('active','disabled'))
);
CREATE TABLE memberships (
    id uuid PRIMARY KEY,
    tenant_id uuid NOT NULL REFERENCES tenants(id),
    user_id uuid NOT NULL REFERENCES users(id),
    role text NOT NULL CHECK (role IN ('student','teacher','admin')),
    status text NOT NULL DEFAULT 'active' CHECK (status IN ('active','revoked')),
    UNIQUE (tenant_id,user_id)
);
CREATE TABLE sessions (
    token_hash text PRIMARY KEY,
    user_id uuid NOT NULL REFERENCES users(id),
    expires_at timestamptz NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX sessions_expiry ON sessions(expires_at);
CREATE TABLE login_attempts (
    email_hash text PRIMARY KEY,
    attempts integer NOT NULL DEFAULT 0,
    window_start timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE audit_events (
    id uuid PRIMARY KEY,
    tenant_id uuid NOT NULL REFERENCES tenants(id),
    actor_id uuid NOT NULL REFERENCES users(id),
    action text NOT NULL CHECK (length(action) <= 80),
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX audit_events_tenant ON audit_events(tenant_id,created_at);
ALTER TABLE memberships ENABLE ROW LEVEL SECURITY;
ALTER TABLE memberships FORCE ROW LEVEL SECURITY;
CREATE POLICY own_memberships ON memberships FOR SELECT TO maaher_runtime
    USING (user_id::text = current_setting('app.user_id',true) AND status='active');
ALTER TABLE tenants ENABLE ROW LEVEL SECURITY;
ALTER TABLE tenants FORCE ROW LEVEL SECURITY;
CREATE POLICY member_tenants ON tenants FOR SELECT TO maaher_runtime
    USING (status='active' AND EXISTS (
        SELECT 1 FROM memberships m WHERE m.tenant_id=tenants.id
        AND m.user_id::text=current_setting('app.user_id',true) AND m.status='active'
    ));
ALTER TABLE audit_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_events FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_audit ON audit_events FOR SELECT TO maaher_runtime
    USING (tenant_id::text=current_setting('app.tenant_id',true) AND EXISTS (
        SELECT 1 FROM memberships m JOIN tenants t ON t.id=m.tenant_id
        WHERE m.tenant_id=audit_events.tenant_id AND m.status='active'
        AND m.user_id::text=current_setting('app.user_id',true) AND m.role='admin'
    ));
CREATE POLICY append_audit ON audit_events FOR INSERT TO maaher_runtime
    WITH CHECK (tenant_id::text=current_setting('app.tenant_id',true)
        AND actor_id::text=current_setting('app.user_id',true) AND EXISTS (
            SELECT 1 FROM memberships m JOIN tenants t ON t.id=m.tenant_id
            WHERE m.tenant_id=audit_events.tenant_id AND m.status='active'
            AND m.user_id::text=current_setting('app.user_id',true)
        ));
REVOKE ALL ON users,tenants,memberships,sessions,login_attempts,audit_events FROM PUBLIC;
GRANT USAGE ON SCHEMA public TO maaher_runtime;
GRANT SELECT ON users,tenants,memberships,audit_events TO maaher_runtime;
GRANT SELECT,INSERT,DELETE ON sessions TO maaher_runtime;
GRANT SELECT,INSERT,UPDATE ON login_attempts TO maaher_runtime;
GRANT INSERT ON audit_events TO maaher_runtime;
