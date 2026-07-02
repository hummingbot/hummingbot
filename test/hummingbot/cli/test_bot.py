import json
import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from hummingbot.cli import bot
from hummingbot.cli.strategy_configs import controller_loader_name


class ControllerLoaderNameTest(unittest.TestCase):
    def test_flattens_dots_to_avoid_db_truncation(self):
        # Hummingbot derives the DB name via name.split('.')[0]; a dotted controller name would
        # collide on the first segment. The loader name must flatten dots.
        self.assertEqual(controller_loader_name("conf_generic.lp_jit.hype_usdc.yml"),
                         "conf_generic_lp_jit_hype_usdc.yml")
        # split('.')[0] on the loader stem returns the WHOLE name (no truncation/collision)
        stem = Path(controller_loader_name("conf_generic.lp_jit.hype_usdc.yml")).stem
        self.assertEqual(stem.split(".")[0], stem)

    def test_plain_name_unchanged(self):
        self.assertEqual(controller_loader_name("conf_pmm_simple.yml"), "conf_pmm_simple.yml")


class BotStateTest(unittest.TestCase):
    def test_tail_lines_seeks_from_end(self):
        with TemporaryDirectory() as d:
            p = Path(d) / "log.txt"
            p.write_text("\n".join(f"line{i}" for i in range(100)) + "\n")
            self.assertEqual(bot.tail_lines(p, 3), ["line97", "line98", "line99"])
            self.assertEqual(bot.tail_lines(p, 0), [])
            self.assertEqual(bot.tail_lines(Path(d) / "missing", 5), [])

    def test_meta_pid_status_roundtrip(self):
        with TemporaryDirectory() as d:
            with patch.object(bot, "bot_dir", return_value=Path(d)):
                self.assertFalse(bot.exists())
                bot.write_meta({"name": "n", "type": "controller", "file": "c.yml"})
                self.assertTrue(bot.exists())
                bot.update_meta(db_path="/x/n.sqlite")
                self.assertEqual(bot.read_meta()["db_path"], "/x/n.sqlite")
                self.assertEqual(bot.config_file_path(), None)
                bot.write_pid(999999)  # almost certainly not a live pid
                self.assertEqual(bot.read_pid(), 999999)
                bot.clear_pid()
                self.assertIsNone(bot.read_pid())
                bot.write_status({"running": True, "updated_at": 1.0})
                self.assertTrue(bot.read_status()["running"])


class BotPathsTest(unittest.TestCase):
    def test_bot_dir_under_data_path(self):
        with TemporaryDirectory() as d, patch.object(bot, "data_path", return_value=d):
            self.assertEqual(bot.bot_dir(), Path(d) / "bot")

    def test_structured_log_file_uses_meta_name(self):
        with TemporaryDirectory() as d, \
                patch.object(bot, "bot_dir", return_value=Path(d) / "bot"), \
                patch.object(bot, "prefix_path", return_value=d):
            # no meta -> default name
            self.assertEqual(bot.structured_log_file(), Path(d) / "logs" / "logs_hummingbot.log")
            bot.write_meta({"name": "mybot"})
            self.assertEqual(bot.structured_log_file(), Path(d) / "logs" / "logs_mybot.log")


class AtomicWriteTest(unittest.TestCase):
    def test_failed_replace_cleans_up_tmp_and_reraises(self):
        with TemporaryDirectory() as d:
            target = Path(d) / "meta.json"
            with patch.object(bot.os, "replace", side_effect=OSError("disk full")):
                with self.assertRaises(OSError):
                    bot._atomic_write(target, "{}")
            self.assertFalse(target.exists())
            self.assertEqual(list(Path(d).glob("*.tmp")), [])  # no temp file left behind

    def test_failure_with_tmp_already_gone_still_reraises(self):
        def replace_after_tmp_vanishes(tmp, dst):
            os.remove(tmp)  # simulate the tmp disappearing before cleanup runs
            raise OSError("boom")

        with TemporaryDirectory() as d:
            with patch.object(bot.os, "replace", side_effect=replace_after_tmp_vanishes):
                with self.assertRaises(OSError):
                    bot._atomic_write(Path(d) / "meta.json", "{}")


class PidAliveTest(unittest.TestCase):
    def test_own_pid_is_alive(self):
        self.assertTrue(bot.pid_alive(os.getpid()))

    def test_process_lookup_error_means_dead(self):
        with patch.object(bot.os, "kill", side_effect=ProcessLookupError):
            self.assertFalse(bot.pid_alive(12345))

    def test_permission_error_means_alive(self):
        # a pid we can't signal still exists (e.g. owned by another user)
        with patch.object(bot.os, "kill", side_effect=PermissionError):
            self.assertTrue(bot.pid_alive(1))


