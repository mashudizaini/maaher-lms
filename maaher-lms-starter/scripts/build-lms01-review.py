"""Generate a review patch against verified GitHub blobs, never apply it.

Reviews include pre-existing workspace changes as well as this continuation.
No Git metadata, caches, private artifacts or active environment files enter
the patch. The JSON manifest hashes source files and the resulting patch.
"""
import argparse
import difflib
import hashlib
import json
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PREFIX = "maaher-lms-starter/"
EXPECTED_BASE = "8941a79dcf611df66c4ee43e78b902b62ddbfce2"
CLAUDE_REPORT_SHA = "004a19183409b152d0947ab6f5b99af2000d9dd3324c9a2c77ea66a4106032ce"


def digest(data):
    return hashlib.sha256(data).hexdigest()


def blob(data):
    return hashlib.sha1(b"blob "+str(len(data)).encode()+b"\0"+data).hexdigest()


def sources():
    paths = {Path(n) for n in ("AGENTS.md", "CLAUDE.md", "README.md", ".gitignore", ".env.example", "docker-compose.yml")}
    paths.add(Path('reviews/LMS-01-author-response.md'))
    excluded = {".git", "node_modules", ".next", "__pycache__", ".pytest_cache", "test-results", "playwright-report"}
    extensions = {".css", ".py", ".sql", ".txt", ".lock", ".ini", ".md", ".ts", ".tsx", ".json", ".yml", ".yaml", ".sh"}
    for directory in ("apps", "docs", "infra", "scripts", ".agents", ".claude", ".github"):
        for parent, dirs, files in os.walk(ROOT/directory):
            dirs[:] = sorted(d for d in dirs if d not in excluded)
            for name in sorted(files):
                path = Path(parent)/name
                if path.is_symlink() or name.startswith(".env"):
                    continue
                if path.suffix in extensions or name in {"Dockerfile", ".dockerignore"} or name.startswith("Dockerfile."):
                    paths.add(path.relative_to(ROOT))
    return paths


def diff(old,current,path):
    lines=difflib.unified_diff((old or b'').decode().splitlines(keepends=True),
                              (current or b'').decode().splitlines(keepends=True),
                              fromfile=f'a/{PREFIX}{path}' if old is not None else '/dev/null',
                              tofile=f'b/{PREFIX}{path}' if current is not None else '/dev/null')
    return ''.join(line if line.endswith('\n') else line+'\n\\ No newline at end of file\n' for line in lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline-payload", type=Path, required=True)
    parser.add_argument("--baseline-tree", type=Path, required=True)
    parser.add_argument('--reviewed-snapshot',type=Path,required=True)
    args = parser.parse_args()
    tree = json.loads(args.baseline_tree.read_text())
    assert tree["sha"] == EXPECTED_BASE, "Unexpected baseline SHA"
    assert not tree.get("truncated", False), "Incomplete baseline tree"
    blobs = {entry["path"]: entry["sha"] for entry in tree["tree"] if entry["type"] == "blob"}
    baseline = {}
    for entry in json.loads(args.baseline_payload.read_text()):
        name = entry["path"]
        assert name.startswith(PREFIX)
        relative = Path(name.removeprefix(PREFIX))
        assert not relative.is_absolute() and ".." not in relative.parts
        data = entry["content"].encode()
        assert blob(data) == blobs[name], f"Baseline blob mismatch: {name}"
        baseline[relative] = data
    assert len(baseline) == len(blobs) == 25, "Incomplete baseline payload"
    changes, parts = [], []
    for path in sorted(sources() | baseline.keys()):
        current = (ROOT/path).read_bytes() if (ROOT/path).is_file() else None
        old = baseline.get(path)
        if current == old:
            continue
        name = path.as_posix()
        parts.append(diff(old,current,name))
        changes.append({"path": name, "baseline_git_blob": blob(old) if old is not None else None,
                        "current_sha256": digest(current) if current is not None else None})
    patch = "".join(parts).encode()
    output = ROOT/"reviews/LMS-01-author.patch"
    output.write_bytes(patch)
    reviewed_manifest_data=(args.reviewed_snapshot/'reviews/LMS-01-review-manifest.json').read_bytes()
    reviewed_manifest=json.loads(reviewed_manifest_data)
    reviewed_files={Path(item['path']):item['current_sha256'] for item in reviewed_manifest['changes']}
    # Preserve the exact manifest and patch inspected by the original reviewer.
    for data,target in ((reviewed_manifest_data,'LMS-01-reviewed-manifest.json'),
                        ((args.reviewed_snapshot/'reviews/LMS-01-author.patch').read_bytes(),'LMS-01-author-before-claude-fixes.patch')):
        destination=ROOT/'reviews'/target
        if destination.exists():
            assert destination.read_bytes()==data,'Refusing to overwrite different review history'
        else:
            destination.write_bytes(data)
    assert digest((ROOT/'reviews/LMS-01-author-before-claude-fixes.patch').read_bytes())==reviewed_manifest['patch_sha256']
    incremental=[];post_changes=[]
    for path in sorted(sources() | baseline.keys() | reviewed_files.keys()):
        current=(ROOT/path).read_bytes() if (ROOT/path).is_file() else None
        saved=args.reviewed_snapshot/path
        if saved.is_file():
            old=saved.read_bytes()
        elif path in reviewed_files:
            assert current is not None and digest(current)==reviewed_files[path],f'Missing reviewed content: {path}'
            old=current  # Uncopied root/skill file is provably unchanged.
        else:
            old=baseline.get(path)
        if path in reviewed_files and old is not None:
            assert digest(old)==reviewed_files[path],f'Reviewed snapshot changed: {path}'
        if old!=current:
            incremental.append(diff(old,current,path.as_posix()))
            post_changes.append({'path':path.as_posix(),'reviewed_sha256':digest(old) if old is not None else None,
                                 'current_sha256':digest(current) if current is not None else None})
    incremental_data=''.join(incremental).encode()
    (ROOT/'reviews/LMS-01-post-claude.patch').write_bytes(incremental_data)
    report_digest=digest((ROOT/'reviews/LMS-01-claude.md').read_bytes())
    assert report_digest==CLAUDE_REPORT_SHA,'Original independent report changed'
    manifest = {"baseline_commit": EXPECTED_BASE, "baseline_blobs_verified": len(baseline),
                "baseline_payload_sha256": digest(args.baseline_payload.read_bytes()),
                "baseline_tree_sha256": digest(args.baseline_tree.read_bytes()),
                "patch_sha256": digest(patch), "strip_at_github_repository_root": 1,
                "strip_at_starter_root": 2,
                'post_claude_patch_sha256':digest(incremental_data),
                'reviewed_manifest_sha256':digest(reviewed_manifest_data),
                'original_claude_report_sha256':report_digest,
                'post_claude_changes':post_changes,
                "note": "Full baseline diff and incremental post-review diff; includes author response, excludes recursive patch/manifest/history and reviewer report content, secrets and generated artifacts. Do not apply to active workspace.",
                "changes": changes}
    (ROOT/"reviews/LMS-01-review-manifest.json").write_text(json.dumps(manifest, indent=2)+"\n")
    print(f"Verified {len(baseline)} baseline blobs; patch contains {len(changes)} changed files")
    print(f'Post-Claude diff: {len(post_changes)} changed files; original report fingerprint unchanged')


if __name__ == "__main__":
    main()
