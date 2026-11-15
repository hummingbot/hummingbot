import asyncio
import tempfile
from dataclasses import replace
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from test.hummingbot.connector.derivative.neutronx_perpetual.fixtures import (
    NETWORK,
    chain_order,
    chain_position,
    fill_json,
    market,
    order_json,
)
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import AsyncMock, patch

from neutronx_sdk.indexer import FillV1, OrderbookV1, OrderV1, TickerV1, TradeV1
from neutronx_sdk.orders import Side

from hummingbot.client.config.config_crypt import ETHKeyFileSecretManger
from hummingbot.client.config.config_helpers import (
    ClientConfigAdapter,
    load_connector_config_map_from_file,
    save_to_yml,
)
from hummingbot.client.config.security import Security
from hummingbot.client.settings import AllConnectorSettings
from hummingbot.connector.derivative.neutronx_perpetual import (
    neutronx_perpetual_constants as CONSTANTS,
    neutronx_perpetual_utils as utils,
    neutronx_perpetual_web_utils as web_utils,
)
from hummingbot.connector.derivative.neutronx_perpetual.data_sources import translators
from hummingbot.core.data_type.common import OrderType, PositionAction, PositionSide, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState
from hummingbot.core.data_type.order_book_message import OrderBookMessageType
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest


class TranslatorsTests(TestCase):
    def test_pair_mapping(self):
        markets = [market(), market("ETH/USDC"), market("OLD/USDC", "DELISTED")]
        self.assertEqual("BTC-USDC", translators.to_trading_pair("BTC/USDC"))
        self.assertEqual("BTC/USDC", translators.to_exchange_pair("BTC-USDC"))
        self.assertEqual({"BTC/USDC": "BTC-USDC", "ETH/USDC": "ETH-USDC"}, dict(translators.symbol_map(markets)))
        self.assertEqual("OLD-USDC", translators.compact_lookup(markets)["OLDUSDC"])
        self.assertIs(Side.SELL, translators.to_side(TradeType.SELL))

    def test_trading_rule(self):
        rule = translators.trading_rule(market(tick="0.5", min_quantity="0.001"), Decimal(10))
        self.assertEqual(Decimal("0.5"), rule.min_price_increment)
        self.assertEqual(CONSTANTS.QUANTITY_INCREMENT, rule.min_base_amount_increment)
        self.assertEqual(Decimal("0.001"), rule.min_order_size)
        self.assertEqual(Decimal(10), rule.min_notional_size)
        self.assertEqual("USDC", rule.buy_order_collateral_token)
        no_tick = translators.trading_rule(market(tick="0", min_quantity="10"), Decimal(10))
        self.assertEqual(CONSTANTS.DEFAULT_PRICE_INCREMENT, no_tick.min_price_increment)
        self.assertEqual(CONSTANTS.QUANTITY_INCREMENT, no_tick.min_base_amount_increment)

    def test_order_states(self):
        self.assertIs(OrderState.CANCELED, translators.order_state("EXPIRED"))
        self.assertIs(OrderState.FAILED, translators.order_state("rejected"))
        self.assertIs(OrderState.PARTIALLY_FILLED, translators.order_state("PARTIALLY_FILLED"))
        self.assertIs(OrderState.OPEN, translators.order_state("SOMETHING_NEW"))

    @staticmethod
    def _in_flight(client_order_id: str, amount: str = "0.01") -> InFlightOrder:
        return InFlightOrder(
            client_order_id=client_order_id,
            trading_pair="BTC-USDC",
            order_type=OrderType.LIMIT,
            trade_type=TradeType.SELL,
            amount=Decimal(amount),
            creation_timestamp=1,
            price=Decimal(65000),
        )

    def test_order_updates(self):
        order = OrderV1.from_json(order_json(7, "FILLED", "0.01"))
        indexed = translators.order_update(order, self._in_flight("101"), order.updated_at.timestamp())
        self.assertEqual(("7", "101", OrderState.FILLED), (indexed.exchange_order_id, indexed.client_order_id, indexed.new_state))
        chained = translators.order_update(chain_order(8, "PARTIALLY_FILLED"), self._in_flight("102"), 5.0)
        self.assertEqual((OrderState.PARTIALLY_FILLED, 5.0), (chained.new_state, chained.update_timestamp))

    def test_reduce_only_order_shrunk_by_the_chain_is_cancelled_after_its_fills(self):
        shrunk = chain_order(9, "FILLED", quantity="0.004", filled="0.004")
        update = translators.order_update(shrunk, self._in_flight("103", "0.01"), 5.0)
        self.assertIs(OrderState.CANCELED, update.new_state)
        whole = translators.order_update(chain_order(10, "FILLED", filled="0.01"), self._in_flight("104"), 5.0)
        self.assertIs(OrderState.FILLED, whole.new_state)
        dust = translators.settled_state("FILLED", Decimal("0.009999999999"), Decimal("0.01"))
        self.assertIs(OrderState.FILLED, dust)
        self.assertIs(OrderState.CANCELED, translators.settled_state("CANCELLED", Decimal("0.01"), Decimal("0.01")))

    def test_filled_amount_of_a_finished_order(self):
        self.assertEqual(Decimal("0.01"), translators.filled_amount("FILLED", Decimal("0.01"), Decimal(0)))
        self.assertEqual(Decimal("0.003"), translators.filled_amount("CANCELLED", Decimal("0.01"), Decimal("0.003")))
        self.assertEqual(Decimal("0.003"), translators.filled_amount("PARTIALLY_FILLED", Decimal("0.01"), Decimal("0.003")))

    def test_trade_update_fee_and_role(self):
        order = InFlightOrder(
            client_order_id="101",
            trading_pair="BTC-USDC",
            order_type=OrderType.LIMIT_MAKER,
            trade_type=TradeType.BUY,
            amount=Decimal("0.01"),
            creation_timestamp=1,
            price=Decimal(65000),
            exchange_order_id="7",
            position=PositionAction.OPEN,
        )
        update = translators.trade_update(FillV1.from_json(fill_json("101:1", 7)), order, utils.DEFAULT_FEES)
        self.assertFalse(update.is_taker)
        self.assertEqual(Decimal(650), update.fill_quote_amount)
        self.assertEqual(Decimal("0.325"), update.fee.flat_fees[0].amount)
        taker = translators.trade_update(FillV1.from_json(fill_json("101:2", 7, role="taker")), order, utils.DEFAULT_FEES)
        self.assertTrue(taker.is_taker)

    def test_positions_are_signed(self):
        short = translators.to_position(chain_position(side="SHORT"), "BTC-USDC")
        self.assertIs(PositionSide.SHORT, short.position_side)
        self.assertEqual(Decimal("-0.2"), short.amount)
        long = translators.to_position(chain_position(side="LONG"), "BTC-USDC")
        self.assertEqual(Decimal("0.2"), long.amount)

    def test_funding_from_ticker(self):
        ticker = TickerV1.from_json(
            {"pair": "BTCUSDC", "mark_price": "65000", "funding_rate": "0.0001", "next_funding_at": "2026-11-10T13:00:00+00:00"}
        )
        info = translators.funding_info(ticker, "BTC-USDC")
        self.assertEqual(Decimal(65000), info.mark_price)
        self.assertEqual(int(datetime(2026, 11, 10, 13, tzinfo=timezone.utc).timestamp()), info.next_funding_utc_timestamp)
        update = translators.funding_info_update(TickerV1.from_json({"pair": "BTCUSDC"}), "BTC-USDC")
        self.assertIsNone(update.rate)
        self.assertIsNone(update.next_funding_utc_timestamp)
        empty = translators.funding_info(TickerV1.from_json({"pair": "BTCUSDC", "last_price": "1"}), "BTC-USDC")
        self.assertEqual((Decimal(1), Decimal(0), 0), (empty.mark_price, empty.rate, empty.next_funding_utc_timestamp))

    def test_order_book_and_trade_messages(self):
        book = OrderbookV1.from_json(
            {"pair": "BTCUSDC", "bids": [{"price": "1", "quantity": "2"}], "asks": [{"price": "3", "quantity": "4"}]}
        )
        snapshot = translators.snapshot_message(book, "BTC-USDC", 7, 0.007)
        self.assertIs(OrderBookMessageType.SNAPSHOT, snapshot.type)
        self.assertEqual(7, snapshot.update_id)
        self.assertEqual(1.0, snapshot.bids[0].price)
        trade_json = {"id": "1:1", "pair": "BTCUSDC", "price": "100", "quantity": "1", "block_height": 1,
                      "time": "2026-11-10T12:00:00Z"}
        trade = TradeV1.from_json(trade_json)
        self.assertIs(TradeType.BUY, translators.trade_side(trade, Decimal(99)))
        self.assertIs(TradeType.SELL, translators.trade_side(trade, Decimal(101)))
        self.assertIs(TradeType.BUY, translators.trade_side(trade, None))
        sold = TradeV1.from_json({**trade_json, "taker_side": "SELL"})
        message = translators.trade_message(sold, "BTC-USDC", Decimal(1))
        self.assertEqual(float(TradeType.SELL.value), message.content["trade_type"])
        self.assertGreater(translators.next_update_id(10), 10)
        self.assertEqual(10**15 + 1, translators.next_update_id(10**15))
        self.assertTrue(translators.reduce_only(PositionAction.CLOSE))


