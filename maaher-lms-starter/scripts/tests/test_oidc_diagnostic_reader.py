from pathlib import Path
import runpy
import subprocess

module = runpy.run_path(str(Path(__file__).resolve().parents[1] / "read-auth0-diagnostics.py"))
SENTINEL = "private-token-email-and-url-sentinel"


def test_reader_extracts_only_complete_allowlisted_codes():
    assert module["extract_codes"](f"{SENTINEL}\napi | MAAHER_AUTH0_DIAGNOSTIC code=OIDC_OWNER_APPROVAL_REQUIRED\n"
                                   f"MAAHER_AUTH0_DIAGNOSTIC code=OIDC_{SENTINEL}\n"
                                   "MAAHER_AUTH0_DIAGNOSTIC code=OIDC_PROVIDER_DENIED extra-private-text\n") == ["OIDC_OWNER_APPROVAL_REQUIRED"]
    for code in module["CODES"]:
        assert module["extract_codes"]("api | MAAHER_AUTH0_DIAGNOSTIC code=" + code) == [code]


def test_file_output_omits_raw_text_and_prints_only_the_latest_code(tmp_path, capsys):
    path = tmp_path / "api.log"
    path.write_text(f"{SENTINEL}\nMAAHER_AUTH0_DIAGNOSTIC code=OIDC_PROVIDER_DENIED\n"
                    "MAAHER_AUTH0_DIAGNOSTIC code=OIDC_ASSURANCE_MISMATCH\n")
    assert module["main"](["--log-file", str(path)]) == 0
    output = capsys.readouterr().out
    assert SENTINEL not in output and str(path) not in output
    assert "OIDC_ASSURANCE_MISMATCH" in output and "OIDC_PROVIDER_DENIED" not in output


def test_compose_failure_never_prints_stderr_or_a_raw_response(monkeypatch, capsys):
    def run(command, **kwargs):
        assert command == ["docker", "compose", "logs", "--no-color", "--since", "10m", "--tail", "200", "api"]
        assert kwargs["stdout"] == subprocess.PIPE and kwargs["stderr"] == subprocess.STDOUT
        assert kwargs["timeout"] == 20
        return subprocess.CompletedProcess(command, 1, SENTINEL.encode(), SENTINEL.encode())
    monkeypatch.setattr(module["subprocess"], "run", run)
    assert module["main"](["--compose"]) == 1
    assert SENTINEL not in capsys.readouterr().out


def test_no_diagnostic_is_not_reported_as_a_success(tmp_path, capsys):
    path = tmp_path / "api.log"; path.write_text(SENTINEL)
    assert module["main"](["--log-file", str(path)]) == 2
    output = capsys.readouterr().out
    assert SENTINEL not in output and "SKIP" in output
