import asyncio
import functools
import json
import re
from decimal import Decimal
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from typing import Any, Callable, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pandas as pd
from aioresponses.core import aioresponses
from bidict import bidict

import hummingbot.connector.derivative.binance_perpetual.binance_perpetual_constants as CONSTANTS
import hummingbot.connector.derivative.binance_perpetual.binance_perpetual_web_utils as web_utils
from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.connector.derivative.binance_perpetual.binance_perpetual_api_order_book_data_source import (
    BinancePerpetualAPIOrderBookDataSource,
)
from hummingbot.connector.derivative.binance_perpetual.binance_perpetual_derivative import BinancePerpetualDerivative
from hummingbot.connector.test_support.network_mocking_assistant import NetworkMockingAssistant
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.connector.utils import get_new_client_order_id
from hummingbot.core.data_type.common import OrderType, PositionAction, PositionMode, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState
from hummingbot.core.data_type.limit_order import LimitOrder
from hummingbot.core.data_type.trade_fee import TokenAmount
from hummingbot.core.event.event_logger import EventLogger
from hummingbot.core.event.events import MarketEvent, OrderFilledEvent


class BinancePerpetualDerivativeUnitTest(IsolatedAsyncioWrapperTestCase):
    # the level is required to receive logs from the data source logger
    level = 0

    start_timestamp: float = pd.Timestamp("2021-01-01", tz="UTC").timestamp()

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.base_asset = "COINALPHA"
        cls.quote_asset = "HBOT"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.symbol = f"{cls.base_asset}{cls.quote_asset}"
        cls.domain = CONSTANTS.TESTNET_DOMAIN
        cls.listen_key = "TEST_LISTEN_KEY"

    def setUp(self) -> None:
        super().setUp()
        self.log_records = []

        self.ws_sent_messages = []
        self.ws_incoming_messages = asyncio.Queue()
        self.resume_test_event = asyncio.Event()
        self.client_config_map = ClientConfigAdapter(ClientConfigMap())

        self.exchange = BinancePerpetualDerivative(
            client_config_map=self.client_config_map,
            binance_perpetual_api_key="testAPIKey",
            binance_perpetual_api_secret="testSecret",
            trading_pairs=[self.trading_pair],
            domain=self.domain,
        )

        if hasattr(self.exchange, "_time_synchronizer"):
            self.exchange._time_synchronizer.add_time_offset_ms_sample(0)
            self.exchange._time_synchronizer.logger().setLevel(1)
            self.exchange._time_synchronizer.logger().addHandler(self)

        BinancePerpetualAPIOrderBookDataSource._trading_pair_symbol_map = {
            self.domain: bidict({self.symbol: self.trading_pair})
        }

        self.exchange._set_current_timestamp(1640780000)
        self.exchange.logger().setLevel(1)
        self.exchange.logger().addHandler(self)
        self.exchange._order_tracker.logger().setLevel(1)
        self.exchange._order_tracker.logger().addHandler(self)
        self.mocking_assistant = NetworkMockingAssistant(self.local_event_loop)
        self.test_task: Optional[asyncio.Task] = None
        self.resume_test_event = asyncio.Event()
        self._initialize_event_loggers()

    @property
    def all_symbols_url(self):
        url = web_utils.public_rest_url(path_url=CONSTANTS.EXCHANGE_INFO_URL)
        return url

    @property
    def latest_prices_url(self):
        url = web_utils.public_rest_url(
            path_url=CONSTANTS.TICKER_PRICE_CHANGE_URL
        )
        url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        return url

    @property
    def network_status_url(self):
        url = web_utils.public_rest_url(path_url=CONSTANTS.PING_URL)
        return url

    @property
    def trading_rules_url(self):
        url = web_utils.public_rest_url(path_url=CONSTANTS.EXCHANGE_INFO_URL)
        return url

    @property
    def balance_url(self):
        url = web_utils.private_rest_url(path_url=CONSTANTS.ACCOUNT_INFO_URL)
        return url

    @property
    def funding_info_url(self):
        url = web_utils.public_rest_url(
            path_url=CONSTANTS.TICKER_PRICE_CHANGE_URL
        )
        url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        return url

    @property
    def funding_payment_url(self):
        url = web_utils.private_rest_url(
            path_url=CONSTANTS.GET_INCOME_HISTORY_URL
        )
        url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        return url

    def tearDown(self) -> None:
        self.test_task and self.test_task.cancel()
        BinancePerpetualAPIOrderBookDataSource._trading_pair_symbol_map = {}
        super().tearDown()

    def _initialize_event_loggers(self):
        self.buy_order_completed_logger = EventLogger()
        self.sell_order_completed_logger = EventLogger()
        self.order_cancelled_logger = EventLogger()
        self.order_filled_logger = EventLogger()
        self.funding_payment_completed_logger = EventLogger()

        events_and_loggers = [
            (MarketEvent.BuyOrderCompleted, self.buy_order_completed_logger),
            (MarketEvent.SellOrderCompleted, self.sell_order_completed_logger),
            (MarketEvent.OrderCancelled, self.order_cancelled_logger),
            (MarketEvent.OrderFilled, self.order_filled_logger),
            (MarketEvent.FundingPaymentCompleted, self.funding_payment_completed_logger)]

        for event, logger in events_and_loggers:
            self.exchange.add_listener(event, logger)

    def handle(self, record):
        self.log_records.append(record)

    def _is_logged(self, log_level: str, message: str) -> bool:
        return any(record.levelname == log_level and record.getMessage() == message for record in self.log_records)

    def _create_exception_and_unlock_test_with_event(self, exception):
        self.resume_test_event.set()
        raise exception

    def _return_calculation_and_set_done_event(self, calculation: Callable, *args, **kwargs):
        if self.resume_test_event.is_set():
            raise asyncio.CancelledError
        self.resume_test_event.set()
        return calculation(*args, **kwargs)

    def _get_position_risk_api_endpoint_single_position_list(self) -> List[Dict[str, Any]]:
        positions = [
            {
                "symbol": self.symbol,
                "positionAmt": "1",
                "entryPrice": "10",
                "markPrice": "11",
                "unRealizedProfit": "1",
                "liquidationPrice": "100",
                "leverage": "1",
                "maxNotionalValue": "9",
                "marginType": "cross",
                "isolatedMargin": "0",
                "isAutoAddMargin": "false",
                "positionSide": "BOTH",
                "notional": "11",
                "isolatedWallet": "0",
                "updateTime": int(self.start_timestamp),
            }
        ]
        return positions

    def _get_wrong_symbol_position_risk_api_endpoint_single_position_list(self) -> List[Dict[str, Any]]:
        positions = [
            {
                "symbol": f"{self.symbol}_230331",
                "positionAmt": "1",
                "entryPrice": "10",
                "markPrice": "11",
                "unRealizedProfit": "1",
                "liquidationPrice": "100",
                "leverage": "1",
                "maxNotionalValue": "9",
                "marginType": "cross",
                "isolatedMargin": "0",
                "isAutoAddMargin": "false",
                "positionSide": "BOTH",
                "notional": "11",
                "isolatedWallet": "0",
                "updateTime": int(self.start_timestamp),
            }
        ]
        return positions

    def _get_account_update_ws_event_single_position_dict(self) -> Dict[str, Any]:
        account_update = {
            "e": "ACCOUNT_UPDATE",
            "E": 1564745798939,
            "T": 1564745798938,
            "a": {
                "m": "POSITION",
                "B": [
                    {"a": "USDT", "wb": "122624.12345678", "cw": "100.12345678", "bc": "50.12345678"},
                ],
                "P": [
                    {
                        "s": self.symbol,
                        "pa": "1",
                        "ep": "10",
                        "cr": "200",
                        "up": "1",
                        "mt": "cross",
                        "iw": "0.00000000",
                        "ps": "BOTH",
                    },
                ],
            },
        }
        return account_update

    def _get_wrong_symbol_account_update_ws_event_single_position_dict(self) -> Dict[str, Any]:
        account_update = {
            "e": "ACCOUNT_UPDATE",
            "E": 1564745798939,
            "T": 1564745798938,
            "a": {
                "m": "POSITION",
                "B": [
                    {"a": "USDT", "wb": "122624.12345678", "cw": "100.12345678", "bc": "50.12345678"},
                ],
                "P": [
                    {
                        "s": f"{self.symbol}_230331",
                        "pa": "1",
                        "ep": "10",
                        "cr": "200",
                        "up": "1",
                        "mt": "cross",
                        "iw": "0.00000000",
                        "ps": "BOTH",
                    },
                ],
            },
        }
        return account_update

    def _get_income_history_dict(self) -> List:
        income_history = [{
            "income": 1,
            "symbol": self.symbol,
            "time": self.start_timestamp,
        }]
        return income_history

    def _get_funding_info_dict(self) -> Dict[str, Any]:
        funding_info = {
            "indexPrice": 1000,
            "markPrice": 1001,
            "nextFundingTime": self.start_timestamp + 8 * 60 * 60,
            "lastFundingRate": 1010
        }
        return funding_info

    def _get_trading_pair_symbol_map(self) -> Dict[str, str]:
        trading_pair_symbol_map = {self.symbol: f"{self.base_asset}-{self.quote_asset}"}
        return trading_pair_symbol_map

    def _get_exchange_info_mock_response(
            self,
            margin_asset: str = "HBOT",
            min_order_size: float = 1,
            min_price_increment: float = 2,
            min_base_amount_increment: float = 3,
            min_notional_size: float = 4,
    ) -> Dict[str, Any]:
        mocked_exchange_info = {  # irrelevant fields removed
            "symbols": [
                {
                    "symbol": self.symbol,
                    "pair": self.symbol,
                    "contractType": "PERPETUAL",
                    "baseAsset": self.base_asset,
                    "quoteAsset": self.quote_asset,
                    "marginAsset": margin_asset,
                    "status": "TRADING",
                    "filters": [
                        {
                            "filterType": "PRICE_FILTER",
                            "maxPrice": "300",
                            "minPrice": "0.0001",
                            "tickSize": str(min_price_increment),
                        },
                        {
                            "filterType": "LOT_SIZE",
                            "maxQty": "10000000",
                            "minQty": str(min_order_size),
                            "stepSize": str(min_base_amount_increment),
                        },
                        {
                            "filterType": "MIN_NOTIONAL",
                            "notional": str(min_notional_size),
                        },
                    ],
                }
            ],
        }

        return mocked_exchange_info

    def _get_exchange_info_error_mock_response(
            self,
            margin_asset: str = "HBOT",
            min_order_size: float = 1,
            min_price_increment: float = 2,
            min_base_amount_increment: float = 3,
            min_notional_size: float = 4,
    ) -> Dict[str, Any]:
        mocked_exchange_info = {  # irrelevant fields removed
            "symbols": [
                {
                    "symbol": self.symbol,
                    "pair": self.symbol,
                    "contractType": "PERPETUAL",
                    "baseAsset": self.base_asset,
                    "quoteAsset": self.quote_asset,
                    "marginAsset": margin_asset,
                    "status": "TRADING",
                }
            ],
        }

        return mocked_exchange_info

    @aioresponses()
    async def test_existing_account_position_detected_on_positions_update(self, req_mock):
        self._simulate_trading_rules_initialized()

        url = web_utils.private_rest_url(
            CONSTANTS.POSITION_INFORMATION_URL, domain=self.domain
        )
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        positions = self._get_position_risk_api_endpoint_single_position_list()
        req_mock.get(regex_url, body=json.dumps(positions))

        await self.exchange._update_positions()

        self.assertEqual(len(self.exchange.account_positions), 1)
        pos = list(self.exchange.account_positions.values())[0]
        self.assertEqual(pos.trading_pair.replace("-", ""), self.symbol)

    @aioresponses()
    async def test_wrong_symbol_position_detected_on_positions_update(self, req_mock):
        self._simulate_trading_rules_initialized()

        url = web_utils.private_rest_url(
            CONSTANTS.POSITION_INFORMATION_URL, domain=self.domain
        )
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        positions = self._get_wrong_symbol_position_risk_api_endpoint_single_position_list()
        req_mock.get(regex_url, body=json.dumps(positions))

        await self.exchange._update_positions()

        self.assertEqual(len(self.exchange.account_positions), 0)

    @aioresponses()
    async def test_account_position_updated_on_positions_update(self, req_mock):
        self._simulate_trading_rules_initialized()
        url = web_utils.private_rest_url(
            CONSTANTS.POSITION_INFORMATION_URL, domain=self.domain
        )
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        positions = self._get_position_risk_api_endpoint_single_position_list()
        req_mock.get(regex_url, body=json.dumps(positions))

        await self.exchange._update_positions()

        self.assertEqual(len(self.exchange.account_positions), 1)
        pos = list(self.exchange.account_positions.values())[0]
        self.assertEqual(pos.amount, 1)

        positions[0]["positionAmt"] = "2"
        req_mock.get(regex_url, body=json.dumps(positions))
        await self.exchange._update_positions()

        pos = list(self.exchange.account_positions.values())[0]
        self.assertEqual(pos.amount, 2)

    @aioresponses()
    async def test_new_account_position_detected_on_positions_update(self, req_mock):
        self._simulate_trading_rules_initialized()
        url = web_utils.private_rest_url(
            CONSTANTS.POSITION_INFORMATION_URL, domain=self.domain
        )
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        req_mock.get(regex_url, body=json.dumps([]))

        await self.exchange._update_positions()

        self.assertEqual(len(self.exchange.account_positions), 0)

        positions = self._get_position_risk_api_endpoint_single_position_list()
        req_mock.get(regex_url, body=json.dumps(positions))
        await self.exchange._update_positions()

        self.assertEqual(len(self.exchange.account_positions), 1)

    @aioresponses()
    async def test_closed_account_position_removed_on_positions_update(self, req_mock):
        self._simulate_trading_rules_initialized()
        url = web_utils.private_rest_url(
            CONSTANTS.POSITION_INFORMATION_URL, domain=self.domain
        )
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        positions = self._get_position_risk_api_endpoint_single_position_list()
        req_mock.get(regex_url, body=json.dumps(positions))

        await self.exchange._update_positions()

        self.assertEqual(len(self.exchange.account_positions), 1)

        positions[0]["positionAmt"] = "0"
        req_mock.get(regex_url, body=json.dumps(positions))
        await self.exchange._update_positions()

        self.assertEqual(len(self.exchange.account_positions), 0)

    async def test_supported_position_modes(self):
        linear_connector = self.exchange
        expected_result = [PositionMode.ONEWAY, PositionMode.HEDGE]
        self.assertEqual(expected_result, linear_connector.supported_position_modes())

    @aioresponses()
    async def test_set_position_mode_initial_mode_is_none(self, mock_api):
        self._simulate_trading_rules_initialized()
        self.assertIsNone(self.exchange._position_mode)

        url = web_utils.private_rest_url(CONSTANTS.CHANGE_POSITION_MODE_URL, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        get_position_mode_response = {"dualSidePosition": False}  # True: Hedge Mode; False: One-way Mode
        post_position_mode_response = {"code": 200, "msg": "success"}
        mock_api.get(regex_url, body=json.dumps(get_position_mode_response))
        mock_api.post(regex_url, body=json.dumps(post_position_mode_response))

        await self.exchange._trading_pair_position_mode_set(PositionMode.HEDGE, self.trading_pair)

        self.assertEqual(PositionMode.HEDGE, self.exchange._position_mode)

    @aioresponses()
    async def test_set_position_initial_mode_unchanged(self, mock_api):
        self.exchange._position_mode = PositionMode.ONEWAY
        url = web_utils.private_rest_url(CONSTANTS.CHANGE_POSITION_MODE_URL, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        get_position_mode_response = {"dualSidePosition": False}  # True: Hedge Mode; False: One-way Mode

        mock_api.get(regex_url, body=json.dumps(get_position_mode_response))
        await self.exchange._trading_pair_position_mode_set(PositionMode.ONEWAY, self.trading_pair)

        self.assertEqual(PositionMode.ONEWAY, self.exchange.position_mode)

    @aioresponses()
    async def test_set_position_mode_diff_initial_mode_change_successful(self, mock_api):
        self.exchange._position_mode = PositionMode.ONEWAY
        url = web_utils.private_rest_url(CONSTANTS.CHANGE_POSITION_MODE_URL, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        get_position_mode_response = {"dualSidePosition": False}  # True: Hedge Mode; False: One-way Mode
        post_position_mode_response = {"code": 200, "msg": "success"}

        mock_api.get(regex_url, body=json.dumps(get_position_mode_response))
        mock_api.post(regex_url, body=json.dumps(post_position_mode_response))

        await self.exchange._trading_pair_position_mode_set(PositionMode.HEDGE, self.trading_pair)

        self.assertEqual(PositionMode.HEDGE, self.exchange._position_mode)

    @aioresponses()
    async def test_set_position_mode_diff_initial_mode_change_fail(self, mock_api):
        self.exchange._position_mode = PositionMode.ONEWAY
        url = web_utils.private_rest_url(CONSTANTS.CHANGE_POSITION_MODE_URL, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        get_position_mode_response = {"dualSidePosition": False}  # True: Hedge Mode; False: One-way Mode
        post_position_mode_response = {"code": -4059, "msg": "No need to change position side."}

        mock_api.get(regex_url, body=json.dumps(get_position_mode_response))
        mock_api.post(regex_url, body=json.dumps(post_position_mode_response))

        await self.exchange._trading_pair_position_mode_set(PositionMode.HEDGE, self.trading_pair)

        self.assertEqual(PositionMode.ONEWAY, self.exchange.position_mode)

    async def test_format_trading_rules(self):
        margin_asset = self.quote_asset
        min_order_size = 1
        min_price_increment = 2
        min_base_amount_increment = 3
        min_notional_size = 4
        mocked_response = self._get_exchange_info_mock_response(
            margin_asset, min_order_size, min_price_increment, min_base_amount_increment, min_notional_size
        )
        self._simulate_trading_rules_initialized()
        trading_rules = await self.exchange._format_trading_rules(mocked_response)

        self.assertEqual(1, len(trading_rules))

        trading_rule = trading_rules[0]

        self.assertEqual(min_order_size, trading_rule.min_order_size)
        self.assertEqual(min_price_increment, trading_rule.min_price_increment)
        self.assertEqual(min_base_amount_increment, trading_rule.min_base_amount_increment)
        self.assertEqual(min_notional_size, trading_rule.min_notional_size)
        self.assertEqual(margin_asset, trading_rule.buy_order_collateral_token)
        self.assertEqual(margin_asset, trading_rule.sell_order_collateral_token)

    async def test_format_trading_rules_exception(self):
        margin_asset = self.quote_asset
        min_order_size = 1
        min_price_increment = 2
        min_base_amount_increment = 3
        min_notional_size = 4
        mocked_response = self._get_exchange_info_error_mock_response(
            margin_asset, min_order_size, min_price_increment, min_base_amount_increment, min_notional_size
        )
        self._simulate_trading_rules_initialized()

        await self.exchange._format_trading_rules(mocked_response)
        self.assertTrue(self._is_logged(
            "ERROR",
            f"Error parsing the trading pair rule {mocked_response['symbols'][0]}. Error: 'filters'. Skipping..."
        ))

    async def test_get_collateral_token(self):
        margin_asset = self.quote_asset
        self._simulate_trading_rules_initialized()

        self.assertEqual(margin_asset, self.exchange.get_buy_collateral_token(self.trading_pair))
        self.assertEqual(margin_asset, self.exchange.get_sell_collateral_token(self.trading_pair))

    async def test_buy_order_fill_event_takes_fee_from_update_event(self):
        self.exchange.start_tracking_order(
            order_id="OID1",
            exchange_order_id="8886774",
            trading_pair=self.trading_pair,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("1"),
            order_type=OrderType.LIMIT,
            leverage=1,
            position_action=PositionAction.OPEN,
        )

        order = self.exchange.in_flight_orders.get("OID1")

        partial_fill = {
            "e": "ORDER_TRADE_UPDATE",
            "E": 1568879465651,
            "T": 1568879465650,
            "o": {
                "s": self.trading_pair,
                "c": order.client_order_id,
                "S": "BUY",
                "o": "TRAILING_STOP_MARKET",
                "f": "GTC",
                "q": "1",
                "p": "10000",
                "ap": "0",
                "sp": "7103.04",
                "x": "TRADE",
                "X": "PARTIALLY_FILLED",
                "i": 8886774,
                "l": "0.1",
                "z": "0.1",
                "L": "10000",
                "N": "HBOT",
                "n": "20",
                "T": 1568879465651,
                "t": 1,
                "b": "0",
                "a": "9.91",
                "m": False,
                "R": False,
                "wt": "CONTRACT_PRICE",
                "ot": "TRAILING_STOP_MARKET",
                "ps": "LONG",
                "cp": False,
                "AP": "7476.89",
                "cr": "5.0",
                "rp": "0"
            }

        }

        mock_user_stream = AsyncMock()
        mock_user_stream.get.side_effect = functools.partial(self._return_calculation_and_set_done_event,
                                                             lambda: partial_fill)

        self.exchange._user_stream_tracker._user_stream = mock_user_stream

        self.test_task = self.local_event_loop.create_task(self.exchange._user_stream_event_listener())
        await self.resume_test_event.wait()

        self.assertEqual(1, len(self.order_filled_logger.event_log))
        fill_event: OrderFilledEvent = self.order_filled_logger.event_log[0]
        self.assertEqual(Decimal("0"), fill_event.trade_fee.percent)
        self.assertEqual(
            [TokenAmount(partial_fill["o"]["N"], Decimal(partial_fill["o"]["n"]))], fill_event.trade_fee.flat_fees
        )

        complete_fill = {
            "e": "ORDER_TRADE_UPDATE",
            "E": 1568879465651,
            "T": 1568879465650,
            "o": {
                "s": self.trading_pair,
                "c": order.client_order_id,
                "S": "BUY",
                "o": "TRAILING_STOP_MARKET",
                "f": "GTC",
                "q": "1",
                "p": "10000",
                "ap": "0",
                "sp": "7103.04",
                "x": "TRADE",
                "X": "FILLED",
                "i": 8886774,
                "l": "0.9",
                "z": "1",
                "L": "10000",
                "N": "HBOT",
                "n": "30",
                "T": 1568879465651,
                "t": 2,
                "b": "0",
                "a": "9.91",
                "m": False,
                "R": False,
                "wt": "CONTRACT_PRICE",
                "ot": "TRAILING_STOP_MARKET",
                "ps": "LONG",
                "cp": False,
                "AP": "7476.89",
                "cr": "5.0",
                "rp": "0"
            }

        }

        self.resume_test_event = asyncio.Event()
        mock_user_stream.get.side_effect = functools.partial(self._return_calculation_and_set_done_event,
                                                             lambda: complete_fill)

        self.test_task = self.local_event_loop.create_task(self.exchange._user_stream_event_listener())
        await self.resume_test_event.wait()

        self.assertEqual(2, len(self.order_filled_logger.event_log))
        fill_event: OrderFilledEvent = self.order_filled_logger.event_log[1]
        self.assertEqual(Decimal("0"), fill_event.trade_fee.percent)
        self.assertEqual([TokenAmount(complete_fill["o"]["N"], Decimal(complete_fill["o"]["n"]))],
                         fill_event.trade_fee.flat_fees)

    async def test_sell_order_fill_event_takes_fee_from_update_event(self):
        self.exchange.start_tracking_order(
            order_id="OID1",
            exchange_order_id="8886774",
            trading_pair=self.trading_pair,
            trade_type=TradeType.SELL,
            price=Decimal("10000"),
            amount=Decimal("1"),
            order_type=OrderType.LIMIT,
            leverage=1,
            position_action=PositionAction.OPEN,
        )

        order = self.exchange.in_flight_orders.get("OID1")

        partial_fill = {
            "e": "ORDER_TRADE_UPDATE",
            "E": 1568879465651,
            "T": 1568879465650,
            "o": {
                "s": self.trading_pair,
                "c": order.client_order_id,
                "S": "SELL",
                "o": "TRAILING_STOP_MARKET",
                "f": "GTC",
                "q": "1",
                "p": "10000",
                "ap": "0",
                "sp": "7103.04",
                "x": "TRADE",
                "X": "PARTIALLY_FILLED",
                "i": 8886774,
                "l": "0.1",
                "z": "0.1",
                "L": "10000",
                "N": self.quote_asset,
                "n": "20",
                "T": 1568879465651,
                "t": 1,
                "b": "0",
                "a": "9.91",
                "m": False,
                "R": False,
                "wt": "CONTRACT_PRICE",
                "ot": "TRAILING_STOP_MARKET",
                "ps": "LONG",
                "cp": False,
                "AP": "7476.89",
                "cr": "5.0",
                "rp": "0"
            }
        }

        mock_user_stream = AsyncMock()
        mock_user_stream.get.side_effect = functools.partial(self._return_calculation_and_set_done_event,
                                                             lambda: partial_fill)

        self.exchange._user_stream_tracker._user_stream = mock_user_stream

        self.test_task = self.local_event_loop.create_task(self.exchange._user_stream_event_listener())
        await self.resume_test_event.wait()

        self.assertEqual(1, len(self.order_filled_logger.event_log))
        fill_event: OrderFilledEvent = self.order_filled_logger.event_log[0]
        self.assertEqual(Decimal("0"), fill_event.trade_fee.percent)
        self.assertEqual(
            [TokenAmount(partial_fill["o"]["N"], Decimal(partial_fill["o"]["n"]))], fill_event.trade_fee.flat_fees
        )

        complete_fill = {
            "e": "ORDER_TRADE_UPDATE",
            "E": 1568879465651,
            "T": 1568879465650,
            "o": {
                "s": self.trading_pair,
                "c": order.client_order_id,
                "S": "SELL",
                "o": "TRAILING_STOP_MARKET",
                "f": "GTC",
                "q": "1",
                "p": "10000",
                "ap": "0",
                "sp": "7103.04",
                "x": "TRADE",
                "X": "FILLED",
                "i": 8886774,
                "l": "0.9",
                "z": "1",
                "L": "10000",
                "N": self.quote_asset,
                "n": "30",
                "T": 1568879465651,
                "t": 2,
                "b": "0",
                "a": "9.91",
                "m": False,
                "R": False,
                "wt": "CONTRACT_PRICE",
                "ot": "TRAILING_STOP_MARKET",
                "ps": "LONG",
                "cp": False,
                "AP": "7476.89",
                "cr": "5.0",
                "rp": "0"
            }

        }

        self.resume_test_event = asyncio.Event()
        mock_user_stream.get.side_effect = functools.partial(self._return_calculation_and_set_done_event,
                                                             lambda: complete_fill)

        self.test_task = self.local_event_loop.create_task(self.exchange._user_stream_event_listener())
        await self.resume_test_event.wait()

        self.assertEqual(2, len(self.order_filled_logger.event_log))
        fill_event: OrderFilledEvent = self.order_filled_logger.event_log[1]
        self.assertEqual(Decimal("0"), fill_event.trade_fee.percent)
        self.assertEqual([TokenAmount(complete_fill["o"]["N"], Decimal(complete_fill["o"]["n"]))],
                         fill_event.trade_fee.flat_fees)

    async def test_order_fill_event_ignored_for_repeated_trade_id(self):
        self.exchange.start_tracking_order(
            order_id="OID1",
            exchange_order_id="8886774",
            trading_pair=self.trading_pair,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("1"),
            order_type=OrderType.LIMIT,
            leverage=1,
            position_action=PositionAction.OPEN,
        )

        order = self.exchange.in_flight_orders.get("OID1")

        partial_fill = {
            "e": "ORDER_TRADE_UPDATE",
            "E": 1568879465651,
            "T": 1568879465650,
            "o": {
                "s": self.trading_pair,
                "c": order.client_order_id,
                "S": "BUY",
                "o": "TRAILING_STOP_MARKET",
                "f": "GTC",
                "q": "1",
                "p": "10000",
                "ap": "0",
                "sp": "7103.04",
                "x": "TRADE",
                "X": "PARTIALLY_FILLED",
                "i": 8886774,
                "l": "0.1",
                "z": "0.1",
                "L": "10000",
                "N": self.quote_asset,
                "n": "20",
                "T": 1568879465651,
                "t": 1,
                "b": "0",
                "a": "9.91",
                "m": False,
                "R": False,
                "wt": "CONTRACT_PRICE",
                "ot": "TRAILING_STOP_MARKET",
                "ps": "LONG",
                "cp": False,
                "AP": "7476.89",
                "cr": "5.0",
                "rp": "0"
            }
        }

        mock_user_stream = AsyncMock()
        mock_user_stream.get.side_effect = functools.partial(self._return_calculation_and_set_done_event,
                                                             lambda: partial_fill)

        self.exchange._user_stream_tracker._user_stream = mock_user_stream

        self.test_task = self.local_event_loop.create_task(self.exchange._user_stream_event_listener())
        await self.resume_test_event.wait()

        self.assertEqual(1, len(self.order_filled_logger.event_log))
        fill_event: OrderFilledEvent = self.order_filled_logger.event_log[0]
        self.assertEqual(Decimal("0"), fill_event.trade_fee.percent)
        self.assertEqual(
            [TokenAmount(partial_fill["o"]["N"], Decimal(partial_fill["o"]["n"]))], fill_event.trade_fee.flat_fees
        )

        repeated_partial_fill = {
            "e": "ORDER_TRADE_UPDATE",
            "E": 1568879465651,
            "T": 1568879465650,
            "o": {
                "s": self.trading_pair,
                "c": order.client_order_id,
                "S": "BUY",
                "o": "TRAILING_STOP_MARKET",
                "f": "GTC",
                "q": "1",
                "p": "10000",
                "ap": "0",
                "sp": "7103.04",
                "x": "TRADE",
                "X": "PARTIALLY_FILLED",
                "i": 8886774,
                "l": "0.1",
                "z": "0.1",
                "L": "10000",
                "N": self.quote_asset,
                "n": "20",
                "T": 1568879465651,
                "t": 1,
                "b": "0",
                "a": "9.91",
                "m": False,
                "R": False,
                "wt": "CONTRACT_PRICE",
                "ot": "TRAILING_STOP_MARKET",
                "ps": "LONG",
                "cp": False,
                "AP": "7476.89",
                "cr": "5.0",
                "rp": "0"
            }
        }

        self.resume_test_event = asyncio.Event()
        mock_user_stream.get.side_effect = functools.partial(self._return_calculation_and_set_done_event,
                                                             lambda: repeated_partial_fill)

        self.test_task = self.local_event_loop.create_task(self.exchange._user_stream_event_listener())
        await self.resume_test_event.wait()

        self.assertEqual(1, len(self.order_filled_logger.event_log))

        self.assertEqual(0, len(self.buy_order_completed_logger.event_log))

    async def test_fee_is_zero_when_not_included_in_fill_event(self):
        self.exchange.start_tracking_order(
            order_id="OID1",
            exchange_order_id="8886774",
            trading_pair=self.trading_pair,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("1"),
            order_type=OrderType.LIMIT,
            leverage=1,
            position_action=PositionAction.OPEN,
        )

        order = self.exchange.in_flight_orders.get("OID1")

        partial_fill = {
            "e": "ORDER_TRADE_UPDATE",
            "E": 1568879465651,
            "T": 1568879465650,
            "o": {
                "s": self.trading_pair,
                "c": order.client_order_id,
                "S": "BUY",
                "o": "TRAILING_STOP_MARKET",
                "f": "GTC",
                "q": "1",
                "p": "10000",
                "ap": "0",
                "sp": "7103.04",
                "x": "TRADE",
                "X": "PARTIALLY_FILLED",
                "i": 8886774,
                "l": "0.1",
                "z": "0.1",
                "L": "10000",
                # "N": "USDT", //Do not include fee asset
                # "n": "20", //Do not include fee amount
                "T": 1568879465651,
                "t": 1,
                "b": "0",
                "a": "9.91",
                "m": False,
                "R": False,
                "wt": "CONTRACT_PRICE",
                "ot": "TRAILING_STOP_MARKET",
                "ps": "LONG",
                "cp": False,
                "AP": "7476.89",
                "cr": "5.0",
                "rp": "0"
            }

        }

        await self.exchange._process_user_stream_event(event_message=partial_fill)

        self.assertEqual(1, len(self.order_filled_logger.event_log))
        fill_event: OrderFilledEvent = self.order_filled_logger.event_log[0]
        self.assertEqual(Decimal("0"), fill_event.trade_fee.percent)
        self.assertEqual(0, len(fill_event.trade_fee.flat_fees))

    async def test_order_event_with_cancelled_status_marks_order_as_cancelled(self):
        self._simulate_trading_rules_initialized()
        self.exchange.start_tracking_order(
            order_id="OID1",
            exchange_order_id="8886774",
            trading_pair=self.trading_pair,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("1"),
            order_type=OrderType.LIMIT,
            leverage=1,
            position_action=PositionAction.OPEN,
        )

        order = self.exchange.in_flight_orders.get("OID1")

        partial_fill = {
            "e": "ORDER_TRADE_UPDATE",
            "E": 1568879465651,
            "T": 1568879465650,
            "o": {
                "s": self.trading_pair,
                "c": order.client_order_id,
                "S": "BUY",
                "o": "TRAILING_STOP_MARKET",
                "f": "GTC",
                "q": "1",
                "p": "10000",
                "ap": "0",
                "sp": "7103.04",
                "x": "TRADE",
                "X": "CANCELED",
                "i": 8886774,
                "l": "0.1",
                "z": "0.1",
                "L": "10000",
                "N": self.quote_asset,
                "n": "20",
                "T": 1568879465651,
                "t": 1,
                "b": "0",
                "a": "9.91",
                "m": False,
                "R": False,
                "wt": "CONTRACT_PRICE",
                "ot": "TRAILING_STOP_MARKET",
                "ps": "LONG",
                "cp": False,
                "AP": "7476.89",
                "cr": "5.0",
                "rp": "0"
            }

        }

        mock_user_stream = AsyncMock()
        mock_user_stream.get.side_effect = functools.partial(self._return_calculation_and_set_done_event,
                                                             lambda: partial_fill)

        self.exchange._user_stream_tracker._user_stream = mock_user_stream

        self.test_task = self.local_event_loop.create_task(self.exchange._user_stream_event_listener())
        await self.resume_test_event.wait()
        await asyncio.sleep(0.001)

        self.assertEqual(1, len(self.order_cancelled_logger.event_log))

        self.assertTrue(self._is_logged(
            "INFO",
            f"Successfully canceled order {order.client_order_id}."
        ))

    async def test_user_stream_event_listener_raises_cancelled_error(self):
        mock_user_stream = AsyncMock()
        mock_user_stream.get.side_effect = asyncio.CancelledError

        self.exchange._user_stream_tracker._user_stream = mock_user_stream
        with self.assertRaises(asyncio.CancelledError):
            await self.exchange._user_stream_event_listener()

    async def test_margin_call_event(self):
        self._simulate_trading_rules_initialized()
        margin_call = {
            "e": "MARGIN_CALL",
            "E": 1587727187525,
            "cw": "3.16812045",
            "p": [
                {
                    "s": self.symbol,
                    "ps": "LONG",
                    "pa": "1.327",
                    "mt": "CROSSED",
                    "iw": "0",
                    "mp": "187.17127",
                    "up": "-1.166074",
                    "mm": "1.614445"
                }
            ]
        }

        mock_user_stream = AsyncMock()
        mock_user_stream.get.side_effect = functools.partial(self._return_calculation_and_set_done_event,
                                                             lambda: margin_call)

        self.exchange._user_stream_tracker._user_stream = mock_user_stream

        self.test_task = self.local_event_loop.create_task(self.exchange._user_stream_event_listener())
        await self.resume_test_event.wait()

        self.assertTrue(self._is_logged(
            "WARNING",
            "Margin Call: Your position risk is too high, and you are at risk of liquidation. "
            "Close your positions or add additional margin to your wallet."
        ))
        self.assertTrue(self._is_logged(
            "INFO",
            f"Margin Required: 1.614445. Negative PnL assets: {self.trading_pair}: -1.166074, ."
        ))

    async def test_wrong_symbol_margin_call_event(self):
        self._simulate_trading_rules_initialized()
        margin_call = {
            "e": "MARGIN_CALL",
            "E": 1587727187525,
            "cw": "3.16812045",
            "p": [
                {
                    "s": f"{self.symbol}_230331",
                    "ps": "LONG",
                    "pa": "1.327",
                    "mt": "CROSSED",
                    "iw": "0",
                    "mp": "187.17127",
                    "up": "-1.166074",
                    "mm": "1.614445"
                }
            ]
        }

        mock_user_stream = AsyncMock()
        mock_user_stream.get.side_effect = functools.partial(self._return_calculation_and_set_done_event,
                                                             lambda: margin_call)

        self.exchange._user_stream_tracker._user_stream = mock_user_stream

        self.test_task = self.local_event_loop.create_task(self.exchange._user_stream_event_listener())
        await self.resume_test_event.wait()

        self.assertTrue(self._is_logged(
            "WARNING",
            "Margin Call: Your position risk is too high, and you are at risk of liquidation. "
            "Close your positions or add additional margin to your wallet."
        ))
        self.assertTrue(self._is_logged(
            "INFO",
            "Margin Required: 0. Negative PnL assets: ."
        ))

    @aioresponses()
    @patch("hummingbot.connector.derivative.binance_perpetual.binance_perpetual_derivative."
           "BinancePerpetualDerivative.current_timestamp")
    async def test_update_order_fills_from_trades_successful(self, req_mock, mock_timestamp):
        self._simulate_trading_rules_initialized()
        self.exchange._last_poll_timestamp = 0
        mock_timestamp.return_value = 1

        self.exchange.start_tracking_order(
            order_id="OID1",
            exchange_order_id="8886774",
            trading_pair=self.trading_pair,
            trade_type=TradeType.SELL,
            price=Decimal("10000"),
            amount=Decimal("1"),
            order_type=OrderType.LIMIT,
            leverage=1,
            position_action=PositionAction.OPEN,
        )

        trades = [{"buyer": False,
                   "commission": "0",
                   "commissionAsset": self.quote_asset,
                   "id": 698759,
                   "maker": False,
                   "orderId": "8886774",
                   "price": "10000",
                   "qty": "0.5",
                   "quoteQty": "5000",
                   "realizedPnl": "0",
                   "side": "SELL",
                   "positionSide": "SHORT",
                   "symbol": "COINALPHAHBOT",
                   "time": 1000}]

        url = web_utils.private_rest_url(
            CONSTANTS.ACCOUNT_TRADE_LIST_URL, domain=self.domain
        )
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        req_mock.get(regex_url, body=json.dumps(trades))

        await self.exchange._update_order_fills_from_trades()

        in_flight_orders = self.exchange._order_tracker.active_orders

        self.assertTrue("OID1" in in_flight_orders)

        self.assertEqual("OID1", in_flight_orders["OID1"].client_order_id)
        self.assertEqual(f"{self.base_asset}-{self.quote_asset}", in_flight_orders["OID1"].trading_pair)
        self.assertEqual(OrderType.LIMIT, in_flight_orders["OID1"].order_type)
        self.assertEqual(TradeType.SELL, in_flight_orders["OID1"].trade_type)
        self.assertEqual(10000, in_flight_orders["OID1"].price)
        self.assertEqual(1, in_flight_orders["OID1"].amount)
        self.assertEqual("8886774", in_flight_orders["OID1"].exchange_order_id)
        self.assertEqual(OrderState.PENDING_CREATE, in_flight_orders["OID1"].current_state)
        self.assertEqual(1, in_flight_orders["OID1"].leverage)
        self.assertEqual(PositionAction.OPEN, in_flight_orders["OID1"].position)

        self.assertEqual(0.5, in_flight_orders["OID1"].executed_amount_base)
        self.assertEqual(5000, in_flight_orders["OID1"].executed_amount_quote)
        self.assertEqual(1, in_flight_orders["OID1"].last_update_timestamp)

        self.assertTrue("698759" in in_flight_orders["OID1"].order_fills.keys())

    @aioresponses()
    async def test_update_order_fills_from_trades_failed(self, req_mock):
        self.exchange._set_current_timestamp(1640001112.0)
        self.exchange._last_poll_timestamp = 0
        self._simulate_trading_rules_initialized()
        self.exchange.start_tracking_order(
            order_id="OID1",
            exchange_order_id="8886774",
            trading_pair=self.trading_pair,
            trade_type=TradeType.SELL,
            price=Decimal("10000"),
            amount=Decimal("1"),
            order_type=OrderType.LIMIT,
            leverage=1,
            position_action=PositionAction.OPEN,
        )

        url = web_utils.private_rest_url(
            CONSTANTS.ACCOUNT_TRADE_LIST_URL, domain=self.domain
        )
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        req_mock.get(regex_url, exception=Exception())

        await self.exchange._update_order_fills_from_trades()

        in_flight_orders = self.exchange._order_tracker.active_orders

        # Nothing has changed
        self.assertTrue("OID1" in in_flight_orders)

        self.assertEqual("OID1", in_flight_orders["OID1"].client_order_id)
        self.assertEqual(f"{self.base_asset}-{self.quote_asset}", in_flight_orders["OID1"].trading_pair)
        self.assertEqual(OrderType.LIMIT, in_flight_orders["OID1"].order_type)
        self.assertEqual(TradeType.SELL, in_flight_orders["OID1"].trade_type)
        self.assertEqual(10000, in_flight_orders["OID1"].price)
        self.assertEqual(1, in_flight_orders["OID1"].amount)
        self.assertEqual("8886774", in_flight_orders["OID1"].exchange_order_id)
        self.assertEqual(OrderState.PENDING_CREATE, in_flight_orders["OID1"].current_state)
        self.assertEqual(1, in_flight_orders["OID1"].leverage)
        self.assertEqual(PositionAction.OPEN, in_flight_orders["OID1"].position)

        self.assertEqual(0, in_flight_orders["OID1"].executed_amount_base)
        self.assertEqual(0, in_flight_orders["OID1"].executed_amount_quote)
        self.assertEqual(1640001112.0, in_flight_orders["OID1"].last_update_timestamp)

        # Error was logged
        self.assertTrue(self._is_logged("NETWORK",
                                        f"Error fetching trades update for the order {self.trading_pair}: ."))

    @aioresponses()
    @patch("hummingbot.connector.derivative.binance_perpetual.binance_perpetual_derivative."
           "BinancePerpetualDerivative.current_timestamp")
    async def test_update_order_status_successful(self, req_mock, mock_timestamp):
        self._simulate_trading_rules_initialized()
        self.exchange._last_poll_timestamp = 0
        mock_timestamp.return_value = 1

        self.exchange.start_tracking_order(
            order_id="OID1",
            exchange_order_id="8886774",
            trading_pair=self.trading_pair,
            trade_type=TradeType.SELL,
            price=Decimal("10000"),
            amount=Decimal("1"),
            order_type=OrderType.LIMIT,
            leverage=1,
            position_action=PositionAction.OPEN,
        )

        order = {"avgPrice": "0.00000",
                 "clientOrderId": "OID1",
                 "cumQuote": "5000",
                 "executedQty": "0.5",
                 "orderId": 8886774,
                 "origQty": "1",
                 "origType": "LIMIT",
                 "price": "10000",
                 "reduceOnly": False,
                 "side": "SELL",
                 "positionSide": "LONG",
                 "status": "PARTIALLY_FILLED",
                 "closePosition": False,
                 "symbol": f"{self.base_asset}{self.quote_asset}",
                 "time": 1000,
                 "timeInForce": "GTC",
                 "type": "LIMIT",
                 "priceRate": "0.3",
                 "updateTime": 2000,
                 "workingType": "CONTRACT_PRICE",
                 "priceProtect": False}

        url = web_utils.private_rest_url(
            CONSTANTS.ORDER_URL, domain=self.domain
        )
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        req_mock.get(regex_url, body=json.dumps(order))

        await self.exchange._update_order_status()
        await asyncio.sleep(0.001)

        in_flight_orders = self.exchange._order_tracker.active_orders

        self.assertTrue("OID1" in in_flight_orders)

        self.assertEqual("OID1", in_flight_orders["OID1"].client_order_id)
        self.assertEqual(f"{self.base_asset}-{self.quote_asset}", in_flight_orders["OID1"].trading_pair)
        self.assertEqual(OrderType.LIMIT, in_flight_orders["OID1"].order_type)
        self.assertEqual(TradeType.SELL, in_flight_orders["OID1"].trade_type)
        self.assertEqual(10000, in_flight_orders["OID1"].price)
        self.assertEqual(1, in_flight_orders["OID1"].amount)
        self.assertEqual("8886774", in_flight_orders["OID1"].exchange_order_id)
        self.assertEqual(OrderState.PARTIALLY_FILLED, in_flight_orders["OID1"].current_state)
        self.assertEqual(1, in_flight_orders["OID1"].leverage)
        self.assertEqual(PositionAction.OPEN, in_flight_orders["OID1"].position)

        # Processing an order update should not impact trade fill information
        self.assertEqual(Decimal("0"), in_flight_orders["OID1"].executed_amount_base)
        self.assertEqual(Decimal("0"), in_flight_orders["OID1"].executed_amount_quote)

        self.assertEqual(2, in_flight_orders["OID1"].last_update_timestamp)

        self.assertEqual(0, len(in_flight_orders["OID1"].order_fills))

    @aioresponses()
    @patch("hummingbot.connector.derivative.binance_perpetual.binance_perpetual_derivative."
           "BinancePerpetualDerivative.current_timestamp")
    async def test_request_order_status_successful(self, req_mock, mock_timestamp):
        self._simulate_trading_rules_initialized()
        self.exchange._last_poll_timestamp = 0
        mock_timestamp.return_value = 1

        self.exchange.start_tracking_order(
            order_id="OID1",
            exchange_order_id="8886774",
            trading_pair=self.trading_pair,
            trade_type=TradeType.SELL,
            price=Decimal("10000"),
            amount=Decimal("1"),
            order_type=OrderType.LIMIT,
            leverage=1,
            position_action=PositionAction.OPEN,
        )
        tracked_order = self.exchange._order_tracker.fetch_order("OID1")

        order = {"avgPrice": "0.00000",
                 "clientOrderId": "OID1",
                 "cumQuote": "5000",
                 "executedQty": "0.5",
                 "orderId": 8886774,
                 "origQty": "1",
                 "origType": "LIMIT",
                 "price": "10000",
                 "reduceOnly": False,
                 "side": "SELL",
                 "positionSide": "LONG",
                 "status": "PARTIALLY_FILLED",
                 "closePosition": False,
                 "symbol": f"{self.base_asset}{self.quote_asset}",
                 "time": 1000,
                 "timeInForce": "GTC",
                 "type": "LIMIT",
                 "priceRate": "0.3",
                 "updateTime": 2000,
                 "workingType": "CONTRACT_PRICE",
                 "priceProtect": False}

        url = web_utils.private_rest_url(
            CONSTANTS.ORDER_URL, domain=self.domain
        )
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        req_mock.get(regex_url, body=json.dumps(order))

        order_update = await self.exchange._request_order_status(tracked_order)

        in_flight_orders = self.exchange._order_tracker.active_orders
        self.assertTrue("OID1" in in_flight_orders)

        self.assertEqual(order_update.client_order_id, in_flight_orders["OID1"].client_order_id)
        self.assertEqual(OrderState.PARTIALLY_FILLED, order_update.new_state)
        self.assertEqual(0, len(in_flight_orders["OID1"].order_fills))

    @aioresponses()
    async def test_set_leverage_successful(self, req_mock):
        self._simulate_trading_rules_initialized()
        trading_pair = f"{self.base_asset}-{self.quote_asset}"
        symbol = f"{self.base_asset}{self.quote_asset}"
        leverage = 21

        response = {
            "leverage": leverage,
            "maxNotionalValue": "1000000",
            "symbol": symbol
        }

        url = web_utils.private_rest_url(
            CONSTANTS.SET_LEVERAGE_URL, domain=self.domain
        )
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        req_mock.post(regex_url, body=json.dumps(response))

        success, msg = await self.exchange._set_trading_pair_leverage(trading_pair, leverage)
        self.assertEqual(success, True)
        self.assertEqual(msg, '')

    @aioresponses()
    async def test_set_leverage_failed(self, req_mock):
        self._simulate_trading_rules_initialized()
        trading_pair = f"{self.base_asset}-{self.quote_asset}"
        symbol = f"{self.base_asset}{self.quote_asset}"
        leverage = 21

        response = {"leverage": 0,
                    "maxNotionalValue": "1000000",
                    "symbol": symbol}

        url = web_utils.private_rest_url(
            CONSTANTS.SET_LEVERAGE_URL, domain=self.domain
        )
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        req_mock.post(regex_url, body=json.dumps(response))

        success, message = await self.exchange._set_trading_pair_leverage(trading_pair, leverage)
        self.assertEqual(success, False)
        self.assertEqual(message, 'Unable to set leverage')

    @aioresponses()
    async def test_fetch_funding_payment_successful(self, req_mock):
        self._simulate_trading_rules_initialized()
        income_history = self._get_income_history_dict()

        url = web_utils.private_rest_url(
            CONSTANTS.GET_INCOME_HISTORY_URL, domain=self.domain
        )
        regex_url_income_history = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        req_mock.get(regex_url_income_history, body=json.dumps(income_history))

        funding_info = self._get_funding_info_dict()

        url = web_utils.public_rest_url(
            CONSTANTS.MARK_PRICE_URL, domain=self.domain
        )
        regex_url_funding_info = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        req_mock.get(regex_url_funding_info, body=json.dumps(funding_info))

        # Fetch from exchange with REST API - safe_ensure_future, not immediately
        await self.exchange._update_funding_payment(self.trading_pair, True)

        req_mock.get(regex_url_income_history, body=json.dumps(income_history))

        # Fetch once received
        await self.exchange._update_funding_payment(self.trading_pair, True)

        self.assertTrue(len(self.funding_payment_completed_logger.event_log) == 1)

        funding_info_logged = self.funding_payment_completed_logger.event_log[0]

        self.assertTrue(funding_info_logged.trading_pair == f"{self.base_asset}-{self.quote_asset}")

        self.assertEqual(funding_info_logged.funding_rate, funding_info["lastFundingRate"])
        self.assertEqual(funding_info_logged.amount, income_history[0]["income"])

    @aioresponses()
    async def test_fetch_funding_payment_failed(self, req_mock):
        self._simulate_trading_rules_initialized()
        url = web_utils.private_rest_url(
            CONSTANTS.GET_INCOME_HISTORY_URL, domain=self.domain
        )
        regex_url_income_history = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        req_mock.get(regex_url_income_history, exception=Exception)

        await self.exchange._update_funding_payment(self.trading_pair, False)

        self.assertTrue(self._is_logged(
            "NETWORK",
            f"Unexpected error while fetching last fee payment for {self.trading_pair}.",
        ))

    @aioresponses()
    async def test_cancel_all_successful(self, mocked_api):
        url = web_utils.private_rest_url(
            CONSTANTS.ORDER_URL, domain=self.domain
        )
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        cancel_response = {"code": 200, "msg": "success", "status": "CANCELED"}
        mocked_api.delete(regex_url, body=json.dumps(cancel_response))

        self.exchange.start_tracking_order(
            order_id="OID1",
            exchange_order_id="8886774",
            trading_pair=self.trading_pair,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("1"),
            order_type=OrderType.LIMIT,
            leverage=1,
            position_action=PositionAction.OPEN,
        )

        self.exchange.start_tracking_order(
            order_id="OID2",
            exchange_order_id="8886775",
            trading_pair=self.trading_pair,
            trade_type=TradeType.BUY,
            price=Decimal("10101"),
            amount=Decimal("1"),
            order_type=OrderType.LIMIT,
            leverage=1,
            position_action=PositionAction.OPEN,
        )

        self.assertTrue("OID1" in self.exchange._order_tracker._in_flight_orders)
        self.assertTrue("OID2" in self.exchange._order_tracker._in_flight_orders)

        cancellation_results = await self.exchange.cancel_all(timeout_seconds=1)

        order_cancelled_events = self.order_cancelled_logger.event_log

        self.assertEqual(0, len(order_cancelled_events))
        self.assertEqual(2, len(cancellation_results))

    @aioresponses()
    async def test_cancel_all_unknown_order(self, req_mock):
        self._simulate_trading_rules_initialized()
        url = web_utils.private_rest_url(
            CONSTANTS.ORDER_URL, domain=self.domain
        )
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        cancel_response = {"code": -2011, "msg": "Unknown order sent."}
        req_mock.delete(regex_url, body=json.dumps(cancel_response))

        self.exchange.start_tracking_order(
            order_id="OID1",
            exchange_order_id="8886774",
            trading_pair=self.trading_pair,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("1"),
            order_type=OrderType.LIMIT,
            leverage=1,
            position_action=PositionAction.OPEN,
        )

        tracked_order = self.exchange._order_tracker.fetch_order("OID1")
        tracked_order.current_state = OrderState.OPEN

        self.assertTrue("OID1" in self.exchange._order_tracker._in_flight_orders)

        cancellation_results = await self.exchange.cancel_all(timeout_seconds=1)

        self.assertEqual(1, len(cancellation_results))
        self.assertEqual("OID1", cancellation_results[0].order_id)

        self.assertTrue(self._is_logged(
            "DEBUG",
            "The order OID1 does not exist on Binance Perpetuals. "
            "No cancelation needed."
        ))

        self.assertTrue("OID1" in self.exchange._order_tracker._order_not_found_records)

    @aioresponses()
    async def test_cancel_all_exception(self, req_mock):
        url = web_utils.private_rest_url(
            CONSTANTS.ORDER_URL, domain=self.domain
        )
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        req_mock.delete(regex_url, exception=Exception())

        self.exchange.start_tracking_order(
            order_id="OID1",
            exchange_order_id="8886774",
            trading_pair=self.trading_pair,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("1"),
            order_type=OrderType.LIMIT,
            leverage=1,
            position_action=PositionAction.OPEN,
        )

        tracked_order = self.exchange._order_tracker.fetch_order("OID1")
        tracked_order.current_state = OrderState.OPEN

        self.assertTrue("OID1" in self.exchange._order_tracker._in_flight_orders)

        cancellation_results = await self.exchange.cancel_all(timeout_seconds=1)

        self.assertEqual(1, len(cancellation_results))
        self.assertEqual("OID1", cancellation_results[0].order_id)

        self.assertTrue(self._is_logged(
            "ERROR",
            "Failed to cancel order OID1",
        ))

        self.assertTrue("OID1" in self.exchange._order_tracker._in_flight_orders)

    @aioresponses()
    async def test_cancel_order_successful(self, mock_api):
        self._simulate_trading_rules_initialized()
        url = web_utils.private_rest_url(
            CONSTANTS.ORDER_URL, domain=self.domain
        )
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        cancel_response = {
            "clientOrderId": "ODI1",
            "cumQty": "0",
            "cumQuote": "0",
            "executedQty": "0",
            "orderId": 283194212,
            "origQty": "11",
            "origType": "TRAILING_STOP_MARKET",
            "price": "0",
            "reduceOnly": False,
            "side": "BUY",
            "positionSide": "SHORT",
            "status": "CANCELED",
            "stopPrice": "9300",
            "closePosition": False,
            "symbol": "BTCUSDT",
            "timeInForce": "GTC",
            "type": "TRAILING_STOP_MARKET",
            "activatePrice": "9020",
            "priceRate": "0.3",
            "updateTime": 1571110484038,
            "workingType": "CONTRACT_PRICE",
            "priceProtect": False
        }
        mock_api.delete(regex_url, body=json.dumps(cancel_response))

        self.exchange.start_tracking_order(
            order_id="OID1",
            exchange_order_id="8886774",
            trading_pair=self.trading_pair,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("1"),
            order_type=OrderType.LIMIT,
            leverage=1,
            position_action=PositionAction.OPEN,
        )
        tracked_order = self.exchange._order_tracker.fetch_order("OID1")
        tracked_order.current_state = OrderState.OPEN

        self.assertTrue("OID1" in self.exchange._order_tracker._in_flight_orders)

        canceled_order_id = await self.exchange._execute_cancel(trading_pair=self.trading_pair, order_id="OID1")
        await asyncio.sleep(0.01)

        order_cancelled_events = self.order_cancelled_logger.event_log

        self.assertEqual(1, len(order_cancelled_events))
        self.assertEqual("OID1", canceled_order_id)

    @aioresponses()
    async def test_cancel_order_failed(self, mock_api):
        self._simulate_trading_rules_initialized()
        url = web_utils.private_rest_url(
            CONSTANTS.ORDER_URL, domain=self.domain
        )
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        cancel_response = {
            "clientOrderId": "ODI1",
            "cumQty": "0",
            "cumQuote": "0",
            "executedQty": "0",
            "orderId": 283194212,
            "origQty": "11",
            "origType": "TRAILING_STOP_MARKET",
            "price": "0",
            "reduceOnly": False,
            "side": "BUY",
            "positionSide": "SHORT",
            "status": "FILLED",
            "stopPrice": "9300",
            "closePosition": False,
            "symbol": "BTCUSDT",
            "timeInForce": "GTC",
            "type": "TRAILING_STOP_MARKET",
            "activatePrice": "9020",
            "priceRate": "0.3",
            "updateTime": 1571110484038,
            "workingType": "CONTRACT_PRICE",
            "priceProtect": False
        }
        mock_api.delete(regex_url, body=json.dumps(cancel_response))

        self.exchange.start_tracking_order(
            order_id="OID1",
            exchange_order_id="8886774",
            trading_pair=self.trading_pair,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("1"),
            order_type=OrderType.LIMIT,
            leverage=1,
            position_action=PositionAction.OPEN,
        )
        tracked_order = self.exchange._order_tracker.fetch_order("OID1")
        tracked_order.current_state = OrderState.OPEN

        self.assertTrue("OID1" in self.exchange._order_tracker._in_flight_orders)

        await self.exchange._execute_cancel(trading_pair=self.trading_pair, order_id="OID1")

        order_cancelled_events = self.order_cancelled_logger.event_log

        self.assertEqual(0, len(order_cancelled_events))

    @aioresponses()
    async def test_create_order_successful(self, req_mock):
        url = web_utils.private_rest_url(
            CONSTANTS.ORDER_URL, domain=self.domain
        )
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        create_response = {"updateTime": int(self.start_timestamp),
                           "status": "NEW",
                           "orderId": "8886774"}
        req_mock.post(regex_url, body=json.dumps(create_response))
        self._simulate_trading_rules_initialized()

        await self.exchange._create_order(
            trade_type=TradeType.BUY,
            order_id="OID1",
            trading_pair=self.trading_pair,
            amount=Decimal("10000"),
            order_type=OrderType.LIMIT,
            position_action=PositionAction.OPEN,
            price=Decimal("10000"))

        self.assertTrue("OID1" in self.exchange._order_tracker._in_flight_orders)

    @aioresponses()
    @patch("hummingbot.connector.derivative.binance_perpetual.binance_perpetual_web_utils.get_current_server_time")
    async def test_place_order_manage_server_overloaded_error_unkown_order(self, mock_api, mock_seconds_counter: MagicMock):
        mock_seconds_counter.return_value = 1640780000
        self.exchange._set_current_timestamp(1640780000)
        self.exchange._last_poll_timestamp = (self.exchange.current_timestamp -
                                              self.exchange.UPDATE_ORDER_STATUS_MIN_INTERVAL - 1)
        url = web_utils.private_rest_url(
            CONSTANTS.ORDER_URL, domain=self.domain
        )
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_response = {"code": -1003, "msg": "Unknown error, please check your request or try again later."}

        mock_api.post(regex_url, body=json.dumps(mock_response), status=503)
        self._simulate_trading_rules_initialized()

        o_id, timestamp = await self.exchange._place_order(
            trade_type=TradeType.BUY,
            order_id="OID1",
            trading_pair=self.trading_pair,
            amount=Decimal("10000"),
            order_type=OrderType.LIMIT,
            position_action=PositionAction.OPEN,
            price=Decimal("10000"))
        self.assertEqual(o_id, "UNKNOWN")

    @aioresponses()
    async def test_create_limit_maker_successful(self, req_mock):
        url = web_utils.private_rest_url(
            CONSTANTS.ORDER_URL, domain=self.domain
        )
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        create_response = {"updateTime": int(self.start_timestamp),
                           "status": "NEW",
                           "orderId": "8886774"}
        req_mock.post(regex_url, body=json.dumps(create_response))
        self._simulate_trading_rules_initialized()

        await self.exchange._create_order(
            trade_type=TradeType.BUY,
            order_id="OID1",
            trading_pair=self.trading_pair,
            amount=Decimal("10000"),
            order_type=OrderType.LIMIT_MAKER,
            position_action=PositionAction.OPEN,
            price=Decimal("10000"))

        self.assertTrue("OID1" in self.exchange._order_tracker._in_flight_orders)

    @aioresponses()
    async def test_create_order_exception(self, req_mock):
        url = web_utils.private_rest_url(
            CONSTANTS.ORDER_URL, domain=self.domain
        )
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        req_mock.post(regex_url, exception=Exception())
        self._simulate_trading_rules_initialized()
        await self.exchange._create_order(
            trade_type=TradeType.BUY,
            order_id="OID1",
            trading_pair=self.trading_pair,
            amount=Decimal("10000"),
            order_type=OrderType.LIMIT,
            position_action=PositionAction.OPEN,
            price=Decimal("1010"))
        await asyncio.sleep(0.001)

        self.assertTrue("OID1" not in self.exchange._order_tracker._in_flight_orders)

        # The order amount is quantizied
        # "Error submitting buy LIMIT order to Binance_perpetual for 9999 COINALPHA-HBOT 1010."
        self.assertTrue(self._is_logged(
            "NETWORK",
            f"Error submitting {TradeType.BUY.name.lower()} {OrderType.LIMIT.name.upper()} order to {self.exchange.name_cap} for "
            f"{Decimal('9999')} {self.trading_pair} {Decimal('1010')}.",
        ))

    async def test_create_order_min_order_size_failure(self):
        self._simulate_trading_rules_initialized()
        margin_asset = self.quote_asset
        min_order_size = 3
        mocked_response = self._get_exchange_info_mock_response(margin_asset, min_order_size=min_order_size)
        trading_rules = await self.exchange._format_trading_rules(mocked_response)
        self.exchange._trading_rules[self.trading_pair] = trading_rules[0]
        trade_type = TradeType.BUY
        amount = Decimal("2")

        await self.exchange._create_order(
            trade_type=trade_type,
            order_id="OID1",
            trading_pair=self.trading_pair,
            amount=amount,
            order_type=OrderType.LIMIT,
            position_action=PositionAction.OPEN,
            price=Decimal("1010"))

        await asyncio.sleep(0.001)

        self.assertTrue("OID1" not in self.exchange._order_tracker._in_flight_orders)

        self.assertTrue(self._is_logged(
            "INFO",
            "Order OID1 has failed. Order Update: OrderUpdate(trading_pair='COINALPHA-HBOT', "
            "update_timestamp=1640780000.0, new_state=<OrderState.FAILED: 6>, client_order_id='OID1', "
            "exchange_order_id=None, misc_updates={'error_message': 'Order amount 2 is lower than minimum order size 3 "
            "for the pair COINALPHA-HBOT. The order will not be created.', 'error_type': 'ValueError'})"
        ))

    async def test_create_order_min_notional_size_failure(self):
        margin_asset = self.quote_asset
        min_notional_size = 10
        self._simulate_trading_rules_initialized()
        mocked_response = self._get_exchange_info_mock_response(margin_asset,
                                                                min_notional_size=min_notional_size,
                                                                min_base_amount_increment=0.5)
        trading_rules = await self.exchange._format_trading_rules(mocked_response)
        self.exchange._trading_rules[self.trading_pair] = trading_rules[0]
        trade_type = TradeType.BUY
        amount = Decimal("2")
        price = Decimal("4")

        await self.exchange._create_order(
            trade_type=trade_type,
            order_id="OID1",
            trading_pair=self.trading_pair,
            amount=amount,
            order_type=OrderType.LIMIT,
            position_action=PositionAction.OPEN,
            price=price)
        await asyncio.sleep(0.001)

        self.assertTrue("OID1" not in self.exchange._order_tracker._in_flight_orders)

    async def test_restore_tracking_states_only_registers_open_orders(self):
        orders = []
        orders.append(InFlightOrder(
            client_order_id="OID1",
            exchange_order_id="EOID1",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            amount=Decimal("1000.0"),
            price=Decimal("1.0"),
            creation_timestamp=1640001112.223,
        ))
        orders.append(InFlightOrder(
            client_order_id="OID2",
            exchange_order_id="EOID2",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            amount=Decimal("1000.0"),
            price=Decimal("1.0"),
            creation_timestamp=1640001112.223,
            initial_state=OrderState.CANCELED
        ))
        orders.append(InFlightOrder(
            client_order_id="OID3",
            exchange_order_id="EOID3",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            amount=Decimal("1000.0"),
            price=Decimal("1.0"),
            creation_timestamp=1640001112.223,
            initial_state=OrderState.FILLED
        ))
        orders.append(InFlightOrder(
            client_order_id="OID4",
            exchange_order_id="EOID4",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            amount=Decimal("1000.0"),
            price=Decimal("1.0"),
            creation_timestamp=1640001112.223,
            initial_state=OrderState.FAILED
        ))

        tracking_states = {order.client_order_id: order.to_json() for order in orders}

        self.exchange.restore_tracking_states(tracking_states)

        self.assertIn("OID1", self.exchange.in_flight_orders)
        self.assertNotIn("OID2", self.exchange.in_flight_orders)
        self.assertNotIn("OID3", self.exchange.in_flight_orders)
        self.assertNotIn("OID4", self.exchange.in_flight_orders)

    @patch("hummingbot.connector.utils.get_tracking_nonce")
    async def test_client_order_id_on_order(self, mocked_nonce):
        mocked_nonce.return_value = 4

        result = self.exchange.buy(
            trading_pair=self.trading_pair,
            amount=Decimal("1"),
            order_type=OrderType.LIMIT,
            price=Decimal("2"),
            position_action="OPEN",
        )
        expected_client_order_id = get_new_client_order_id(
            is_buy=True,
            trading_pair=self.trading_pair,
            hbot_order_id_prefix=CONSTANTS.BROKER_ID,
            max_id_len=CONSTANTS.MAX_ORDER_ID_LEN,
        )

        self.assertEqual(result, expected_client_order_id)

        result = self.exchange.sell(
            trading_pair=self.trading_pair,
            amount=Decimal("1"),
            order_type=OrderType.LIMIT,
            price=Decimal("2"),
            position_action="OPEN",
        )
        expected_client_order_id = get_new_client_order_id(
            is_buy=False,
            trading_pair=self.trading_pair,
            hbot_order_id_prefix=CONSTANTS.BROKER_ID,
            max_id_len=CONSTANTS.MAX_ORDER_ID_LEN,
        )

        self.assertEqual(result, expected_client_order_id)

    @aioresponses()
    async def test_update_balances(self, mock_api):
        url = web_utils.public_rest_url(CONSTANTS.SERVER_TIME_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        response = {"serverTime": 1640000003000}

        mock_api.get(regex_url,
                     body=json.dumps(response))

        url = web_utils.private_rest_url(CONSTANTS.ACCOUNT_INFO_URL, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        response = {
            "feeTier": 0,
            "canTrade": True,
            "canDeposit": True,
            "canWithdraw": True,
            "updateTime": 0,
            "totalInitialMargin": "0.00000000",
            "totalMaintMargin": "0.00000000",
            "totalWalletBalance": "23.72469206",
            "totalUnrealizedProfit": "0.00000000",
            "totalMarginBalance": "23.72469206",
            "totalPositionInitialMargin": "0.00000000",
            "totalOpenOrderInitialMargin": "0.00000000",
            "totalCrossWalletBalance": "23.72469206",
            "totalCrossUnPnl": "0.00000000",
            "availableBalance": "23.72469206",
            "maxWithdrawAmount": "23.72469206",
            "assets": [
                {
                    "asset": "USDT",
                    "walletBalance": "23.72469206",
                    "unrealizedProfit": "0.00000000",
                    "marginBalance": "23.72469206",
                    "maintMargin": "0.00000000",
                    "initialMargin": "0.00000000",
                    "positionInitialMargin": "0.00000000",
                    "openOrderInitialMargin": "0.00000000",
                    "crossWalletBalance": "23.72469206",
                    "crossUnPnl": "0.00000000",
                    "availableBalance": "23.72469206",
                    "maxWithdrawAmount": "23.72469206",
                    "marginAvailable": True,
                    "updateTime": 1625474304765,
                },
                {
                    "asset": "BUSD",
                    "walletBalance": "103.12345678",
                    "unrealizedProfit": "0.00000000",
                    "marginBalance": "103.12345678",
                    "maintMargin": "0.00000000",
                    "initialMargin": "0.00000000",
                    "positionInitialMargin": "0.00000000",
                    "openOrderInitialMargin": "0.00000000",
                    "crossWalletBalance": "103.12345678",
                    "crossUnPnl": "0.00000000",
                    "availableBalance": "100.12345678",
                    "maxWithdrawAmount": "103.12345678",
                    "marginAvailable": True,
                    "updateTime": 1625474304765,
                }
            ],
            "positions": [{
                "symbol": "BTCUSDT",
                "initialMargin": "0",
                "maintMargin": "0",
                "unrealizedProfit": "0.00000000",
                "positionInitialMargin": "0",
                "openOrderInitialMargin": "0",
                "leverage": "100",
                "isolated": True,
                "entryPrice": "0.00000",
                "maxNotional": "250000",
                "bidNotional": "0",
                "askNotional": "0",
                "positionSide": "BOTH",
                "positionAmt": "0",
                "updateTime": 0,
            }
            ]
        }

        mock_api.get(regex_url, body=json.dumps(response))
        await self.exchange._update_balances()

        available_balances = self.exchange.available_balances
        total_balances = self.exchange.get_all_balances()

        self.assertEqual(Decimal("23.72469206"), available_balances["USDT"])
        self.assertEqual(Decimal("100.12345678"), available_balances["BUSD"])
        self.assertEqual(Decimal("23.72469206"), total_balances["USDT"])
        self.assertEqual(Decimal("103.12345678"), total_balances["BUSD"])

    @aioresponses()
    @patch("hummingbot.connector.time_synchronizer.TimeSynchronizer._current_seconds_counter")
    async def test_account_info_request_includes_timestamp(self, mock_api, mock_seconds_counter):
        mock_seconds_counter.return_value = 1000

        url = web_utils.public_rest_url(CONSTANTS.SERVER_TIME_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        response = {"serverTime": 1640000003000}

        mock_api.get(regex_url,
                     body=json.dumps(response))

        url = web_utils.private_rest_url(CONSTANTS.ACCOUNT_INFO_URL, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        response = {
            "feeTier": 0,
            "canTrade": True,
            "canDeposit": True,
            "canWithdraw": True,
            "updateTime": 0,
            "totalInitialMargin": "0.00000000",
            "totalMaintMargin": "0.00000000",
            "totalWalletBalance": "23.72469206",
            "totalUnrealizedProfit": "0.00000000",
            "totalMarginBalance": "23.72469206",
            "totalPositionInitialMargin": "0.00000000",
            "totalOpenOrderInitialMargin": "0.00000000",
            "totalCrossWalletBalance": "23.72469206",
            "totalCrossUnPnl": "0.00000000",
            "availableBalance": "23.72469206",
            "maxWithdrawAmount": "23.72469206",
            "assets": [
                {
                    "asset": "USDT",
                    "walletBalance": "23.72469206",
                    "unrealizedProfit": "0.00000000",
                    "marginBalance": "23.72469206",
                    "maintMargin": "0.00000000",
                    "initialMargin": "0.00000000",
                    "positionInitialMargin": "0.00000000",
                    "openOrderInitialMargin": "0.00000000",
                    "crossWalletBalance": "23.72469206",
                    "crossUnPnl": "0.00000000",
                    "availableBalance": "23.72469206",
                    "maxWithdrawAmount": "23.72469206",
                    "marginAvailable": True,
                    "updateTime": 1625474304765,
                },
                {
                    "asset": "BUSD",
                    "walletBalance": "103.12345678",
                    "unrealizedProfit": "0.00000000",
                    "marginBalance": "103.12345678",
                    "maintMargin": "0.00000000",
                    "initialMargin": "0.00000000",
                    "positionInitialMargin": "0.00000000",
                    "openOrderInitialMargin": "0.00000000",
                    "crossWalletBalance": "103.12345678",
                    "crossUnPnl": "0.00000000",
                    "availableBalance": "100.12345678",
                    "maxWithdrawAmount": "103.12345678",
                    "marginAvailable": True,
                    "updateTime": 1625474304765,
                }
            ],
            "positions": [{
                "symbol": "BTCUSDT",
                "initialMargin": "0",
                "maintMargin": "0",
                "unrealizedProfit": "0.00000000",
                "positionInitialMargin": "0",
                "openOrderInitialMargin": "0",
                "leverage": "100",
                "isolated": True,
                "entryPrice": "0.00000",
                "maxNotional": "250000",
                "bidNotional": "0",
                "askNotional": "0",
                "positionSide": "BOTH",
                "positionAmt": "0",
                "updateTime": 0,
            }
            ]
        }

        mock_api.get(regex_url, body=json.dumps(response))
        await self.exchange._update_balances()

        account_request = next(((key, value) for key, value in mock_api.requests.items()
                                if key[1].human_repr().startswith(url)))
        request_params = account_request[1][0].kwargs["params"]
        self.assertIsInstance(request_params["timestamp"], int)

    async def test_limit_orders(self):
        self.exchange.start_tracking_order(
            order_id="OID1",
            exchange_order_id="8886774",
            trading_pair=self.trading_pair,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("1"),
            order_type=OrderType.LIMIT,
            leverage=1,
            position_action=PositionAction.OPEN,
        )
        self.exchange.start_tracking_order(
            order_id="OID2",
            exchange_order_id="8886774",
            trading_pair=self.trading_pair,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("1"),
            order_type=OrderType.LIMIT,
            leverage=1,
            position_action=PositionAction.OPEN,
        )

        limit_orders = self.exchange.limit_orders

        self.assertEqual(len(limit_orders), 2)
        self.assertIsInstance(limit_orders, list)
        self.assertIsInstance(limit_orders[0], LimitOrder)

    def _simulate_trading_rules_initialized(self):
        margin_asset = self.quote_asset
        mocked_response = self._get_exchange_info_mock_response(margin_asset)
        self.exchange._initialize_trading_pair_symbols_from_exchange_info(mocked_response)
        self.exchange._trading_rules = {
            self.trading_pair: TradingRule(
                trading_pair=self.trading_pair,
                min_order_size=Decimal(str(1)),
                min_price_increment=Decimal(str(2)),
                min_base_amount_increment=Decimal(str(3)),
                min_notional_size=Decimal(str(4)),
            )
        }
        return self.exchange._trading_rules
