#!/usr/bin/env python3
"""Configure a Bright Data API key without exposing it in shell history."""

from __future__ import annotations

import argparse
import getpass
import os
from pathlib import Path
import re
import ssl
import stat
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import webbrowser


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ENV_FILE = PROJECT_ROOT / ".env"
SETTINGS_URL = "https://brightdata.com/cp/setting/users"
DEFAULT_BASE_URL = "https://api.brightdata.com"
DEFAULT_DATASET_ID = "gd_l1vikfch901nx3by4"
TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9_-]{20,256}$")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Open Bright Data API-key settings, securely store the key in .env, "
            "and restart the backend."
        )
    )
    parser.add_argument(
        "--env-file",
        type=Path,
        default=DEFAULT_ENV_FILE,
        help="dotenv file to update (default: project .env)",
    )
    parser.add_argument(
        "--token-stdin",
        action="store_true",
        help="read one API key line from stdin instead of prompting",
    )
    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="do not open the Bright Data settings page",
    )
    parser.add_argument(
        "--skip-token-check",
        action="store_true",
        help="store the key without calling Bright Data's no-charge balance endpoint",
    )
    parser.add_argument(
        "--skip-restart",
        action="store_true",
        help="do not recreate and health-check the Docker backend",
    )
    return parser.parse_args()


def read_env_value(env_path: Path, key: str) -> str | None:
    if not env_path.exists():
        return None
    for line in env_path.read_text(encoding="utf-8").splitlines():
        if not line or line.lstrip().startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        if name.strip() == key:
            return value.strip().strip("'\"") or None
    return None


def validate_token_format(token: str) -> str:
    token = token.strip()
    if not TOKEN_PATTERN.fullmatch(token):
        raise ValueError(
            "API key must be 20-256 characters using only letters, numbers, '_' or '-'."
        )
    return token


def obtain_token(args: argparse.Namespace, env_path: Path) -> str:
    existing_token = os.getenv("BRIGHTDATA_API_TOKEN") or read_env_value(
        env_path, "BRIGHTDATA_API_TOKEN"
    )
    if existing_token:
        print("Existing BRIGHTDATA_API_TOKEN found; validating it without displaying it.")
        return validate_token_format(existing_token)

    if not args.no_browser:
        print(f"Opening Bright Data API-key settings: {SETTINGS_URL}")
        webbrowser.open(SETTINGS_URL, new=2)

    print(
        "Sign in, choose 'Add API key', use the minimum required User permission, "
        "set an expiration date, and copy the key shown once."
    )
    if args.token_stdin:
        token = sys.stdin.readline()
    elif sys.stdin.isatty():
        token = getpass.getpass("Paste the Bright Data API key (hidden): ")
    else:
        raise RuntimeError(
            "Interactive input is unavailable. Run in a terminal or pass --token-stdin."
        )
    return validate_token_format(token)


