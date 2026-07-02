import asyncio
import io
import json
import unittest
from contextlib import redirect_stdout
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import typer

from hummingbot.cli.commands.balance import _render, balance
from hummingbot.cli.output import ExitCode


def _sample():
    return {
        "kraken": {
            "assets": [
                {"asset": "BTC", "total": Decimal("0.5"), "available": Decimal("0.4"),
                 "value": Decimal("30000"), "allocated": "20%"},
                {"asset": "USDT", "total": Decimal("100"), "available": Decimal("100"),
                 "value": Decimal("100"), "allocated": "0%"},
            ],
            "allocated_total": Decimal("6000"),
            "usd_total": Decimal("30100"),
        },
    }


class BalanceRenderTest(unittest.TestCase):
    def test_render_markdown_table_totals_and_grand_total(self):
        text = _render(_sample(), "$")
        self.assertIn("## kraken", text)                       # per-connector heading
        self.assertIn("| asset | total | value($) | allocated |", text)  # Markdown table header
        self.assertIn("BTC", text)
        self.assertIn("balances: $", text)                     # per-connector balances line
        self.assertIn("allocated:", text)                      # allocated % line
        self.assertIn("connectors total (net): $", text)       # grand total line

    def test_render_empty_exchange(self):
        result = {"kraken": {"assets": [], "allocated_total": Decimal("0"), "usd_total": Decimal("0")}}
        text = _render(result, "$")
        self.assertIn("## kraken", text)
        self.assertIn("_(no balance)_", text)

    def test_render_units_only_hides_value_and_grand_total(self):
        text = _render(_sample(), "$", units_only=True)
        self.assertIn("| asset | total | available |", text)   # units-only columns
        self.assertNotIn("value($)", text)                     # no USD value column
        self.assertNotIn("connectors total", text)             # no grand total when priceless


