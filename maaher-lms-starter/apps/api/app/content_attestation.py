"""Internal Fernet proof of validation; never a login credential or client input."""
import hashlib
import hmac
import json
from cryptography.fernet import InvalidToken
from .auth_support import cipher

POLICY='maaher-content-v2-controls-cpu250'


def fingerprint(kind,context,content,resources=None):
    data=content.encode('utf8')
    digest=hashlib.sha256(json.dumps([POLICY,kind,[str(x) for x in context]],separators=(',',':')).encode())
    digest.update(len(data).to_bytes(8,'big'));digest.update(data)
    digest.update(json.dumps(resources or [],sort_keys=True,separators=(',',':'),ensure_ascii=False).encode('utf8'))
    return ('content-validation:'+digest.hexdigest()).encode()


def seal(kind,context,content,resources=None,ring=None):
    return (ring or cipher()).encrypt(fingerprint(kind,context,content,resources)).decode()


def valid(token,kind,context,content,resources=None,ring=None):
    if not isinstance(token,str) or not token or len(token)>1024:return False
    try:return hmac.compare_digest((ring or cipher()).decrypt(token.encode()),fingerprint(kind,context,content,resources))
    except (InvalidToken,UnicodeError,ValueError):return False
