#!/usr/bin/env python3
"""Copy only the public server contract at an immutable revision.

Run through uv with tests/requirements.txt. Authentication/fetching the private
server repository is the caller's responsibility; this script never reads keys.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile

from openapi_spec_validator import validate

ROOT = Path(__file__).resolve().parents[1]
SPEC = Path("reference/api/openapi.json")
PROVENANCE = Path("reference/api/openapi-source.json")
SOURCE_REPOSITORY = "lambdadb/lambdadb"
SOURCE_PATH = "api/openapi.json"


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def validate_public(data):
    spec = json.loads(data)
    validate(spec)
    if spec.get("x-internal") or not spec.get("paths"):
        raise ValueError("Only a nonempty public contract can be published")
    if any(not (p == "/collections" or p.startswith("/collections/")) for p in spec["paths"]):
        raise ValueError("Unexpected public API path; review the publication allowlist explicitly")
    if "AdminApiKey" in spec.get("components", {}).get("securitySchemes", {}):
        raise ValueError("Administrator authentication must not be published")


def read_source(repo, commit):
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise ValueError("Source commit must be a full lowercase 40-character SHA, not a branch")
    kind = subprocess.check_output(["git", "-C", str(repo), "cat-file", "-t", commit], text=True).strip()
    if kind != "commit":
        raise ValueError("Source revision must identify a commit")
    return subprocess.check_output(["git", "-C", str(repo), "show", f"{commit}:{SOURCE_PATH}"])


def atomic_write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def sync(root, repo, commit, evidence):
    if not evidence or not evidence.strip():
        raise ValueError("Publication evidence is required; a merge does not establish deployment")
    data = read_source(repo, commit)
    validate_public(data)
    record = {"repository": SOURCE_REPOSITORY, "path": SOURCE_PATH, "commit": commit,
              "sha256": sha256(data), "publicationEvidence": evidence.strip()}
    atomic_write(root / SPEC, data)
    atomic_write(root / PROVENANCE, (json.dumps(record, indent=2) + "\n").encode())
    return record


def check(root, repo=None):
    data = (root / SPEC).read_bytes()
    record = json.loads((root / PROVENANCE).read_text())
    if record.get("repository") != SOURCE_REPOSITORY or record.get("path") != SOURCE_PATH:
        raise ValueError("Unexpected source repository/path; only api/openapi.json is allowed")
    if not re.fullmatch(r"[0-9a-f]{40}", record.get("commit", "")):
        raise ValueError("Missing immutable source commit")
    if not isinstance(record.get("publicationEvidence"), str) or not record["publicationEvidence"].strip():
        raise ValueError("Missing publication evidence")
    if record.get("sha256") != sha256(data):
        raise ValueError("Spec differs from its recorded digest; resync from the server")
    validate_public(data)
    if repo is not None and data != read_source(repo, record["commit"]):
        raise ValueError("Spec differs from the pinned server commit")
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--server-repo", type=Path, help="Authenticated local lambdadb checkout")
    parser.add_argument("--commit", help="Exact server commit SHA (sync only)")
    parser.add_argument("--publication-evidence", help="Evidence that the selected public contract is approved for publication")
    parser.add_argument("--check", action="store_true", help="Verify locally; add --server-repo for source-byte verification")
    args = parser.parse_args()
    if args.check:
        if args.commit or args.publication_evidence:
            parser.error("--check uses the recorded commit/evidence")
        record = check(ROOT, args.server_repo)
    else:
        if not args.server_repo or not args.commit or not args.publication_evidence:
            parser.error("Sync requires --server-repo, --commit, and --publication-evidence")
        record = sync(ROOT, args.server_repo, args.commit, args.publication_evidence)
        check(ROOT, args.server_repo)
    mode = "verified against server" if args.server_repo else "verified local digest and public scope"
    print(f"{mode}: {record['repository']}@{record['commit']}:{record['path']}")


if __name__ == "__main__":
    main()
