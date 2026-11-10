"""Local development preflight. Never prints secrets, tokens or response bodies.

Run with the project's venv on the Mac where .env and Docker actually live.
Public discovery is read-only. --start-flow creates only a five-minute login
attempt, does not follow the authorization URL, and never sends email or logs in.
"""
import argparse
from pathlib import Path
import os
from urllib.parse import parse_qs, urlsplit

from dotenv import dotenv_values
import httpx
import psycopg

DOMAIN = 'dev-hl2un81cojtbhbv4.us.auth0.com'
CLIENT_ID = 'FjD4enWFIU9PNdnLjGwc1M1x4p8xsdW3'
ISSUER = 'https://' + DOMAIN + '/'
NAMES = ('AUTH0_DOMAIN','AUTH0_CLIENT_ID','AUTH0_CLIENT_SECRET','APP_ORIGIN',
         'APP_ENV','LOCAL_INSECURE_COOKIES','MIGRATION_DATABASE_URL','AUTH_DATABASE_URL',
         'AUTH0_ASSURANCE_PROFILE')
ASSURANCES = {'fido2':'maaher-fido2-uv-v1','dev-totp':'maaher-dev-totp-v1'}


class Report:
    def __init__(self):
        self.items = []

    def add(self, check, status, detail):
        self.items.append((check,status,detail))
        print(f'{status}: {check} — {detail}')

    def result(self):
        failed = sum(item[1]=='FAIL' for item in self.items)
        skipped = sum(item[1]=='SKIP' for item in self.items)
        print(f'Preflight: {len(self.items)-failed-skipped} PASS, {failed} FAIL, {skipped} SKIP.')
        print('Ini bukan login end-to-end atau persetujuan produksi; Client Secret belum diuji pada token exchange.')
        return 1 if failed else (2 if skipped else 0)


def load_config(root, report):
    try:
        values = dotenv_values(root/'.env') if (root/'.env').is_file() else {}
    except (OSError,UnicodeError,ValueError):
        report.add('.env','FAIL','file lokal belum dapat dibaca sebagai dotenv; isi file tidak ditampilkan')
        return {},False
    config = {name: os.environ.get(name,values.get(name) or '') for name in NAMES}
    if not config['AUTH0_ASSURANCE_PROFILE'] and 'AUTH0_ASSURANCE_PROFILE' not in values and 'AUTH0_ASSURANCE_PROFILE' not in os.environ:
        config['AUTH0_ASSURANCE_PROFILE'] = 'fido2'
    ready = True
    for name, expected in (('AUTH0_DOMAIN',DOMAIN),('AUTH0_CLIENT_ID',CLIENT_ID)):
        match = config[name] == expected
        report.add(name,'PASS' if match else 'FAIL','sesuai aplikasi yang didaftarkan' if match else 'periksa field ini pada .env/export lokal')
        ready = ready and match
    secret = bool(config['AUTH0_CLIENT_SECRET'])
    report.add('AUTH0_CLIENT_SECRET','PASS' if secret else 'FAIL','tersedia; nilainya tidak ditampilkan' if secret else 'belum tersedia pada proses lokal')
    ready = ready and secret
    try:
        origin = urlsplit(config['APP_ORIGIN'])
        origin.port
        valid = (origin.hostname in {'localhost','127.0.0.1'} and not origin.username
                 and not origin.password and not origin.path and not origin.query and not origin.fragment
                 and origin.scheme in {'http','https'} and config['APP_ENV']=='local')
    except ValueError:
        valid = False
    report.add('development origin','PASS' if valid else 'FAIL','origin loopback local valid' if valid else 'gunakan APP_ENV=local dan APP_ORIGIN loopback exact tanpa trailing slash')
    profile = config['AUTH0_ASSURANCE_PROFILE'] in ASSURANCES
    report.add('assurance profile','PASS' if profile else 'FAIL','profil dikenali; dev-totp bukan assurance produksi' if profile else 'gunakan fido2 atau dev-totp secara eksplisit')
    return config, ready and valid and profile


