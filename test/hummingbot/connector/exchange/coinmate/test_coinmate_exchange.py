from decimal import Decimal
from typing import Any, Tuple

from hummingbot.connector.exchange.coinmate import (
    coinmate_constants as CONSTANTS,
    coinmate_web_utils as web_utils
)
from hummingbot.connector.exchange.coinmate.coinmate_exchange import CoinmateExchange
from hummingbot.connector.test_support.exchange_connector_test import (
    AbstractExchangeConnectorTests
)
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.core.data_type.common import OrderType
from hummingbot.core.data_type.trade_fee import (
    AddedToCostTradeFee,
    TokenAmount,
    TradeFeeBase,
)


class CoinmateExchangeTests(
    AbstractExchangeConnectorTests.ExchangeConnectorTests
):

    @property
    def all_symbols_url(self):
        return web_utils.public_rest_url(
            path_url=CONSTANTS.TRADING_PAIRS_PATH_URL, domain=self.exchange._domain
        )

    @property
    def latest_prices_url(self):
        return web_utils.public_rest_url(
            path_url=CONSTANTS.TICKER_PATH_URL, domain=self.exchange._domain
        )

    @property
    def network_status_url(self):
        return web_utils.public_rest_url(
            CONSTANTS.SERVER_TIME_PATH_URL, domain=self.exchange._domain
        )

    @property
    def trading_rules_url(self):
        return web_utils.public_rest_url(
            CONSTANTS.TRADING_PAIRS_PATH_URL, domain=self.exchange._domain
        )

    @property
    def order_creation_url(self):
        return web_utils.private_rest_url(
            CONSTANTS.BUY_LIMIT_PATH_URL, domain=self.exchange._domain
        )

    @property
    def balance_url(self):
        return web_utils.private_rest_url(
            CONSTANTS.ACCOUNTS_PATH_URL, domain=self.exchange._domain
        )

    @property
    def all_symbols_request_mock_response(self):
        return {
            "error": False,
            "errorMessage": None,
            "data": [
                {
                    "name": f"{self.base_asset}_{self.quote_asset}",
                    "firstCurrency": self.base_asset,
                    "secondCurrency": self.quote_asset,
                    "priceDecimals": 2,
                    "lotDecimals": 8,
                    "minAmount": 0.001
                }
            ]
        }

    @property
    def latest_prices_request_mock_response(self):
        return {
            "error": False,
            "errorMessage": None,
            "data": {
                "last": str(self.expected_latest_price),
                "high": "55000.00",
                "low": "49000.00",
                "amount": "123.45",
                "bid": "49900.00",
                "ask": "50100.00",
                "change": "2.5",
                "open": "49000.00",
                "timestamp": 1234567890123
            }
        }

    @property
    def all_symbols_including_invalid_pair_mock_response(self) -> Tuple[str, Any]:
        response = {
            "error": False,
            "errorMessage": None,
            "data": [
                {
                    "name": f"{self.base_asset}_{self.quote_asset}",
                    "firstCurrency": self.base_asset,
                    "secondCurrency": self.quote_asset,
                    "priceDecimals": 2,
                    "lotDecimals": 8,
                    "minAmount": 0.001
                },
                {
                    "name": "INVALID_PAIR",
                    "firstCurrency": "INVALID",
                    "secondCurrency": "PAIR",
                    "priceDecimals": 2,
                    "lotDecimals": 8,
                    "minAmount": 0.001
                }
            ]
        }
        return "INVALID-PAIR", response

    @property
    def network_status_request_successful_mock_response(self):
        return {"serverTime": 1234567890123}

    @property
    def trading_rules_request_mock_response(self):
        return self.all_symbols_request_mock_response

    @property
    def trading_rules_request_erroneous_mock_response(self):
        return {
            "error": True,
            "errorMessage": "Server error",
            "data": None
        }

    @property
    def order_creation_request_successful_mock_response(self):
        return {
            "error": False,
            "errorMessage": None,
            "data": int(self.expected_exchange_order_id)
        }

    @property
    def balance_request_mock_response_for_base_and_quote(self):
        return {
            "error": False,
            "errorMessage": None,
            "data": {
                self.base_asset: {
                    "currency": self.base_asset,
                    "balance": "10.0",
                    "reserved": "1.0",
                    "available": "9.0"
                },
                self.quote_asset: {
                    "currency": self.quote_asset,
                    "balance": "2000.0",
                    "reserved": "100.0",
                    "available": "1900.0"
                }
            }
        }

    @property
    def balance_request_mock_response_only_base(self):
        return {
            "error": False,
            "errorMessage": None,
            "data": {
                self.base_asset: {
                    "currency": self.base_asset,
                    "balance": "10.0",
                    "reserved": "1.0",
                    "available": "9.0"
                }
            }
        }

    @property
    def expected_latest_price(self):
        return 50000.0

    @property
    def expected_supported_order_types(self):
        return [OrderType.LIMIT, OrderType.MARKET]

    @property
    def expected_trading_rule(self):
        return TradingRule(
            trading_pair=self.trading_pair,
            min_order_size=Decimal("0.001"),
            min_price_increment=Decimal("0.01"),
            min_base_amount_increment=Decimal("1e-8"),
        )

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
    def expected_fill_fee(self) -> TradeFeeBase:
        return AddedToCostTradeFee(
            percent=Decimal("0.003"),
            percent_token=self.quote_asset,
            flat_fees=[TokenAmount(token=self.quote_asset, amount=Decimal("75"))]
        )

    @property
    def expected_fill_trade_id(self) -> str:
        return "67890"

    def exchange_symbol_for_tokens(self, base_token: str, quote_token: str) -> str:
        return f"{base_token}_{quote_token}"

    def create_exchange_instance(self):
        client_config_map = self.get_default_client_config_map()
        return CoinmateExchange(
            coinmate_api_key="test_api_key",
            coinmate_secret_key="test_secret_key",
            coinmate_client_id="test_client_id",
            trading_pairs=[self.trading_pair],
            client_config_map=client_config_map
        )
