"""Bounded auth budgets, key rotation and secret-free audit records."""
from datetime import datetime,timedelta,timezone
import json
import os
from uuid import uuid4

from cryptography.fernet import Fernet,MultiFernet,InvalidToken
from fastapi import HTTPException
from fastapi.responses import JSONResponse

from .security import token_digest


class KeyRing:
    def __init__(self):
        try:
            raw=os.environ.get('AUTH_ENCRYPTION_KEYS')
            keys=json.loads(raw) if raw else {'legacy':os.environ['AUTH_ENCRYPTION_KEY']}
            if not isinstance(keys,dict) or not keys or any(not isinstance(k,str) or not isinstance(v,str) for k,v in keys.items()):
                raise ValueError('Invalid keyring')
            active=os.environ.get('AUTH_ACTIVE_KEY_ID',next(iter(keys)))
            if not keys or active not in keys or any(not k.isalnum() or len(k)>32 for k in keys):
                raise ValueError('Invalid key ids')
            self.active=active
            self.keys={k:Fernet(v.encode()) for k,v in keys.items()}
            self.ring=MultiFernet([self.keys[active]]+[v for k,v in self.keys.items() if k!=active])
        except (KeyError,ValueError,TypeError,StopIteration):
            raise HTTPException(503,'Layanan keamanan belum dikonfigurasi') from None

    def encrypt(self,data):
        return self.active.encode()+b':'+self.keys[self.active].encrypt(data)

    def decrypt(self,data):
        if b':' in data and data.split(b':',1)[0].decode() not in self.keys:
            raise InvalidToken
        raw=data.split(b':',1)[1] if b':' in data else data
        return self.ring.decrypt(raw)

    def rotate(self,data):
        return self.encrypt(self.decrypt(data))


def cipher():
    return KeyRing()


def bucket(key):
    return int(token_digest(key)[:8],16)%4096


def throttle(db,key,limit=5,minutes=15,kind='account',bucket_id=None):
    # Fixed keyspace: at most 5*4096 rows, even with arbitrary email/token input.
    bid=bucket(key) if bucket_id is None else bucket_id
    db.execute('INSERT INTO auth_rate_buckets(kind,bucket,attempts) VALUES(%s,%s,0) ON CONFLICT DO NOTHING',(kind,bid))
    row=db.execute('SELECT * FROM auth_rate_buckets WHERE kind=%s AND bucket=%s FOR UPDATE',(kind,bid)).fetchone()
    now=datetime.now(timezone.utc)
    count=row['attempts'] if row['window_start']>now-timedelta(minutes=minutes) else 0
    if count>=limit:
        return False
    db.execute('UPDATE auth_rate_buckets SET attempts=%s,window_start=%s WHERE kind=%s AND bucket=%s',
               (count+1,row['window_start'] if count else now,kind,bid))
    return True


def reset_throttle(db,key,kind='account'):
    db.execute('UPDATE auth_rate_buckets SET attempts=0,window_start=now() WHERE kind=%s AND bucket=%s',(kind,bucket(key)))


def limited():
    return JSONResponse({'detail':'Terlalu banyak percobaan. Coba lagi nanti'},status_code=429,
                        headers={'Retry-After':'60','Cache-Control':'no-store','X-Content-Type-Options':'nosniff'})


def password_slot(db):
    # Transaction locks cap expensive password operations across all API workers.
    for slot in range(4):
        if db.execute('SELECT pg_try_advisory_xact_lock(%s) AS ok',(781100+slot,)).fetchone()['ok']:
            return True
    return False


def reserve_session_slot(db,user_id,verified=False):
    """Bound each pool without letting password holders evict MFA sessions.

    Only an independent operator can pin an unverified enrollment/recovery.
    Password-only clients cannot exhaust capacity and veto every future login.
    """
    capacity=20 if verified else 100
    count=db.execute('SELECT count(*) AS n FROM sessions WHERE user_id=%s AND mfa_verified=%s',
                     (user_id,verified)).fetchone()['n']
    if count<capacity:
        return True
    db.execute("""DELETE FROM sessions WHERE token_hash IN (
      SELECT s.token_hash FROM sessions s WHERE s.user_id=%s AND s.mfa_verified=%s
      AND NOT EXISTS(SELECT 1 FROM mfa_requests r WHERE r.session_hash=s.token_hash
          AND r.approved_at IS NOT NULL AND r.consumed_at IS NULL AND r.expires_at>now())
      AND NOT EXISTS(SELECT 1 FROM mfa_enrollments e WHERE e.session_hash=s.token_hash AND e.expires_at>now())
      ORDER BY s.created_at,s.token_hash LIMIT %s)""",(user_id,verified,count-capacity+1))
    return db.execute('SELECT count(*) AS n FROM sessions WHERE user_id=%s AND mfa_verified=%s',
                      (user_id,verified)).fetchone()['n']<capacity


def security_event(db,user_id,action):
    # Unknown identities are aggregated in fixed rate counters, never one audit
    # row (or persistent email key) per random anonymous request.
    if user_id is not None:
        db.execute('INSERT INTO auth_events(id,user_id,action) VALUES(%s,%s,%s)',(uuid4(),user_id,action))


def tenant_event(db,actor,action,target_type=None,target_id=None):
    db.execute('INSERT INTO audit_events(id,tenant_id,actor_id,action,target_type,target_id) VALUES(%s,%s,%s,%s,%s,%s)',
               (uuid4(),actor.tenant_id,actor.user_id,action,target_type,target_id))


def enqueue(db,email,kind,token):
    payload=cipher().encrypt(token.encode()).decode()
    db.execute("""INSERT INTO auth_mail_outbox(id,recipient,kind,encrypted_token,expires_at)
                  VALUES(%s,%s,%s,%s,now()+interval '1 hour')""",(uuid4(),email,kind,payload))
