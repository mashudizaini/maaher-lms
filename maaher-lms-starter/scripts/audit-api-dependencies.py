"""Check pinned runtime packages against PyPI's version-specific advisories.

This is an advisory snapshot, not proof of absence of vulnerabilities. Fail
on an unavailable source as well as on active advisories. Never modify pins.
"""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import httpx


def check(line):
    name, version = line.split("==", 1)
    try:
        response = httpx.get(f"https://pypi.org/pypi/{name}/{version}/json", timeout=20)
        response.raise_for_status()
        vulnerabilities = [v for v in response.json()["vulnerabilities"] if not v.get("withdrawn")]
        return name, version, vulnerabilities, None
    except (httpx.HTTPError, KeyError, ValueError) as error:
        return name, version, [], type(error).__name__


def main():
    lock = Path(__file__).resolve().parents[1]/"apps/api/requirements.lock"
    lines = [line for line in lock.read_text().splitlines() if line and not line.startswith("#")]
    failed = 0
    with ThreadPoolExecutor(max_workers=6) as pool:
        for name, version, vulnerabilities, error in pool.map(check, lines):
            if error:
                print(f"UNKNOWN {name}=={version}: {error}")
                failed += 1
            for advisory in vulnerabilities:
                print(f"ADVISORY {name}=={version}: {advisory['id']} {advisory.get('link','')}; fixed={advisory.get('fixed_in',[])}")
                failed += 1
    print(f"PyPI runtime advisory snapshot: {len(lines)} pins checked, {failed} findings/errors")
    return int(bool(failed))


if __name__ == "__main__":
    raise SystemExit(main())
