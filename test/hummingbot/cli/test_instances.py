import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from hummingbot.cli import instances
from hummingbot.cli.instances import Instance, list_instances, pid_alive


class InstancesTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = TemporaryDirectory()
        self._data_dir = self._tmp.name
        patcher = patch.object(instances, "data_path", return_value=self._data_dir)
        self.addCleanup(patcher.stop)
        patcher.start()

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_invalid_names_rejected(self):
        for bad in ("", "../escape", "a/b", "."):
            with self.assertRaises(ValueError):
                Instance(bad)

    def test_meta_roundtrip_and_update(self):
        inst = Instance("bot1")
        inst.dir.mkdir(parents=True)
        inst.write_meta({"name": "bot1", "config": "c.yml"})
        self.assertTrue(inst.exists())
        self.assertEqual(inst.read_meta()["config"], "c.yml")

        inst.update_meta(db_path="/tmp/x.sqlite", pid=4321)
        meta = inst.read_meta()
        self.assertEqual(meta["db_path"], "/tmp/x.sqlite")
        self.assertEqual(meta["pid"], 4321)
        self.assertEqual(meta["config"], "c.yml")  # preserved
        self.assertEqual(inst.db_path(), "/tmp/x.sqlite")

    def test_atomic_write_status(self):
        inst = Instance("bot2")
        inst.dir.mkdir(parents=True)
        inst.write_status({"running": True, "engine": {"strategy_running": True}})
        self.assertTrue(inst.read_status()["running"])
        # no stray temp files left behind
        leftovers = [p for p in inst.dir.iterdir() if p.name.startswith(".")]
        self.assertEqual(leftovers, [])

    def test_pid_lifecycle(self):
        inst = Instance("bot3")
        inst.dir.mkdir(parents=True)
        self.assertIsNone(inst.read_pid())
        inst.write_pid(os.getpid())
        self.assertEqual(inst.read_pid(), os.getpid())
        self.assertTrue(inst.is_running())  # our own pid is alive
        inst.clear_pid()
        self.assertIsNone(inst.read_pid())
        self.assertFalse(inst.is_running())

    def test_pid_alive_false_for_dead_pid(self):
        # PID 2**31-1 is astronomically unlikely to exist.
        self.assertFalse(pid_alive(2 ** 31 - 1))

    def test_read_status_handles_corrupt_json(self):
        inst = Instance("bot4")
        inst.dir.mkdir(parents=True)
        inst.status_file.write_text("{not json")
        self.assertIsNone(inst.read_status())

    def test_list_instances(self):
        self.assertEqual(list_instances(), [])
        for name in ("alpha", "beta"):
            inst = Instance(name)
            inst.dir.mkdir(parents=True)
            inst.write_meta({"name": name})
        # a directory without meta.json is ignored
        (Path(self._data_dir) / "instances" / "no_meta").mkdir(parents=True)
        names = sorted(i.name for i in list_instances())
        self.assertEqual(names, ["alpha", "beta"])


if __name__ == "__main__":
    unittest.main()
