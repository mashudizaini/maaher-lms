"""Explicit assurance profiles. Phone TOTP is only for local synthetic data."""
import os
from urllib.parse import urlsplit

FIDO2_ASSURANCE = "maaher-fido2-uv-v1"
DEV_TOTP_ASSURANCE = "maaher-dev-totp-v1"


def configured_assurance():
    profile = os.environ.get("AUTH0_ASSURANCE_PROFILE", "fido2")
    if profile == "fido2":
        return FIDO2_ASSURANCE
    if profile != "dev-totp" or os.environ.get("APP_ENV") != "local":
        return None
    try:
        origin = urlsplit(os.environ.get("APP_ORIGIN", ""))
        origin.port
    except ValueError:
        return None
    if (origin.scheme not in {"http", "https"} or origin.hostname not in {"localhost", "127.0.0.1"}
            or origin.username or origin.password or origin.path or origin.query or origin.fragment):
        return None
    return DEV_TOTP_ASSURANCE
