"""Regression reproductions for the independent Claude review, H1/M1..M6/L1..L7."""
from contextlib import contextmanager
from datetime import datetime,timedelta,timezone
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import threading
import time
from uuid import uuid4

import httpx
import psycopg
from psycopg.rows import dict_row
import pyotp
import pytest
from fastapi.testclient import TestClient
from cryptography.fernet import Fernet,InvalidToken

from app.main import app
from app.auth_support import cipher,bucket
from app.database import transaction,session_context,user_context,tenant_context
from app.security import new_token,token_digest
from auth_helpers import sign_in,authorize_mfa,enroll_mfa,make_admin,issue_invite,mail_token

ORIGIN={'origin':'https://testserver'}


def test_h1_password_and_compromised_email_cannot_bootstrap_mfa(identity):
    client,owner,user,tenant,_,email,password=identity
    assert sign_in(client,email,password).status_code==200
    assert client.post('/auth/mfa/enroll',json={'password':password},headers=ORIGIN).status_code==403
    # Simulate possession of the reset email as well as the password.
    assert client.post('/auth/password-reset/request',json={'email':email},headers=ORIGIN).status_code==202
    token=mail_token(owner,email,'password-reset')
    replacement='Attacker controls reset email 123!'
    assert client.post('/auth/password-reset/confirm',json={'token':token,'password':replacement},headers=ORIGIN).status_code==200
    assert sign_in(client,email,replacement).status_code==200
    assert client.post('/auth/mfa/enroll',json={'password':replacement},headers=ORIGIN).status_code==403
    assert client.post('/auth/mfa/verify',json={'code':'123456'},headers=ORIGIN).status_code==400
    with psycopg.connect(owner) as db:
        assert db.execute('SELECT count(*) FROM mfa_factors WHERE user_id=%s',(user,)).fetchone()[0]==0
        assert db.execute('SELECT count(*) FROM mfa_enrollments WHERE user_id=%s',(user,)).fetchone()[0]==0
    # The attack has not imposed an attacker-owned factor on a normal user.
    assert client.get('/auth/me',headers={'x-tenant-id':str(tenant)}).status_code==200


def test_h1_authorization_is_session_bound_one_use_and_independent(identity):
    client,_,_,_,_,email,password=identity
    assert sign_in(client,email,password).status_code==200
    authorization=authorize_mfa(client)
    with TestClient(app,base_url='https://testserver') as attacker:
        assert sign_in(attacker,email,password).status_code==200
        assert attacker.post('/auth/mfa/enroll',json={'password':password,'authorization':authorization},headers=ORIGIN).status_code==403
    response=client.post('/auth/mfa/enroll',json={'password':password,'authorization':authorization},headers=ORIGIN)
    assert response.status_code==200
    assert client.post('/auth/mfa/enroll',json={'password':password,'authorization':authorization},headers=ORIGIN).status_code==403
    totp=pyotp.parse_uri(response.json()['provisioning_uri'])
    assert client.post('/auth/mfa/verify',json={'code':totp.now()},headers=ORIGIN).status_code==200


def test_h1_legitimate_owner_recovers_legacy_attacker_factor_and_all_sessions(identity):
    client,owner,user,tenant,_,email,password=identity
    stolen_secret=pyotp.random_base32()
    with psycopg.connect(owner) as db:
        db.execute('UPDATE memberships SET role=\'admin\' WHERE user_id=%s',(user,))
        db.execute('INSERT INTO mfa_factors(user_id,encrypted_secret,confirmed,trust_verified) VALUES(%s,%s,true,false)',
                   (user,cipher().encrypt(stolen_secret.encode()).decode()))
    with TestClient(app,base_url='https://testserver') as attacker:
        assert sign_in(attacker,email,password).status_code==200
        attacker_cookie=attacker.cookies.get('maaher_session')
        assert attacker.post('/auth/mfa/verify',json={'code':pyotp.TOTP(stolen_secret).now()},headers=ORIGIN).status_code==400
        assert sign_in(client,email,password).status_code==200
        proof=authorize_mfa(client,'recovery')
        replacement='Recovered independent owner password 123!'
        response=client.post('/auth/mfa/enroll',json={'password':password,'new_password':replacement,'authorization':proof},headers=ORIGIN)
        assert response.status_code==200,response.text
        fresh=pyotp.parse_uri(response.json()['provisioning_uri'])
        with psycopg.connect(owner) as db:
            old=db.execute('SELECT encrypted_secret,trust_verified FROM mfa_factors WHERE user_id=%s',(user,)).fetchone()
            assert cipher().decrypt(old[0].encode()).decode()==stolen_secret and old[1] is False
        assert client.post('/auth/mfa/verify',json={'code':fresh.now()},headers=ORIGIN).status_code==200
        assert client.get('/auth/me',headers={'x-tenant-id':str(tenant)}).status_code==200
        assert attacker.get('/auth/me',headers={'x-tenant-id':str(tenant)}).status_code==401
        assert attacker.cookies.get('maaher_session')==attacker_cookie
    assert sign_in(client,email,password).status_code==401
    with psycopg.connect(owner) as db:
        factor=db.execute('SELECT encrypted_secret,trust_verified FROM mfa_factors WHERE user_id=%s',(user,)).fetchone()
        assert cipher().decrypt(factor[0].encode()).decode()==fresh.secret and factor[1] is True
        assert db.execute("SELECT count(*) FROM mfa_operator_audit WHERE user_id=%s AND purpose='recovery'",(user,)).fetchone()[0]==1
    assert sign_in(client,email,replacement).status_code==200
    assert client.get('/auth/me',headers={'x-tenant-id':str(tenant)}).status_code==403


