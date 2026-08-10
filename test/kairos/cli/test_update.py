import io
import json
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

import typer

from kairos.cli.commands import update as update_mod
from kairos.cli.output import ExitCode


class UpdateCommandTest(unittest.TestCase):
    """The update command's flow with git/bot/environment faked at its seams."""

    def setUp(self) -> None:
        self.running = patch("kairos.cli.bot.running", return_value=False).start()
        self.addCleanup(patch.stopall)

    def _run(self, check=False, as_json=False) -> str:
        buf = io.StringIO()
        with redirect_stdout(buf):
            update_mod.update(check, as_json)
        return buf.getvalue()

    def _fail(self, check=False) -> int:
        with redirect_stdout(io.StringIO()):
            with self.assertRaises(typer.Exit) as ctx:
                update_mod.update(check, False)
        return ctx.exception.exit_code

    def _git_script(self, replies: dict):
        """Patch _git to answer from a {first-arg-tuple-prefix: reply} table and record calls."""
        calls = []

        def fake_git(*args):
            calls.append(args)
            for prefix, reply in replies.items():
                if args[:len(prefix)] == prefix:
                    return reply
            return ""
        patch.object(update_mod, "_git", side_effect=fake_git).start()
        return calls

    # -- refusals --

    def test_docker_install_refuses_with_host_instructions(self):
        with patch.dict("os.environ", {"INSTALLATION_TYPE": "docker"}):
            self.assertEqual(self._fail(), ExitCode.ERROR)

    def test_running_bot_refuses(self):
        self.running.return_value = True
        self.assertEqual(self._fail(), ExitCode.ERROR)

    def test_non_git_checkout_refuses(self):
        with patch.object(update_mod, "REPO_ROOT", update_mod.REPO_ROOT / "does-not-exist"):
            self.assertEqual(self._fail(), ExitCode.ERROR)

    def test_diverged_local_branch_refuses(self):
        self._git_script({
            ("rev-parse", "--abbrev-ref"): "feat/x",
            ("rev-parse", "--short", "HEAD"): "aaa1111",
            ("rev-parse", "--short", "@{u}"): "bbb2222",
            ("rev-list", "--count", "HEAD..@{u}"): "3",
            ("rev-list", "--count", "@{u}..HEAD"): "2",
        })
        self.assertEqual(self._fail(), ExitCode.ERROR)

    # -- check / up-to-date --

    def test_check_reports_without_touching_the_tree(self):
        calls = self._git_script({
            ("rev-parse", "--abbrev-ref"): "master",
            ("rev-parse", "--short", "HEAD"): "aaa1111",
            ("rev-parse", "--short", "@{u}"): "bbb2222",
            ("rev-list", "--count", "HEAD..@{u}"): "5",
            ("rev-list", "--count", "@{u}..HEAD"): "0",
        })
        payload = json.loads(self._run(check=True, as_json=True))
        self.assertEqual(payload["behind"], 5)
        self.assertFalse(payload["up_to_date"])
        self.assertNotIn(("merge", "--ff-only", "@{u}"), calls)

    def test_up_to_date_is_a_no_op(self):
        calls = self._git_script({
            ("rev-parse", "--abbrev-ref"): "master",
            ("rev-parse", "--short", "HEAD"): "aaa1111",
            ("rev-parse", "--short", "@{u}"): "aaa1111",
            ("rev-list", "--count", "HEAD..@{u}"): "0",
            ("rev-list", "--count", "@{u}..HEAD"): "0",
        })
        out = self._run()
        self.assertIn("up_to_date: yes", out)
        self.assertNotIn(("merge", "--ff-only", "@{u}"), calls)

    # -- the update itself --

    def test_fast_forward_without_compiled_changes_skips_rebuild(self):
        calls = self._git_script({
            ("rev-parse", "--abbrev-ref"): "master",
            ("rev-parse", "--short", "HEAD"): "aaa1111",
            ("rev-parse", "--short", "@{u}"): "bbb2222",
            ("rev-list", "--count", "HEAD..@{u}"): "2",
            ("rev-list", "--count", "@{u}..HEAD"): "0",
            ("diff",): "",
        })
        rebuild = patch.object(update_mod, "_rebuild_extensions").start()
        out = self._run()
        self.assertIn(("merge", "--ff-only", "@{u}"), calls)
        rebuild.assert_not_called()
        self.assertIn("extensions_rebuilt: no", out)

    def test_fast_forward_with_pyx_changes_rebuilds(self):
        self._git_script({
            ("rev-parse", "--abbrev-ref"): "master",
            ("rev-parse", "--short", "HEAD"): "aaa1111",
            ("rev-parse", "--short", "@{u}"): "bbb2222",
            ("rev-list", "--count", "HEAD..@{u}"): "1",
            ("rev-list", "--count", "@{u}..HEAD"): "0",
            ("diff", "--name-only", "aaa1111..HEAD", "--", "*.pyx"): "kairos/core/x.pyx",
        })
        rebuild = patch.object(update_mod, "_rebuild_extensions").start()
        out = self._run()
        rebuild.assert_called_once()
        self.assertIn("extensions_rebuilt: yes", out)

    def test_environment_change_adds_conda_note(self):
        def fake_git(*args):
            table = {
                ("rev-parse", "--abbrev-ref"): "master",
                ("rev-parse", "--short", "HEAD"): "aaa1111",
                ("rev-parse", "--short", "@{u}"): "bbb2222",
                ("rev-list", "--count", "HEAD..@{u}"): "1",
                ("rev-list", "--count", "@{u}..HEAD"): "0",
            }
            for prefix, reply in table.items():
                if args[:len(prefix)] == prefix:
                    return reply
            if args[0] == "diff" and "setup/environment.yml" in args:
                return "setup/environment.yml"
            return ""
        patch.object(update_mod, "_git", side_effect=fake_git).start()
        patch.object(update_mod, "_rebuild_extensions").start()
        out = self._run()
        self.assertIn("make install", out)


if __name__ == "__main__":
    unittest.main()
