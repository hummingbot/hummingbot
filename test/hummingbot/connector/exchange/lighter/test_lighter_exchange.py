import asyncio
from decimal import Decimal
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import AsyncMock, MagicMock

from hummingbot.connector.exchange.lighter import lighter_constants as CONSTANTS
from hummingbot.connector.exchange.lighter.lighter_exchange import LighterExchange
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import OrderState


class MockSignerClient:
    ORDER_TIME_IN_FORCE_GOOD_TILL_TIME = 0
    ORDER_TIME_IN_FORCE_POST_ONLY = 1
    ORDER_TYPE_LIMIT = 0

    def __init__(self):
        self.create_order = AsyncMock(return_value=(None, {"code": 200}, None))
        self.create_market_order = AsyncMock(return_value=(None, {"code": 200}, None))
        self.cancel_order = AsyncMock(return_value=(None, {"code": 200}, None))


class LighterExchangeTests(TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.connector = LighterExchange.__new__(LighterExchange)
        self.connector._domain = "lighter"
        self.connector._trading_required = True
        self.connector._account_index = 724450
        self.connector._l1_address = "0xabc"
        self.connector._api_key_index = 2
        self.connector._api_private_key = "0xprivate"
        self.connector._signer_client = MockSignerClient()
        self.connector._tx_lock = asyncio.Lock()
        self.connector._markets_by_trading_pair = {
            "ETH-USDC": SimpleNamespace(
                market_id=2048,
                trading_pair="ETH-USDC",
                exchange_symbol="ETH/USDC",
                size_decimals=3,
                price_decimals=2,
                maker_fee=Decimal("0.0001"),
                taker_fee=Decimal("0.0004"),
                raw_info={"last_trade_price": "2500"},
            )
        }
        self.connector._markets_by_id = {2048: self.connector._markets_by_trading_pair["ETH-USDC"]}
        self.connector._markets_by_exchange_symbol = {"ETH/USDC": self.connector._markets_by_trading_pair["ETH-USDC"]}
        self.connector._current_timestamp = 123456.0
        self.connector.quantize_order_price = MagicMock(side_effect=lambda trading_pair, price: price)

    def test_extract_tx_code(self):
        self.assertEqual(200, self.connector._extract_tx_code({"code": "200"}))
        self.assertEqual(500, self.connector._extract_tx_code(SimpleNamespace(code=500)))
        self.assertIsNone(self.connector._extract_tx_code({"message": "ok"}))
        self.assertIsNone(self.connector._extract_tx_code({"code": "bad"}))
        self.assertIsNone(self.connector._extract_tx_code(SimpleNamespace(code="bad")))
        self.assertIsNone(self.connector._extract_tx_code(None))

    def test_is_tx_response_success(self):
        self.assertTrue(self.connector._is_tx_response_success({"code": 200}))
        self.assertFalse(self.connector._is_tx_response_success({"code": 500}))
        self.assertTrue(self.connector._is_tx_response_success({"status": "ok"}))

    def test_process_trade_events_accepts_list_payload(self):
        self.connector._trade_update_from_trade = MagicMock(return_value="trade-update")
        self.connector._order_tracker = SimpleNamespace(process_trade_update=MagicMock())

        self.connector._process_trade_events([{"trade_id": 1}])

        self.connector._trade_update_from_trade.assert_called_once_with({"trade_id": 1})
        self.connector._order_tracker.process_trade_update.assert_called_once_with("trade-update")

    def test_process_trade_events_accepts_market_grouped_payload(self):
        self.connector._trade_update_from_trade = MagicMock(return_value="trade-update")
        self.connector._order_tracker = SimpleNamespace(process_trade_update=MagicMock())

        self.connector._process_trade_events({"2048": [{"trade_id": 1}]})

        self.connector._trade_update_from_trade.assert_called_once_with({"trade_id": 1})
        self.connector._order_tracker.process_trade_update.assert_called_once_with("trade-update")

    def test_process_balance_events_replaces_balances(self):
        self.connector._account_balances = {"OLD": Decimal("1")}
        self.connector._account_available_balances = {"OLD": Decimal("1")}

        self.connector._process_balance_events(
            {
                "1": {
                    "symbol": "ETH",
                    "balance": "2",
                    "locked_balance": "0.5",
                },
                "3": {
                    "symbol": "USDC",
                    "balance": "100",
                    "locked_balance": "10",
                },
            }
        )

        self.assertEqual({"ETH", "USDC"}, set(self.connector._account_balances.keys()))
        self.assertEqual(Decimal("2"), self.connector._account_balances["ETH"])
        self.assertEqual(Decimal("1.5"), self.connector._account_available_balances["ETH"])
        self.assertEqual(Decimal("90"), self.connector._account_available_balances["USDC"])

    def test_account_lookup_params_defaults_to_l1_address(self):
        self.connector._account_index = None
        self.connector._l1_address = "0xabc"

        self.assertEqual(
            {"by": "l1_address", "value": "0xabc", "active_only": "true"},
            self.connector._account_lookup_params(),
        )

    def test_account_lookup_params_uses_index_override(self):
        self.connector._account_index = 12
        self.connector._l1_address = "0xabc"

        self.assertEqual(
            {"by": "index", "value": 12, "active_only": "true"},
            self.connector._account_lookup_params(),
        )

    def test_basic_properties_and_supported_order_types(self):
        self.assertEqual(724450, self.connector.account_index)
        self.assertEqual("lighter", self.connector.name)
        self.assertEqual("lighter", self.connector.domain)
        self.assertEqual(CONSTANTS.MAX_ORDER_ID_LEN, self.connector.client_order_id_max_length)
        self.assertEqual(CONSTANTS.BROKER_ID, self.connector.client_order_id_prefix)
        self.assertEqual(CONSTANTS.EXCHANGE_INFO_PATH_URL, self.connector.trading_rules_request_path)
        self.assertEqual(CONSTANTS.EXCHANGE_INFO_PATH_URL, self.connector.trading_pairs_request_path)
        self.assertEqual(CONSTANTS.PING_PATH_URL, self.connector.check_network_request_path)
        self.assertEqual([OrderType.LIMIT, OrderType.LIMIT_MAKER, OrderType.MARKET], self.connector.supported_order_types())
        self.assertTrue(self.connector.is_cancel_request_in_exchange_synchronous)
        self.assertTrue(self.connector.is_trading_required)
        self.assertIsNotNone(self.connector.authenticator)
        self.connector._signer_client = None
        self.assertIsNone(self.connector.authenticator)

    def test_network_and_rules_requests(self):
        self.connector._api_get = AsyncMock(return_value={"spot_order_book_details": []})

        asyncio.run(self.connector._make_network_check_request())
        rules = asyncio.run(self.connector._make_trading_rules_request())
        pairs = asyncio.run(self.connector._make_trading_pairs_request())

        self.assertEqual({"spot_order_book_details": []}, rules)
        self.assertEqual({"spot_order_book_details": []}, pairs)
        self.connector._api_get.assert_any_await(path_url=CONSTANTS.PING_PATH_URL)
        self.connector._api_get.assert_any_await(
            path_url=CONSTANTS.EXCHANGE_INFO_PATH_URL,
            params={"filter": "all"},
        )

    def test_get_all_pairs_prices(self):
        self.connector._api_get = AsyncMock(
            return_value={
                "spot_order_book_details": [
                    {
                        "symbol": "ETH/USDC",
                        "market_id": 2048,
                        "status": "active",
                        "market_config": {"hidden": False},
                        "min_base_amount": "0.001",
                        "min_quote_amount": "10",
                        "supported_size_decimals": 3,
                        "supported_price_decimals": 2,
                        "maker_fee": "0.0001",
                        "taker_fee": "0.0004",
                        "last_trade_price": "2500",
                    }
                ]
            }
        )

        prices = asyncio.run(self.connector.get_all_pairs_prices())

        self.assertEqual([{"symbol": "ETH/USDC", "price": "2500"}], prices)

    def test_create_data_sources(self):
        self.connector._trading_pairs = ["ETH-USDC"]
        self.connector._web_assistants_factory = SimpleNamespace()
        self.connector._auth = SimpleNamespace()

        order_book_data_source = self.connector._create_order_book_data_source()
        user_stream_data_source = self.connector._create_user_stream_data_source()

        self.assertEqual(self.connector, order_book_data_source._connector)
        self.assertEqual(self.connector, user_stream_data_source._connector)

    def test_status_and_order_update_delegates(self):
        self.connector._ensure_account_ready = AsyncMock()
        self.connector._update_trade_history = AsyncMock()
        self.connector._update_orders = AsyncMock()
        self.connector._update_balances = AsyncMock()
        self.connector._update_lost_orders = AsyncMock()

        asyncio.run(self.connector._status_polling_loop_fetch_updates())
        asyncio.run(self.connector._update_order_status())
        asyncio.run(self.connector._update_lost_orders_status())

        self.connector._ensure_account_ready.assert_awaited_once()
        self.connector._update_trade_history.assert_awaited_once()
        self.connector._update_balances.assert_awaited_once()
        self.connector._update_lost_orders.assert_awaited_once()

    def test_place_limit_maker_order(self):
        self.connector._ensure_account_ready = AsyncMock()
        self.connector._current_timestamp = 10

        order_id, timestamp = asyncio.run(
            self.connector._place_order(
                order_id="123",
                trading_pair="ETH-USDC",
                amount=Decimal("1.234"),
                trade_type=TradeType.BUY,
                order_type=OrderType.LIMIT_MAKER,
                price=Decimal("2500.12"),
            )
        )

        self.assertEqual("123", order_id)
        self.assertEqual(self.connector.current_timestamp, timestamp)
        self.connector._signer_client.create_order.assert_awaited_once()
        call_kwargs = self.connector._signer_client.create_order.await_args.kwargs
        self.assertEqual(2048, call_kwargs["market_index"])
        self.assertEqual(1234, call_kwargs["base_amount"])
        self.assertEqual(250012, call_kwargs["price"])
        self.assertEqual(self.connector._signer_client.ORDER_TIME_IN_FORCE_POST_ONLY, call_kwargs["time_in_force"])

    def test_place_market_order_and_errors(self):
        self.connector._ensure_account_ready = AsyncMock()
        self.connector._current_timestamp = 10

        asyncio.run(
            self.connector._place_order(
                order_id="123",
                trading_pair="ETH-USDC",
                amount=Decimal("1"),
                trade_type=TradeType.SELL,
                order_type=OrderType.MARKET,
                price=Decimal("2500"),
            )
        )

        self.connector._signer_client.create_market_order.assert_awaited_once()
        self.connector._signer_client.create_market_order.return_value = (None, {"code": 200}, "boom")
        with self.assertRaises(IOError):
            asyncio.run(
                self.connector._place_order(
                    order_id="123",
                    trading_pair="ETH-USDC",
                    amount=Decimal("1"),
                    trade_type=TradeType.SELL,
                    order_type=OrderType.MARKET,
                    price=Decimal("2500"),
                )
            )

    def test_place_cancel_success_and_order_missing(self):
        self.connector._ensure_account_ready = AsyncMock()
        tracked_order = SimpleNamespace(trading_pair="ETH-USDC")
        self.connector._find_order = AsyncMock(return_value={"order_id": "999"})

        result = asyncio.run(self.connector._place_cancel("cid", tracked_order))

        self.assertTrue(result)
        self.connector._signer_client.cancel_order.assert_awaited_once_with(market_index=2048, order_index=999)

        self.connector._find_order = AsyncMock(return_value=None)
        self.connector._order_tracker = SimpleNamespace(process_order_not_found=AsyncMock())
        with self.assertRaises(IOError):
            asyncio.run(self.connector._place_cancel("cid", tracked_order))
        self.connector._order_tracker.process_order_not_found.assert_awaited_once_with("cid")

    def test_update_trade_history_processes_trade_update(self):
        tracked_order = SimpleNamespace(trading_pair="ETH-USDC")
        self.connector._order_tracker = SimpleNamespace(
            all_fillable_orders={"cid": tracked_order},
            process_trade_update=MagicMock(),
        )
        self.connector._ensure_account_ready = AsyncMock()
        self.connector._api_get = AsyncMock(return_value={"trades": [{"trade_id": "t1"}]})
        self.connector._trade_update_from_trade = MagicMock(return_value="trade-update")

        asyncio.run(self.connector._update_trade_history())

        self.connector._api_get.assert_awaited_once()
        self.connector._order_tracker.process_trade_update.assert_called_once_with("trade-update")

    def test_request_order_status(self):
        tracked_order = SimpleNamespace(client_order_id="cid", trading_pair="ETH-USDC")
        self.connector._find_order = AsyncMock(
            return_value={
                "status": "open",
                "client_order_id": "cid",
                "order_id": "999",
                "transaction_time": "1000000",
            }
        )

        order_update = asyncio.run(self.connector._request_order_status(tracked_order))

        self.assertEqual("cid", order_update.client_order_id)
        self.assertEqual("999", order_update.exchange_order_id)
        self.assertEqual(OrderState.OPEN, order_update.new_state)

        self.connector._find_order = AsyncMock(return_value=None)
        with self.assertRaises(IOError):
            asyncio.run(self.connector._request_order_status(tracked_order))

    def test_update_balances_removes_stale_assets(self):
        self.connector._account_balances = {"OLD": Decimal("1")}
        self.connector._account_available_balances = {"OLD": Decimal("1")}
        self.connector._api_get = AsyncMock(
            return_value={
                "accounts": [
                    {
                        "index": 724450,
                        "assets": [
                            {"symbol": "ETH", "balance": "2", "locked_balance": "0.5"},
                        ],
                    }
                ]
            }
        )

        asyncio.run(self.connector._update_balances())

        self.assertEqual({"ETH"}, set(self.connector._account_balances))
        self.assertEqual(Decimal("1.5"), self.connector._account_available_balances["ETH"])

    def test_get_last_traded_price(self):
        self.connector._api_get = AsyncMock(
            return_value={
                "spot_order_book_details": [
                    {
                        "symbol": "ETH/USDC",
                        "market_id": 2048,
                        "status": "active",
                        "market_config": {"hidden": False},
                        "min_base_amount": "0.001",
                        "min_quote_amount": "10",
                        "supported_size_decimals": 3,
                        "supported_price_decimals": 2,
                        "maker_fee": "0.0001",
                        "taker_fee": "0.0004",
                        "last_trade_price": "2501",
                    }
                ]
            }
        )

        price = asyncio.run(self.connector._get_last_traded_price("ETH-USDC"))

        self.assertEqual(2501, price)

    def test_format_trading_rules_and_market_accessors(self):
        exchange_info = {
            "spot_order_book_details": [
                {
                    "symbol": "ETH/USDC",
                    "market_id": 2048,
                    "status": "active",
                    "market_config": {"hidden": False},
                    "min_base_amount": "0.001",
                    "min_quote_amount": "10",
                    "supported_size_decimals": 3,
                    "supported_price_decimals": 2,
                    "maker_fee": "0.0001",
                    "taker_fee": "0.0004",
                }
            ]
        }

        rules = asyncio.run(self.connector._format_trading_rules(exchange_info))

        self.assertEqual(1, len(rules))
        self.assertEqual("ETH-USDC", self.connector.market_info_for_trading_pair("ETH-USDC").trading_pair)
        self.assertEqual("ETH-USDC", self.connector.market_info_for_market_id(2048).trading_pair)

    def test_effective_market_order_price_uses_mid_price(self):
        self.connector.get_mid_price = MagicMock(return_value=Decimal("100"))
        self.connector.quantize_order_price = MagicMock(side_effect=lambda trading_pair, price: price)

        buy_price = self.connector._effective_order_price(
            trading_pair="ETH-USDC",
            trade_type=TradeType.BUY,
            order_type=OrderType.MARKET,
            price=Decimal("NaN"),
        )
        sell_price = self.connector._effective_order_price(
            trading_pair="ETH-USDC",
            trade_type=TradeType.SELL,
            order_type=OrderType.MARKET,
            price=Decimal("NaN"),
        )
        limit_price = self.connector._effective_order_price(
            trading_pair="ETH-USDC",
            trade_type=TradeType.SELL,
            order_type=OrderType.LIMIT,
            price=Decimal("99"),
        )

        self.assertEqual(Decimal("105.00"), buy_price)
        self.assertEqual(Decimal("95.00"), sell_price)
        self.assertEqual(Decimal("99"), limit_price)

    def test_create_signer_client_validates_required_fields(self):
        self.connector._account_index = None

        with self.assertRaises(ValueError):
            self.connector._create_signer_client()

    def test_find_order_checks_active_then_inactive(self):
        tracked_order = SimpleNamespace(client_order_id="cid", exchange_order_id=None, trading_pair="ETH-USDC")
        self.connector._ensure_account_ready = AsyncMock()
        self.connector._api_get = AsyncMock(
            side_effect=[
                {"orders": []},
                {"orders": [{"client_order_id": "cid", "order_id": "999"}]},
            ]
        )

        order = asyncio.run(self.connector._find_order(tracked_order, include_inactive=True))

        self.assertEqual("999", order["order_id"])
        self.assertEqual(2, self.connector._api_get.await_count)

    def test_ensure_account_ready_resolves_account_and_rebuilds_auth(self):
        self.connector._account_index = None
        self.connector._signer_client = None
        self.connector._api_get = AsyncMock(return_value={"sub_accounts": [{"index": 724450, "l1_address": "0xabc"}]})
        self.connector._create_signer_client = MagicMock(return_value="signer")
        self.connector._create_web_assistants_factory = MagicMock(return_value="factory")
        self.connector._create_user_stream_tracker = MagicMock(return_value="tracker")

        asyncio.run(self.connector._ensure_account_ready())

        self.assertEqual(724450, self.connector._account_index)
        self.assertEqual("signer", self.connector._signer_client)
        self.assertEqual("factory", self.connector._web_assistants_factory)
        self.assertEqual("tracker", self.connector._user_stream_tracker)

    def test_match_order_by_client_or_exchange_id(self):
        tracked_order = SimpleNamespace(client_order_id="cid", exchange_order_id="999")

        self.assertEqual(
            {"client_order_id": "cid"},
            self.connector._match_order(tracked_order, [{"client_order_id": "cid"}]),
        )
        self.assertEqual(
            {"order_id": "999"},
            self.connector._match_order(tracked_order, [{"order_id": "999"}]),
        )
        self.assertIsNone(self.connector._match_order(tracked_order, [{"order_id": "888"}]))

    def test_process_order_events_filters_invalid_payloads(self):
        tracked_order = SimpleNamespace(trading_pair="ETH-USDC")
        self.connector._order_tracker = SimpleNamespace(
            all_updatable_orders={"cid": tracked_order},
            process_order_update=MagicMock(),
        )

        self.connector._process_order_events(
            {
                "bad-group": "not-list",
                "market": [
                    {},
                    {"client_order_id": "unknown", "status": "open"},
                    {
                        "client_order_id": "cid",
                        "order_id": "999",
                        "status": "open",
                        "transaction_time": "1000000",
                    },
                ],
            }
        )

        self.connector._order_tracker.process_order_update.assert_called_once()

    def test_trade_update_from_trade(self):
        tracked_order = SimpleNamespace(client_order_id="cid", trading_pair="ETH-USDC")
        self.connector._order_tracker = SimpleNamespace(
            all_fillable_orders={"cid": tracked_order},
            all_fillable_orders_by_exchange_order_id={},
        )
        self.connector.trade_fee_schema = MagicMock(return_value=MagicMock())
        trade = {
            "ask_account_id": 724450,
            "bid_account_id": 1,
            "ask_client_id_str": "cid",
            "ask_id_str": "999",
            "is_maker_ask": True,
            "market_id": 2048,
            "trade_id": "t1",
            "price": "2500",
            "size": "0.1",
            "transaction_time": "1000000",
        }

        update = self.connector._trade_update_from_trade(trade)

        self.assertEqual("cid", update.client_order_id)
        self.assertEqual(Decimal("250"), update.fill_quote_amount)
