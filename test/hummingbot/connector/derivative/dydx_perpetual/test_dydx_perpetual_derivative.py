import asyncio
import json
import re
from decimal import Decimal
from typing import Any, Callable, List, Optional, Tuple
from unittest.mock import AsyncMock

from aioresponses import aioresponses
from aioresponses.core import RequestCall

import hummingbot.connector.derivative.dydx_perpetual.dydx_perpetual_constants as CONSTANTS
import hummingbot.connector.derivative.dydx_perpetual.dydx_perpetual_web_utils as web_utils
from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.connector.derivative.dydx_perpetual.dydx_perpetual_derivative import (
    DydxPerpetualAuth,
    DydxPerpetualDerivative,
)
from hummingbot.connector.test_support.perpetual_derivative_test import AbstractPerpetualDerivativeTests
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.connector.utils import combine_to_hb_trading_pair
from hummingbot.core.data_type.common import OrderType, PositionAction, PositionMode, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder
from hummingbot.core.data_type.trade_fee import AddedToCostTradeFee, TokenAmount, TradeFeeBase
from hummingbot.core.web_assistant.connections.data_types import RESTRequest


class DydxPerpetualAuthMock(DydxPerpetualAuth):
    def get_order_signature(
        self,
        position_id: str,
        client_id: str,
        market: str,
        side: str,
        size: str,
        price: str,
        limit_fee: str,
        expiration_epoch_seconds: int,
    ) -> str:
        return "0123456789"

    async def rest_authenticate(self, request: RESTRequest) -> RESTRequest:
        headers = {
            "DYDX-SIGNATURE": "0123456789",
            "DYDX-API-KEY": "someKey",
            "DYDX-TIMESTAMP": "1640780000",
            "DYDX-PASSPHRASE": "somePassphrase",
        }

        if request.headers is not None:
            headers.update(request.headers)

        request.headers = headers
        return request

    def get_account_id(self):
        return "someAccountNumber"