class BalanceCommandTest(unittest.TestCase):
    """End-to-end runs of the `balance` command with login / UserBalances / RateOracle faked."""

    def setUp(self) -> None:
        self.ccm = SimpleNamespace(
            global_token=SimpleNamespace(global_token_symbol="$"),
            commands_timeout=SimpleNamespace(other_commands_timeout=1))
        patch("hummingbot.cli.commands.balance.login", return_value=(self.ccm, "pw")).start()

        self.conn = Mock()
        self.conn.uses_gateway_generic_connector.return_value = False
        acs = patch("hummingbot.client.settings.AllConnectorSettings").start()
        acs.get_connector_settings.return_value = {"binance_perpetual": self.conn}

        open_position = SimpleNamespace(
            trading_pair="ETH-USDT", position_side=SimpleNamespace(name="LONG"),
            amount=Decimal("2"), entry_price=Decimal("100"),
            unrealized_pnl=Decimal("5"), leverage=Decimal("5"))
        flat_position = SimpleNamespace(
            trading_pair="BTC-USDT", position_side=SimpleNamespace(name="SHORT"),
            amount=Decimal("0"), entry_price=Decimal("1"),
            unrealized_pnl=Decimal("0"), leverage=Decimal("1"))
        self.market = SimpleNamespace(
            account_positions={"open": open_position, "flat": flat_position},
            _update_positions=AsyncMock())
        self.ub = SimpleNamespace(
            all_balances_all_exchanges=AsyncMock(return_value={
                "binance_perpetual": {"USDT": Decimal("100"), "XXX": Decimal("2"), "ZED": Decimal("0")}}),
            all_available_balances_all_exchanges=Mock(
                return_value={"binance_perpetual": {"USDT": Decimal("60")}}),
            _markets={"binance_perpetual": self.market},
            update_exchange_balance=AsyncMock(return_value=None),
            all_balances=Mock(return_value={"USDT": Decimal("100")}),
        )
        ub_cls = patch("hummingbot.user.user_balances.UserBalances").start()
        ub_cls.instance.return_value = self.ub

        self.oracle = SimpleNamespace(
            _source=SimpleNamespace(get_prices=AsyncMock(return_value={"USDT-USD": Decimal("1")})),
            quote_token="USD")
        self.oracle_cls = patch("hummingbot.core.rate_oracle.rate_oracle.RateOracle").start()
        self.oracle_cls.get_instance.return_value = self.oracle
        self.addCleanup(patch.stopall)

    def _run(self, connector=None, units_only=False, as_json=False) -> str:
        buf = io.StringIO()
        with redirect_stdout(buf):
            balance(connector, units_only, False, as_json)
        return buf.getvalue()

    def _fail(self, connector=None, units_only=False, as_json=False) -> int:
        with redirect_stdout(io.StringIO()):
            with self.assertRaises(typer.Exit) as ctx:
                balance(connector, units_only, False, as_json)
        return ctx.exception.exit_code

    # -- all connectors --

    def test_all_markdown_with_positions(self):
        out = self._run()
        self.assertIn("## binance_perpetual", out)
        self.assertIn("USDT", out)
        self.assertIn("XXX", out)                    # priceless asset still listed (value 0)
        self.assertNotIn("ZED", out)                 # zero balance hidden on a non-gateway connector
        self.assertIn("allocated:", out)
        self.assertIn("positions:", out)
        self.assertIn("ETH-USDT", out)               # the open perp position
        self.assertNotIn("BTC-USDT", out)            # zero-amount position filtered out
        self.assertIn("net value: $", out)
        self.assertIn("connectors total (net): $", out)

    def test_all_json_payload(self):
        payload = json.loads(self._run(as_json=True))
        self.assertEqual(payload["quote"], "$")
        entry = payload["connectors"]["binance_perpetual"]
        assets = {a["asset"]: a for a in entry["assets"]}
        self.assertEqual(assets["USDT"]["total"], 100.0)
        self.assertEqual(assets["USDT"]["available"], 60.0)
        self.assertEqual(assets["USDT"]["value"], 100.0)
        self.assertEqual(entry["balances_value"], 100.0)
        self.assertEqual(entry["allocated_value"], 40.0)       # 100 - 60 available, at rate 1
        self.assertEqual(len(entry["positions"]), 1)
        self.assertEqual(entry["unrealized_pnl"], 5.0)
        self.assertEqual(entry["net_value"], 105.0)
        self.assertEqual(payload["net_value_total"], 105.0)

    def test_units_only_skips_prices_and_positions(self):
        out = self._run(units_only=True)
        self.oracle_cls.get_instance.assert_not_called()       # no rate-oracle fetch
        self.assertIn("| asset | total | available |", out)
        self.assertNotIn("positions:", out)
        self.assertNotIn("connectors total", out)

    def test_units_only_json_payload(self):
        payload = json.loads(self._run(units_only=True, as_json=True))
        self.assertIsNone(payload["quote"])
        entry = payload["connectors"]["binance_perpetual"]
        self.assertNotIn("value", entry["assets"][0])
        self.assertNotIn("net_value", entry)
        self.assertNotIn("net_value_total", payload)

    def test_all_empty_result(self):
        self.ub.all_balances_all_exchanges = AsyncMock(return_value={})
        out = self._run()
        self.assertIn("No balances", out)

    def test_all_network_timeout(self):
        self.ub.all_balances_all_exchanges = AsyncMock(side_effect=asyncio.TimeoutError)
        self.assertEqual(self._fail(), int(ExitCode.TIMEOUT))

    def test_gateway_connector_shows_zero_balances(self):
        self.conn.uses_gateway_generic_connector.return_value = True
        self.ub._markets = {}                                  # also covers the no-market branch
        out = self._run()
        self.assertIn("ZED", out)
        self.assertNotIn("positions:", out)

    def test_json_without_positions_omits_position_fields(self):
        self.ub._markets = {}
        payload = json.loads(self._run(as_json=True))
        entry = payload["connectors"]["binance_perpetual"]
        self.assertNotIn("positions", entry)
        self.assertNotIn("unrealized_pnl", entry)
        self.assertEqual(entry["net_value"], 100.0)

    def test_positions_only_connector_renders_positions_section(self):
        # all balances zero (hidden on a CEX) but an open position -> positions section only
        self.ub.all_balances_all_exchanges = AsyncMock(
            return_value={"binance_perpetual": {"ZED": Decimal("0")}})
        out = self._run()
        self.assertIn("positions:", out)
        self.assertIn("ETH-USDT", out)
        self.assertNotIn("| asset |", out)

    def test_positions_skipped_without_account_positions_or_on_update_error(self):
        self.ub._markets = {"binance_perpetual": SimpleNamespace()}  # no account_positions attr
        self.assertNotIn("positions:", self._run())
        failing = SimpleNamespace(account_positions={},
                                  _update_positions=AsyncMock(side_effect=RuntimeError("boom")))
        self.ub._markets = {"binance_perpetual": failing}
        self.assertNotIn("positions:", self._run())

    # -- single connector --

    def test_single_connector(self):
        out = self._run("binance_perpetual")
        self.ub.update_exchange_balance.assert_awaited_once()
        self.assertIn("## binance_perpetual", out)
        self.assertIn("USDT", out)
        self.assertIn("positions:", out)

    def test_single_connector_units_only(self):
        out = self._run("binance_perpetual", units_only=True)
        self.oracle_cls.get_instance.assert_not_called()
        self.assertIn("| asset | total | available |", out)
        self.assertNotIn("positions:", out)

    def test_single_connector_unknown_fails(self):
        self.assertEqual(self._fail("nope"), int(ExitCode.CONFIG_ERROR))

    def test_single_connector_auth_error_fails(self):
        self.ub.update_exchange_balance = AsyncMock(return_value="bad credentials")
        self.assertEqual(self._fail("binance_perpetual"), int(ExitCode.ERROR))

    def test_single_connector_timeout(self):
        self.ub.update_exchange_balance = AsyncMock(side_effect=asyncio.TimeoutError)
        self.assertEqual(self._fail("binance_perpetual"), int(ExitCode.TIMEOUT))


if __name__ == "__main__":
    unittest.main()
