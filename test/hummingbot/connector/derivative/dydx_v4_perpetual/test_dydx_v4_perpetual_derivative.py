import asyncio
import json
import re
from decimal import Decimal
from functools import partial
from test.hummingbot.connector.derivative.dydx_v4_perpetual.programmable_v4_client import ProgrammableV4Client
from typing import Any, Callable, Dict, List, Optional, Tuple
from unittest.mock import AsyncMock, patch

from aioresponses import aioresponses
from aioresponses.core import RequestCall

import hummingbot.connector.derivative.dydx_v4_perpetual.dydx_v4_perpetual_constants as CONSTANTS
import hummingbot.connector.derivative.dydx_v4_perpetual.dydx_v4_perpetual_web_utils as web_utils
from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.connector.derivative.dydx_v4_perpetual.dydx_v4_perpetual_derivative import DydxV4PerpetualDerivative
from hummingbot.connector.test_support.perpetual_derivative_test import AbstractPerpetualDerivativeTests
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.connector.utils import combine_to_hb_trading_pair
from hummingbot.core.data_type.common import OrderType, PositionAction, PositionMode, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_row import OrderBookRow
from hummingbot.core.data_type.trade_fee import AddedToCostTradeFee, TokenAmount, TradeFeeBase


class DydxV4PerpetualDerivativeTests(AbstractPerpetualDerivativeTests.PerpetualDerivativeTests):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.dydx_v4_perpetual_secret_phrase = "mirror actor skill push coach wait confirm orchard " \
                                              "lunch mobile athlete gossip awake miracle matter " \
                                              "bus reopen team ladder lazy list timber render wait"
        cls.dydx_v4_perpetual_chain_address = "dydx14zzueazeh0hj67cghhf9jypslcf9sh2n5k6art"
        cls.subaccount_id = 0
        cls.base_asset = "TRX"
        cls.quote_asset = "USD"  # linear
        cls.trading_pair = combine_to_hb_trading_pair(cls.base_asset, cls.quote_asset)

    @property
    def all_symbols_url(self):
        url = web_utils.private_rest_url(CONSTANTS.PATH_MARKETS)
        return url

    @property
    def latest_prices_url(self):
        url = web_utils.private_rest_url(CONSTANTS.PATH_MARKETS + r"\?.*")
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        return regex_url

    @property
    def network_status_url(self):
        url = web_utils.public_rest_url(CONSTANTS.PATH_TIME)
        return url

    @property
    def trading_rules_url(self):
        url = web_utils.private_rest_url(CONSTANTS.PATH_MARKETS)
        return url

    @property
    def order_creation_url(self):
        url = web_utils.private_rest_url(CONSTANTS.PATH_ORDERS)
        return url

    @property
    def balance_url(self):
        path = f"{CONSTANTS.PATH_SUBACCOUNT}/{self.dydx_v4_perpetual_chain_address}/subaccountNumber/{self.subaccount_id}"
        url = web_utils.private_rest_url(path)
        return url

    @property
    def expected_supported_position_modes(self) -> List[PositionMode]:
        return [PositionMode.ONEWAY]

    @property
    def order_creation_request_erroneous_mock_response(self):
        return {"txhash": "017C130E3602A48E5C9D661CAC657BF1B79262D4B71D5C25B1DA62DE2338DA0E",  # noqa: mock
                "raw_log": "ERROR"}  # noqa: mock

    @property
    def order_creation_request_successful_mock_response(self):
        return {"txhash": "017C130E3602A48E5C9D661CAC657BF1B79262D4B71D5C25B1DA62DE2338DA0E",  # noqa: mock
                "raw_log": "[]"}  # noqa: mock

    def _order_cancelation_request_successful_mock_response(self, order: InFlightOrder) -> Dict[str, Any]:
        return {"txhash": "79DBF373DE9C534EE2DC9D009F32B850DA8D0C73833FAA0FD52C6AE8989EC659",  # noqa: mock
                "raw_log": "[]"}  # noqa: mock

    def _order_cancelation_request_erroneous_mock_response(self, order: InFlightOrder) -> Dict[str, Any]:
        return {"txhash": "79DBF373DE9C534EE2DC9D009F32B850DA8D0C73833FAA0FD52C6AE8989EC659",  # noqa: mock
                "raw_log": "Error"}  # noqa: mock

    @property
    def all_symbols_request_mock_response(self):
        mock_response = {
            "markets": {
                self.trading_pair: {
                    'clobPairId': '0', 'ticker': self.trading_pair, 'status': 'ACTIVE', 'oraclePrice': '62730.24877',
                    'priceChange24H': '-2721.74538', 'volume24H': '547242504.5571', 'trades24H': 115614,
                    'nextFundingRate': '0.00000888425925925926', 'initialMarginFraction': '0.05',
                    'maintenanceMarginFraction': '0.03', 'openInterest': '594.8603', 'atomicResolution': -10,
                    'quantumConversionExponent': -9, 'tickSize': '1', 'stepSize': '0.0001',
                    'stepBaseQuantums': 1000000, 'subticksPerTick': 100000
                }
            }
        }
        return mock_response

    @property
    def latest_prices_request_mock_response(self):
        mock_response = {
            "markets": {
                self.trading_pair: {
                    'clobPairId': '0', 'ticker': self.trading_pair, 'status': 'ACTIVE', 'oraclePrice': '62730.24877',
                    'priceChange24H': '-2721.74538', 'volume24H': '547242504.5571', 'trades24H': 115614,
                    'nextFundingRate': '0.00000888425925925926', 'initialMarginFraction': '0.05',
                    'maintenanceMarginFraction': '0.03', 'openInterest': '594.8603', 'atomicResolution': -10,
                    'quantumConversionExponent': -9, 'tickSize': '1', 'stepSize': '0.0001',
                    'stepBaseQuantums': 1000000, 'subticksPerTick': 100000
                }
            }
        }
        return mock_response

    @property
    def all_symbols_including_invalid_pair_mock_response(self) -> Tuple[str, Any]:
        mock_response = {
            "markets": {
                self.trading_pair: {
                    'clobPairId': '0', 'ticker': self.trading_pair, 'status': 'ACTIVE', 'oraclePrice': '62730.24877',
                    'priceChange24H': '-2721.74538', 'volume24H': '547242504.5571', 'trades24H': 115614,
                    'nextFundingRate': '0.00000888425925925926', 'initialMarginFraction': '0.05',
                    'maintenanceMarginFraction': '0.03', 'openInterest': '594.8603', 'atomicResolution': -10,
                    'quantumConversionExponent': -9, 'tickSize': '1', 'stepSize': '0.0001',
                    'stepBaseQuantums': 1000000, 'subticksPerTick': 100000
                },
                "INVALID-PAIR": {
                    'clobPairId': '0', 'ticker': "INVALID-PAIR", 'status': 'INVALID', 'oraclePrice': '62730.24877',
                    'priceChange24H': '-2721.74538', 'volume24H': '547242504.5571', 'trades24H': 115614,
                    'nextFundingRate': '0.00000888425925925926', 'initialMarginFraction': '0.05',
                    'maintenanceMarginFraction': '0.03', 'openInterest': '594.8603', 'atomicResolution': -10,
                    'quantumConversionExponent': -9, 'tickSize': '1', 'stepSize': '0.0001',
                    'stepBaseQuantums': 1000000, 'subticksPerTick': 100000
                },
            }
        }
        return "INVALID-PAIR", mock_response

    @property
    def network_status_request_successful_mock_response(self):
        mock_response = {
            "iso": "2021-02-02T18:35:45Z",
            "epoch": "1611965998.515",
        }
        return mock_response

    @property
    def trading_rules_request_mock_response(self):
        mock_response = {
            "markets": {
                self.trading_pair: {
                    'clobPairId': '0', 'ticker': self.trading_pair, 'status': 'ACTIVE', 'oraclePrice': '62730.24877',
                    'priceChange24H': '-2721.74538', 'volume24H': '547242504.5571', 'trades24H': 115614,
                    'nextFundingRate': '0.00000888425925925926', 'initialMarginFraction': '0.05',
                    'maintenanceMarginFraction': '0.03', 'openInterest': '594.8603', 'atomicResolution': -10,
                    'quantumConversionExponent': -9, 'tickSize': '1', 'stepSize': '0.0001',
                    'stepBaseQuantums': 1000000, 'subticksPerTick': 100000
                }
            }
        }
        return mock_response

    @property
    def trading_rules_request_erroneous_mock_response(self):
        mock_response = {
            "markets": {
                self.trading_pair: {
                    "ticker": self.trading_pair,
                    "status": "ACTIVE",
                }
            }
        }
        return mock_response

    @property
    def balance_request_mock_response_for_base_and_quote(self):
        return {}

    @property
    def balance_request_mock_response_only_base(self):
        return {}

    @property
    def balance_request_mock_response_only_quote(self):
        mock_response = {
            'subaccount':
                {
                    'address': 'dydx1nwtryq2dxy3a3wr5zyyvdsl5t40xx8qgvk6cm3',  # noqa: mock
                    'subaccountNumber': 0,
                    'equity': '10000',
                    'freeCollateral': '10000',
                    'openPerpetualPositions': {
                        self.trading_pair: {
                            'market': self.trading_pair, 'status': 'OPEN', 'side': 'SHORT', 'size': '-100',
                            'maxSize': '-100',
                            'entryPrice': '0.11123', 'exitPrice': None, 'realizedPnl': '-0.000011',
                            'unrealizedPnl': '-0.14263',
                            'createdAt': '2024-04-22T13:47:37.066Z', 'createdAtHeight': '13859546',
                            'closedAt': None,
                            'sumOpen': '100', 'sumClose': '0', 'netFunding': '-0.000011'
                        }
                    },
                    'assetPositions': {
                        'USDC': {'size': '92.486499', 'symbol': 'USDC', 'side': 'LONG', 'assetId': '0'}
                    },
                    'marginEnabled': True
                }
        }
        return mock_response

    @property
    def balance_event_websocket_update(self):
        mock_response = {
            'type': 'subscribed', 'connection_id': '53f4a7b1-410d-4687-9447-d6a367e30c8a', 'message_id': 1,
            'channel': 'v4_subaccounts',
            'id': 'dydx1nwtryq2dxy3a3wr5zyyvdsl5t40xx8qgvk6cm3/0', 'contents': {  # noqa: mock
                'subaccount': {
                    'address': 'dydx1nwtryq2dxy3a3wr5zyyvdsl5t40xx8qgvk6cm3', 'subaccountNumber': 0,  # noqa: mock
                    'equity': '0', 'freeCollateral': '700', 'openPerpetualPositions': {
                        'TRX-USD': {'market': 'TRX-USD', 'status': 'OPEN', 'side': 'SHORT', 'size': '-100',
                                    'maxSize': '-100',
                                    'entryPrice': '0.11123', 'exitPrice': None, 'realizedPnl': '0.001147',
                                    'unrealizedPnl': '-0.185044469', 'createdAt': '2024-04-22T13:47:37.066Z',
                                    'createdAtHeight': '13859546', 'closedAt': None, 'sumOpen': '100', 'sumClose': '0',
                                    'netFunding': '0.001147'}},
                    'assetPositions': {
                        'USDC': {'size': '92.487657', 'symbol': 'USDC', 'side': 'LONG', 'assetId': '0'}},
                    'marginEnabled': True
                }, 'orders': []}
        }
        return mock_response

    @property
    def expected_latest_price(self):
        return 62730.24877

    @property
    def target_funding_info_index_price(self):
        return 2

    @property
    def expected_supported_order_types(self):
        return [OrderType.LIMIT, OrderType.LIMIT_MAKER, OrderType.MARKET]

    @property
    def expected_trading_rule(self):
        trading_rules_resp = self.trading_rules_request_mock_response["markets"][self.trading_pair]
        return TradingRule(
            trading_pair=self.trading_pair,
            min_price_increment=Decimal(trading_rules_resp["tickSize"]),
            min_base_amount_increment=Decimal(trading_rules_resp["stepSize"]),
            supports_limit_orders=True,
            supports_market_orders=True,
            buy_order_collateral_token=self.quote_asset,
            sell_order_collateral_token=self.quote_asset,
        )

    @property
    def expected_logged_error_for_erroneous_trading_rule(self):
        return "Error updating trading rules"

    @property
    def expected_exchange_order_id(self):
        return self.exchange_order_id_prefix + "1"

    @property
    def is_order_fill_http_update_included_in_status_update(self) -> bool:
        return False

    @property
    def is_order_fill_http_update_executed_during_websocket_order_event_processing(self) -> bool:
        return False

    @property
    def expected_partial_fill_price(self) -> Decimal:
        return Decimal("100")

    @property
    def expected_partial_fill_amount(self) -> Decimal:
        return Decimal("10")

    @property
    def expected_partial_fill_fee(self) -> TradeFeeBase:
        return AddedToCostTradeFee(
            percent_token=self.quote_asset,
            flat_fees=[TokenAmount(token=self.quote_asset, amount=Decimal("0.1"))],
        )

    @property
    def expected_fill_fee(self) -> TradeFeeBase:
        return AddedToCostTradeFee(
            percent_token=self.quote_asset,
            flat_fees=[TokenAmount(token=self.quote_asset, amount=Decimal("10"))],
        )

    @property
    def expected_fill_trade_id(self) -> str:
        return "someFillId"

    def exchange_symbol_for_tokens(self, base_token: str, quote_token: str) -> str:
        return f"{base_token}-{quote_token}"

    @staticmethod
    def _callback_wrapper_with_response(callback: Callable, response: Any, *args, **kwargs):
        callback(args, kwargs)
        if isinstance(response, Exception):
            raise response
        else:
            return response

    def create_exchange_instance(self):
        client_config_map = ClientConfigAdapter(ClientConfigMap())
        exchange = DydxV4PerpetualDerivative(
            client_config_map,
            self.dydx_v4_perpetual_secret_phrase,
            self.dydx_v4_perpetual_chain_address,
            trading_pairs=[self.trading_pair],
        )
        exchange._tx_client = ProgrammableV4Client()

        exchange._margin_fractions[self.trading_pair] = {
            "initial": Decimal(0.1),
            "maintenance": Decimal(0.05),
            "clob_pair_id": "15",
            "atomicResolution": -4,
            "stepBaseQuantums": 1000000,
            "quantumConversionExponent": -9,
            "subticksPerTick": 1000000,
        }
        return exchange

    def validate_order_creation_request(self, order: InFlightOrder, request_call: RequestCall):
        raise NotImplementedError

    def validate_order_cancelation_request(self, order: InFlightOrder, request_call: RequestCall):
        raise NotImplementedError

    def validate_order_status_request(self, order: InFlightOrder, request_call: RequestCall):
        request_params = request_call.kwargs["params"]
        if request_params is not None:
            self.assertEqual(self.dydx_v4_perpetual_chain_address, request_params["address"])
            self.assertEqual(CONSTANTS.LAST_FILLS_MAX, request_params["limit"])

    def validate_trades_request(self, order: InFlightOrder, request_call: RequestCall):
        request_params = request_call.kwargs["params"]
        if request_params is not None:
            self.assertEqual(self.dydx_v4_perpetual_chain_address, request_params["address"])
            self.assertEqual(CONSTANTS.LAST_FILLS_MAX, request_params["limit"])

    def configure_all_symbols_response(
            self,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None,
    ) -> List[str]:

        url = self.all_symbols_url
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        response = self.all_symbols_request_mock_response
        mock_api.get(regex_url, body=json.dumps(response), callback=callback)
        return [url]

    def configure_successful_creation_order_status_response(
            self, callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> str:
        creation_response = self.order_creation_request_successful_mock_response
        mock_queue = AsyncMock()
        mock_queue.get.side_effect = partial(
            self._callback_wrapper_with_response, callback=callback, response=creation_response
        )
        self.exchange._tx_client._place_order_responses = mock_queue
        return ""

    def configure_erroneous_creation_order_status_response(
            self, callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> str:
        creation_response = self.order_creation_request_erroneous_mock_response

        mock_queue = AsyncMock()
        mock_queue.get.side_effect = partial(
            self._callback_wrapper_with_response, callback=callback, response=creation_response
        )
        self.exchange._tx_client._place_order_responses = mock_queue
        return ""

    def configure_successful_cancelation_response(
            self, order: InFlightOrder, mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> str:
        response = self._order_cancelation_request_successful_mock_response(order=order)
        mock_queue = AsyncMock()
        mock_queue.get.side_effect = partial(self._callback_wrapper_with_response, callback=callback, response=response)
        self.exchange._tx_client._cancel_order_responses = mock_queue
        return ""

    def configure_erroneous_cancelation_response(
            self, order: InFlightOrder, mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> str:
        response = self._order_cancelation_request_erroneous_mock_response(order=order)
        mock_queue = AsyncMock()
        mock_queue.get.side_effect = partial(self._callback_wrapper_with_response, callback=callback, response=response)
        self.exchange._tx_client._cancel_order_responses = mock_queue
        return ""

    def configure_one_successful_one_erroneous_cancel_all_response(
            self, successful_order: InFlightOrder, erroneous_order: InFlightOrder, mock_api: aioresponses
    ) -> List[str]:
        response = self._order_cancelation_request_successful_mock_response(order=successful_order)
        err_response = self._order_cancelation_request_erroneous_mock_response(order=erroneous_order)

        self.exchange._tx_client._cancel_order_responses.put_nowait(response)
        self.exchange._tx_client._cancel_order_responses.put_nowait(err_response)
        return []

    def configure_order_not_found_error_cancelation_response(
            self, order: InFlightOrder, mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> str:
        # Implement the expected not found response when enabling test_cancel_order_not_found_in_the_exchange
        raise NotImplementedError

    def configure_order_not_found_error_order_status_response(
            self, order: InFlightOrder, mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> List[str]:
        # Implement the expected not found response when enabling
        # test_lost_order_removed_if_not_found_during_order_status_update
        raise NotImplementedError

    def configure_completely_filled_order_status_response(
            self, order: InFlightOrder, mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> List[str]:
        """
        :return: the URL configured
        """
        url_order_status = web_utils.private_rest_url(CONSTANTS.PATH_ORDERS)
        regex_url = re.compile(f"^{url_order_status}".replace(".", r"\.").replace("?", r"\?") + ".*")

        response_order_status = self._order_status_request_completely_filled_mock_response(order=order)
        mock_api.get(regex_url, body=json.dumps(response_order_status), callback=callback)

        return [url_order_status]

    def configure_canceled_order_status_response(
            self, order: InFlightOrder, mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> List[str]:
        """
        :return: the URL configured
        """
        url_fills = web_utils.private_rest_url(CONSTANTS.PATH_FILLS)
        regex_url = re.compile(f"^{url_fills}".replace(".", r"\.").replace("?", r"\?") + ".*")

        response_fills = self._order_fills_request_canceled_mock_response(order=order)
        mock_api.get(regex_url, body=json.dumps(response_fills), callback=callback)

        url_order_status = web_utils.private_rest_url(CONSTANTS.PATH_ORDERS)
        regex_url = re.compile(f"^{url_order_status}".replace(".", r"\.").replace("?", r"\?") + ".*")

        response_order_status = self._order_status_request_canceled_mock_response(order=order)
        mock_api.get(regex_url, body=json.dumps(response_order_status), callback=callback)

        return [url_fills, url_order_status]

    def configure_open_order_status_response(
            self, order: InFlightOrder, mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> List[str]:
        """
        :return: the URL configured
        """
        url = web_utils.private_rest_url(CONSTANTS.PATH_ORDERS)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        response = self._order_status_request_open_mock_response(order=order)
        mock_api.get(regex_url, body=json.dumps(response), callback=callback)
        return [url]

    def configure_http_error_order_status_response(
            self, order: InFlightOrder, mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> str:
        """
        :return: the URL configured
        """
        url = web_utils.private_rest_url(CONSTANTS.PATH_ORDERS)

        regex_url = re.compile(url + r"\?.*")
        mock_api.get(regex_url, status=404, callback=callback)
        return url

    def configure_partially_filled_order_status_response(
            self, order: InFlightOrder, mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> List[str]:
        # Dydx has no partial fill status
        raise NotImplementedError

    def configure_partial_fill_trade_response(
            self, order: InFlightOrder, mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> str:
        # Dydx has no partial fill status
        raise NotImplementedError

    def configure_erroneous_http_fill_trade_response(
            self, order: InFlightOrder, mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> str:
        """
        :return: the URL configured
        """
        url = web_utils.private_rest_url(CONSTANTS.PATH_ORDERS)
        regex_url = re.compile(url + r"\?.*")
        mock_api.get(regex_url, status=400, callback=callback)
        return url

    def configure_full_fill_trade_response(
            self, order: InFlightOrder, mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> str:
        """
        :return: the URL configured
        """
        url = web_utils.private_rest_url(CONSTANTS.PATH_FILLS)

        regex_url = re.compile(url + r"\?.*")
        response = self._order_fills_request_full_fill_mock_response(order=order)
        mock_api.get(regex_url, body=json.dumps(response), callback=callback)
        return url

    def _order_fills_request_completely_filled_mock_response(self, order: InFlightOrder) -> Any:
        return {
            "fills": [
                {
                    "id": self.expected_fill_trade_id,
                    "side": order.trade_type.name,
                    "liquidity": "MAKER" if order.order_type in [OrderType.LIMIT, OrderType.LIMIT_MAKER] else "TAKER",
                    "market": self.trading_pair,
                    "orderId": self.exchange_order_id_prefix + "1",
                    "size": str(order.amount),
                    "price": str(order.price),
                    "fee": str(self.expected_fill_fee.flat_fees[0].amount),
                    "transactionId": "1",
                    "orderClientId": order.client_order_id,
                    "createdAt": "2020-09-22T20:25:26.399Z",
                }
            ]
        }

    def _order_fills_request_canceled_mock_response(self, order: InFlightOrder) -> Any:
        return {"fills": []}

    def _order_status_request_completely_filled_mock_response(self, order: InFlightOrder) -> Any:
        mock_response = [
            {
                "id": self.exchange_order_id_prefix + "1",
                "clientId": order.client_order_id,
                "accountId": "someAccountId",
                "market": self.trading_pair,
                "side": order.trade_type.name,
                "price": str(order.price),
                "triggerPrice": None,
                "trailingPercent": None,
                "size": str(order.amount),
                "remainingSize": "0",
                "type": "LIMIT",
                "createdAt": "2021-01-04T23:44:59.690Z",
                "unfillableAt": None,
                "expiresAt": "2022-12-21T21:30:20.200Z",
                "status": "FILLED",
                "timeInForce": "GTT",
                "postOnly": False,
                "reduceOnly": False,
                "cancelReason": None,
            }
        ]
        return mock_response

    def _order_status_request_canceled_mock_response(self, order: InFlightOrder) -> Any:
        resp = [
            {
                "id": self.exchange_order_id_prefix + "1",
                "clientId": order.client_order_id,
                "accountId": "someAccountId",
                "market": self.trading_pair,
                "side": order.trade_type.name,
                "price": str(order.price),
                "triggerPrice": None,
                "trailingPercent": None,
                "size": 0,
                "remainingSize": "0",
                "type": "LIMIT",
                "createdAt": "2021-01-04T23:44:59.690Z",
                "unfillableAt": None,
                "expiresAt": "2022-12-21T21:30:20.200Z",
                "status": "CANCELED",
                "timeInForce": "GTT",
                "postOnly": False,
                "reduceOnly": False,
                "cancelReason": None,
            }
        ]
        return resp

    def _order_status_request_open_mock_response(self, order: InFlightOrder) -> Any:
        resp = self._order_status_request_completely_filled_mock_response(order)
        resp[0]["status"] = "OPEN"
        resp[0]["remainingSize"] = resp[0]["size"]
        return resp

    def _order_fills_request_partial_fill_mock_response(self, order: InFlightOrder):
        return {
            "fills": [
                {
                    "id": self.expected_fill_trade_id,
                    "side": order.trade_type.name,
                    "liquidity": "MAKER" if order.order_type in [OrderType.LIMIT, OrderType.LIMIT_MAKER] else "TAKER",
                    "market": self.trading_pair,
                    "orderId": order.exchange_order_id,
                    "size": str(order.amount),
                    "price": str(order.price),
                    "fee": str(self.expected_fill_fee.flat_fees[0].amount),
                    "transactionId": "1",
                    "orderClientId": order.client_order_id,
                    "createdAt": "2020-09-22T20:25:26.399Z",
                }
            ]
        }

    def _order_fills_request_full_fill_mock_response(self, order: InFlightOrder):
        return {
            "fills": [
                {
                    "id": self.expected_fill_trade_id,
                    "side": order.trade_type.name,
                    "liquidity": "MAKER" if order.order_type in [OrderType.LIMIT, OrderType.LIMIT_MAKER] else "TAKER",
                    "market": self.trading_pair,
                    "orderId": order.exchange_order_id,
                    "size": str(order.amount),
                    "price": str(order.price),
                    "fee": str(self.expected_fill_fee.flat_fees[0].amount),
                    "transactionId": "1",
                    "orderClientId": order.client_order_id,
                    "createdAt": "2020-09-22T20:25:26.399Z",
                }
            ]
        }

    def _simulate_trading_rules_initialized(self):
        self.exchange._trading_rules = {
            self.trading_pair: TradingRule(
                trading_pair=self.trading_pair,
                min_order_size=Decimal(str(0.01)),
                min_price_increment=Decimal(str(0.0001)),
                min_base_amount_increment=Decimal(str(0.000001)),
            )
        }
        self.exchange._margin_fractions[self.trading_pair] = {
            "initial": Decimal(0.1),
            "maintenance": Decimal(0.05),
            "clob_pair_id": "15",
            "atomicResolution": -4,
            "stepBaseQuantums": 1000000,
            "quantumConversionExponent": -9,
            "subticksPerTick": 1000000,
        }

    def order_event_for_new_order_websocket_update(self, order: InFlightOrder):
        return {
            "type": CONSTANTS.WS_TYPE_CHANNEL_DATA,
            "channel": CONSTANTS.WS_CHANNEL_ACCOUNTS,
            "connection_id": "someConnectionId",
            "message_id": 2,
            "contents": {
                "orders": [
                    {
                        "id": order.exchange_order_id,
                        "clientId": self.client_order_id_prefix + "1",
                        "ticker": self.trading_pair,
                        "side": order.trade_type.name,
                        "size": str(order.amount),
                        "remainingSize": "0",
                        "price": str(order.price),
                        "limitFee": str(self.expected_fill_fee.flat_fees[0].amount),
                        "type": "LIMIT",
                        "status": "OPEN",
                        "signature": "0x456...",
                        "timeInForce": "FOK",
                        "postOnly": "False",
                        "expiresAt": "2021-09-22T20:22:26.399Z",
                        "createdAt": "2020-09-22T20:22:26.399Z",
                    }
                ]
            }
        }

    def order_event_for_canceled_order_websocket_update(self, order: InFlightOrder):
        return {
            "type": CONSTANTS.WS_TYPE_CHANNEL_DATA,
            "channel": CONSTANTS.WS_CHANNEL_ACCOUNTS,
            "connection_id": "someConnectionId",
            "message_id": 2,
            "contents": {
                "orders": [
                    {
                        "id": order.exchange_order_id,
                        "clientId": order.client_order_id,
                        "ticker": self.trading_pair,
                        "side": order.trade_type.name,
                        "size": str(order.amount),
                        "remainingSize": "0",
                        "price": str(order.price),
                        "limitFee": str(self.expected_fill_fee.flat_fees[0].amount),
                        "type": "LIMIT",
                        "status": "CANCELED",
                        "signature": "0x456...",
                        "timeInForce": "FOK",
                        "postOnly": "False",
                        "expiresAt": "2021-09-22T20:22:26.399Z",
                        "createdAt": "2020-09-22T20:22:26.398Z",
                    }
                ]
            }
        }

    def order_event_for_full_fill_websocket_update(self, order: InFlightOrder):
        return {
            "type": CONSTANTS.WS_TYPE_CHANNEL_DATA,
            "channel": CONSTANTS.WS_CHANNEL_ACCOUNTS,
            "connection_id": "someConnectionId",
            "message_id": 2,
            "contents": {
                "orders": [
                    {
                        "id": order.exchange_order_id,
                        "clientId": order.client_order_id,
                        "ticker": self.trading_pair,
                        "side": order.trade_type.name,
                        "size": str(order.amount),
                        "remainingSize": "0",
                        "price": str(order.price),
                        "limitFee": str(self.expected_fill_fee.flat_fees[0].amount),
                        "type": "LIMIT",
                        "status": "FILLED",
                        "signature": "0x456...",
                        "timeInForce": "FOK",
                        "postOnly": "False",
                        "expiresAt": "2021-09-22T20:22:26.399Z",
                        "createdAt": "2020-09-22T20:22:26.399Z",
                    }
                ]
            }
        }

    def trade_event_for_full_fill_websocket_update(self, order: InFlightOrder):
        return {
            "type": CONSTANTS.WS_TYPE_CHANNEL_DATA,
            "channel": CONSTANTS.WS_CHANNEL_ACCOUNTS,
            "connection_id": "someConnectionId",
            "message_id": 2,
            "contents": {
                "fills": [
                    {
                        "id": self.expected_fill_trade_id,
                        "side": order.trade_type.name,
                        "liquidity": "MAKER"
                        if order.order_type in [OrderType.LIMIT, OrderType.LIMIT_MAKER]
                        else "TAKER",
                        "ticker": self.trading_pair,
                        "orderId": order.exchange_order_id,
                        "size": str(order.amount),
                        "price": str(order.price),
                        "fee": str(self.expected_fill_fee.flat_fees[0].amount),
                        "transactionId": "1",
                        "orderClientId": order.client_order_id,
                        "createdAt": "2020-09-22T20:25:26.399Z",
                    }
                ]
            }
        }

    @property
    def funding_info_url(self):
        url = web_utils.public_rest_url(CONSTANTS.PATH_MARKETS)
        url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        return url

    @property
    def funding_payment_url(self):
        pass

    @property
    def funding_info_mock_response(self):
        mock_response = {
            "markets": {
                self.trading_pair: {
                    "market": self.trading_pair,
                    "status": "ONLINE",
                    "baseAsset": self.base_asset,
                    "quoteAsset": self.quote_asset,
                    "stepSize": "0.1",
                    "tickSize": "0.01",
                    "oraclePrice": "2",
                    "priceChange24H": "0",
                    "nextFundingRate": "3",
                    "nextFundingAt": "2022-07-06T09:17:33.000Z",
                    "minOrderSize": "1",
                    "type": "PERPETUAL",
                    "initialMarginFraction": "0.10",
                    "maintenanceMarginFraction": "0.05",
                    "baselinePositionSize": "1000",
                    "incrementalPositionSize": "1000",
                    "incrementalInitialMarginFraction": "0.2",
                    "volume24H": "0",
                    "trades24H": "0",
                    "openInterest": "0",
                    "maxPositionSize": "10000",
                    "assetResolution": "10000000",
                    "syntheticAssetId": "0x4c494e4b2d37000000000000000000",
                }
            }
        }
        return mock_response

    def validate_auth_credentials_present(self, request_call: RequestCall):
        request_headers = request_call.kwargs["headers"]
        self.assertEqual("application/json", request_headers["Accept"])

    @property
    def funding_payment_mock_response(self):
        raise NotImplementedError

    def empty_funding_payment_mock_response(self):
        pass

    @aioresponses()
    def test_funding_payment_polling_loop_sends_update_event(self, *args, **kwargs):
        pass

    def position_event_for_full_fill_websocket_update(self, order: InFlightOrder, unrealized_pnl: float):
        return {
            "type": CONSTANTS.WS_TYPE_CHANNEL_DATA,
            "channel": CONSTANTS.WS_CHANNEL_ACCOUNTS,
            "connection_id": "someConnectionId",
            "message_id": 2,
            "contents": {
                'perpetualPositions': [{
                    'address': 'dydx1nwtryq2dxy3a3wr5zyyvdsl5t40xx8qgvk6cm3', 'subaccountNumber': 0,  # noqa: mock
                    'positionId': '5388e4bc-0e4c-5794-8dec-da4ace4b6189',
                    'market': self.trading_pair,
                    'side': "LONG" if order.trade_type == TradeType.BUY else "SHORT",
                    'status': 'CLOSED',
                    'size': str(order.amount) if order.order_type == TradeType.BUY else str(
                        -order.amount), 'maxSize': '-100', 'netFunding': '0.001147',
                    'entryPrice': '10000', 'exitPrice': None, 'sumOpen': '100', 'sumClose': '0',
                    'realizedPnl': '0.001147', 'unrealizedPnl': str(unrealized_pnl)
                }],
                'assetPositions': [
                    {'address': 'dydx1nwtryq2dxy3a3wr5zyyvdsl5t40xx8qgvk6cm3', 'subaccountNumber': 0,  # noqa: mock
                     'positionId': 'fb5b6131-2871-54c1-86a2-5be9147fe4bc', 'assetId': '0', 'symbol': 'USDC',
                     'side': 'LONG',
                     'size': '103.802996'}]}
        }

    def configure_successful_set_position_mode(
            self,
            position_mode: PositionMode,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None,
    ):
        # There's only one way position mode
        pass

    def configure_failed_set_position_mode(
            self,
            position_mode: PositionMode,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None,
    ) -> Tuple[str, str]:
        # There's only one way position mode, this should never be called
        pass

    def configure_failed_set_leverage(
            self,
            leverage: int,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None,
    ) -> Tuple[str, str]:
        url = web_utils.public_rest_url(CONSTANTS.PATH_MARKETS)
        regex_url = re.compile(f"^{url}")

        # No "markets" in response
        mock_response = {}
        mock_api.get(regex_url, body=json.dumps(mock_response), callback=callback)

        return url, "Failed to obtain markets information."

    def configure_successful_set_leverage(
            self,
            leverage: int,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None,
    ):
        url = web_utils.public_rest_url(CONSTANTS.PATH_MARKETS)
        regex_url = re.compile(f"^{url}")

        # No "markets" in response
        mock_response = {
            "markets": {
                self.trading_pair: {
                    "initialMarginFraction": "0.10",
                    "maintenanceMarginFraction": "0.05",
                    "clobPairId": "15",
                    "atomicResolution": -4,
                    "stepBaseQuantums": 1000000,
                    "quantumConversionExponent": -9,
                    "subticksPerTick": 1000000,
                }
            }
        }
        mock_api.get(regex_url, body=json.dumps(mock_response), callback=callback)

        return url

    def funding_info_event_for_websocket_update(self):
        return {
            "type": CONSTANTS.WS_TYPE_CHANNEL_DATA,
            "connection_id": "someConnectionId",
            "channel": CONSTANTS.WS_CHANNEL_MARKETS,
            "message_id": 2,
            "contents": {
                "markets": {
                    self.trading_pair: {
                        "oraclePrice": "100.23",
                        "priceChange24H": "0.12",
                        "initialMarginFraction": "1.23",
                    }
                }
            }
        }

    def test_get_buy_and_sell_collateral_tokens(self):
        self._simulate_trading_rules_initialized()

        linear_buy_collateral_token = self.exchange.get_buy_collateral_token(self.trading_pair)
        linear_sell_collateral_token = self.exchange.get_sell_collateral_token(self.trading_pair)

        self.assertEqual(self.quote_asset, linear_buy_collateral_token)
        self.assertEqual(self.quote_asset, linear_sell_collateral_token)

    @aioresponses()
    def test_update_balances(self, mock_api):
        response = self.balance_request_mock_response_only_quote

        self._configure_balance_response(response=response, mock_api=mock_api)
        self.async_run_with_timeout(self.exchange._update_balances())

        available_balances = self.exchange.available_balances
        total_balances = self.exchange.get_all_balances()

        self.assertNotIn(self.base_asset, available_balances)
        self.assertNotIn(self.base_asset, total_balances)
        self.assertEqual(Decimal("10000"), available_balances["USD"])
        self.assertEqual(Decimal("10000"), total_balances["USD"])

    def test_user_stream_balance_update(self):
        if self.exchange.real_time_balance_update:
            self.exchange._set_current_timestamp(1640780000)

            balance_event = self.balance_event_websocket_update

            mock_queue = AsyncMock()
            mock_queue.get.side_effect = [balance_event, asyncio.CancelledError]
            self.exchange._user_stream_tracker._user_stream = mock_queue

            try:
                self.async_run_with_timeout(self.exchange._user_stream_event_listener())
            except asyncio.CancelledError:
                pass

            self.assertEqual(Decimal("700"), self.exchange.available_balances["USD"])
            self.assertEqual(Decimal("0"), self.exchange.get_balance("USD"))

    @aioresponses()
    def test_update_order_status_when_order_has_not_changed_and_one_partial_fill(self, mock_api):
        # Dydx has no partial fill status
        pass

    @aioresponses()
    def test_update_order_status_when_order_partially_filled_and_cancelled(self, mock_api):
        # Dydx has no partial fill status
        pass

    @aioresponses()
    def test_user_stream_update_for_partially_cancelled_order(self, mock_api):
        # Dydx has no partial fill status
        pass

    @aioresponses()
    def test_set_position_mode_success(self, mock_api):
        # There's only ONEWAY position mode
        pass

    @aioresponses()
    def test_set_position_mode_failure(self, mock_api):
        # There's only ONEWAY position mode
        pass

    @aioresponses()
    def test_cancel_order_not_found_in_the_exchange(self, mock_api):
        # Disabling this test because the connector has not been updated yet to validate
        # order not found during cancellation (check _is_order_not_found_during_cancelation_error)
        pass

    @aioresponses()
    def test_lost_order_removed_if_not_found_during_order_status_update(self, mock_api):
        # Disabling this test because the connector has not been updated yet to validate
        # order not found during status update (check _is_order_not_found_during_status_update_error)
        pass

    @aioresponses()
    def test_update_order_status_when_canceled(self, mock_api):
        self._simulate_trading_rules_initialized()
        self.exchange._set_current_timestamp(1640780000)

        self.exchange.start_tracking_order(
            order_id=self.client_order_id_prefix + "1",
            exchange_order_id=self.expected_exchange_order_id,
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("1"),
        )
        order = self.exchange.in_flight_orders[self.client_order_id_prefix + "1"]

        self.configure_canceled_order_status_response(
            order=order,
            mock_api=mock_api)

        self.async_run_with_timeout(self.exchange._update_order_status())
        cancel_event = self.order_cancelled_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp, cancel_event.timestamp)
        self.assertEqual(order.client_order_id, cancel_event.order_id)
        self.assertEqual(order.exchange_order_id, cancel_event.exchange_order_id)
        self.assertNotIn(order.client_order_id, self.exchange.in_flight_orders)
        self.assertTrue(
            self.is_logged("INFO", f"Successfully canceled order {order.client_order_id}.")
        )

    @aioresponses()
    def test_update_order_status_when_filled(self, mock_api):
        self._simulate_trading_rules_initialized()
        self.exchange._set_current_timestamp(1640780000)
        request_sent_event = asyncio.Event()

        self.exchange.start_tracking_order(
            order_id=self.client_order_id_prefix + "1",
            exchange_order_id=self.exchange_order_id_prefix + "1",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("1"),
            position_action=PositionAction.OPEN,
        )
        order: InFlightOrder = self.exchange.in_flight_orders[self.client_order_id_prefix + "1"]

        self.configure_completely_filled_order_status_response(
            order=order,
            mock_api=mock_api,
            callback=lambda *args, **kwargs: request_sent_event.set())

        if self.is_order_fill_http_update_included_in_status_update:
            trade_url = self.configure_full_fill_trade_response(
                order=order,
                mock_api=mock_api)
        else:
            # If the fill events will not be requested with the order status, we need to manually set the event
            # to allow the ClientOrderTracker to process the last status update
            order.completely_filled_event.set()
        self.async_run_with_timeout(self.exchange._update_order_status())
        # Execute one more synchronization to ensure the async task that processes the update is finished
        self.async_run_with_timeout(request_sent_event.wait())

        self.async_run_with_timeout(order.wait_until_completely_filled())
        self.assertTrue(order.is_done)

        if self.is_order_fill_http_update_included_in_status_update:
            self.assertTrue(order.is_filled)

            if trade_url:
                trades_request = self._all_executed_requests(mock_api, trade_url)[0]
                self.validate_auth_credentials_present(trades_request)
                self.validate_trades_request(
                    order=order,
                    request_call=trades_request)

            fill_event = self.order_filled_logger.event_log[0]
            self.assertEqual(self.exchange.current_timestamp, fill_event.timestamp)
            self.assertEqual(order.client_order_id, fill_event.order_id)
            self.assertEqual(order.trading_pair, fill_event.trading_pair)
            self.assertEqual(order.trade_type, fill_event.trade_type)
            self.assertEqual(order.order_type, fill_event.order_type)
            self.assertEqual(order.price, fill_event.price)
            self.assertEqual(order.amount, fill_event.amount)
            self.assertEqual(self.expected_fill_fee, fill_event.trade_fee)
            self.assertEqual(PositionAction.OPEN.value, fill_event.position)

        buy_event = self.buy_order_completed_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp, buy_event.timestamp)
        self.assertEqual(order.client_order_id, buy_event.order_id)
        self.assertEqual(order.base_asset, buy_event.base_asset)
        self.assertEqual(order.quote_asset, buy_event.quote_asset)
        self.assertEqual(
            order.amount if self.is_order_fill_http_update_included_in_status_update else Decimal(0),
            buy_event.base_asset_amount)
        self.assertEqual(
            order.amount * order.price
            if self.is_order_fill_http_update_included_in_status_update
            else Decimal(0),
            buy_event.quote_asset_amount)
        self.assertEqual(order.order_type, buy_event.order_type)
        self.assertEqual(order.exchange_order_id, buy_event.exchange_order_id)
        self.assertNotIn(order.client_order_id, self.exchange.in_flight_orders)
        self.assertTrue(
            self.is_logged(
                "INFO",
                f"BUY order {order.client_order_id} completely filled."
            )
        )

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
                self.exchange._order_tracker.process_order_not_found(client_order_id=order.client_order_id))

        self.assertNotIn(order.client_order_id, self.exchange.in_flight_orders)

        self.configure_completely_filled_order_status_response(
            order=order,
            mock_api=mock_api,
            callback=lambda *args, **kwargs: request_sent_event.set())

        if self.is_order_fill_http_update_included_in_status_update:
            trade_url = self.configure_full_fill_trade_response(
                order=order,
                mock_api=mock_api,
                callback=lambda *args, **kwargs: request_sent_event.set())
        else:
            # If the fill events will not be requested with the order status, we need to manually set the event
            # to allow the ClientOrderTracker to process the last status update
            order.completely_filled_event.set()
            request_sent_event.set()

        self.async_run_with_timeout(self.exchange._update_order_status())
        # Execute one more synchronization to ensure the async task that processes the update is finished
        self.async_run_with_timeout(request_sent_event.wait())

        self.async_run_with_timeout(order.wait_until_completely_filled())
        self.assertTrue(order.is_done)
        self.assertTrue(order.is_failure)

        if self.is_order_fill_http_update_included_in_status_update:
            if trade_url:
                trades_request = self._all_executed_requests(mock_api, trade_url)[0]
                self.validate_auth_credentials_present(trades_request)
                self.validate_trades_request(
                    order=order,
                    request_call=trades_request)

            fill_event = self.order_filled_logger.event_log[0]
            self.assertEqual(self.exchange.current_timestamp, fill_event.timestamp)
            self.assertEqual(order.client_order_id, fill_event.order_id)
            self.assertEqual(order.trading_pair, fill_event.trading_pair)
            self.assertEqual(order.trade_type, fill_event.trade_type)
            self.assertEqual(order.order_type, fill_event.order_type)
            self.assertEqual(order.price, fill_event.price)
            self.assertEqual(order.amount, fill_event.amount)
            self.assertEqual(self.expected_fill_fee, fill_event.trade_fee)

        self.assertEqual(0, len(self.buy_order_completed_logger.event_log))
        self.assertIn(order.client_order_id, self.exchange._order_tracker.all_fillable_orders)
        self.assertFalse(
            self.is_logged(
                "INFO",
                f"BUY order {order.client_order_id} completely filled."
            )
        )

        request_sent_event.clear()

        # Configure again the response to the order fills request since it is required by lost orders update logic
        self.configure_full_fill_trade_response(
            order=order,
            mock_api=mock_api,
            callback=lambda *args, **kwargs: request_sent_event.set())

        self.async_run_with_timeout(self.exchange._update_lost_orders_status())
        # Execute one more synchronization to ensure the async task that processes the update is finished
        self.async_run_with_timeout(request_sent_event.wait())

        self.assertTrue(order.is_done)
        self.assertTrue(order.is_failure)

        self.assertEqual(1, len(self.order_filled_logger.event_log))
        self.assertEqual(0, len(self.buy_order_completed_logger.event_log))
        self.assertNotIn(order.client_order_id, self.exchange._order_tracker.all_fillable_orders)
        self.assertFalse(
            self.is_logged(
                "INFO",
                f"BUY order {order.client_order_id} completely filled."
            )
        )

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

        create_event = self.buy_order_created_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp, create_event.timestamp)
        self.assertEqual(self.trading_pair, create_event.trading_pair)
        self.assertEqual(OrderType.LIMIT, create_event.type)
        self.assertEqual(Decimal("100"), create_event.amount)
        self.assertEqual(Decimal("10000"), create_event.price)
        self.assertEqual(order_id, create_event.order_id)

        self.assertTrue(
            self.is_logged(
                "INFO",
                f"Created {OrderType.LIMIT.name} {TradeType.BUY.name} order {order_id} for "
                f"{Decimal('100.000000')} to {PositionAction.OPEN.name} a {self.trading_pair} position."
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

        create_event = self.sell_order_created_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp, create_event.timestamp)
        self.assertEqual(self.trading_pair, create_event.trading_pair)
        self.assertEqual(OrderType.LIMIT, create_event.type)
        self.assertEqual(Decimal("100"), create_event.amount)
        self.assertEqual(Decimal("10000"), create_event.price)
        self.assertEqual(order_id, create_event.order_id)

        self.assertTrue(
            self.is_logged(
                "INFO",
                f"Created {OrderType.LIMIT.name} {TradeType.SELL.name} order {order_id} for "
                f"{Decimal('100.000000')} to {PositionAction.OPEN.name} a {self.trading_pair} position."
            )
        )

    @aioresponses()
    def test_create_buy_market_order_successfully(self, mock_api):
        self._simulate_trading_rules_initialized()
        request_sent_event = asyncio.Event()
        self.exchange._set_current_timestamp(1640780000)

        order_book = OrderBook()
        self.exchange.order_book_tracker._order_books[self.trading_pair] = order_book
        order_book.apply_snapshot(
            bids=[],
            asks=[OrderBookRow(price=5000, amount=20, update_id=1)],
            update_id=1,
        )

        self.configure_successful_creation_order_status_response(
            callback=lambda *args, **kwargs: request_sent_event.set()
        )

        order_id = self.exchange.buy(
            trading_pair=self.trading_pair,
            amount=Decimal("10"),
            order_type=OrderType.MARKET,
            price=Decimal("50000"),
            position_action=PositionAction.OPEN,
        )
        self.async_run_with_timeout(request_sent_event.wait())

        self.assertEqual(1, len(self.exchange.in_flight_orders))
        self.assertIn(order_id, self.exchange.in_flight_orders)

    @aioresponses()
    def test_create_sell_market_order_successfully(self, mock_api):
        self._simulate_trading_rules_initialized()
        request_sent_event = asyncio.Event()
        self.exchange._set_current_timestamp(1640780000)

        order_book = OrderBook()
        self.exchange.order_book_tracker._order_books[self.trading_pair] = order_book
        order_book.apply_snapshot(
            bids=[OrderBookRow(price=5000, amount=20, update_id=1)],
            asks=[],
            update_id=1,
        )

        self.configure_successful_creation_order_status_response(
            callback=lambda *args, **kwargs: request_sent_event.set()
        )

        order_id = self.exchange.sell(
            trading_pair=self.trading_pair,
            amount=Decimal("10"),
            order_type=OrderType.MARKET,
            price=Decimal("10_000"),
            position_action=PositionAction.OPEN,
        )

        self.async_run_with_timeout(request_sent_event.wait())

        self.assertEqual(1, len(self.exchange.in_flight_orders))
        self.assertIn(order_id, self.exchange.in_flight_orders)

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
        failure_event = self.order_failure_logger.event_log[0]
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
    def test_create_order_to_close_long_position(self, mock_api):
        self._simulate_trading_rules_initialized()
        request_sent_event = asyncio.Event()
        self.exchange._set_current_timestamp(1640780000)

        self.configure_successful_creation_order_status_response(
            callback=lambda *args, **kwargs: request_sent_event.set()
        )

        leverage = 5
        self.exchange._perpetual_trading.set_leverage(self.trading_pair, leverage)
        order_id = self.place_sell_order(position_action=PositionAction.CLOSE)
        self.async_run_with_timeout(request_sent_event.wait())

        create_event = self.sell_order_created_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp, create_event.timestamp)
        self.assertEqual(self.trading_pair, create_event.trading_pair)
        self.assertEqual(OrderType.LIMIT, create_event.type)
        self.assertEqual(Decimal("100"), create_event.amount)
        self.assertEqual(Decimal("10000"), create_event.price)
        self.assertEqual(order_id, create_event.order_id)
        self.assertEqual(leverage, create_event.leverage)
        self.assertEqual(PositionAction.CLOSE.value, create_event.position)

        self.assertTrue(
            self.is_logged(
                "INFO",
                f"Created {OrderType.LIMIT.name} {TradeType.SELL.name} order {order_id} for "
                f"{Decimal('100.000000')} to {PositionAction.CLOSE.name} a {self.trading_pair} position."
            )
        )

    @aioresponses()
    def test_create_order_to_close_short_position(self, mock_api):
        self._simulate_trading_rules_initialized()
        request_sent_event = asyncio.Event()
        self.exchange._set_current_timestamp(1640780000)

        self.configure_successful_creation_order_status_response(
            callback=lambda *args, **kwargs: request_sent_event.set()
        )

        leverage = 4
        self.exchange._perpetual_trading.set_leverage(self.trading_pair, leverage)
        order_id = self.place_buy_order(position_action=PositionAction.CLOSE)
        self.async_run_with_timeout(request_sent_event.wait())

        create_event = self.buy_order_created_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp,
                         create_event.timestamp)
        self.assertEqual(self.trading_pair, create_event.trading_pair)
        self.assertEqual(OrderType.LIMIT, create_event.type)
        self.assertEqual(Decimal("100"), create_event.amount)
        self.assertEqual(Decimal("10000"), create_event.price)
        self.assertEqual(order_id, create_event.order_id)
        self.assertEqual(leverage, create_event.leverage)
        self.assertEqual(PositionAction.CLOSE.value, create_event.position)

        self.assertTrue(
            self.is_logged(
                "INFO",
                f"Created {OrderType.LIMIT.name} {TradeType.BUY.name} order {order_id} for "
                f"{Decimal('100.000000')} to {PositionAction.CLOSE.name} a {self.trading_pair} position."
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
            amount=Decimal("0.0001"), price=Decimal("0.0001")
        )
        # The second order is used only to have the event triggered and avoid using timeouts for tests
        order_id = self.place_buy_order()
        self.async_run_with_timeout(request_sent_event.wait())

        self.assertNotIn(order_id_for_invalid_order, self.exchange.in_flight_orders)
        self.assertNotIn(order_id, self.exchange.in_flight_orders)

        self.assertEquals(0, len(self.buy_order_created_logger.event_log))
        failure_event = self.order_failure_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp, failure_event.timestamp)
        self.assertEqual(OrderType.LIMIT, failure_event.order_type)
        self.assertEqual(order_id_for_invalid_order, failure_event.order_id)

        self.assertTrue(
            self.is_logged(
                "WARNING",
                "Buy order amount 0.0001 is lower than the minimum order "
                "size 0.01. The order will not be created, increase the "
                "amount to be higher than the minimum order size."
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

        self.assertNotIn(order.client_order_id, self.exchange.in_flight_orders)
        self.assertTrue(order.is_cancelled)
        cancel_event = self.order_cancelled_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp, cancel_event.timestamp)
        self.assertEqual(order.client_order_id, cancel_event.order_id)

        self.assertTrue(
            self.is_logged(
                "INFO",
                f"Successfully canceled order {order.client_order_id}."
            )
        )

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
    def test_set_leverage_success(self, mock_api):
        self._simulate_trading_rules_initialized()
        request_sent_event = asyncio.Event()
        target_leverage = 2
        self.configure_successful_set_leverage(
            leverage=target_leverage,
            mock_api=mock_api,
            callback=lambda *args, **kwargs: request_sent_event.set(),
        )
        self.exchange.set_leverage(trading_pair=self.trading_pair, leverage=target_leverage)
        self.async_run_with_timeout(request_sent_event.wait())

        self.assertTrue(
            self.is_logged(
                log_level="INFO",
                message=f"Leverage for {self.trading_pair} successfully set to {target_leverage}.",
            )
        )

    @aioresponses()
    @patch("asyncio.Queue.get")
    @patch("hummingbot.connector.derivative.dydx_v4_perpetual.dydx_v4_perpetual_api_order_book_data_source."
           "DydxV4PerpetualAPIOrderBookDataSource._next_funding_time")
    def test_listen_for_funding_info_update_initializes_funding_info(self, mock_api, _next_funding_time_mock,
                                                                     mock_queue_get):
        _next_funding_time_mock.return_value = self.target_funding_info_next_funding_utc_timestamp
        url = self.funding_info_url

        response = self.funding_info_mock_response
        mock_api.get(url, body=json.dumps(response))

        event_messages = [asyncio.CancelledError]
        mock_queue_get.side_effect = event_messages

        try:
            self.async_run_with_timeout(self.exchange._listen_for_funding_info())
        except asyncio.CancelledError:
            pass

        funding_info = self.exchange.get_funding_info(self.trading_pair)

        self.assertEqual(self.trading_pair, funding_info.trading_pair)
        self.assertEqual(self.target_funding_info_index_price, funding_info.index_price)
        self.assertEqual(self.target_funding_info_mark_price, funding_info.mark_price)
        self.assertEqual(
            self.target_funding_info_next_funding_utc_timestamp, funding_info.next_funding_utc_timestamp
        )
        self.assertEqual(self.target_funding_info_rate, funding_info.rate)
