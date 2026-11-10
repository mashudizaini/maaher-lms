"""Test-only uvicorn target with a signed, in-memory HTTPS IdP transport.

Never selected by app code or copied into the runtime image. The test runner
sets synthetic config and uses a fresh maaher_test_* DB. No network Auth0 calls.
"""
import os
import time
from urllib.parse import parse_qs,urlsplit

import httpx
import psycopg
from joserfc import jwt
from joserfc.jwk import RSAKey
from authlib.oauth2.rfc7636 import create_s256_code_challenge

from app.main import app
from app import oidc

if os.environ.get('APP_ENV') != 'local' or os.environ.get('AUTH0_DOMAIN') != 'browser-tests.us.auth0.com':
    raise RuntimeError('Synthetic local browser probe only')
with psycopg.connect(os.environ['TEST_MIGRATION_DATABASE_URL']) as guard:
    if not guard.execute('SELECT current_database()').fetchone()[0].startswith('maaher_test_'):
        raise RuntimeError('Disposable test database required')

key = RSAKey.generate_key(2048,parameters={'kid':'synthetic-browser-key'})
issued = {}
original = oidc.make_client


def handle(request):
    if str(request.url) == 'https://browser-tests.us.auth0.com/.well-known/jwks.json':
        return httpx.Response(200,json={'keys':[key.as_dict(private=False)]})
    assert str(request.url) == 'https://browser-tests.us.auth0.com/oauth/token'
    form = parse_qs(request.content.decode())
    transaction = issued.pop(form['code'][0])
    assert create_s256_code_challenge(form['code_verifier'][0]) == transaction['code_challenge'][0]
    now = int(time.time())
    claims = {'iss':'https://browser-tests.us.auth0.com/','sub':'auth0|synthetic-browser-staff',
              'aud':'synthetic-browser-client','iat':now,'exp':now+300,'auth_time':now,
              'nonce':transaction['nonce'][0],'amr':['pwd','mfa'],oidc.ASSURANCE_CLAIM:oidc.settings().assurance}
    encoded = jwt.encode({'alg':'RS256','kid':key.kid},claims,key)
    return httpx.Response(200,json={'id_token':encoded,'access_token':'synthetic-browser-access-token',
                                    'token_type':'Bearer','expires_in':300})


def make(config):
    client = original(config)
    client.client_kwargs.update(transport=httpx.MockTransport(handle),trust_env=False)
    create = client.create_authorization_url

    async def authorization(*args,**kwargs):
        data = await create(*args,**kwargs)
        params = parse_qs(urlsplit(data['url']).query)
        issued[params['state'][0]] = params
        return data

    client.create_authorization_url = authorization
    return client


oidc.make_client = make
