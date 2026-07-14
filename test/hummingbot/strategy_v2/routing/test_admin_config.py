from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

import yaml

from hummingbot.strategy_v2.routing.paths import default_routing_config_path
from scripts.update_strategy_router_account import update_account


ROOT = Path(__file__).resolve().parents[4]
EXAMPLE = ROOT / "reports/examples/strategy_router_accounts.example.yml"


class RoutingAdminConfigTest(TestCase):
    def test_operational_config_overrides_template(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            template = root / "reports/examples/strategy_router_accounts.example.yml"
            template.parent.mkdir(parents=True)
            template.write_text("version: 1\n", encoding="utf-8")

            self.assertEqual(template, default_routing_config_path(root))

            operational = root / "conf/runtime/strategy_router_accounts.yml"
            operational.parent.mkdir(parents=True)
            operational.write_text("version: 1\n", encoding="utf-8")
            self.assertEqual(operational, default_routing_config_path(root))

    def test_only_allowlisted_limits_change_and_full_config_is_validated(self):
        with TemporaryDirectory() as directory:
            destination = Path(directory) / "strategy_router_accounts.yml"
            result = update_account(
                EXAMPLE,
                destination,
                "binance-mm",
                {
                    "minimum_reserve_quote": 600,
                    "maximum_capital_quote": 3600,
                    "maximum_drawdown_quote": 80,
                    "maximum_gross_exposure_quote": 2600,
                    "maximum_open_orders": 10,
                    "market_data_stale_after_seconds": 25,
                },
            )
            payload = yaml.safe_load(destination.read_text(encoding="utf-8"))
            account = next(
                row for row in payload["accounts"] if row["id"] == "binance-mm"
            )

            self.assertEqual(3600, result["allocation"]["maximum_capital_quote"])
            self.assertEqual(10, account["risk"]["maximum_open_orders"])
            self.assertEqual("paper:none", account["credential_ref"])
            self.assertFalse(account["permissions"]["withdraw"])

    def test_invalid_reserve_cap_relationship_is_rejected(self):
        with TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "reserve exceeds maximum capital"):
                update_account(
                    EXAMPLE,
                    Path(directory) / "strategy_router_accounts.yml",
                    "binance-mm",
                    {
                        "minimum_reserve_quote": 4000,
                        "maximum_capital_quote": 3000,
                    },
                )
