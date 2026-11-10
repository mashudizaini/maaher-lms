import logging

import pytest

from app.oidc_diagnostics import Denial, log_denial, provider_denial


@pytest.mark.parametrize("enabled,environment,origin,logged", [
    ("true", "local", "http://127.0.0.1:3000", True),
    ("true", "local", "https://localhost", True),
    ("false", "local", "http://127.0.0.1:3000", False),
    ("", "local", "http://127.0.0.1:3000", False),
    ("true", "production", "http://127.0.0.1:3000", False),
    ("true", "test", "http://127.0.0.1:3000", False),
    ("true", "local", "https://lms.example.invalid", False),
    ("true", "local", "http://user@localhost", False),
    ("true", "local", "http://localhost/", False),
    ("true", "local", "http://localhost?debug=1", False),
    ("true", "local", "http://localhost#debug", False),
    ("true", "local", "http://localhost:bad", False),
    ("true", "local", "https://[broken", False),
])
def test_diagnostic_log_is_opt_in_and_local_loopback_only(monkeypatch, caplog, enabled, environment, origin, logged):
    monkeypatch.setenv("AUTH0_LOCAL_DIAGNOSTICS", enabled)
    monkeypatch.setenv("APP_ENV", environment)
    monkeypatch.setenv("APP_ORIGIN", origin)
    with caplog.at_level(logging.WARNING, logger="maaher.auth.oidc"):
        log_denial(Denial.PROVIDER_DENIED)
    messages = [record.getMessage() for record in caplog.records if record.name == "maaher.auth.oidc"]
    assert messages == (["MAAHER_AUTH0_DIAGNOSTIC code=OIDC_PROVIDER_DENIED"] if logged else [])


@pytest.mark.parametrize("description,expected", [
    ("Owner approval for synthetic development is required", Denial.OWNER_APPROVAL_REQUIRED),
    ("Development login policy is not configured", Denial.DEV_POLICY_UNCONFIGURED),
    ("Verified staff enrollment is required", Denial.FIDO2_POLICY_ACTIVE),
    ("Staff login policy is not configured", Denial.STAFF_POLICY_UNCONFIGURED),
    ("untrusted-private-email@example.invalid\nBearer private-token-sentinel", Denial.PROVIDER_DENIED),
    ("Owner approval for synthetic development is required private-sentinel", Denial.PROVIDER_DENIED),
])
def test_provider_error_text_only_selects_an_exact_fixed_hint(monkeypatch, caplog, description, expected):
    monkeypatch.setenv("AUTH0_LOCAL_DIAGNOSTICS", "true")
    monkeypatch.setenv("APP_ENV", "local")
    monkeypatch.setenv("APP_ORIGIN", "http://localhost:3000")
    code = provider_denial(description)
    assert code is expected
    with caplog.at_level(logging.WARNING, logger="maaher.auth.oidc"):
        log_denial(code)
    messages = [record.getMessage() for record in caplog.records if record.name == "maaher.auth.oidc"]
    assert messages == ["MAAHER_AUTH0_DIAGNOSTIC code=" + expected.value]
