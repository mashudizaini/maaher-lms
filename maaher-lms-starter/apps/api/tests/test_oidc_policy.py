import pytest

from app.oidc_policy import configured_assurance, FIDO2_ASSURANCE, DEV_TOTP_ASSURANCE


def test_default_profile_remains_fido2(monkeypatch):
    monkeypatch.delenv("AUTH0_ASSURANCE_PROFILE", raising=False)
    monkeypatch.setenv("APP_ENV", "production")
    assert configured_assurance() == FIDO2_ASSURANCE


@pytest.mark.parametrize("environment,origin,allowed", [
    ("local", "http://127.0.0.1:3000", True),
    ("local", "https://localhost", True),
    ("production", "http://127.0.0.1:3000", False),
    ("staging", "http://127.0.0.1:3000", False),
    ("test", "http://127.0.0.1:3000", False),
    ("local", "https://lms.example.invalid", False),
    ("local", "http://localhost.evil.invalid", False),
    ("local", "http://user@localhost", False),
    ("local", "http://localhost/", False),
    ("local", "http://localhost?dev=1", False),
    ("local", "http://localhost#dev", False),
    ("local", "http://localhost:bad", False),
    ("local", "http://localhost:65536", False),
    ("local", "", False),
])
def test_dev_profile_requires_explicit_local_loopback(monkeypatch, environment, origin, allowed):
    monkeypatch.setenv("AUTH0_ASSURANCE_PROFILE", "dev-totp")
    monkeypatch.setenv("APP_ENV", environment)
    monkeypatch.setenv("APP_ORIGIN", origin)
    assert configured_assurance() == (DEV_TOTP_ASSURANCE if allowed else None)


def test_unknown_profile_fails_closed(monkeypatch):
    monkeypatch.setenv("AUTH0_ASSURANCE_PROFILE", "dev-totp-typo")
    assert configured_assurance() is None
