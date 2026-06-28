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


if __name__ == "__main__":
    unittest.main()
