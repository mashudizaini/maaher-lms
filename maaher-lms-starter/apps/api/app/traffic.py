"""Trusted ingress identity and pre-Argon2, fixed-size PostgreSQL budgets."""
import ipaddress
import os
from secrets import compare_digest

from fastapi import HTTPException
from .database import auth_transaction
from .auth_support import throttle

ANONYMOUS_PATHS={'/auth/login','/auth/password-reset/request','/auth/password-reset/confirm','/auth/invitations/accept',
                 '/auth/mfa/request','/auth/mfa/enroll','/auth/mfa/verify','/auth/oidc/login'}


def client_identity(request):
    secret=os.environ.get('BFF_API_SECRET')
    presented=request.headers.get('x-maaher-bff-key','')
    if secret and compare_digest(secret,presented):
        try:
            return str(ipaddress.ip_address(request.headers.get('x-maaher-client-ip','')))
        except ValueError:
            raise HTTPException(403,'Identitas jaringan tidak valid') from None
    if os.environ.get('APP_ENV') not in {'local','test'}:
        raise HTTPException(503,'Jalur ingress tepercaya belum dikonfigurasi')
    # X-Forwarded-For and user-provided identity headers are ignored in local mode.
    return request.client.host if request.client else 'local-unknown'


def admit(request):
    identity=client_identity(request)
    request.state.client_key=identity
    with auth_transaction() as db:
        if not throttle(db,'global',limit=120,minutes=1,kind='global',bucket_id=0):
            return False
        return throttle(db,identity,limit=30,minutes=1,kind='client')