def public_provider(client, report):
    try:
        response = client.get(ISSUER+'.well-known/openid-configuration')
        if response.status_code != 200:
            report.add('Auth0 discovery','FAIL',f'HTTP {response.status_code}; response body tidak ditampilkan')
            return False
        metadata = response.json()
        expected = {'issuer':ISSUER,'authorization_endpoint':ISSUER+'authorize',
                    'token_endpoint':ISSUER+'oauth/token','jwks_uri':ISSUER+'.well-known/jwks.json'}
        if any(metadata.get(k)!=v for k,v in expected.items()):
            report.add('Auth0 discovery','FAIL','issuer/endpoint tidak cocok; URL dari response tidak diikuti')
            return False
        if ('code' not in metadata.get('response_types_supported',[])
                or 'RS256' not in metadata.get('id_token_signing_alg_values_supported',[])
                or 'client_secret_basic' not in metadata.get('token_endpoint_auth_methods_supported',[])):
            report.add('Auth0 discovery','FAIL','code/RS256/client_secret_basic belum terkonfirmasi')
            return False
        report.add('Auth0 discovery','PASS','issuer, endpoint dan kemampuan protokol sesuai')
        keys = client.get(expected['jwks_uri'])
        if keys.status_code != 200:
            report.add('Auth0 JWKS','FAIL',f'HTTP {keys.status_code}; response body tidak ditampilkan')
            return False
        available = any(k.get('kty')=='RSA' and k.get('kid') and k.get('n') and k.get('e')
                        and k.get('alg','RS256')=='RS256' for k in keys.json().get('keys',[]))
        report.add('Auth0 JWKS','PASS' if available else 'FAIL','public RSA key tersedia' if available else 'public RSA key tidak terkonfirmasi')
        return available
    except (httpx.HTTPError,ValueError,TypeError,AttributeError):
        report.add('Auth0 network','FAIL','HTTPS/DNS/proxy/TLS atau format response gagal; periksa jaringan host tanpa menonaktifkan TLS')
        return False


def database(config, report):
    if not config['MIGRATION_DATABASE_URL'] or not config['AUTH_DATABASE_URL']:
        report.add('database','SKIP','migration/auth URL belum tersedia; jangan bagikan nilainya')
        return
    try:
        # Read-only transactions; never migrations, cleanup, provisioning or writes.
        with psycopg.connect(config['MIGRATION_DATABASE_URL'],connect_timeout=5,options='-c default_transaction_read_only=on') as owner:
            name = owner.execute('SELECT current_database()').fetchone()[0]
            if not name.startswith('maaher_test_'):
                report.add('database','FAIL','checker hanya untuk DB development sintetis maaher_test_*; tidak menginspeksi data pengguna')
                return
            revision = owner.execute('SELECT version_num FROM alembic_version').fetchone()[0]
            if revision not in {'0005_dev_totp', '0006_courses'}:
                report.add('database migration','FAIL','migration 0005 belum aktif; periksa source dan DB development yang dipilih')
                return
            report.add('database migration','PASS','schema Auth0 tersedia pada head yang dikenali di DB sintetis')
        with psycopg.connect(config['AUTH_DATABASE_URL'],connect_timeout=5,options='-c default_transaction_read_only=on') as auth:
            if auth.execute('SELECT current_database()').fetchone()[0] != name:
                report.add('auth role','FAIL','auth dan migration URL menuju database berbeda')
                return
            valid = auth.execute("""SELECT NOT r.rolsuper AND NOT r.rolbypassrls
                AND pg_has_role(current_user,'maaher_auth','MEMBER')
                AND NOT pg_has_role(current_user,'maaher_runtime','MEMBER')
                AND NOT EXISTS(SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
                  WHERE n.nspname='public' AND c.relkind='r' AND pg_has_role(current_user,c.relowner,'USAGE'))
                FROM pg_roles r WHERE r.rolname=current_user""").fetchone()[0]
            report.add('auth role','PASS' if valid else 'FAIL','credential auth terpisah/nonowner' if valid else 'periksa pemisahan role DB')
            if valid:
                present = auth.execute("SELECT EXISTS(SELECT 1 FROM oidc_identities i JOIN users u ON u.id=i.user_id WHERE i.issuer=%s AND i.status='active' AND u.status='active')",(ISSUER,)).fetchone()[0]
                report.add('identity binding','PASS' if present else 'FAIL','binding aktif tersedia; bukan bukti enrollment/key live' if present else 'belum ada binding terverifikasi; ikuti runbook tanpa auto-link email')
    except (psycopg.Error,ValueError,IndexError,TypeError):
        report.add('database connection/schema','FAIL','koneksi/role/schema belum dapat diverifikasi; detail credential tidak dicetak')