class CorruptStateTest(unittest.TestCase):
    """Missing/corrupt state files must read as None, never crash a status command."""

    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.botdir = Path(self._tmp.name)
        patcher = patch.object(bot, "bot_dir", return_value=self.botdir)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_missing_files_read_none(self):
        self.assertIsNone(bot.read_meta())
        self.assertIsNone(bot.read_status())
        self.assertIsNone(bot.read_loaded())
        self.assertIsNone(bot.read_pid())

    def test_corrupt_json_reads_none(self):
        (self.botdir / "meta.json").write_text("{not json")
        (self.botdir / "status.json").write_text("{not json")
        (self.botdir / "loaded.json").write_text("{not json")
        (self.botdir / "bot.pid").write_text("not-a-pid")
        self.assertIsNone(bot.read_meta())
        self.assertIsNone(bot.read_status())
        self.assertIsNone(bot.read_loaded())
        self.assertIsNone(bot.read_pid())

    def test_running_false_without_pid_true_with_live_pid(self):
        self.assertFalse(bot.running())
        bot.write_pid(os.getpid())
        self.assertTrue(bot.running())

    def test_clear_pid_noop_when_absent(self):
        bot.clear_pid()  # no pid file -> nothing to unlink, no error
        self.assertIsNone(bot.read_pid())

    def test_db_and_config_paths_from_meta(self):
        bot.write_meta({"db_path": "/x/n.sqlite", "config_file_path": "conf_x.yml"})
        self.assertEqual(bot.db_path(), "/x/n.sqlite")
        self.assertEqual(bot.config_file_path(), "conf_x.yml")

    def test_loaded_roundtrip_and_clear(self):
        bot.write_loaded("conf_x.yml", "controller")
        self.assertEqual(bot.read_loaded(), {"file": "conf_x.yml", "type": "controller"})
        bot.clear_loaded()
        self.assertIsNone(bot.read_loaded())
        bot.clear_loaded()  # idempotent when already gone


class DbAndLogDiscoveryTest(unittest.TestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.data = self.root / "data"
        self.logs = self.root / "logs"
        self.data.mkdir()
        self.logs.mkdir()
        for target, value in (("data_path", str(self.data)), ("prefix_path", str(self.root))):
            patcher = patch.object(bot, target, return_value=value)
            patcher.start()
            self.addCleanup(patcher.stop)
        botdir = patch.object(bot, "bot_dir", return_value=self.root / "bot")
        botdir.start()
        self.addCleanup(botdir.stop)

    def test_db_path_for_tries_dot_flattened_variant(self):
        (self.data / "a_b.sqlite").write_text("")
        self.assertEqual(bot.db_path_for("a_b"), str(self.data / "a_b.sqlite"))
        self.assertEqual(bot.db_path_for("a.b"), str(self.data / "a_b.sqlite"))  # flattened
        self.assertIsNone(bot.db_path_for("ghost"))

    def test_resolve_db_path_prefers_recorded_then_name(self):
        recorded = self.data / "recorded.sqlite"
        recorded.write_text("")
        bot.write_meta({"name": "mybot", "db_path": str(recorded)})
        self.assertEqual(bot.resolve_db_path(), str(recorded))
        # stale recorded path -> fall back to data/<name>.sqlite
        recorded.unlink()
        (self.data / "mybot.sqlite").write_text("")
        self.assertEqual(bot.resolve_db_path(), str(self.data / "mybot.sqlite"))

    def test_resolve_db_path_none_without_name(self):
        bot.write_meta({"type": "controller"})  # no name recorded
        self.assertIsNone(bot.resolve_db_path())

    def test_structured_log_for_tries_dot_flattened_variant(self):
        (self.logs / "logs_a_b.log").write_text("")
        self.assertEqual(bot.structured_log_for("a_b"), self.logs / "logs_a_b.log")
        self.assertEqual(bot.structured_log_for("a.b"), self.logs / "logs_a_b.log")
        self.assertIsNone(bot.structured_log_for("ghost"))

    def test_list_bots_unions_dbs_and_logs(self):
        (self.data / "alpha.sqlite").write_text("")
        (self.logs / "logs_beta.log").write_text("")
        (self.logs / "logs_alpha.log").write_text("")  # same bot counted once
        self.assertEqual(bot.list_bots(), ["alpha", "beta"])

    def test_list_bots_empty_when_dirs_missing(self):
        with patch.object(bot, "data_path", return_value=str(self.root / "no_data")), \
                patch.object(bot, "prefix_path", return_value=str(self.root / "no_prefix")):
            self.assertEqual(bot.list_bots(), [])


class MetaWriteTest(unittest.TestCase):
    def test_write_meta_serializes_non_json_types_via_str(self):
        with TemporaryDirectory() as d, patch.object(bot, "bot_dir", return_value=Path(d)):
            bot.write_meta({"path": Path("/x")})
            self.assertEqual(json.loads((Path(d) / "meta.json").read_text()), {"path": "/x"})


if __name__ == "__main__":
    unittest.main()
