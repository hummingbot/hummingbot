import unittest
from typing import List
from unittest.mock import MagicMock

from prompt_toolkit.completion import CompleteEvent
from prompt_toolkit.document import Document

import hummingbot.client.hummingbot_application  # noqa: F401  imported first to break the client/ui import cycle
from hummingbot.client.settings import GATEWAY_CHAINS, GATEWAY_ETH_DEXS, GATEWAY_NAMESPACES
from hummingbot.client.ui.completer import HummingbotCompleter

CHAINS = ["ethereum", "solana"]
ETH_DEXS = ["uniswap/amm", "uniswap/clmm"]
NAMESPACES = ["ethereum-mainnet", "solana-mainnet-beta", "uniswap"]


class GatewayCompleterTest(unittest.TestCase):
    """The gateway completers read module-level lists that the Gateway monitor loop fills in."""

    def setUp(self):
        # These lists are held by reference inside the completers, so they have to be
        # populated in place rather than rebound.
        self._saved = (list(GATEWAY_CHAINS), list(GATEWAY_ETH_DEXS), list(GATEWAY_NAMESPACES))
        GATEWAY_CHAINS[:] = CHAINS
        GATEWAY_ETH_DEXS[:] = ETH_DEXS
        GATEWAY_NAMESPACES[:] = NAMESPACES

        app = MagicMock()
        app.app.prompt_text = ">>> "
        self.completer = HummingbotCompleter(app)

    def tearDown(self):
        GATEWAY_CHAINS[:], GATEWAY_ETH_DEXS[:], GATEWAY_NAMESPACES[:] = self._saved

    def completions(self, text: str) -> List[str]:
        document = Document(text, len(text))
        return [c.text for c in self.completer.get_completions(document, CompleteEvent())]

    def test_subcommands_complete_while_being_typed(self):
        self.assertEqual(
            ["allowance", "approve", "balance", "config", "connect", "generate-certs", "list"],
            self.completions("gateway "),
        )
        self.assertEqual(["config", "connect"], self.completions("gateway co"))

    def test_config_completes_namespace_then_action(self):
        self.assertEqual(NAMESPACES, self.completions("gateway config "))
        self.assertEqual(["ethereum-mainnet"], self.completions("gateway config eth"))
        self.assertEqual(["update"], self.completions("gateway config ethereum-mainnet "))
        self.assertEqual(["update"], self.completions("gateway config ethereum-mainnet up"))

    def test_chain_arguments_complete(self):
        for command in ("balance", "connect"):
            self.assertEqual(CHAINS, self.completions(f"gateway {command} "), command)
            # a partially typed chain still completes - it used to stop at the first character
            self.assertEqual(["solana"], self.completions(f"gateway {command} sol"), command)

    def test_connector_arguments_complete_for_ethereum_connectors(self):
        for command in ("allowance", "approve"):
            self.assertEqual(ETH_DEXS, self.completions(f"gateway {command} "), command)
            self.assertEqual(ETH_DEXS, self.completions(f"gateway {command} uni"), command)

    def test_free_form_arguments_get_no_suggestions(self):
        # the argument after the connector is a token symbol, after the chain a token list,
        # and after `update` a config path/value - none of them are completable
        self.assertEqual([], self.completions("gateway approve uniswap/amm "))
        self.assertEqual([], self.completions("gateway balance ethereum "))
        self.assertEqual([], self.completions("gateway config ethereum-mainnet update "))
        self.assertEqual([], self.completions("gateway config ethereum-mainnet update nodeURL "))

    def test_argument_less_subcommands_get_no_suggestions(self):
        # these must not fall through to the generic subcommand completer
        self.assertEqual([], self.completions("gateway list "))
        self.assertEqual([], self.completions("gateway generate-certs "))

    def test_unknown_subcommand_gets_no_suggestions(self):
        self.assertEqual([], self.completions("gateway nonsense "))


if __name__ == "__main__":
    unittest.main()
