"""Gateway is restarted for a config write, and for nothing else.

Gateway reads its config once, at startup: a chain binds its RPC connection in the
constructor of a per-network singleton, and a connector's settings are the fields of a
module-level object evaluated at import. So a config write needs the restart -- measured
against a running Gateway, setting `jupiter.slippagePct` to 5 left `GET /config`
answering 5 while quotes went on applying 1.

Token and pool lists are read off disk per request, so those writes are live the moment
they land. The commands used to restart Gateway for them anyway, which cost every caller
a process bounce -- and, on a Docker Gateway whose restart policy is not `always`, risked
not coming back at all, since Gateway exits 0 and that is not a failure to revive from.
"""
import asyncio
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from hummingbot.core.gateway.gateway_http_client import GatewayHttpClient

REPO_ROOT = Path(__file__).resolve().parents[4]
PACKAGE = REPO_ROOT / "hummingbot"


class TestGatewayRestartsOnlyForConfig(unittest.TestCase):

    def test_a_config_write_restarts_gateway(self):
        client = GatewayHttpClient.get_instance()
        with patch.object(GatewayHttpClient, "api_request", new_callable=AsyncMock) as api:
            api.return_value = {}
            asyncio.new_event_loop().run_until_complete(
                client.update_config("jupiter", "slippagePct", 2)
            )
        called = [c.args[1] for c in api.call_args_list]
        self.assertIn("config/update", called)
        self.assertIn("restart", called)

    def test_the_token_command_does_not_restart_gateway(self):
        source = (PACKAGE / "client" / "command" / "gateway_token_command.py").read_text()
        self.assertNotIn("post_restart", source)

    def test_the_pool_command_does_not_restart_gateway(self):
        source = (PACKAGE / "client" / "command" / "gateway_pool_command.py").read_text()
        self.assertNotIn("post_restart", source)

    def test_config_update_is_the_only_thing_that_restarts_gateway(self):
        # A new caller of post_restart is a new process bounce; it should be a decision,
        # not a copy-paste. update_config is the one place that has earned it.
        callers = set()
        for path in PACKAGE.rglob("*.py"):
            for line in path.read_text(errors="ignore").splitlines():
                if "post_restart" in line and "def post_restart" not in line:
                    callers.add(str(path.relative_to(REPO_ROOT)))
        self.assertEqual({"hummingbot/core/gateway/gateway_http_client.py"}, callers)


if __name__ == "__main__":
    unittest.main()
