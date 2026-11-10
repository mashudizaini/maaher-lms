"""MFA changes require an independent, session-bound operator authorization."""
from datetime import datetime, timedelta, timezone
from typing import Literal
from uuid import uuid4

import pyotp
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from .auth import COOKIE,SESSION_SECONDS,auth_connection,passwords,secure_cookie,session_user,verify_origin
from .auth_support import cipher,limited,security_event,throttle,reset_throttle,reserve_session_slot
from .security import new_token,token_digest
from .database import external_managed

router=APIRouter(prefix='/auth/mfa',dependencies=[Depends(verify_origin)])


class RequestAuthorization(BaseModel):
    model_config=ConfigDict(extra='forbid')
    purpose: Literal['bootstrap','recovery']


class Enrollment(BaseModel):
    model_config=ConfigDict(extra='forbid')
    password: str=Field(min_length=1,max_length=1024)
    authorization: str=Field(default='',max_length=128)
    new_password: str | None=Field(default=None,min_length=15,max_length=1024)


class Verification(BaseModel):
    model_config=ConfigDict(extra='forbid')
    code: str=Field(pattern=r'^[0-9]{6}$')


@router.post('/request')
def request_authorization(body: RequestAuthorization,request: Request,
                          db=Depends(auth_connection,scope='function')):
    uid=session_user(request,db,require_mfa=False)
    if external_managed(db,uid):
        raise HTTPException(403,'Kelola faktor akun staff melalui Auth0')
    digest=token_digest(request.cookies[COOKIE])
    factor=db.execute('SELECT confirmed FROM mfa_factors WHERE user_id=%s',(uid,)).fetchone()
    if body.purpose=='bootstrap' and factor and factor['confirmed']:
        raise HTTPException(409,'MFA sudah aktif; gunakan pemulihan terverifikasi')
    # Renew expired requests without reviving their approval. The independent
    # operator audit is retained separately and does not reference this row by FK.
    db.execute("""DELETE FROM mfa_requests WHERE session_hash=%s AND purpose=%s
                  AND expires_at<=now()""",(digest,body.purpose))
    rid=uuid4()
    # Concurrent retries share the existing unexpired ID and preserve any grant.
    # A request alone still grants no authority and cannot affect another session.
    row=db.execute("""INSERT INTO mfa_requests(id,user_id,session_hash,purpose,expires_at)
                  VALUES(%s,%s,%s,%s,now()+interval '10 minutes')
                  ON CONFLICT(session_hash,purpose) DO UPDATE SET id=mfa_requests.id
                  RETURNING id""",(rid,uid,digest,body.purpose)).fetchone()
    return {'request_id':row['id']}


@router.post('/enroll')
def enroll(body: Enrollment,request: Request,db=Depends(auth_connection,scope='function')):
    uid=session_user(request,db,require_mfa=False)
    if external_managed(db,uid):
        raise HTTPException(403,'Kelola faktor akun staff melalui Auth0')
    encryption=cipher()
    digest=token_digest(request.cookies[COOKIE])
    authorization=db.execute("""SELECT * FROM mfa_requests WHERE user_id=%s AND session_hash=%s
        AND token_hash=%s AND approved_at IS NOT NULL AND consumed_at IS NULL AND expires_at>now() FOR UPDATE""",
        (uid,digest,token_digest(body.authorization))).fetchone()
    if not authorization:
        raise HTTPException(403,'Otorisasi operator independen diperlukan; password/email tidak cukup')
    if not throttle(db,f'mfa:{uid}'):
        return limited()
    user=db.execute('SELECT email,password_hash FROM users WHERE id=%s',(uid,)).fetchone()
    if not passwords.verify(body.password,user['password_hash']):
        security_event(db,uid,'mfa.failed')
        return JSONResponse({'detail':'Verifikasi gagal'},status_code=400)
    factor=db.execute('SELECT confirmed FROM mfa_factors WHERE user_id=%s FOR UPDATE',(uid,)).fetchone()
    if authorization['purpose']=='bootstrap' and factor and factor['confirmed']:
        raise HTTPException(409,'MFA sudah aktif; pemulihan memerlukan verifikasi operator')
    if authorization['purpose']=='recovery' and body.new_password is None:
        raise HTTPException(422,'Pemulihan memerlukan kata sandi baru minimal 15 karakter')
    secret=pyotp.random_base32()
    # The active factor remains unchanged until confirmation of the new factor.
    db.execute("""INSERT INTO mfa_enrollments(session_hash,user_id,encrypted_secret,password_hash,purpose,expires_at)
      VALUES(%s,%s,%s,%s,%s,now()+interval '10 minutes')
      ON CONFLICT(session_hash) DO UPDATE SET encrypted_secret=excluded.encrypted_secret,
      password_hash=excluded.password_hash,purpose=excluded.purpose,created_at=now(),expires_at=excluded.expires_at""",
      (digest,uid,encryption.encrypt(secret.encode()).decode(),
       passwords.hash(body.new_password) if body.new_password else None,authorization['purpose']))
    db.execute('UPDATE mfa_requests SET consumed_at=now() WHERE id=%s',(authorization['id'],))
    security_event(db,uid,'mfa.enrollment_started')
    return {'provisioning_uri':pyotp.TOTP(secret).provisioning_uri(user['email'],issuer_name='Maaher LMS')}


