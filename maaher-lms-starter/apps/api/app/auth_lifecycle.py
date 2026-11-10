"""Invitation, password recovery and tenant membership revocation."""
from datetime import datetime, timedelta, timezone
from typing import Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, field_validator
from psycopg.errors import RaiseException

from .auth import connection, auth_connection, passwords, principal, session_user, verify_origin
from .auth_support import cipher, enqueue, limited, security_event, tenant_event, throttle, password_slot
from .security import Principal, new_token, token_digest
from .database import user_context, tenant_context, external_managed

router = APIRouter(prefix="/auth")


class EmailBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: str = Field(min_length=3, max_length=254)

    @field_validator("email")
    @classmethod
    def valid_email(cls, value):
        value = value.strip().lower()
        # Deliberately conservative ASCII mailbox; reject headers/control chars.
        if (not value.isascii() or value.count("@") != 1 or any(c.isspace() or ord(c)<33 for c in value)
                or not all(value.split("@")) or "." not in value.split("@")[1]):
            raise ValueError("Alamat email tidak valid")
        return value


class Invitation(EmailBody):
    role: Literal["student", "teacher", "admin"]


class TokenBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    token: str = Field(min_length=32, max_length=128)


class AcceptInvitation(TokenBody):
    password: str | None = Field(default=None, min_length=15, max_length=1024)


class ResetPassword(TokenBody):
    password: str = Field(min_length=15, max_length=1024)


class MembershipRole(BaseModel):
    model_config = ConfigDict(extra='forbid')
    role: Literal['student','teacher','admin']


def admin(actor: Principal = Depends(principal)):
    if actor.role != "admin":
        raise HTTPException(403, "Hanya admin organisasi yang diizinkan")
    return actor


@router.post("/invitations", status_code=202, dependencies=[Depends(verify_origin)])
def invite(body: Invitation, actor=Depends(admin), db=Depends(auth_connection, scope='function')):
    user_context(db, actor.user_id)
    tenant_context(db, actor.tenant_id)
    cipher()  # Fail before accounting/writes if encryption isn't configured.
    if not throttle(db, f"invite:{actor.tenant_id}:{actor.user_id}", limit=20):
        return limited()
    db.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
               (f"invite:{actor.tenant_id}:{body.email}",))
    token = new_token()
    invitation_id = uuid4()
    db.execute("UPDATE invitations SET revoked_at=now() WHERE tenant_id=%s AND email=%s AND consumed_at IS NULL",
               (actor.tenant_id, body.email))
    db.execute("""INSERT INTO invitations(id,tenant_id,invited_by,email,role,token_hash,expires_at)
                  VALUES (%s,%s,%s,%s,%s,%s,%s)""",
               (invitation_id, actor.tenant_id, actor.user_id, body.email, body.role, token_digest(token),
                datetime.now(timezone.utc)+timedelta(hours=1)))
    enqueue(db, body.email, "invitation", token)
    tenant_event(db, actor, "invitation.created", "invitation", invitation_id)
    return {"message": "Undangan masuk antrean pengiriman"}


@router.post("/invitations/accept", dependencies=[Depends(verify_origin)])
def accept_invitation(body: AcceptInvitation, request: Request, db=Depends(auth_connection, scope='function')):
    user_id = session_user(request, db, optional=True)
    if not throttle(db, f"accept:{token_digest(body.token)}", limit=10):
        return limited()
    if not password_slot(db):
        return limited()
    password_hash = passwords.hash(body.password) if body.password else None
    # Savepoint preserves committed rate accounting on invalid/replayed tokens.
    try:
        with db.transaction():
            tenant = db.execute("SELECT accept_invitation(%s,%s,%s) AS tenant_id",
                                (token_digest(body.token), password_hash, token_digest(request.cookies['maaher_session']) if user_id else None)).fetchone()["tenant_id"]
    except RaiseException:
        from fastapi.responses import JSONResponse
        return JSONResponse({"detail": "Undangan tidak berlaku atau akun harus masuk terlebih dahulu"}, status_code=400)
    return {"message": "Undangan diterima. Silakan masuk", "tenant_id": tenant}


@router.post("/password-reset/request", status_code=202, dependencies=[Depends(verify_origin)])
def request_reset(body: EmailBody, db=Depends(auth_connection, scope='function')):
    cipher()
    # Same public response for known, unknown and throttled accounts.
    allowed = throttle(db, f"reset:{body.email}")
    token = new_token()
    db.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s,0))", ("auth-email:"+body.email,))
    user = db.execute("SELECT id,status FROM users WHERE email=%s", (body.email,)).fetchone()
    if allowed and user and user["status"] == "active" and not external_managed(db, user["id"]):
        db.execute("DELETE FROM password_resets WHERE user_id=%s", (user["id"],))
        db.execute("INSERT INTO password_resets(token_hash,user_id,expires_at) VALUES (%s,%s,now()+interval '1 hour')",
                   (token_digest(token), user["id"]))
        enqueue(db, body.email, "password-reset", token)
        security_event(db, user["id"], "reset.requested")
    return {"message": "Jika akun tersedia, petunjuk pemulihan akan dikirim"}


@router.post("/password-reset/confirm", dependencies=[Depends(verify_origin)])
def confirm_reset(body: ResetPassword, db=Depends(auth_connection, scope='function')):
    if not throttle(db, f"reset-confirm:{token_digest(body.token)}", limit=10):
        return limited()
    if not password_slot(db):
        return limited()
    changed = db.execute("SELECT reset_password(%s,%s) AS changed",
                         (token_digest(body.token), passwords.hash(body.password))).fetchone()["changed"]
    if not changed:
        from fastapi.responses import JSONResponse
        return JSONResponse({"detail": "Tautan pemulihan tidak berlaku"}, status_code=400)
    return {"message": "Kata sandi diperbarui. Silakan masuk kembali"}


@router.post("/memberships/{user_id}/revoke", dependencies=[Depends(verify_origin)])
def revoke(user_id: UUID, request: Request, actor=Depends(admin), db=Depends(connection, scope='function')):
    changed = db.execute("SELECT change_member(%s,%s,%s,'revoked') AS changed",
                         (token_digest(request.cookies['maaher_session']), actor.tenant_id, user_id)).fetchone()["changed"]
    if not changed:
        raise HTTPException(404, "Keanggotaan tidak tersedia")
    return {"message": "Akses organisasi dicabut"}


@router.get('/tenant-members')
def tenant_members(request: Request, after: UUID | None=None, actor=Depends(admin),db=Depends(connection,scope='function')):
    rows=db.execute('SELECT * FROM list_members(%s,%s,%s)',
                      (token_digest(request.cookies['maaher_session']),actor.tenant_id,after)).fetchall()
    return {'members':rows[:100],'next_cursor':str(rows[99]['user_id']) if len(rows)>100 else None}


@router.post('/memberships/{user_id}/role', dependencies=[Depends(verify_origin)])
def change_role(user_id: UUID,body: MembershipRole,request: Request,
                actor=Depends(admin),db=Depends(connection,scope='function')):
    changed=db.execute('SELECT change_member(%s,%s,%s,%s) AS changed',
                       (token_digest(request.cookies['maaher_session']),actor.tenant_id,user_id,body.role)).fetchone()['changed']
    if not changed:
        raise HTTPException(404,'Keanggotaan tidak tersedia')
    return {'message':'Peran keanggotaan diperbarui'}
