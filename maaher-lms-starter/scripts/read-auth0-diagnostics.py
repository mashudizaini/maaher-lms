"""Read local API logs and print only allowlisted OIDC codes, never raw logs."""
import argparse
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/api"))
from app.oidc_diagnostics import Denial

CODES = {code.value for code in Denial}
PATTERN = re.compile(r"(?:^|\s)MAAHER_AUTH0_DIAGNOSTIC code=(OIDC_[A-Z0-9_]+)\s*$")
MAX_BYTES = 1024 * 1024


def extract_codes(raw):
    result = []
    for line in raw.splitlines():
        match = PATTERN.search(line)
        if match and match[1] in CODES:
            result.append(match[1])
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--compose", action="store_true", help="Capture last 200 API log entries from this project's Compose")
    source.add_argument("--log-file", type=Path, help="Existing API log file; contents/path are never printed")
    args = parser.parse_args(argv)
    try:
        if args.compose:
            run = subprocess.run(["docker", "compose", "logs", "--no-color", "--since", "10m", "--tail", "200", "api"],
                                 cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=20, check=False)
            if run.returncode:
                print("FAIL: log Compose belum dapat dibaca; stderr/raw log tidak ditampilkan")
                return 1
            data = run.stdout[-MAX_BYTES:]
        else:
            with args.log_file.open("rb") as stream:
                stream.seek(0, 2)
                stream.seek(max(0, stream.tell() - MAX_BYTES))
                data = stream.read(MAX_BYTES)
    except (OSError, subprocess.TimeoutExpired):
        print("FAIL: log API belum dapat dibaca; path/exception/raw log tidak ditampilkan")
        return 1
    codes = extract_codes(data.decode("utf-8", errors="replace"))
    if not codes:
        print("SKIP: belum ada kode diagnosis; periksa source/flag API dan lakukan satu percobaan login baru")
        return 2
    print("Latest local diagnostic: " + codes[-1])
    print("Kode ini petunjuk tahap kegagalan, bukan verifikasi setting Auth0 atau izin binding.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