@router.post('/verify')
def verify(body: Verification,request: Request,response: Response,db=Depends(auth_connection,scope='function')):
    uid=session_user(request,db,require_mfa=False)
    if external_managed(db,uid):
        raise HTTPException(403,'Kelola faktor akun staff melalui Auth0')
    email=db.execute('SELECT email FROM users WHERE id=%s',(uid,)).fetchone()['email']
    # Same order as login/password reset: a concurrent old-password login cannot
    # recreate an attacker session after recovery has revoked all sessions.
    db.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))',('auth-email:'+email,))
    session_user(request,db,require_mfa=False)
    encryption=cipher()
    digest=token_digest(request.cookies[COOKIE])
    # Serialize enrollment completion and code replay across sessions.
    db.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))',('factor:'+str(uid),))
    # An abandoned setup must not shadow an existing trusted authenticator.
    pending=db.execute('SELECT * FROM mfa_enrollments WHERE session_hash=%s AND expires_at>now() FOR UPDATE',(digest,)).fetchone()
    active=db.execute('SELECT * FROM mfa_factors WHERE user_id=%s FOR UPDATE',(uid,)).fetchone()
    if active and not (active['confirmed'] and active['trust_verified']):
        active=None
    now=datetime.now(timezone.utc)
    # Ordinary OTP guesses retain their budget across login/session rotation.
    # An independently authorized recovery/enrollment gets a private budget,
    # so an attacker cannot consume it by knowing the account password.
    client=getattr(request.state,'client_key',request.client.host)
    rate_key=f'mfa-proof:{uid}:{digest}' if pending and pending['expires_at']>now else f'mfa-verify:{uid}:{client}'
    if not throttle(db,rate_key,kind='mfa'):
        return limited()
    factor=pending or active
    counter=None
    if factor and (not pending or pending['expires_at']>now):
        totp=pyotp.TOTP(encryption.decrypt(factor['encrypted_secret'].encode()).decode())
        for offset in (-1,0,1):
            candidate=totp.timecode(now)+offset
            if candidate>factor.get('last_counter',-1) and totp.verify(body.code,for_time=candidate*totp.interval):
                counter=candidate; break
    if counter is None:
        security_event(db,uid,'mfa.failed')
        return JSONResponse({'detail':'Kode MFA tidak berlaku'},status_code=400)
    reset_throttle(db,rate_key,kind='mfa')
    session=db.execute('SELECT expires_at FROM sessions WHERE token_hash=%s AND user_id=%s FOR UPDATE',(digest,uid)).fetchone()
    if not session:
        raise HTTPException(401,'Silakan masuk kembali')
    if pending:
        db.execute("""INSERT INTO mfa_factors(user_id,encrypted_secret,confirmed,last_counter,trust_verified)
           VALUES(%s,%s,true,%s,true) ON CONFLICT(user_id) DO UPDATE SET encrypted_secret=excluded.encrypted_secret,
           confirmed=true,trust_verified=true,last_counter=excluded.last_counter,created_at=now()""",(uid,pending['encrypted_secret'],counter))
        if pending['purpose']=='recovery':
            db.execute('UPDATE users SET password_hash=%s WHERE id=%s',(pending['password_hash'],uid))
            db.execute('DELETE FROM password_resets WHERE user_id=%s',(uid,))
            db.execute('DELETE FROM sessions WHERE user_id=%s',(uid,))
            security_event(db,uid,'mfa.recovered')
        else:
            db.execute('DELETE FROM sessions WHERE token_hash=%s',(digest,))
    else:
        db.execute('UPDATE mfa_factors SET last_counter=%s WHERE user_id=%s',(counter,uid))
        db.execute('DELETE FROM sessions WHERE token_hash=%s',(digest,))
    token=new_token()
    if not reserve_session_slot(db,uid,verified=True):
        raise HTTPException(503,'Kapasitas session terotorisasi sementara penuh')
    db.execute('INSERT INTO sessions(token_hash,user_id,expires_at,mfa_verified) VALUES(%s,%s,%s,true)',
               (token_digest(token),uid,session['expires_at']))
    response.set_cookie(COOKIE,token,max_age=min(SESSION_SECONDS,max(0,int((session['expires_at']-now).total_seconds()))),
                        httponly=True,secure=secure_cookie(),samesite='lax',path='/')
    security_event(db,uid,'mfa.verified')
    return {'message':'MFA berhasil diverifikasi'}