def test_h1_production_operator_trust_cannot_be_enabled_by_email_or_boolean(identity,monkeypatch):
    from app.mfa_operator import approve_request
    client=identity[0]
    assert sign_in(client,identity[5],identity[6]).status_code==200
    rid=client.post('/auth/mfa/request',json={'purpose':'bootstrap'},headers=ORIGIN).json()['request_id']
    monkeypatch.setenv('APP_ENV','production')
    monkeypatch.setenv('OPERATOR_MFA_VERIFIED','true')
    with psycopg.connect(os.environ['TEST_OPERATOR_DATABASE_URL'],row_factory=dict_row) as db:
        with pytest.raises(RuntimeError,match='unconfigured'):
            approve_request(db,rid,'email-or-boolean-is-not-proof')


@pytest.mark.parametrize('query',[
    'SELECT password_hash FROM users','SELECT * FROM users','SELECT * FROM sessions','SELECT * FROM mfa_factors',
    "INSERT INTO sessions(token_hash,user_id,expires_at,mfa_verified) VALUES('forged',gen_random_uuid(),now(),true)",
    "INSERT INTO sessions(token_hash,user_id,expires_at,mfa_verified) VALUES('forged',gen_random_uuid(),now(),false)",
    "SELECT reset_password('forged','forged')","SELECT accept_invitation('forged','forged',NULL::text)",
    "SELECT authorize_mfa_request(gen_random_uuid(),'forged','forged-reference')",
])
def test_m4_runtime_actual_login_cannot_read_hashes_or_mint_mfa_sessions(identity,query):
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        with transaction() as db:
            assert db.execute('SELECT current_user AS name').fetchone()['name']=='maaher_api'
            db.execute(query)


def test_m6_definers_are_nonlogin_nonsuperuser_minimum_privilege(identity):
    with psycopg.connect(identity[1],row_factory=dict_row) as db:
        rows=db.execute("""SELECT p.proname,r.rolname,r.rolsuper,r.rolcanlogin,r.rolcreaterole,p.proconfig,
             EXISTS(SELECT 1 FROM aclexplode(coalesce(p.proacl,acldefault('f',p.proowner))) a
                    WHERE a.grantee=0 AND a.privilege_type='EXECUTE') AS public_execute
             FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace JOIN pg_roles r ON r.oid=p.proowner
             WHERE n.nspname='public' AND p.prosecdef""").fetchall()
        assert len(rows) == 14
        assert {row['proname'] for row in rows} == {'resolve_session','tenant_admin','list_members','change_member',
            'reset_password','accept_invitation','authorize_mfa_request','retain_auth_data','runtime_identity','course_member_role','course_assignment_guard','course_student_access','enrollment_lock_student','enrollment_guard'}
        for row in rows:
            assert row['rolname']=='maaher_definer'
            assert not any(row[k] for k in ('rolsuper','rolcanlogin','rolcreaterole','public_execute'))
            assert 'search_path=pg_catalog,public,pg_temp' in [v.replace(' ','') for v in row['proconfig']]
        assert not db.execute("SELECT has_table_privilege('maaher_definer','sessions','INSERT') AS ok").fetchone()['ok']
        assert not db.execute("SELECT has_schema_privilege('maaher_definer','public','CREATE') AS ok").fetchone()['ok']
        assert not db.execute("SELECT has_column_privilege('maaher_definer','users','password_hash','SELECT') AS ok").fetchone()['ok']
        assert not db.execute("SELECT has_column_privilege('maaher_definer','mfa_factors','encrypted_secret','SELECT') AS ok").fetchone()['ok']
    with transaction() as db:
        for group in ('maaher_auth','maaher_definer','maaher_mfa_operator','maaher_maintenance'):
            assert not db.execute("SELECT pg_has_role(current_user,%s,'MEMBER') AS ok",(group,)).fetchone()['ok']


