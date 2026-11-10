"""Server-managed sessions with separate authentication and tenant DB roles."""
from datetime import datetime,timedelta,timezone
import os
from uuid import UUID,uuid4

from fastapi import APIRouter,Depends,HTTPException,Request,Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel,ConfigDict,Field
from pwdlib import PasswordHash
from psycopg import Error as DatabaseError

from .database import transaction,auth_transaction,user_context,tenant_context,session_context,external_managed
from .security import Principal,authorize,new_token,token_digest
from .auth_support import security_event,throttle,reset_throttle,limited,password_slot,reserve_session_slot

router=APIRouter(prefix='/auth')
passwords=PasswordHash.recommended()
dummy_hash=passwords.hash(new_token())
COOKIE='maaher_session'
SESSION_SECONDS=8*60*60


class Login(BaseModel):
    model_config=ConfigDict(extra='forbid')
    email: str=Field(min_length=3,max_length=254)
    password: str=Field(min_length=1,max_length=1024)


def verify_origin(request: Request):
    expected=os.environ.get('APP_ORIGIN')
    if not expected or request.headers.get('origin')!=expected:
        raise HTTPException(403,'Asal permintaan tidak diizinkan')


def secure_cookie():
    return not(os.environ.get('APP_ENV')=='local' and os.environ.get('LOCAL_INSECURE_COOKIES')=='true')


def connection():
    try:
        with transaction() as db:
            yield db
    except DatabaseError:
        raise HTTPException(503,'Penyimpanan transaksi gagal atau belum dapat dipastikan. Periksa status sebelum mencoba lagi') from None


def auth_connection():
    try:
        with auth_transaction() as db:
            yield db
    except DatabaseError:
        raise HTTPException(503,'Penyimpanan transaksi gagal atau belum dapat dipastikan. Periksa status sebelum mencoba lagi') from None


def session_user(request,db,require_mfa=True,optional=False):
    token=request.cookies.get(COOKIE,'')
    row=None
    if 32<=len(token)<=128:
        row=db.execute('SELECT * FROM resolve_session(%s)',(token_digest(token),)).fetchone()
    if not row:
        if optional:
            return None
        raise HTTPException(401,'Silakan masuk kembali')
    user_context(db,row['id'])
    session_context(db,token_digest(token))
    request.state.auth_session=row
    if require_mfa and row['mfa_required'] and not(row['mfa_verified'] and row['factor_confirmed']):
        raise HTTPException(403,'Verifikasi MFA diperlukan')
    return row['id']


def principal(request: Request,db=Depends(connection,scope='function')):
    uid=session_user(request,db)
    try:
        tid=UUID(request.headers.get('x-tenant-id',''))
    except ValueError:
        raise HTTPException(403,'Pilih organisasi yang Anda ikuti') from None
    membership=db.execute("""SELECT m.role FROM memberships m JOIN tenants t ON t.id=m.tenant_id
       WHERE m.user_id=%s AND m.tenant_id=%s AND m.status='active' AND t.status='active'""",(uid,tid)).fetchone()
    if not membership:
        raise HTTPException(403,'Akses organisasi ditolak')
    tenant_context(db,tid)
    return Principal(uid,tid,membership['role'])