class UtilsTests(TestCase):
    def test_config_maps_share_one_shape(self):
        mainnet = set(utils.NeutronxPerpetualConfigMap.model_fields)
        testnet = set(utils.NeutronxPerpetualTestnetConfigMap.model_fields)
        self.assertIn("neutronx_perpetual_private_key", mainnet)
        self.assertEqual({f.replace("neutronx_perpetual_", "neutronx_perpetual_testnet_", 1) for f in mainnet if f.startswith("neutronx")},
                         {f for f in testnet if f.startswith("neutronx")})
        self.assertEqual("neutronx_perpetual", utils.NeutronxPerpetualConfigMap.model_config["title"])
        self.assertTrue(utils.NeutronxPerpetualConfigMap.model_fields["neutronx_perpetual_private_key"].json_schema_extra["is_secure"])
        self.assertEqual(0, utils.KEYS.neutronx_perpetual_agent_key_id)
        self.assertEqual("", utils.KEYS.neutronx_perpetual_indexer_api_key)
        api_key_field = utils.NeutronxPerpetualConfigMap.model_fields["neutronx_perpetual_indexer_api_key"]
        self.assertFalse(api_key_field.is_required())
        self.assertTrue(api_key_field.json_schema_extra["is_secure"])

    def test_config_without_indexer_api_key_survives_encryption(self):
        manager = ETHKeyFileSecretManger("connector-tests")
        with tempfile.TemporaryDirectory() as directory, patch.object(Security, "secrets_manager", manager):
            path = Path(directory) / f"{CONSTANTS.TESTNET_DOMAIN}.yml"
            adapter = ClientConfigAdapter(AllConnectorSettings.get_connector_config_keys(CONSTANTS.TESTNET_DOMAIN))
            adapter.neutronx_perpetual_testnet_account_address = "neutronx1a"
            adapter.neutronx_perpetual_testnet_private_key = "ab" * 32
            save_to_yml(path, adapter)
            self.assertNotIn("ab" * 32, path.read_text())
            loaded = load_connector_config_map_from_file(path)
        self.assertEqual("ab" * 32, loaded.neutronx_perpetual_testnet_private_key.get_secret_value())
        self.assertEqual("", loaded.neutronx_perpetual_testnet_indexer_api_key.get_secret_value())

    def test_hummingbot_discovers_both_domains(self):
        settings = AllConnectorSettings.create_connector_settings()
        self.assertIn(CONSTANTS.DOMAIN, settings)
        self.assertIn(CONSTANTS.TESTNET_DOMAIN, settings)
        params = settings[CONSTANTS.TESTNET_DOMAIN].conn_init_parameters(
            api_keys={"neutronx_perpetual_testnet_account_address": "neutronx1a"}
        )
        self.assertEqual("neutronx1a", params["neutronx_perpetual_account_address"])
        self.assertEqual(CONSTANTS.TESTNET_DOMAIN, params["domain"])

    def test_web_utils_need_configured_indexer(self):
        self.assertEqual("https://indexer.test/v1/status", web_utils.indexer_rest_url(NETWORK, "/status"))
        self.assertEqual("wss://indexer.test/v1/ws", web_utils.indexer_ws_url(NETWORK))
        bare = replace(NETWORK, indexer_url=None, indexer_ws_url=None)
        with self.assertRaises(ValueError):
            web_utils.indexer_rest_url(bare, "/status")
        with self.assertRaises(ValueError):
            web_utils.indexer_ws_url(bare)
        self.assertEqual("https://api.neutronx.com/v1/status", web_utils.public_rest_url("/status"))
        anonymous, keyed = web_utils.rate_limits(), web_utils.rate_limits("nx_key")
        self.assertEqual([114, 60], [limit.limit for limit in anonymous])
        self.assertEqual([594, 60], [limit.limit for limit in keyed])
        self.assertEqual(CONSTANTS.INDEXER_STATUS_LIMIT_ID, anonymous[1].limit_id)
        self.assertEqual({}, web_utils.indexer_headers(None))
        self.assertEqual({"X-API-Key": "nx_key"}, web_utils.indexer_headers("nx_key"))
        self.assertEqual("https://api.neutronx.com/v1", web_utils.network_for(CONSTANTS.DOMAIN).indexer_url)
        self.assertEqual("wss://indexer-test.neutronchain.io/v1/ws", web_utils.indexer_ws_url(web_utils.network_for(CONSTANTS.TESTNET_DOMAIN)))

    def test_api_key_pre_processor_keeps_headers(self):
        request = RESTRequest(method=RESTMethod.GET, url="https://x", headers={"Accept": "application/json"})
        headers = asyncio.run(web_utils.IndexerApiKeyPreProcessor("nx_key").pre_process(request)).headers
        self.assertEqual({"Accept": "application/json", "X-API-Key": "nx_key"}, headers)
        plain, keyed = web_utils.build_api_factory(), web_utils.build_api_factory(api_key="nx_key")
        self.assertEqual((1, 2), (len(plain._rest_pre_processors), len(keyed._rest_pre_processors)))
        self.assertEqual(1, len(plain._rest_post_processors))

    def test_rate_limit_backoff_grows_and_honours_retry_after(self):
        clock = [0.0]
        with patch.object(web_utils.time, "monotonic", side_effect=lambda: clock[0]):
            backoff = web_utils.IndexerBackoff()
            delays = []
            for retry_after in (None, None, None, 10, None, None, None, None, None, None, 90):
                delays.append(backoff.hit(retry_after))
                clock[0] += 0.1
                self.assertEqual(delays[-1], backoff.hit(None) if retry_after is None else delays[-1])
                clock[0] += delays[-1]
            self.assertEqual([1.0, 2.0, 4.0, 10.0, 16.0, 30.0, 30.0, 30.0, 30.0, 30.0, 90.0], delays)
            backoff.clear()
            clock[0] += 100
            self.assertEqual(1.0, backoff.hit(None))
        self.assertEqual((3.0, None, None), (web_utils.retry_after({"Retry-After": "3"}), web_utils.retry_after(None),
                                             web_utils.retry_after({"Retry-After": "soon"})))

    def test_rate_limited_response_pauses_every_request_but_the_network_check(self):
        backoff = web_utils.IndexerBackoff()
        post = web_utils.IndexerBackoffPostProcessor(backoff)
        pre = web_utils.IndexerBackoffPreProcessor(backoff)
        limited = SimpleNamespace(status=429, headers={"Retry-After": "2"}, url="https://x/fills", text=AsyncMock())
        with self.assertRaises(web_utils.IndexerRateLimitedError) as raised:
            asyncio.run(post.post_process(limited))
        self.assertEqual(2.0, raised.exception.retry_after)
        self.assertIsInstance(raised.exception, IOError)
        limited.text.assert_awaited_once()
        request = RESTRequest(method=RESTMethod.GET, url="https://x/fills", throttler_limit_id=CONSTANTS.INDEXER_REST_LIMIT_ID)
        status = RESTRequest(method=RESTMethod.GET, url="https://x/status", throttler_limit_id=CONSTANTS.INDEXER_STATUS_LIMIT_ID)
        with patch("asyncio.sleep", new=AsyncMock()) as sleep:
            asyncio.run(pre.pre_process(status))
            sleep.assert_not_awaited()
            asyncio.run(pre.pre_process(request))
            sleep.assert_awaited_once()
        ok = SimpleNamespace(status=200, headers={}, url="https://x/fills")
        self.assertIs(ok, asyncio.run(post.post_process(ok)))
        self.assertEqual(1.0, backoff.hit(None))

    def test_shared_request_runs_one_fetch_for_concurrent_callers(self):
        calls = []

        async def fetch():
            calls.append(1)
            await asyncio.sleep(0)
            if len(calls) == 3:
                raise IOError("indexer down")
            return len(calls)

        async def scenario():
            shared = web_utils.SharedRequest(fetch, ttl=60)
            first = await asyncio.gather(shared.get(), shared.get(), shared.get())
            cached = await shared.get()
            fresh = web_utils.SharedRequest(fetch)
            second = await fresh.get()
            with self.assertRaises(IOError):
                await fresh.get()
            return first, cached, second, await fresh.get()

        self.assertEqual(([1, 1, 1], 1, 2, 4), asyncio.run(scenario()))