def test_m4_forged_gucs_cannot_authorize_tenant_identity_or_admin_changes(identity):
    client,owner,user,tenant,foreign,email,password=identity
    assert sign_in(client,email,password).status_code==200
    with psycopg.connect(owner) as db:
        other=db.execute('SELECT user_id FROM memberships WHERE tenant_id=%s',(foreign,)).fetchone()[0]
    with transaction() as db:
        user_context(db,other);tenant_context(db,foreign)
        assert db.execute('SELECT * FROM memberships').fetchall()==[]
        assert db.execute("SELECT change_member('forged',%s,%s,'revoked') AS changed",(foreign,other)).fetchone()['changed'] is False
        session_context(db,token_digest(client.cookies.get('maaher_session')))
        rows=db.execute('SELECT user_id FROM memberships').fetchall()
        assert rows==[{'user_id':user}]
        assert db.execute('SELECT * FROM audit_events').fetchall()==[]


@contextmanager
def commit_server(mode,tmp_path):
    with socket.socket() as probe:
        probe.bind(('127.0.0.1',0));port=probe.getsockname()[1]
    entered=tmp_path/'entered';release=tmp_path/'release'
    env=os.environ.copy();api=Path(__file__).parents[1]
    env.update(PYTHONPATH=os.pathsep.join((str(api),str(Path(__file__).parent))),
               LMS_COMMIT_MODE=mode,LMS_COMMIT_ENTERED=str(entered),LMS_COMMIT_RELEASE=str(release))
    process=subprocess.Popen([sys.executable,'-m','uvicorn','commit_probe_app:app','--host','127.0.0.1',
       '--port',str(port),'--no-access-log','--log-level','error'],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    try:
        with httpx.Client(base_url=f'http://127.0.0.1:{port}',trust_env=False,timeout=20) as api:
            deadline=time.monotonic()+15
            while True:
                assert process.poll() is None,'Probe API exited'
                try:
                    if api.get('/healthz').status_code==200: break
                except httpx.TransportError: pass
                assert time.monotonic()<deadline
                time.sleep(.02)
            yield api,entered,release
    finally:
        release.touch()
        process.terminate()
        try: process.wait(timeout=5)
        except subprocess.TimeoutExpired: process.kill();process.wait(timeout=5)


def test_m1_real_uvicorn_does_not_send_headers_or_cookie_until_commit(identity,tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    _,owner,user,tenant,_,email,password=identity
    headers_received=threading.Event()
    with commit_server('delay',tmp_path) as (api,entered,release):
        api.event_hooks['response']=[lambda response:headers_received.set()]
        with ThreadPoolExecutor(max_workers=1) as pool:
            pending=pool.submit(api.post,'/auth/login',json={'email':email,'password':password},headers=ORIGIN)
            deadline=time.monotonic()+10
            while not entered.exists():
                assert not pending.done(),'Response completed before COMMIT barrier'
                assert time.monotonic()<deadline
                time.sleep(.01)
            assert not headers_received.is_set(),'Response headers/cookie escaped before COMMIT'
            assert not pending.done()
            with psycopg.connect(owner) as observer:
                assert observer.execute('SELECT count(*) FROM sessions WHERE user_id=%s',(user,)).fetchone()[0]==0
            release.touch()
            response=pending.result(timeout=10)
        assert response.status_code==200 and 'set-cookie' in response.headers
        cookie=response.cookies.get('maaher_session')
        assert api.get('/auth/me',headers={'cookie':f'maaher_session={cookie}','x-tenant-id':str(tenant)}).status_code==200


@pytest.mark.parametrize('operation',['login','logout'])
def test_m1_real_uvicorn_commit_failure_has_no_success_or_cookie(identity,tmp_path,operation):
    client,owner,user,tenant,_,email,password=identity
    headers=ORIGIN.copy()
    if operation=='logout':
        assert sign_in(client,email,password).status_code==200
        old=client.cookies.get('maaher_session');headers['cookie']=f'maaher_session={old}'
    with commit_server('fail',tmp_path) as (api,entered,_):
        response=api.post('/auth/'+operation,json={'email':email,'password':password} if operation=='login' else {},headers=headers)
        assert entered.exists()
        assert response.status_code==503
        assert 'Penyimpanan transaksi' in response.json()['detail']
        assert 'set-cookie' not in response.headers
        with psycopg.connect(owner) as observer:
            assert observer.execute('SELECT count(*) FROM sessions WHERE user_id=%s',(user,)).fetchone()[0]==(1 if operation=='logout' else 0)
        if operation=='logout':
            assert api.get('/auth/me',headers={'cookie':f'maaher_session={old}','x-tenant-id':str(tenant)}).status_code==200


def test_m2_random_anonymous_inputs_have_bounded_rows_and_argon_cost(identity,monkeypatch):
    from app.auth import passwords
    client,owner=identity[:2]
    calls=[];original=passwords.verify
    monkeypatch.setattr(passwords,'verify',lambda *args:(calls.append(True),original(*args))[1])
    with psycopg.connect(owner) as db:
        before=db.execute('SELECT count(*) FROM auth_events WHERE user_id IS NULL').fetchone()[0]
        old_attempts=db.execute('SELECT count(*) FROM login_attempts').fetchone()[0]
    statuses=[]
    for _ in range(40):
        statuses.append(client.post('/auth/login',json={'email':f'{uuid4()}@example.invalid','password':'synthetic wrong password'},headers=ORIGIN).status_code)
    for _ in range(40):
        statuses.append(client.post('/auth/password-reset/request',json={'email':f'{uuid4()}@example.invalid'},headers=ORIGIN).status_code)
    assert 429 in statuses and len(calls)<=30
    with psycopg.connect(owner) as db:
        assert db.execute('SELECT count(*) FROM auth_events WHERE user_id IS NULL').fetchone()[0]==before
        assert db.execute('SELECT count(*) FROM login_attempts').fetchone()[0]==old_attempts
        assert db.execute('SELECT count(*) FROM auth_rate_buckets').fetchone()[0]<=32


def test_m2_password_work_is_capped_across_processes_with_db_locks(identity,monkeypatch):
    from app.auth import passwords
    client,owner,_,_,_,email,password=identity
    calls=[];original=passwords.verify
    monkeypatch.setattr(passwords,'verify',lambda *args:(calls.append(True),original(*args))[1])
    with psycopg.connect(owner) as guard:
        for slot in range(4): guard.execute('SELECT pg_advisory_xact_lock(%s)',(781100+slot,))
        assert sign_in(client,email,password).status_code==429
        assert calls==[]
    assert sign_in(client,email,password).status_code==200


def test_m3_attack_cannot_lock_correct_password_or_spoof_client_identity(identity):
    _,owner,_,_,_,email,password=identity
    with TestClient(app,base_url='https://testserver',client=('198.51.100.10',1)) as attacker:
        for _ in range(10):
            assert attacker.post('/auth/login',json={'email':email,'password':'wrong'},headers={**ORIGIN,'x-forwarded-for':'198.51.100.20'}).status_code==401
        assert attacker.post('/auth/login',json={'email':email,'password':'wrong'},headers=ORIGIN).status_code==429
        # Even a correct password on the same network is not account-locked.
        assert sign_in(attacker,email,password).status_code==200
        assert sign_in(attacker,email,'wrong').status_code==401
    with TestClient(app,base_url='https://testserver',client=('198.51.100.20',1)) as legitimate:
        assert sign_in(legitimate,email,password).status_code==200
    with psycopg.connect(owner) as db:
        assert db.execute("SELECT attempts FROM auth_rate_buckets WHERE kind='client' AND bucket=%s",(bucket('198.51.100.20'),)).fetchone()[0]==1


def test_m5_corrupt_outbox_is_quarantined_and_valid_message_still_sends(identity,monkeypatch):
    from app.mail_worker import deliver_one
    owner=identity[1];monkeypatch.setenv('SMTP_FROM','lms@example.invalid')
    tokens=[new_token() for _ in range(3)];ids=[uuid4() for _ in range(3)]
    payloads=[Fernet(Fernet.generate_key()).encrypt(tokens[0].encode()).decode(),cipher().encrypt(b'invalid token format').decode(),cipher().encrypt(tokens[2].encode()).decode()]
    with psycopg.connect(owner) as db:
        db.execute("UPDATE auth_mail_outbox SET expires_at=now()-interval '1 second'")
        for index in range(3):
            db.execute("INSERT INTO auth_mail_outbox(id,recipient,kind,encrypted_token,expires_at) VALUES(%s,%s,'password-reset',%s,now()+make_interval(mins=>%s))",(ids[index],f'{index}@example.invalid',payloads[index],10+index*10))
    sent=[]
    for _ in range(3):
        with psycopg.connect(os.environ['TEST_MAIL_DATABASE_URL'],row_factory=dict_row) as db:
            assert deliver_one(db,sent.append)
    assert len(sent)==1 and tokens[2] in sent[0].get_content()
    with psycopg.connect(owner,row_factory=dict_row) as db:
        for identifier in ids[:2]:
            row=db.execute('SELECT * FROM auth_mail_outbox WHERE id=%s',(identifier,)).fetchone()
            assert row['dead_at'] and row['attempts']==1 and row['error_code']=='invalid_payload'
            assert row['recipient']=='' and row['encrypted_token'] is None
        row=db.execute('SELECT * FROM auth_mail_outbox WHERE id=%s',(ids[2],)).fetchone()
        assert row['sent_at'] and row['recipient']=='' and row['encrypted_token'] is None


def test_l1_stale_cookie_does_not_block_new_invitation_or_authorize_existing(identity):
    client,owner,_,_,foreign,_,password=identity
    headers,_=make_admin(identity)
    _,token=issue_invite(identity,headers)
    client.cookies.clear();client.cookies.set('maaher_session','expired-or-forged-cookie-value-xxxxxxxxxxxx')
    assert client.post('/auth/invitations/accept',json={'token':token,'password':password},headers=ORIGIN).status_code==200
    with psycopg.connect(owner) as db:
        other_email=db.execute('SELECT u.email FROM users u JOIN memberships m ON m.user_id=u.id WHERE m.tenant_id=%s',(foreign,)).fetchone()[0]
    # Existing recipients still require their own valid session; stale != proof.
    with psycopg.connect(owner) as db:
        forged=new_token()
        db.execute("INSERT INTO invitations(id,tenant_id,invited_by,email,role,token_hash,expires_at) VALUES(%s,%s,%s,%s,'student',%s,now()+interval '1 hour')",(uuid4(),identity[3],identity[2],other_email,token_digest(forged)))
    assert client.post('/auth/invitations/accept',json={'token':forged,'password':password},headers=ORIGIN).status_code==400


def test_l7_password_only_session_has_no_metadata_accept_or_logout_privilege(identity):
    client=identity[0];make_admin(identity)
    assert sign_in(client,identity[5],identity[6]).status_code==200
    for path in ('/auth/memberships','/auth/security-events'):
        assert client.get(path).status_code==403
    assert client.post('/auth/logout',headers=ORIGIN).status_code==403
    assert client.post('/auth/invitations/accept',json={'token':'x'*43},headers=ORIGIN).status_code==403
    # Recovery/enrollment request is a narrow exception, granting no authority.
    assert client.post('/auth/mfa/request',json={'purpose':'recovery'},headers=ORIGIN).status_code==200


def test_m2_retention_removes_sensitive_expired_data_and_preserves_live_identity(identity):
    from app.maintenance import retain
    client,owner,user,tenant,_,email,password=identity
    assert sign_in(client,email,password).status_code==200
    live_hash=token_digest(client.cookies.get('maaher_session'))
    old_hash=token_digest(new_token());old_event,new_event=uuid4(),uuid4();old_invite,new_invite=uuid4(),uuid4()
    old_audit,new_audit=uuid4(),uuid4();old_mail,new_mail=uuid4(),uuid4()
    with psycopg.connect(owner) as db:
        db.execute("INSERT INTO sessions(token_hash,user_id,expires_at) VALUES(%s,%s,now()-interval '1 day')",(old_hash,user))
        db.execute("INSERT INTO auth_events(id,user_id,action,created_at) VALUES(%s,%s,'login.failed',now()-interval '31 days'),(%s,%s,'login.succeeded',now())",(old_event,user,new_event,user))
        db.execute("INSERT INTO audit_events(id,tenant_id,actor_id,action,created_at) VALUES(%s,%s,%s,'old',now()-interval '366 days'),(%s,%s,%s,'fresh',now())",(old_audit,tenant,user,new_audit,tenant,user))
        for identifier,expiry in ((old_invite,'-8 days'),(new_invite,'1 hour')):
            db.execute("INSERT INTO invitations(id,tenant_id,invited_by,email,role,token_hash,expires_at) VALUES(%s,%s,%s,%s,'student',%s,now()+%s::interval)",
                       (identifier,tenant,user,email,new_token(),expiry))
        for identifier,expiry in ((old_mail,'-1 second'),(new_mail,'1 hour')):
            db.execute("INSERT INTO auth_mail_outbox(id,recipient,kind,encrypted_token,expires_at) VALUES(%s,%s,'password-reset',%s,now()+%s::interval)",(identifier,email,cipher().encrypt(new_token().encode()).decode(),expiry))
        db.execute("INSERT INTO password_resets(token_hash,user_id,expires_at) VALUES('expired-reset',%s,now()-interval '1 day')",(user,))
        db.execute("INSERT INTO mfa_requests(id,user_id,session_hash,purpose,expires_at) VALUES(%s,%s,%s,'bootstrap',now()-interval '1 second')",(uuid4(),user,old_hash))
        db.execute("INSERT INTO mfa_requests(id,user_id,session_hash,purpose,expires_at) VALUES(%s,%s,%s,'bootstrap',now()+interval '10 minutes')",(uuid4(),user,live_hash))
        db.execute("INSERT INTO login_attempts(email_hash,window_start) VALUES('expired-key',now()-interval '2 days')")
        db.execute("INSERT INTO auth_rate_buckets(kind,bucket,attempts,window_start) VALUES('reset',4095,1,now()-interval '2 days')")
    with psycopg.connect(os.environ['TEST_MAINTENANCE_DATABASE_URL'],row_factory=dict_row) as db:
        retain(db)
    with psycopg.connect(owner) as db:
        for table,old,new in (('auth_events',old_event,new_event),('audit_events',old_audit,new_audit),('invitations',old_invite,new_invite),('auth_mail_outbox',old_mail,new_mail)):
            assert db.execute(f'SELECT id FROM {table} WHERE id=%s',(old,)).fetchone() is None
            assert db.execute(f'SELECT id FROM {table} WHERE id=%s',(new,)).fetchone()[0]==new
        assert db.execute('SELECT token_hash FROM sessions WHERE token_hash=%s',(old_hash,)).fetchone() is None
        assert db.execute('SELECT token_hash FROM sessions WHERE token_hash=%s',(live_hash,)).fetchone()[0]==live_hash
        assert db.execute("SELECT token_hash FROM password_resets WHERE token_hash='expired-reset'").fetchone() is None
        assert db.execute("SELECT email_hash FROM login_attempts WHERE email_hash='expired-key'").fetchone() is None
        assert db.execute("SELECT bucket FROM auth_rate_buckets WHERE kind='reset' AND bucket=4095").fetchone() is None
        assert db.execute('SELECT email FROM users WHERE id=%s',(user,)).fetchone()[0]==email
        assert db.execute('SELECT status FROM memberships WHERE tenant_id=%s AND user_id=%s',(tenant,user)).fetchone()[0]=='active'
    with transaction() as db:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            db.execute('SELECT retain_auth_data()')


def test_l2_multifernet_rotation_preserves_factors_pending_enrollment_and_mail(identity,monkeypatch):
    from app.key_rotation import rotate_rows
    client,owner,user,_,_,email,password=identity
    assert sign_in(client,email,password).status_code==200
    enroll_mfa(client,password)
    assert client.post('/auth/password-reset/request',json={'email':email},headers=ORIGIN).status_code==202
    token=mail_token(owner,email,'password-reset')
    grant=authorize_mfa(client,'recovery')
    response=client.post('/auth/mfa/enroll',json={'password':password,'new_password':'Rotation recovery password 123!','authorization':grant},headers=ORIGIN)
    assert response.status_code==200
    replacement=pyotp.parse_uri(response.json()['provisioning_uri'])
    flow_hash=token_digest(new_token())
    with psycopg.connect(owner) as db:
        db.execute("""INSERT INTO oidc_login_flows(browser_hash,state_hash,encrypted_state,config_hash,expires_at)
                      VALUES(%s,%s,%s,'synthetic-rotation-config',now()+interval '5 minutes')""",
                   (flow_hash,token_digest(new_token()),cipher().encrypt(b'{"oidc":"synthetic-rotation-state"}').decode()))
    old_key=os.environ['AUTH_ENCRYPTION_KEY'];new_key=Fernet.generate_key().decode()
    monkeypatch.setenv('AUTH_ENCRYPTION_KEYS',json.dumps({'v2':new_key,'legacy':old_key}))
    monkeypatch.setenv('AUTH_ACTIVE_KEY_ID','v2')
    with psycopg.connect(owner) as db:
        assert rotate_rows(db)>=3
    monkeypatch.setenv('AUTH_ENCRYPTION_KEYS',json.dumps({'v2':new_key}))
    assert mail_token(owner,email,'password-reset')==token
    with psycopg.connect(owner) as db:
        factor=db.execute('SELECT encrypted_secret FROM mfa_factors WHERE user_id=%s',(user,)).fetchone()[0]
        pending=db.execute('SELECT encrypted_secret FROM mfa_enrollments WHERE user_id=%s',(user,)).fetchone()[0]
        assert factor.startswith('v2:') and pending.startswith('v2:')
        assert cipher().decrypt(pending.encode()).decode()==replacement.secret
        flow=db.execute('SELECT encrypted_state FROM oidc_login_flows WHERE browser_hash=%s',(flow_hash,)).fetchone()[0]
        assert flow.startswith('v2:') and cipher().decrypt(flow.encode())==b'{"oidc":"synthetic-rotation-state"}'
    assert client.post('/auth/mfa/verify',json={'code':replacement.now()},headers=ORIGIN).status_code==200
    # Rotation is atomic: unreadable data aborts all updates, never drops factors.
    with psycopg.connect(owner) as db:
        other=db.execute('SELECT id FROM users WHERE id<>%s AND NOT EXISTS(SELECT 1 FROM mfa_factors f WHERE f.user_id=users.id) LIMIT 1',(user,)).fetchone()[0]
        db.execute("INSERT INTO mfa_factors(user_id,encrypted_secret) VALUES(%s,'corrupt-ciphertext')",(other,))
    newest=Fernet.generate_key().decode()
    monkeypatch.setenv('AUTH_ENCRYPTION_KEYS',json.dumps({'v3':newest,'v2':new_key}));monkeypatch.setenv('AUTH_ACTIVE_KEY_ID','v3')
    with pytest.raises(InvalidToken):
        with psycopg.connect(owner) as db: rotate_rows(db)
    with psycopg.connect(owner) as db:
        assert db.execute('SELECT encrypted_secret FROM mfa_factors WHERE user_id=%s',(user,)).fetchone()[0].startswith('v2:')
        # Clean only this intentional poison fixture so later test fixtures remain usable.
        db.execute('DELETE FROM mfa_factors WHERE user_id=%s',(other,))


def test_l3_five_smtp_attempts_fit_token_lifetime_and_scrub_exhausted_payload(identity,monkeypatch):
    import smtplib
    from app.mail_worker import deliver_one
    owner=identity[1];monkeypatch.setenv('SMTP_FROM','lms@example.invalid')
    identifier=uuid4()
    with psycopg.connect(owner) as db:
        db.execute("UPDATE auth_mail_outbox SET expires_at=now()-interval '1 second'")
        db.execute("INSERT INTO auth_mail_outbox(id,recipient,kind,encrypted_token,expires_at) VALUES(%s,'retry@example.invalid','invitation',%s,now()+interval '1 hour')",(identifier,cipher().encrypt(new_token().encode()).decode()))
    calls=[]
    def failed(message):
        calls.append(True);raise smtplib.SMTPException('synthetic outage')
    for attempt in range(5):
        with psycopg.connect(os.environ['TEST_MAIL_DATABASE_URL'],row_factory=dict_row) as db:
            assert deliver_one(db,failed)
            row=db.execute('SELECT * FROM auth_mail_outbox WHERE id=%s',(identifier,)).fetchone()
            assert row['attempts']==attempt+1
            if attempt<4:
                delay=(row['next_attempt_at']-datetime.now(timezone.utc)).total_seconds()
                assert 590<delay<=600
                assert 4*delay<(row['expires_at']-row['created_at']).total_seconds()
                db.execute('UPDATE auth_mail_outbox SET next_attempt_at=now() WHERE id=%s',(identifier,))
            else:
                assert row['dead_at'] and row['recipient']=='' and row['encrypted_token'] is None
    assert len(calls)==5
    with psycopg.connect(os.environ['TEST_MAIL_DATABASE_URL'],row_factory=dict_row) as db:
        assert deliver_one(db,failed) is False


def test_l6_member_discovery_role_changes_and_revoke_are_tenant_scoped(identity):
    client,owner,user,tenant,foreign,_,password=identity
    headers,_=make_admin(identity)
    with psycopg.connect(owner) as db:
        other,other_email=db.execute('SELECT u.id,u.email FROM users u JOIN memberships m ON m.user_id=u.id WHERE m.tenant_id=%s',(foreign,)).fetchone()
        db.execute("INSERT INTO memberships(id,tenant_id,user_id,role) VALUES(%s,%s,%s,'teacher')",(uuid4(),tenant,other))
    with TestClient(app,base_url='https://testserver') as member:
        assert sign_in(member,other_email,password).status_code==200
        assert member.get('/auth/tenant-members',headers=headers).status_code==403
        rows=client.get('/auth/tenant-members',headers=headers).json()['members']
        assert {row['user_id'] for row in rows}=={str(user),str(other)}
        assert all('password_hash' not in row for row in rows)
        assert client.get('/auth/tenant-members',headers={**headers,'x-tenant-id':str(foreign)}).status_code==403
        assert client.post(f'/auth/memberships/{other}/role',json={'role':'admin'},headers=headers).status_code==200
        # Promoting an existing password session must immediately demand MFA.
        assert member.get('/auth/me',headers=headers).status_code==403
        assert client.post(f'/auth/memberships/{other}/role',json={'role':'teacher'},headers=headers).status_code==200
        assert member.get('/auth/me',headers=headers).status_code==200
        assert client.post(f'/auth/memberships/{other}/revoke',headers=headers).status_code==200
        assert member.get('/auth/me',headers=headers).status_code==403
        assert member.get('/auth/me',headers={'x-tenant-id':str(foreign)}).status_code==200
    assert client.post(f'/auth/memberships/{user}/role',json={'role':'student'},headers=headers).status_code==404
    audit=client.get('/auth/audit',headers=headers).json()
    assert sum(row['action']=='membership.role_changed' and row['target_id']==str(other) for row in audit)==2


def test_l6_member_pagination_has_no_gaps_or_foreign_records(identity):
    client,owner,_,tenant,foreign,_,_=identity
    headers,_=make_admin(identity)
    expected=set()
    with psycopg.connect(owner) as db:
        expected.update(str(row[0]) for row in db.execute('SELECT user_id FROM memberships WHERE tenant_id=%s',(tenant,)))
        for _ in range(101):
            uid=uuid4();expected.add(str(uid))
            db.execute("INSERT INTO users(id,email,password_hash) VALUES(%s,%s,'unused-synthetic-hash')",(uid,f'{uid}@example.invalid'))
            db.execute("INSERT INTO memberships(id,tenant_id,user_id,role) VALUES(%s,%s,%s,'student')",(uuid4(),tenant,uid))
    first=client.get('/auth/tenant-members',headers=headers).json()
    assert len(first['members'])==100 and first['next_cursor']
    second=client.get('/auth/tenant-members',params={'after':first['next_cursor']},headers=headers).json()
    seen=[row['user_id'] for row in first['members']+second['members']]
    assert len(seen)==102 and len(set(seen))==102 and set(seen)==expected
    assert second['next_cursor'] is None


def test_m3_mfa_guess_budget_survives_relogin_and_does_not_lock_owner_network(identity):
    client=identity[0];headers,totp=make_admin(identity)
    with TestClient(app,base_url='https://testserver',client=('198.51.100.70',1)) as attacker:
        assert sign_in(attacker,identity[5],identity[6]).status_code==200
        wrong=next(str(number).zfill(6) for number in range(10)
                   if not totp.verify(str(number).zfill(6),valid_window=1))
        for _ in range(5):
            assert attacker.post('/auth/mfa/verify',json={'code':wrong},headers=ORIGIN).status_code==400
        assert sign_in(attacker,identity[5],identity[6]).status_code==200
        assert attacker.post('/auth/mfa/verify',json={'code':wrong},headers=ORIGIN).status_code==429
    with TestClient(app,base_url='https://testserver',client=('198.51.100.71',1)) as owner:
        assert sign_in(owner,identity[5],identity[6]).status_code==200
        counter=totp.timecode(datetime.now(timezone.utc))+1
        assert owner.post('/auth/mfa/verify',json={'code':totp.at(counter*totp.interval)},headers=ORIGIN).status_code==200
        assert owner.get('/auth/me',headers=headers).status_code==200


def test_m3_password_holder_cannot_exhaust_capacity_or_evict_owner_mfa_and_approved_recovery(identity):
    client,owner,user,tenant,_,email,password=identity
    assert sign_in(client,email,password).status_code==200
    enroll_mfa(client,password)
    verified_hash=token_digest(client.cookies.get('maaher_session'))
    with psycopg.connect(owner) as db:
        for _ in range(100):
            db.execute("INSERT INTO sessions(token_hash,user_id,expires_at) VALUES(%s,%s,now()+interval '1 hour')",(token_digest(new_token()),user))
    with TestClient(app,base_url='https://testserver') as recovering:
        assert sign_in(recovering,email,password).status_code==200
        proof=authorize_mfa(recovering,'recovery')
        pinned=token_digest(recovering.cookies.get('maaher_session'))
        with TestClient(app,base_url='https://testserver') as next_login:
            assert sign_in(next_login,email,password).status_code==200
        with psycopg.connect(owner) as db:
            assert db.execute('SELECT count(*) FROM sessions WHERE user_id=%s AND NOT mfa_verified',(user,)).fetchone()[0]==100
            assert db.execute('SELECT mfa_verified FROM sessions WHERE token_hash=%s',(verified_hash,)).fetchone()[0] is True
            assert db.execute('SELECT token_hash FROM sessions WHERE token_hash=%s',(pinned,)).fetchone()[0]==pinned
        assert client.get('/auth/me',headers={'x-tenant-id':str(tenant)}).status_code==200