def verify_token(token: str, base_url: str = DEFAULT_BASE_URL) -> str:
    url = f"{base_url.rstrip('/')}/customer/balance"
    request = urllib.request.Request(
        url,
        headers={"Authorization": f"Bearer {token}"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            return classify_token_status(response.status)
    except urllib.error.HTTPError as exc:
        return classify_token_status(exc.code)
    except urllib.error.URLError as exc:
        if is_certificate_verification_error(exc.reason):
            print(
                "Python CA certificates are unavailable; retrying the token check "
                "with the system trust store."
            )
            return verify_token_with_curl(token, url)
        raise RuntimeError(f"Could not reach Bright Data: {exc.reason}") from exc


def classify_token_status(status: int) -> str:
    if status == 200:
        return "verified"
    if status == 403:
        return "verified_limited_permissions"
    if status == 401:
        raise RuntimeError("Bright Data rejected the API key (HTTP 401).")
    raise RuntimeError(f"Bright Data token check failed with HTTP {status}.")


def is_certificate_verification_error(reason: object) -> bool:
    return isinstance(reason, ssl.SSLCertVerificationError) or (
        "CERTIFICATE_VERIFY_FAILED" in str(reason)
    )


def verify_token_with_curl(token: str, url: str) -> str:
    try:
        result = subprocess.run(
            [
                "curl",
                "--silent",
                "--show-error",
                "--output",
                "/dev/null",
                "--write-out",
                "%{http_code}",
                "--header",
                "@-",
                "--max-time",
                "15",
                url,
            ],
            input=f"Authorization: Bearer {token}\n",
            text=True,
            capture_output=True,
            check=False,
        )
    except FileNotFoundError as exc:
        raise RuntimeError(
            "Python CA certificates are unavailable and system curl was not found."
        ) from exc

    if result.returncode != 0:
        raise RuntimeError(
            "System trust-store token check failed "
            f"(curl exit code {result.returncode})."
        )
    try:
        status = int(result.stdout.strip())
    except ValueError as exc:
        raise RuntimeError("System trust-store token check returned no HTTP status.") from exc
    return classify_token_status(status)


def update_dotenv(env_path: Path, values: dict[str, str]) -> None:
    if env_path.is_symlink():
        raise RuntimeError("Refusing to replace a symlinked env file.")
    env_path = env_path.resolve()
    env_path.parent.mkdir(parents=True, exist_ok=True)

    original = env_path.read_text(encoding="utf-8") if env_path.exists() else ""
    lines = original.splitlines()
    managed_keys = set(values)
    written_keys: set[str] = set()
    updated: list[str] = []

    for line in lines:
        if not line or line.lstrip().startswith("#") or "=" not in line:
            updated.append(line)
            continue
        name = line.split("=", 1)[0].strip()
        if name in managed_keys:
            if name not in written_keys:
                updated.append(f"{name}={values[name]}")
                written_keys.add(name)
            continue
        updated.append(line)

    missing = {key: value for key, value in values.items() if key not in written_keys}
    if missing and updated and updated[-1] != "":
        updated.append("")
    updated.extend(f"{key}={value}" for key, value in missing.items())
    content = "\n".join(updated).rstrip("\n") + "\n"

    previous_mode = stat.S_IMODE(env_path.stat().st_mode) if env_path.exists() else 0o600
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=env_path.parent,
        prefix=f".{env_path.name}.",
        delete=False,
    ) as temp_file:
        temp_file.write(content)
        temp_path = Path(temp_file.name)

    try:
        temp_path.chmod(previous_mode & 0o600)
        temp_path.replace(env_path)
    finally:
        if temp_path.exists():
            temp_path.unlink()
    env_path.chmod(0o600)


def restart_backend(env_path: Path) -> None:
    subprocess.run(
        [
            "docker",
            "compose",
            "--env-file",
            str(env_path),
            "up",
            "-d",
            "--force-recreate",
            "backend",
        ],
        cwd=PROJECT_ROOT,
        check=True,
    )


def wait_for_backend(env_path: Path) -> None:
    port = read_env_value(env_path, "BACKEND_PORT") or "8001"
    url = f"http://127.0.0.1:{port}/ready"
    deadline = time.monotonic() + 45
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=3) as response:
                if response.status == 200:
                    print(f"Backend is ready at {url}.")
                    return
        except (urllib.error.URLError, ConnectionError, TimeoutError):
            time.sleep(1)
    raise RuntimeError(f"Backend did not become ready within 45 seconds: {url}")


def main() -> int:
    args = parse_args()
    env_path = args.env_file.expanduser()
    try:
        token = obtain_token(args, env_path)
        base_url = read_env_value(env_path, "BRIGHTDATA_BASE_URL") or DEFAULT_BASE_URL
        if args.skip_token_check:
            print("Token check skipped by request.")
        else:
            result = verify_token(token, base_url)
            if result == "verified_limited_permissions":
                print("API key was accepted; the balance endpoint is restricted for this role.")
            else:
                print("API key authentication verified.")

        update_dotenv(
            env_path,
            {
                "INFLUENCER_PROVIDER": "brightdata",
                "BRIGHTDATA_API_TOKEN": token,
                "BRIGHTDATA_INSTAGRAM_PROFILE_DATASET_ID": DEFAULT_DATASET_ID,
                "BRIGHTDATA_BASE_URL": DEFAULT_BASE_URL,
            },
        )
        print(f"Bright Data settings saved to {env_path} with mode 0600.")

        if args.skip_restart:
            print("Backend restart skipped by request.")
        else:
            restart_backend(env_path)
            wait_for_backend(env_path)
        print("Bright Data setup completed without printing the API key.")
        return 0
    except (OSError, RuntimeError, ValueError, subprocess.CalledProcessError) as exc:
        print(f"Setup failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
