"""Secret redaction and network-destination boundaries of the local checker."""
from pathlib import Path
import runpy
from urllib.parse import urlencode

import httpx

module = runpy.run_path(str(Path(__file__).resolve().parents[1]/'verify-auth0-local.py'))
Report = module['Report']
SENTINEL = 'private-synthetic-secret-do-not-log'
ORIGIN = 'http://127.0.0.1:3000'


def test_untrusted_discovery_issuer_is_not_followed(capsys):
    calls = []
    def handler(request):
        calls.append(str(request.url))
        return httpx.Response(200,json={'issuer':'https://evil.invalid/','jwks_uri':'https://evil.invalid/'+SENTINEL})
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        assert module['public_provider'](client,Report()) is False
    assert calls == [module['ISSUER']+'.well-known/openid-configuration']
    assert SENTINEL not in capsys.readouterr().out


def test_response_body_never_becomes_a_diagnostic(capsys):
    with httpx.Client(transport=httpx.MockTransport(lambda request:httpx.Response(503,text=SENTINEL))) as client:
        module['application'](client,{'APP_ORIGIN':ORIGIN},Report(),True)
    output = capsys.readouterr().out
    assert SENTINEL not in output and 'FAIL' in output


def start_response(request, malicious=False):
    if request.url.path.endswith('/config'):
        return httpx.Response(200,json={'enabled':True,'assurance':'maaher-fido2-uv-v1'})
    params = {'client_id':module['CLIENT_ID'],'response_type':'code','code_challenge_method':'S256',
              'prompt':'login','max_age':'0','nonce':SENTINEL,'state':SENTINEL,'code_challenge':SENTINEL,
              'redirect_uri':'https://evil.invalid/' if malicious else ORIGIN+'/api/auth/oidc/callback'}
    return httpx.Response(200,json={'authorization_url':module['ISSUER']+'authorize?'+urlencode(params)},
                          headers={'set-cookie':f'maaher_oidc_flow={SENTINEL}; HttpOnly; SameSite=Lax; Path=/'})


def test_start_flow_validates_parameters_without_printing_capabilities(capsys):
    report = Report()
    with httpx.Client(transport=httpx.MockTransport(start_response)) as client:
        module['application'](client,{'APP_ORIGIN':ORIGIN},report,True)
    assert all(item[1]=='PASS' for item in report.items)
    assert SENTINEL not in capsys.readouterr().out


def test_bad_callback_is_not_followed_or_accepted(capsys):
    calls = []
    def handler(request):
        calls.append(str(request.url));return start_response(request,True)
    report = Report()
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        module['application'](client,{'APP_ORIGIN':ORIGIN},report,True)
    assert report.items[-1][1]=='FAIL'
    assert all(url.startswith(ORIGIN) for url in calls)
    assert SENTINEL not in capsys.readouterr().out


def test_nonlocal_origin_prevents_live_probes(tmp_path,monkeypatch,capsys):
    for name in module['NAMES']:monkeypatch.delenv(name,raising=False)
    (tmp_path/'.env').write_text(f'AUTH0_DOMAIN={module["DOMAIN"]}\nAUTH0_CLIENT_ID={module["CLIENT_ID"]}\nAUTH0_CLIENT_SECRET={SENTINEL}\nAPP_ENV=local\nAPP_ORIGIN=https://evil.invalid\n')
    config, valid = module['load_config'](tmp_path,Report())
    assert valid is False and config['AUTH0_CLIENT_SECRET']==SENTINEL
    assert SENTINEL not in capsys.readouterr().out


def test_database_errors_do_not_print_credentials(monkeypatch,capsys):
    def fail(*args,**kwargs):
        assert kwargs['options']=='-c default_transaction_read_only=on'
        raise module['psycopg'].OperationalError('failed connection '+SENTINEL)
    monkeypatch.setattr(module['psycopg'],'connect',fail)
    module['database']({'MIGRATION_DATABASE_URL':SENTINEL,'AUTH_DATABASE_URL':SENTINEL},Report())
    output = capsys.readouterr().out
    assert SENTINEL not in output and 'FAIL' in output


def test_service_with_the_wrong_profile_prevents_start_flow(capsys):
    calls = []
    def handler(request):
        calls.append(request.url.path)
        return start_response(request)
    report = Report()
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        module['application'](client,{'APP_ORIGIN':ORIGIN,'AUTH0_ASSURANCE_PROFILE':'dev-totp'},report,True)
    assert calls == ['/api/auth/oidc/config']
    assert report.items[-1][1]=='FAIL'
    assert SENTINEL not in capsys.readouterr().out


def test_unknown_profile_prevents_live_probes(tmp_path,monkeypatch,capsys):
    for name in module['NAMES']:monkeypatch.delenv(name,raising=False)
    (tmp_path/'.env').write_text(f'AUTH0_DOMAIN={module["DOMAIN"]}\nAUTH0_CLIENT_ID={module["CLIENT_ID"]}\nAUTH0_CLIENT_SECRET={SENTINEL}\nAPP_ENV=local\nAPP_ORIGIN={ORIGIN}\nAUTH0_ASSURANCE_PROFILE=unknown\n')
    _, valid = module['load_config'](tmp_path,Report())
    assert valid is False
    assert SENTINEL not in capsys.readouterr().out
