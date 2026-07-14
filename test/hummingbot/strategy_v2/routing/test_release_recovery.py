import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from hummingbot.strategy_v2.routing.release import load_release_manifest


class RoutingReleaseRecoveryTest(TestCase):
    def test_recovered_release_requires_bound_audit_evidence(self):
        payload = {
            "version": 1,
            "deployment_id": "paper-candidate-a",
            "strategy_id": "pmm_mister",
            "candidate_id": "candidate-a",
            "controller_config": "conf/controllers/candidate.yml",
            "script_config": "conf/scripts/candidate.yml",
            "runtime_file": "data/candidate_runtime.json",
            "database_file": "data/candidate.sqlite",
            "config_hash": "12345678",
            "status": "active_verified",
            "paper_only": True,
            "staged_at": "2026-07-13T00:00:00+00:00",
            "start_command": ["scripts/run_candidate_paper.sh"],
            "rollback_recovered_at": "2026-07-13T01:00:00+00:00",
            "rollback_recovery": {
                "reasons": ["runtime_stale"],
                "evidence_collected_at": "2026-07-13T00:59:59+00:00",
                "runtime_candidate_id": "candidate-a",
            },
        }
        with TemporaryDirectory() as directory:
            path = Path(directory) / "release.json"
            path.write_text(json.dumps(payload), encoding="utf-8")

            manifest = load_release_manifest(path)

            self.assertEqual("candidate-a", manifest.releases[0].candidate_id)

    def test_recovery_candidate_mismatch_is_rejected(self):
        payload = {
            "version": 1,
            "deployment_id": "paper-candidate-a",
            "strategy_id": "pmm_mister",
            "candidate_id": "candidate-a",
            "controller_config": "conf/controllers/candidate.yml",
            "script_config": "conf/scripts/candidate.yml",
            "config_hash": "12345678",
            "status": "active_verified",
            "paper_only": True,
            "staged_at": "2026-07-13T00:00:00+00:00",
            "start_command": ["scripts/run_candidate_paper.sh"],
            "rollback_recovered_at": "2026-07-13T01:00:00+00:00",
            "rollback_recovery": {
                "reasons": ["runtime_stale"],
                "evidence_collected_at": "2026-07-13T00:59:59+00:00",
                "runtime_candidate_id": "candidate-b",
            },
        }
        with TemporaryDirectory() as directory:
            path = Path(directory) / "release.json"
            path.write_text(json.dumps(payload), encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "candidate does not match"):
                load_release_manifest(path)
