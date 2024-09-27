import asyncio
import json
import logging
import re
from copy import deepcopy
from decimal import Decimal
from typing import Any, Callable, List, Optional, Tuple
from unittest.mock import AsyncMock

import pandas as pd
from aioresponses import aioresponses
from aioresponses.core import RequestCall

import hummingbot.connector.derivative.hashkey_perpetual.hashkey_perpetual_constants as CONSTANTS
import hummingbot.connector.derivative.hashkey_perpetual.hashkey_perpetual_web_utils as web_utils
from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.connector.derivative.hashkey_perpetual.hashkey_perpetual_derivative import HashkeyPerpetualDerivative
from hummingbot.connector.derivative.position import Position
from hummingbot.connector.test_support.perpetual_derivative_test import AbstractPerpetualDerivativeTests
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.connector.utils import combine_to_hb_trading_pair, get_new_client_order_id
from hummingbot.core.data_type.common import OrderType, PositionAction, PositionMode, PositionSide, TradeType
from hummingbot.core.data_type.funding_info import FundingInfo
from hummingbot.core.data_type.in_flight_order import InFlightOrder
from hummingbot.core.data_type.trade_fee import AddedToCostTradeFee, TokenAmount, TradeFeeBase


class HashkeyPerpetualDerivativeTests(AbstractPerpetualDerivativeTests.PerpetualDerivativeTests):
    _logger = logging.getLogger(__name__)

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.api_key = "someKey"
        cls.api_secret = "someSecret"
        cls.user_id = "someUserId"
        cls.base_asset = "BTC"
        cls.quote_asset = "USDT"  # linear
        cls.trading_pair = combine_to_hb_trading_pair(cls.base_asset, cls.quote_asset)

    @property
    def all_symbols_url(self):
        url = web_utils.rest_url(path_url=CONSTANTS.EXCHANGE_INFO_URL)
        return url

    @property
    def latest_prices_url(self):
        url = web_utils.rest_url(
            path_url=CONSTANTS.TICKER_PRICE_URL
        )
        url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        return url

    @property
    def network_status_url(self):
        url = web_utils.rest_url(path_url=CONSTANTS.PING_URL)
        url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        return url

    @property
    def trading_rules_url(self):
        url = web_utils.rest_url(path_url=CONSTANTS.EXCHANGE_INFO_URL)
        url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        return url

    @property
    def order_creation_url(self):
        url = web_utils.rest_url(
            path_url=CONSTANTS.ORDER_URL
        )
        url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        return url

    @property
    def balance_url(self):
        url = web_utils.rest_url(path_url=CONSTANTS.ACCOUNT_INFO_URL)
        return url

    @property
    def funding_info_url(self):
        url = web_utils.rest_url(
            path_url=CONSTANTS.FUNDING_INFO_URL,
        )
        url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        return url

    @property
    def mark_price_url(self):
        url = web_utils.rest_url(
            path_url=CONSTANTS.MARK_PRICE_URL,
        )
        url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        return url

    @property
    def index_price_url(self):
        url = web_utils.rest_url(
            path_url=CONSTANTS.INDEX_PRICE_URL,
        )
        url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        return url

    @property
    def funding_payment_url(self):
        pass

    @property
    def balance_request_mock_response_only_base(self):
        pass

    @property
    def all_symbols_request_mock_response(self):
        mock_response = {
            "contracts": [
                {
                    "filters": [
                        {
                            "minPrice": "0.1",
                            "maxPrice": "100000.00000000",
                            "tickSize": "0.1",
                            "filterType": "PRICE_FILTER"
                        },
                        {
                            "minQty": "0.001",
                            "maxQty": "10",
                            "stepSize": "0.001",
                            "marketOrderMinQty": "0",
                            "marketOrderMaxQty": "0",
                            "filterType": "LOT_SIZE"
                        },
                        {
                            "minNotional": "0",
                            "filterType": "MIN_NOTIONAL"
                        },
                        {
                            "maxSellPrice": "999999",
                            "buyPriceUpRate": "0.05",
                            "sellPriceDownRate": "0.05",
                            "maxEntrustNum": 200,
                            "maxConditionNum": 200,
                            "filterType": "LIMIT_TRADING"
                        },
                        {
                            "buyPriceUpRate": "0.05",
                            "sellPriceDownRate": "0.05",
                            "filterType": "MARKET_TRADING"
                        },
                        {
                            "noAllowMarketStartTime": "0",
                            "noAllowMarketEndTime": "0",
                            "limitOrderStartTime": "0",
                            "limitOrderEndTime": "0",
                            "limitMinPrice": "0",
                            "limitMaxPrice": "0",
                            "filterType": "OPEN_QUOTE"
                        }
                    ],
                    "exchangeId": "301",
                    "symbol": "BTCUSDT-PERPETUAL",
                    "symbolName": "BTCUSDT-PERPETUAL",
                    "status": "TRADING",
                    "baseAsset": "BTCUSDT-PERPETUAL",
                    "baseAssetPrecision": "0.001",
                    "quoteAsset": "USDT",
                    "quoteAssetPrecision": "0.1",
                    "icebergAllowed": False,
                    "inverse": False,
                    "index": "USDT",
                    "marginToken": "USDT",
                    "marginPrecision": "0.0001",
                    "contractMultiplier": "0.001",
                    "underlying": "BTC",
                    "riskLimits": [
                        {
                            "riskLimitId": "200000722",
                            "quantity": "1000.00",
                            "initialMargin": "0.10",
                            "maintMargin": "0.005",
                            "isWhite": False
                        }
                    ]
                }
            ]
        }
        return mock_response

    @property
    def latest_prices_request_mock_response(self):
        mock_response = [
            {
                "s": "BTCUSDT-PERPETUAL",
                "p": "9999.9"
            }
        ]
        return mock_response

    @property
    def all_symbols_including_invalid_pair_mock_response(self):
        mock_response = mock_response = {
            "contracts": [
                {
                    "filters": [
                        {
                            "minPrice": "0.1",
                            "maxPrice": "100000.00000000",
                            "tickSize": "0.1",
                            "filterType": "PRICE_FILTER"
                        },
                        {
                            "minQty": "0.001",
                            "maxQty": "10",
                            "stepSize": "0.001",
                            "marketOrderMinQty": "0",
                            "marketOrderMaxQty": "0",
                            "filterType": "LOT_SIZE"
                        },
                        {
                            "minNotional": "0",
                            "filterType": "MIN_NOTIONAL"
                        },
                        {
                            "maxSellPrice": "999999",
                            "buyPriceUpRate": "0.05",
                            "sellPriceDownRate": "0.05",
                            "maxEntrustNum": 200,
                            "maxConditionNum": 200,
                            "filterType": "LIMIT_TRADING"
                        },
                        {
                            "buyPriceUpRate": "0.05",
                            "sellPriceDownRate": "0.05",
                            "filterType": "MARKET_TRADING"
                        },
                        {
                            "noAllowMarketStartTime": "0",
                            "noAllowMarketEndTime": "0",
                            "limitOrderStartTime": "0",
                            "limitOrderEndTime": "0",
                            "limitMinPrice": "0",
                            "limitMaxPrice": "0",
                            "filterType": "OPEN_QUOTE"
                        }
                    ],
                    "exchangeId": "301",
                    "symbol": "BTCUSDT-PERPETUAL",
                    "symbolName": "BTCUSDT-PERPETUAL",
                    "status": "STOPPING",
                    "baseAsset": "BTCUSDT-PERPETUAL",
                    "baseAssetPrecision": "0.001",
                    "quoteAsset": "USDT",
                    "quoteAssetPrecision": "0.1",
                    "icebergAllowed": False,
                    "inverse": False,
                    "index": "USDT",
                    "marginToken": "USDT",
                    "marginPrecision": "0.0001",
                    "contractMultiplier": "0.001",
                    "underlying": "BTC",
                    "riskLimits": [
                        {
                            "riskLimitId": "200000722",
                            "quantity": "1000.00",
                            "initialMargin": "0.10",
                            "maintMargin": "0.005",
                            "isWhite": False
                        }
                    ]
                }
            ]
        }
        return "INVALID-PAIR", mock_response

    def empty_funding_payment_mock_response(self):
        pass

    @aioresponses()
    def test_funding_payment_polling_loop_sends_update_event(self, *args, **kwargs):
        pass

    @property
    def network_status_request_successful_mock_response(self):
        mock_response = {}
        return mock_response

    @property
    def trading_rules_request_mock_response(self):
        return self.all_symbols_request_mock_response

    @property
    def trading_rules_request_erroneous_mock_response(self):
        _, resp = self.all_symbols_including_invalid_pair_mock_response
        return resp

    @property
    def order_creation_request_successful_mock_response(self):
        mock_response = {
            "time": "1723800711177",
            "updateTime": "1723800711191",
            "orderId": "1753761908689837056",
            "clientOrderId": get_new_client_order_id(
                is_buy=True,
                trading_pair=self.trading_pair,
                hbot_order_id_prefix=CONSTANTS.HBOT_BROKER_ID,
                max_id_len=CONSTANTS.MAX_ORDER_ID_LEN,
            ),
            "symbol": self.exchange_trading_pair,
            "price": "5050",
            "leverage": "5",
            "origQty": "100",
            "executedQty": "0",
            "avgPrice": "0",
            "marginLocked": "101",
            "type": "LIMIT",
            "side": "BUY_OPEN",
            "timeInForce": "GTC",
            "status": "NEW",
            "priceType": "INPUT",
            "contractMultiplier": "0.00100000"
        }
        return mock_response

    @property
    def limit_maker_order_creation_request_successful_mock_response(self):
        mock_response = {
            "time": "1723800711177",
            "updateTime": "1723800711191",
            "orderId": "1753761908689837056",
            "clientOrderId": get_new_client_order_id(
                is_buy=True,
                trading_pair=self.trading_pair,
                hbot_order_id_prefix=CONSTANTS.HBOT_BROKER_ID,
                max_id_len=CONSTANTS.MAX_ORDER_ID_LEN,
            ),
            "symbol": self.exchange_trading_pair,
            "price": "5050",
            "leverage": "5",
            "origQty": "100",
            "executedQty": "0",
            "avgPrice": "0",
            "marginLocked": "101",
            "type": "LIMIT",
            "side": "BUY_OPEN",
            "timeInForce": "GTC",
            "status": "NEW",
            "priceType": "INPUT",
            "contractMultiplier": "0.00100000"
        }
        return mock_response

    @property
    def balance_request_mock_response_for_base_and_quote(self):
        mock_response = [
            {
                "balance": "3000",
                "availableBalance": "2000",
                "positionMargin": "500",
                "orderMargin": "500",
                "asset": "USDT",
                "crossUnRealizedPnl": "1000"
            }
        ]
        return mock_response

    @aioresponses()
    def test_update_balances(self, mock_api):
        response = self.balance_request_mock_response_for_base_and_quote
        self._configure_balance_response(response=response, mock_api=mock_api)

        self.async_run_with_timeout(self.exchange._update_balances())

        available_balances = self.exchange.available_balances
        total_balances = self.exchange.get_all_balances()

        self.assertEqual(Decimal("2000"), available_balances[self.quote_asset])
        self.assertEqual(Decimal("3000"), total_balances[self.quote_asset])

    @property
    def balance_event_websocket_update(self):
        mock_response = [
            {
                "e": "outboundContractAccountInfo",        # event type
                "E": "1714717314118",                      # event time
                "T": True,                                 # can trade
                "W": True,                                 # can withdraw
                "D": True,                                 # can deposit
                "B": [                                     # balances changed
                    {
                        "a": "USDT",                       # asset
                        "f": "474960.65",                  # free amount
                        "l": "100000",                     # locked amount
                        "r": ""                            # to be released
                    }
                ]
            }
        ]
        return mock_response

    @property
    def position_event_websocket_update(self):
        mock_response = [
            {
                "e": "outboundContractPositionInfo",  # event type
                "E": "1715224789008",                 # event time
                "A": "1649292498437183234",           # account ID
                "s": self.exchange_trading_pair,      # symbol
                "S": "LONG",                          # side, LONG or SHORT
                "p": "3212.78",                       # avg Price
                "P": "3000",                          # total position
                "a": "3000",                          # available position
                "f": "0",                             # liquidation price
                "m": "13680.323",                     # portfolio margin
                "r": "-3.8819",                       # realised profit and loss (Pnl)
                "up": "-4909.9255",                   # unrealized profit and loss (unrealizedPnL)
                "pr": "-0.3589",                      # profit rate of current position
                "pv": "73579.09",                     # position value (USDT)
                "v": "5.00",                          # leverage
                "mt": "CROSS",          # position type, only CROSS, ISOLATED later will support
                "mm": "0"                             # min margin
            }
        ]
        return mock_response

    @property
    def position_event_websocket_update_zero(self):
        mock_response = [
            {
                "e": "outboundContractPositionInfo",  # event type
                "E": "1715224789008",                 # event time
                "A": "1649292498437183234",           # account ID
                "s": self.exchange_trading_pair,      # symbol
                "S": "LONG",                          # side, LONG or SHORT
                "p": "3212.78",                       # avg Price
                "P": "0",                             # total position
                "a": "0",                             # available position
                "f": "0",                             # liquidation price
                "m": "13680.323",                     # portfolio margin
                "r": "-3.8819",                       # realised profit and loss (Pnl)
                "up": "-4909.9255",                   # unrealized profit and loss (unrealizedPnL)
                "pr": "-0.3589",                      # profit rate of current position
                "pv": "73579.09",                     # position value (USDT)
                "v": "5.00",                          # leverage
                "mt": "CROSS",          # position type, only CROSS, ISOLATED later will support
                "mm": "0"                             # min margin
            }
        ]
        return mock_response

    @property
    def expected_latest_price(self):
        return 9999.9

    @property
    def funding_payment_mock_response(self):
        raise NotImplementedError

    @property
    def expected_supported_position_modes(self) -> List[PositionMode]:
        raise NotImplementedError  # test is overwritten

    @property
    def target_funding_info_next_funding_utc_str(self):
        datetime_str = str(
            pd.Timestamp.utcfromtimestamp(
                self.target_funding_info_next_funding_utc_timestamp)
        ).replace(" ", "T") + "Z"
        return datetime_str

    @property
    def target_funding_info_next_funding_utc_str_ws_updated(self):
        datetime_str = str(
            pd.Timestamp.utcfromtimestamp(
                self.target_funding_info_next_funding_utc_timestamp_ws_updated)
        ).replace(" ", "T") + "Z"
        return datetime_str

    @property
    def target_funding_payment_timestamp_str(self):
        datetime_str = str(
            pd.Timestamp.utcfromtimestamp(
                self.target_funding_payment_timestamp)
        ).replace(" ", "T") + "Z"
        return datetime_str

    @property
    def funding_info_mock_response(self):
        mock_response = self.latest_prices_request_mock_response
        funding_info = mock_response[0]
        funding_info["index_price"] = self.target_funding_info_index_price
        funding_info["mark_price"] = self.target_funding_info_mark_price
        funding_info["predicted_funding_rate"] = self.target_funding_info_rate
        return funding_info

    @property
    def funding_rate_mock_response(self):
        return [
            {
                "symbol": "ETHUSDT-PERPETUAL",
                "rate": "0.0001",
                "nextSettleTime": "1724140800000"
            },
            {
                "symbol": "BTCUSDT-PERPETUAL",
                "rate": self.target_funding_info_rate,
                "nextSettleTime": str(self.target_funding_info_next_funding_utc_timestamp * 1e3)
            },
        ]

    @property
    def index_price_mock_response(self):
        return {
            "index": {
                f"{self.base_asset}{self.quote_asset}": self.target_funding_info_index_price
            },
            "edp": {
                f"{self.base_asset}{self.quote_asset}": "2"
            }
        }

    @property
    def mark_price_mock_response(self):
        return {
            "exchangeId": 301,
            "symbolId": self.exchange_trading_pair,
            "price": self.target_funding_info_mark_price,
            "time": str(self.target_funding_info_next_funding_utc_timestamp * 1e3)
        }

    @property
    def expected_supported_order_types(self):
        return [OrderType.LIMIT, OrderType.MARKET, OrderType.LIMIT_MAKER]

    @property
    def expected_trading_rule(self):
        rule = self.trading_rules_request_mock_response["contracts"][0]

        trading_pair = f"{rule['underlying']}-{rule['quoteAsset']}"
        trading_filter_info = {item["filterType"]: item for item in rule.get("filters", [])}

        min_order_size = trading_filter_info.get("LOT_SIZE", {}).get("minQty")
        min_price_increment = trading_filter_info.get("PRICE_FILTER", {}).get("minPrice")
        min_base_amount_increment = rule.get("baseAssetPrecision")
        min_notional_size = trading_filter_info.get("MIN_NOTIONAL", {}).get("minNotional")

        return TradingRule(trading_pair,
                           min_order_size=Decimal(min_order_size),
                           min_price_increment=Decimal(min_price_increment),
                           min_base_amount_increment=Decimal(min_base_amount_increment),
                           min_notional_size=Decimal(min_notional_size))

    @property
    def expected_logged_error_for_erroneous_trading_rule(self):
        erroneous_rule = self.trading_rules_request_erroneous_mock_response["contracts"][0]
        return f"Error parsing the trading pair rule {erroneous_rule}. Skipping."

    @property
    def expected_exchange_order_id(self):
        return "1753761908689837056"

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
    def expected_fill_fee(self) -> TradeFeeBase:
        return AddedToCostTradeFee(
            percent_token=self.quote_asset,
            flat_fees=[TokenAmount(token=self.quote_asset, amount=Decimal("0.1"))],
        )

    @property
    def expected_fill_trade_id(self) -> str:
        return "1755540311713595904"

    def async_run_with_timeout(self, coroutine, timeout: int = 1):
        ret = asyncio.get_event_loop().run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    def exchange_symbol_for_tokens(self, base_token: str, quote_token: str) -> str:
        return f"{base_token}{quote_token}-PERPETUAL"

    def create_exchange_instance(self) -> HashkeyPerpetualDerivative:
        client_config_map = ClientConfigAdapter(ClientConfigMap())
        exchange = HashkeyPerpetualDerivative(
            client_config_map,
            self.api_key,
            self.api_secret,
            trading_pairs=[self.trading_pair],
        )
        return exchange

    def validate_auth_credentials_present(self, request_call: RequestCall):
        request_headers = request_call.kwargs["headers"]
        request_params = request_call.kwargs["params"]

        self.assertIn("X-HK-APIKEY", request_headers)
        self.assertIn("timestamp", request_params)
        self.assertIn("signature", request_params)

    def validate_order_creation_request(self, order: InFlightOrder, request_call: RequestCall):
        request_params = request_call.kwargs["params"]
        self.assertEqual(order.trade_type.name.lower(), request_params["side"].split("_")[0].lower())
        self.assertEqual(self.exchange_trading_pair, request_params["symbol"])
        self.assertEqual(order.amount, self.exchange.get_amount_of_contracts(
            self.trading_pair, abs(Decimal(str(request_params["quantity"])))))
        self.assertEqual(order.client_order_id, request_params["clientOrderId"])

    def validate_order_cancelation_request(self, order: InFlightOrder, request_call: RequestCall):
        request_params = request_call.kwargs["params"]
        request_data = request_call.kwargs["data"]
        self.assertIsNotNone(request_params)
        self.assertIsNone(request_data)

    def validate_order_status_request(self, order: InFlightOrder, request_call: RequestCall):
        request_params = request_call.kwargs["params"]
        request_data = request_call.kwargs["data"]
        self.assertIsNotNone(request_params)
        self.assertIsNone(request_data)

    def validate_trades_request(self, order: InFlightOrder, request_call: RequestCall):
        request_params = request_call.kwargs["params"]
        self.assertEqual(self.exchange_trading_pair, request_params["symbol"])
        self.assertEqual(order.exchange_order_id, request_params["orderId"])

    def configure_successful_cancelation_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None,
    ) -> str:
        """
        :return: the URL configured for the cancelation
        """
        url = web_utils.rest_url(path_url=CONSTANTS.ORDER_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        response = self._order_cancelation_request_successful_mock_response(order=order)
        mock_api.delete(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_erroneous_cancelation_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None,
    ) -> str:
        url = web_utils.rest_url(
            path_url=CONSTANTS.ORDER_URL
        )
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        mock_api.delete(regex_url, status=400, callback=callback)
        return url

    def configure_one_successful_one_erroneous_cancel_all_response(
            self,
            successful_order: InFlightOrder,
            erroneous_order: InFlightOrder,
            mock_api: aioresponses,
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
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> str:
        url = web_utils.rest_url(path_url=CONSTANTS.ORDER_URL)

        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")

        response = self._order_status_request_completely_filled_mock_response(order=order)
        mock_api.get(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_canceled_order_status_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None,
    ) -> str:
        url = web_utils.rest_url(path_url=CONSTANTS.ORDER_URL)

        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")

        response = self._order_status_request_canceled_mock_response(order=order)
        mock_api.get(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_open_order_status_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None,
    ) -> str:
        url = web_utils.rest_url(path_url=CONSTANTS.ORDER_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")

        response = self._order_status_request_open_mock_response(order=order)
        mock_api.get(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_http_error_order_status_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None,
    ) -> str:
        url = web_utils.rest_url(path_url=CONSTANTS.ORDER_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")

        mock_api.get(regex_url, status=404, callback=callback)
        return url

    def configure_partially_filled_order_status_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None,
    ) -> str:
        url = web_utils.rest_url(path_url=CONSTANTS.ORDER_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")

        response = self._order_status_request_partially_filled_mock_response(order=order)
        mock_api.get(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_partial_fill_trade_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None,
    ) -> str:
        url = web_utils.rest_url(path_url=CONSTANTS.ORDER_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")

        response = self._order_fills_request_partial_fill_mock_response(order=order)
        mock_api.get(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_full_fill_trade_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None,
    ) -> str:
        url = web_utils.rest_url(
            path_url=CONSTANTS.ACCOUNT_TRADE_LIST_URL,
        )
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")

        response = self._order_fills_request_full_fill_mock_response(order=order)
        mock_api.get(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_erroneous_http_fill_trade_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None,
    ) -> str:
        url = web_utils.rest_url(path_url=CONSTANTS.ORDER_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")

        mock_api.get(regex_url, status=400, callback=callback)
        return url

    def configure_failed_set_position_mode(
            self,
            position_mode: PositionMode,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None
    ):
        url = web_utils.rest_url(
            path_url=CONSTANTS.SET_POSITION_MODE_URL
        )
        get_position_url = web_utils.rest_url(
            path_url=CONSTANTS.POSITION_INFORMATION_URL
        )
        regex_url = re.compile(f"^{url}")
        regex_get_position_url = re.compile(f"^{get_position_url}")

        error_msg = ""
        get_position_mock_response = [
            {"mode": 'single'}
        ]
        mock_response = {
            "label": "1666",
            "detail": "",
        }
        mock_api.get(regex_get_position_url, body=json.dumps(get_position_mock_response), callback=callback)
        mock_api.post(regex_url, body=json.dumps(mock_response), callback=callback)

        return url, f"{error_msg}"

    def configure_successful_set_position_mode(
            self,
            position_mode: PositionMode,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None,
    ):
        pass

    def configure_failed_set_leverage(
            self,
            leverage: PositionMode,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None,
    ) -> Tuple[str, str]:
        url = web_utils.rest_url(path_url=CONSTANTS.SET_LEVERAGE_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")

        err_msg = "leverage is diff"
        mock_response = {
            "code": "0001",
            "msg": err_msg
        }
        mock_api.post(regex_url, body=json.dumps(mock_response), callback=callback)
        return url, err_msg

    def configure_successful_set_leverage(
            self,
            leverage: int,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None,
    ):
        url = web_utils.rest_url(path_url=CONSTANTS.SET_LEVERAGE_URL)
        regex_url = re.compile(f"^{url}")

        mock_response = {
            "code": "0000",
            "symbolId": "BTCUSDT-PERPETUAL",
            "leverage": str(leverage)
        }

        mock_api.post(regex_url, body=json.dumps(mock_response), callback=callback)

        return url

    def order_event_for_new_order_websocket_update(self, order: InFlightOrder):
        self._simulate_trading_rules_initialized()
        return [
            {
                "e": "contractExecutionReport",          # event type
                "E": "1714716899100",                    # event time
                "s": self.exchange_trading_pair,         # symbol
                "c": order.client_order_id,              # client order ID
                "S": "BUY",                              # side
                "o": "LIMIT",                            # order type
                "f": "GTC",                              # time in force
                "q": self.exchange.get_quantity_of_contracts(self.trading_pair, order.amount),         # order quantity
                "p": str(order.price),                   # order price
                "X": "NEW",                              # current order status
                "i": order.exchange_order_id,            # order ID
                "l": "0",                                # last executed quantity
                "z": "0",                                # cumulative filled quantity
                "L": "",                                 # last executed price
                "n": "0",                                # commission amount
                "N": "",                                 # commission asset
                "u": True,                               # is the trade normal, ignore for now
                "w": True,                               # is the order working?
                "m": False,                              # is this trade the maker side?
                "O": "1714716899068",                    # order creation time
                "Z": "0",                                # cumulative quote asset transacted quantity
                "C": False,                              # is close, Is the buy close or sell close
                "V": "26105.5",                          # average executed price
                "reqAmt": "0",                           # requested cash amount
                "d": "",                                 # execution ID
                "r": "10000",                            # unfilled quantity
                "v": "5",                                # leverage
                "P": "30000",                            # Index price
                "lo": True,                              # Is liquidation Order
                "lt": "LIQUIDATION_MAKER"                # Liquidation type "LIQUIDATION_MAKER_ADL", "LIQUIDATION_MAKER", "LIQUIDATION_TAKER" (To be released)
            }
        ]

    def order_event_for_canceled_order_websocket_update(self, order: InFlightOrder):
        self._simulate_trading_rules_initialized()

        return [
            {
                "e": "contractExecutionReport",          # event type
                "E": "1714716899100",                    # event time
                "s": self.exchange_trading_pair,         # symbol
                "c": order.client_order_id,              # client order ID
                "S": "BUY",                              # side
                "o": "LIMIT",                            # order type
                "f": "GTC",                              # time in force
                "q": self.exchange.get_quantity_of_contracts(self.trading_pair, order.amount),         # order quantity
                "p": str(order.price),                   # order price
                "X": "CANCELED",                        # current order status
                "i": order.exchange_order_id,            # order ID
                "l": "0",                                # last executed quantity
                "z": "0",                                # cumulative filled quantity
                "L": "",                                 # last executed price
                "n": "0",                                # commission amount
                "N": "",                                 # commission asset
                "u": True,                               # is the trade normal, ignore for now
                "w": True,                               # is the order working?
                "m": False,                              # is this trade the maker side?
                "O": "1714716899068",                    # order creation time
                "Z": "0",                                # cumulative quote asset transacted quantity
                "C": False,                              # is close, Is the buy close or sell close
                "V": "26105.5",                          # average executed price
                "reqAmt": "0",                           # requested cash amount
                "d": "",                                 # execution ID
                "r": "10000",                            # unfilled quantity
                "v": "5",                                # leverage
                "P": "30000",                            # Index price
                "lo": True,                              # Is liquidation Order
                "lt": "LIQUIDATION_MAKER"                # Liquidation type "LIQUIDATION_MAKER_ADL", "LIQUIDATION_MAKER", "LIQUIDATION_TAKER" (To be released)
            }
        ]

    def order_event_for_full_fill_websocket_update(self, order: InFlightOrder):
        self._simulate_trading_rules_initialized()

        quantity = self.exchange.get_quantity_of_contracts(self.trading_pair, order.amount)
        return [
            {
                "e": "contractExecutionReport",          # event type
                "E": "1714716899100",                    # event time
                "s": self.exchange_trading_pair,         # symbol
                "c": order.client_order_id,              # client order ID
                "S": "BUY",                              # side
                "o": "LIMIT",                            # order type
                "f": "GTC",                              # time in force
                "q": str(quantity),                      # order quantity
                "p": str(order.price),                   # order price
                "X": "FILLED",                           # current order status
                "i": order.exchange_order_id,            # order ID
                "l": str(quantity),                      # last executed quantity
                "z": "0",                                # cumulative filled quantity
                "L": str(order.price),                   # last executed price
                "n": "0.1",                                # commission amount
                "N": "USDT",                             # commission asset
                "u": True,                               # is the trade normal, ignore for now
                "w": True,                               # is the order working?
                "m": False,                              # is this trade the maker side?
                "O": "1714716899068",                    # order creation time
                "Z": "0",                                # cumulative quote asset transacted quantity
                "C": False,                              # is close, Is the buy close or sell close
                "V": "26105.5",                          # average executed price
                "reqAmt": "0",                           # requested cash amount
                "d": "",                                 # execution ID
                "r": "10000",                            # unfilled quantity
                "v": "5",                                # leverage
                "P": "30000",                            # Index price
                "lo": True,                              # Is liquidation Order
                "lt": "LIQUIDATION_MAKER"                # Liquidation type "LIQUIDATION_MAKER_ADL", "LIQUIDATION_MAKER", "LIQUIDATION_TAKER" (To be released)
            }
        ]

    def trade_event_for_full_fill_websocket_update(self, order: InFlightOrder):
        self._simulate_trading_rules_initialized()

        return [
            {
                "e": "ticketInfo",                 # event type
                "E": "1714717146971",              # event time
                "s": self.exchange_trading_pair,   # symbol
                "q": self.exchange.get_quantity_of_contracts(self.trading_pair, order.amount),                      # quantity
                "t": "1714717146957",              # time
                "p": str(order.price),             # price
                "T": self.expected_fill_trade_id,  # ticketId
                "o": order.exchange_order_id,      # orderId
                "c": order.client_order_id,        # clientOrderId
                "a": "1649292498437183232",        # accountId
                "m": True,                         # isMaker
                "S": order.trade_type              # side  SELL or BUY
            }
        ]

    def position_event_for_full_fill_websocket_update(self, order: InFlightOrder, unrealized_pnl: float):
        mock_response = [
            {
                "e": "outboundContractPositionInfo",  # event type
                "E": "1715224789008",                 # event time
                "A": "1649292498437183234",           # account ID
                "s": self.exchange_trading_pair,      # symbol
                "S": "LONG",                          # side, LONG or SHORT
                "p": "3212.78",                       # avg Price
                "P": "3000",                          # total position
                "a": "3000",                          # available position
                "f": "0",                             # liquidation price
                "m": "13680.323",                     # portfolio margin
                "r": "-3.8819",                       # realised profit and loss (Pnl)
                "up": str(unrealized_pnl),            # unrealized profit and loss (unrealizedPnL)
                "pr": "-0.3589",                      # profit rate of current position
                "pv": "73579.09",                     # position value (USDT)
                "v": "5.00",                          # leverage
                "mt": "CROSS",                        # position type, only CROSS, ISOLATED later will support
                "mm": "0"                             # min margin
            }
        ]
        return mock_response

    def funding_info_event_for_websocket_update(self):
        return []

    def test_create_order_with_invalid_position_action_raises_value_error(self):
        self._simulate_trading_rules_initialized()

        with self.assertRaises(ValueError) as exception_context:
            asyncio.get_event_loop().run_until_complete(
                self.exchange._create_order(
                    trade_type=TradeType.BUY,
                    order_id="C1",
                    trading_pair=self.trading_pair,
                    amount=Decimal("1"),
                    order_type=OrderType.LIMIT,
                    price=Decimal("46000"),
                    position_action=PositionAction.NIL,
                ),
            )

        self.assertEqual(
            f"Invalid position action {PositionAction.NIL}. Must be one of {[PositionAction.OPEN, PositionAction.CLOSE]}",
            str(exception_context.exception)
        )

    def test_user_stream_update_for_new_order(self):
        self.exchange._set_current_timestamp(1640780000)
        self.exchange.start_tracking_order(
            order_id="11",
            exchange_order_id=str(self.expected_exchange_order_id),
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("1"),
        )
        order = self.exchange.in_flight_orders["11"]

        order_event = self.order_event_for_new_order_websocket_update(order=order)

        mock_queue = AsyncMock()
        event_messages = [order_event, asyncio.CancelledError]
        mock_queue.get.side_effect = event_messages
        self.exchange._user_stream_tracker._user_stream = mock_queue

        try:
            self.async_run_with_timeout(self.exchange._user_stream_event_listener())
        except asyncio.CancelledError:
            pass

        self.assertEqual(1, len(self.buy_order_created_logger.event_log))
        self.assertTrue(order.is_open)

    def test_user_stream_balance_update(self):
        client_config_map = ClientConfigAdapter(ClientConfigMap())
        connector = HashkeyPerpetualDerivative(
            client_config_map=client_config_map,
            hashkey_perpetual_api_key=self.api_key,
            hashkey_perpetual_secret_key=self.api_secret,
            trading_pairs=[self.trading_pair],
        )
        connector._set_current_timestamp(1640780000)

        balance_event = self.balance_event_websocket_update

        mock_queue = AsyncMock()
        mock_queue.get.side_effect = [balance_event, asyncio.CancelledError]
        self.exchange._user_stream_tracker._user_stream = mock_queue

        try:
            self.async_run_with_timeout(self.exchange._user_stream_event_listener())
        except asyncio.CancelledError:
            pass

        self.assertEqual(Decimal("474960.65"), self.exchange.available_balances[self.quote_asset])
        self.assertEqual(Decimal("574960.65"), self.exchange.get_balance(self.quote_asset))

    def test_user_stream_position_update(self):
        client_config_map = ClientConfigAdapter(ClientConfigMap())
        connector = HashkeyPerpetualDerivative(
            client_config_map=client_config_map,
            hashkey_perpetual_api_key=self.api_key,
            hashkey_perpetual_secret_key=self.api_secret,
            trading_pairs=[self.trading_pair],
        )
        connector._set_current_timestamp(1640780000)

        position_event = self.position_event_websocket_update

        mock_queue = AsyncMock()
        mock_queue.get.side_effect = [position_event, asyncio.CancelledError]
        self.exchange._user_stream_tracker._user_stream = mock_queue
        self._simulate_trading_rules_initialized()
        pos_key = self.exchange._perpetual_trading.position_key(self.trading_pair, PositionSide.LONG)
        self.exchange.account_positions[pos_key] = Position(
            trading_pair=self.trading_pair,
            position_side=PositionSide.LONG,
            unrealized_pnl=Decimal('1'),
            entry_price=Decimal('1'),
            amount=Decimal('1'),
            leverage=Decimal('1'),
        )
        amount_precision = Decimal(self.exchange.trading_rules[self.trading_pair].min_base_amount_increment)
        try:
            asyncio.get_event_loop().run_until_complete(self.exchange._user_stream_event_listener())
        except asyncio.CancelledError:
            pass

        self.assertEqual(len(self.exchange.account_positions), 1)
        pos = list(self.exchange.account_positions.values())[0]
        self.assertEqual(pos.amount, 3000 * amount_precision)

    def test_user_stream_remove_position_update(self):
        client_config_map = ClientConfigAdapter(ClientConfigMap())
        connector = HashkeyPerpetualDerivative(
            client_config_map=client_config_map,
            hashkey_perpetual_api_key=self.api_key,
            hashkey_perpetual_secret_key=self.api_secret,
            trading_pairs=[self.trading_pair],
        )
        connector._set_current_timestamp(1640780000)

        position_event = self.position_event_websocket_update_zero
        self._simulate_trading_rules_initialized()
        pos_key = self.exchange._perpetual_trading.position_key(self.trading_pair, PositionSide.LONG)
        self.exchange.account_positions[pos_key] = Position(
            trading_pair=self.trading_pair,
            position_side=PositionSide.LONG,
            unrealized_pnl=Decimal('1'),
            entry_price=Decimal('1'),
            amount=Decimal('1'),
            leverage=Decimal('1'),
        )
        mock_queue = AsyncMock()
        mock_queue.get.side_effect = [position_event, asyncio.CancelledError]
        self.exchange._user_stream_tracker._user_stream = mock_queue

        try:
            asyncio.get_event_loop().run_until_complete(self.exchange._user_stream_event_listener())
        except asyncio.CancelledError:
            pass
        self.assertEqual(len(self.exchange.account_positions), 0)

    def test_supported_position_modes(self):
        client_config_map = ClientConfigAdapter(ClientConfigMap())
        linear_connector = HashkeyPerpetualDerivative(
            client_config_map=client_config_map,
            hashkey_perpetual_api_key=self.api_key,
            hashkey_perpetual_secret_key=self.api_secret,
            trading_pairs=[self.trading_pair],
        )

        expected_result = [PositionMode.HEDGE]
        self.assertEqual(expected_result, linear_connector.supported_position_modes())

    def test_get_buy_and_sell_collateral_tokens(self):
        self._simulate_trading_rules_initialized()
        buy_collateral_token = self.exchange.get_buy_collateral_token(self.trading_pair)
        sell_collateral_token = self.exchange.get_sell_collateral_token(self.trading_pair)
        self.assertEqual(self.quote_asset, buy_collateral_token)
        self.assertEqual(self.quote_asset, sell_collateral_token)

    @aioresponses()
    def test_resolving_trading_pair_symbol_duplicates_on_trading_rules_update_first_is_good(self, mock_api):
        self.exchange._set_current_timestamp(1000)

        url = self.trading_rules_url

        response = self.trading_rules_request_mock_response
        results = response["contracts"]
        duplicate = deepcopy(results[0])
        duplicate["name"] = f"{self.exchange_trading_pair}_12345"
        results.append(duplicate)
        mock_api.get(url, body=json.dumps(response))

        self.async_run_with_timeout(coroutine=self.exchange._update_trading_rules())

        self.assertEqual(1, len(self.exchange.trading_rules))
        self.assertIn(self.trading_pair, self.exchange.trading_rules)
        self.assertEqual(repr(self.expected_trading_rule), repr(self.exchange.trading_rules[self.trading_pair]))

    @aioresponses()
    def test_resolving_trading_pair_symbol_duplicates_on_trading_rules_update_second_is_good(self, mock_api):
        self.exchange._set_current_timestamp(1000)

        url = self.trading_rules_url

        response = self.trading_rules_request_mock_response
        results = response["contracts"]
        duplicate = deepcopy(results[0])
        duplicate["name"] = f"{self.exchange_trading_pair}_12345"
        results.insert(0, duplicate)
        mock_api.get(url, body=json.dumps(response))

        self.async_run_with_timeout(coroutine=self.exchange._update_trading_rules())

        self.assertEqual(1, len(self.exchange.trading_rules))
        self.assertIn(self.trading_pair, self.exchange.trading_rules)
        self.assertEqual(repr(self.expected_trading_rule), repr(self.exchange.trading_rules[self.trading_pair]))

    @aioresponses()
    def test_update_trading_rules_ignores_rule_with_error(self, mock_api):
        # Response only contains valid trading rule
        pass

    @aioresponses()
    def test_cancel_lost_order_raises_failure_event_when_request_fails(self, mock_api):
        request_sent_event = asyncio.Event()
        self.exchange._set_current_timestamp(1640780000)

        self.exchange.start_tracking_order(
            order_id="11",
            exchange_order_id="4",
            trading_pair=self.trading_pair,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("100"),
            order_type=OrderType.LIMIT,
        )

        self.assertIn("11", self.exchange.in_flight_orders)
        order = self.exchange.in_flight_orders["11"]

        for _ in range(self.exchange._order_tracker._lost_order_count_limit + 1):
            self.async_run_with_timeout(
                self.exchange._order_tracker.process_order_not_found(client_order_id=order.client_order_id))

        self.assertNotIn(order.client_order_id, self.exchange.in_flight_orders)

        url = self.configure_erroneous_cancelation_response(
            order=order,
            mock_api=mock_api,
            callback=lambda *args, **kwargs: request_sent_event.set())

        self.async_run_with_timeout(self.exchange._cancel_lost_orders())
        self.async_run_with_timeout(request_sent_event.wait())

        cancel_request = self._all_executed_requests(mock_api, url)[0]
        self.validate_auth_credentials_present(cancel_request)
        self.validate_order_cancelation_request(
            order=order,
            request_call=cancel_request)

        self.assertIn(order.client_order_id, self.exchange._order_tracker.lost_orders)
        self.assertEqual(0, len(self.order_cancelled_logger.event_log))

    @aioresponses()
    def test_user_stream_update_for_order_full_fill(self, mock_api):
        self.exchange._set_current_timestamp(1640780000)
        leverage = 2
        self.exchange._perpetual_trading.set_leverage(self.trading_pair, leverage)
        self.exchange.start_tracking_order(
            order_id="OID1",
            exchange_order_id="EOID1",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("1"),
            position_action=PositionAction.OPEN,
        )
        order = self.exchange.in_flight_orders["OID1"]

        order_event = self.order_event_for_full_fill_websocket_update(order=order)
        trade_event = self.trade_event_for_full_fill_websocket_update(order=order)
        mock_queue = AsyncMock()
        event_messages = []
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

        fill_event = self.order_filled_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp, fill_event.timestamp)
        self.assertEqual(order.client_order_id, fill_event.order_id)
        self.assertEqual(order.trading_pair, fill_event.trading_pair)
        self.assertEqual(order.trade_type, fill_event.trade_type)
        self.assertEqual(order.order_type, fill_event.order_type)
        self.assertEqual(order.price, fill_event.price)
        self.assertEqual(order.amount, fill_event.amount)
        expected_fee = self.expected_fill_fee
        self.assertEqual(expected_fee, fill_event.trade_fee)
        self.assertEqual(leverage, fill_event.leverage)
        self.assertEqual(PositionAction.OPEN.value, fill_event.position)

        buy_event = self.buy_order_completed_logger.event_log[0]
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

        self.assertTrue(
            self.is_logged(
                "INFO",
                f"BUY order {order.client_order_id} completely filled."
            )
        )

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

    def _order_cancelation_request_successful_mock_response(self, order: InFlightOrder) -> Any:
        self._simulate_trading_rules_initialized()
        return {
            "time": "1724071031231",
            "updateTime": "1724071031274",
            "orderId": order.exchange_order_id,
            "clientOrderId": order.client_order_id,
            "symbol": self.exchange_trading_pair,
            "price": "5050",
            "leverage": order.leverage,
            "origQty": str(self.exchange.get_quantity_of_contracts(self.trading_pair, order.amount)),
            "executedQty": str(self.exchange.get_quantity_of_contracts(self.trading_pair, order.amount)),
            "avgPrice": "5000",
            "marginLocked": "0",
            "type": "LIMIT",
            "side": "BUY_OPEN",
            "timeInForce": "IOC",
            "status": "CANCELED",
            "priceType": "INPUT",
            "isLiquidationOrder": False,
            "indexPrice": "0",
            "liquidationType": ""
        }

    def _order_status_request_completely_filled_mock_response(self, order: InFlightOrder) -> Any:
        self._simulate_trading_rules_initialized()
        return {
            "time": "1724071031231",
            "updateTime": "1724071031274",
            "orderId": order.exchange_order_id,
            "clientOrderId": order.client_order_id,
            "symbol": self.exchange_trading_pair,
            "price": "5050",
            "leverage": order.leverage,
            "origQty": str(self.exchange.get_quantity_of_contracts(self.trading_pair, order.amount)),
            "executedQty": str(self.exchange.get_quantity_of_contracts(self.trading_pair, order.amount)),
            "avgPrice": "5000",
            "marginLocked": "0",
            "type": "LIMIT",
            "side": "BUY_OPEN",
            "timeInForce": "IOC",
            "status": "FILLED",
            "priceType": "INPUT",
            "isLiquidationOrder": False,
            "indexPrice": "0",
            "liquidationType": ""
        }

    def _order_status_request_canceled_mock_response(self, order: InFlightOrder) -> Any:
        resp = self._order_cancelation_request_successful_mock_response(order)
        return resp

    def _order_status_request_open_mock_response(self, order: InFlightOrder) -> Any:
        resp = self._order_status_request_completely_filled_mock_response(order)
        resp["status"] = "NEW"
        return resp

    def _order_status_request_partially_filled_mock_response(self, order: InFlightOrder) -> Any:
        resp = self._order_status_request_completely_filled_mock_response(order)
        resp["status"] = "PARTIALLY_FILLED"
        return resp

    def _order_fills_request_partial_fill_mock_response(self, order: InFlightOrder):
        resp = self._order_status_request_completely_filled_mock_response(order)
        resp["status"] = "PARTIALLY_FILLED"
        return resp

    def _order_fills_request_full_fill_mock_response(self, order: InFlightOrder):
        return [
            {
                "time": "1723728772839",
                "tradeId": "1753158447036129024",
                "orderId": order.exchange_order_id,
                "symbol": self.exchange_trading_pair,
                "price": str(order.price),
                "quantity": str(self.exchange.get_quantity_of_contracts(self.trading_pair, order.amount)),
                "commissionAsset": order.quote_asset,
                "commission": "0",
                "makerRebate": "0",
                "type": "LIMIT",
                "side": f"{'BUY' if order.trade_type == TradeType.BUY else 'SELL'}_{order.position.value}",
                "realizedPnl": "0",
                "isMaker": True
            },
        ]

    @aioresponses()
    def test_start_network_update_trading_rules(self, mock_api):
        self.exchange._set_current_timestamp(1000)

        url = self.trading_rules_url

        response = self.trading_rules_request_mock_response
        results = response["contracts"]
        duplicate = deepcopy(results[0])
        duplicate["name"] = f"{self.exchange_trading_pair}_12345"
        results.append(duplicate)
        mock_api.get(url, body=json.dumps(response))

        self.async_run_with_timeout(self.exchange.start_network())

        self.assertEqual(1, len(self.exchange.trading_rules))
        self.assertIn(self.trading_pair, self.exchange.trading_rules)
        self.assertEqual(repr(self.expected_trading_rule), repr(self.exchange.trading_rules[self.trading_pair]))

    def place_limit_maker_buy_order(
        self,
        amount: Decimal = Decimal("100"),
        price: Decimal = Decimal("10_000"),
        position_action: PositionAction = PositionAction.OPEN,
    ):
        order_id = self.exchange.buy(
            trading_pair=self.trading_pair,
            amount=amount,
            order_type=OrderType.LIMIT_MAKER,
            price=price,
            position_action=position_action,
        )
        return order_id

    @aioresponses()
    def test_create_buy_limit_maker_order_successfully(self, mock_api):
        """Open long position"""
        self._simulate_trading_rules_initialized()
        request_sent_event = asyncio.Event()
        self.exchange._set_current_timestamp(1640780000)

        url = self.order_creation_url

        creation_response = self.limit_maker_order_creation_request_successful_mock_response

        mock_api.post(url,
                      body=json.dumps(creation_response),
                      callback=lambda *args, **kwargs: request_sent_event.set())

        leverage = 2
        self.exchange._perpetual_trading.set_leverage(self.trading_pair, leverage)
        order_id = self.place_limit_maker_buy_order()
        self.async_run_with_timeout(request_sent_event.wait())

        order_request = self._all_executed_requests(mock_api, url)[0]
        self.validate_auth_credentials_present(order_request)
        self.assertIn(order_id, self.exchange.in_flight_orders)
        self.validate_order_creation_request(
            order=self.exchange.in_flight_orders[order_id],
            request_call=order_request)

        create_event = self.buy_order_created_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp,
                         create_event.timestamp)
        self.assertEqual(self.trading_pair, create_event.trading_pair)
        self.assertEqual(OrderType.LIMIT_MAKER, create_event.type)
        self.assertEqual(Decimal("100"), create_event.amount)
        self.assertEqual(Decimal("10000"), create_event.price)
        self.assertEqual(order_id, create_event.order_id)
        self.assertEqual(str(self.expected_exchange_order_id),
                         create_event.exchange_order_id)
        self.assertEqual(leverage, create_event.leverage)
        self.assertEqual(PositionAction.OPEN.value, create_event.position)

        self.assertTrue(
            self.is_logged(
                "INFO",
                f"Created {OrderType.LIMIT_MAKER.name} {TradeType.BUY.name} order {order_id} for "
                f"{Decimal('100.000000')} to {PositionAction.OPEN.name} a {self.trading_pair} position "
                f"at {Decimal('10000.0000')}."
            )
        )

    @aioresponses()
    def test_update_position_mode(
            self,
            mock_api: aioresponses,
    ):
        self._simulate_trading_rules_initialized()
        get_position_url = web_utils.rest_url(
            path_url=CONSTANTS.POSITION_INFORMATION_URL
        )
        regex_get_position_url = re.compile(f"^{get_position_url}")
        response = [
            {
                "symbol": "BTCUSDT-PERPETUAL",
                "side": "SHORT",
                "avgPrice": "3366.01",
                "position": "200030",
                "available": "200030",
                "leverage": "10",
                "lastPrice": "2598.09",
                "positionValue": "673303.6",
                "liquidationPrice": "9553.83",
                "margin": "105389.3738",
                "marginRate": "",
                "unrealizedPnL": "152047.5663",
                "profitRate": "1.4427",
                "realizedPnL": "-215.2107",
                "minMargin": "38059.0138"
            },
        ]
        mock_api.get(regex_get_position_url, body=json.dumps(response))
        self.async_run_with_timeout(self.exchange._update_positions())

        pos_key = self.exchange._perpetual_trading.position_key(self.trading_pair, PositionSide.SHORT)
        position: Position = self.exchange.account_positions[pos_key]
        self.assertEqual(self.trading_pair, position.trading_pair)
        self.assertEqual(PositionSide.SHORT, position.position_side)

        get_position_url = web_utils.rest_url(
            path_url=CONSTANTS.POSITION_INFORMATION_URL
        )
        regex_get_position_url = re.compile(f"^{get_position_url}")
        response = [
            {
                "symbol": "BTCUSDT-PERPETUAL",
                "side": "LONG",
                "avgPrice": "3366.01",
                "position": "200030",
                "available": "200030",
                "leverage": "10",
                "lastPrice": "2598.09",
                "positionValue": "673303.6",
                "liquidationPrice": "9553.83",
                "margin": "105389.3738",
                "marginRate": "",
                "unrealizedPnL": "152047.5663",
                "profitRate": "1.4427",
                "realizedPnL": "-215.2107",
                "minMargin": "38059.0138"
            },
        ]
        mock_api.get(regex_get_position_url, body=json.dumps(response))
        self.async_run_with_timeout(self.exchange._update_positions())
        position: Position = self.exchange.account_positions[f"{self.trading_pair}LONG"]
        self.assertEqual(self.trading_pair, position.trading_pair)
        self.assertEqual(PositionSide.LONG, position.position_side)

    @aioresponses()
    def test_set_position_mode_success(self, mock_api):
        # There's only HEDGE position mode
        pass

    @aioresponses()
    def test_set_position_mode_failure(self, mock_api):
        # There's only HEDGE position mode
        pass

    @aioresponses()
    def test_listen_for_funding_info_update_initializes_funding_info(self, mock_api: aioresponses):
        mock_api.get(self.funding_info_url, body=json.dumps(self.funding_rate_mock_response), repeat=True)
        mock_api.get(self.mark_price_url, body=json.dumps(self.mark_price_mock_response), repeat=True)
        mock_api.get(self.index_price_url, body=json.dumps(self.index_price_mock_response), repeat=True)

        try:
            self.async_run_with_timeout(self.exchange._listen_for_funding_info())
        except asyncio.TimeoutError:
            pass

        funding_info: FundingInfo = self.exchange.get_funding_info(self.trading_pair)

        self.assertEqual(self.trading_pair, funding_info.trading_pair)
        self.assertEqual(self.target_funding_info_index_price, funding_info.index_price)
        self.assertEqual(self.target_funding_info_mark_price, funding_info.mark_price)
        self.assertEqual(
            self.target_funding_info_next_funding_utc_timestamp, funding_info.next_funding_utc_timestamp
        )
        self.assertEqual(self.target_funding_info_rate, funding_info.rate)

    @aioresponses()
    def test_listen_for_funding_info_update_updates_funding_info(self, mock_api: aioresponses):
        # Hashkey global not support update funding info by websocket
        pass
