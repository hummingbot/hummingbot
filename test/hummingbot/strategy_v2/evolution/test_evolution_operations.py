import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from hummingbot.strategy_v2.evolution.config import EvolutionConfig
from hummingbot.strategy_v2.evolution.models import EvolutionPolicy, StrategySpec
from hummingbot.strategy_v2.evolution.operations import source_fingerprint
from hummingbot.strategy_v2.evolution.supervisor import EvolutionSupervisor
from scripts.strategy_evolution_loop import _backoff_seconds


ROOT = Path(__file__).resolve().parents[4]


class EvolutionOperationsTest(TestCase):
    def test_backoff_is_exponential_and_capped(self):
        observed = [
            _backoff_seconds(index, initial=5, maximum=300) for index in range(1, 9)
        ]

        self.assertEqual([5, 10, 20, 40, 80, 160, 300, 300], observed)

    def test_health_accepts_live_running_cycle(self):
        with TemporaryDirectory() as directory:
            heartbeat = Path(directory) / "heartbeat.json"
            heartbeat.write_text(
                json.dumps(
                    {
                        "status": "running",
                        "pid": os.getpid(),
                        "cycle_started_at": datetime.now(timezone.utc).isoformat(),
                    }
                ),
                encoding="utf-8",
            )

            result = self._health(heartbeat)

            self.assertEqual(0, result.returncode, result.stdout + result.stderr)
            self.assertIn("status=running", result.stdout)

    def test_health_rejects_degraded_and_future_heartbeat(self):
        with TemporaryDirectory() as directory:
            heartbeat = Path(directory) / "heartbeat.json"
            heartbeat.write_text(
                json.dumps(
                    {
                        "status": "degraded",
                        "pid": os.getpid(),
                        "last_activity": datetime.now(timezone.utc).isoformat(),
                    }
                ),
                encoding="utf-8",
            )
            degraded_liveness = self._health(heartbeat)
            degraded_readiness = self._health(heartbeat, mode="readiness")
            heartbeat.write_text(
                json.dumps(
                    {
                        "status": "healthy",
                        "pid": os.getpid(),
                        "last_activity": (
                            datetime.now(timezone.utc) + timedelta(minutes=10)
                        ).isoformat(),
                    }
                ),
                encoding="utf-8",
            )
            future = self._health(heartbeat)

            self.assertEqual(0, degraded_liveness.returncode)
            self.assertEqual(1, degraded_readiness.returncode)
            self.assertEqual(2, future.returncode)

    def test_strategy_internal_error_marks_supervisor_degraded(self):
        with TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            state = root / "data/strategy-evolution/strategies/alpha/state.json"
            state.parent.mkdir(parents=True)
            state.write_text("{broken", encoding="utf-8")
            spec = StrategySpec(
                strategy_id="alpha",
                name="Alpha",
                family="test",
                thesis="test",
                target="test.alpha",
                evidence_file="reports/evidence.json",
                walk_forward_file="reports/walk.json",
            )

            payload = EvolutionSupervisor(
                EvolutionConfig(root, EvolutionPolicy(), (spec,))
            ).run_once()
            heartbeat = json.loads(
                (root / "data/strategy-evolution/heartbeat.json").read_text(
                    encoding="utf-8"
                )
            )

            self.assertEqual("error", payload["strategies"][0]["status"])
            self.assertEqual("degraded", heartbeat["status"])
            self.assertIsNotNone(heartbeat["last_error"])

    def test_source_fingerprint_changes_only_for_release_sources(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "hummingbot/strategy_v2/evolution/example.py"
            source.parent.mkdir(parents=True)
            source.write_text("VALUE = 1\n", encoding="utf-8")
            first = source_fingerprint(root)
            generated = root / "conf/controllers/conf_evo_generated.yml"
            generated.parent.mkdir(parents=True)
            generated.write_text("ignored: true\n", encoding="utf-8")
            self.assertEqual(first, source_fingerprint(root))
            source.write_text("VALUE = 2\n", encoding="utf-8")
            self.assertNotEqual(first, source_fingerprint(root))

    @staticmethod
    def _health(heartbeat: Path, mode: str = "liveness") -> subprocess.CompletedProcess:
        return subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts/check_strategy_evolution_health.py"),
                "--heartbeat",
                str(heartbeat),
                "--mode",
                mode,
                "--expected-source-sha256",
                "",
            ],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
