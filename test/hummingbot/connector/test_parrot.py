import asyncio
import json
from asyncio import CancelledError
from copy import copy
from decimal import Decimal
from unittest import TestCase
from unittest.mock import patch

from aioresponses import aioresponses

import hummingbot.connector.parrot as parrot


class ParrotConnectorUnitTest(TestCase):
    # logging.Level required to receive logs from the data source logger
    level = 0

    @classmethod
    def setUpClass(cls):
        cls.ev_loop: asyncio.AbstractEventLoop = asyncio.get_event_loop()

    def setUp(self) -> None:
        super().setUp()
        self.log_records = []

        parrot.logger().setLevel(1)
        parrot.logger().addHandler(self)

        self.campaigns_get_resp = {"status": "success", "campaigns": [
            {"id": 1, "campaign_name": "zilliqa", "link": "https://zilliqa.com/index.html", "markets": [
                {"market_id": 1, "exchange_name": "binance", "base_asset": "ZIL", "quote_asset": "USDT",
                 "base_asset_full_name": "zilliqa", "quote_asset_full_name": "tether", "trading_pair": "ZILUSDT",
                 "return": 1.4600818845692998, "last_snapshot_ts": 1592263560000,
                 "last_snapshot_volume": 7294.967867187001, "trailing_1h_volume": 525955.48182515,
                 "hourly_payout_usd": 1.488095238095238, "bots": 10, "last_hour_bots": 14, "filled_24h_volume": 0.0,
                 "market_24h_usd_volume": 0.0},
            ]}]}
        self.expected_campaign_no_markets = parrot.CampaignSummary(market_id=1, trading_pair='ZIL-USDT',
                                                                   exchange_name='binance', spread_max=Decimal('0'),
                                                                   payout_asset='', liquidity=Decimal('0'),
                                                                   liquidity_usd=Decimal('0'), active_bots=0,
                                                                   reward_per_wk=Decimal('0'), apy=Decimal('0'))
        self.expected_campaign_w_markets = parrot.CampaignSummary(market_id=1, trading_pair='ZIL-USDT',
                                                                  exchange_name='binance', spread_max=Decimal('0.02'),
                                                                  payout_asset='ZIL', liquidity=Decimal('0'),
                                                                  liquidity_usd=Decimal('0'), active_bots=15,
                                                                  reward_per_wk=Decimal('205930.0'), apy=Decimal('0'))
        self.expected_campaign_32_markets = {
            32: parrot.CampaignSummary(market_id=32, trading_pair='ALGO-USDT', exchange_name='binance',
                                       spread_max=Decimal('0.015'), payout_asset='ALGO', liquidity=Decimal('0'),
                                       liquidity_usd=Decimal('0'), active_bots=18, reward_per_wk=Decimal('341.0'),
                                       apy=Decimal('0'))}
        self.markets_get_resp = {"status": "success", "markets": [
            {"base_asset": "ZIL",
             "base_asset_full_name": "zilliqa", "exchange_name": "binance",
             "market_id": 1, "quote_asset": "USDT", "quote_asset_full_name": "tether", "trading_pair": "ZIL/USDT",
             "base_asset_address": "", "quote_asset_address": "",
             "active_bounty_periods": [
                 {"bounty_period_id": 2396, "bounty_campaign_id": 38, "bounty_campaign_name": "dafi",
                  "bounty_campaign_link": "https://zilliqa.com/index.html", "start_timestamp": 1657584000000,
                  "end_timestamp": 1658188800000, "budget": {"bid": 102965.0, "ask": 102965.0}, "spread_max": 2.0,
                  "payout_asset": "ZIL"}], "return": 8.694721275945772, "last_snapshot_ts": 1657812180000,
             "last_snapshot_volume": 3678.5291375, "trailing_1h_volume": 261185.66037849995,
             "hourly_payout_usd": 4.317788244047619, "bots": 15, "last_hour_bots": 18, "filled_24h_volume": 6816.23476,
             "weekly_reward_in_usd": 751.8118232323908, "weekly_reward": {"ZIL": 205735.9191468253},
             "has_user_bots": 'false', "market_24h_usd_volume": 0.0}]}

        self.get_fail = {"status": "error", "message": "ERROR message"}

        self.snapshot_get_resp = {"status": "success", "market_snapshot": {"market_id": 32, "timestamp": 1657747860000,
                                                                           "last_snapshot_ts": 1657747864000,
                                                                           "annualized_return": 0.4026136989303596,
                                                                           "payout_summary": {"open_volume": {
                                                                               "reward": {
                                                                                   "ask": {"ALGO": 0.01691468253968254},
                                                                                   "bid": {
                                                                                       "ALGO": 0.01691468253968254}},
                                                                               "reward_profoma": {
                                                                                   "ask": {"ALGO": 0.01691468253968254},
                                                                                   "bid": {
                                                                                       "ALGO": 0.01691468253968254}},
                                                                               "payout_asset_usd_rate": {
                                                                                   "ALGO": 0.30415},
                                                                               "total_hourly_payout_usd": 0.6173520833333332},
                                                                               "filled_volume": {}},
                                                                           "summary_stats": {"open_volume": {
                                                                               "ask": {"accumulated_roll_over": 0},
                                                                               "bid": {"accumulated_roll_over": 0},
                                                                               "bots": 17, "oov_ask": 16274,
                                                                               "oov_bid": 31099, "bots_ask": 14,
                                                                               "bots_bid": 9,
                                                                               "spread_ask": 0.29605111465204803,
                                                                               "spread_bid": 0.33684674006707405,
                                                                               "last_hour_bots": 19,
                                                                               "oov_eligible_ask": 16156,
                                                                               "oov_eligible_bid": 26059,
                                                                               "last_hour_bots_ask": 16,
                                                                               "last_hour_bots_bid": 15,
                                                                               "base_asset_usd_rate": 0.30415,
                                                                               "quote_asset_usd_rate": 1},
                                                                               "filled_volume": {}}},
                                  "user_snapshot": {"timestamp": 1657747860000, "is_default": True,
                                                    "rewards_summary": {"ask": {}, "bid": {}},
                                                    "summary_stats": {"oov_ask": 0, "oov_bid": 0, "reward_pct": 0,
                                                                      "spread_ask": -1, "spread_bid": -1,
                                                                      "reward": {"ask": {}, "bid": {}},
                                                                      "reward_profoma": {"ask": {}, "bid": {}},
                                                                      "open_volume_pct": 0, "oov_eligible_ask": 0,
                                                                      "oov_eligible_bid": 0}},
                                  "market_mid_price": 0.30415}
        self.expected_snapshots_bad_timestamp = {"status": "error",
                                                 "message": "Data not available for timestamp 1657747860000."}
        self.expected_snapshots_error = {"status": "error", "message": "404: Not Found"}

        self.expected_summary = {
            'ALGO-USDT': parrot.CampaignSummary(market_id=32, trading_pair='ALGO-USDT', exchange_name='binance',
                                                spread_max=Decimal('0.015'), payout_asset='ALGO',
                                                liquidity=Decimal('42215'),
                                                liquidity_usd=Decimal('12839.69224999999898390035113'), active_bots=17,
                                                reward_per_wk=Decimal('341.0'),
                                                apy=Decimal('0.40261369893035958700266974119585938751697540283203125'))}

    def handle(self, record):
        self.log_records.append(record)

    def _is_logged(self, log_level: str, message: str) -> bool:
        return any(record.levelname == log_level and record.getMessage().startswith(message)
                   for record in self.log_records)

    @aioresponses()
    def test_get_active_campaigns_empty_markets(self, mocked_http):
        mocked_http.get(f"{parrot.PARROT_MINER_BASE_URL}campaigns", body=json.dumps(self.campaigns_get_resp))
        mocked_http.get(f"{parrot.PARROT_MINER_BASE_URL}markets", body=json.dumps(""))

        campaigns = self.ev_loop.run_until_complete(parrot.get_active_campaigns("binance"))

        self.assertEqual({1: self.expected_campaign_no_markets}, campaigns)
        self.assertTrue(self._is_logged("WARNING",
                                        "Could not get active markets from Hummingbot API"
                                        " (returned response '')."))

    @aioresponses()
    def test_get_active_campaigns_failed_markets(self, mocked_http):
        mocked_http.get(f"{parrot.PARROT_MINER_BASE_URL}campaigns", body=json.dumps(self.campaigns_get_resp))
        mocked_http.get(f"{parrot.PARROT_MINER_BASE_URL}markets", body=json.dumps(self.get_fail))

        campaigns = self.ev_loop.run_until_complete(parrot.get_active_campaigns("binance"))

        self.assertEqual({1: self.expected_campaign_no_markets}, campaigns)
        self.assertTrue(self._is_logged("WARNING",
                                        "Could not get active markets from Hummingbot API"
                                        f" (returned response '{self.get_fail}')."))

    @aioresponses()
    def test_get_active_campaigns_markets_wrong_id(self, mocked_http):
        mocked_http.get(f"{parrot.PARROT_MINER_BASE_URL}campaigns", body=json.dumps(self.campaigns_get_resp))
        market_wrong_id = self.markets_get_resp
        market_wrong_id["markets"][0]["market_id"] = 10
        mocked_http.get(f"{parrot.PARROT_MINER_BASE_URL}markets", body=json.dumps(market_wrong_id))

        campaigns = self.ev_loop.run_until_complete(parrot.get_active_campaigns("binance"))

        self.assertEqual({1: self.expected_campaign_no_markets}, campaigns)
        self.assertFalse(self._is_logged("WARNING",
                                         "Could not get active markets from Hummingbot API"
                                         f" (returned response '{self.get_fail}')."))

    @aioresponses()
    def test_get_active_campaigns_markets(self, mocked_http):
        mocked_http.get(f"{parrot.PARROT_MINER_BASE_URL}campaigns", body=json.dumps(self.campaigns_get_resp))
        mocked_http.get(f"{parrot.PARROT_MINER_BASE_URL}markets", body=json.dumps(self.markets_get_resp))

        campaigns = self.ev_loop.run_until_complete(parrot.get_active_campaigns("binance", ["ZIL-USDT"]))
        self.assertEqual({1: self.expected_campaign_w_markets}, campaigns)

    # def test_get_active_campaigns_markets_live(self):
    #    campaigns = self.ev_loop.run_until_complete(parrot.get_active_campaigns("binance", ["ALGO-USDT"]))
    #    self.assertEqual({1: self.expected_campaign_w_markets}, campaigns)

    @aioresponses()
    def test_get_active_markets(self, mocked_http):
        mocked_http.get(f"{parrot.PARROT_MINER_BASE_URL}markets", body=json.dumps(self.markets_get_resp))
        campaigns = {1: copy(self.expected_campaign_no_markets)}
        campaigns = self.ev_loop.run_until_complete(parrot.get_active_markets(campaigns))
        self.assertNotEqual({1: self.expected_campaign_no_markets}, campaigns)
        self.assertEqual({1: self.expected_campaign_w_markets}, campaigns)

    @aioresponses()
    def test_get_market_snapshots(self, mocked_http):
        market_id = 32
        mocked_http.get(
            f"{parrot.PARROT_MINER_BASE_URL}charts/market_band?chart_interval=1&market_id={market_id}",
            body=json.dumps({"status": "success", "data": [
                {"timestamp": 1662589860000, "price": 0.30005, "ask": 0.301145, "bid": 0.298362,
                 "spread_ask": 0.3647958323482506, "spread_bid": 0.5624147716913023, "liquidity": 32932.5255}]}))
        snapshot = self.ev_loop.run_until_complete(parrot.get_market_snapshots(market_id))
        self.assertEqual({'data': [{'ask': 0.301145,
                                    'bid': 0.298362,
                                    'liquidity': 32932.5255,
                                    'price': 0.30005,
                                    'spread_ask': 0.3647958323482506,
                                    'spread_bid': 0.5624147716913023,
                                    'timestamp': 1662589860000}],
                          'status': 'success'}, snapshot)

    @aioresponses()
    def test_get_market_snapshots_returns_none(self, mocked_http):
        market_id = 32
        # 'status' == "error"
        mocked_http.get(
            f"{parrot.PARROT_MINER_BASE_URL}charts/market_band?chart_interval=1&market_id={market_id}",
            body=json.dumps({"status": "error", "data": []}))
        snapshot = self.ev_loop.run_until_complete(parrot.get_market_snapshots(market_id))
        self.assertEqual(None, snapshot)

        # No 'status' field
        mocked_http.get(
            f"{parrot.PARROT_MINER_BASE_URL}charts/market_band?chart_interval=1&market_id={market_id}",
            body=json.dumps({"data": []}))
        snapshot = self.ev_loop.run_until_complete(parrot.get_market_snapshots(market_id))
        self.assertEqual(None, snapshot)

        # JSON resp is None
        mocked_http.get(
            f"{parrot.PARROT_MINER_BASE_URL}charts/market_band?chart_interval=1&market_id={market_id}",
            body=json.dumps(None))
        snapshot = self.ev_loop.run_until_complete(parrot.get_market_snapshots(market_id))
        self.assertEqual(None, snapshot)

    @aioresponses()
    def test_get_market_last_snapshot(self, mocked_http):
        market_id = 32
        timestamp = 1662589860000
        mocked_http.get(
            f"{parrot.PARROT_MINER_BASE_URL}user/single_snapshot?aggregate_period=1m&market_id={market_id}&timestamp={timestamp}",
            body=json.dumps(self.snapshot_get_resp))
        with patch("hummingbot.connector.parrot.get_market_snapshots") as mocked_snapshots:
            mocked_snapshots.return_value = {"status": "success", "data": [{"timestamp": timestamp}]}
            snapshot = self.ev_loop.run_until_complete(parrot.get_market_last_snapshot(market_id))
        self.assertEqual(self.snapshot_get_resp, snapshot)

    # This test is likely to fail with time as the data will change
    # def test_get_market_last_snapshot_live(self):
    #    market_id = 32
    #    snapshot = self.ev_loop.run_until_complete(parrot.get_market_last_snapshot(market_id))
    #    self.assertEqual(self.snapshot_get_resp, snapshot)

    @aioresponses()
    def test_get_campaign_summary(self, mocked_http):
        timestamp = 16577478600000
        mocked_http.get(
            f"{parrot.PARROT_MINER_BASE_URL}user/single_snapshot?aggregate_period=1m&market_id={32}&timestamp={timestamp}",
            body=json.dumps(self.snapshot_get_resp))
        with patch("hummingbot.connector.parrot.get_market_snapshots") as mocked_snapshots:
            mocked_snapshots.return_value = {"status": "success", "data": [{"timestamp": timestamp}]}
            with patch('hummingbot.connector.parrot.get_active_campaigns') as mocked_ac:
                mocked_ac.return_value = self.expected_campaign_32_markets
                summary = self.ev_loop.run_until_complete(parrot.get_campaign_summary("binance", ["ALGO-USDT"]))
        self.assertEqual(self.expected_summary, summary)

    @aioresponses()
    def test_get_campaign_summary_http_error(self, mocked_http):
        timestamp = 16577478600000
        mocked_http.get(
            f"{parrot.PARROT_MINER_BASE_URL}user/single_snapshot?market_id={32}&timestamp={timestamp}&aggregate_period=1m",
            body=json.dumps(self.snapshot_get_resp))
        with patch('hummingbot.connector.parrot.get_active_campaigns') as mocked_ac:
            with patch("hummingbot.connector.parrot.get_market_snapshots") as mocked_snapshots:
                mocked_snapshots.return_value = {"status": "success", "data": [{"timestamp": timestamp}]}
                with patch('hummingbot.connector.parrot.get_market_snapshots') as mocked_ss:
                    mocked_ac.return_value = self.expected_campaign_32_markets
                    mocked_ss.return_value = self.expected_snapshots_error
                    summary = self.ev_loop.run_until_complete(parrot.get_campaign_summary("binance", ["ALGO-USDT"]))
        # No snapshot, just dict re-arrangement
        self.assertEqual({}, summary)
        self.assertTrue(self._is_logged("ERROR", "Unexpected error while requesting data from Hummingbot API."))

    @aioresponses()
    def test_get_campaign_summary_exception(self, mocked_http):
        mocked_http.get(
            f"{parrot.PARROT_MINER_BASE_URL}user/single_snapshot?market_id={32}&timestamp={-1}&aggregate_period=1m",
            body=json.dumps(self.snapshot_get_resp))
        with patch('hummingbot.connector.parrot.get_active_campaigns') as mocked_ac:
            with patch('hummingbot.connector.parrot.get_market_snapshots') as mocked_ss:
                with self.assertRaises(CancelledError):
                    mocked_ac.side_effect = asyncio.CancelledError
                    mocked_ss.return_value = self.expected_campaign_32_markets
                    self.ev_loop.run_until_complete(parrot.get_campaign_summary("binance", ["ALGO-USDT"]))
                    self.assertTrue(
                        self._is_logged("ERROR", "Unexpected error while requesting data from Hummingbot API."))

                with self.assertRaises(CancelledError):
                    mocked_ac.return_value = self.expected_campaign_32_markets
                    mocked_ss.side_effect = asyncio.CancelledError
                    self.ev_loop.run_until_complete(parrot.get_campaign_summary("binance", ["ALGO-USDT"]))
                    self.assertTrue(
                        self._is_logged("ERROR", "Unexpected error while requesting data from Hummingbot API."))

    @aioresponses()
    def test_retrieve_active_campaigns_error_is_logged(self, mock_api):
        resp = {"status": "error", "message": "Rate limit exceeded: 10 per 1 minute"}
        mock_api.get(f"{parrot.PARROT_MINER_BASE_URL}campaigns", body=json.dumps(resp))
        mock_api.get(f"{parrot.PARROT_MINER_BASE_URL}markets", body=json.dumps(resp))

        campaigns = asyncio.get_event_loop().run_until_complete(
            parrot.get_active_campaigns(
                exchange="binance",
                trading_pairs=["COINALPHA-HBOT"]))

        self.assertEqual(0, len(campaigns))
        self.assertTrue(self._is_logged("WARNING",
                                        "Could not get active campaigns from Hummingbot API"
                                        f" (returned response '{resp}')."))

    @aioresponses()
    def test_active_campaigns_are_filtered_by_token_pair(self, mock_api):
        url = f"{parrot.PARROT_MINER_BASE_URL}campaigns"
        resp = {
            "status": "success",
            "campaigns": [{
                "id": 26,
                "campaign_name": "xym",
                "link": "https://symbolplatform.com/",
                "markets": [{
                    "market_id": 62,
                    "trading_pair": "XYM-BTC",
                    "exchange_name": "kucoin",
                    "base_asset": "XYM",
                    "base_asset_full_name": "symbol",
                    "quote_asset": "BTC",
                    "quote_asset_full_name": "bitcoin"}]},
                {
                    "id": 27,
                    "campaign_name": "test",
                    "link": "https://symbolplatform.com/",
                    "markets": [{
                        "market_id": 63,
                        "trading_pair": "COINALPHA-HBOT",
                        "exchange_name": "kucoin",
                        "base_asset": "COINALPHA",
                        "base_asset_full_name": "coinalpha",
                        "quote_asset": "HBOT",
                        "quote_asset_full_name": "hbot"}]}]}

        mock_api.get(url, body=json.dumps(resp))
        mock_api.get(f"{parrot.PARROT_MINER_BASE_URL}markets", body=json.dumps(self.markets_get_resp))

        campaigns = asyncio.get_event_loop().run_until_complete(
            parrot.get_active_campaigns(
                exchange="kucoin",
                trading_pairs=["COINALPHA-HBOT"]))

        self.assertEqual(1, len(campaigns))
        campaign_summary: parrot.CampaignSummary = campaigns[63]
        self.assertEqual("COINALPHA-HBOT", campaign_summary.trading_pair)
        self.assertEqual("kucoin", campaign_summary.exchange_name)
        self.assertEqual(Decimal("0"), campaign_summary.spread_max)

    @aioresponses()
    def test_active_campaigns_are_filtered_by_exchange_name(self, mock_api):
        url = f"{parrot.PARROT_MINER_BASE_URL}campaigns"
        resp = {
            "status": "success",
            "campaigns": [{
                "id": 26,
                "campaign_name": "xym",
                "link": "https://symbolplatform.com/",
                "markets": [{
                    "market_id": 62,
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
                        "payout_asset": "XYM"}]}]}]}

        mock_api.get(url, body=json.dumps(resp))
        mock_api.get(f"{parrot.PARROT_MINER_BASE_URL}markets", body=json.dumps(self.markets_get_resp))

        campaigns = asyncio.get_event_loop().run_until_complete(
            parrot.get_active_campaigns(
                exchange="test_exchange",
                trading_pairs=["XYM-BTC"]))

        self.assertEqual(0, len(campaigns))

        mock_api.get(url, body=json.dumps(resp))
        mock_api.get(f"{parrot.PARROT_MINER_BASE_URL}markets", body=json.dumps(self.markets_get_resp))

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
