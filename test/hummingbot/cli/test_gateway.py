import unittest
from types import SimpleNamespace
from unittest.mock import patch

from hummingbot.cli.commands import gateway


class GatewayHelpersTest(unittest.TestCase):
    def test_container_status_parses_output(self):
        with patch.object(gateway, "_docker") as docker:
            docker.return_value = SimpleNamespace(stdout="Up 2 hours\n", stderr="", returncode=0)
            self.assertEqual(gateway._container_status(), "Up 2 hours")

    def test_container_status_none_when_absent(self):
        with patch.object(gateway, "_docker") as docker:
            docker.return_value = SimpleNamespace(stdout="\n", stderr="", returncode=0)
            self.assertIsNone(gateway._container_status())

    def test_is_running_false_on_error(self):
        with patch.object(gateway, "_arun", side_effect=RuntimeError("no connection")):
            self.assertFalse(gateway._is_running(object()))

    def test_is_running_true(self):
        with patch.object(gateway, "_arun", return_value=True):
            self.assertTrue(gateway._is_running(object()))

    def test_split_network_splits_on_first_hyphen(self):
        self.assertEqual(gateway._split_network("solana-mainnet-beta", False), ("solana", "mainnet-beta"))
        self.assertEqual(gateway._split_network("ethereum-mainnet", False), ("ethereum", "mainnet"))
        self.assertEqual(gateway._split_network("ethereum-base", False), ("ethereum", "base"))

    def test_split_network_rejects_bare_chain(self):
        with patch.object(gateway, "fail", side_effect=SystemExit) as failed:
            with self.assertRaises(SystemExit):
                gateway._split_network("solana", False)
            failed.assert_called_once()

    def test_pull_image_success(self):
        with patch.object(gateway, "_docker") as docker:
            docker.return_value = SimpleNamespace(returncode=0, stdout="", stderr="")
            self.assertTrue(gateway._pull_image("img:latest", False, required=True))

    def test_pull_image_tolerates_local_only_when_not_required(self):
        # pull fails, but the image exists locally and pull isn't required -> tolerated (returns False)
        def fake_docker(*args):
            if args[0] == "pull":
                return SimpleNamespace(returncode=1, stdout="", stderr="denied")
            return SimpleNamespace(returncode=0, stdout="", stderr="")  # image inspect ok
        with patch.object(gateway, "_docker", side_effect=fake_docker):
            self.assertFalse(gateway._pull_image("local/img:latest", False, required=False))

    def test_pull_image_fails_when_required(self):
        def fake_docker(*args):
            return SimpleNamespace(returncode=1, stdout="", stderr="denied")
        with patch.object(gateway, "_docker", side_effect=fake_docker):
            with patch.object(gateway, "fail", side_effect=SystemExit) as failed:
                with self.assertRaises(SystemExit):
                    gateway._pull_image("img:latest", False, required=True)
                failed.assert_called_once()


if __name__ == "__main__":
    unittest.main()
