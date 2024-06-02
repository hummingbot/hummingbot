import asyncio
import json
import re
from decimal import Decimal
from typing import Any, Awaitable, Callable, Dict, List, Optional, Tuple
from unittest.mock import AsyncMock, patch

from aioresponses import aioresponses
from aioresponses.core import RequestCall

from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.connector.exchange.cube import cube_constants as CONSTANTS, cube_web_utils as web_utils
from hummingbot.connector.exchange.cube.cube_exchange import CubeExchange
from hummingbot.connector.exchange.cube.cube_ws_protobufs import trade_pb2
from hummingbot.connector.test_support.exchange_connector_test import AbstractExchangeConnectorTests
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.connector.utils import get_new_numeric_client_order_id
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState
from hummingbot.core.data_type.trade_fee import DeductedFromReturnsTradeFee, TokenAmount, TradeFeeBase
from hummingbot.core.event.events import (
    BuyOrderCompletedEvent,
    BuyOrderCreatedEvent,
    MarketOrderFailureEvent,
    OrderCancelledEvent,
    OrderFilledEvent,
)


class CubeExchangeTests(AbstractExchangeConnectorTests.ExchangeConnectorTests):

    @classmethod
    def setUpClass(self) -> None:
        super().setUpClass()
        self.base_asset = "SOL"
        self.quote_asset = "USDC"
        self.trading_pair = f"{self.base_asset}-{self.quote_asset}"

    def setUp(self) -> None:
        super().setUp()

        self.log_records = []
        self.async_tasks: List[asyncio.Task] = []

        self.exchange = self.create_exchange_instance()

        self.exchange.logger().setLevel(1)
        self.exchange.logger().addHandler(self)
        self.exchange._order_tracker.logger().setLevel(1)
        self.exchange._order_tracker.logger().addHandler(self)

        self._initialize_event_loggers()

        exchange_market_info = {"result": {
            "assets": [{
                "assetId": 5,
                "symbol": "SOL",
                "decimals": 9,
                "displayDecimals": 2,
                "settles": "true",
                "assetType": "Crypto",
                "sourceId": 3,
                "metadata": {},
                "status": 1
            }, {
                "assetId": 7,
                "symbol": "USDC",
                "decimals": 6,
                "displayDecimals": 2,
                "settles": "true",
                "assetType": "Crypto",
                "sourceId": 3,
                "metadata": {
                    "mint": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
                },
                "status": 1
            }],
            "markets": [
                {
                    "marketId": 100006,
                    "symbol": "SOLUSDC",
                    "baseAssetId": 5,
                    "baseLotSize": "10000000",
                    "quoteAssetId": 7,
                    "quoteLotSize": "100",
                    "priceDisplayDecimals": 2,
                    "protectionPriceLevels": 1000,
                    "priceBandBidPct": 25,
                    "priceBandAskPct": 400,
                    "priceTickSize": "0.01",
                    "quantityTickSize": "0.01",
                    "status": 1,
                    "feeTableId": 2
                }
            ]
        }}

        self.exchange._initialize_trading_pair_symbols_from_exchange_info(exchange_market_info)

        trading_rule = TradingRule(
            self.trading_pair,
            min_order_size=Decimal("0.001"),
            min_price_increment=Decimal("0.01"),
            min_base_amount_increment=Decimal("10000000") / (10 ** 9),
            min_notional_size=Decimal("100") / (10 ** 6),
        )

        self.exchange._trading_rules[self.trading_pair] = trading_rule

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: int = 2):
        ret = asyncio.get_event_loop().run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    @property
    def all_symbols_url(self):
        return web_utils.public_rest_url(path_url=CONSTANTS.EXCHANGE_INFO_PATH_URL, domain=self.exchange._domain)

    @property
    def latest_prices_url(self):
        url = web_utils.public_rest_url(path_url=CONSTANTS.TICKER_BOOK_PATH_URL, domain=self.exchange._domain)
        # url = f"{url}?symbol={self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset)}"
        return url

    @property
    def network_status_url(self):
        url = web_utils.private_rest_url(CONSTANTS.PING_PATH_URL, domain=self.exchange._domain)
        return url

    @property
    def trading_rules_url(self):
        url = web_utils.private_rest_url(CONSTANTS.EXCHANGE_INFO_PATH_URL, domain=self.exchange._domain)
        return url

    @property
    def order_creation_url(self):
        url = web_utils.private_rest_url(CONSTANTS.POST_ORDER_PATH_URL, domain=self.exchange._domain)
        return url

    @property
    def balance_url(self):
        url = web_utils.private_rest_url(CONSTANTS.ACCOUNTS_PATH_URL.format(self.exchange.cube_subaccount_id), domain=self.exchange._domain)
        return url

    @property
    def all_symbols_request_mock_response(self):
        return {
            "result": {
                "assets": [
                    {
                        "assetId": 5,
                        "symbol": self.base_asset,
                        "decimals": 9,
                        "displayDecimals": 2,
                        "settles": True,
                        "assetType": "Crypto",
                        "sourceId": 3,
                        "metadata": {},
                        "status": 1
                    },
                    {
                        "assetId": 7,
                        "symbol": self.quote_asset,
                        "decimals": 6,
                        "displayDecimals": 2,
                        "settles": True,
                        "assetType": "Crypto",
                        "sourceId": 3,
                        "metadata": {
                            "mint": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
                        },
                        "status": 1
                    }
                ],
                "markets": [
                    {
                        "marketId": 100006,
                        "symbol": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
                        "baseAssetId": 5,
                        "baseLotSize": "10000000",
                        "quoteAssetId": 7,
                        "quoteLotSize": "100",
                        "priceDisplayDecimals": 2,
                        "protectionPriceLevels": 1000,
                        "priceBandBidPct": 25,
                        "priceBandAskPct": 400,
                        "priceTickSize": "0.01",
                        "quantityTickSize": "0.01",
                        "status": 1,
                        "feeTableId": 2
                    }
                ],
                "feeTables": [
                    {
                        "feeTableId": 1,
                        "feeTiers": [
                            {
                                "priority": 0,
                                "makerFeeRatio": 0.0,
                                "takerFeeRatio": 0.0
                            }
                        ]
                    },
                    {
                        "feeTableId": 2,
                        "feeTiers": [
                            {
                                "priority": 0,
                                "makerFeeRatio": 0.0004,
                                "takerFeeRatio": 0.0008
                            }
                        ]
                    }
                ]
            }
        }

    @property
    def latest_prices_request_mock_response(self):
        return {
            "result": [
                {
                    "ticker_id": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
                    "base_currency": self.base_asset,
                    "quote_currency": self.quote_asset,
                    "last_price": self.expected_latest_price,
                    "base_volume": 8234.44,
                    "quote_volume": 1509640.3168,
                    "bid": 184.94,
                    "ask": 185.1,
                    "high": 195.32,
                    "low": 170.97,
                    "open": 172.98
                }
            ]
        }

    @property
    def all_symbols_including_invalid_pair_mock_response(self) -> Tuple[str, Any]:
        response = {
            "result": {
                "assets": [
                    {
                        "assetId": 5,
                        "symbol": self.base_asset,
                        "decimals": 9,
                        "displayDecimals": 2,
                        "settles": True,
                        "assetType": "Crypto",
                        "sourceId": 3,
                        "metadata": {},
                        "status": 1
                    },
                    {
                        "assetId": 7,
                        "symbol": self.quote_asset,
                        "decimals": 6,
                        "displayDecimals": 2,
                        "settles": True,
                        "assetType": "Crypto",
                        "sourceId": 3,
                        "metadata": {
                            "mint": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
                        },
                        "status": 1
                    }
                ],
                "markets": [
                    {
                        "marketId": 100006,
                        "symbol": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
                        "baseAssetId": 5,
                        "baseLotSize": "10000000",
                        "quoteAssetId": 7,
                        "quoteLotSize": "100",
                        "priceDisplayDecimals": 2,
                        "protectionPriceLevels": 1000,
                        "priceBandBidPct": 25,
                        "priceBandAskPct": 400,
                        "priceTickSize": "0.01",
                        "quantityTickSize": "0.01",
                        "status": 1,
                        "feeTableId": 2
                    },
                    {
                        "marketId": 100006,
                        "symbol": self.exchange_symbol_for_tokens("INVALID", "PAIR"),
                        "baseAssetId": 5,
                        "baseLotSize": "10000000",
                        "quoteAssetId": 7,
                        "quoteLotSize": "100",
                        "priceDisplayDecimals": 2,
                        "protectionPriceLevels": 1000,
                        "priceBandBidPct": 25,
                        "priceBandAskPct": 400,
                        "priceTickSize": "0.01",
                        "quantityTickSize": "0.01",
                        "status": 1,
                        "feeTableId": 2
                    }
                ],
                "feeTables": [
                    {
                        "feeTableId": 1,
                        "feeTiers": [
                            {
                                "priority": 0,
                                "makerFeeRatio": 0.0,
                                "takerFeeRatio": 0.0
                            }
                        ]
                    },
                    {
                        "feeTableId": 2,
                        "feeTiers": [
                            {
                                "priority": 0,
                                "makerFeeRatio": 0.0004,
                                "takerFeeRatio": 0.0008
                            }
                        ]
                    }
                ]
            }
        }

        return "INVALID-PAIR", response

    @property
    def network_status_request_successful_mock_response(self):
        return {}

    @property
    def trading_rules_request_mock_response(self):
        return {
            "result": {
                "assets": [
                    {
                        "assetId": 5,
                        "symbol": self.base_asset,
                        "decimals": 9,
                        "displayDecimals": 2,
                        "settles": True,
                        "assetType": "Crypto",
                        "sourceId": 3,
                        "metadata": {},
                        "status": 1
                    },
                    {
                        "assetId": 7,
                        "symbol": self.quote_asset,
                        "decimals": 6,
                        "displayDecimals": 2,
                        "settles": True,
                        "assetType": "Crypto",
                        "sourceId": 3,
                        "metadata": {
                            "mint": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
                        },
                        "status": 1
                    }
                ],
                "markets": [
                    {
                        "marketId": 100006,
                        "symbol": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
                        "baseAssetId": 5,
                        "baseLotSize": "10000000",
                        "quoteAssetId": 7,
                        "quoteLotSize": "100",
                        "priceDisplayDecimals": 2,
                        "protectionPriceLevels": 1000,
                        "priceBandBidPct": 25,
                        "priceBandAskPct": 400,
                        "priceTickSize": "0.01",
                        "quantityTickSize": "0.01",
                        "status": 1,
                        "feeTableId": 2
                    }
                ],
                "feeTables": [
                    {
                        "feeTableId": 1,
                        "feeTiers": [
                            {
                                "priority": 0,
                                "makerFeeRatio": 0.0,
                                "takerFeeRatio": 0.0
                            }
                        ]
                    },
                    {
                        "feeTableId": 2,
                        "feeTiers": [
                            {
                                "priority": 0,
                                "makerFeeRatio": 0.0004,
                                "takerFeeRatio": 0.0008
                            }
                        ]
                    }
                ]
            }
        }

    @property
    def trading_rules_request_erroneous_mock_response(self):
        return {
            "result": {
                "assets": [
                    {
                        "assetId": 5,
                        "symbol": self.base_asset,
                        "decimals": 9,
                        "displayDecimals": 2,
                        "settles": True,
                        "assetType": "Crypto",
                        "sourceId": 3,
                        "metadata": {},
                        "status": 1
                    },
                    {
                        "assetId": 7,
                        "symbol": self.quote_asset,
                        "decimals": 6,
                        "displayDecimals": 2,
                        "settles": True,
                        "assetType": "Crypto",
                        "sourceId": 3,
                        "metadata": {
                            "mint": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
                        },
                        "status": 1
                    }
                ],
                "markets": [
                    {
                        "marketId": 100006,
                        "symbol": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
                        "baseAssetId": 5,
                        "quoteAssetId": 7,
                        "quoteLotSize": "100",
                        "priceDisplayDecimals": 2,
                        "protectionPriceLevels": 1000,
                        "priceBandBidPct": 25,
                        "priceBandAskPct": 400,
                        "status": 1,
                        "feeTableId": 2
                    }
                ],
                "feeTables": [
                    {
                        "feeTableId": 1,
                        "feeTiers": [
                            {
                                "priority": 0,
                                "makerFeeRatio": 0.0,
                                "takerFeeRatio": 0.0
                            }
                        ]
                    },
                    {
                        "feeTableId": 2,
                        "feeTiers": [
                            {
                                "priority": 0,
                                "makerFeeRatio": 0.0004,
                                "takerFeeRatio": 0.0008
                            }
                        ]
                    }
                ]
            }
        }

    @property
    def order_creation_request_successful_mock_response(self):
        return {'result': {'Ack': {'msgSeqNum': 24112895, 'clientOrderId': 11111647030279, 'requestId': 11111647030279,
                                   'exchangeOrderId': self.expected_exchange_order_id, 'marketId': 100006,
                                   'price': 18256, 'quantity': 1,
                                   'side': 1, 'timeInForce': 1, 'orderType': 0, 'transactTime': 1711042496071379572,
                                   'subaccountId': 38393, 'cancelOnDisconnect': False}}}

    @property
    def balance_request_mock_response_for_base_and_quote(self):
        return {
            "result": {
                "1": {
                    "name": "primary",
                    "inner": [
                        {
                            "amount": "10000000000",
                            "receivedAmount": "10000000000",
                            "pendingDeposits": "0",
                            "assetId": 5,
                            "accountingType": "asset"
                        },
                        {
                            "amount": "2000000000",
                            "receivedAmount": "2000000000",
                            "pendingDeposits": "0",
                            "assetId": 7,
                            "accountingType": "asset"
                        }
                    ]
                }
            }
        }

    @property
    def balance_request_mock_response_only_base(self):
        return {
            "result": {
                "1": {
                    "name": "primary",
                    "inner": [
                        {
                            "amount": "15000000000",
                            "receivedAmount": "15000000000",
                            "pendingDeposits": "0",
                            "assetId": 5,
                            "accountingType": "asset"
                        }
                    ]
                }
            }
        }

    @property
    def balance_event_websocket_update(self):
        position = trade_pb2.AssetPosition(
            subaccount_id=1,
            asset_id=5,
            total=trade_pb2.RawUnits(
                word0=15000000000,
            ),
            available=trade_pb2.RawUnits(
                word0=10000000000,
            )
        )

        positions = trade_pb2.AssetPositions(
            positions=[position]
        )

        boostrap = trade_pb2.Bootstrap(
            position=positions
        )

        return boostrap.SerializeToString()

    @property
    def expected_latest_price(self):
        return 9999.9

    @property
    def expected_supported_order_types(self):
        return [OrderType.LIMIT, OrderType.LIMIT_MAKER, OrderType.MARKET]

    @property
    def expected_trading_rule(self):
        return TradingRule(
            trading_pair=self.trading_pair,
            min_order_size=Decimal("0.01"),
            min_price_increment=Decimal("0.01"),
            min_base_amount_increment=Decimal("0.01"),
            min_notional_size=Decimal("0.0001"))

    @property
    def expected_logged_error_for_erroneous_trading_rule(self):
        markets = self.trading_rules_request_erroneous_mock_response.get("result", {}).get("markets", [])
        erroneous_rule = markets[0]
        return f"Error parsing the trading pair rule {erroneous_rule}. Skipping."

    @property
    def expected_exchange_order_id(self):
        return 28

    @property
    def is_order_fill_http_update_included_in_status_update(self) -> bool:
        return True

    @property
    def is_order_fill_http_update_executed_during_websocket_order_event_processing(self) -> bool:
        return False

    @property
    def expected_partial_fill_price(self) -> Decimal:
        return Decimal(10500)

    @property
    def expected_partial_fill_amount(self) -> Decimal:
        return Decimal("1")

    @property
    def expected_fill_fee(self) -> TradeFeeBase:
        return DeductedFromReturnsTradeFee(
            percent_token=self.base_asset,
            flat_fees=[TokenAmount(token=self.base_asset, amount=Decimal("30"))])

    @property
    def expected_fill_trade_id(self) -> str:
        return str(30000)

    def exchange_symbol_for_tokens(self, base_token: str, quote_token: str) -> str:
        return f"{base_token}{quote_token}"

    def create_exchange_instance(self):
        client_config_map = ClientConfigAdapter(ClientConfigMap())
        return CubeExchange(
            client_config_map=client_config_map,
            cube_api_key="1111111111-11111-11111-11111-1111111111",
            cube_api_secret="111111111111111111111111111111",
            cube_subaccount_id="1",
            trading_pairs=[self.trading_pair],
            trading_required=False,
            domain="live",
        )

    def validate_auth_credentials_present(self, request_call: RequestCall):
        self._validate_auth_credentials_taking_parameters_from_argument(
            request_call_tuple=request_call
        )

    def validate_order_creation_request(self, order: InFlightOrder, request_call: RequestCall):
        request_data = json.loads(request_call.kwargs["data"])
        request_order_type = TradeType.BUY if request_data["side"] == 0 else TradeType.SELL

        self.assertEqual(order.trade_type.name.upper(), request_order_type.name.upper())
        self.assertEqual(CubeExchange.cube_order_type(OrderType.LIMIT), request_data["orderType"])
        self.assertEqual(int(10000), Decimal(request_data["quantity"]))
        self.assertEqual(int(100000000), Decimal(request_data["price"]))
        self.assertEqual(int(order.client_order_id), request_data["clientOrderId"])

    def validate_order_cancelation_request(self, order: InFlightOrder, request_call: RequestCall):
        request_data = json.loads(request_call.kwargs["data"])
        self.assertEqual(int(order.client_order_id),
                         request_data["clientOrderId"])
        self.assertEqual(int(order.client_order_id),
                         request_data["requestId"])
        self.assertEqual(self.exchange.cube_subaccount_id, request_data["subaccountId"])

    def validate_order_status_request(self, order: InFlightOrder, request_call: RequestCall):
        request_params = request_call.kwargs["params"]
        self.assertEqual(500,
                         request_params["limit"])
        self.assertEqual(1640780030000000000, request_params["createdBefore"])

    def validate_trades_request(self, order: InFlightOrder, request_call: RequestCall):
        request_params = request_call.kwargs["params"]

        self.assertEqual(order.exchange_order_id, str(request_params["orderIds"]))

    def configure_successful_cancelation_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        url = web_utils.private_rest_url(CONSTANTS.POST_ORDER_PATH_URL)
        auth_header = self.exchange.authenticator.header_for_authentication()
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        response = self._order_cancelation_request_successful_mock_response(order=order)
        mock_api.delete(regex_url, body=json.dumps(response), callback=callback, headers=auth_header)
        return url

    def configure_erroneous_cancelation_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        url = web_utils.private_rest_url(CONSTANTS.POST_ORDER_PATH_URL)
        auth_header = self.exchange.authenticator.header_for_authentication()
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        mock_api.delete(regex_url, status=400, callback=callback, headers=auth_header)
        return url

    def configure_order_not_found_error_cancelation_response(
            self, order: InFlightOrder, mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> str:
        url = web_utils.private_rest_url(CONSTANTS.POST_ORDER_PATH_URL)
        auth_header = self.exchange.authenticator.header_for_authentication()
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        response = {"result": {"Rej": {"reason": 2}}}
        mock_api.delete(regex_url, status=200, body=json.dumps(response), callback=callback, headers=auth_header)
        return url

    def configure_one_successful_one_erroneous_cancel_all_response(
            self,
            successful_order: InFlightOrder,
            erroneous_order: InFlightOrder,
            mock_api: aioresponses) -> List[str]:
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
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        url = web_utils.private_rest_url(CONSTANTS.ORDER_PATH_URL.format(self.exchange.cube_subaccount_id))
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        response = self._order_status_request_completely_filled_mock_response(order=order)
        mock_api.get(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_canceled_order_status_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        url = web_utils.private_rest_url(CONSTANTS.ORDER_PATH_URL.format(self.exchange.cube_subaccount_id))
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        response = self._order_status_request_canceled_mock_response(order=order)
        mock_api.get(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_erroneous_http_fill_trade_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        url = web_utils.private_rest_url(path_url=CONSTANTS.FILLS_PATH_URL.format(self.exchange.cube_subaccount_id))
        regex_url = re.compile(url + r"\?.*")
        mock_api.get(regex_url, status=400, callback=callback)
        return url

    def configure_open_order_status_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        """
        :return: the URL configured
        """
        url = web_utils.private_rest_url(CONSTANTS.ORDER_PATH_URL.format(self.exchange.cube_subaccount_id))
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        response = self._order_status_request_open_mock_response(order=order)
        mock_api.get(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_http_error_order_status_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        url = web_utils.private_rest_url(CONSTANTS.ORDER_PATH_URL.format(self.exchange.cube_subaccount_id))
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        mock_api.get(regex_url, status=401, callback=callback)
        return url

    def configure_partially_filled_order_status_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        url = web_utils.private_rest_url(CONSTANTS.ORDER_PATH_URL.format(self.exchange.cube_subaccount_id))
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        response = self._order_status_request_partially_filled_mock_response(order=order)
        mock_api.get(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_order_not_found_error_order_status_response(
            self, order: InFlightOrder, mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> List[str]:
        url = web_utils.private_rest_url(CONSTANTS.ORDER_PATH_URL.format(self.exchange.cube_subaccount_id))
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        response = {"result": {"fills": []}}
        mock_api.get(regex_url, body=json.dumps(response), status=200, callback=callback)
        return [url]

    def configure_partial_fill_trade_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        url = web_utils.private_rest_url(path_url=CONSTANTS.FILLS_PATH_URL.format(self.exchange.cube_subaccount_id))
        regex_url = re.compile(url + r"\?.*")
        response = self._order_fills_request_partial_fill_mock_response(order=order)
        mock_api.get(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_full_fill_trade_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        url = web_utils.private_rest_url(path_url=CONSTANTS.FILLS_PATH_URL.format(self.exchange.cube_subaccount_id))
        regex_url = re.compile(url + r"\?.*")
        response = self._order_fills_request_full_fill_mock_response(order=order)
        mock_api.get(regex_url, body=json.dumps(response), callback=callback)
        return url

    def order_event_for_new_order_websocket_update(self, order: InFlightOrder):
        # OrderResponse:  new_ack
        # {
        #     msg_seq_num: 41359380
        #     client_order_id: 111114258471803
        #     request_id: 111114258471803
        #     exchange_order_id: 914930889
        #     market_id: 100006
        #     price: 17976
        #     quantity: 1
        #     side: ASK
        #     time_in_force: GOOD_FOR_SESSION
        #     transact_time: 1711095259064065797
        #     subaccount_id: 38393
        # }

        new_ack = trade_pb2.NewOrderAck(
            msg_seq_num=41359380,
            client_order_id=int(order.client_order_id),
            request_id=int(order.client_order_id),
            exchange_order_id=int(order.exchange_order_id),
            market_id=100006,
            price=int(order.price),
            quantity=int(order.amount),
            side=trade_pb2.Side.ASK if order.trade_type == TradeType.SELL else trade_pb2.Side.BID,
            time_in_force=trade_pb2.TimeInForce.GOOD_FOR_SESSION,
            transact_time=1711095259064065797,
            subaccount_id=38393
        )

        order_response = trade_pb2.OrderResponse(
            new_ack=new_ack
        )

        return order_response.SerializeToString()

    def order_event_for_canceled_order_websocket_update(self, order: InFlightOrder):
        # cancel_ack
        # {
        #     msg_seq_num: 41359101
        #     client_order_id: 111114258399802
        #     request_id: 111114258399802
        #     transact_time: 1711095258062910625
        #     subaccount_id: 38393
        #     reason: REQUESTED
        #     market_id: 100006
        #     exchange_order_id: 914921092
        # }

        cancel_ack = trade_pb2.CancelOrderAck(
            msg_seq_num=41359101,
            client_order_id=int(order.client_order_id),
            request_id=int(order.client_order_id),
            transact_time=1711095258062910625,
            subaccount_id=38393,
            reason=trade_pb2.CancelOrderAck.Reason.REQUESTED,
            market_id=100006,
            exchange_order_id=int(order.exchange_order_id)
        )

        order_response = trade_pb2.OrderResponse(
            cancel_ack=cancel_ack
        )

        return order_response.SerializeToString()

    def order_event_for_full_fill_websocket_update(self, order: InFlightOrder):
        # fill
        # {
        #     msg_seq_num: 41377011
        #     market_id: 100006
        #     client_order_id: 111114258471803
        #     exchange_order_id: 914930889
        #     fill_price: 17976
        #     fill_quantity: 1
        #     transact_time: 1711095326700540286
        #     subaccount_id: 38393
        #     cumulative_quantity: 1
        #     side: ASK
        #     fee_ratio {
        #         mantissa: 4
        #         exponent: -4
        #     }
        #     trade_id: 1280602
        # }

        fill = trade_pb2.Fill(
            msg_seq_num=41377011,
            market_id=100006,
            client_order_id=int(order.client_order_id),
            exchange_order_id=int(order.exchange_order_id),
            fill_price=int(order.price * Decimal(1e2)),
            fill_quantity=int(order.amount * Decimal(1e3)),
            transact_time=1711095326700540286,
            subaccount_id=38393,
            cumulative_quantity=1,
            side=trade_pb2.Side.ASK if order.trade_type == TradeType.SELL else trade_pb2.Side.BID,
            fee_ratio=trade_pb2.FixedPointDecimal(mantissa=4, exponent=-4),
            trade_id=1280602
        )

        order_response = trade_pb2.OrderResponse(
            fill=fill
        )

        return order_response.SerializeToString()

    def trade_event_for_full_fill_websocket_update(self, order: InFlightOrder):
        return None

    @aioresponses()
    def test_create_buy_limit_order_successfully(self, mock_api):
        pass
        # self._simulate_trading_rules_initialized()
        # request_sent_event = asyncio.Event()
        # self.exchange._set_current_timestamp(1640780000)
        #
        # url = self.order_creation_url
        #
        # creation_response = self.order_creation_request_successful_mock_response
        #
        # mock_api.post(url,
        #               body=json.dumps(creation_response),
        #               callback=lambda *args, **kwargs: request_sent_event.set())
        #
        # order_id = self.place_buy_order()
        # self.async_run_with_timeout(request_sent_event.wait())
        #
        # order_request = self._all_executed_requests(mock_api, url)[0]
        # self.validate_auth_credentials_present(order_request)
        #
        # self.assertIn(order_id, self.exchange.in_flight_orders)
        # self.validate_order_creation_request(
        #     order=self.exchange.in_flight_orders[order_id],
        #     request_call=order_request)
        #
        # create_event: BuyOrderCreatedEvent = self.buy_order_created_logger.event_log[0]
        # self.assertEqual(self.exchange.current_timestamp, create_event.timestamp)
        # self.assertEqual(self.trading_pair, create_event.trading_pair)
        # self.assertEqual(OrderType.LIMIT, create_event.type)
        # self.assertEqual(Decimal("100"), create_event.amount)
        # self.assertEqual(Decimal("10000"), create_event.price)
        # self.assertEqual(order_id, create_event.order_id)
        # self.assertEqual(str(self.expected_exchange_order_id), create_event.exchange_order_id)
        #
        # self.assertTrue(
        #     self.is_logged(
        #         "INFO",
        #         f"Created {OrderType.LIMIT.name} {TradeType.BUY.name} order {order_id} for "
        #         f"{Decimal('100.000000')} {self.trading_pair}."
        #     )
        # )

    @aioresponses()
    def test_create_order_fails_and_raises_failure_event(self, mock_api):
        pass
        # self._simulate_trading_rules_initialized()
        # request_sent_event = asyncio.Event()
        # self.exchange._set_current_timestamp(1640780000)
        # url = self.order_creation_url
        # mock_api.post(url,
        #               status=400,
        #               callback=lambda *args, **kwargs: request_sent_event.set())
        #
        # order_id = self.place_buy_order()
        # self.async_run_with_timeout(request_sent_event.wait())
        #
        # order_request = self._all_executed_requests(mock_api, url)[0]
        # self.validate_auth_credentials_present(order_request)
        # self.assertNotIn(order_id, self.exchange.in_flight_orders)
        # order_to_validate_request = InFlightOrder(
        #     client_order_id=order_id,
        #     trading_pair=self.trading_pair,
        #     order_type=OrderType.LIMIT,
        #     trade_type=TradeType.BUY,
        #     amount=Decimal("100"),
        #     creation_timestamp=self.exchange.current_timestamp,
        #     price=Decimal("10000")
        # )
        # self.validate_order_creation_request(
        #     order=order_to_validate_request,
        #     request_call=order_request)
        #
        # self.assertEquals(0, len(self.buy_order_created_logger.event_log))
        # failure_event: MarketOrderFailureEvent = self.order_failure_logger.event_log[0]
        # self.assertEqual(self.exchange.current_timestamp, failure_event.timestamp)
        # self.assertEqual(OrderType.LIMIT, failure_event.order_type)
        # self.assertEqual(order_id, failure_event.order_id)
        #
        # self.assertTrue(
        #     self.is_logged(
        #         "INFO",
        #         f"Order {order_id} has failed. Order Update: OrderUpdate(trading_pair='{self.trading_pair}', "
        #         f"update_timestamp={self.exchange.current_timestamp}, new_state={repr(OrderState.FAILED)}, "
        #         f"client_order_id='{order_id}', exchange_order_id=None, misc_updates=None)"
        #     )
        # )

    def test_initial_status_dict(self):
        self.exchange._set_trading_pair_symbol_map(None)

        status_dict = self.exchange.status_dict

        self.assertEqual(self._expected_initial_status_dict(), status_dict)
        self.assertFalse(self.exchange.ready)

    @aioresponses()
    def test_update_balances(self, mock_api):
        response = self.balance_request_mock_response_for_base_and_quote
        self._configure_balance_response(response=response, mock_api=mock_api)

        self.async_run_with_timeout(self.exchange._update_balances())

        available_balances = self.exchange.available_balances
        total_balances = self.exchange.get_all_balances()

        self.assertEqual(Decimal("10"), available_balances[self.base_asset])
        self.assertEqual(Decimal("2000"), available_balances[self.quote_asset])
        self.assertEqual(Decimal("10"), total_balances[self.base_asset])
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
    def test_lost_order_included_in_order_fills_update_and_not_in_order_status_update(self, mock_api):
        self.exchange._set_current_timestamp(1640780000)
        request_sent_event = asyncio.Event()

        self.exchange.start_tracking_order(
            order_id=self.client_order_id_prefix + "1",
            exchange_order_id=str(self.expected_exchange_order_id),
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal("100"),
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

            fill_event: OrderFilledEvent = self.order_filled_logger.event_log[0]

            self.assertEqual(self.exchange.current_timestamp, fill_event.timestamp)
            self.assertEqual(order.client_order_id, fill_event.order_id)
            self.assertEqual(order.trading_pair, fill_event.trading_pair)
            self.assertEqual(order.trade_type, fill_event.trade_type)
            self.assertEqual(order.order_type, fill_event.order_type)
            self.assertEqual(order.price, fill_event.price / Decimal(1e5))
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
                self.exchange._order_tracker.process_order_not_found(client_order_id=order.client_order_id))

        self.assertNotIn(order.client_order_id, self.exchange.in_flight_orders)

        order_event = self.order_event_for_canceled_order_websocket_update(order=order)

        done_ack = trade_pb2.Done(
            latest_transact_time=1711095259064065797,
            read_only=True,
        )

        boostrap_message = trade_pb2.Bootstrap(
            done=done_ack
        )

        done_message = boostrap_message.SerializeToString()

        mock_queue = AsyncMock()
        event_messages = [done_message, order_event, asyncio.CancelledError]
        mock_queue.get.side_effect = event_messages
        self.exchange._user_stream_tracker._user_stream = mock_queue

        try:
            self.async_run_with_timeout(self.exchange._user_stream_event_listener())
        except asyncio.CancelledError:
            pass

        self.assertNotIn(order.client_order_id, self.exchange._order_tracker.lost_orders)
        self.assertEqual(0, len(self.order_cancelled_logger.event_log))
        self.assertNotIn(order.client_order_id, self.exchange.in_flight_orders)
        self.assertFalse(order.is_cancelled)
        self.assertTrue(order.is_failure)

    @aioresponses()
    def test_lost_order_removed_if_not_found_during_order_status_update(self, mock_api):
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

        if self.is_order_fill_http_update_included_in_status_update:
            # This is done for completeness reasons (to have a response available for the trades request)
            self.configure_erroneous_http_fill_trade_response(order=order, mock_api=mock_api)

        self.configure_order_not_found_error_order_status_response(
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
            self.is_logged("INFO", f"BUY order {order.client_order_id} completely filled."))

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
                self.exchange._order_tracker.process_order_not_found(client_order_id=order.client_order_id))

        self.assertNotIn(order.client_order_id, self.exchange.in_flight_orders)

        order_event = self.order_event_for_full_fill_websocket_update(order=order)
        trade_event = self.trade_event_for_full_fill_websocket_update(order=order)

        done_ack = trade_pb2.Done(
            latest_transact_time=1711095259064065797,
            read_only=True,
        )

        boostrap_message = trade_pb2.Bootstrap(
            done=done_ack
        )

        done_message = boostrap_message.SerializeToString()

        mock_queue = AsyncMock()
        event_messages = [done_message]
        if trade_event:
            event_messages.append(trade_event)
        if order_event:
            event_messages.append(order_event)
        event_messages.append(asyncio.CancelledError)
        mock_queue.get.side_effect = event_messages
        self.exchange._user_stream_tracker._user_stream = mock_queue

        if self.is_order_fill_http_update_executed_during_websocket_order_event_processing:
            self.configure_full_fill_trade_response(
                order=order,
                mock_api=mock_api)

        try:
            self.async_run_with_timeout(self.exchange._user_stream_event_listener())
        except asyncio.CancelledError:
            pass
        # Execute one more synchronization to ensure the async task that processes the update is finished
        self.async_run_with_timeout(order.wait_until_completely_filled())

        fill_event: OrderFilledEvent = self.order_filled_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp, fill_event.timestamp)
        self.assertEqual(order.client_order_id, fill_event.order_id)
        self.assertEqual(order.trading_pair, fill_event.trading_pair)
        self.assertEqual(order.trade_type, fill_event.trade_type)
        self.assertEqual(order.order_type, fill_event.order_type)
        self.assertEqual(int(order.price), int(fill_event.price))
        self.assertEqual(order.amount, int(fill_event.amount))
        self.assertEqual(0, len(self.buy_order_completed_logger.event_log))
        self.assertNotIn(order.client_order_id, self.exchange.in_flight_orders)
        self.assertNotIn(order.client_order_id, self.exchange._order_tracker.lost_orders)
        self.assertTrue(order.is_filled)
        self.assertTrue(order.is_failure)

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

        urls = self.configure_completely_filled_order_status_response(
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

        for url in (urls if isinstance(urls, list) else [urls]):
            order_status_request = self._all_executed_requests(mock_api, url)[0]
            self.validate_auth_credentials_present(order_status_request)
            self.validate_order_status_request(
                order=order,
                request_call=order_status_request)

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

            fill_event: OrderFilledEvent = self.order_filled_logger.event_log[0]
            self.assertEqual(self.exchange.current_timestamp, fill_event.timestamp)
            self.assertEqual(order.client_order_id, fill_event.order_id)
            self.assertEqual(order.trading_pair, fill_event.trading_pair)
            self.assertEqual(order.trade_type, fill_event.trade_type)
            self.assertEqual(order.order_type, fill_event.order_type)
            self.assertEqual(order.price, fill_event.price / Decimal(1e5))
            self.assertEqual(order.amount, fill_event.amount)
            self.assertEqual(self.expected_fill_fee, fill_event.trade_fee)

        buy_event: BuyOrderCompletedEvent = self.buy_order_completed_logger.event_log[0]
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
            buy_event.quote_asset_amount / Decimal(1e5))
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
    def test_update_order_fills_from_trades_triggers_filled_event(self, mock_api):
        self.exchange._set_current_timestamp(1640780000)
        self.exchange._last_poll_timestamp = (self.exchange.current_timestamp -
                                              self.exchange.UPDATE_ORDER_STATUS_MIN_INTERVAL - 1)

        self.exchange.start_tracking_order(
            order_id="OID1",
            exchange_order_id="100234",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal("199.99"),
            amount=Decimal("0.01"),
        )
        order = self.exchange.in_flight_orders["OID1"]

        url = web_utils.private_rest_url(CONSTANTS.FILLS_PATH_URL.format(self.exchange.cube_subaccount_id))
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        trade_fill = {
            "result": {
                "name": "primary",
                "fills": [
                    {
                        "marketId": 100006,
                        "tradeId": 1280532,
                        "orderId": int(order.exchange_order_id),
                        "baseAmount": "10000000",
                        "quoteAmount": "1999900",
                        "feeAmount": "4000",
                        "feeAssetId": 5,
                        "filledAt": 1711093947444675299,
                        "side": "Bid",
                        "aggressingSide": "Ask",
                        "price": 19999,
                        "quantity": 1
                    }
                ]
            }
        }

        mock_response = trade_fill
        auth_header = self.exchange.authenticator.header_for_authentication()
        mock_api.get(regex_url, body=json.dumps(mock_response), headers=auth_header)

        self.async_run_with_timeout(self.exchange._update_orders_fills([order]))

        request = self._all_executed_requests(mock_api, url)[0]
        self.validate_auth_credentials_present(request)
        request_params = request.kwargs["params"]
        self.assertEqual(int(order.exchange_order_id), request_params["orderIds"])

        fill_event: OrderFilledEvent = self.order_filled_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp, fill_event.timestamp)
        self.assertEqual(order.client_order_id, fill_event.order_id)
        self.assertEqual(order.trading_pair, fill_event.trading_pair)
        self.assertEqual(order.trade_type, fill_event.trade_type)
        self.assertEqual(order.order_type, fill_event.order_type)
        self.assertEqual(Decimal(trade_fill["result"]["fills"][0]["price"]) / 10 ** 2, fill_event.price)
        self.assertEqual(Decimal(trade_fill["result"]["fills"][0]["baseAmount"]) / 10 ** 9, fill_event.amount)

    @aioresponses()
    def test_update_order_fills_from_trades_with_repeated_fill_triggers_only_one_event(self, mock_api):
        self.exchange._set_current_timestamp(1640780000)
        self.exchange._last_poll_timestamp = (self.exchange.current_timestamp -
                                              self.exchange.UPDATE_ORDER_STATUS_MIN_INTERVAL - 1)

        self.exchange.start_tracking_order(
            order_id="OID1",
            exchange_order_id="100234",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal("199.99"),
            amount=Decimal("0.01"),
        )
        order = self.exchange.in_flight_orders["OID1"]

        url = web_utils.private_rest_url(CONSTANTS.FILLS_PATH_URL.format(self.exchange.cube_subaccount_id))
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        trade_fill = {
            "result": {
                "name": "primary",
                "fills": [
                    {
                        "marketId": 100006,
                        "tradeId": 1280532,
                        "orderId": int(order.exchange_order_id),
                        "baseAmount": "10000000",
                        "quoteAmount": "1999900",
                        "feeAmount": "4000",
                        "feeAssetId": 5,
                        "filledAt": 1711093947444675299,
                        "side": "Bid",
                        "aggressingSide": "Ask",
                        "price": 19999,
                        "quantity": 1
                    }
                ]
            }
        }

        mock_response = trade_fill
        auth_header = self.exchange.authenticator.header_for_authentication()
        mock_api.get(regex_url, body=json.dumps(mock_response), headers=auth_header)

        self.async_run_with_timeout(self.exchange._update_orders_fills([order, order, order]))

        request = self._all_executed_requests(mock_api, url)[0]
        self.validate_auth_credentials_present(request)
        request_params = request.kwargs["params"]
        self.assertEqual(int(order.exchange_order_id), request_params["orderIds"])

        self.assertEqual(1, len(self.order_filled_logger.event_log))
        fill_event: OrderFilledEvent = self.order_filled_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp, fill_event.timestamp)
        self.assertEqual(order.client_order_id, fill_event.order_id)
        self.assertEqual(order.trading_pair, fill_event.trading_pair)
        self.assertEqual(order.trade_type, fill_event.trade_type)
        self.assertEqual(order.order_type, fill_event.order_type)
        self.assertEqual(Decimal(trade_fill["result"]["fills"][0]["price"]) / 10 ** 2, fill_event.price)
        self.assertEqual(Decimal(trade_fill["result"]["fills"][0]["baseAmount"]) / 10 ** 9, fill_event.amount)

    @aioresponses()
    def test_update_order_status_when_failed(self, mock_api):
        self.exchange._set_current_timestamp(1640780000)
        self.exchange._last_poll_timestamp = (self.exchange.current_timestamp -
                                              self.exchange.UPDATE_ORDER_STATUS_MIN_INTERVAL - 1)

        self.exchange.start_tracking_order(
            order_id="11111",
            exchange_order_id="100234",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal("199.99"),
            amount=Decimal("0.01"),
            creation_timestamp=self.exchange.current_timestamp
        )
        order = self.exchange.in_flight_orders["11111"]

        url_fill = web_utils.private_rest_url(CONSTANTS.FILLS_PATH_URL.format(self.exchange.cube_subaccount_id))
        regex_url_fill = re.compile(f"^{url_fill}".replace(".", r"\.").replace("?", r"\?"))

        trade_fill = {
            "result": {
                "name": "primary",
                "fills": []
            }
        }

        mock_response = trade_fill
        auth_header = self.exchange.authenticator.header_for_authentication()
        mock_api.get(regex_url_fill, body=json.dumps(mock_response), headers=auth_header)

        url_order_status = web_utils.private_rest_url(CONSTANTS.ORDER_PATH_URL.format(self.exchange.cube_subaccount_id))
        regex_url_order_status = re.compile(f"^{url_order_status}".replace(".", r"\.").replace("?", r"\?"))

        order_status = {
            "result": {
                "name": "primary",
                "orders": [
                    {
                        "orderId": int(order.exchange_order_id),
                        "marketId": 100006,
                        "side": "Ask",
                        "price": 17939,
                        "qty": 1,
                        "createdAt": 111111,
                        "canceledAt": 111112,
                        "reason": "Requested",
                        "status": "rejected",
                        "clientOrderId": int(order.client_order_id),
                        "timeInForce": 1,
                        "orderType": 0,
                        "selfTradePrevention": 0,
                        "cancelOnDisconnect": "false",
                        "postOnly": "true"
                    }
                ]
            }
        }
        mock_response = order_status
        auth_header = self.exchange.authenticator.header_for_authentication()
        mock_api.get(regex_url_order_status, body=json.dumps(mock_response), headers=auth_header)

        self.async_run_with_timeout(self.exchange._update_order_status())

        request = self._all_executed_requests(mock_api, regex_url_order_status)[0]
        self.validate_auth_credentials_present(request)
        request_params = request.kwargs["params"]
        self.assertEqual(int((order.creation_timestamp + 30) * 1e9), request_params["createdBefore"])
        self.assertEqual(500, request_params["limit"])

        failure_event: MarketOrderFailureEvent = self.order_failure_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp, failure_event.timestamp)
        self.assertEqual(order.client_order_id, failure_event.order_id)
        self.assertEqual(order.order_type, failure_event.order_type)
        self.assertNotIn(order.client_order_id, self.exchange.in_flight_orders)

        canceled_at_time = order_status["result"]["orders"][0]["canceledAt"] * 1e-9

        self.assertTrue(
            self.is_logged(
                "INFO",
                f"Order {order.client_order_id} has failed. Order Update: OrderUpdate(trading_pair='{self.trading_pair}',"
                f" update_timestamp={canceled_at_time}, new_state={repr(OrderState.FAILED)}, "
                f"client_order_id='{order.client_order_id}', exchange_order_id='{order.exchange_order_id}', "
                "misc_updates=None)")
        )

    def test_user_stream_update_for_order_failure(self):
        self.exchange._set_current_timestamp(1640780000)
        self.exchange.start_tracking_order(
            order_id="111111",
            exchange_order_id="100234",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("1"),
        )
        order = self.exchange.in_flight_orders["111111"]

        new_reject = trade_pb2.NewOrderReject(
            msg_seq_num=41359380,
            client_order_id=int(order.client_order_id),
            request_id=int(order.client_order_id),
            market_id=100006,
            price=int(order.price),
            quantity=int(order.amount),
            side=trade_pb2.Side.ASK if order.trade_type == TradeType.SELL else trade_pb2.Side.BID,
            time_in_force=trade_pb2.TimeInForce.GOOD_FOR_SESSION,
            transact_time=1711095259064065797,
            subaccount_id=38393,
            reason=trade_pb2.NewOrderReject.Reason.INVALID_QUANTITY,
            order_type=trade_pb2.OrderType.LIMIT
        )

        order_response = trade_pb2.OrderResponse(
            new_reject=new_reject
        )

        event_message = order_response.SerializeToString()

        done_ack = trade_pb2.Done(
            latest_transact_time=1711095259064065797,
            read_only=True,
        )

        boostrap_message = trade_pb2.Bootstrap(
            done=done_ack
        )

        done_message = boostrap_message.SerializeToString()

        mock_queue = AsyncMock()
        mock_queue.get.side_effect = [done_message, event_message, asyncio.CancelledError]
        self.exchange._user_stream_tracker._user_stream = mock_queue
        try:
            self.async_run_with_timeout(self.exchange._user_stream_event_listener())
        except asyncio.CancelledError:
            pass

        failure_event: MarketOrderFailureEvent = self.order_failure_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp, failure_event.timestamp)
        self.assertEqual(order.client_order_id, failure_event.order_id)
        self.assertEqual(order.order_type, failure_event.order_type)
        self.assertNotIn(order.client_order_id, self.exchange.in_flight_orders)
        self.assertTrue(order.is_failure)
        self.assertTrue(order.is_done)

    @patch("hummingbot.connector.utils.get_tracking_nonce")
    def test_client_order_id_on_order(self, mocked_nonce):
        mocked_nonce.return_value = 7
        prefix = CONSTANTS.HBOT_ORDER_ID_PREFIX

        result = self.exchange.buy(
            trading_pair=self.trading_pair,
            amount=Decimal("1"),
            order_type=OrderType.LIMIT,
            price=Decimal("2"),
        )
        expected_client_order_id = get_new_numeric_client_order_id(nonce_creator=self.exchange._nonce_creator,
                                                                   max_id_bit_count=CONSTANTS.MAX_ORDER_ID_LEN)
        expected_client_order_id = f"{prefix}{expected_client_order_id - 1}"
        self.assertEqual(result, expected_client_order_id)

        result = self.exchange.sell(
            trading_pair=self.trading_pair,
            amount=Decimal("1"),
            order_type=OrderType.LIMIT,
            price=Decimal("2"),
        )
        expected_client_order_id = get_new_numeric_client_order_id(nonce_creator=self.exchange._nonce_creator,
                                                                   max_id_bit_count=CONSTANTS.MAX_ORDER_ID_LEN)
        expected_client_order_id = f"{prefix}{expected_client_order_id - 1}"
        self.assertEqual(result, expected_client_order_id)

    @aioresponses()
    def test_place_order_get_rejection(self, mock_api):
        self.exchange._set_current_timestamp(1640780000)
        self.exchange._last_poll_timestamp = (self.exchange.current_timestamp -
                                              self.exchange.UPDATE_ORDER_STATUS_MIN_INTERVAL - 1)
        url = web_utils.private_rest_url(CONSTANTS.POST_ORDER_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        mock_response = {
            "result": {
                "Rej": {
                    "transactTime": 1711095259064065797,
                    "reason": "SOME REASON"
                }
            }
        }
        mock_api.post(regex_url, body=json.dumps(mock_response), status=200)

        o_id, transact_time = self.async_run_with_timeout(self.exchange._place_order(
            order_id="999999",
            trading_pair=self.trading_pair,
            amount=Decimal("1"),
            trade_type=TradeType.BUY,
            order_type=OrderType.LIMIT,
            price=Decimal("2"),
        ))
        self.assertEqual(o_id, "UNKNOWN")

    @aioresponses()
    def test_place_order_manage_server_overloaded_error_unkown_order(self, mock_api):
        self.exchange._set_current_timestamp(1640780000)
        self.exchange._last_poll_timestamp = (self.exchange.current_timestamp -
                                              self.exchange.UPDATE_ORDER_STATUS_MIN_INTERVAL - 1)
        url = web_utils.private_rest_url(CONSTANTS.POST_ORDER_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        mock_response = {"code": -1003, "msg": "Unknown error, please check your request or try again later."}
        mock_api.post(regex_url, body=json.dumps(mock_response), status=503)

        o_id, transact_time = self.async_run_with_timeout(self.exchange._place_order(
            order_id="999999",
            trading_pair=self.trading_pair,
            amount=Decimal("1"),
            trade_type=TradeType.BUY,
            order_type=OrderType.LIMIT,
            price=Decimal("2"),
        ))
        self.assertEqual(o_id, "UNKNOWN")

    @aioresponses()
    def test_place_order_manage_server_overloaded_error_failure(self, mock_api):
        self.exchange._set_current_timestamp(1640780000)
        self.exchange._last_poll_timestamp = (self.exchange.current_timestamp -
                                              self.exchange.UPDATE_ORDER_STATUS_MIN_INTERVAL - 1)

        url = web_utils.private_rest_url(CONSTANTS.POST_ORDER_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        mock_response = {"code": -1003, "msg": "Service Unavailable."}
        mock_api.post(regex_url, body=json.dumps(mock_response), status=503)

        self.assertRaises(
            IOError,
            self.async_run_with_timeout,
            self.exchange._place_order(
                order_id="999999",
                trading_pair=self.trading_pair,
                amount=Decimal("1"),
                trade_type=TradeType.BUY,
                order_type=OrderType.LIMIT,
                price=Decimal("2"),
            ))

        mock_response = {"code": -1003, "msg": "Internal error; unable to process your request. Please try again."}
        mock_api.post(regex_url, body=json.dumps(mock_response), status=503)

        self.assertRaises(
            IOError,
            self.async_run_with_timeout,
            self.exchange._place_order(
                order_id="999999",
                trading_pair=self.trading_pair,
                amount=Decimal("1"),
                trade_type=TradeType.BUY,
                order_type=OrderType.LIMIT,
                price=Decimal("2"),
            ))

    def test_format_trading_rules__min_notional_present(self):
        exchange_info = {
            "result": {
                "assets": [
                    {
                        "assetId": 5,
                        "symbol": self.base_asset,
                        "decimals": 9,
                        "displayDecimals": 2,
                        "settles": True,
                        "assetType": "Crypto",
                        "sourceId": 3,
                        "metadata": {},
                        "status": 1
                    },
                    {
                        "assetId": 7,
                        "symbol": self.quote_asset,
                        "decimals": 6,
                        "displayDecimals": 2,
                        "settles": True,
                        "assetType": "Crypto",
                        "sourceId": 3,
                        "metadata": {
                            "mint": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
                        },
                        "status": 1
                    }
                ],
                "markets": [
                    {
                        "marketId": 100006,
                        "symbol": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
                        "baseAssetId": 5,
                        "baseLotSize": "10000000",
                        "quoteAssetId": 7,
                        "quoteLotSize": "100",
                        "priceDisplayDecimals": 2,
                        "protectionPriceLevels": 1000,
                        "priceBandBidPct": 25,
                        "priceBandAskPct": 400,
                        "priceTickSize": "0.01",
                        "quantityTickSize": "0.01",
                        "status": 1,
                        "feeTableId": 2
                    }
                ],
                "feeTables": [
                    {
                        "feeTableId": 1,
                        "feeTiers": [
                            {
                                "priority": 0,
                                "makerFeeRatio": 0.0,
                                "takerFeeRatio": 0.0
                            }
                        ]
                    },
                    {
                        "feeTableId": 2,
                        "feeTiers": [
                            {
                                "priority": 0,
                                "makerFeeRatio": 0.0004,
                                "takerFeeRatio": 0.0008
                            }
                        ]
                    }
                ]
            }
        }

        result = self.async_run_with_timeout(self.exchange._format_trading_rules(exchange_info))

        self.assertEqual(result[0].min_notional_size, Decimal("0.0001"))

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
            amount=Decimal("2"),
        )
        order: InFlightOrder = self.exchange.in_flight_orders[self.client_order_id_prefix + "1"]

        order_url = self.configure_partially_filled_order_status_response(
            order=order,
            mock_api=mock_api)

        if self.is_order_fill_http_update_included_in_status_update:
            trade_url = self.configure_partial_fill_trade_response(
                order=order,
                mock_api=mock_api)

        self.assertTrue(order.is_open)

        self.async_run_with_timeout(self.exchange._update_order_status())

        if order_url:
            order_status_request = self._all_executed_requests(mock_api, order_url)[0]
            self.validate_auth_credentials_present(order_status_request)
            self.validate_order_status_request(
                order=order,
                request_call=order_status_request)

        self.assertTrue(order.is_open)
        self.assertEqual(OrderState.PARTIALLY_FILLED, order.current_state)

        if self.is_order_fill_http_update_included_in_status_update:
            if trade_url:
                trades_request = self._all_executed_requests(mock_api, trade_url)[0]
                self.validate_auth_credentials_present(trades_request)
                self.validate_trades_request(
                    order=order,
                    request_call=trades_request)

            fill_event: OrderFilledEvent = self.order_filled_logger.event_log[0]
            self.assertEqual(self.exchange.current_timestamp, fill_event.timestamp)
            self.assertEqual(order.client_order_id, fill_event.order_id)
            self.assertEqual(order.trading_pair, fill_event.trading_pair)
            self.assertEqual(order.trade_type, fill_event.trade_type)
            self.assertEqual(order.order_type, fill_event.order_type)
            self.assertEqual(self.expected_partial_fill_price, fill_event.price / Decimal(1e3))
            self.assertEqual(self.expected_partial_fill_amount, fill_event.amount)
            self.assertEqual(self.expected_fill_fee, fill_event.trade_fee)

    @aioresponses()
    def test_update_trading_rules(self, mock_api):
        self.exchange._set_current_timestamp(1000)

        self.configure_trading_rules_response(mock_api=mock_api)

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

    def test_user_stream_balance_update(self):
        if self.exchange.real_time_balance_update:
            self.exchange._set_current_timestamp(1640780000)

            balance_event = self.balance_event_websocket_update

            done_ack = trade_pb2.Done(
                latest_transact_time=1711095259064065797,
                read_only=True,
            )

            boostrap_message = trade_pb2.Bootstrap(
                done=done_ack
            )

            done_message = boostrap_message.SerializeToString()

            mock_queue = AsyncMock()
            mock_queue.get.side_effect = [balance_event, done_message, asyncio.CancelledError]
            self.exchange._user_stream_tracker._user_stream = mock_queue

            try:
                self.async_run_with_timeout(self.exchange._user_stream_event_listener())
            except asyncio.CancelledError:
                pass

            # self.async_run_with_timeout(self.exchange._user_stream_event_listener())

            self.assertEqual(Decimal("10"), self.exchange.available_balances[self.base_asset])
            self.assertEqual(Decimal("15"), self.exchange.get_balance(self.base_asset))

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
        done_ack = trade_pb2.Done(
            latest_transact_time=1711095259064065797,
            read_only=True,
        )

        boostrap_message = trade_pb2.Bootstrap(
            done=done_ack
        )

        done_message = boostrap_message.SerializeToString()

        mock_queue = AsyncMock()
        event_messages = [done_message, order_event, asyncio.CancelledError]
        mock_queue.get.side_effect = event_messages
        self.exchange._user_stream_tracker._user_stream = mock_queue

        try:
            self.async_run_with_timeout(self.exchange._user_stream_event_listener())
        except asyncio.CancelledError:
            pass

        cancel_event: OrderCancelledEvent = self.order_cancelled_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp, cancel_event.timestamp)
        self.assertEqual(order.client_order_id, cancel_event.order_id)
        self.assertEqual(order.exchange_order_id, cancel_event.exchange_order_id)
        self.assertNotIn(order.client_order_id, self.exchange.in_flight_orders)
        self.assertTrue(order.is_cancelled)
        self.assertTrue(order.is_done)

        self.assertTrue(
            self.is_logged("INFO", f"Successfully canceled order {order.client_order_id}.")
        )

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
        trade_event = self.trade_event_for_full_fill_websocket_update(order=order)

        done_ack = trade_pb2.Done(
            latest_transact_time=1711095259064065797,
            read_only=True,
        )

        boostrap_message = trade_pb2.Bootstrap(
            done=done_ack
        )

        done_message = boostrap_message.SerializeToString()

        mock_queue = AsyncMock()
        event_messages = [done_message]
        if trade_event:
            event_messages.append(trade_event)
        if order_event:
            event_messages.append(order_event)
        event_messages.append(asyncio.CancelledError)
        mock_queue.get.side_effect = event_messages
        self.exchange._user_stream_tracker._user_stream = mock_queue

        if self.is_order_fill_http_update_executed_during_websocket_order_event_processing:
            self.configure_full_fill_trade_response(
                order=order,
                mock_api=mock_api)

        try:
            self.async_run_with_timeout(self.exchange._user_stream_event_listener())
        except asyncio.CancelledError:
            pass
        # Execute one more synchronization to ensure the async task that processes the update is finished
        self.async_run_with_timeout(order.wait_until_completely_filled())

        fill_event: OrderFilledEvent = self.order_filled_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp, fill_event.timestamp)
        self.assertEqual(order.client_order_id, fill_event.order_id)
        self.assertEqual(order.trading_pair, fill_event.trading_pair)
        self.assertEqual(order.trade_type, fill_event.trade_type)
        self.assertEqual(order.order_type, fill_event.order_type)
        self.assertEqual(order.price, Decimal(int(fill_event.price)))
        self.assertEqual(order.amount, Decimal(int(fill_event.amount)))

        buy_event: BuyOrderCompletedEvent = self.buy_order_completed_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp, buy_event.timestamp)
        self.assertEqual(order.client_order_id, buy_event.order_id)
        self.assertEqual(order.base_asset, buy_event.base_asset)
        self.assertEqual(order.quote_asset, buy_event.quote_asset)
        self.assertEqual(order.amount, Decimal(int(buy_event.base_asset_amount)))
        self.assertEqual(Decimal(int(order.amount * fill_event.price)), Decimal(int(buy_event.quote_asset_amount)))
        self.assertEqual(order.order_type, buy_event.order_type)
        self.assertEqual(order.exchange_order_id, buy_event.exchange_order_id)
        self.assertNotIn(order.client_order_id, self.exchange.in_flight_orders)
        self.assertTrue(order.is_filled)
        self.assertTrue(order.is_done)

        self.assertTrue(
            self.is_logged(
                "INFO",
                f"BUY order {order.client_order_id} completely filled."
            )
        )

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

        done_ack = trade_pb2.Done(
            latest_transact_time=1711095259064065797,
            read_only=True,
        )

        boostrap_message = trade_pb2.Bootstrap(
            done=done_ack
        )

        done_message = boostrap_message.SerializeToString()

        mock_queue = AsyncMock()
        event_messages = [done_message, order_event, asyncio.CancelledError]
        mock_queue.get.side_effect = event_messages
        self.exchange._user_stream_tracker._user_stream = mock_queue

        try:
            self.async_run_with_timeout(self.exchange._user_stream_event_listener())
        except asyncio.CancelledError:
            pass

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

    def _validate_auth_credentials_taking_parameters_from_argument(self, request_call_tuple: RequestCall):
        request_headers = request_call_tuple.kwargs["headers"]
        self.assertIn("x-api-timestamp", request_headers)
        self.assertIn("x-api-signature", request_headers)
        self.assertIn("x-api-key", request_headers)
        self.assertEqual("1111111111-11111-11111-11111-1111111111", request_headers["x-api-key"])

    def _order_cancelation_request_successful_mock_response(self, order: InFlightOrder) -> Any:
        return {'result': {
            'Ack': {'msgSeqNum': 38377824, 'clientOrderId': order.client_order_id, 'requestId': order.client_order_id,
                    'transactTime': 1711085861601585726, 'subaccountId': 38393, 'reason': 2, 'marketId': 100006,
                    'exchangeOrderId': order.exchange_order_id}}}

    def _order_status_request_completely_filled_mock_response(self, order: InFlightOrder) -> Any:
        return {
            "result": {
                "name": "primary",
                "orders": [{
                    "orderId": order.exchange_order_id,
                    "marketId": 100006,
                    "side": "Bid",
                    "price": str(order.price * Decimal(1e2)),
                    "qty": 1,
                    "createdAt": 1711093892075781247,
                    "filledAt": 1711093947444675299,
                    "filledTotal": {
                        "baseAmount": str(order.amount * Decimal(1e9)),
                        "quoteAmount": str((order.amount * (order.price * Decimal(1e2))) * Decimal(1e9)),
                        "feeAmount": "4000",
                        "feeAssetId": 5,
                        "filledAt": 1711093947444675299
                    },
                    "fills": [
                        {
                            "baseAmount": str(order.amount * Decimal(1e9)),
                            "quoteAmount": str((order.amount * (order.price * Decimal(1e2))) * Decimal(1e9)),
                            "feeAmount": "4000",
                            "feeAssetId": 5,
                            "filledAt": 1711093947444675299,
                            "tradeId": 1280532,
                            "baseBatchId": "a10f5765-eb88-4c19-bd83-829650aa8cac",
                            "quoteBatchId": "c78614be-6a60-45e1-a920-4b32224084fb",
                            "baseSettled": "true",
                            "quoteSettled": "true"
                        }
                    ],
                    "settled": "true",
                    "status": "filled",
                    "clientOrderId": order.client_order_id,
                    "timeInForce": 1,
                    "orderType": 0,
                    "selfTradePrevention": 0,
                    "cancelOnDisconnect": "false",
                    "postOnly": "true"
                }
                ]
            }
        }

    def _order_status_request_canceled_mock_response(self, order: InFlightOrder) -> Any:
        return {
            "result": {
                "name": "primary",
                "orders": [{
                    "orderId": order.exchange_order_id,
                    "marketId": 100006,
                    "side": "Ask",
                    "price": str(order.price * Decimal(1e2)),
                    "qty": int(order.amount * Decimal(1e2)),
                    "createdAt": 1711094008074744935,
                    "canceledAt": 1711094115868231244,
                    "reason": "Requested",
                    "status": "canceled",
                    "clientOrderId": order.client_order_id,
                    "timeInForce": 1,
                    "orderType": 0,
                    "selfTradePrevention": 0,
                    "cancelOnDisconnect": "false",
                    "postOnly": "true"
                },
                ]
            }
        }

    def _order_status_request_open_mock_response(self, order: InFlightOrder) -> Any:
        return {
            "result": {
                "name": "primary",
                "orders": [{
                    "orderId": order.exchange_order_id,
                    "marketId": 100006,
                    "side": "Ask",
                    "price": str(order.price * Decimal(1e2)),
                    "qty": int(order.amount * Decimal(1e2)),
                    "createdAt": 1711094008074744935,
                    "canceledAt": 1711094115868231244,
                    "reason": "Requested",
                    "status": "open",
                    "clientOrderId": order.client_order_id,
                    "timeInForce": 1,
                    "orderType": 0,
                    "selfTradePrevention": 0,
                    "cancelOnDisconnect": "false",
                    "postOnly": "true"
                },
                ]
            }
        }

    def _order_status_request_partially_filled_mock_response(self, order: InFlightOrder) -> Any:
        return {
            "result": {
                "name": "primary",
                "orders": [{
                    "orderId": order.exchange_order_id,
                    "marketId": 100006,
                    "side": "Bid",
                    "price": str(order.price * Decimal(1e2)),
                    "qty": str(order.amount * Decimal(1e2)),
                    "createdAt": 1711093892075781247,
                    "filledAt": 1711093947444675299,
                    "filledTotal": {
                        "baseAmount": str(self.expected_partial_fill_amount * Decimal(1e9)),
                        "quoteAmount": str(
                            (self.expected_partial_fill_amount * order.price) * Decimal(1e9)),
                        "feeAmount": "4000",
                        "feeAssetId": 5,
                        "filledAt": 1711093947444675299
                    },
                    "fills": [
                        {
                            "baseAmount": str(self.expected_partial_fill_amount * Decimal(1e9)),
                            "quoteAmount": str(
                                (self.expected_partial_fill_amount * order.price) * Decimal(1e9)),
                            "feeAmount": "4000",
                            "feeAssetId": 5,
                            "filledAt": 1711093947444675299,
                            "tradeId": 1280532,
                            "baseBatchId": "a10f5765-eb88-4c19-bd83-829650aa8cac",
                            "quoteBatchId": "c78614be-6a60-45e1-a920-4b32224084fb",
                            "baseSettled": "true",
                            "quoteSettled": "true"
                        }
                    ],
                    "settled": "true",
                    "status": "p-filled",
                    "clientOrderId": order.client_order_id,
                    "timeInForce": 1,
                    "orderType": 0,
                    "selfTradePrevention": 0,
                    "cancelOnDisconnect": "false",
                    "postOnly": "true"
                }
                ]
            }
        }

    def _order_fills_request_partial_fill_mock_response(self, order: InFlightOrder):
        return {
            "result": {
                "name": "primary",
                "fills": [
                    {
                        "marketId": 100006,
                        "tradeId": self.expected_fill_trade_id,
                        "orderId": int(order.exchange_order_id),
                        "baseAmount": str(self.expected_partial_fill_amount * Decimal(1e9)),
                        "quoteAmount": str((self.expected_partial_fill_amount * self.expected_partial_fill_price) * Decimal(1e9)),
                        "feeAmount": str(self.expected_fill_fee.flat_fees[0].amount * Decimal(1e9)),
                        "feeAssetId": 5,
                        "filledAt": 1711093947444675299,
                        "side": "Bid",
                        "aggressingSide": "Ask",
                        "price": str(self.expected_partial_fill_price),
                        "quantity": 1
                    }
                ]
            }
        }

    def _order_fills_request_full_fill_mock_response(self, order: InFlightOrder):
        return {
            "result": {
                "name": "primary",
                "fills": [
                    {
                        "marketId": 100006,
                        "tradeId": self.expected_fill_trade_id,
                        "orderId": int(order.exchange_order_id),
                        "baseAmount": str(order.amount * Decimal(1e9)),
                        "quoteAmount": str((order.amount * (order.price * Decimal(1e2))) * Decimal(1e9)),
                        "feeAmount": str(self.expected_fill_fee.flat_fees[0].amount * Decimal(1e9)),
                        "feeAssetId": 5,
                        "filledAt": 1711093947444675299,
                        "side": "Bid",
                        "aggressingSide": "Ask",
                        "price": str(order.price),
                        "quantity": 1
                    }
                ]
            }
        }

    def _expected_initial_status_dict(self) -> Dict[str, bool]:
        return {
            "symbols_mapping_initialized": False,
            "order_books_initialized": False,
            "account_balance": True,
            "trading_rule_initialized": True,
            "user_stream_initialized": True,
        }