class DydxPerpetualDerivativeTests(AbstractPerpetualDerivativeTests.PerpetualDerivativeTests):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.api_key = "someKey"
        cls.api_secret = "someSecret"
        cls.passphrase = "somePassphrase"
        cls.account_number = "someAccountNumber"
        cls.ethereum_address = "someEthAddress"
        cls.stark_private_key = "0123456789"
        cls.base_asset = "HBOT"
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
        url = web_utils.private_rest_url(CONSTANTS.PATH_ACCOUNTS + "/" + str(self.account_number))
        return url

    @property
    def expected_supported_position_modes(self) -> List[PositionMode]:
        return [PositionMode.ONEWAY]

    @property
    def all_symbols_request_mock_response(self):
        mock_response = {
            "markets": {
                self.trading_pair: {
                    "market": self.trading_pair,
                    "status": "ONLINE",
                    "baseAsset": self.base_asset,
                    "quoteAsset": self.quote_asset,
                    "stepSize": "0.1",
                    "tickSize": "0.01",
                    "indexPrice": "12",
                    "oraclePrice": "101",
                    "priceChange24H": "0",
                    "nextFundingRate": "0.0000125000",
                    "nextFundingAt": "2022-07-06T12:20:53.000Z",
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

    @property
    def latest_prices_request_mock_response(self):
        mock_response = {
            "markets": {
                self.trading_pair: {
                    "market": self.trading_pair,
                    "status": "ONLINE",
                    "baseAsset": self.base_asset,
                    "quoteAsset": self.quote_asset,
                    "stepSize": "0.1",
                    "tickSize": "0.01",
                    "indexPrice": "12",
                    "oraclePrice": "101",
                    "priceChange24H": "0",
                    "nextFundingRate": "0.0000125000",
                    "nextFundingAt": "2022-07-06T12:20:53.000Z",
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

    @property
    def all_symbols_including_invalid_pair_mock_response(self) -> Tuple[str, Any]:
        mock_response = {
            "markets": {
                self.trading_pair: {
                    "market": self.trading_pair,
                    "status": "ONLINE",
                    "baseAsset": self.base_asset,
                    "quoteAsset": self.quote_asset,
                    "stepSize": "0.1",
                    "tickSize": "0.01",
                    "indexPrice": "12",
                    "oraclePrice": "101",
                    "priceChange24H": "0",
                    "nextFundingRate": "0.0000125000",
                    "nextFundingAt": "2022-07-06T12:20:53.000Z",
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
                },
                "INVALID-PAIR": {
                    "market": "INVALID-PAIR",
                    "status": "OFFLINE",
                    "baseAsset": "INVALID",
                    "quoteAsset": "PAIR",
                    "stepSize": "0.1",
                    "tickSize": "0.01",
                    "indexPrice": "12",
                    "oraclePrice": "101",
                    "priceChange24H": "0",
                    "nextFundingRate": "0.0000125000",
                    "nextFundingAt": "2022-07-06T12:20:53.000Z",
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
                    "market": self.trading_pair,
                    "status": "ONLINE",
                    "baseAsset": self.base_asset,
                    "quoteAsset": self.quote_asset,
                    "stepSize": "0.1",
                    "tickSize": "0.01",
                    "indexPrice": "12",
                    "oraclePrice": "101",
                    "priceChange24H": "0",
                    "nextFundingRate": "0.0000125000",
                    "nextFundingAt": "2022-07-06T12:20:53.000Z",
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

    @property
    def trading_rules_request_erroneous_mock_response(self):
        mock_response = {
            "markets": {
                self.trading_pair: {
                    "market": self.trading_pair,
                    "status": "ONLINE",
                    "baseAsset": self.base_asset,
                    "quoteAsset": self.quote_asset,
                }
            }
        }
        return mock_response

    @property
    def order_creation_request_successful_mock_response(self):
        mock_response = {
            "order": {
                "id": self.exchange_order_id_prefix + "1",
                "clientId": self.client_order_id_prefix + "1",
                "accountId": "someAccountId",
                "market": self.trading_pair,
                "side": "SELL",
                "price": "18000",
                "triggerPrice": None,
                "trailingPercent": None,
                "size": "100",
                "remainingSize": "100",
                "type": "LIMIT",
                "createdAt": "2021-01-04T23:44:59.690Z",
                "unfillableAt": None,
                "expiresAt": "2022-12-21T21:30:20.200Z",
                "status": "PENDING",
                "timeInForce": "GTT",
                "postOnly": False,
                "reduceOnly": False,
                "cancelReason": None,
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
            "account": {
                "starkKey": "180913017c740260fea4b2c62828a4008ca8b0d6e4",
                "positionId": "1812",
                "equity": "10000",
                "freeCollateral": "10000",
                "quoteBalance": "10000",
                "pendingDeposits": "0",
                "pendingWithdrawals": "0",
                "createdAt": "2021-04-09T21:08:34.984Z",
                "openPositions": {
                    self.trading_pair: {
                        "market": self.trading_pair,
                        "status": "OPEN",
                        "side": "LONG",
                        "size": "1000",
                        "maxSize": "1050",
                        "entryPrice": "100",
                        "exitPrice": None,
                        "unrealizedPnl": "50",
                        "realizedPnl": "100",
                        "createdAt": "2021-01-04T23:44:59.690Z",
                        "closedAt": None,
                        "netFunding": "500",
                        "sumOpen": "1050",
                        "sumClose": "50",
                    }
                },
                "accountNumber": "5",
                "id": "id",
            }
        }
        return mock_response

    @property
    def balance_event_websocket_update(self):
        mock_response = {
            "type": CONSTANTS.WS_TYPE_CHANNEL_DATA,
            "channel": CONSTANTS.WS_CHANNEL_ACCOUNTS,
            "connection_id": "someConnectionId",
            "id": self.account_number,
            "message_id": 2,
            "contents": {
                "accounts": [
                    {
                        "id": self.account_number,
                        "positionId": "somePositionId",
                        "userId": "someUserId",
                        "accountNumber": "0",
                        "starkKey": "0x456...",
                        "quoteBalance": "700",
                        "pendingDeposits": "400",
                        "pendingWithdrawals": "0",
                        "lastTransactionId": "14",
                    }
                ]
            },
        }
        return mock_response

    @property
    def expected_latest_price(self):
        return 12

    @property
    def expected_supported_order_types(self):
        return [OrderType.LIMIT, OrderType.LIMIT_MAKER]

    @property
    def expected_trading_rule(self):
        trading_rules_resp = self.trading_rules_request_mock_response["markets"][self.trading_pair]
        return TradingRule(
            trading_pair=self.trading_pair,
            min_order_size=Decimal(trading_rules_resp["minOrderSize"]),
            min_price_increment=Decimal(trading_rules_resp["tickSize"]),
            min_base_amount_increment=Decimal(trading_rules_resp["stepSize"]),
            min_notional_size=Decimal(trading_rules_resp["minOrderSize"]) * Decimal(trading_rules_resp["tickSize"]),
            supports_limit_orders=True,
            supports_market_orders=True,
            buy_order_collateral_token=trading_rules_resp["quoteAsset"],
            sell_order_collateral_token=trading_rules_resp["quoteAsset"],
        )

    @property
    def expected_logged_error_for_erroneous_trading_rule(self):
        return "Error updating trading rules"

    @property
    def expected_exchange_order_id(self):
        return self.exchange_order_id_prefix + "1"

    @property
    def is_cancel_request_executed_synchronously_by_server(self) -> bool:
        return False

    @property
    def is_order_fill_http_update_included_in_status_update(self) -> bool:
        return True

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

    def create_exchange_instance(self):
        client_config_map = ClientConfigAdapter(ClientConfigMap())
        exchange = DydxPerpetualDerivative(
            client_config_map,
            self.api_key,
            self.api_secret,
            self.passphrase,
            self.ethereum_address,
            self.stark_private_key,
            trading_pairs=[self.trading_pair],
        )
        exchange._position_id = 1234

        authenticator = DydxPerpetualAuthMock(
            self.api_key, self.api_secret, self.passphrase, self.ethereum_address, self.stark_private_key
        )

        exchange._auth = authenticator
        exchange._web_assistants_factory._auth = authenticator

        exchange._rate_limits_config["placeOrderRateLimiting"] = {}
        exchange._rate_limits_config["placeOrderRateLimiting"]["targetNotional"] = 40000
        exchange._rate_limits_config["placeOrderRateLimiting"]["minLimitConsumption"] = 4
        exchange._rate_limits_config["placeOrderRateLimiting"]["minMarketConsumption"] = 20
        exchange._rate_limits_config["placeOrderRateLimiting"]["maxOrderConsumption"] = 100
        exchange._rate_limits_config["placeOrderRateLimiting"]["minTriggerableConsumption"] = 100
        exchange._rate_limits_config["placeOrderRateLimiting"]["maxPoints"] = 1750
        exchange._rate_limits_config["placeOrderRateLimiting"]["windowSec"] = 10

        return exchange

    def place_buy_order(
        self,
        amount: Decimal = Decimal("100"),
        price: Decimal = Decimal("10_000"),
        position_action: PositionAction = PositionAction.OPEN,
    ):
        notional_amount = amount * price
        self.exchange._order_notional_amounts[notional_amount] = len(self.exchange._order_notional_amounts.keys())
        self.exchange._current_place_order_requests = 1
        self.exchange._throttler.set_rate_limits(self.exchange.rate_limits_rules)
        return super().place_buy_order(amount, price, position_action)

    def place_sell_order(
        self,
        amount: Decimal = Decimal("100"),
        price: Decimal = Decimal("10_000"),
        position_action: PositionAction = PositionAction.OPEN,
    ):
        notional_amount = amount * price
        self.exchange._order_notional_amounts[notional_amount] = len(self.exchange._order_notional_amounts.keys())
        self.exchange._current_place_order_requests = 1
        self.exchange._throttler.set_rate_limits(self.exchange.rate_limits_rules)
        return super().place_sell_order(amount, price, position_action)

    def validate_auth_credentials_present(self, request_call: RequestCall):
        request_headers = request_call.kwargs["headers"]
        self.assertIn(request_headers["Content-Type"], ["application/json", "application/x-www-form-urlencoded"])

        self.assertIn("DYDX-SIGNATURE", request_headers)
        self.assertIn("DYDX-API-KEY", request_headers)
        self.assertIn("DYDX-TIMESTAMP", request_headers)
        self.assertIn("DYDX-PASSPHRASE", request_headers)

    def validate_order_creation_request(self, order: InFlightOrder, request_call: RequestCall):
        request_data = json.loads(request_call.kwargs["data"])
        self.assertEqual(self.exchange_trading_pair, request_data["market"])
        self.assertEqual(order.trade_type.name.upper(), request_data["side"])
        self.assertEqual(order.price, Decimal(request_data["price"]))
        self.assertEqual(order.amount, Decimal(request_data["size"]))
        self.assertEqual(order.order_type.name.upper(), request_data["type"])
        self.assertEqual(CONSTANTS.TIF_GOOD_TIL_TIME, request_data["timeInForce"])
        self.assertFalse(request_data["reduceOnly"])

    def validate_order_cancelation_request(self, order: InFlightOrder, request_call: RequestCall):
        request_params = request_call.kwargs["params"]
        self.assertEqual(order.exchange_order_id, request_params["id"])
        self.assertEqual(self.trading_pair, request_params["market"])
        self.assertEqual("BUY" if order.trade_type == TradeType.BUY else "SELL", request_params["side"])

    def validate_order_status_request(self, order: InFlightOrder, request_call: RequestCall):
        request_params = request_call.kwargs["params"]
        if request_params is not None:
            self.assertEqual(order.exchange_order_id, request_params["orderId"])
            self.assertEqual(CONSTANTS.LAST_FILLS_MAX, request_params["limit"])

    def validate_trades_request(self, order: InFlightOrder, request_call: RequestCall):
        request_params = request_call.kwargs["params"]
        if request_params is not None:
            self.assertEqual(order.exchange_order_id, request_params["orderId"])
            self.assertEqual(CONSTANTS.LAST_FILLS_MAX, request_params["limit"])

    def configure_successful_cancelation_response(
        self, order: InFlightOrder, mock_api: aioresponses, callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> str:
        """
        :return: the URL configured for the cancelation
        """
        url = web_utils.private_rest_url(CONSTANTS.PATH_ACTIVE_ORDERS)

        regex_url = re.compile(f"^{url}".replace(".", r"\.") + r"\?.*")
        response = self._order_cancelation_request_successful_mock_response(order=order)
        mock_api.delete(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_erroneous_cancelation_response(
        self, order: InFlightOrder, mock_api: aioresponses, callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> str:
        """
        :return: the URL configured for the cancelation
        """
        url = web_utils.private_rest_url(CONSTANTS.PATH_ACTIVE_ORDERS)

        regex_url = re.compile(f"^{url}".replace(".", r"\.") + r"\?.*")
        response = {}
        mock_api.delete(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_one_successful_one_erroneous_cancel_all_response(
        self, successful_order: InFlightOrder, erroneous_order: InFlightOrder, mock_api: aioresponses
    ) -> List[str]:
        """
        :return: a list of all configured URLs for the cancelations
        """
        all_urls = []
        url = self.configure_successful_cancelation_response(order=successful_order, mock_api=mock_api)
        all_urls.append(url)
        url = self.configure_erroneous_cancelation_response(order=erroneous_order, mock_api=mock_api)
        all_urls.append(url)
        return all_urls

    def configure_completely_filled_order_status_response(
        self, order: InFlightOrder, mock_api: aioresponses, callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> List[str]:
        """
        :return: the URL configured
        """
        url_order_status = web_utils.private_rest_url(CONSTANTS.PATH_ORDERS + "/" + str(order.exchange_order_id))

        response_order_status = self._order_status_request_completely_filled_mock_response(order=order)
        mock_api.get(url_order_status, body=json.dumps(response_order_status), callback=callback)

        return [url_order_status]

    def configure_canceled_order_status_response(
        self, order: InFlightOrder, mock_api: aioresponses, callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> List[str]:
        """
        :return: the URL configured
        """
        url_fills = web_utils.private_rest_url(CONSTANTS.PATH_FILLS)

        response_fills = self._order_fills_request_canceled_mock_response(order=order)
        mock_api.get(url_fills, body=json.dumps(response_fills), callback=callback)

        url_order_status = web_utils.private_rest_url(CONSTANTS.PATH_ORDERS + "/" + str(order.exchange_order_id))

        response_order_status = self._order_status_request_canceled_mock_response(order=order)
        mock_api.get(url_order_status, body=json.dumps(response_order_status), callback=callback)

        return [url_fills, url_order_status]

    def configure_open_order_status_response(
        self, order: InFlightOrder, mock_api: aioresponses, callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> List[str]:
        """
        :return: the URL configured
        """
        url = web_utils.private_rest_url(CONSTANTS.PATH_ORDERS + "/" + str(order.exchange_order_id))

        regex_url = re.compile(url + r"\?.*")
        response = self._order_status_request_open_mock_response(order=order)
        mock_api.get(regex_url, body=json.dumps(response), callback=callback)
        return [url]

    def configure_http_error_order_status_response(
        self, order: InFlightOrder, mock_api: aioresponses, callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> str:
        """
        :return: the URL configured
        """
        url = web_utils.private_rest_url(CONSTANTS.PATH_ORDERS + "/" + str(order.exchange_order_id))

        regex_url = re.compile(url + r"\?.*")
        mock_api.get(regex_url, status=404, callback=callback)
        return url

    def configure_partially_filled_order_status_response(
        self, order: InFlightOrder, mock_api: aioresponses, callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> List[str]:
        # Dydx has no partial fill status
        raise NotImplementedError

    def configure_partial_fill_trade_response(
        self, order: InFlightOrder, mock_api: aioresponses, callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> str:
        # Dydx has no partial fill status
        raise NotImplementedError

    def configure_erroneous_http_fill_trade_response(
        self, order: InFlightOrder, mock_api: aioresponses, callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> str:
        """
        :return: the URL configured
        """
        url = web_utils.private_rest_url(CONSTANTS.PATH_ORDERS + "/" + str(order.exchange_order_id))
        regex_url = re.compile(url + r"\?.*")
        mock_api.get(regex_url, status=400, callback=callback)
        return url

    def configure_full_fill_trade_response(
        self, order: InFlightOrder, mock_api: aioresponses, callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> str:
        """
        :return: the URL configured
        """
        url = web_utils.private_rest_url(CONSTANTS.PATH_FILLS)

        regex_url = re.compile(url + r"\?.*")
        response = self._order_fills_request_full_fill_mock_response(order=order)
        mock_api.get(regex_url, body=json.dumps(response), callback=callback)
        return url

    def _order_cancelation_request_successful_mock_response(self, order: InFlightOrder) -> Any:
        return {
            "cancelOrders": [
                {
                    "id": order.exchange_order_id,
                    "clientId": order.client_order_id,
                    "accountId": "someAccountId",
                    "market": self.trading_pair,
                    "side": order.trade_type.name,
                    "price": str(order.price),
                    "triggerPrice": None,
                    "trailingPercent": None,
                    "size": str(order.amount),
                    "remainingSize": str(order.amount),
                    "type": "LIMIT",
                    "createdAt": "2021-01-04T23:44:59.690Z",
                    "unfillableAt": None,
                    "expiresAt": "2022-12-21T21:30:20.200Z",
                    "status": "PENDING",
                    "timeInForce": "GTT",
                    "postOnly": False,
                    "reduceOnly": False,
                    "cancelReason": None,
                }
            ]
        }

    def _order_fills_request_completely_filled_mock_response(self, order: InFlightOrder) -> Any:
        return {
            "fills": [
                {
                    "id": self.expected_fill_trade_id,
                    "accountId": self.account_number,
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
        mock_response = {
            "order": {
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
        }
        return mock_response

    def _order_status_request_canceled_mock_response(self, order: InFlightOrder) -> Any:
        resp = self._order_status_request_completely_filled_mock_response(order)
        resp["order"]["status"] = "CANCELED"
        resp["order"]["remainingSize"] = resp["order"]["size"]
        return resp

    def _order_status_request_open_mock_response(self, order: InFlightOrder) -> Any:
        resp = self._order_status_request_completely_filled_mock_response(order)
        resp["order"]["status"] = "OPEN"
        resp["order"]["remainingSize"] = resp["order"]["size"]
        return resp

    def _order_fills_request_partial_fill_mock_response(self, order: InFlightOrder):
        return {
            "fills": [
                {
                    "id": self.expected_fill_trade_id,
                    "accountId": self.account_number,
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
                    "accountId": self.account_number,
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

    def order_event_for_new_order_websocket_update(self, order: InFlightOrder):
        return {
            "type": CONSTANTS.WS_TYPE_CHANNEL_DATA,
            "channel": CONSTANTS.WS_CHANNEL_ACCOUNTS,
            "connection_id": "someConnectionId",
            "id": self.account_number,
            "message_id": 2,
            "contents": {
                "orders": [
                    {
                        "id": order.exchange_order_id,
                        "clientId": self.client_order_id_prefix + "1",
                        "market": self.trading_pair,
                        "accountId": self.account_number,
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
            },
        }

    def order_event_for_canceled_order_websocket_update(self, order: InFlightOrder):
        return {
            "type": CONSTANTS.WS_TYPE_CHANNEL_DATA,
            "channel": CONSTANTS.WS_CHANNEL_ACCOUNTS,
            "connection_id": "someConnectionId",
            "id": self.account_number,
            "message_id": 2,
            "contents": {
                "orders": [
                    {
                        "id": order.exchange_order_id,
                        "clientId": order.client_order_id,
                        "market": self.trading_pair,
                        "accountId": self.account_number,
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
                        "createdAt": "2020-09-22T20:22:26.399Z",
                    }
                ]
            },
        }

    def order_event_for_full_fill_websocket_update(self, order: InFlightOrder):
        return {
            "type": CONSTANTS.WS_TYPE_CHANNEL_DATA,
            "channel": CONSTANTS.WS_CHANNEL_ACCOUNTS,
            "connection_id": "someConnectionId",
            "id": self.account_number,
            "message_id": 2,
            "contents": {
                "orders": [
                    {
                        "id": order.exchange_order_id,
                        "clientId": order.client_order_id,
                        "market": self.trading_pair,
                        "accountId": self.account_number,
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
            },
        }

    def trade_event_for_full_fill_websocket_update(self, order: InFlightOrder):
        return {
            "type": CONSTANTS.WS_TYPE_CHANNEL_DATA,
            "channel": CONSTANTS.WS_CHANNEL_ACCOUNTS,
            "connection_id": "someConnectionId",
            "id": self.account_number,
            "message_id": 2,
            "contents": {
                "fills": [
                    {
                        "id": self.expected_fill_trade_id,
                        "accountId": self.account_number,
                        "side": order.trade_type.name,
                        "liquidity": "MAKER"
                        if order.order_type in [OrderType.LIMIT, OrderType.LIMIT_MAKER]
                        else "TAKER",
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
            },
        }

    @property
    def funding_info_url(self):
        url = web_utils.public_rest_url(CONSTANTS.PATH_MARKETS)
        url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        return url

    @property
    def funding_payment_url(self):
        url = web_utils.private_rest_url(CONSTANTS.PATH_FUNDING)
        url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        return url

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
                    "indexPrice": "1",
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

    @property
    def empty_funding_payment_mock_response(self):
        mock_response = {
            "fundingPayments": [
                {
                    "market": self.trading_pair,
                    "payment": "200",
                    "rate": "100",
                    "positionSize": "500",
                    "price": "90",
                    "effectiveAt": "2022-07-05T12:20:53.000Z",
                }
            ]
        }
        return mock_response

    @property
    def funding_payment_mock_response(self):
        mock_response = {
            "fundingPayments": [
                {
                    "market": self.trading_pair,
                    "payment": "200",
                    "rate": "100",
                    "positionSize": "500",
                    "price": "90",
                    "effectiveAt": "2022-07-06T12:20:53.000Z",
                }
            ]
        }
        return mock_response

    def position_event_for_full_fill_websocket_update(self, order: InFlightOrder, unrealized_pnl: float):
        return {
            "type": CONSTANTS.WS_TYPE_CHANNEL_DATA,
            "channel": CONSTANTS.WS_CHANNEL_ACCOUNTS,
            "connection_id": "someConnectionId",
            "id": self.account_number,
            "message_id": 2,
            "contents": {
                "positions": [
                    {
                        "id": self.expected_fill_trade_id,
                        "accountId": self.account_number,
                        "market": self.trading_pair,
                        "side": "LONG" if order.trade_type == TradeType.BUY else "SHORT",
                        "status": "CLOSED",
                        "size": str(order.amount) if order.order_type == TradeType.BUY else str(-order.amount),
                        "maxSize": "300",
                        "entryPrice": "10000",
                        "exitPrice": "38",
                        "realizedPnl": "50",
                        "unrealizedPnl": str(unrealized_pnl),
                        "createdAt": "2020-09-22T20:25:26.399Z",
                        "openTransactionId": "2",
                        "closeTransactionId": "23",
                        "lastTransactionId": "23",
                        "closedAt": "2020-14-22T20:25:26.399Z",
                        "sumOpen": "300",
                        "sumClose": "100",
                    }
                ]
            },
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
                self.trading_pair: {
                    "indexPrice": "100.23",
                    "oraclePrice": "100.23",
                    "priceChange24H": "0.12",
                    "initialMarginFraction": "1.23",
                }
            },
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