def application(client, config, report, start_flow=False):
    origin = config['APP_ORIGIN']
    try:
        response = client.get(origin+'/api/auth/oidc/config')
        if response.status_code!=200 or response.json().get('enabled') is not True:
            report.add('API/web Auth0 config','FAIL','service belum aktif/konfigurasi belum termuat; periksa source dan restart service development')
            return
        expected_assurance = ASSURANCES.get(config.get('AUTH0_ASSURANCE_PROFILE','fido2'))
        if not expected_assurance or response.json().get('assurance') != expected_assurance:
            report.add('API/web Auth0 config','FAIL','profil service berbeda dari konfigurasi lokal; periksa source dan restart API')
            return
        report.add('API/web Auth0 config','PASS','service menyatakan konfigurasi tersedia; secret belum divalidasi provider')
        if not start_flow:
            report.add('OIDC start flow','SKIP','jalankan dengan --start-flow untuk memeriksa cookie/state/PKCE; tidak melakukan login')
            return
        started = client.post(origin+'/api/auth/oidc/login',json={},headers={'origin':origin})
        if started.status_code!=200:
            report.add('OIDC start flow','FAIL',f'HTTP {started.status_code}; response body tidak ditampilkan')
            return
        target = urlsplit(started.json().get('authorization_url',''))
        query = parse_qs(target.query)
        cookie = next((c for c in client.cookies.jar if c.name=='maaher_oidc_flow'),None)
        expected = {'client_id':[CLIENT_ID],'redirect_uri':[origin+'/api/auth/oidc/callback'],
                    'response_type':['code'],'code_challenge_method':['S256'],'prompt':['login'],'max_age':['0']}
        valid = (target.scheme=='https' and target.netloc==DOMAIN and target.path=='/authorize'
                 and all(query.get(k)==v for k,v in expected.items())
                 and query.get('nonce') and query.get('state') and query.get('code_challenge')
                 and cookie is not None and cookie.has_nonstandard_attr('HttpOnly')
                 and str(cookie.get_nonstandard_attr('SameSite','')).lower()=='lax'
                 and (urlsplit(origin).scheme=='http' or cookie.secure))
        report.add('OIDC start flow','PASS' if valid else 'FAIL','URL/callback/state/nonce/PKCE/cookie sesuai; nilainya tidak ditampilkan' if valid else 'parameter atau cookie belum sesuai implementasi')
        print('Flow diagnostik tidak dibuka; masa berlaku maksimal lima menit. Login nyata dimulai lewat tombol Auth0 di browser Anda.')
    except (httpx.HTTPError,ValueError,TypeError,AttributeError):
        report.add('API/web connection','FAIL','service loopback/response belum dapat diverifikasi; raw response dan exception tidak dicetak')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project-root',type=Path,default=Path(__file__).resolve().parents[1])
    parser.add_argument('--start-flow',action='store_true')
    args = parser.parse_args()
    report = Report()
    root = args.project_root.resolve()
    source = (root/'apps/api/app/oidc.py').is_file()
    report.add('Auth0 source','PASS' if source else 'FAIL','source OIDC ditemukan' if source else 'terapkan source Auth0 development terlebih dahulu')
    config, valid = load_config(root,report)
    if valid and source:
        with httpx.Client(timeout=15,follow_redirects=False) as client:
            public_provider(client,report)
            database(config,report)
            application(client,config,report,args.start_flow)
    else:
        report.add('live probes','SKIP','lengkapi konfigurasi/source pada Mac; tidak ada secret yang perlu diunggah')
    return report.result()


if __name__=='__main__':
    raise SystemExit(main())
