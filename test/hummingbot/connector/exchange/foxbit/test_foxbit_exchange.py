import asyncio
import json
import re
from decimal import Decimal
from typing import Any, Callable, Dict, List, Optional, Tuple
from unittest.mock import AsyncMock, patch

from aioresponses import aioresponses
from aioresponses.core import RequestCall
from bidict import bidict

from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.connector.exchange.foxbit import (
    foxbit_constants as CONSTANTS,
    foxbit_utils as utils,
    foxbit_web_utils as web_utils,
)
from hummingbot.connector.exchange.foxbit.foxbit_exchange import FoxbitExchange
from hummingbot.connector.test_support.exchange_connector_test import AbstractExchangeConnectorTests
from hummingbot.connector.test_support.network_mocking_assistant import NetworkMockingAssistant
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder
from hummingbot.core.data_type.trade_fee import DeductedFromReturnsTradeFee, TokenAmount, TradeFeeBase


class FoxbitExchangeTests(AbstractExchangeConnectorTests.ExchangeConnectorTests):

    def setUp(self) -> None:
        super().setUp()
        self.mocking_assistant = NetworkMockingAssistant()
        mapping = bidict()
        mapping[1] = self.trading_pair
        self.exchange._trading_pair_instrument_id_map = mapping

    @property
    def all_symbols_url(self):
        return web_utils.public_rest_url(path_url=CONSTANTS.EXCHANGE_INFO_PATH_URL, domain=self.exchange._domain)

    @property
    def latest_prices_url(self):
        url = web_utils.public_rest_url(path_url=CONSTANTS.TICKER_PRICE_CHANGE_PATH_URL, domain=self.exchange._domain)
        url = f"{url}?symbol={self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset)}"
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
        url = web_utils.private_rest_url(CONSTANTS.ORDER_PATH_URL, domain=self.exchange._domain)
        return url

    @property
    def balance_url(self):
        url = web_utils.private_rest_url(CONSTANTS.ACCOUNTS_PATH_URL, domain=self.exchange._domain)
        return url

    @property
    def all_symbols_request_mock_response(self):
        return {
            "data": [
                {
                    "symbol": '{}{}'.format(self.base_asset.lower(), self.quote_asset.lower()),
                    "quantity_min": "0.00002",
                    "quantity_increment": "0.00001",
                    "price_min": "1.0",
                    "price_increment": "0.0001",
                    "base": {
                        "symbol": self.base_asset.lower(),
                        "name": "Bitcoin",
                        "type": "CRYPTO"
                    },
                    "quote": {
                        "symbol": self.quote_asset.lower(),
                        "name": "Bitcoin",
                        "type": "CRYPTO"
                    }
                }
            ]
        }

    @property
    def latest_prices_request_mock_response(self):
        return {
            "OMSId": 1,
            "InstrumentId": 1,
            "BestBid": 0.00,
            "BestOffer": 0.00,
            "LastTradedPx": 0.00,
            "LastTradedQty": 0.00,
            "LastTradeTime": 635872032000000000,
            "SessionOpen": 0.00,
            "SessionHigh": 0.00,
            "SessionLow": 0.00,
            "SessionClose": 0.00,
            "Volume": 0.00,
            "CurrentDayVolume": 0.00,
            "CurrentDayNumTrades": 0,
            "CurrentDayPxChange": 0.0,
            "Rolling24HrVolume": 0.0,
            "Rolling24NumTrades": 0.0,
            "Rolling24HrPxChange": 0.0,
            "TimeStamp": 635872032000000000,
        }

    @property
    def all_symbols_including_invalid_pair_mock_response(self) -> Tuple[str, Any]:
        response = {
            "timezone": "UTC",
            "serverTime": 1639598493658,
            "rateLimits": [],
            "exchangeFilters": [],
            "symbols": [
                {
                    "symbol": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
                    "status": "TRADING",
                    "baseAsset": self.base_asset,
                    "baseAssetPrecision": 8,
                    "quoteAsset": self.quote_asset,
                    "quotePrecision": 8,
                    "quoteAssetPrecision": 8,
                    "baseCommissionPrecision": 8,
                    "quoteCommissionPrecision": 8,
                    "orderTypes": [
                        "LIMIT",
                        "LIMIT_MAKER",
                        "MARKET",
                        "STOP_LOSS_LIMIT",
                        "TAKE_PROFIT_LIMIT"
                    ],
                    "icebergAllowed": True,
                    "ocoAllowed": True,
                    "quoteOrderQtyMarketAllowed": True,
                    "isSpotTradingAllowed": True,
                    "isMarginTradingAllowed": True,
                    "filters": [],
                    "permissions": [
                        "MARGIN"
                    ]
                },
                {
                    "symbol": self.exchange_symbol_for_tokens("INVALID", "PAIR"),
                    "status": "TRADING",
                    "baseAsset": "INVALID",
                    "baseAssetPrecision": 8,
                    "quoteAsset": "PAIR",
                    "quotePrecision": 8,
                    "quoteAssetPrecision": 8,
                    "baseCommissionPrecision": 8,
                    "quoteCommissionPrecision": 8,
                    "orderTypes": [
                        "LIMIT",
                        "LIMIT_MAKER",
                        "MARKET",
                        "STOP_LOSS_LIMIT",
                        "TAKE_PROFIT_LIMIT"
                    ],
                    "icebergAllowed": True,
                    "ocoAllowed": True,
                    "quoteOrderQtyMarketAllowed": True,
                    "isSpotTradingAllowed": True,
                    "isMarginTradingAllowed": True,
                    "filters": [],
                    "permissions": [
                        "MARGIN"
                    ]
                },
            ]
        }

        return "INVALID-PAIR", response

    @property
    def network_status_request_successful_mock_response(self):
        return {}

    @property
    def trading_rules_request_mock_response(self):
        return {
            "data": [
                {
                    "symbol": '{}{}'.format(self.base_asset, self.quote_asset),
                    "quantity_min": "0.00002",
                    "quantity_increment": "0.00001",
                    "price_min": "1.0",
                    "price_increment": "0.0001",
                    "base": {
                        "symbol": self.base_asset,
                        "name": "Bitcoin",
                        "type": "CRYPTO"
                    },
                    "quote": {
                        "symbol": self.quote_asset,
                        "name": "Bitcoin",
                        "type": "CRYPTO"
                    }
                }
            ]
        }

    @property
    def trading_rules_request_erroneous_mock_response(self):
        return {
            "data": [
                {
                    "symbol": '{}'.format(self.base_asset),
                    "quantity_min": "0.00002",
                    "quantity_increment": "0.00001",
                    "price_min": "1.0",
                    "price_increment": "0.0001",
                    "base": {
                        "symbol": self.base_asset,
                        "name": "Bitcoin",
                        "type": "CRYPTO"
                    },
                    "quote": {
                        "symbol": self.quote_asset,
                        "name": "Bitcoin",
                        "type": "CRYPTO"
                    }
                }
            ]
        }

    @property
    def order_creation_request_successful_mock_response(self):
        return {
            "id": self.expected_exchange_order_id,
            "sn": "OKMAKSDHRVVREK"
        }

    @property
    def balance_request_mock_response_for_base_and_quote(self):
        return {
            "data": [
                {
                    "currency_symbol": self.base_asset,
                    "balance": "15.0",
                    "balance_available": "10.0",
                    "balance_locked": "0.0"
                },
                {
                    "currency_symbol": self.quote_asset,
                    "balance": "2000.0",
                    "balance_available": "2000.0",
                    "balance_locked": "0.0"
                }
            ]
        }

    @property
    def balance_request_mock_response_only_base(self):
        return {
            "data": [
                {
                    "currency_symbol": self.base_asset,
                    "balance": "15.0",
                    "balance_available": "10.0",
                    "balance_locked": "0.0"
                }
            ]
        }

    @property
    def balance_event_websocket_update(self):
        return {
            "n": "AccountPositionEvent",
            "o": '{"ProductSymbol":"' + self.base_asset + '","Hold":"5.0","Amount": "15.0"}'
        }

    @property
    def expected_latest_price(self):
        return 9999.9

    @property
    def expected_supported_order_types(self):
        return [OrderType.LIMIT, OrderType.MARKET]

    @property
    def expected_trading_rule(self):
        return TradingRule(
            trading_pair=self.trading_pair,
            min_order_size=Decimal(self.trading_rules_request_mock_response["data"][0]["quantity_min"]),
            min_price_increment=Decimal(self.trading_rules_request_mock_response["data"][0]["price_increment"]),
            min_base_amount_increment=Decimal(self.trading_rules_request_mock_response["data"][0]["quantity_increment"]),
            min_notional_size=Decimal(self.trading_rules_request_mock_response["data"][0]["price_min"]),
        )

    @property
    def expected_logged_error_for_erroneous_trading_rule(self):
        erroneous_rule = self.trading_rules_request_erroneous_mock_response["data"][0]["symbol"]
        return f"Error parsing the trading pair rule {erroneous_rule}. Skipping."

    @property
    def expected_exchange_order_id(self):
        return 28

    @property
    def is_cancel_request_executed_synchronously_by_server(self) -> bool:
        return True

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
        return Decimal("0.5")

    @property
    def expected_fill_fee(self) -> TradeFeeBase:
        return DeductedFromReturnsTradeFee(
            percent_token=self.quote_asset,
            flat_fees=[TokenAmount(token=self.quote_asset, amount=Decimal("30"))])

    @property
    def expected_fill_trade_id(self) -> str:
        return 30000

    def exchange_symbol_for_tokens(self, base_token: str, quote_token: str) -> str:
        return f"{base_token}{quote_token}"

    def create_exchange_instance(self):
        client_config_map = ClientConfigAdapter(ClientConfigMap())
        return FoxbitExchange(
            client_config_map=client_config_map,
            foxbit_api_key="testAPIKey",
            foxbit_api_secret="testSecret",
            foxbit_user_id="testUserId",
            trading_pairs=[self.trading_pair],
        )

    def validate_auth_credentials_present(self, request_call: RequestCall):
        self._validate_auth_credentials_taking_parameters_from_argument(
            request_call_tuple=request_call,
            params=request_call.kwargs["params"] or request_call.kwargs["data"]
        )

    def validate_order_creation_request(self, order: InFlightOrder, request_call: RequestCall):
        request_data = eval(request_call.kwargs["data"])
        self.assertEqual(self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset), request_data["market_symbol"])
        self.assertEqual(order.trade_type.name.upper(), request_data["side"])
        self.assertEqual(FoxbitExchange.foxbit_order_type(OrderType.LIMIT), request_data["type"])
        self.assertEqual(Decimal("100"), Decimal(request_data["quantity"]))
        self.assertEqual(Decimal("10000"), Decimal(request_data["price"]))
        self.assertEqual(order.client_order_id, request_data["client_order_id"])

    def validate_order_cancelation_request(self, order: InFlightOrder, request_call: RequestCall):
        request_data = eval(request_call.kwargs["data"])
        self.assertEqual(order.client_order_id, request_data["client_order_id"])

    def validate_order_status_request(self, order: InFlightOrder, request_call: RequestCall):
        request_params = request_call.kwargs["params"]
        self.assertEqual(self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
                         request_params["symbol"])
        self.assertEqual(order.client_order_id, request_params["origClientOrderId"])

    def validate_trades_request(self, order: InFlightOrder, request_call: RequestCall):
        request_params = request_call.kwargs["params"]
        self.assertEqual(self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
                         request_params["symbol"])
        self.assertEqual(order.exchange_order_id, str(request_params["orderId"]))

    def configure_successful_cancelation_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        url = web_utils.private_rest_url(CONSTANTS.CANCEL_ORDER_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        response = self._order_cancelation_request_successful_mock_response(order=order)
        mock_api.put(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_erroneous_cancelation_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        url = web_utils.private_rest_url(CONSTANTS.CANCEL_ORDER_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        mock_api.put(regex_url, status=400, callback=callback)
        return url

    def configure_order_not_found_error_cancelation_response(
        self,
        order: InFlightOrder,
        mock_api: aioresponses,
        callback: Optional[Callable] = lambda *args, **kwargs: None,
    ) -> str:
        url = web_utils.private_rest_url(CONSTANTS.CANCEL_ORDER_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        response = {"code": -2011, "msg": "Unknown order sent."}
        mock_api.put(regex_url, status=400, body=json.dumps(response), callback=callback)
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
        url = web_utils.private_rest_url(CONSTANTS.GET_ORDER_BY_CLIENT_ID.format(order.client_order_id))
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        response = self._order_status_request_completely_filled_mock_response(order=order)
        mock_api.get(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_canceled_order_status_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        url = web_utils.private_rest_url(CONSTANTS.GET_ORDER_BY_ID.format(order.exchange_order_id))
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        response = self._order_status_request_canceled_mock_response(order=order)
        mock_api.get(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_erroneous_http_fill_trade_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        # Trade fills not requested during status update in this connector
        pass

    def configure_open_order_status_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        """
        :return: the URL configured
        """
        url = web_utils.private_rest_url(CONSTANTS.GET_ORDER_BY_ID.format(order.exchange_order_id))
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        response = self._order_status_request_open_mock_response(order=order)
        mock_api.get(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_http_error_order_status_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        url = web_utils.private_rest_url(CONSTANTS.GET_ORDER_BY_ID.format(order.exchange_order_id))
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        mock_api.get(regex_url, status=401, callback=callback)
        return url

    def configure_partially_filled_order_status_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        url = web_utils.private_rest_url(CONSTANTS.GET_ORDER_BY_ID.format(order.exchange_order_id))
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        response = self._order_status_request_partially_filled_mock_response(order=order)
        mock_api.get(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_order_not_found_error_order_status_response(
        self, order: InFlightOrder, mock_api: aioresponses, callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> List[str]:
        url = web_utils.private_rest_url(CONSTANTS.ORDER_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        response = {"code": -2013, "msg": "Order does not exist."}
        mock_api.get(regex_url, body=json.dumps(response), status=400, callback=callback)
        return [url]

    def configure_partial_fill_trade_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        url = web_utils.private_rest_url(path_url=CONSTANTS.MY_TRADES_PATH_URL)
        regex_url = re.compile(url + r"\?.*")
        response = self._order_fills_request_partial_fill_mock_response(order=order)
        mock_api.get(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_full_fill_trade_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        url = web_utils.private_rest_url(path_url=CONSTANTS.MY_TRADES_PATH_URL)
        regex_url = re.compile(url + r"\?.*")
        response = self._order_fills_request_full_fill_mock_response(order=order)
        mock_api.get(regex_url, body=json.dumps(response), callback=callback)
        return url

    def order_event_for_new_order_websocket_update(self, order: InFlightOrder):
        return {
            "id": order.exchange_order_id,
            "sn": "OKMAKSDHRVVREK",
            "client_order_id": order.client_order_id,
            "market_symbol": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
            "side": "BUY",
            "type": "LIMIT",
            "state": "ACTIVE",
            "price": str(order.price),
            "price_avg": str(order.price),
            "quantity": str(order.amount),
            "quantity_executed": "0.0",
            "instant_amount": "0.0",
            "instant_amount_executed": "0.0",
            "created_at": "2022-09-08T17:06:32.999Z",
            "trades_count": "0",
            "remark": "A remarkable note for the order."
        }

    def order_event_for_canceled_order_websocket_update(self, order: InFlightOrder):
        return {
            "id": order.exchange_order_id,
            "sn": "OKMAKSDHRVVREK",
            "client_order_id": order.client_order_id,
            "market_symbol": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
            "side": "BUY",
            "type": "LIMIT",
            "state": "CANCELLED",
            "price": str(order.price),
            "price_avg": str(order.price),
            "quantity": str(order.amount),
            "quantity_executed": "0.0",
            "instant_amount": "0.0",
            "instant_amount_executed": "0.0",
            "created_at": "2022-09-08T17:06:32.999Z",
            "trades_count": "0",
            "remark": "A remarkable note for the order."
        }

    def order_event_for_full_fill_websocket_update(self, order: InFlightOrder):
        return {
            "n": "OrderStateEvent",
            "o": "{'Side': 'Buy'," +
            "'OrderId': " + order.client_order_id + "1'," +
            "'Price': " + str(order.price) + "," +
            "'Quantity': " + str(order.amount) + "," +
            "'OrderType': 'Limit'," +
            "'ClientOrderId': " + order.client_order_id + "," +
            "'OrderState': 1," +
            "'OrigQuantity': " + str(order.amount) + "," +
            "'QuantityExecuted': " + str(order.amount) + "," +
            "'AvgPrice': " + str(order.price) + "," +
            "'ChangeReason': 'Fill'," +
            "'Instrument': 1}"
        }

    def trade_event_for_full_fill_websocket_update(self, order: InFlightOrder):
        return {
            "n": "OrderTradeEvent",
            "o": "{'InstrumentId': 1," +
            "'OrderType': 'Limit'," +
            "'OrderId': " + order.client_order_id + "1," +
            "'ClientOrderId': " + order.client_order_id + "," +
            "'Price': " + str(order.price) + "," +
            "'Value': " + str(order.price) + "," +
            "'Quantity': " + str(order.amount) + "," +
            "'RemainingQuantity': 0.00," +
            "'Side': 'Buy'," +
            "'TradeId': 1," +
            "'TradeTimeMS': 1640780000}"
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

    @aioresponses()
    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_all_trading_pairs(self, mock_api, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()
        ixm_config = {
            'm': 0,
            'i': 1,
            'n': 'GetInstruments',
            'o': '[{"OMSId":1,"InstrumentId":1,"Symbol":"COINALPHA/HBOT","Product1":1,"Product1Symbol":"COINALPHA","Product2":2,"Product2Symbol":"HBOT","InstrumentType":"Standard","VenueInstrumentId":1,"VenueId":1,"SortIndex":0,"SessionStatus":"Running","PreviousSessionStatus":"Paused","SessionStatusDateTime":"2020-07-11T01:27:02.851Z","SelfTradePrevention":true,"QuantityIncrement":1e-8,"PriceIncrement":0.01,"MinimumQuantity":1e-8,"MinimumPrice":0.01,"VenueSymbol":"BTC/BRL","IsDisable":false,"MasterDataId":0,"PriceCollarThreshold":0,"PriceCollarPercent":0,"PriceCollarEnabled":false,"PriceFloorLimit":0,"PriceFloorLimitEnabled":false,"PriceCeilingLimit":0,"PriceCeilingLimitEnabled":false,"CreateWithMarketRunning":true,"AllowOnlyMarketMakerCounterParty":false}]'
        }
        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value,
            message=json.dumps(ixm_config))

        ixm_response = {
            'm': 0,
            'i': 1,
            'n':
            'SubscribeLevel1',
            'o': '{"OMSId":1,"InstrumentId":1,"MarketId":"coinalphahbot","BestBid":145899,"BestOffer":145901,"LastTradedPx":145899,"LastTradedQty":0.0009,"LastTradeTime":1662663925,"SessionOpen":145899,"SessionHigh":145901,"SessionLow":145899,"SessionClose":145901,"Volume":0.0009,"CurrentDayVolume":0.008,"CurrentDayNumTrades":17,"CurrentDayPxChange":2,"Rolling24HrVolume":0.008,"Rolling24NumTrades":17,"Rolling24HrPxChange":0.0014,"TimeStamp":1662736972}'
        }
        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value,
            message=json.dumps(ixm_response))

        self.exchange._set_trading_pair_symbol_map(None)
        url = self.all_symbols_url

        response = self.all_symbols_request_mock_response
        mock_api.get(url, body=json.dumps(response))

        all_trading_pairs = self.async_run_with_timeout(coroutine=self.exchange.all_trading_pairs())

        self.assertEqual(1, len(all_trading_pairs))

    @aioresponses()
    @patch("hummingbot.connector.time_synchronizer.TimeSynchronizer._current_seconds_counter")
    def test_update_time_synchronizer_successfully(self, mock_api, seconds_counter_mock):
        request_sent_event = asyncio.Event()
        seconds_counter_mock.side_effect = [0, 0, 0]

        self.exchange._time_synchronizer.clear_time_offset_ms_samples()
        url = web_utils.private_rest_url(CONSTANTS.SERVER_TIME_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        response = {"timestamp": 1640000003000}

        mock_api.get(regex_url,
                     body=json.dumps(response),
                     callback=lambda *args, **kwargs: request_sent_event.set())

        self.async_run_with_timeout(self.exchange._update_time_synchronizer())

        self.assertEqual(response["timestamp"] * 1e-3, self.exchange._time_synchronizer.time())

    @aioresponses()
    def test_update_time_synchronizer_failure_is_logged(self, mock_api):
        request_sent_event = asyncio.Event()

        url = web_utils.private_rest_url(CONSTANTS.SERVER_TIME_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        response = {"code": -1121, "msg": "Dummy error"}

        mock_api.get(regex_url,
                     body=json.dumps(response),
                     callback=lambda *args, **kwargs: request_sent_event.set())

        get_error = False

        try:
            self.async_run_with_timeout(self.exchange._update_time_synchronizer())
            get_error = True
        except Exception:
            get_error = True

        self.assertTrue(get_error)

    @aioresponses()
    def test_update_time_synchronizer_raises_cancelled_error(self, mock_api):
        url = web_utils.private_rest_url(CONSTANTS.SERVER_TIME_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_api.get(regex_url,
                     exception=asyncio.CancelledError)

        self.assertRaises(
            asyncio.CancelledError,
            self.async_run_with_timeout, self.exchange._update_time_synchronizer())

    @aioresponses()
    def test_update_order_fills_from_trades_triggers_filled_event(self, mock_api):
        self.exchange._set_current_timestamp(1640780000)
        self.exchange._last_poll_timestamp = 0

        self.exchange.start_tracking_order(
            order_id="OID1",
            exchange_order_id="100234",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("1"),
        )
        order = self.exchange.in_flight_orders["OID1"]

        url = '{}{}{}'.format(web_utils.private_rest_url(CONSTANTS.MY_TRADES_PATH_URL), 'market_symbol=', self.trading_pair)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        trade_fill = {
            "data": {
                "id": 28457,
                "sn": "TC5JZVW2LLJ3IW",
                "order_id": int(order.exchange_order_id),
                "market_symbol": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
                "side": "BUY",
                "price": "9999",
                "quantity": "1",
                "fee": "10.10",
                "fee_currency_symbol": self.quote_asset,
                "created_at": "2021-02-15T22:06:32.999Z"
            }
        }

        trade_fill_non_tracked_order = {
            "data": {
                "id": 3000,
                "sn": "AB5JQAW9TLJKJ0",
                "order_id": int(order.exchange_order_id),
                "market_symbol": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
                "side": "BUY",
                "price": "9999",
                "quantity": "1",
                "fee": "10.10",
                "fee_currency_symbol": self.quote_asset,
                "created_at": "2021-02-15T22:06:33.999Z"
            }
        }

        mock_response = [trade_fill, trade_fill_non_tracked_order]
        mock_api.get(regex_url, body=json.dumps(mock_response))

        self.exchange.add_exchange_order_ids_from_market_recorder(
            {str(trade_fill_non_tracked_order['data']["order_id"]): "OID99"})

        self.async_run_with_timeout(self.exchange._update_order_fills_from_trades())

        request = self._all_executed_requests(mock_api, web_utils.private_rest_url(CONSTANTS.MY_TRADES_PATH_URL))[0]
        self.validate_auth_credentials_present(request)
        request_params = request.kwargs["params"]
        self.assertEqual(self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset), request_params["market_symbol"])

    @aioresponses()
    def test_update_order_fills_request_parameters(self, mock_api):
        self.exchange._set_current_timestamp(1640780000)
        self.exchange._last_poll_timestamp = 0

        url = '{}{}{}'.format(web_utils.private_rest_url(CONSTANTS.MY_TRADES_PATH_URL), 'market_symbol=', self.trading_pair)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_response = []
        mock_api.get(regex_url, body=json.dumps(mock_response))

        self.async_run_with_timeout(self.exchange._update_order_fills_from_trades())

        request = self._all_executed_requests(mock_api, web_utils.private_rest_url(CONSTANTS.MY_TRADES_PATH_URL))[0]
        self.validate_auth_credentials_present(request)
        request_params = request.kwargs["params"]
        self.assertEqual(self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset), request_params["market_symbol"])

    @aioresponses()
    def test_update_order_fills_from_trades_with_repeated_fill_triggers_only_one_event(self, mock_api):
        self.exchange._set_current_timestamp(1640780000)
        self.exchange._last_poll_timestamp = 0

        url = '{}{}{}'.format(web_utils.private_rest_url(CONSTANTS.MY_TRADES_PATH_URL), 'market_symbol=', self.trading_pair)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        trade_fill_non_tracked_order = {
            "data": {
                "id": 3000,
                "sn": "AB5JQAW9TLJKJ0",
                "order_id": 9999,
                "market_symbol": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
                "side": "BUY",
                "price": "9999",
                "quantity": "1",
                "fee": "10.10",
                "fee_currency_symbol": self.quote_asset,
                "created_at": "2021-02-15T22:06:33.999Z"
            }
        }

        mock_response = [trade_fill_non_tracked_order, trade_fill_non_tracked_order]
        mock_api.get(regex_url, body=json.dumps(mock_response))

        self.exchange.add_exchange_order_ids_from_market_recorder(
            {str(trade_fill_non_tracked_order['data']["order_id"]): "OID99"})

        self.async_run_with_timeout(self.exchange._update_order_fills_from_trades())

        request = self._all_executed_requests(mock_api, web_utils.private_rest_url(CONSTANTS.MY_TRADES_PATH_URL))[0]
        self.validate_auth_credentials_present(request)
        request_params = request.kwargs["params"]
        self.assertEqual(self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset), request_params["market_symbol"])

    @aioresponses()
    def test_update_order_status_when_failed(self, mock_api):
        self.exchange._set_current_timestamp(1640780000)
        self.exchange._last_poll_timestamp = 0

        self.exchange.start_tracking_order(
            order_id="OID1",
            exchange_order_id="100234",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("1"),
        )
        order = self.exchange.in_flight_orders["OID1"]

        url = web_utils.private_rest_url(CONSTANTS.GET_ORDER_BY_ID.format(order.exchange_order_id))
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        order_status = {
            "id": order.exchange_order_id,
            "sn": "OKMAKSDHRVVREK",
            "client_order_id": order.client_order_id,
            "market_symbol": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
            "side": "BUY",
            "type": "LIMIT",
            "state": "CANCELED",
            "price": str(order.price),
            "price_avg": str(order.price),
            "quantity": str(order.amount),
            "quantity_executed": "0.0",
            "instant_amount": "0.0",
            "instant_amount_executed": "0.0",
            "created_at": "2022-09-08T17:06:32.999Z",
            "trades_count": "1",
            "remark": "A remarkable note for the order."
        }

        mock_response = order_status
        mock_api.get(regex_url, body=json.dumps(mock_response))

        self.async_run_with_timeout(self.exchange._update_order_status())

        request = self._all_executed_requests(mock_api, web_utils.private_rest_url(CONSTANTS.GET_ORDER_BY_ID.format(order.exchange_order_id)))
        self.assertEqual([], request)

    @aioresponses()
    def test_cancel_order_raises_failure_event_when_request_fails(self, mock_api):
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

        url = self.configure_erroneous_cancelation_response(
            order=order,
            mock_api=mock_api,
            callback=lambda *args, **kwargs: request_sent_event.set())

        self.exchange.cancel(trading_pair=self.trading_pair, client_order_id="11")
        self.async_run_with_timeout(request_sent_event.wait())

        cancel_request = self._all_executed_requests(mock_api, url)[0]
        self.validate_auth_credentials_present(cancel_request)
        self.validate_order_cancelation_request(
            order=order,
            request_call=cancel_request)

        self.assertEqual(0, len(self.order_cancelled_logger.event_log))
        self.assertTrue(any(log.msg.startswith(f"Failed to cancel order {order.client_order_id}")
                            for log in self.log_records))

    def test_client_order_id_on_order(self):
        self.exchange._set_current_timestamp(1640780000)

        result = self.exchange.buy(
            trading_pair=self.trading_pair,
            amount=Decimal("1"),
            order_type=OrderType.LIMIT,
            price=Decimal("2"),
        )
        expected_client_order_id = utils.get_client_order_id(
            is_buy=True,
        )

        self.assertEqual(result[:12], expected_client_order_id[:12])
        self.assertEqual(result[:2], self.exchange.client_order_id_prefix)
        self.assertLess(len(expected_client_order_id), self.exchange.client_order_id_max_length)

        result = self.exchange.sell(
            trading_pair=self.trading_pair,
            amount=Decimal("1"),
            order_type=OrderType.LIMIT,
            price=Decimal("2"),
        )
        expected_client_order_id = utils.get_client_order_id(
            is_buy=False,
        )

        self.assertEqual(result[:12], expected_client_order_id[:12])

    @aioresponses()
    def test_create_order(self, mock_api):
        self._simulate_trading_rules_initialized()
        _order = self.async_run_with_timeout(self.exchange._create_order(TradeType.BUY,
                                                                         '551100',
                                                                         self.trading_pair,
                                                                         Decimal(1.01),
                                                                         OrderType.LIMIT,
                                                                         Decimal(22354.01)))
        self.assertIsNone(_order)

    @aioresponses()
    def test_create_limit_buy_order_raises_error(self, mock_api):
        self._simulate_trading_rules_initialized()
        try:
            self.async_run_with_timeout(self.exchange._create_order(TradeType.BUY,
                                                                    '551100',
                                                                    self.trading_pair,
                                                                    Decimal(1.01),
                                                                    OrderType.LIMIT,
                                                                    Decimal(22354.01)))
        except Exception as err:
            self.assertEqual('', err.args[0])

    @aioresponses()
    def test_create_limit_sell_order_raises_error(self, mock_api):
        self._simulate_trading_rules_initialized()
        try:
            self.async_run_with_timeout(self.exchange._create_order(TradeType.SELL,
                                                                    '551100',
                                                                    self.trading_pair,
                                                                    Decimal(1.01),
                                                                    OrderType.LIMIT,
                                                                    Decimal(22354.01)))
        except Exception as err:
            self.assertEqual('', err.args[0])

    def test_initial_status_dict(self):
        self.exchange._set_trading_pair_symbol_map(None)

        status_dict = self.exchange.status_dict

        expected_initial_dict = {
            "symbols_mapping_initialized": False,
            "instruments_mapping_initialized": True,
            "order_books_initialized": False,
            "account_balance": False,
            "trading_rule_initialized": False
        }

        self.assertEqual(expected_initial_dict, status_dict)
        self.assertFalse(self.exchange.ready)

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_get_last_trade_prices(self, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()
        ixm_response = {
            'm': 0,
            'i': 1,
            'n':
            'SubscribeLevel1',
            'o': '{"OMSId":1,"InstrumentId":1,"MarketId":"coinalphahbot","BestBid":145899,"BestOffer":145901,"LastTradedPx":145899,"LastTradedQty":0.0009,"LastTradeTime":1662663925,"SessionOpen":145899,"SessionHigh":145901,"SessionLow":145899,"SessionClose":145901,"Volume":0.0009,"CurrentDayVolume":0.008,"CurrentDayNumTrades":17,"CurrentDayPxChange":2,"Rolling24HrVolume":0.008,"Rolling24NumTrades":17,"Rolling24HrPxChange":0.0014,"TimeStamp":1662736972}'
        }
        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value,
            message=json.dumps(ixm_response))

        expected_value = 145899.0
        ret_value = self.async_run_with_timeout(self.exchange._get_last_traded_price(self.trading_pair))

        self.assertEqual(expected_value, ret_value)

    def _validate_auth_credentials_taking_parameters_from_argument(self,
                                                                   request_call_tuple: RequestCall,
                                                                   params: Dict[str, Any]):
        request_headers = request_call_tuple.kwargs["headers"]
        self.assertIn("X-FB-ACCESS-SIGNATURE", request_headers)
        self.assertEqual("testAPIKey", request_headers["X-FB-ACCESS-KEY"])

    def _order_cancelation_request_successful_mock_response(self, order: InFlightOrder) -> Any:
        return {
            "data": [
                {
                    "sn": "OKMAKSDHRVVREK",
                    "id": "21"
                }
            ]
        }

    def _order_status_request_completely_filled_mock_response(self, order: InFlightOrder) -> Any:
        return {
            "id": order.exchange_order_id,
            "sn": "OKMAKSDHRVVREK",
            "client_order_id": order.client_order_id,
            "market_symbol": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
            "side": "BUY",
            "type": "LIMIT",
            "state": "FILLED",
            "price": str(order.price),
            "price_avg": str(order.price),
            "quantity": str(order.amount),
            "quantity_executed": str(order.amount),
            "instant_amount": "0.0",
            "instant_amount_executed": "0.0",
            "created_at": "2022-09-08T17:06:32.999Z",
            "trades_count": "3",
            "remark": "A remarkable note for the order."
        }

    def _order_status_request_canceled_mock_response(self, order: InFlightOrder) -> Any:
        return {
            "id": order.exchange_order_id,
            "sn": "OKMAKSDHRVVREK",
            "client_order_id": order.client_order_id,
            "market_symbol": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
            "side": "BUY",
            "type": "LIMIT",
            "state": "CANCELED",
            "price": str(order.price),
            "price_avg": str(order.price),
            "quantity": str(order.amount),
            "quantity_executed": "0.0",
            "instant_amount": "0.0",
            "instant_amount_executed": "0.0",
            "created_at": "2022-09-08T17:06:32.999Z",
            "trades_count": "1",
            "remark": "A remarkable note for the order."
        }

    def _order_status_request_open_mock_response(self, order: InFlightOrder) -> Any:
        return {
            "id": order.exchange_order_id,
            "sn": "OKMAKSDHRVVREK",
            "client_order_id": order.client_order_id,
            "market_symbol": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
            "side": "BUY",
            "type": "LIMIT",
            "state": "ACTIVE",
            "price": str(order.price),
            "price_avg": str(order.price),
            "quantity": str(order.amount),
            "quantity_executed": "0.0",
            "instant_amount": "0.0",
            "instant_amount_executed": "0.0",
            "created_at": "2022-09-08T17:06:32.999Z",
            "trades_count": "0",
            "remark": "A remarkable note for the order."
        }

    def _order_status_request_partially_filled_mock_response(self, order: InFlightOrder) -> Any:
        return {
            "id": order.exchange_order_id,
            "sn": "OKMAKSDHRVVREK",
            "client_order_id": order.client_order_id,
            "market_symbol": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
            "side": "BUY",
            "type": "LIMIT",
            "state": "PARTIALLY_FILLED",
            "price": str(order.price),
            "price_avg": str(order.price),
            "quantity": str(order.amount),
            "quantity_executed": str(order.amount / 2),
            "instant_amount": "0.0",
            "instant_amount_executed": "0.0",
            "created_at": "2022-09-08T17:06:32.999Z",
            "trades_count": "2",
        }

    def _order_fills_request_full_fill_mock_response(self, order: InFlightOrder):
        return {
            "n": "OrderTradeEvent",
            "o": "{'InstrumentId': 1," +
            "'OrderType': 'Limit'," +
            "'OrderId': " + order.client_order_id + "1," +
            "'ClientOrderId': " + order.client_order_id + "," +
            "'Price': " + str(order.price) + "," +
            "'Value': " + str(order.price) + "," +
            "'Quantity': " + str(order.amount) + "," +
            "'RemainingQuantity': 0.00," +
            "'Side': 'Buy'," +
            "'TradeId': 1," +
            "'TradeTimeMS': 1640780000}"
        }

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_exchange_properties_and_commons(self, ws_connect_mock):
        self.assertEqual(CONSTANTS.EXCHANGE_INFO_PATH_URL, self.exchange.trading_rules_request_path)
        self.assertEqual(CONSTANTS.EXCHANGE_INFO_PATH_URL, self.exchange.trading_pairs_request_path)
        self.assertEqual(CONSTANTS.PING_PATH_URL, self.exchange.check_network_request_path)
        self.assertTrue(self.exchange.is_cancel_request_in_exchange_synchronous)
        self.assertTrue(self.exchange.is_trading_required)
        self.assertEqual('1', self.exchange.convert_from_exchange_instrument_id('1'))
        self.assertEqual('1', self.exchange.convert_to_exchange_instrument_id('1'))
        self.assertEqual('MARKET', self.exchange.foxbit_order_type(OrderType.MARKET))
        try:
            self.exchange.foxbit_order_type(OrderType.LIMIT_MAKER)
        except Exception as err:
            self.assertEqual('Order type not supported by Foxbit.', err.args[0])

        self.assertEqual(OrderType.MARKET, self.exchange.to_hb_order_type('MARKET'))
        self.assertEqual([OrderType.LIMIT, OrderType.MARKET], self.exchange.supported_order_types())
        self.assertTrue(self.exchange.trading_pair_instrument_id_map_ready)

        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()
        ixm_config = {
            'm': 0,
            'i': 1,
            'n': 'GetInstruments',
            'o': '[{"OMSId":1,"InstrumentId":1,"Symbol":"COINALPHA/HBOT","Product1":1,"Product1Symbol":"COINALPHA","Product2":2,"Product2Symbol":"HBOT","InstrumentType":"Standard","VenueInstrumentId":1,"VenueId":1,"SortIndex":0,"SessionStatus":"Running","PreviousSessionStatus":"Paused","SessionStatusDateTime":"2020-07-11T01:27:02.851Z","SelfTradePrevention":true,"QuantityIncrement":1e-8,"PriceIncrement":0.01,"MinimumQuantity":1e-8,"MinimumPrice":0.01,"VenueSymbol":"BTC/BRL","IsDisable":false,"MasterDataId":0,"PriceCollarThreshold":0,"PriceCollarPercent":0,"PriceCollarEnabled":false,"PriceFloorLimit":0,"PriceFloorLimitEnabled":false,"PriceCeilingLimit":0,"PriceCeilingLimitEnabled":false,"CreateWithMarketRunning":true,"AllowOnlyMarketMakerCounterParty":false}]'
        }
        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value,
            message=json.dumps(ixm_config))
        _currentTP = self.async_run_with_timeout(self.exchange.trading_pair_instrument_id_map())
        self.assertIsNotNone(_currentTP)
        self.assertEqual(self.trading_pair, _currentTP[1])
        _currentTP = self.async_run_with_timeout(self.exchange.exchange_instrument_id_associated_to_pair('COINALPHA-HBOT'))
        self.assertEqual(1, _currentTP)

        self.assertIsNotNone(self.exchange.get_fee('COINALPHA', 'BOT', OrderType.MARKET, TradeType.BUY, 1.0, 22500.011, False))

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
    def test_user_stream_update_for_order_full_fill(self, mock_api):
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

    def test_user_stream_raises_cancel_exception(self):
        pass

    def test_user_stream_logs_errors(self):
        pass

    @aioresponses()
    def test_lost_order_included_in_order_fills_update_and_not_in_order_status_update(self, mock_api):
        pass

    def test_lost_order_removed_after_cancel_status_user_event_received(self):
        pass

    @aioresponses()
    def test_lost_order_user_stream_full_fill_events_are_processed(self, mock_api):
        pass
