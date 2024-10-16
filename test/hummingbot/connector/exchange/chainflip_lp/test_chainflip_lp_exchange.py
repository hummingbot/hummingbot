import asyncio
from functools import partial
from test.hummingbot.connector.exchange.chainflip_lp.mock_rpc_executor import MockRPCExecutor
from typing import Any, Callable, Dict, List, Optional, Tuple, Union
from unittest.mock import AsyncMock

from _decimal import Decimal
from aioresponses import aioresponses
from aioresponses.core import RequestCall
from bidict import bidict
from substrateinterface import Keypair

from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.connector.exchange.chainflip_lp import chainflip_lp_constants as CONSTANTS
from hummingbot.connector.exchange.chainflip_lp.chainflip_lp_data_formatter import DataFormatter
from hummingbot.connector.exchange.chainflip_lp.chainflip_lp_exchange import ChainflipLpExchange
from hummingbot.connector.test_support.exchange_connector_test import AbstractExchangeConnectorTests
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState
from hummingbot.core.data_type.trade_fee import TradeFeeBase
from hummingbot.core.event.events import BuyOrderCreatedEvent, MarketOrderFailureEvent
from hummingbot.core.network_iterator import NetworkStatus


class ChainflipLpExchangeTests(AbstractExchangeConnectorTests.ExchangeConnectorTests):
    client_order_id_prefix = "0x"
    exchange_order_id_prefix = "0x"

    @property
    def all_symbols_url(self):
        raise NotImplementedError

    @property
    def latest_prices_url(self):
        raise NotImplementedError

    @property
    def network_status_url(self):
        raise NotImplementedError

    @property
    def trading_rules_url(self):
        raise NotImplementedError

    @property
    def order_creation_url(self):
        raise NotImplementedError

    @property
    def balance_url(self):
        raise NotImplementedError

    @property
    def expected_partial_fill_price(self) -> Decimal:
        raise NotImplementedError

    @property
    def expected_partial_fill_amount(self) -> Decimal:
        raise NotImplementedError

    @property
    def expected_fill_fee(self) -> TradeFeeBase:
        raise NotImplementedError

    @property
    def expected_fill_trade_id(self) -> str:
        raise NotImplementedError

    def validate_auth_credentials_present(self, request_call: RequestCall):
        raise NotImplementedError

    def validate_order_creation_request(self, order: InFlightOrder, request_call: RequestCall):
        raise NotImplementedError

    def validate_order_cancelation_request(self, order: InFlightOrder, request_call: RequestCall):
        raise NotImplementedError

    def validate_order_status_request(self, order: InFlightOrder, request_call: RequestCall):
        raise NotImplementedError

    def validate_trades_request(elf, order: InFlightOrder, request_call: RequestCall):
        raise NotImplementedError

    def configure_order_not_found_error_cancelation_response(
        self,
        order: InFlightOrder,
        mock_api: aioresponses,
        callback: Optional[Callable] = lambda *args, **kwargs: None,
    ) -> str:
        """
        :return: the URL configured for the cancelation
        """
        raise NotImplementedError

    def configure_one_successful_one_erroneous_cancel_all_response(
        self, successful_order: InFlightOrder, erroneous_order: InFlightOrder, mock_api: aioresponses
    ) -> List[str]:
        """
        :return: a list of all configured URLs for the cancelations
        """

    def configure_completely_filled_order_status_response(
        self, order: InFlightOrder, mock_api: aioresponses, callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> List[str]:
        """
        :return: the URL configured
        """
        raise NotImplementedError

    def configure_canceled_order_status_response(
        self, order: InFlightOrder, mock_api: aioresponses, callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> Union[str, List[str]]:
        """
        :return: the URL configured
        """
        raise NotImplementedError

    def configure_open_order_status_response(
        self, order: InFlightOrder, mock_api: aioresponses, callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> List[str]:
        """
        :return: the URL configured
        """
        raise NotImplementedError

    def configure_http_error_order_status_response(
        self, order: InFlightOrder, mock_api: aioresponses, callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> str:
        """
        :return: the URL configured
        """
        raise NotImplementedError

    def configure_partially_filled_order_status_response(
        self, order: InFlightOrder, mock_api: aioresponses, callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> str:
        """
        :return: the URL configured
        """
        raise NotImplementedError

    def configure_order_not_found_error_order_status_response(
        self,
        order: InFlightOrder,
        mock_api: aioresponses,
        callback: Optional[Callable] = lambda *args, **kwargs: None,
    ) -> List[str]:
        """
        :return: the URL configured
        """
        raise NotImplementedError

    def configure_partial_fill_trade_response(
        self, order: InFlightOrder, mock_api: aioresponses, callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> str:
        """
        :return: the URL configured
        """
        raise NotImplementedError

    def configure_erroneous_http_fill_trade_response(
        self, order: InFlightOrder, mock_api: aioresponses, callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> str:
        """
        :return: the URL configured
        """
        raise NotImplementedError

    def configure_full_fill_trade_response(
        self, order: InFlightOrder, mock_api: aioresponses, callback: Optional[Callable] = None
    ) -> str:
        """
        :return: the URL configured
        """
        raise NotImplementedError

    def order_event_for_new_order_websocket_update(self, order: InFlightOrder):
        raise NotImplementedError

    def order_event_for_canceled_order_websocket_update(self, order: InFlightOrder):
        raise NotImplementedError

    def order_event_for_full_fill_websocket_update(self, order: InFlightOrder):
        raise NotImplementedError

    def trade_event_for_full_fill_websocket_update(self, order: InFlightOrder):
        return None

    @property
    def exchange_trading_pair(self) -> str:
        return self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset)

    @property
    def expected_trading_rule(self):
        trading_rule = TradingRule(
            trading_pair=self.trading_pair,
            min_order_size=0,
            max_order_size=10**6,
            min_price_increment=Decimal("0.00001"),
            min_base_amount_increment=Decimal("0.00001"),
            min_quote_amount_increment=Decimal("0.00001"),
        )
        return trading_rule

    @property
    def all_assets_mock_response(self):
        return [
            {"chain": "Ethereum", "asset": self.quote_asset},
            {"chain": "Ethereum", "asset": self.base_asset},
        ]

    @property
    def place_order_mock_response(self):
        return {
            "result": {
                "tx_details": {
                    "tx_hash": "0x3cb78cdbbfc34634e33d556a94ee7438938b65a5b852ee523e4fc3c0ec3f8151",  # noqa: mock
                    "response": [
                        {
                            "base_asset": "ETH",
                            "quote_asset": "USDC",
                            "side": "buy",
                            "id": "0x11",  # noqa: mock
                            "tick": 50,
                            "sell_amount_total": "0x100000",  # noqa: mock
                            "collected_fees": "0x0",  # noqa: mock
                            "bought_amount": "0x0",  # noqa: mock
                            "sell_amount_change": {"increase": "0x100000"},  # noqa: mock
                        }
                    ],
                }
            },
        }

    @property
    def all_symbols_request_mock_response(self):
        response = {
            "result": {
                "fees": {
                    "Ethereum": {
                        self.base_asset: {
                            "limit_order_fee_hundredth_pips": 500,
                            "range_order_fee_hundredth_pips": 500,
                            "range_order_total_fees_earned": {
                                "base": "0x3d4a754fc1d2302",  # noqa: mock
                                "quote": "0x3689782a",  # noqa: mock
                            },
                            "limit_order_total_fees_earned": {
                                "base": "0x83c94dd54804790a",  # noqa: mock
                                "quote": "0x670a76ae0",  # noqa: mock
                            },
                            "range_total_swap_inputs": {
                                "base": "0x1dc18b046dde67f2b0",  # noqa: mock
                                "quote": "0x1a774f80e62",  # noqa: mock
                            },
                            "limit_total_swap_inputs": {
                                "base": "0x369c2e5bafeffddab46",  # noqa: mock
                                "quote": "0x2be491b4d31d",  # noqa: mock
                            },
                            "quote_asset": {"chain": "Ethereum", "asset": self.quote_asset},
                        },
                    }
                }
            }
        }
        return response

    @property
    def latest_prices_request_mock_response(self):
        response = {
            "result": {
                "base_asset": {"chain": "Ethereum", "asset": "ETH"},
                "quote_asset": {"chain": "Ethereum", "asset": "USDC"},
                "sell": "0x3bc9b4d35fc93990865a6",  # noqa: mock
                "buy": "0x3baddb29af3e837abc358",  # noqa: mock
                "range_order": "0x3bc9b4d35fc93990865a6",  # noqa: mock
            }
        }

        return response

    @property
    def all_symbols_including_invalid_pair_mock_response(self) -> Tuple[str, Any]:
        response = {
            "result": {
                "fees": {
                    "Ethereum": {
                        self.base_asset: {
                            "limit_order_fee_hundredth_pips": 500,
                            "range_order_fee_hundredth_pips": 500,
                            "range_order_total_fees_earned": {
                                "base": "0x3d4a754fc1d2302",  # noqa: mock
                                "quote": "0x3689782a",  # noqa: mock
                            },
                            "limit_order_total_fees_earned": {
                                "base": "0x83c94dd54804790a",  # noqa: mock
                                "quote": "0x670a76ae0",  # noqa: mock
                            },
                            "range_total_swap_inputs": {
                                "base": "0x1dc18b046dde67f2b0",  # noqa: mock
                                "quote": "0x1a774f80e62",  # noqa: mock
                            },
                            "limit_total_swap_inputs": {
                                "base": "0x369c2e5bafeffddab46",  # noqa: mock
                                "quote": "0x2be491b4d31d",  # noqa: mock
                            },
                            "quote_asset": {"chain": "Ethereum", "asset": self.quote_asset},
                        },
                        "INVALID": {
                            "limit_order_fee_hundredth_pips": 500,
                            "range_order_fee_hundredth_pips": 500,
                            "range_order_total_fees_earned": {
                                "base": "0x3d4a754fc1d2302",  # noqa: mock
                                "quote": "0x3689782a",  # noqa: mock
                            },
                            "limit_order_total_fees_earned": {
                                "base": "0x83c94dd54804790a",  # noqa: mock
                                "quote": "0x670a76ae0",  # noqa: mock
                            },
                            "range_total_swap_inputs": {
                                "base": "0x1dc18b046dde67f2b0",  # noqa: mock
                                "quote": "0x1a774f80e62",  # noqa: mock
                            },
                            "limit_total_swap_inputs": {
                                "base": "0x369c2e5bafeffddab46",  # noqa: mock
                                "quote": "0x2be491b4d31d",  # noqa: mock
                            },
                            "quote_asset": {"chain": "Ethereum", "asset": "PAIR"},
                        },
                    }
                }
            }
        }

        return "INVALID-PAIR", response

    @property
    def network_status_request_successful_mock_response(self):
        return True

    @property
    def trading_rules_request_mock_response(self):
        raise NotImplementedError

    @property
    def trading_rules_request_erroneous_mock_response(self):
        raise NotImplementedError

    @property
    def order_creation_request_successful_mock_response(self):
        response = {
            "result": {
                "tx_details": {
                    "tx_hash": "0x3cb78cdbbfc34634e33d556a94ee7438938b65a5b852ee523e4fc3c0ec3f8151",  # noqa: mock
                    "response": [
                        {
                            "base_asset": self.base_asset,
                            "quote_asset": self.quote_asset,
                            "side": "buy",
                            "id": "0x11",  # noqa: mock
                            "tick": 50,
                            "sell_amount_total": "0x100000",  # noqa: mock
                            "collected_fees": "0x0",  # noqa: mock
                            "bought_amount": "0x0",  # noqa: mock
                            "sell_amount_change": {"increase": "0x100000"},  # noqa: mock
                        }
                    ],
                }
            },
        }
        return response

    @property
    def balance_request_mock_response_for_base_and_quote(self):
        response = {
            "result": {
                "Ethereum": {
                    "ETH": "0x2386f26fc0bda2",  # noqa: mock
                    "FLIP": "0xde0b6b3a763ec60",  # noqa: mock
                    "USDC": "0x8bb50bca00",  # noqa: mock
                },
            }
        }
        return response

    @property
    def balance_request_mock_response_only_base(self):
        response = {"result": {"Ethereum": {"ETH": "0x2386f26fc0bda2"}}}  # noqa: mock
        return response

    @property
    def balance_event_websocket_update(self):
        response = {
            "result": {
                "Ethereum": [
                    {"asset": self.base_asset, "balance": "0x2386f26fc0bda2"},  # noqa: mock
                    {"asset": self.quote_asset, "balance": "0x8bb50bca00"},  # noqa: mock
                ]
            },
        }
        return response

    @property
    def expected_latest_price(self):
        return 9999.9

    @property
    def expected_supported_order_types(self):
        return [OrderType.LIMIT]

    @property
    def expected_logged_error_for_erroneous_trading_rule(self):
        erroneous_rule = self.trading_rules_request_erroneous_mock_response["symbols"][0]
        return f"Error parsing the trading pair rule {erroneous_rule}. Skipping."

    @property
    def is_order_fill_http_update_included_in_status_update(self) -> bool:
        return True

    @property
    def is_order_fill_http_update_executed_during_websocket_order_event_processing(self) -> bool:
        return False

    @property
    def expected_exchange_order_id(self):
        return "0x11"  # noqa: mock

    def exchange_symbol_for_tokens(self, base_token: str, quote_token: str) -> str:
        return f"{base_token}-{quote_token}"

    def create_exchange_instance(self):
        client_config_map = ClientConfigAdapter(ClientConfigMap())
        exchange = ChainflipLpExchange(
            client_config_map=client_config_map,
            chainflip_lp_api_url="",
            chainflip_lp_address=self._address,
            chainflip_eth_chain=self._eth_chain,
            chainflip_usdc_chain=self._usdc_chain,
            trading_pairs=[self.trading_pair],
        )
        exchange._data_source._rpc_executor = MockRPCExecutor()
        return exchange

    def configure_no_fills_trade_response(self):
        order_fills_response = []
        self.exchange._data_source._rpc_executor._order_fills_responses.put_nowait(order_fills_response)

    def configure_all_symbols_response(
        self, mock_api: aioresponses, callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> str:
        all_assets_mock_response = self.all_assets_mock_response
        self.exchange._data_source._rpc_executor._all_assets_responses.put_nowait(all_assets_mock_response)
        response = self.all_symbols_request_mock_response
        self.exchange._data_source._rpc_executor._all_markets_responses.put_nowait(response)
        return ""

    def configure_successful_creation_order_status_response(
        self, callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> str:
        all_assets_mock_response = {"result": self.all_assets_mock_response}
        self.exchange._data_source._rpc_executor._all_assets_responses.put_nowait(all_assets_mock_response)
        self.exchange._data_source._rpc_executor._check_connection_response.put_nowait(True)
        mock_queue = AsyncMock()
        mock_queue.get.side_effect = partial(
            self._callback_wrapper_with_response, callback=callback, response=self.place_order_mock_response
        )
        self.exchange._data_source._rpc_executor._place_order_responses = mock_queue
        return ""

    def configure_erroneous_creation_order_status_response(
        self, callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> str:
        all_assets_mock_response = {"result": self.all_assets_mock_response}
        self.exchange._data_source._rpc_executor._all_assets_responses.put_nowait(all_assets_mock_response)
        creation_response = False
        mock_queue = AsyncMock()
        mock_queue.get.side_effect = partial(
            self._callback_wrapper_with_response, callback=callback, response=creation_response
        )
        self.exchange._data_source._rpc_executor._place_order_responses = mock_queue
        return ""

    def configure_successful_cancelation_response(
        self, order: InFlightOrder, mock_api: aioresponses, callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> str:
        all_assets_mock_response = {"result": self.all_assets_mock_response}
        self.exchange._data_source._rpc_executor._all_assets_responses.put_nowait(all_assets_mock_response)
        response = self._order_cancelation_request_successful_mock_response(order=order)
        mock_queue = AsyncMock()
        mock_queue.get.side_effect = partial(self._callback_wrapper_with_response, callback=callback, response=response)
        self.exchange._data_source._rpc_executor._cancel_order_responses = mock_queue
        return ""

    def configure_erroneous_cancelation_response(
        self, order: InFlightOrder, mock_api: aioresponses, callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> str:
        response = False
        mock_queue = AsyncMock()
        mock_queue.get.side_effect = partial(self._callback_wrapper_with_response, callback=callback, response=response)
        self.exchange._data_source._rpc_executor._cancel_order_responses = mock_queue
        return ""

    def _configure_balance_response(
        self,
        response: Dict[str, Any],
        mock_api: aioresponses,
        callback: Optional[Callable] = lambda *args, **kwargs: None,
    ) -> str:
        all_assets_mock_response = self.all_assets_mock_response
        self.exchange._data_source._rpc_executor._all_assets_responses.put_nowait(all_assets_mock_response)
        self.exchange._data_source._rpc_executor._balances_responses.put_nowait(response)
        return ""

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()

        cls._address = Keypair.create_from_mnemonic(
            "hollow crack grain grab equal rally ceiling manage goddess grass negative canal"  # noqa: mock
        ).ss58_address
        cls._eth_chain = CONSTANTS.DEFAULT_CHAIN_CONFIG["ETH"]
        cls._usdc_chain = CONSTANTS.DEFAULT_CHAIN_CONFIG["USDC"]
        cls.base_asset_dict = {"chain": "Ethereum", "asset": "ETH"}
        cls.quote_asset_dict = {"chain": "Ethereum", "asset": "USDC"}
        cls.base_asset = "ETH"
        cls.quote_asset = "USDC"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.ex_trading_pair = f"{cls.base_asset}-{cls.quote_asset}"

    def setUp(self):
        super().setUp()
        self._original_async_loop = asyncio.get_event_loop()
        self.async_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.async_loop)
        self._logs_event: Optional[asyncio.Event] = None
        self.exchange._data_source.logger().setLevel(1)
        self.exchange._data_source.logger().addHandler(self)
        self.exchange._set_trading_pair_symbol_map(bidict({self.exchange_trading_pair: self.trading_pair}))

    def tearDown(self) -> None:
        super().tearDown()
        self.async_loop.stop()
        self.async_loop.close()
        asyncio.set_event_loop(self._original_async_loop)
        self._logs_event = None

    def handle(self, record):
        super().handle(record=record)
        if self._logs_event is not None:
            self._logs_event.set()

    def reset_log_event(self):
        if self._logs_event is not None:
            self._logs_event.clear()

    async def wait_for_a_log(self):
        if self._logs_event is not None:
            await self._logs_event.wait()

    @aioresponses()
    def test_check_network_success(self, mock_api):
        self.exchange._data_source._rpc_executor._check_connection_response.put_nowait(True)
        network_status = self.async_run_with_timeout(coroutine=self.exchange.check_network())
        self.assertEqual(NetworkStatus.CONNECTED, network_status)

    @aioresponses()
    def test_check_network_failure(self, mock_api):
        self.exchange._data_source._rpc_executor._check_connection_response.put_nowait(False)

        ret = self.async_run_with_timeout(coroutine=self.exchange.check_network())

        self.assertEqual(ret, NetworkStatus.NOT_CONNECTED)

    @aioresponses()
    def test_check_network_raises_cancel_exception(self, mock_api):
        mock_queue = AsyncMock()
        mock_queue.get.side_effect = asyncio.CancelledError
        self.exchange._data_source._rpc_executor._check_connection_response = mock_queue

        self.assertRaises(asyncio.CancelledError, self.async_run_with_timeout, self.exchange.check_network())

    @aioresponses()
    def test_get_last_trade_prices(self, mock_api):
        response = self.latest_prices_request_mock_response
        asset_response = self.all_assets_mock_response
        self.exchange._data_source._rpc_executor._get_market_price_responses.put_nowait(response)
        self.exchange._data_source._rpc_executor._all_assets_responses.put_nowait(asset_response)
        formatted_response = DataFormatter.format_market_price(response)

        latest_prices: Dict[str, float] = self.async_run_with_timeout(
            self.exchange.get_last_traded_prices(trading_pairs=[self.trading_pair])
        )

        self.assertEqual(1, len(latest_prices))
        self.assertEqual(formatted_response["price"], latest_prices[self.trading_pair])

    @aioresponses()
    def test_all_trading_pairs(self, mock_api):
        self.exchange._set_trading_pair_symbol_map(None)

        self.configure_all_symbols_response(mock_api=mock_api)

        all_trading_pairs = self.async_run_with_timeout(coroutine=self.exchange.all_trading_pairs())

        expected_valid_trading_pairs = self._expected_valid_trading_pairs()

        self.assertEqual(len(expected_valid_trading_pairs), len(all_trading_pairs))
        for trading_pair in expected_valid_trading_pairs:
            self.assertIn(trading_pair, all_trading_pairs)

    @aioresponses()
    def test_invalid_trading_pair_not_in_all_trading_pairs(self, mock_api):
        all_assets_mock_response = self.all_assets_mock_response
        self.exchange._data_source._rpc_executor._all_assets_responses.put_nowait(all_assets_mock_response)
        invalid_pair, response = self.all_symbols_including_invalid_pair_mock_response
        self.exchange._data_source._rpc_executor._all_markets_responses.put_nowait(response)

        all_trading_pairs = self.async_run_with_timeout(coroutine=self.exchange.all_trading_pairs())

        self.assertNotIn(invalid_pair, all_trading_pairs)

    @aioresponses()
    def test_all_trading_pairs_does_not_raise_exception(self, mock_api):
        self.exchange._set_trading_pair_symbol_map(None)
        self.exchange._data_source._assets_list = []
        queue_mock = AsyncMock()
        queue_mock.return_value = []
        self.exchange._data_source._rpc_executor._all_markets_responses = queue_mock

        result: List[str] = self.async_run_with_timeout(self.exchange.all_trading_pairs())

        self.assertEqual(0, len(result))

    def test_is_exception_related_to_time_synchronizer_returns_false(self):
        self.assertFalse(self.exchange._is_request_exception_related_to_time_synchronizer(request_exception=None))

    def test_create_user_stream_tracker_task(self):
        self.assertIsNone(self.exchange._create_user_stream_tracker_task())

    @aioresponses()
    def test_create_buy_limit_order_successfully(self, mock_api):
        self._simulate_trading_rules_initialized()
        request_sent_event = asyncio.Event()
        self.exchange._set_current_timestamp(1640780000)

        self.configure_successful_creation_order_status_response(
            callback=lambda *args, **kwargs: request_sent_event.set()
        )

        order_id = self.place_buy_order()
        self.async_run_with_timeout(request_sent_event.wait())

        self.assertIn(order_id, self.exchange.in_flight_orders)

        create_event: BuyOrderCreatedEvent = self.buy_order_created_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp, create_event.timestamp)
        self.assertEqual(self.trading_pair, create_event.trading_pair)
        self.assertEqual(OrderType.LIMIT, create_event.type)
        self.assertEqual(Decimal("100"), create_event.amount)
        self.assertEqual(Decimal("10000"), create_event.price)
        self.assertEqual(order_id, create_event.order_id)
        self.assertEqual(str(self.expected_exchange_order_id), create_event.exchange_order_id)

        self.assertTrue(
            self.is_logged(
                "INFO",
                f"Created {OrderType.LIMIT.name} {TradeType.BUY.name} order {order_id} for "
                f"{Decimal('100.000000')} {self.trading_pair} at {Decimal('10000.0000')}.",
            )
        )

    @aioresponses()
    def test_create_sell_limit_order_successfully(self, mock_api):
        self._simulate_trading_rules_initialized()
        request_sent_event = asyncio.Event()
        self.exchange._set_current_timestamp(1640780000)

        self.configure_successful_creation_order_status_response(
            callback=lambda *args, **kwargs: request_sent_event.set()
        )

        order_id = self.place_sell_order()
        self.async_run_with_timeout(request_sent_event.wait())

        self.assertIn(order_id, self.exchange.in_flight_orders)

        create_event: BuyOrderCreatedEvent = self.sell_order_created_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp, create_event.timestamp)
        self.assertEqual(self.trading_pair, create_event.trading_pair)
        self.assertEqual(OrderType.LIMIT, create_event.type)
        self.assertEqual(Decimal("100"), create_event.amount)
        self.assertEqual(Decimal("10000"), create_event.price)
        self.assertEqual(order_id, create_event.order_id)
        self.assertEqual(str(self.expected_exchange_order_id), create_event.exchange_order_id)

    def test_create_order_fails_and_raises_failure_event(self):
        self._simulate_trading_rules_initialized()
        request_sent_event = asyncio.Event()
        self.exchange._set_current_timestamp(1640780000)

        self.configure_erroneous_creation_order_status_response(
            callback=lambda *args, **kwargs: request_sent_event.set()
        )
        order_id = self.place_buy_order()
        self.async_run_with_timeout(request_sent_event.wait())

        self.assertNotIn(order_id, self.exchange.in_flight_orders)
        self.assertEqual(0, len(self.buy_order_created_logger.event_log))
        failure_event: MarketOrderFailureEvent = self.order_failure_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp, failure_event.timestamp)
        self.assertEqual(OrderType.LIMIT, failure_event.order_type)
        self.assertEqual(order_id, failure_event.order_id)

        self.assertTrue(
            self.is_logged(
                "INFO",
                f"Order {order_id} has failed. Order Update: OrderUpdate(trading_pair='{self.trading_pair}', "
                f"update_timestamp={self.exchange.current_timestamp}, new_state={repr(OrderState.FAILED)}, "
                f"client_order_id='{order_id}', exchange_order_id=None, misc_updates=None)",
            )
        )

    @aioresponses()
    def test_cancel_order_successfully(self, mock_api):
        request_sent_event = asyncio.Event()
        self.exchange._set_current_timestamp(1640780000)

        self.exchange.start_tracking_order(
            order_id=self.client_order_id_prefix + "1",
            exchange_order_id=self.exchange_order_id_prefix + "1",
            trading_pair=self.trading_pair,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("100"),
            order_type=OrderType.LIMIT,
        )

        self.assertIn(self.client_order_id_prefix + "1", self.exchange.in_flight_orders)
        order: InFlightOrder = self.exchange.in_flight_orders[self.client_order_id_prefix + "1"]

        self.configure_successful_cancelation_response(
            order=order, mock_api=mock_api, callback=lambda *args, **kwargs: request_sent_event.set()
        )

        self.exchange.cancel(trading_pair=order.trading_pair, client_order_id=order.client_order_id)

        self.async_run_with_timeout(request_sent_event.wait())

        self.assertNotIn(order.client_order_id, self.exchange.in_flight_orders)

    @aioresponses()
    def test_update_balances(self, mock_api):
        response = self.balance_request_mock_response_for_base_and_quote
        formmatted_data = DataFormatter.format_balance_response(response)
        self._configure_balance_response(response=response, mock_api=mock_api)

        self.async_run_with_timeout(self.exchange._update_balances())

        available_balances = self.exchange.available_balances
        total_balances = self.exchange.get_all_balances()

        base_asset_key = f"{self.base_asset}"
        quote_asset_key = f"{self.quote_asset}"

        self.assertEqual(formmatted_data[base_asset_key], available_balances[base_asset_key])
        self.assertEqual(formmatted_data[quote_asset_key], available_balances[quote_asset_key])
        self.assertEqual(formmatted_data[base_asset_key], total_balances[base_asset_key])
        self.assertEqual(formmatted_data[quote_asset_key], total_balances[quote_asset_key])

        response = self.balance_request_mock_response_only_base

        self._configure_balance_response(response=response, mock_api=mock_api)
        self.async_run_with_timeout(self.exchange._update_balances())

        formmatted_data = DataFormatter.format_balance_response(response)

        available_balances = self.exchange.available_balances
        total_balances = self.exchange.get_all_balances()
        self.assertNotIn(quote_asset_key, available_balances)
        self.assertNotIn(quote_asset_key, total_balances)
        self.assertEqual(formmatted_data[base_asset_key], available_balances[base_asset_key])
        self.assertEqual(formmatted_data[base_asset_key], total_balances[base_asset_key])

    @aioresponses()
    def test_update_trading_rules(self, mock_api):
        self.exchange._set_current_timestamp(1000)

        all_assets_mock_response = {"result": self.all_assets_mock_response}
        self.exchange._data_source._rpc_executor._all_assets_responses.put_nowait(all_assets_mock_response)
        response = self.all_symbols_request_mock_response
        self.exchange._data_source._rpc_executor._all_markets_responses.put_nowait(response)

        self.async_run_with_timeout(coroutine=self.exchange._update_trading_rules())

        self.assertTrue(self.trading_pair in self.exchange.trading_rules)
        trading_rule: TradingRule = self.exchange.trading_rules[self.trading_pair]

        self.assertTrue(self.trading_pair in self.exchange.trading_rules)
        self.assertEqual(repr(self.expected_trading_rule), repr(trading_rule))

    @aioresponses()
    def test_update_trading_rules_ignores_rule_with_error(self, mock_api):
        # no trading rules in chainflip lp
        pass

    @aioresponses()
    def test_create_order_fails_when_trading_rule_error_and_raises_failure_event(self, mock_api):
        # no trading rules in chainflip LP
        pass

    @aioresponses()
    def test_cancel_order_raises_failure_event_when_request_fails(self, mock_api):
        # no error being raised so test can be ignored
        pass

    @aioresponses()
    def test_cancel_order_not_found_in_the_exchange(self, mock_api):
        pass

    @aioresponses()
    def test_cancel_two_orders_with_cancel_all_and_one_fails(self, mock_api):
        pass

    @aioresponses()
    def test_update_order_status_when_filled(self, mock_api):
        pass

    @aioresponses()
    def test_update_order_status_when_canceled(self, mock_api):
        pass

    @aioresponses()
    def test_update_order_status_when_order_has_not_changed(self, mock_api):
        pass

    @aioresponses()
    def test_update_order_status_when_request_fails_marks_order_as_not_found(self, mock_api):
        pass

    @aioresponses()
    def test_update_order_status_when_order_has_not_changed_and_one_partial_fill(self, mock_api):
        pass

    @aioresponses()
    def test_update_order_status_when_filled_correctly_processed_even_when_trade_fill_update_fails(self, mock_api):
        pass

    def test_user_stream_update_for_new_order(self):
        pass

    def test_user_stream_update_for_canceled_order(self):
        pass

    @aioresponses()
    def test_user_stream_update_for_order_full_fill(self, mock_api):
        pass

    def test_user_stream_balance_update(self):
        pass

    def test_user_stream_raises_cancel_exception(self):
        pass

    def test_user_stream_logs_errors(self):
        pass

    @aioresponses()
    def test_lost_order_included_in_order_fills_update_and_not_in_order_status_update(self, mock_api):
        pass

    @aioresponses()
    def test_cancel_lost_order_successfully(self, mock_api):
        pass

    @aioresponses()
    def test_cancel_lost_order_raises_failure_event_when_request_fails(self, mock_api):
        pass

    @aioresponses()
    def test_lost_order_removed_if_not_found_during_order_status_update(self, mock_api):
        pass

    def test_lost_order_removed_after_cancel_status_user_event_received(self):
        pass

    @aioresponses()
    def test_lost_order_user_stream_full_fill_events_are_processed(self, mock_api):
        pass

    def _order_cancelation_request_successful_mock_response(self, order: InFlightOrder) -> Any:
        return True

    @staticmethod
    def _callback_wrapper_with_response(callback: Callable, response: Any, *args, **kwargs):
        callback(args, kwargs)
        if isinstance(response, Exception):
            raise response
        else:
            return response

    def _exchange_order_id(self, order_number: int) -> str:
        template_exchange_id = self.expected_exchange_order_id
        digits = len(str(order_number))
        prefix = template_exchange_id[:-digits]
        return f"{prefix}{order_number}"
