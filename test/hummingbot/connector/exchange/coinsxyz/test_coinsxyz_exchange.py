#!/usr/bin/env python3

import unittest
from decimal import Decimal

from hummingbot.connector.test_support.exchange_connector_test import AbstractExchangeConnectorTest
from hummingbot.core.data_type.common import OrderType
from hummingbot.core.data_type.trade_fee import TokenAmount


class CoinsxyzExchangeTest(AbstractExchangeConnectorTest.ExchangeConnectorTest):
    """Integration tests for CoinsxyzExchange using the standard test framework."""

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.api_key = "test_api_key"
        cls.secret_key = "test_secret_key"
        cls.base_asset = "BTC"
        cls.quote_asset = "USDT"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"

    def setUp(self) -> None:
        super().setUp()
        self.exchange._trading_pairs = [self.trading_pair]

    @property
    def all_symbols_url(self):
        return "https://api.coins.xyz/v1/exchangeInfo"

    @property
    def latest_prices_url(self):
        return "https://api.coins.xyz/v1/ticker/24hr"

    @property
    def network_status_url(self):
        return "https://api.coins.xyz/v1/ping"

    @property
    def trading_rules_url(self):
        return "https://api.coins.xyz/v1/exchangeInfo"

    @property
    def order_creation_url(self):
        return "https://api.coins.xyz/v1/order"

    @property
    def balance_url(self):
        return "https://api.coins.xyz/v1/account"

    @property
    def all_symbols_request_mock_response(self):
        return {
            "symbols": [
                {
                    "symbol": "BTCUSDT",
                    "status": "TRADING",
                    "baseAsset": "BTC",
                    "quoteAsset": "USDT",
                    "filters": [
                        {
                            "filterType": "PRICE_FILTER",
                            "minPrice": "0.01",
                            "maxPrice": "1000000.00",
                            "tickSize": "0.01"
                        },
                        {
                            "filterType": "LOT_SIZE",
                            "minQty": "0.001",
                            "maxQty": "9000.00",
                            "stepSize": "0.001"
                        }
                    ]
                }
            ]
        }

    @property
    def latest_prices_request_mock_response(self):
        return [
            {
                "symbol": "BTCUSDT",
                "price": "50000.00"
            }
        ]

    @property
    def all_symbols_including_invalid_pair_mock_response(self):
        return {
            "symbols": [
                {
                    "symbol": "BTCUSDT",
                    "status": "TRADING",
                    "baseAsset": "BTC",
                    "quoteAsset": "USDT"
                },
                {
                    "symbol": "INVALIDPAIR",
                    "status": "BREAK",
                    "baseAsset": "INVALID",
                    "quoteAsset": "PAIR"
                }
            ]
        }

    @property
    def network_status_request_successful_mock_response(self):
        return {}

    @property
    def trading_rules_request_mock_response(self):
        return self.all_symbols_request_mock_response

    @property
    def trading_rules_request_erroneous_mock_response(self):
        return {"error": "Invalid request"}

    @property
    def order_creation_request_successful_mock_response(self):
        return {
            "orderId": "12345",
            "transactTime": 1234567890000,
            "status": "NEW"
        }

    @property
    def balance_request_mock_response_for_base_and_quote(self):
        return {
            "balances": [
                {
                    "asset": "BTC",
                    "free": "1.0",
                    "locked": "0.0"
                },
                {
                    "asset": "USDT",
                    "free": "10000.0",
                    "locked": "0.0"
                }
            ]
        }

    @property
    def balance_request_mock_response_only_base(self):
        return {
            "balances": [
                {
                    "asset": "BTC",
                    "free": "1.0",
                    "locked": "0.0"
                }
            ]
        }

    @property
    def balance_event_websocket_update(self):
        return {
            "e": "outboundAccountPosition",
            "E": 1234567890000,
            "B": [
                {
                    "a": "BTC",
                    "f": "1.0",
                    "l": "0.0"
                }
            ]
        }

    @property
    def expected_latest_price(self):
        return 50000.0

    @property
    def expected_supported_order_types(self):
        return [OrderType.LIMIT, OrderType.MARKET]

    @property
    def expected_trading_rule(self):
        return {
            "trading_pair": self.trading_pair,
            "min_order_size": Decimal("0.001"),
            "min_price_increment": Decimal("0.01"),
            "min_base_amount_increment": Decimal("0.001"),
        }

    @property
    def expected_logged_error_for_erroneous_trading_rule(self):
        return "ERROR - Could not fetch trading rules from coinsxyz"

    @property
    def expected_exchange_order_id(self):
        return "12345"

    @property
    def is_order_fill_http_update_included_in_status_update(self) -> bool:
        return True

    @property
    def is_order_fill_http_update_executed_during_websocket_order_event_processing(self) -> bool:
        return False

    @property
    def expected_partial_fill_price(self) -> Decimal:
        return Decimal("50000")

    @property
    def expected_partial_fill_amount(self) -> Decimal:
        return Decimal("0.5")

    @property
    def expected_fill_fee(self) -> TokenAmount:
        return TokenAmount("USDT", Decimal("25"))

    @property
    def expected_fill_trade_id(self) -> str:
        return "67890"

    def exchange_symbol_for_tokens(self, base_token: str, quote_token: str) -> str:
        return f"{base_token}{quote_token}"

    def create_exchange_instance(self):
        from hummingbot.connector.exchange.coinsxyz.coinsxyz_exchange import CoinsxyzExchange
        return CoinsxyzExchange(
            coinsxyz_api_key=self.api_key,
            coinsxyz_secret_key=self.secret_key,
            trading_pairs=[self.trading_pair],
            trading_required=True
        )

    def validate_auth_credentials_present(self, request_call_tuple: tuple):
        """Validate that authentication credentials are present in the request."""
        request_call = request_call_tuple[0]
        headers = request_call[1].get("headers", {})
        params = request_call[1].get("params", {})

        self.assertIn("X-COINS-APIKEY", headers)
        self.assertIn("timestamp", params)
        self.assertIn("signature", params)

    def validate_order_creation_request(self, order, request_call_tuple: tuple):
        """Validate order creation request parameters."""
        request_call = request_call_tuple[0]
        request_data = request_call[1].get("data", {})

        self.assertEqual(request_data["symbol"], self.exchange_symbol_for_tokens(order.base_asset, order.quote_asset))
        self.assertEqual(request_data["side"], order.trade_type.name)
        self.assertEqual(request_data["type"], order.order_type.name)
        self.assertEqual(Decimal(request_data["quantity"]), order.amount)

    def validate_order_cancelation_request(self, order, request_call_tuple: tuple):
        """Validate order cancellation request parameters."""
        request_call = request_call_tuple[0]
        params = request_call[1].get("params", {})

        self.assertEqual(params["symbol"], self.exchange_symbol_for_tokens(order.base_asset, order.quote_asset))
        self.assertEqual(params["orderId"], order.exchange_order_id)

    def validate_order_status_request(self, order, request_call_tuple: tuple):
        """Validate order status request parameters."""
        request_call = request_call_tuple[0]
        params = request_call[1].get("params", {})

        self.assertEqual(params["symbol"], self.exchange_symbol_for_tokens(order.base_asset, order.quote_asset))
        self.assertEqual(params["orderId"], order.exchange_order_id)

    def validate_trades_request(self, order, request_call_tuple: tuple):
        """Validate trades request parameters."""
        request_call = request_call_tuple[0]
        params = request_call[1].get("params", {})

        self.assertEqual(params["symbol"], self.exchange_symbol_for_tokens(order.base_asset, order.quote_asset))

    def configure_successful_cancelation_response(
        self,
        order,
        mock_api,
        **kwargs
    ) -> str:
        """Configure mock response for successful order cancellation."""
        mock_response = {
            "orderId": order.exchange_order_id,
            "status": "CANCELED"
        }
        mock_api.return_value = mock_response
        return order.exchange_order_id

    def configure_erroneous_cancelation_response(
        self,
        order,
        mock_api,
        **kwargs
    ) -> str:
        """Configure mock response for erroneous order cancellation."""
        mock_api.side_effect = Exception("Order not found")
        return "Order not found"

    def configure_order_not_found_error_cancelation_response(
        self,
        order,
        mock_api,
        **kwargs
    ) -> str:
        """Configure mock response for order not found during cancellation."""
        mock_api.side_effect = Exception("Order not found")
        return "Order not found"

    def configure_order_not_found_error_order_status_response(
        self,
        order,
        mock_api,
        **kwargs
    ) -> list:
        """Configure mock response for order not found during status check."""
        mock_api.side_effect = Exception("Order not found")
        return ["Order not found"]

    def configure_completely_filled_order_status_response(
        self,
        order,
        mock_api,
        **kwargs
    ) -> str:
        """Configure mock response for completely filled order status."""
        mock_response = {
            "orderId": order.exchange_order_id,
            "status": "FILLED",
            "executedQty": str(order.amount),
            "cummulativeQuoteQty": str(order.amount * order.price)
        }
        mock_api.return_value = mock_response
        return order.exchange_order_id

    def configure_canceled_order_status_response(
        self,
        order,
        mock_api,
        **kwargs
    ) -> str:
        """Configure mock response for canceled order status."""
        mock_response = {
            "orderId": order.exchange_order_id,
            "status": "CANCELED"
        }
        mock_api.return_value = mock_response
        return order.exchange_order_id

    def configure_open_order_status_response(
        self,
        order,
        mock_api,
        **kwargs
    ) -> str:
        """Configure mock response for open order status."""
        mock_response = {
            "orderId": order.exchange_order_id,
            "status": "NEW",
            "executedQty": "0",
            "cummulativeQuoteQty": "0"
        }
        mock_api.return_value = mock_response
        return order.exchange_order_id

    def configure_http_error_order_status_response(
        self,
        order,
        mock_api,
        **kwargs
    ) -> str:
        """Configure mock response for HTTP error during order status check."""
        mock_api.side_effect = Exception("HTTP Error")
        return "HTTP Error"

    def configure_partially_filled_order_status_response(
        self,
        order,
        mock_api,
        **kwargs
    ) -> str:
        """Configure mock response for partially filled order status."""
        mock_response = {
            "orderId": order.exchange_order_id,
            "status": "PARTIALLY_FILLED",
            "executedQty": str(self.expected_partial_fill_amount),
            "cummulativeQuoteQty": str(self.expected_partial_fill_amount * self.expected_partial_fill_price)
        }
        mock_api.return_value = mock_response
        return order.exchange_order_id

    def configure_partial_fill_trade_response(
        self,
        order,
        mock_api,
        **kwargs
    ) -> str:
        """Configure mock response for partial fill trade."""
        mock_response = [
            {
                "id": self.expected_fill_trade_id,
                "orderId": order.exchange_order_id,
                "price": str(self.expected_partial_fill_price),
                "qty": str(self.expected_partial_fill_amount),
                "commission": str(self.expected_fill_fee.amount),
                "commissionAsset": self.expected_fill_fee.token,
                "time": 1234567890000
            }
        ]
        mock_api.return_value = mock_response
        return self.expected_fill_trade_id

    def order_event_for_new_order_websocket_update(self, order):
        """Generate websocket update for new order."""
        return {
            "e": "executionReport",
            "E": 1234567890000,
            "s": self.exchange_symbol_for_tokens(order.base_asset, order.quote_asset),
            "c": order.client_order_id,
            "i": order.exchange_order_id,
            "S": order.trade_type.name,
            "o": order.order_type.name,
            "q": str(order.amount),
            "p": str(order.price),
            "X": "NEW",
            "z": "0",
            "Z": "0"
        }

    def order_event_for_canceled_order_websocket_update(self, order):
        """Generate websocket update for canceled order."""
        return {
            "e": "executionReport",
            "E": 1234567890000,
            "s": self.exchange_symbol_for_tokens(order.base_asset, order.quote_asset),
            "c": order.client_order_id,
            "i": order.exchange_order_id,
            "X": "CANCELED"
        }

    def order_event_for_full_fill_websocket_update(self, order):
        """Generate websocket update for fully filled order."""
        return {
            "e": "executionReport",
            "E": 1234567890000,
            "s": self.exchange_symbol_for_tokens(order.base_asset, order.quote_asset),
            "c": order.client_order_id,
            "i": order.exchange_order_id,
            "X": "FILLED",
            "z": str(order.amount),
            "Z": str(order.amount * order.price)
        }

    def trade_event_for_full_fill_websocket_update(self, order):
        """Generate websocket update for trade fill."""
        return {
            "e": "trade",
            "E": 1234567890000,
            "s": self.exchange_symbol_for_tokens(order.base_asset, order.quote_asset),
            "t": self.expected_fill_trade_id,
            "i": order.exchange_order_id,
            "p": str(order.price),
            "q": str(order.amount),
            "n": str(self.expected_fill_fee.amount),
            "N": self.expected_fill_fee.token
        }


if __name__ == "__main__":
    unittest.main()
