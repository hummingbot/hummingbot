import io
import json
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import typer

from kairos.cli.commands import doctor as doctor_mod
from kairos.cli.output import ExitCode


class DoctorRowTest(unittest.TestCase):
    """Individual checks with their seams patched."""

    def setUp(self) -> None:
        self.addCleanup(patch.stopall)

    # -- clock --

    def test_clock_ok_warn_fail_thresholds(self):
        import time
        now = time.time()
        for skew, status in [(0.5, "ok"), (5.0, "warn"), (60.0, "fail")]:
            patch.object(doctor_mod, "_remote_unix_time", return_value=now - skew).start()
            self.assertEqual(doctor_mod._clock_row()["status"], status, f"skew={skew}")

    def test_clock_offline_is_a_warn_not_a_crash(self):
        patch.object(doctor_mod, "_remote_unix_time", return_value=None).start()
        row = doctor_mod._clock_row()
        self.assertEqual(row["status"], "warn")
        self.assertIn("offline", row["detail"])

    # -- disk --

    def _disk(self, free):
        from collections import namedtuple
        Usage = namedtuple("usage", "total used free")
        patch.object(doctor_mod.shutil, "disk_usage",
                     return_value=Usage(100 << 30, 0, free)).start()
        return doctor_mod._disk_row()

    def test_disk_thresholds(self):
        self.assertEqual(self._disk(50 << 30)["status"], "ok")
        self.assertEqual(self._disk(500 << 20)["status"], "warn")
        self.assertEqual(self._disk(50 << 20)["status"], "fail")

    # -- bot state --

    def test_stale_pid_warns(self):
        patch("kairos.cli.bot.exists", return_value=True).start()
        patch("kairos.cli.bot.read_pid", return_value=99999999).start()
        patch("kairos.cli.bot.is_engine_pid", return_value=False).start()
        row = doctor_mod._bot_row()
        self.assertEqual(row["status"], "warn")
        self.assertIn("stale bot.pid", row["detail"])

    def test_running_bot_is_ok(self):
        patch("kairos.cli.bot.exists", return_value=True).start()
        patch("kairos.cli.bot.read_pid", return_value=42).start()
        patch("kairos.cli.bot.is_engine_pid", return_value=True).start()
        self.assertEqual(doctor_mod._bot_row()["status"], "ok")

    # -- loaded pointer --

    def test_dangling_loaded_pointer_warns(self):
        d = TemporaryDirectory()
        self.addCleanup(d.cleanup)
        patch("kairos.cli.bot.read_loaded",
              return_value={"file": "conf_x.yml", "type": "v2-script"}).start()
        patch.dict("kairos.cli.strategy_configs.TYPE_DIRS",
                   {"v2-script": Path(d.name)}).start()
        row = doctor_mod._loaded_row()
        self.assertEqual(row["status"], "warn")
        self.assertIn("missing on disk", row["detail"])
        (Path(d.name) / "conf_x.yml").write_text("a: 1\n")
        self.assertEqual(doctor_mod._loaded_row()["status"], "ok")

    # -- keystore --

    def test_keystore_without_password_skips(self):
        import os
        patch("kairos.client.config.security.Security.new_password_required",
              return_value=False).start()
        env = {k: v for k, v in os.environ.items() if k not in ("HBOT_PASSWORD", "CONFIG_PASSWORD")}
        with patch.dict(os.environ, env, clear=True):
            row = doctor_mod._keystore_row()
        self.assertEqual(row["status"], "skip")

    def test_keystore_bad_password_fails(self):
        patch("kairos.client.config.security.Security.new_password_required",
              return_value=False).start()
        patch("kairos.client.config.security.Security.login", return_value=False).start()
        with patch.dict("os.environ", {"HBOT_PASSWORD": "wrong"}):
            row = doctor_mod._keystore_row()
        self.assertEqual(row["status"], "fail")


class DoctorRunTest(unittest.TestCase):
    """The command's aggregation: exit code = health."""

    def setUp(self) -> None:
        self.addCleanup(patch.stopall)

    def _patch_checks(self, statuses):
        rows = [doctor_mod._row(f"c{i}", s, "detail") for i, s in enumerate(statuses)]
        patch.object(doctor_mod, "CHECKS", [lambda r=r: r for r in rows]).start()

    def test_healthy_run_exits_zero_and_lists_all_checks(self):
        self._patch_checks(["ok", "warn", "skip", "ok"])
        buf = io.StringIO()
        with redirect_stdout(buf):
            doctor_mod.doctor(as_json=False)  # not raising == exit 0
        out = buf.getvalue()
        for name in ("c0", "c1", "c2", "c3"):
            self.assertIn(name, out)

    def test_any_fail_exits_error(self):
        self._patch_checks(["ok", "fail", "ok"])
        with redirect_stdout(io.StringIO()):
            with self.assertRaises(typer.Exit) as ctx:
                doctor_mod.doctor(as_json=False)
        self.assertEqual(ctx.exception.exit_code, ExitCode.ERROR)

    def test_json_payload_shape(self):
        self._patch_checks(["ok", "warn"])
        buf = io.StringIO()
        with redirect_stdout(buf):
            doctor_mod.doctor(as_json=True)
        payload = json.loads(buf.getvalue())
        self.assertTrue(payload["healthy"])
        self.assertEqual([c["status"] for c in payload["checks"]], ["ok", "warn"])

    def test_a_crashing_check_becomes_a_fail_row_not_a_crash(self):
        def boom():
            raise RuntimeError("kaput")
        boom.__name__ = "_clock_row"
        patch.object(doctor_mod, "CHECKS", [boom]).start()
        buf = io.StringIO()
        with redirect_stdout(buf):
            with self.assertRaises(typer.Exit):
                doctor_mod.doctor(as_json=False)
        self.assertIn("kaput", buf.getvalue())


if __name__ == "__main__":
    unittest.main()
