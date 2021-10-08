import asyncio
import json

from aioresponses import aioresponses
from unittest import TestCase

import hummingbot.connector.parrot as parrot


class CampaignsAPIFunctionTests(TestCase):
    # logging.Level required to receive logs from the data source logger
    level = 0

    def setUp(self) -> None:
        super().setUp()
        self.log_records = []

        parrot.logger().setLevel(1)
        parrot.logger().addHandler(self)

    def handle(self, record):
        self.log_records.append(record)

    def _is_logged(self, log_level: str, message: str) -> bool:
        return any(record.levelname == log_level and record.getMessage().startswith(message)
                   for record in self.log_records)

    @aioresponses()
    def test_retrieve_active_campaigns_error_is_logged(self, mock_api):
        url = f"{parrot.PARROT_MINER_BASE_URL}campaigns"
        resp = {"error": "Rate limit exceeded: 10 per 1 minute"}
        mock_api.get(url, body=json.dumps(resp))

        campaigns = asyncio.get_event_loop().run_until_complete(
            parrot.get_active_campaigns(
                exchange="binance",
                trading_pairs=["COINALPHA-HBOT"]))

        self.assertEqual(0, len(campaigns))
        self.assertTrue(self._is_logged("WARNING",
                                        "Could not get active campaigns from Hummingbot API"
                                        f" (returned response '{resp}')."))
