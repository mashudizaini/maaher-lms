"""Auth0 staff login using Authlib OIDC and private, one-use database state.

No email linking, provider token persistence, public provisioning or operator
recovery approval is exposed here. Bound staff have no local-auth fallback.
"""
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
import json
import os
import re
import time
from urllib.parse import urlsplit
from uuid import uuid4

from authlib.integrations.starlette_client import OAuth, OAuthError
from cryptography.fernet import InvalidToken
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from httpx import HTTPError
from joserfc.errors import JoseError

from .auth import COOKIE, SESSION_SECONDS, auth_connection, secure_cookie, session_user, verify_origin
from .auth_support import cipher, reserve_session_slot, security_event
from .database import auth_transaction, user_context
from .security import new_token, token_digest
from .oidc_policy import FIDO2_ASSURANCE, DEV_TOTP_ASSURANCE, configured_assurance

router = APIRouter(prefix="/auth/oidc")
FLOW_COOKIE = "maaher_oidc_flow"
FLOW_SECONDS = 300
STAFF_SESSION_SECONDS = 30 * 60
ASSURANCE_CLAIM = "https://maaherlms.aimz.my.id/assurance"
ASSURANCE = FIDO2_ASSURANCE


@dataclass(frozen=True)
class Settings:
    issuer: str
    client_id: str
    client_secret: str = field(repr=False)
    origin: str
    assurance: str = FIDO2_ASSURANCE

    @property
    def callback(self):
        return self.origin + "/api/auth/oidc/callback"

    @property
    def fingerprint(self):
        return token_digest(json.dumps([self.issuer, self.client_id, self.callback, self.assurance]))


def settings():
    domain = os.environ.get("AUTH0_DOMAIN", "")
    client_id = os.environ.get("AUTH0_CLIENT_ID", "")
    secret = os.environ.get("AUTH0_CLIENT_SECRET", "")
    origin = os.environ.get("APP_ORIGIN", "")
    assurance = configured_assurance()
    try:
        parsed = urlsplit(origin)
        parsed.port
    except ValueError:
        raise HTTPException(503, "Login Auth0 belum dikonfigurasi") from None
    local = os.environ.get("APP_ENV") == "local" and parsed.hostname in {"127.0.0.1", "localhost"}
    if (not assurance
            or not re.fullmatch(r"(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+auth0\.com", domain)
            or len(domain) > 253 or not 3 <= len(client_id) <= 128
            or not client_id.isascii() or any(c.isspace() for c in client_id) or not secret
            or not parsed.hostname or parsed.username or parsed.password or parsed.path
            or parsed.query or parsed.fragment
            or not (parsed.scheme == "https" or (local and parsed.scheme == "http"))):
        raise HTTPException(503, "Login Auth0 belum dikonfigurasi")
    return Settings("https://" + domain + "/", client_id, secret, origin, assurance)


def require_policy_database(config, db):
    if (config.assurance == DEV_TOTP_ASSURANCE
            and not db.execute("SELECT current_database() AS name").fetchone()["name"].startswith("maaher_test_")):
        raise HTTPException(503, "TOTP development hanya untuk database sintetis maaher_test_*")


def make_client(config):
    # Pin Auth0 endpoints/issuer/RS256. Never discover URLs from tokens or clients.
    # A new client avoids sharing mutable state across concurrent requests.
    return OAuth().register(
        "auth0", client_id=config.client_id, client_secret=config.client_secret,
        authorize_url=config.issuer + "authorize",
        access_token_url=config.issuer + "oauth/token",
        issuer=config.issuer, jwks_uri=config.issuer + ".well-known/jwks.json",
        id_token_signing_alg_values_supported=["RS256"],
        client_kwargs={"scope": "openid", "code_challenge_method": "S256",
                       "token_endpoint_auth_method": "client_secret_basic",
                       "timeout": 10, "follow_redirects": False},
    )


def clear_flow(response):
    response.delete_cookie(FLOW_COOKIE, path="/", secure=secure_cookie(), httponly=True, samesite="lax")


def denied():
    response = JSONResponse({"detail": "Login Auth0 tidak berlaku atau tidak diizinkan"}, status_code=400)
    clear_flow(response)
    return response


@router.get("/config")
def configuration():
    try:
        config = settings()
    except HTTPException:
        return {"enabled": False}
    return {"enabled": True, "assurance": config.assurance}


@router.post("/login", dependencies=[Depends(verify_origin)])
async def start(request: Request, response: Response, config=Depends(settings),
                db=Depends(auth_connection, scope="function")):
    require_policy_database(config, db)
    client = make_client(config)
    data = await client.create_authorization_url(config.callback, nonce=new_token(), prompt="login", max_age="0")
    request.scope["session"] = {}
    await client.save_authorize_data(request, redirect_uri=config.callback, **data)
    encrypted = cipher().encrypt(json.dumps(request.session).encode()).decode()
    browser = new_token()
    db.execute("DELETE FROM oidc_login_flows WHERE expires_at<=now() OR browser_hash=%s",
               (token_digest(request.cookies.get(FLOW_COOKIE, "")),))
    db.execute("""INSERT INTO oidc_login_flows(browser_hash,state_hash,encrypted_state,config_hash,expires_at)
                  VALUES(%s,%s,%s,%s,now()+interval '5 minutes')""",
               (token_digest(browser), token_digest(data["state"]), encrypted, config.fingerprint))
    response.set_cookie(FLOW_COOKIE, browser, max_age=FLOW_SECONDS, httponly=True,
                        secure=secure_cookie(), samesite="lax", path="/")
    return {"authorization_url": data["url"]}