@router.post('/login',dependencies=[Depends(verify_origin)])
def login(body: Login,request: Request,response: Response,db=Depends(auth_connection,scope='function')):
    email=body.email.strip().lower()
    client=getattr(request.state,'client_key',request.client.host)
    key=f'login:{email}:{client}'
    allowed=throttle(db,key,limit=10,kind='account')
    db.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))',('auth-email:'+email,))
    user=db.execute('SELECT * FROM users WHERE email=%s',(email,)).fetchone()
    if not password_slot(db):
        return limited()
    # Resource budgets run before Argon2. Account failures never veto a correct
    # password: an attacker cannot lock an account by knowing its email address.
    valid=passwords.verify(body.password,user['password_hash'] if user else dummy_hash)
    if not valid or not user or user['status']!='active' or external_managed(db,user['id']):
        security_event(db,user['id'] if user else None,'login.failed')
        if not allowed:
            return limited()
        return JSONResponse({'detail':'Email atau kata sandi salah'},status_code=401)
    reset_throttle(db,key,kind='account')
    token=new_token()
    db.execute('DELETE FROM sessions WHERE token_hash=%s OR (user_id=%s AND expires_at<=now())',
               (token_digest(request.cookies.get(COOKIE,'')),user['id']))
    if not reserve_session_slot(db,user['id']):
        return limited()
    db.execute('INSERT INTO sessions(token_hash,user_id,expires_at) VALUES(%s,%s,%s)',
               (token_digest(token),user['id'],datetime.now(timezone.utc)+timedelta(seconds=SESSION_SECONDS)))
    user_context(db,user['id'])
    security_event(db,user['id'],'login.succeeded')
    response.set_cookie(COOKIE,token,max_age=SESSION_SECONDS,httponly=True,secure=secure_cookie(),samesite='lax',path='/')
    return {'message':'Berhasil masuk','mfa_required':bool(db.execute("""SELECT confirmed FROM mfa_factors WHERE user_id=%s""",(user['id'],)).fetchone())
            or bool(db.execute("SELECT 1 FROM memberships WHERE user_id=%s AND role='admin' AND status='active' LIMIT 1",(user['id'],)).fetchone())}


@router.get('/memberships')
def memberships(request: Request,db=Depends(connection,scope='function')):
    uid=session_user(request,db)
    return db.execute("""SELECT m.tenant_id,t.name,m.role FROM memberships m JOIN tenants t ON t.id=m.tenant_id
      WHERE m.user_id=%s AND m.status='active' AND t.status='active' ORDER BY t.name,m.tenant_id LIMIT 100""",(uid,)).fetchall()


@router.get('/security-events')
def own_security_events(request: Request,db=Depends(auth_connection,scope='function')):
    uid=session_user(request,db)
    return db.execute('SELECT id,action,created_at FROM auth_events WHERE user_id=%s ORDER BY created_at DESC,id LIMIT 100',(uid,)).fetchall()


@router.get('/me')
def me(actor: Principal=Depends(principal)):
    return {'user_id':actor.user_id,'tenant_id':actor.tenant_id,'role':actor.role}


@router.post('/logout',dependencies=[Depends(verify_origin)])
def logout(request: Request,response: Response,db=Depends(auth_connection,scope='function')):
    uid=session_user(request,db)
    email=db.execute('SELECT email FROM users WHERE id=%s',(uid,)).fetchone()['email']
    db.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))',('auth-email:'+email,))
    db.execute('DELETE FROM sessions WHERE token_hash=%s AND user_id=%s',(token_digest(request.cookies[COOKIE]),uid))
    security_event(db,uid,'logout')
    response.delete_cookie(COOKIE,path='/',secure=secure_cookie(),httponly=True,samesite='lax')
    return {'message':'Berhasil keluar'}


@router.post('/tenant-selection',dependencies=[Depends(verify_origin)])
def select_tenant(actor: Principal=Depends(principal),db=Depends(connection,scope='function')):
    db.execute('INSERT INTO audit_events(id,tenant_id,actor_id,action) VALUES(%s,%s,%s,%s)',
               (uuid4(),actor.tenant_id,actor.user_id,'tenant.selected'))
    return {'tenant_id':actor.tenant_id,'role':actor.role}


@router.get('/audit')
def audit(actor: Principal=Depends(principal),db=Depends(connection,scope='function')):
    if not authorize(actor,{'admin'}):
        raise HTTPException(403,'Hanya admin organisasi yang dapat mengakses')
    return db.execute('SELECT id,actor_id,action,target_type,target_id,created_at FROM audit_events WHERE tenant_id=%s ORDER BY created_at DESC,id LIMIT 100',
                      (actor.tenant_id,)).fetchall()
