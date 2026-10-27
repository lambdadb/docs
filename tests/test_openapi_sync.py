"""Exercise immutable sync, private/admin exclusion, and source/digest drift."""
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
module = importlib.util.spec_from_file_location("sync_openapi", ROOT / "scripts/sync_openapi.py")
sync = importlib.util.module_from_spec(module)
module.loader.exec_module(sync)


class SyncTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name) / "server"
        self.docs = Path(self.temp.name) / "docs"
        (self.repo / "api").mkdir(parents=True)
        self.public = {"openapi": "3.1.1", "info": {"title": "Test", "version": "1"},
                       "paths": {"/collections": {"get": {"responses": {"200": {"description": "OK"}}}}}}
        (self.repo / "api/openapi.json").write_text(json.dumps(self.public))
        (self.repo / "api/openapi-admin.json").write_text('{"private":true}')
        self.git("init", "-q")
        self.git("add", ".")
        self.git("-c", "user.name=Contract Test", "-c", "user.email=contract@example.invalid",
                 "-c", "commit.gpgsign=false", "-c", "core.hooksPath=/dev/null", "commit", "-qm", "fixture")
        self.commit = self.git("rev-parse", "HEAD").strip()

    def git(self, *args):
        return subprocess.check_output(["git", "-C", str(self.repo), *args], text=True)

    def test_pins_git_blob_not_worktree_and_excludes_admin(self):
        (self.repo / "api/openapi.json").write_text('{"modified":true}')
        sync.sync(self.docs, self.repo, self.commit, "Confirmed test deployment")
        record = sync.check(self.docs, self.repo)
        self.assertEqual(self.commit, record["commit"])
        self.assertEqual(self.public, json.loads((self.docs / sync.SPEC).read_bytes()))
        self.assertFalse((self.docs / "reference/api/openapi-admin.json").exists())

    def test_rejects_moving_ref_and_missing_evidence(self):
        for commit, evidence in (("HEAD", "deployment"), (self.commit, " ")):
            with self.assertRaises(ValueError):
                sync.sync(self.docs, self.repo, commit, evidence)
        self.assertFalse((self.docs / sync.SPEC).exists())

    def test_detects_local_and_source_drift(self):
        sync.sync(self.docs, self.repo, self.commit, "deployment")
        data = (self.docs / sync.SPEC).read_bytes() + b"\n"
        (self.docs / sync.SPEC).write_bytes(data)
        with self.assertRaisesRegex(ValueError, "digest"):
            sync.check(self.docs)
        record = json.loads((self.docs / sync.PROVENANCE).read_text())
        record["sha256"] = sync.sha256(data)
        (self.docs / sync.PROVENANCE).write_text(json.dumps(record))
        with self.assertRaisesRegex(ValueError, "pinned server"):
            sync.check(self.docs, self.repo)

    def test_rejects_admin_spec_and_wrong_provenance(self):
        for change in ({"x-internal": True}, {"paths": {"/projects": self.public["paths"]["/collections"]}}):
            with self.assertRaises(ValueError):
                sync.validate_public(json.dumps({**self.public, **change}).encode())
        sync.sync(self.docs, self.repo, self.commit, "deployment")
        record = json.loads((self.docs / sync.PROVENANCE).read_text())
        record["path"] = "api/openapi-admin.json"
        (self.docs / sync.PROVENANCE).write_text(json.dumps(record))
        with self.assertRaises(ValueError):
            sync.check(self.docs)