def consume_flow(browser, state):
    # Commit consumption before the token exchange: retries/replays cannot redeem
    # the same state even if the provider or the final app transaction fails.
    with auth_transaction() as db:
        row = db.execute("""DELETE FROM oidc_login_flows WHERE browser_hash=%s AND state_hash=%s
                          AND expires_at>now() RETURNING encrypted_state,config_hash""",
                         (token_digest(browser), token_digest(state))).fetchone()
    return row


@router.get("/callback")
async def callback(request: Request, response: Response, config=Depends(settings),
                   db=Depends(auth_connection, scope="function")):
    require_policy_database(config, db)
    query = request.query_params
    if (any(len(query.getlist(k)) != 1 for k in query)
            or set(query) - {"state", "code", "error", "error_description", "iss"}
            or ("iss" in query and query["iss"] != config.issuer)
            or not 20 <= len(query.get("state", "")) <= 256
            or len(query.get("code", "")) > 4096
            or not 32 <= len(request.cookies.get(FLOW_COOKIE, "")) <= 128):
        return denied()
    flow = consume_flow(request.cookies[FLOW_COOKIE], query["state"])
    if not flow or flow["config_hash"] != config.fingerprint:
        return denied()
    if query.get("error") or not query.get("code"):
        return denied()
    try:
        request.scope["session"] = json.loads(cipher().decrypt(flow["encrypted_state"].encode()).decode())
        token = await make_client(config).authorize_access_token(
            request, leeway=0,
            claims_options={"iss": {"essential": True, "value": config.issuer},
                            "aud": {"essential": True, "values": [config.client_id]},
                            "auth_time": {"essential": True}},
        )
        claims = token.get("userinfo")
        now = time.time()
        if (not claims or claims.get(ASSURANCE_CLAIM) != config.assurance
                or "mfa" not in claims.get("amr", [])
                or isinstance(claims.get("auth_time"), bool)
                or not isinstance(claims.get("auth_time"), (int, float))
                or not now - FLOW_SECONDS <= claims["auth_time"] <= now + 30
                or not isinstance(claims.get("sub"), str) or not 1 <= len(claims["sub"]) <= 255):
            return denied()
    except (OAuthError, JoseError, HTTPError, InvalidToken, ValueError, TypeError, KeyError):
        return denied()
    identity = db.execute("""SELECT i.id,i.user_id,i.is_operator,u.email FROM oidc_identities i
        JOIN users u ON u.id=i.user_id WHERE i.issuer=%s AND i.subject=%s AND i.status='active'
        AND u.status='active'""", (config.issuer, claims["sub"])).fetchone()
    if not identity:
        return denied()
    uid = identity["user_id"]
    db.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s,0))", ("auth-email:" + identity["email"],))
    user_context(db, uid)
    if not reserve_session_slot(db, uid, verified=True):
        raise HTTPException(503, "Kapasitas session terotorisasi sementara penuh")
    opaque = new_token()
    lifetime = min(SESSION_SECONDS, STAFF_SESSION_SECONDS)
    db.execute("DELETE FROM sessions WHERE token_hash=%s", (token_digest(request.cookies.get(COOKIE, "")),))
    db.execute("INSERT INTO sessions(token_hash,user_id,expires_at,mfa_verified) VALUES(%s,%s,%s,true)",
               (token_digest(opaque), uid, datetime.now(timezone.utc) + timedelta(seconds=lifetime)))
    db.execute("INSERT INTO oidc_sessions(token_hash,identity_id,authenticated_at,assurance) VALUES(%s,%s,%s,%s)",
               (token_digest(opaque), identity["id"], datetime.fromtimestamp(claims["auth_time"], timezone.utc), config.assurance))
    security_event(db, uid, "login.succeeded")
    response.set_cookie(COOKIE, opaque, max_age=lifetime, httponly=True,
                        secure=secure_cookie(), samesite="lax", path="/")
    clear_flow(response)
    return {"message": "Berhasil masuk melalui Auth0", "is_operator": identity["is_operator"]}


@router.get("/session")
def provider_session(request: Request, db=Depends(auth_connection, scope="function")):
    uid = session_user(request, db)
    row = db.execute("""SELECT i.is_operator,o.authenticated_at FROM oidc_sessions o
                       JOIN oidc_identities i ON i.id=o.identity_id
                       WHERE o.token_hash=%s AND i.user_id=%s AND i.status='active'""",
                     (token_digest(request.cookies[COOKIE]), uid)).fetchone()
    if not row:
        raise HTTPException(403, "Session Auth0 diperlukan")
    return {"provider": "auth0", "is_operator": row["is_operator"],
            "authenticated_at": row["authenticated_at"]}
