"""Internal Fernet proof of validation; never a login credential or client input."""
import hashlib
import hmac
import json
from cryptography.fernet import InvalidToken
from .auth_support import cipher

POLICY='maaher-content-v3-controls'
# Same Markdown/URL/control acceptance rules; resource budget changes do not
# invalidate old proofs or force legacy course downtime/new assignment versions.
COMPATIBLE_POLICIES=(POLICY,'maaher-content-v2-controls-cpu250')


def fingerprint(kind,context,content,resources=None,policy=POLICY):
    data=content.encode('utf8')
    digest=hashlib.sha256(json.dumps([policy,kind,[str(x) for x in context]],separators=(',',':')).encode())
    digest.update(len(data).to_bytes(8,'big'));digest.update(data)
    digest.update(json.dumps(resources or [],sort_keys=True,separators=(',',':'),ensure_ascii=False).encode('utf8'))
    return ('content-validation:'+digest.hexdigest()).encode()


def seal(kind,context,content,resources=None,ring=None):
    return (ring or cipher()).encrypt(fingerprint(kind,context,content,resources)).decode()


def valid(token,kind,context,content,resources=None,ring=None):
    if not isinstance(token,str) or not token or len(token)>1024:return False
    try:
        payload=(ring or cipher()).decrypt(token.encode())
        return any(hmac.compare_digest(payload,fingerprint(kind,context,content,resources,policy)) for policy in COMPATIBLE_POLICIES)
    except (InvalidToken,UnicodeError,ValueError):return False
