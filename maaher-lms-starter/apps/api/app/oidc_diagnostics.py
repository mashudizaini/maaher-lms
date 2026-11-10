"""Opt-in local diagnostics: fixed codes only, never callback/token contents."""
from enum import Enum
import logging
import os
from urllib.parse import urlsplit

logger = logging.getLogger("maaher.auth.oidc")


class Denial(Enum):
    INVALID_CALLBACK = "OIDC_INVALID_CALLBACK"
    FLOW_UNAVAILABLE = "OIDC_FLOW_UNAVAILABLE"
    FLOW_CONFIG_CHANGED = "OIDC_FLOW_CONFIG_CHANGED"
    PROVIDER_DENIED = "OIDC_PROVIDER_DENIED"
    OWNER_APPROVAL_REQUIRED = "OIDC_OWNER_APPROVAL_REQUIRED"
    DEV_POLICY_UNCONFIGURED = "OIDC_DEV_POLICY_UNCONFIGURED"
    FIDO2_POLICY_ACTIVE = "OIDC_FIDO2_POLICY_ACTIVE"
    STAFF_POLICY_UNCONFIGURED = "OIDC_STAFF_POLICY_UNCONFIGURED"
    FLOW_PAYLOAD_INVALID = "OIDC_FLOW_PAYLOAD_INVALID"
    CLIENT_AUTH_FAILED = "OIDC_CLIENT_AUTH_FAILED"
    CODE_EXCHANGE_REJECTED = "OIDC_CODE_EXCHANGE_REJECTED"
    PROVIDER_PROTOCOL_ERROR = "OIDC_PROVIDER_PROTOCOL_ERROR"
    PROVIDER_HTTP_FAILED = "OIDC_PROVIDER_HTTP_FAILED"
    ID_TOKEN_INVALID = "OIDC_ID_TOKEN_INVALID"
    TOKEN_RESPONSE_INVALID = "OIDC_TOKEN_RESPONSE_INVALID"
    ASSURANCE_MISMATCH = "OIDC_ASSURANCE_MISMATCH"
    MFA_MISSING = "OIDC_MFA_MISSING"
    AUTH_TIME_INVALID = "OIDC_AUTH_TIME_INVALID"
    SUBJECT_INVALID = "OIDC_SUBJECT_INVALID"
    IDENTITY_UNAVAILABLE = "OIDC_IDENTITY_UNAVAILABLE"


def log_denial(code: Denial):
    if os.environ.get("AUTH0_LOCAL_DIAGNOSTICS") != "true" or os.environ.get("APP_ENV") != "local":
        return
    try:
        origin = urlsplit(os.environ.get("APP_ORIGIN", ""))
        origin.port
    except ValueError:
        return
    if (origin.scheme not in {"http", "https"} or origin.hostname not in {"localhost", "127.0.0.1"}
            or origin.username or origin.password or origin.path or origin.query or origin.fragment):
        return
    logger.warning("MAAHER_AUTH0_DIAGNOSTIC code=%s", code.value)


def provider_denial(description):
    # Untrusted callback text selects an exact allowlisted hint, never a log
    # string or an authorization decision. Unknown descriptions stay generic.
    return {
        "Owner approval for synthetic development is required": Denial.OWNER_APPROVAL_REQUIRED,
        "Development login policy is not configured": Denial.DEV_POLICY_UNCONFIGURED,
        "Verified staff enrollment is required": Denial.FIDO2_POLICY_ACTIVE,
        "Staff login policy is not configured": Denial.STAFF_POLICY_UNCONFIGURED,
    }.get(description, Denial.PROVIDER_DENIED)
