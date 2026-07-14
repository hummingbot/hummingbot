from copy import deepcopy
from pathlib import Path
from unittest import TestCase

import yaml

from hummingbot.strategy_v2.routing.config import RoutingConfig, load_routing_config


ROOT = Path(__file__).resolve().parents[4]
EXAMPLE = ROOT / "reports/examples/strategy_router_accounts.example.yml"


class RoutingConfigTest(TestCase):
    def setUp(self):
        self.payload = yaml.safe_load(EXAMPLE.read_text(encoding="utf-8"))

    def test_loads_documented_paper_configuration(self):
        config = load_routing_config(EXAMPLE)

        self.assertEqual("paper", config.environment.value)
        self.assertEqual(5, len(config.accounts))
        self.assertEqual(
            4, len([row for row in config.accounts if row.trading_enabled])
        )
        self.assertFalse(config.release.allow_live_actions)
        self.assertFalse(config.release.allow_automatic_transfers)

    def test_paper_account_rejects_live_credential_reference(self):
        payload = deepcopy(self.payload)
        payload["accounts"][1]["credential_ref"] = "env-prefix:GATE_MM"

        with self.assertRaisesRegex(ValueError, "paper accounts"):
            RoutingConfig.model_validate(payload)

    def test_parent_cycle_is_rejected(self):
        payload = deepcopy(self.payload)
        payload["accounts"][0]["kind"] = "subaccount"
        payload["accounts"][0]["parent_id"] = "binance-mm"

        with self.assertRaisesRegex(ValueError, "parent cycle"):
            RoutingConfig.model_validate(payload)

    def test_duplicate_worker_is_rejected(self):
        payload = deepcopy(self.payload)
        payload["accounts"][2]["worker_id"] = payload["accounts"][1]["worker_id"]

        with self.assertRaisesRegex(ValueError, "worker_id"):
            RoutingConfig.model_validate(payload)

    def test_strategy_binding_must_match_account_sleeve(self):
        payload = deepcopy(self.payload)
        payload["strategy_bindings"][0]["account_selector"]["account_ids"] = [
            "binance-directional"
        ]

        with self.assertRaisesRegex(ValueError, "not allowed"):
            RoutingConfig.model_validate(payload)

    def test_unknown_secret_fields_are_rejected(self):
        payload = deepcopy(self.payload)
        payload["accounts"][1]["api_secret"] = "must-not-be-accepted"

        with self.assertRaises(ValueError):
            RoutingConfig.model_validate(payload)

    def test_evolution_auto_start_is_rejected(self):
        payload = deepcopy(self.payload)
        payload["integration"]["evolution"]["allow_evolution_auto_start"] = True

        with self.assertRaisesRegex(ValueError, "cannot auto-start"):
            RoutingConfig.model_validate(payload)
