import asyncio
import json
from functools import partial
from test.hummingbot.connector.exchange.polkadex.programmable_query_executor import ProgrammableQueryExecutor
from typing import Any, Callable, Dict, List, Optional, Tuple
from unittest.mock import AsyncMock, MagicMock, patch

from _decimal import Decimal
from aioresponses import aioresponses
from aioresponses.core import RequestCall
from bidict import bidict
from substrateinterface import SubstrateInterface

from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.connector.exchange.polkadex.polkadex_exchange import PolkadexExchange
from hummingbot.connector.test_support.exchange_connector_test import AbstractExchangeConnectorTests
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState
from hummingbot.core.data_type.trade_fee import AddedToCostTradeFee, TokenAmount, TradeFeeBase
from hummingbot.core.event.events import (
    BuyOrderCompletedEvent,
    BuyOrderCreatedEvent,
    MarketOrderFailureEvent,
    OrderCancelledEvent,
    OrderFilledEvent,
    SellOrderCreatedEvent,
)
from hummingbot.core.network_iterator import NetworkStatus


class PolkadexExchangeTests(AbstractExchangeConnectorTests.ExchangeConnectorTests):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls._seed_phrase = (
            "hollow crack grain grab equal rally ceiling manage goddess grass negative canal"  # noqa: mock
        )

    def setUp(self) -> None:
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
    def all_assets_mock_response(self):
        return {
            "getAllAssets": {
                "items": [
                    {"asset_id": "1", "name": self.quote_asset},
                    {"asset_id": self.base_asset, "name": self.base_asset},
                ]
            }
        }

    @property
    def all_symbols_request_mock_response(self):
        return {
            "getAllMarkets": {
                "items": [
                    {
                        "base_asset_precision": "8",
                        "market": self.exchange_trading_pair,
                        "max_order_price": "10000",
                        "max_order_qty": "20000",
                        "min_order_price": "2.0E-4",
                        "min_order_qty": "0.001",
                        "price_tick_size": "1.0E-4",
                        "qty_step_size": "0.0001",
                        "quote_asset_precision": "8",
                    }
                ]
            }
        }

    @property
    def latest_prices_request_mock_response(self):
        return {
            "getRecentTrades": {
                "items": [
                    {
                        "isReverted": None,
                        "m": None,
                        "p": str(self.expected_latest_price),
                        "q": "1",
                        "t": "1668606574722",
                        "sid": 896,
                    },
                ]
            }
        }

    @property
    def all_symbols_including_invalid_pair_mock_response(self) -> Tuple[str, Any]:
        response = {
            "getAllMarkets": {
                "items": [
                    {
                        "base_asset_precision": "8",
                        "market": self.exchange_trading_pair,
                        "max_order_price": "10000",
                        "max_order_qty": "10000",
                        "min_order_price": "1.0E-4",
                        "min_order_qty": "0.001",
                        "price_tick_size": "1.0E-4",
                        "qty_step_size": "0.001",
                        "quote_asset_precision": "8",
                    },
                    {
                        "base_asset_precision": "8",
                        "market": "INVALID-1",
                        "max_order_price": "10000",
                        "max_order_qty": "10000",
                        "min_order_price": "1.0E-4",
                        "min_order_qty": "0.001",
                        "price_tick_size": "1.0E-4",
                        "qty_step_size": "0.001",
                        "quote_asset_precision": "8",
                    },
                ]
            }
        }

        return "INVALID-1", response

    @property
    def network_status_request_successful_mock_response(self):
        raise NotImplementedError

    @property
    def trading_rules_request_mock_response(self):
        return self.all_symbols_request_mock_response

    @property
    def trading_rules_request_erroneous_mock_response(self):
        return {
            "getAllMarkets": {
                "items": [
                    {
                        "base_asset_precision": "8",
                        "market": self.exchange_trading_pair,
                    }
                ]
            }
        }

    @property
    def order_creation_request_successful_mock_response(self):
        return {"place_order": self.expected_exchange_order_id}

    @property
    def balance_request_mock_response_for_base_and_quote(self):
        return {
            "getAllBalancesByMainAccount": {
                "items": [
                    {
                        "a": self.base_asset,
                        "f": "10.0000",
                        "r": "5",
                    },
                    {
                        "a": "1",
                        "f": "2000",
                        "r": "0",
                    },
                ]
            }
        }

    @property
    def balance_request_mock_response_only_base(self):
        return {
            "getAllBalancesByMainAccount": {
                "items": [
                    {
                        "a": self.base_asset,
                        "f": "10.0000",
                        "r": "5",
                    },
                ]
            }
        }

    @property
    def balance_event_websocket_update(self):
        data = {
            "type": "SetBalance",
            "snapshot_number": 50133,
            "event_id": 4300053,
            "user": "5C5ZpV7Hunb7yG2CwDtnhxaYc3aug4UTLxRvu6HERxJqrtJY",
            "asset": {"asset": self.base_asset},
            "free": "10",
            "pending_withdrawal": "0",
            "reserved": "5",
        }

        return {
            "websocket_streams": {
                "data": json.dumps(data),
            }
        }

    @property
    def expected_latest_price(self):
        return 9999.9

    @property
    def expected_supported_order_types(self):
        return [OrderType.LIMIT, OrderType.MARKET]

    @property
    def expected_trading_rule(self):
        market_info = self.all_symbols_request_mock_response["getAllMarkets"]["items"][0]
        trading_pair = self.trading_pair
        min_order_size = Decimal(market_info["min_order_qty"])
        max_order_size = Decimal(market_info["max_order_qty"])
        min_order_price = Decimal(market_info["min_order_price"])
        amount_increment = Decimal(market_info["qty_step_size"])
        price_increment = Decimal(market_info["price_tick_size"])
        trading_rule = TradingRule(
            trading_pair=trading_pair,
            min_order_size=min_order_size,
            max_order_size=max_order_size,
            min_price_increment=price_increment,
            min_base_amount_increment=amount_increment,
            min_quote_amount_increment=price_increment,
            min_notional_size=min_order_size * min_order_price,
            min_order_value=min_order_size * min_order_price,
        )

        return trading_rule

    @property
    def expected_logged_error_for_erroneous_trading_rule(self):
        erroneous_rule = self.trading_rules_request_erroneous_mock_response["getAllMarkets"]["items"][0]
        return f"Error parsing the trading pair rule: {erroneous_rule}. Skipping..."

    @property
    def expected_exchange_order_id(self):
        return "0x1b99cba5555ad0ba890756fe16e499cb884b46a165b89bdce77ee8913b55ffff"  # noqa: mock

    @property
    def is_order_fill_http_update_included_in_status_update(self) -> bool:
        return False

    @property
    def is_order_fill_http_update_executed_during_websocket_order_event_processing(self) -> bool:
        raise NotImplementedError

    @property
    def expected_partial_fill_price(self) -> Decimal:
        return Decimal("10500")

    @property
    def expected_partial_fill_amount(self) -> Decimal:
        return Decimal("0.5")

    @property
    def expected_partial_fill_fee(self) -> TradeFeeBase:
        return AddedToCostTradeFee(
            percent_token=self.quote_asset, flat_fees=[TokenAmount(token=self.quote_asset, amount=Decimal("10"))]
        )

    @property
    def expected_fill_fee(self) -> TradeFeeBase:
        return AddedToCostTradeFee(
            percent_token=self.quote_asset, flat_fees=[TokenAmount(token=self.quote_asset, amount=Decimal("30"))]
        )

    @property
    def expected_fill_trade_id(self) -> str:
        return "9999"

    @property
    def exchange_trading_pair(self) -> str:
        return self.exchange_symbol_for_tokens(self.base_asset, "1")

    def exchange_symbol_for_tokens(self, base_token: str, quote_token: str) -> str:
        return f"{base_token}-{quote_token}"

    def create_exchange_instance(self):
        client_config_map = ClientConfigAdapter(ClientConfigMap())

        with patch("hummingbot.connector.exchange.polkadex.polkadex_data_source.SubstrateInterface.connect_websocket"):
            exchange = PolkadexExchange(
                client_config_map=client_config_map,
                polkadex_seed_phrase=self._seed_phrase,
                trading_pairs=[self.trading_pair],
            )
        encode_mock = MagicMock(
            return_value="0x1b99cba5555ad0ba890756fe16e499cb884b46a165b89bdce77ee8913b55fff1"  # noqa: mock
        )
        exchange._data_source._substrate_interface = MagicMock(
            spec=SubstrateInterface, spec_sec=SubstrateInterface, autospec=True
        )
        exchange._data_source._substrate_interface.create_scale_object.return_value.encode = encode_mock

        exchange._data_source._query_executor = ProgrammableQueryExecutor()
        return exchange

    def validate_auth_credentials_present(self, request_call: RequestCall):
        raise NotImplementedError

    def validate_order_creation_request(self, order: InFlightOrder, request_call: RequestCall):
        raise NotImplementedError

    def validate_order_cancelation_request(self, order: InFlightOrder, request_call: RequestCall):
        raise NotImplementedError

    def validate_order_status_request(self, order: InFlightOrder, request_call: RequestCall):
        raise NotImplementedError

    def validate_trades_request(self, order: InFlightOrder, request_call: RequestCall):
        raise NotImplementedError

    def configure_successful_cancelation_response(
        self, order: InFlightOrder, mock_api: aioresponses, callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> str:
        response = self._order_cancelation_request_successful_mock_response(order=order)
        mock_queue = AsyncMock()
        mock_queue.get.side_effect = partial(self._callback_wrapper_with_response, callback=callback, response=response)
        self.exchange._data_source._query_executor._cancel_order_responses = mock_queue
        return ""

    def configure_erroneous_cancelation_response(
        self, order: InFlightOrder, mock_api: aioresponses, callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> str:
        response = {}
        mock_queue = AsyncMock()
        mock_queue.get.side_effect = partial(self._callback_wrapper_with_response, callback=callback, response=response)
        self.exchange._data_source._query_executor._cancel_order_responses = mock_queue
        return ""

    def configure_order_not_found_error_cancelation_response(
        self, order: InFlightOrder, mock_api: aioresponses, callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> str:
        not_found_error = {
            "path": ["cancel_order"],
            "data": None,
            "errorType": "Lambda:Unhandled",
            "errorInfo": None,
            "locations": [{"line": 2, "column": 3, "sourceName": None}],
            "message": '{"errorMessage":"{\\"code\\":-32000,\\"message\\":\\"Order not found : '
            "0x1b99cba5555ad0ba890756fe16e499cb884b46a165b89bdce77ee8913b55ffff"  # noqa: mock
            '\\"}","errorType":"Lambda:Handled"}',
        }
        not_found_exception = IOError(str(not_found_error))
        mock_queue = AsyncMock()
        mock_queue.get.side_effect = partial(
            self._callback_wrapper_with_response, callback=callback, response=not_found_exception
        )
        self.exchange._data_source._query_executor._cancel_order_responses = mock_queue
        return ""

    def configure_one_successful_one_erroneous_cancel_all_response(
        self, successful_order: InFlightOrder, erroneous_order: InFlightOrder, mock_api: aioresponses
    ) -> List[str]:
        response = self._order_cancelation_request_successful_mock_response(order=successful_order)
        self.exchange._data_source._query_executor._cancel_order_responses.put_nowait(response)
        self.exchange._data_source._query_executor._cancel_order_responses.put_nowait({})
        return []

    def configure_completely_filled_order_status_response(
        self, order: InFlightOrder, mock_api: aioresponses, callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> List[str]:
        order_history_response = {"listOrderHistorybyMainAccount": {"items": []}}
        self.exchange._data_source._query_executor._order_history_responses.put_nowait(order_history_response)
        response = self._order_status_request_completely_filled_mock_response(order=order)
        mock_queue = AsyncMock()
        mock_queue.get.side_effect = partial(self._callback_wrapper_with_response, callback=callback, response=response)
        self.exchange._data_source._query_executor._order_responses = mock_queue
        return []

    def configure_canceled_order_status_response(
        self, order: InFlightOrder, mock_api: aioresponses, callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> List[str]:
        order_history_response = {"listOrderHistorybyMainAccount": {"items": []}}
        self.exchange._data_source._query_executor._order_history_responses.put_nowait(order_history_response)
        response = self._order_status_request_canceled_mock_response(order=order)
        mock_queue = AsyncMock()
        mock_queue.get.side_effect = partial(self._callback_wrapper_with_response, callback=callback, response=response)
        self.exchange._data_source._query_executor._order_responses = mock_queue
        return []

    def configure_open_order_status_response(
        self, order: InFlightOrder, mock_api: aioresponses, callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> List[str]:
        order_history_response = {"listOrderHistorybyMainAccount": {"items": []}}
        self.exchange._data_source._query_executor._order_history_responses.put_nowait(order_history_response)
        response = self._order_status_request_open_mock_response(order=order)
        mock_queue = AsyncMock()
        mock_queue.get.side_effect = partial(self._callback_wrapper_with_response, callback=callback, response=response)
        self.exchange._data_source._query_executor._order_responses = mock_queue
        return []

    def configure_http_error_order_status_response(
        self, order: InFlightOrder, mock_api: aioresponses, callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> str:
        order_history_response = {"listOrderHistorybyMainAccount": {"items": []}}
        self.exchange._data_source._query_executor._order_history_responses.put_nowait(order_history_response)
        mock_queue = AsyncMock()
        mock_queue.get.side_effect = IOError("Test failure")
        self.exchange._data_source._query_executor._order_responses = mock_queue
        return ""

    def configure_partially_filled_order_status_response(
        self, order: InFlightOrder, mock_api: aioresponses, callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> List[str]:
        order_history_response = {"listOrderHistorybyMainAccount": {"items": []}}
        self.exchange._data_source._query_executor._order_history_responses.put_nowait(order_history_response)
        response = self._order_status_request_partially_filled_mock_response(order=order)
        mock_queue = AsyncMock()
        mock_queue.get.side_effect = partial(self._callback_wrapper_with_response, callback=callback, response=response)
        self.exchange._data_source._query_executor._order_responses = mock_queue
        return []

    def configure_order_not_found_error_order_status_response(
        self, order: InFlightOrder, mock_api: aioresponses, callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> List[str]:
        order_history_response = {"listOrderHistorybyMainAccount": {"items": []}}
        self.exchange._data_source._query_executor._order_history_responses.put_nowait(order_history_response)
        response = {"findOrderByMainAccount": None}
        mock_queue = AsyncMock()
        mock_queue.get.side_effect = partial(self._callback_wrapper_with_response, callback=callback, response=response)
        self.exchange._data_source._query_executor._order_responses = mock_queue
        return []

    def configure_partial_fill_trade_response(
        self, order: InFlightOrder, mock_api: aioresponses, callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> str:
        raise NotImplementedError

    def configure_erroneous_http_fill_trade_response(
        self, order: InFlightOrder, mock_api: aioresponses, callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> str:
        raise NotImplementedError

    def configure_full_fill_trade_response(
        self, order: InFlightOrder, mock_api: aioresponses, callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> str:
        raise NotImplementedError

    def configure_all_symbols_response(
        self, mock_api: aioresponses, callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> str:
        all_assets_mock_response = self.all_assets_mock_response
        self.exchange._data_source._query_executor._all_assets_responses.put_nowait(all_assets_mock_response)
        response = self.all_symbols_request_mock_response
        self.exchange._data_source._query_executor._all_markets_responses.put_nowait(response)
        return ""

    def configure_successful_creation_order_status_response(
        self, callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> str:
        creation_response = self.order_creation_request_successful_mock_response
        mock_queue = AsyncMock()
        mock_queue.get.side_effect = partial(
            self._callback_wrapper_with_response, callback=callback, response=creation_response
        )
        self.exchange._data_source._query_executor._place_order_responses = mock_queue
        return ""

    def configure_erroneous_creation_order_status_response(
        self, callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> str:
        creation_response = {"place_order": None}
        mock_queue = AsyncMock()
        mock_queue.get.side_effect = partial(
            self._callback_wrapper_with_response, callback=callback, response=creation_response
        )
        self.exchange._data_source._query_executor._place_order_responses = mock_queue
        return ""

    def order_event_for_new_order_websocket_update(self, order: InFlightOrder):
        data = {
            "type": "Order",
            "snapshot_number": 50133,
            "event_id": 4300054,
            "client_order_id": "0x" + order.client_order_id.encode("utf-8").hex(),
            "avg_filled_price": "0",
            "fee": "0",
            "filled_quantity": "0",
            "status": "OPEN",
            "id": order.exchange_order_id,
            "user": "5EqHNNKJWA4U6dyZDvUSkKPQCt6PGgrAxiSBRvC6wqz2xKXU",
            "main_account": "5C5ZpV7Hunb7yG2CwDtnhxaYc3aug4UTLxRvu6HERxJqrtJY",
            "pair": {"base_asset": self.base_asset, "quote_asset": "1"},
            "side": "Bid" if order.trade_type == TradeType.BUY else "Ask",
            "order_type": "MARKET" if order.order_type == OrderType.MARKET else "LIMIT",
            "qty": str(order.amount),
            "price": str(order.price),
            "quote_order_qty": str(order.amount * order.price),
            "timestamp": 1682480373,
            "overall_unreserved_volume": "0",
        }

        return {"websocket_streams": {"data": json.dumps(data)}}

    def order_event_for_canceled_order_websocket_update(self, order: InFlightOrder):
        data = {
            "type": "Order",
            "snapshot_number": 50133,
            "event_id": 4300054,
            "client_order_id": "0x" + order.client_order_id.encode("utf-8").hex(),
            "avg_filled_price": "0",
            "fee": "0",
            "filled_quantity": "0",
            "status": "CANCELLED",
            "id": order.exchange_order_id,
            "user": "5EqHNNKJWA4U6dyZDvUSkKPQCt6PGgrAxiSBRvC6wqz2xKXU",
            "main_account": "5C5ZpV7Hunb7yG2CwDtnhxaYc3aug4UTLxRvu6HERxJqrtJY",
            "pair": {"base_asset": self.base_asset, "quote_asset": "1"},
            "side": "Bid" if order.trade_type == TradeType.BUY else "Ask",
            "order_type": "MARKET" if order.order_type == OrderType.MARKET else "LIMIT",
            "qty": str(order.amount),
            "price": str(order.price),
            "quote_order_qty": str(order.amount * order.price),
            "timestamp": 1682480373,
            "overall_unreserved_volume": "0",
        }

        return {"websocket_streams": {"data": json.dumps(data)}}

    def order_event_for_full_fill_websocket_update(self, order: InFlightOrder):
        data = {
            "type": "Order",
            "snapshot_number": 50133,
            "event_id": int(self.expected_fill_trade_id),
            "client_order_id": "0x" + order.client_order_id.encode("utf-8").hex(),
            "avg_filled_price": str(order.price),
            "fee": str(self.expected_fill_fee.flat_fees[0].amount),
            "filled_quantity": str(order.amount),
            "status": "CLOSED",
            "id": order.exchange_order_id,
            "user": "5EqHNNKJWA4U6dyZDvUSkKPQCt6PGgrAxiSBRvC6wqz2xKXU",  # noqa: mock
            "main_account": "5C5ZpV7Hunb7yG2CwDtnhxaYc3aug4UTLxRvu6HERxJqrtJY",  # noqa: mock
            "pair": {"base_asset": self.base_asset, "quote_asset": "1"},
            "side": "Bid" if order.trade_type == TradeType.BUY else "Ask",
            "order_type": "MARKET" if order.order_type == OrderType.MARKET else "LIMIT",
            "qty": str(order.amount),
            "price": str(order.price),
            "quote_order_qty": str(order.amount * order.price),
            "timestamp": 1682480373,
            "overall_unreserved_volume": "0",
        }

        return {"websocket_streams": {"data": json.dumps(data)}}

    def trade_event_for_full_fill_websocket_update(self, order: InFlightOrder):
        raise NotImplementedError

    @aioresponses()
    def test_check_network_failure(self, mock_api):
        all_assets_mock_response = {"getAllAssets": {"items": []}}
        self.exchange._data_source._query_executor._all_assets_responses.put_nowait(all_assets_mock_response)

        ret = self.async_run_with_timeout(coroutine=self.exchange.check_network())

        self.assertEqual(ret, NetworkStatus.NOT_CONNECTED)

    @aioresponses()
    def test_check_network_raises_cancel_exception(self, mock_api):
        mock_queue = AsyncMock()
        mock_queue.get.side_effect = asyncio.CancelledError
        self.exchange._data_source._query_executor._all_assets_responses = mock_queue

        self.assertRaises(
            asyncio.CancelledError, self.async_run_with_timeout, self.exchange.check_network(), 2
        )

    @aioresponses()
    def test_check_network_success(self, mock_api):
        all_assets_mock_response = self.all_assets_mock_response
        self.exchange._data_source._query_executor._all_assets_responses.put_nowait(all_assets_mock_response)

        network_status = self.async_run_with_timeout(coroutine=self.exchange.check_network())

        self.assertEqual(NetworkStatus.CONNECTED, network_status)

    @aioresponses()
    def test_all_trading_pairs_does_not_raise_exception(self, mock_api):
        self.exchange._set_trading_pair_symbol_map(None)
        queue_mock = AsyncMock()
        queue_mock.get.side_effect = Exception
        self.exchange._data_source._query_executor._all_assets_responses = queue_mock

        result: List[str] = self.async_run_with_timeout(self.exchange.all_trading_pairs())

        self.assertEqual(0, len(result))

    @aioresponses()
    def test_invalid_trading_pair_not_in_all_trading_pairs(self, mock_api):
        self.exchange._set_trading_pair_symbol_map(None)
        all_assets_mock_response = self.all_assets_mock_response
        self.exchange._data_source._query_executor._all_assets_responses.put_nowait(all_assets_mock_response)
        invalid_pair, response = self.all_symbols_including_invalid_pair_mock_response
        self.exchange._data_source._query_executor._all_markets_responses.put_nowait(response)

        all_trading_pairs = self.async_run_with_timeout(coroutine=self.exchange.all_trading_pairs())

        self.assertNotIn(invalid_pair, all_trading_pairs)

    @aioresponses()
    def test_get_last_trade_prices(self, mock_api):
        response = self.latest_prices_request_mock_response
        self.exchange._data_source._query_executor._recent_trades_responses.put_nowait(response)

        latest_prices: Dict[str, float] = self.async_run_with_timeout(
            self.exchange.get_last_traded_prices(trading_pairs=[self.trading_pair])
        )

        self.assertEqual(1, len(latest_prices))
        self.assertEqual(self.expected_latest_price, latest_prices[self.trading_pair])

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
                f"{Decimal('100.000000')} {self.trading_pair}.",
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

        create_event: SellOrderCreatedEvent = self.sell_order_created_logger.event_log[0]
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
                f"Created {OrderType.LIMIT.name} {TradeType.SELL.name} order {order_id} for "
                f"{Decimal('100.000000')} {self.trading_pair}.",
            )
        )

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

        self.assertEquals(0, len(self.buy_order_created_logger.event_log))
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
    def test_create_order_fails_when_trading_rule_error_and_raises_failure_event(self, mock_api):
        self._simulate_trading_rules_initialized()
        request_sent_event = asyncio.Event()
        self.exchange._set_current_timestamp(1640780000)

        self.configure_erroneous_creation_order_status_response(
            callback=lambda *args, **kwargs: request_sent_event.set()
        )

        order_id_for_invalid_order = self.place_buy_order(
            amount=Decimal("0.0001"), price=Decimal("0.0000001")
        )
        # The second order is used only to have the event triggered and avoid using timeouts for tests
        order_id = self.place_buy_order()
        self.async_run_with_timeout(request_sent_event.wait())

        self.assertNotIn(order_id_for_invalid_order, self.exchange.in_flight_orders)
        self.assertNotIn(order_id, self.exchange.in_flight_orders)

        self.assertEquals(0, len(self.buy_order_created_logger.event_log))
        failure_event: MarketOrderFailureEvent = self.order_failure_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp, failure_event.timestamp)
        self.assertEqual(OrderType.LIMIT, failure_event.order_type)
        self.assertEqual(order_id_for_invalid_order, failure_event.order_id)

        self.assertTrue(
            self.is_logged(
                "WARNING",
                "Buy order amount 0 is lower than the minimum order size 0.01. The order will not be created."
            )
        )
        self.assertTrue(
            self.is_logged(
                "INFO",
                f"Order {order_id} has failed. Order Update: OrderUpdate(trading_pair='{self.trading_pair}', "
                f"update_timestamp={self.exchange.current_timestamp}, new_state={repr(OrderState.FAILED)}, "
                f"client_order_id='{order_id}', exchange_order_id=None, misc_updates=None)"
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

        self.assertIn(order.client_order_id, self.exchange.in_flight_orders)
        self.assertTrue(order.is_pending_cancel_confirmation)

    @aioresponses()
    def test_cancel_order_raises_failure_event_when_request_fails(self, mock_api):
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
        order = self.exchange.in_flight_orders[self.client_order_id_prefix + "1"]

        self.configure_erroneous_cancelation_response(
            order=order, mock_api=mock_api, callback=lambda *args, **kwargs: request_sent_event.set()
        )

        self.exchange.cancel(trading_pair=self.trading_pair, client_order_id=self.client_order_id_prefix + "1")
        self.async_run_with_timeout(request_sent_event.wait())

        self.assertEquals(0, len(self.order_cancelled_logger.event_log))
        self.assertTrue(
            any(
                log.msg.startswith(f"Failed to cancel order {order.client_order_id}")
                for log in self.log_records
            )
        )

    @aioresponses()
    def test_cancel_order_not_found_in_the_exchange(self, mock_api):
        self.exchange._set_current_timestamp(1640780000)
        request_sent_event = asyncio.Event()

        self.exchange.start_tracking_order(
            order_id=self.client_order_id_prefix + "1",
            exchange_order_id=str(self.expected_exchange_order_id),
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("1"),
        )

        self.assertIn(self.client_order_id_prefix + "1", self.exchange.in_flight_orders)
        order = self.exchange.in_flight_orders[self.client_order_id_prefix + "1"]

        self.configure_order_not_found_error_cancelation_response(
            order=order, mock_api=mock_api, callback=lambda *args, **kwargs: request_sent_event.set()
        )

        self.exchange.cancel(trading_pair=self.trading_pair, client_order_id=self.client_order_id_prefix + "1")
        self.async_run_with_timeout(request_sent_event.wait())

        self.assertFalse(order.is_done)
        self.assertFalse(order.is_failure)
        self.assertFalse(order.is_cancelled)

        self.assertIn(order.client_order_id, self.exchange._order_tracker.all_updatable_orders)
        self.assertEqual(1, self.exchange._order_tracker._order_not_found_records[order.client_order_id])

    @aioresponses()
    def test_update_balances(self, mock_api):
        response = self.balance_request_mock_response_for_base_and_quote
        self._configure_balance_response(response=response, mock_api=mock_api)

        self.async_run_with_timeout(self.exchange._update_balances())

        available_balances = self.exchange.available_balances
        total_balances = self.exchange.get_all_balances()

        self.assertEqual(Decimal("10"), available_balances[self.base_asset])
        self.assertEqual(Decimal("2000"), available_balances[self.quote_asset])
        self.assertEqual(Decimal("15"), total_balances[self.base_asset])
        self.assertEqual(Decimal("2000"), total_balances[self.quote_asset])

        response = self.balance_request_mock_response_only_base

        self._configure_balance_response(response=response, mock_api=mock_api)
        self.async_run_with_timeout(self.exchange._update_balances())

        available_balances = self.exchange.available_balances
        total_balances = self.exchange.get_all_balances()

        self.assertNotIn(self.quote_asset, available_balances)
        self.assertNotIn(self.quote_asset, total_balances)
        self.assertEqual(Decimal("10"), available_balances[self.base_asset])
        self.assertEqual(Decimal("15"), total_balances[self.base_asset])

    @aioresponses()
    def test_update_order_status_when_filled(self, mock_api):
        self.exchange._set_current_timestamp(1640780000)
        request_sent_event = asyncio.Event()

        self.exchange.start_tracking_order(
            order_id=self.client_order_id_prefix + "1",
            exchange_order_id=str(self.expected_exchange_order_id),
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("1"),
        )
        order: InFlightOrder = self.exchange.in_flight_orders[self.client_order_id_prefix + "1"]

        # to allow the ClientOrderTracker to process the last status update
        order.completely_filled_event.set()

        self.configure_completely_filled_order_status_response(
            order=order, mock_api=mock_api, callback=lambda *args, **kwargs: request_sent_event.set()
        )

        self.async_run_with_timeout(self.exchange._update_order_status())
        # Execute one more synchronization to ensure the async task that processes the update is finished
        self.async_run_with_timeout(request_sent_event.wait())

        self.async_run_with_timeout(order.wait_until_completely_filled())
        self.assertTrue(order.is_done)

        buy_event: BuyOrderCompletedEvent = self.buy_order_completed_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp, buy_event.timestamp)
        self.assertEqual(order.client_order_id, buy_event.order_id)
        self.assertEqual(order.base_asset, buy_event.base_asset)
        self.assertEqual(order.quote_asset, buy_event.quote_asset)
        self.assertEqual(
            order.amount if self.is_order_fill_http_update_included_in_status_update else Decimal("0"),
            buy_event.base_asset_amount,
        )
        self.assertEqual(
            order.amount * order.price
            if self.is_order_fill_http_update_included_in_status_update
            else Decimal("0"),
            buy_event.quote_asset_amount,
        )
        self.assertEqual(order.order_type, buy_event.order_type)
        self.assertEqual(order.exchange_order_id, buy_event.exchange_order_id)
        self.assertNotIn(order.client_order_id, self.exchange.in_flight_orders)
        self.assertTrue(
            self.is_logged("INFO", f"BUY order {order.client_order_id} completely filled.")
        )

    @aioresponses()
    def test_update_order_status_when_request_fails_marks_order_as_not_found(self, mock_api):
        self.exchange._set_current_timestamp(1640780000)

        self.exchange.start_tracking_order(
            order_id=self.client_order_id_prefix + "1",
            exchange_order_id=str(self.expected_exchange_order_id),
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("1"),
        )
        order: InFlightOrder = self.exchange.in_flight_orders[self.client_order_id_prefix + "1"]

        self.configure_http_error_order_status_response(
            order=order,
            mock_api=mock_api)

        self.async_run_with_timeout(self.exchange._update_order_status())

        self.assertTrue(order.is_open)
        self.assertFalse(order.is_filled)
        self.assertFalse(order.is_done)

        self.assertEqual(1, self.exchange._order_tracker._order_not_found_records[order.client_order_id])

    @aioresponses()
    def test_update_order_status_when_order_has_not_changed_and_one_partial_fill(self, mock_api):
        self.exchange._set_current_timestamp(1640780000)

        self.exchange.start_tracking_order(
            order_id=self.client_order_id_prefix + "1",
            exchange_order_id=str(self.expected_exchange_order_id),
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("1"),
        )
        order: InFlightOrder = self.exchange.in_flight_orders[self.client_order_id_prefix + "1"]

        self.configure_partially_filled_order_status_response(order=order, mock_api=mock_api)

        self.assertTrue(order.is_open)

        self.async_run_with_timeout(self.exchange._update_order_status())

        self.assertTrue(order.is_open)
        self.assertEqual(OrderState.PARTIALLY_FILLED, order.current_state)

    @aioresponses()
    def test_cancel_lost_order_successfully(self, mock_api):
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

        for _ in range(self.exchange._order_tracker._lost_order_count_limit + 1):
            self.async_run_with_timeout(
                self.exchange._order_tracker.process_order_not_found(client_order_id=order.client_order_id))

        self.assertNotIn(order.client_order_id, self.exchange.in_flight_orders)

        self.configure_successful_cancelation_response(
            order=order,
            mock_api=mock_api,
            callback=lambda *args, **kwargs: request_sent_event.set())

        self.async_run_with_timeout(self.exchange._cancel_lost_orders())
        self.async_run_with_timeout(request_sent_event.wait())

        self.assertIn(order.client_order_id, self.exchange._order_tracker.lost_orders)
        self.assertTrue(order.is_failure)

    @aioresponses()
    def test_cancel_lost_order_raises_failure_event_when_request_fails(self, mock_api):
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
        order = self.exchange.in_flight_orders[self.client_order_id_prefix + "1"]

        for _ in range(self.exchange._order_tracker._lost_order_count_limit + 1):
            self.async_run_with_timeout(
                self.exchange._order_tracker.process_order_not_found(client_order_id=order.client_order_id))

        self.assertNotIn(order.client_order_id, self.exchange.in_flight_orders)

        self.configure_erroneous_cancelation_response(
            order=order,
            mock_api=mock_api,
            callback=lambda *args, **kwargs: request_sent_event.set())

        self.async_run_with_timeout(self.exchange._cancel_lost_orders())
        self.async_run_with_timeout(request_sent_event.wait())

        self.assertIn(order.client_order_id, self.exchange._order_tracker.lost_orders)
        self.assertEquals(0, len(self.order_cancelled_logger.event_log))
        self.assertTrue(
            any(
                log.msg.startswith(f"Failed to cancel order {order.client_order_id}")
                for log in self.log_records
            )
        )

    def test_lost_order_removed_after_cancel_status_user_event_received(self):
        self.exchange._set_current_timestamp(1640780000)
        self.exchange.start_tracking_order(
            order_id=self.client_order_id_prefix + "1",
            exchange_order_id=str(self.expected_exchange_order_id),
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("1"),
        )
        order = self.exchange.in_flight_orders[self.client_order_id_prefix + "1"]

        for _ in range(self.exchange._order_tracker._lost_order_count_limit + 1):
            self.async_run_with_timeout(
                self.exchange._order_tracker.process_order_not_found(client_order_id=order.client_order_id)
            )

        self.assertNotIn(order.client_order_id, self.exchange.in_flight_orders)

        order_event = self.order_event_for_canceled_order_websocket_update(order=order)
        self.reset_log_event()

        self.exchange._data_source._process_private_event(event=order_event)
        self.async_run_with_timeout(self.wait_for_a_log())

        self.assertNotIn(order.client_order_id, self.exchange._order_tracker.lost_orders)
        self.assertEqual(0, len(self.order_cancelled_logger.event_log))
        self.assertNotIn(order.client_order_id, self.exchange.in_flight_orders)
        self.assertFalse(order.is_cancelled)
        self.assertTrue(order.is_failure)

    @aioresponses()
    def test_lost_order_user_stream_full_fill_events_are_processed(self, mock_api):
        self.exchange._set_current_timestamp(1640780000)
        self.exchange.start_tracking_order(
            order_id=self.client_order_id_prefix + "1",
            exchange_order_id=str(self.expected_exchange_order_id),
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("1"),
        )
        order = self.exchange.in_flight_orders[self.client_order_id_prefix + "1"]

        for _ in range(self.exchange._order_tracker._lost_order_count_limit + 1):
            self.async_run_with_timeout(
                self.exchange._order_tracker.process_order_not_found(client_order_id=order.client_order_id)
            )

        self.assertNotIn(order.client_order_id, self.exchange.in_flight_orders)

        order_event = self.order_event_for_full_fill_websocket_update(order=order)
        self.reset_log_event()

        self.exchange._data_source._process_private_event(event=order_event)
        self.async_run_with_timeout(self.wait_for_a_log())

        # Execute one more synchronization to ensure the async task that processes the update is finished
        self.async_run_with_timeout(order.wait_until_completely_filled())

        fill_event: OrderFilledEvent = self.order_filled_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp, fill_event.timestamp)
        self.assertEqual(order.client_order_id, fill_event.order_id)
        self.assertEqual(order.trading_pair, fill_event.trading_pair)
        self.assertEqual(order.trade_type, fill_event.trade_type)
        self.assertEqual(order.order_type, fill_event.order_type)
        self.assertEqual(order.price, fill_event.price)
        self.assertEqual(order.amount, fill_event.amount)
        expected_fee = self.expected_fill_fee
        self.assertEqual(expected_fee, fill_event.trade_fee)

        self.assertEqual(0, len(self.buy_order_completed_logger.event_log))
        self.assertNotIn(order.client_order_id, self.exchange.in_flight_orders)
        self.assertNotIn(order.client_order_id, self.exchange._order_tracker.lost_orders)
        self.assertTrue(order.is_filled)
        self.assertTrue(order.is_failure)

    def test_user_stream_balance_update(self):
        self.exchange._set_current_timestamp(1640780000)

        balance_event = self.balance_event_websocket_update

        all_assets_mock_response = self.all_assets_mock_response
        self.exchange._data_source._query_executor._all_assets_responses.put_nowait(all_assets_mock_response)

        self.async_run_with_timeout(
            self.exchange._data_source._process_balance_event(
                event=json.loads(balance_event["websocket_streams"]["data"])
            )
        )

        self.assertEqual(Decimal("10"), self.exchange.available_balances[self.base_asset])
        self.assertEqual(Decimal("15"), self.exchange.get_balance(self.base_asset))

    def test_user_stream_update_for_new_order(self):
        self.exchange._set_current_timestamp(1640780000)
        self.exchange.start_tracking_order(
            order_id=self.client_order_id_prefix + "1",
            exchange_order_id=str(self.expected_exchange_order_id),
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("1"),
        )
        order = self.exchange.in_flight_orders[self.client_order_id_prefix + "1"]

        order_event = self.order_event_for_new_order_websocket_update(order=order)

        self.reset_log_event()
        self.exchange._data_source._process_private_event(event=order_event)
        self.async_run_with_timeout(self.wait_for_a_log())

        event: BuyOrderCreatedEvent = self.buy_order_created_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp, event.timestamp)
        self.assertEqual(order.order_type, event.type)
        self.assertEqual(order.trading_pair, event.trading_pair)
        self.assertEqual(order.amount, event.amount)
        self.assertEqual(order.price, event.price)
        self.assertEqual(order.client_order_id, event.order_id)
        self.assertEqual(order.exchange_order_id, event.exchange_order_id)
        self.assertTrue(order.is_open)

        tracked_order: InFlightOrder = list(self.exchange.in_flight_orders.values())[0]

        self.assertTrue(self.is_logged("INFO", tracked_order.build_order_created_message()))

    def test_user_stream_update_for_canceled_order(self):
        self.exchange._set_current_timestamp(1640780000)
        self.exchange.start_tracking_order(
            order_id=self.client_order_id_prefix + "1",
            exchange_order_id=str(self.expected_exchange_order_id),
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("1"),
        )
        order = self.exchange.in_flight_orders[self.client_order_id_prefix + "1"]

        order_event = self.order_event_for_canceled_order_websocket_update(order=order)

        self.reset_log_event()
        self.exchange._data_source._process_private_event(event=order_event)
        self.async_run_with_timeout(self.wait_for_a_log())

        cancel_event: OrderCancelledEvent = self.order_cancelled_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp, cancel_event.timestamp)
        self.assertEqual(order.client_order_id, cancel_event.order_id)
        self.assertEqual(order.exchange_order_id, cancel_event.exchange_order_id)
        self.assertNotIn(order.client_order_id, self.exchange.in_flight_orders)
        self.assertTrue(order.is_cancelled)
        self.assertTrue(order.is_done)

        self.assertTrue(self.is_logged("INFO", f"Successfully canceled order {order.client_order_id}."))

    @aioresponses()
    def test_user_stream_update_for_order_full_fill(self, mock_api):
        self.exchange._set_current_timestamp(1640780000)
        self.exchange.start_tracking_order(
            order_id=self.client_order_id_prefix + "1",
            exchange_order_id=str(self.expected_exchange_order_id),
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("1"),
        )
        order = self.exchange.in_flight_orders[self.client_order_id_prefix + "1"]

        order_event = self.order_event_for_full_fill_websocket_update(order=order)

        self.reset_log_event()
        self.exchange._data_source._process_private_event(event=order_event)
        self.async_run_with_timeout(self.wait_for_a_log())

        # Execute one more synchronization to ensure the async task that processes the update is finished
        self.async_run_with_timeout(order.wait_until_completely_filled())

        fill_event: OrderFilledEvent = self.order_filled_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp, fill_event.timestamp)
        self.assertEqual(order.client_order_id, fill_event.order_id)
        self.assertEqual(order.trading_pair, fill_event.trading_pair)
        self.assertEqual(order.trade_type, fill_event.trade_type)
        self.assertEqual(order.order_type, fill_event.order_type)
        self.assertEqual(order.price, fill_event.price)
        self.assertEqual(order.amount, fill_event.amount)
        expected_fee = self.expected_fill_fee
        self.assertEqual(expected_fee, fill_event.trade_fee)

        buy_event: BuyOrderCompletedEvent = self.buy_order_completed_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp, buy_event.timestamp)
        self.assertEqual(order.client_order_id, buy_event.order_id)
        self.assertEqual(order.base_asset, buy_event.base_asset)
        self.assertEqual(order.quote_asset, buy_event.quote_asset)
        self.assertEqual(order.amount, buy_event.base_asset_amount)
        self.assertEqual(order.amount * fill_event.price, buy_event.quote_asset_amount)
        self.assertEqual(order.order_type, buy_event.order_type)
        self.assertEqual(order.exchange_order_id, buy_event.exchange_order_id)
        self.assertNotIn(order.client_order_id, self.exchange.in_flight_orders)
        self.assertTrue(order.is_filled)
        self.assertTrue(order.is_done)

        self.assertTrue(self.is_logged("INFO", f"BUY order {order.client_order_id} completely filled."))

    def test_user_stream_logs_errors(self):
        # This test does not apply to Polkadex because it handles private events in its own data source
        pass

    def test_user_stream_raises_cancel_exception(self):
        # This test does not apply to Polkadex because it handles private events in its own data source
        pass

    @aioresponses()
    def test_lost_order_included_in_order_fills_update_and_not_in_order_status_update(self, mock_api):
        self.exchange._set_current_timestamp(1640780000)
        request_sent_event = asyncio.Event()

        self.exchange.start_tracking_order(
            order_id=self.client_order_id_prefix + "1",
            exchange_order_id=str(self.expected_exchange_order_id),
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("1"),
        )
        order: InFlightOrder = self.exchange.in_flight_orders[self.client_order_id_prefix + "1"]

        for _ in range(self.exchange._order_tracker._lost_order_count_limit + 1):
            self.async_run_with_timeout(
                self.exchange._order_tracker.process_order_not_found(client_order_id=order.client_order_id)
            )

        self.assertNotIn(order.client_order_id, self.exchange.in_flight_orders)

        order.completely_filled_event.set()
        request_sent_event.set()

        self.async_run_with_timeout(self.exchange._update_order_status())
        # Execute one more synchronization to ensure the async task that processes the update is finished
        self.async_run_with_timeout(request_sent_event.wait())

        self.async_run_with_timeout(order.wait_until_completely_filled())
        self.assertTrue(order.is_done)
        self.assertTrue(order.is_failure)

        self.assertEqual(0, len(self.buy_order_completed_logger.event_log))
        self.assertIn(order.client_order_id, self.exchange._order_tracker.all_fillable_orders)
        self.assertFalse(
            self.is_logged("INFO", f"BUY order {order.client_order_id} completely filled.")
        )

        request_sent_event.clear()

        self.configure_completely_filled_order_status_response(
            order=order, mock_api=mock_api, callback=lambda *args, **kwargs: request_sent_event.set()
        )

        self.async_run_with_timeout(self.exchange._update_lost_orders_status())
        # Execute one more synchronization to ensure the async task that processes the update is finished
        self.async_run_with_timeout(request_sent_event.wait())

        self.assertTrue(order.is_done)
        self.assertTrue(order.is_failure)

        self.assertEqual(0, len(self.buy_order_completed_logger.event_log))
        self.assertNotIn(order.client_order_id, self.exchange._order_tracker.all_fillable_orders)
        self.assertFalse(
            self.is_logged("INFO", f"BUY order {order.client_order_id} completely filled.")
        )

    def test_initial_status_dict(self):
        self.exchange._set_trading_pair_symbol_map(None)

        status_dict = self.exchange.status_dict

        expected_initial_dict = {
            "symbols_mapping_initialized": False,
            "order_books_initialized": False,
            "account_balance": False,
            "trading_rule_initialized": False,
            "user_stream_initialized": False,
        }

        self.assertEqual(expected_initial_dict, status_dict)
        self.assertFalse(self.exchange.ready)

    @aioresponses()
    def test_update_trading_rules(self, mock_api):
        self.exchange._set_current_timestamp(1000)

        all_assets_mock_response = self.all_assets_mock_response
        self.exchange._data_source._query_executor._all_assets_responses.put_nowait(all_assets_mock_response)
        response = self.trading_rules_request_mock_response
        self.exchange._data_source._query_executor._all_markets_responses.put_nowait(response)

        self.async_run_with_timeout(coroutine=self.exchange._update_trading_rules())

        self.assertTrue(self.trading_pair in self.exchange.trading_rules)
        trading_rule: TradingRule = self.exchange.trading_rules[self.trading_pair]

        self.assertTrue(self.trading_pair in self.exchange.trading_rules)
        self.assertEqual(repr(self.expected_trading_rule), repr(trading_rule))

        trading_rule_with_default_values = TradingRule(trading_pair=self.trading_pair)

        # The following element can't be left with the default value because that breaks quantization in Cython
        self.assertNotEqual(trading_rule_with_default_values.min_base_amount_increment,
                            trading_rule.min_base_amount_increment)
        self.assertNotEqual(trading_rule_with_default_values.min_price_increment,
                            trading_rule.min_price_increment)

    @aioresponses()
    def test_update_trading_rules_ignores_rule_with_error(self, mock_api):
        self.exchange._set_current_timestamp(1000)

        all_assets_mock_response = self.all_assets_mock_response
        self.exchange._data_source._query_executor._all_assets_responses.put_nowait(all_assets_mock_response)
        response = self.trading_rules_request_erroneous_mock_response
        self.exchange._data_source._query_executor._all_markets_responses.put_nowait(response)

        self.async_run_with_timeout(coroutine=self.exchange._update_trading_rules())

        self.assertEqual(0, len(self.exchange._trading_rules))
        self.assertTrue(
            self.is_logged("ERROR", self.expected_logged_error_for_erroneous_trading_rule)
        )

    def test_user_stream_status_is_based_on_listening_tasks(self):
        self.exchange._set_trading_pair_symbol_map(None)
        self.exchange._data_source._events_listening_tasks.append(self.async_loop.create_task(asyncio.sleep(120)))

        status_dict = self.exchange.status_dict

        expected_initial_dict = {
            "symbols_mapping_initialized": False,
            "order_books_initialized": False,
            "account_balance": False,
            "trading_rule_initialized": False,
            "user_stream_initialized": True,
        }

        self.assertEqual(expected_initial_dict, status_dict)
        self.assertFalse(self.exchange.ready)

    def test_is_exception_related_to_time_synchronizer_returns_false(self):
        self.assertFalse(self.exchange._is_request_exception_related_to_time_synchronizer(request_exception=None))

    def test_create_user_stream_tracker_task(self):
        self.assertIsNone(self.exchange._create_user_stream_tracker_task())

    def _configure_balance_response(
        self,
        response: Dict[str, Any],
        mock_api: aioresponses,
        callback: Optional[Callable] = lambda *args, **kwargs: None,
    ) -> str:
        all_assets_mock_response = self.all_assets_mock_response
        self.exchange._data_source._query_executor._all_assets_responses.put_nowait(all_assets_mock_response)
        self.exchange._data_source._query_executor._balances_responses.put_nowait(response)
        return ""

    def _order_cancelation_request_successful_mock_response(self, order: InFlightOrder) -> Any:
        return {"cancel_order": True}

    def _order_status_request_open_mock_response(self, order: InFlightOrder) -> Any:
        return {
            "findOrderByMainAccount": {
                "afp": "0",
                "cid": "0x" + order.client_order_id.encode("utf-8").hex(),
                "fee": "0",
                "fq": "0",
                "id": order.exchange_order_id,
                "isReverted": False,
                "m": self.exchange_trading_pair,
                "ot": "MARKET" if order.order_type == OrderType.MARKET else "LIMIT",
                "p": str(order.price),
                "q": str(order.amount),
                "s": "Bid" if order.trade_type == TradeType.BUY else "Ask",
                "sid": 1,
                "st": "OPEN",
                "t": 160001112.223,
                "u": "",
            }
        }

    def _order_status_request_canceled_mock_response(self, order: InFlightOrder) -> Any:
        return {
            "findOrderByMainAccount": {
                "afp": "0",
                "cid": "0x" + order.client_order_id.encode("utf-8").hex(),
                "fee": "0",
                "fq": "0",
                "id": order.exchange_order_id,
                "isReverted": False,
                "m": self.exchange_trading_pair,
                "ot": "MARKET" if order.order_type == OrderType.MARKET else "LIMIT",
                "p": str(order.price),
                "q": str(order.amount),
                "s": "Bid" if order.trade_type == TradeType.BUY else "Ask",
                "sid": 1,
                "st": "CANCELLED",
                "t": 160001112.223,
                "u": "",
            }
        }

    def _order_status_request_completely_filled_mock_response(self, order: InFlightOrder) -> Any:
        return {
            "findOrderByMainAccount": {
                "afp": str(order.price),
                "cid": "0x" + order.client_order_id.encode("utf-8").hex(),
                "fee": str(self.expected_fill_fee.flat_fees[0].amount),
                "fq": str(order.amount),
                "id": order.exchange_order_id,
                "isReverted": False,
                "m": self.exchange_trading_pair,
                "ot": "MARKET" if order.order_type == OrderType.MARKET else "LIMIT",
                "p": str(order.price),
                "q": str(order.amount),
                "s": "Bid" if order.trade_type == TradeType.BUY else "Ask",
                "sid": int(self.expected_fill_trade_id),
                "st": "CLOSED",
                "t": 160001112.223,
                "u": "",
            }
        }

    def _order_status_request_partially_filled_mock_response(self, order: InFlightOrder) -> Any:
        return {
            "findOrderByMainAccount": {
                "afp": str(self.expected_partial_fill_price),
                "cid": "0x" + order.client_order_id.encode("utf-8").hex(),
                "fee": str(self.expected_partial_fill_fee.flat_fees[0].amount),
                "fq": str(self.expected_partial_fill_amount),
                "id": order.exchange_order_id,
                "isReverted": False,
                "m": self.exchange_trading_pair,
                "ot": "MARKET" if order.order_type == OrderType.MARKET else "LIMIT",
                "p": str(order.price),
                "q": str(order.amount),
                "s": "Bid" if order.trade_type == TradeType.BUY else "Ask",
                "sid": int(self.expected_fill_trade_id),
                "st": "OPEN",
                "t": 160001112.223,
                "u": "",
            }
        }

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
