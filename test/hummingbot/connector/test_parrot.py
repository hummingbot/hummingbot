import asyncio
import json

from aioresponses import aioresponses
from decimal import Decimal
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

    @aioresponses()
    def test_active_campaigns_are_filetered_by_token_pair(self, mock_api):
        url = f"{parrot.PARROT_MINER_BASE_URL}campaigns"
        resp = [
            {
                "id": 26,
                "campaign_name": "xym",
                "link": "https://symbolplatform.com/",
                "markets": [{
                    "id": 62,
                    "trading_pair": "XYM-BTC",
                    "exchange_name": "kucoin",
                    "base_asset": "XYM",
                    "base_asset_full_name": "symbol",
                    "quote_asset": "BTC",
                    "quote_asset_full_name": "bitcoin"}],
                "bounty_periods": [{
                    "id": 823,
                    "start_datetime": "2021-10-05T00:00:00",
                    "end_datetime": "2021-10-12T00:00:00",
                    "payout_parameters": [{
                        "id": 2212,
                        "market_id": 62,
                        "bid_budget": 1371.5,
                        "ask_budget": 1371.5,
                        "exponential_decay_function_factor": 8.0,
                        "spread_max": 1.5,
                        "payout_asset": "XYM"}]}]},
            {
                "id": 27,
                "campaign_name": "test",
                "link": "https://symbolplatform.com/",
                "markets": [{
                    "id": 63,
                    "trading_pair": "COINALPHA-HBOT",
                    "exchange_name": "kucoin",
                    "base_asset": "COINALPHA",
                    "base_asset_full_name": "coinalpha",
                    "quote_asset": "HBOT",
                    "quote_asset_full_name": "hbot"}],
                "bounty_periods": [{
                    "id": 823,
                    "start_datetime": "2021-10-05T00:00:00",
                    "end_datetime": "2021-10-12T00:00:00",
                    "payout_parameters": [
                        {"id": 2213,
                         "market_id": 63,
                         "bid_budget": 1371.5,
                         "ask_budget": 1371.5,
                         "exponential_decay_function_factor": 8.0,
                         "spread_max": 1.5,
                         "payout_asset": "HBOT"}]}]}]

        mock_api.get(url, body=json.dumps(resp))

        campaigns = asyncio.get_event_loop().run_until_complete(
            parrot.get_active_campaigns(
                exchange="kucoin",
                trading_pairs=["COINALPHA-HBOT"]))

        self.assertEqual(1, len(campaigns))
        campaign_summary: parrot.CampaignSummary = campaigns[63]
        self.assertEquals("COINALPHA-HBOT", campaign_summary.trading_pair)
        self.assertEquals("kucoin", campaign_summary.exchange_name)
        self.assertEquals(Decimal("0.015"), campaign_summary.spread_max)

    @aioresponses()
    def test_active_campaigns_are_filetered_by_exchange_name(self, mock_api):
        url = f"{parrot.PARROT_MINER_BASE_URL}campaigns"
        resp = [
            {
                "id": 26,
                "campaign_name": "xym",
                "link": "https://symbolplatform.com/",
                "markets": [{
                    "id": 62,
                    "trading_pair": "XYM-BTC",
                    "exchange_name": "ascendex",
                    "base_asset": "XYM",
                    "base_asset_full_name": "symbol",
                    "quote_asset": "BTC",
                    "quote_asset_full_name": "bitcoin"}],
                "bounty_periods": [{
                    "id": 823,
                    "start_datetime": "2021-10-05T00:00:00",
                    "end_datetime": "2021-10-12T00:00:00",
                    "payout_parameters": [{
                        "id": 2212,
                        "market_id": 62,
                        "bid_budget": 1371.5,
                        "ask_budget": 1371.5,
                        "exponential_decay_function_factor": 8.0,
                        "spread_max": 1.5,
                        "payout_asset": "XYM"}]}]}]

        mock_api.get(url, body=json.dumps(resp))

        campaigns = asyncio.get_event_loop().run_until_complete(
            parrot.get_active_campaigns(
                exchange="test_exchange",
                trading_pairs=["XYM-BTC"]))

        self.assertEqual(0, len(campaigns))

        mock_api.get(url, body=json.dumps(resp))
        campaigns = asyncio.get_event_loop().run_until_complete(
            parrot.get_active_campaigns(
                exchange="ascend_ex",
                trading_pairs=["XYM-BTC"]))
        self.assertEqual(1, len(campaigns))

    @aioresponses()
    def test_get_campaign_summary_logs_error_if_exception_happens(self, mock_api):
        url = f"{parrot.PARROT_MINER_BASE_URL}campaigns"

        mock_api.get(url, exception=Exception("Test error description"))

        campaigns = asyncio.get_event_loop().run_until_complete(
            parrot.get_campaign_summary(
                exchange="test_exchange",
                trading_pairs=["XYM-BTC"]))

        self.assertEqual(0, len(campaigns))
        self.assertTrue(self._is_logged("ERROR",
                                        "Unexpected error while requesting data from Hummingbot API."))

    def test_are_same_entity(self):
        self.assertTrue(parrot.are_same_entity("ascend_ex", "ascendex"))
        self.assertTrue(parrot.are_same_entity("ascend_ex", "ascend_ex"))
        self.assertTrue(parrot.are_same_entity("gate_io", "gateio"))
        self.assertFalse(parrot.are_same_entity("gate_io", "gateios"))
