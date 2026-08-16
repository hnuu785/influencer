from __future__ import annotations

import importlib.util
from pathlib import Path
import ssl
import stat
import subprocess
import urllib.error

import pytest


SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "setup_brightdata.py"
SPEC = importlib.util.spec_from_file_location("setup_brightdata", SCRIPT_PATH)
assert SPEC and SPEC.loader
setup_brightdata = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(setup_brightdata)


def test_update_dotenv_replaces_settings_and_preserves_unrelated_values(tmp_path):
    env_path = tmp_path / ".env"
    env_path.write_text(
        "POSTGRES_DB=influence\n"
        "INFLUENCER_PROVIDER=public_web\n"
        "BRIGHTDATA_API_TOKEN=old\n"
        "BRIGHTDATA_API_TOKEN=duplicate-old\n",
        encoding="utf-8",
    )

    setup_brightdata.update_dotenv(
        env_path,
        {
            "INFLUENCER_PROVIDER": "brightdata",
            "BRIGHTDATA_API_TOKEN": "new-token-123456789012345",
            "BRIGHTDATA_BASE_URL": "https://api.brightdata.com",
        },
    )

    content = env_path.read_text(encoding="utf-8")
    assert "POSTGRES_DB=influence" in content
    assert "INFLUENCER_PROVIDER=brightdata" in content
    assert "BRIGHTDATA_API_TOKEN=new-token-123456789012345" in content
    assert "BRIGHTDATA_API_TOKEN=old" not in content
    assert "BRIGHTDATA_API_TOKEN=duplicate-old" not in content
    assert content.count("BRIGHTDATA_API_TOKEN=") == 1
    assert "BRIGHTDATA_BASE_URL=https://api.brightdata.com" in content
    assert stat.S_IMODE(env_path.stat().st_mode) == 0o600


def test_verify_token_accepts_success(monkeypatch):
    class Response:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

    monkeypatch.setattr(
        setup_brightdata.urllib.request,
        "urlopen",
        lambda *_args, **_kwargs: Response(),
    )

    assert setup_brightdata.verify_token("a" * 32) == "verified"


@pytest.mark.parametrize(
    ("status", "expected"),
    [(403, "verified_limited_permissions")],
)
def test_verify_token_accepts_limited_permission_response(monkeypatch, status, expected):
    def reject(*_args, **_kwargs):
        raise urllib.error.HTTPError("url", status, "Forbidden", {}, None)

    monkeypatch.setattr(setup_brightdata.urllib.request, "urlopen", reject)

    assert setup_brightdata.verify_token("a" * 32) == expected


def test_verify_token_rejects_unauthorized_key(monkeypatch):
    def reject(*_args, **_kwargs):
        raise urllib.error.HTTPError("url", 401, "Unauthorized", {}, None)

    monkeypatch.setattr(setup_brightdata.urllib.request, "urlopen", reject)

    with pytest.raises(RuntimeError, match="rejected"):
        setup_brightdata.verify_token("a" * 32)


def test_verify_token_uses_system_trust_store_for_python_ca_failure(monkeypatch):
    certificate_error = ssl.SSLCertVerificationError(
        1, "certificate verify failed: unable to get local issuer certificate"
    )

    def fail_python_trust_store(*_args, **_kwargs):
        raise urllib.error.URLError(certificate_error)

    monkeypatch.setattr(
        setup_brightdata.urllib.request, "urlopen", fail_python_trust_store
    )
    monkeypatch.setattr(
        setup_brightdata,
        "verify_token_with_curl",
        lambda token, url: "verified" if token and url else "unexpected",
    )

    assert setup_brightdata.verify_token("a" * 32) == "verified"


def test_curl_fallback_keeps_token_out_of_process_arguments(monkeypatch):
    captured = {}

    def run(args, **kwargs):
        captured["args"] = args
        captured["input"] = kwargs["input"]
        return subprocess.CompletedProcess(args, 0, stdout="200", stderr="")

    monkeypatch.setattr(setup_brightdata.subprocess, "run", run)
    token = "secret-token-123456789012345"

    assert (
        setup_brightdata.verify_token_with_curl(
            token, "https://api.brightdata.com/customer/balance"
        )
        == "verified"
    )
    assert token not in " ".join(captured["args"])
    assert captured["input"] == f"Authorization: Bearer {token}\n"


def test_wait_for_backend_retries_connection_reset(monkeypatch, tmp_path):
    class Response:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

    responses = iter(
        [ConnectionResetError(54, "Connection reset by peer"), Response()]
    )

    def urlopen(*_args, **_kwargs):
        response = next(responses)
        if isinstance(response, Exception):
            raise response
        return response

    env_path = tmp_path / ".env"
    env_path.write_text("BACKEND_PORT=8001\n", encoding="utf-8")
    monkeypatch.setattr(setup_brightdata.urllib.request, "urlopen", urlopen)
    monkeypatch.setattr(setup_brightdata.time, "sleep", lambda _seconds: None)

    setup_brightdata.wait_for_backend(env_path)


def test_validate_token_format_rejects_shell_metacharacters():
    with pytest.raises(ValueError, match="20-256"):
        setup_brightdata.validate_token_format("$(unsafe-token-value)")
