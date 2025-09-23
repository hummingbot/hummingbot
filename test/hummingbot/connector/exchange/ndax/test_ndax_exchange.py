import json
import re
import time
from decimal import Decimal
from typing import Any, Callable, Dict, List, Optional, Tuple

from aioresponses import aioresponses
from aioresponses.core import RequestCall

from hummingbot.connector.exchange.ndax import ndax_constants as CONSTANTS, ndax_web_utils as web_utils
from hummingbot.connector.exchange.ndax.ndax_exchange import NdaxExchange
from hummingbot.connector.test_support.exchange_connector_test import AbstractExchangeConnectorTests
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder
from hummingbot.core.data_type.trade_fee import DeductedFromReturnsTradeFee, TradeFeeBase


class NdaxExchangeTests(AbstractExchangeConnectorTests.ExchangeConnectorTests):

    maxDiff = None

    @property
    def all_symbols_url(self):
        return f"{web_utils.public_rest_url(path_url=CONSTANTS.MARKETS_URL, domain=self.exchange._domain)}?OMSId=1"

    @property
    def latest_prices_url(self):
        symbol = self.exchange_trading_pair
        url = web_utils.public_rest_url(path_url=CONSTANTS.TICKER_PATH_URL.format(symbol), domain=self.exchange._domain)
        return url

    @property
    def network_status_url(self):
        url = web_utils.public_rest_url(CONSTANTS.PING_PATH_URL, domain=self.exchange._domain)
        return url

    @property
    def trading_rules_url(self):
        url = f"{web_utils.private_rest_url(CONSTANTS.MARKETS_URL, domain=self.exchange._domain)}?OMSId=1"
        return url

    @property
    def order_creation_url(self):
        url = web_utils.private_rest_url(CONSTANTS.SEND_ORDER_PATH_URL, domain=self.exchange._domain)
        return url

    @property
    def balance_url(self):
        url = web_utils.private_rest_url(CONSTANTS.ACCOUNT_POSITION_PATH_URL, domain=self.exchange._domain)
        return url

    @property
    def all_symbols_request_mock_response(self):
        return [
            {
                "InstrumentId": 1,
                "Product1Symbol": self.base_asset,
                "Product2Symbol": self.quote_asset,
                "Product1": 1234,
                "Product2": 5678,
                "SessionStatus": "Running",
            }
        ]

    @property
    def latest_prices_request_mock_response(self):
        return {
            f"{self.base_asset}_{self.quote_asset}": {
                "base_id": 21794,
                "quote_id": 0,
                "last_price": 2211.00,
                "base_volume": 397.90000000000000000000000000,
                "quote_volume": 2650.7070000000000000000000000,
            }
        }

    @property
    def all_symbols_including_invalid_pair_mock_response(self) -> Tuple[str, Any]:
        response = [
            {
                "InstrumentId": 1,
                "Product1Symbol": self.base_asset,
                "Product2Symbol": self.quote_asset,
                "Product1": 1234,
                "Product2": 5678,
                "SessionStatus": "Running",
            },
            {
                "InstrumentId": 1,
                "Product1Symbol": "INVALID",
                "Product2Symbol": "PAIR",
                "Product1": 1234,
                "Product2": 5678,
                "SessionStatus": "Stopped",
            },
        ]

        return "INVALID-PAIR", response

    @property
    def network_status_request_successful_mock_response(self):
        return {"msg": "PONG"}

    @property
    def trading_rules_request_mock_response(self):
        return [
            {
                "Product1Symbol": self.base_asset,
                "Product2Symbol": self.quote_asset,
                "QuantityIncrement": 0.0000010000000000000000000000,
                "MinimumQuantity": 0.0001000000000000000000000000,
                "MinimumPrice": 15000.000000000000000000000000,
                "PriceIncrement": 0.0001,
            }
        ]

    @property
    def trading_rules_request_erroneous_mock_response(self):
        return [
            {
                "Product1Symbol": self.base_asset,
                "Product2Symbol": self.quote_asset,
            }
        ]

    @property
    def order_creation_request_successful_mock_response(self):
        return {"status": "Accepted", "errormsg": "", "OrderId": self.expected_exchange_order_id}

    @property
    def trading_fees_mock_response(self):
        return [
            {
                "currency_pair": self.exchange_trading_pair,
                "market": self.exchange_trading_pair,
                "fees": {"maker": "1.0000", "taker": "2.0000"},
            },
            {"currency_pair": "btcusd", "market": "btcusd", "fees": {"maker": "0.3000", "taker": "0.4000"}},
        ]

    @property
    def balance_request_mock_response_for_base_and_quote(self):
        return [
            {"ProductSymbol": self.base_asset, "Hold": "5.00", "Amount": "15.00"},
            {"ProductSymbol": self.quote_asset, "Hold": "0.00", "Amount": "2000.00"},
        ]

    @property
    def balance_request_mock_response_only_base(self):
        return [{"ProductSymbol": self.base_asset, "Hold": "5.00", "Amount": "15.00"}]

    @property
    def balance_event_websocket_update(self):
        raise NotImplementedError

    @property
    def expected_latest_price(self):
        return 2211.00

    @property
    def expected_supported_order_types(self):
        return [OrderType.MARKET, OrderType.LIMIT, OrderType.LIMIT_MAKER]

    @property
    def expected_trading_rule(self):
        return TradingRule(
            trading_pair=self.trading_pair,
            min_order_size=Decimal("1e-4"),
            min_price_increment=Decimal("1e-4"),
            min_base_amount_increment=Decimal("1e-6"),
            min_quote_amount_increment=Decimal("1e-56"),
            min_notional_size=Decimal("0"),
        )

    @property
    def expected_logged_error_for_erroneous_trading_rule(self):
        erroneous_rule = self.trading_rules_request_erroneous_mock_response[0]
        return f"Error parsing the trading pair rule: {erroneous_rule}. Skipping..."

    @property
    def expected_exchange_order_id(self):
        return 28

    @property
    def is_order_fill_http_update_included_in_status_update(self) -> bool:
        return False

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
        return self.exchange.get_fee(
            base_currency=self.base_asset,
            quote_currency=self.quote_asset,
            order_type=OrderType.LIMIT,
            order_side=TradeType.BUY,
            amount=Decimal("1"),
            price=Decimal("10000"),
        )

    @property
    def expected_fill_trade_id(self) -> str:
        return str(30000)

    def setUp(self) -> None:
        super().setUp()
        self.exchange._auth._token = "testToken"
        self.exchange._auth._token_expiration = time.time() + 3600
        self.exchange.authenticator._account_id = 1

    def exchange_symbol_for_tokens(self, base_token: str, quote_token: str) -> str:
        return f"{base_token.lower()}{quote_token.lower()}"

    def create_exchange_instance(self):
        return NdaxExchange(
            ndax_uid="0001",
            ndax_api_key="testAPIKey",
            ndax_secret_key="testSecret",
            ndax_account_name="testAccount",
            trading_pairs=[self.trading_pair],
        )

    def validate_auth_credentials_present(self, request_call: RequestCall):
        request_headers = request_call.kwargs["headers"]
        expected_headers = ["APToken", "Content-Type"]
        self.assertEqual("testToken", request_headers["APToken"])
        for header in expected_headers:
            self.assertIn(header, request_headers)

    def validate_order_creation_request(self, order: InFlightOrder, request_call: RequestCall):
        request_data = json.loads(request_call.kwargs["data"])
        self.assertEqual(Decimal("100"), Decimal(request_data["Quantity"]))
        self.assertEqual(Decimal("10000"), Decimal(request_data["LimitPrice"]))
        self.assertEqual(order.client_order_id, str(request_data["ClientOrderId"]))

    def validate_order_cancelation_request(self, order: InFlightOrder, request_call: RequestCall):
        request_data = json.loads(request_call.kwargs["data"])
        self.assertEqual(order.exchange_order_id, request_data["OrderId"])

    def validate_order_status_request(self, order: InFlightOrder, request_call: RequestCall):
        request_data = request_call.kwargs["params"]
        self.assertEqual("1", str(request_data["OMSId"]))
        self.assertEqual("1", str(request_data["AccountId"]))

    def validate_trades_request(self, order: InFlightOrder, request_call: RequestCall):
        request_data = request_call.kwargs["data"]
        self.assertEqual(order.client_order_id, str(request_data["client_order_id"]))

    def configure_successful_cancelation_response(
        self, order: InFlightOrder, mock_api: aioresponses, callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> str:
        url = web_utils.private_rest_url(CONSTANTS.CANCEL_ORDER_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        response = self._order_cancelation_request_successful_mock_response(order=order)
        mock_api.post(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_erroneous_cancelation_response(
        self, order: InFlightOrder, mock_api: aioresponses, callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> str:
        url = web_utils.private_rest_url(CONSTANTS.CANCEL_ORDER_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        mock_api.post(regex_url, status=400, callback=callback)
        return url

    def configure_order_not_found_error_cancelation_response(
        self, order: InFlightOrder, mock_api: aioresponses, callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> str:
        url = web_utils.private_rest_url(CONSTANTS.CANCEL_ORDER_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        response = self._get_error_response(104, "Resource Not Found")
        mock_api.post(regex_url, status=200, body=json.dumps(response), callback=callback)
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
    ) -> str:
        url = web_utils.private_rest_url(CONSTANTS.GET_ORDER_STATUS_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        response = self._order_status_request_completely_filled_mock_response(order=order)
        mock_api.get(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_canceled_order_status_response(
        self, order: InFlightOrder, mock_api: aioresponses, callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> str:
        url = web_utils.private_rest_url(CONSTANTS.GET_ORDER_STATUS_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        response = self._order_status_request_canceled_mock_response(order=order)

        # It's called twice, once during the _request_order_status call and once during _all_trade_updates_for_order
        # TODO: Refactor the code to avoid calling the same endpoint twice
        mock_api.get(regex_url, body=json.dumps(response), callback=callback)
        mock_api.get(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_erroneous_http_fill_trade_response(
        self, order: InFlightOrder, mock_api: aioresponses, callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> str:
        url = web_utils.private_rest_url(CONSTANTS.GET_ORDER_STATUS_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        mock_api.get(regex_url, status=400, callback=callback)
        return url

    def configure_open_order_status_response(
        self, order: InFlightOrder, mock_api: aioresponses, callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> str:
        """
        :return: the URL configured
        """
        url = web_utils.private_rest_url(CONSTANTS.GET_ORDER_STATUS_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        response = self._order_status_request_open_mock_response(order=order)
        mock_api.get(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_http_error_order_status_response(
        self, order: InFlightOrder, mock_api: aioresponses, callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> str:
        url = web_utils.private_rest_url(CONSTANTS.GET_ORDER_STATUS_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        mock_api.get(regex_url, status=401, callback=callback)
        return url

    def configure_partially_filled_order_status_response(
        self, order: InFlightOrder, mock_api: aioresponses, callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> str:
        url = web_utils.private_rest_url(CONSTANTS.GET_ORDER_STATUS_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        response = self._order_status_request_partially_filled_mock_response(order=order)
        mock_api.get(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_order_not_found_error_order_status_response(
        self, order: InFlightOrder, mock_api: aioresponses, callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> List[str]:
        url = web_utils.private_rest_url(CONSTANTS.GET_ORDER_STATUS_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        response = self._get_error_response(104, "Resource Not Found")
        mock_api.get(regex_url, status=400, body=json.dumps(response), callback=callback)
        return url

    def configure_partial_fill_trade_response(
        self, order: InFlightOrder, mock_api: aioresponses, callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> str:
        url = web_utils.private_rest_url(CONSTANTS.GET_ORDER_STATUS_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        response = self._order_fills_request_partial_fill_mock_response(order=order)
        mock_api.get(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_full_fill_trade_response(
        self, order: InFlightOrder, mock_api: aioresponses, callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> str:
        url = web_utils.private_rest_url(CONSTANTS.GET_TRADES_HISTORY_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        response = self._order_fills_request_full_fill_mock_response(order=order)
        mock_api.get(regex_url, body=json.dumps(response), callback=callback)
        return url

    def _configure_balance_response(
        self,
        response: Dict[str, Any],
        mock_api: aioresponses,
        callback: Optional[Callable] = lambda *args, **kwargs: None,
    ) -> str:

        url = self.balance_url
        mock_api.get(
            re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?")), body=json.dumps(response), callback=callback
        )
        return url

    def order_event_for_new_order_websocket_update(self, order: InFlightOrder):
        return {
            "m": 3,
            "i": 2,
            "n": CONSTANTS.ORDER_STATE_EVENT_ENDPOINT_NAME,
            "o": json.dumps(
                {
                    "Side": "Sell",
                    "OrderId": order.exchange_order_id,
                    "Price": 35000,
                    "Quantity": 1,
                    "Instrument": 1,
                    "Account": 4,
                    "OrderType": "Limit",
                    "ClientOrderId": order.client_order_id,
                    "OrderState": "Working",
                    "ReceiveTime": 0,
                    "OrigQuantity": 1,
                    "QuantityExecuted": 0,
                    "AvgPrice": 0,
                    "ChangeReason": "NewInputAccepted",
                }
            ),
        }

    def order_event_for_canceled_order_websocket_update(self, order: InFlightOrder):
        return {
            "m": 3,
            "i": 2,
            "n": CONSTANTS.ORDER_STATE_EVENT_ENDPOINT_NAME,
            "o": json.dumps(
                {
                    "Side": "Sell",
                    "OrderId": order.exchange_order_id,
                    "Price": 35000,
                    "Quantity": 1,
                    "Instrument": 1,
                    "Account": 4,
                    "OrderType": "Limit",
                    "ClientOrderId": order.client_order_id,
                    "OrderState": "Canceled",
                    "ReceiveTime": 0,
                    "OrigQuantity": 1,
                    "QuantityExecuted": 0,
                    "AvgPrice": 0,
                    "ChangeReason": "NewInputAccepted",
                }
            ),
        }

    def order_event_for_full_fill_websocket_update(self, order: InFlightOrder):
        return {
            "m": 3,
            "i": 2,
            "n": CONSTANTS.ORDER_STATE_EVENT_ENDPOINT_NAME,
            "o": json.dumps(
                {
                    "Side": "Sell",
                    "OrderId": order.exchange_order_id,
                    "Price": 35000,
                    "Quantity": str(order.amount),
                    "Instrument": 1,
                    "Account": 1,
                    "OrderType": "Limit",
                    "ClientOrderId": order.client_order_id,
                    "OrderState": "FullyExecuted",
                    "ReceiveTime": 0,
                    "OrigQuantity": 1,
                    "QuantityExecuted": 0,
                    "AvgPrice": 0,
                    "ChangeReason": "NewInputAccepted",
                }
            ),
        }

    def trade_event_for_full_fill_websocket_update(self, order: InFlightOrder):
        return {
            "m": 3,
            "i": 2,
            "n": CONSTANTS.ORDER_TRADE_EVENT_ENDPOINT_NAME,
            "o": json.dumps(
                {
                    "OMSId": 1,  # OMS Id [Integer]
                    "TradeId": 213,  # Trade Id [64-bit Integer]
                    "OrderId": int(order.exchange_order_id),  # Order Id [64-bit Integer]
                    "AccountId": 1,  # Your Account Id [Integer]
                    "ClientOrderId": order.client_order_id,  # Your client order id. [64-bit Integer]
                    "InstrumentId": 1,  # Instrument Id [Integer]
                    "Side": order.trade_type.name.capitalize(),  # [String] Values are "Buy", "Sell", "Short" (future)
                    "Quantity": str(order.amount),  # Quantity [Decimal]
                    "Price": str(order.price),  # Price [Decimal]
                    "Value": 0.95,  # Value [Decimal]
                    "TradeTime": 635978008210426109,  # TimeStamp in Microsoft ticks format
                    "ContraAcctId": 3,
                    #  The Counterparty of the trade. The counterparty is always
                    #  the clearing account. [Integer]
                    "OrderTradeRevision": 1,  # Usually 1
                    "Direction": "NoChange",  # "Uptick", "Downtick", "NoChange"
                }
            ),
        }

    def _order_cancelation_request_successful_mock_response(self, order: InFlightOrder) -> Any:
        return {
            "result": True,
            "errormsg": "",
            "errorcode": 0,
            "detail": "",
        }

    def _order_status_request_completely_filled_mock_response(self, order: InFlightOrder) -> Any:
        return {
            "Side": "Sell",
            "OrderId": order.exchange_order_id,
            "Price": str(order.price),
            "Quantity": str(order.amount),
            "DisplayQuantity": str(order.amount),
            "Instrument": 5,
            "Account": 528,
            "AccountName": "hbot",
            "OrderType": "Limit",
            "ClientOrderId": 0,
            "OrderState": "FullyExecuted",
            "ReceiveTime": 1627380780887,
            "ReceiveTimeTicks": 637629775808866338,
            "LastUpdatedTime": 1627380783860,
            "LastUpdatedTimeTicks": 637629775838598558,
            "OrigQuantity": 1.0000000000000000000000000000,
            "QuantityExecuted": 1.0000000000000000000000000000,
            "GrossValueExecuted": 41720.830000000000000000000000,
            "ExecutableValue": 0.0000000000000000000000000000,
            "AvgPrice": 41720.830000000000000000000000,
            "CounterPartyId": 0,
            "ChangeReason": "Trade",
            "OrigOrderId": order.client_order_id,
            "OrigClOrdId": order.client_order_id,
            "EnteredBy": 492,
            "UserName": "hbot",
            "IsQuote": False,
            "InsideAsk": 41720.830000000000000000000000,
            "InsideAskSize": 0.9329960000000000000000000000,
            "InsideBid": 41718.340000000000000000000000,
            "InsideBidSize": 0.0632560000000000000000000000,
            "LastTradePrice": 41720.830000000000000000000000,
            "RejectReason": "",
            "IsLockedIn": False,
            "CancelReason": "",
            "OrderFlag": "AddedToBook, RemovedFromBook",
            "UseMargin": False,
            "StopPrice": 0.0000000000000000000000000000,
            "PegPriceType": "Last",
            "PegOffset": 0.0000000000000000000000000000,
            "PegLimitOffset": 0.0000000000000000000000000000,
            "IpAddress": "103.6.151.12",
            "ClientOrderIdUuid": None,
            "OMSId": 1,
        }

    def _order_status_request_canceled_mock_response(self, order: InFlightOrder) -> Any:
        return {
            "Side": "Sell",
            "OrderId": order.exchange_order_id,
            "Price": str(order.price),
            "Quantity": str(order.amount),
            "DisplayQuantity": str(order.amount),
            "Instrument": 5,
            "Account": 528,
            "AccountName": "hbot",
            "OrderType": "Limit",
            "ClientOrderId": 0,
            "OrderState": "Canceled",
            "ReceiveTime": 1627380780887,
            "ReceiveTimeTicks": 637629775808866338,
            "LastUpdatedTime": 1627380783860,
            "LastUpdatedTimeTicks": 637629775838598558,
            "OrigQuantity": 1.0000000000000000000000000000,
            "QuantityExecuted": 1.0000000000000000000000000000,
            "GrossValueExecuted": 41720.830000000000000000000000,
            "ExecutableValue": 0.0000000000000000000000000000,
            "AvgPrice": 41720.830000000000000000000000,
            "CounterPartyId": 0,
            "ChangeReason": "Trade",
            "OrigOrderId": order.client_order_id,
            "OrigClOrdId": order.client_order_id,
            "EnteredBy": 492,
            "UserName": "hbot",
            "IsQuote": False,
            "InsideAsk": 41720.830000000000000000000000,
            "InsideAskSize": 0.9329960000000000000000000000,
            "InsideBid": 41718.340000000000000000000000,
            "InsideBidSize": 0.0632560000000000000000000000,
            "LastTradePrice": 41720.830000000000000000000000,
            "RejectReason": "",
            "IsLockedIn": False,
            "CancelReason": "",
            "OrderFlag": "AddedToBook, RemovedFromBook",
            "UseMargin": False,
            "StopPrice": 0.0000000000000000000000000000,
            "PegPriceType": "Last",
            "PegOffset": 0.0000000000000000000000000000,
            "PegLimitOffset": 0.0000000000000000000000000000,
            "IpAddress": "103.6.151.12",
            "ClientOrderIdUuid": None,
            "OMSId": 1,
        }

    def _order_status_request_open_mock_response(self, order: InFlightOrder) -> Any:
        return {
            "Side": "Sell",
            "OrderId": order.exchange_order_id,
            "Price": str(order.price),
            "Quantity": str(order.amount),
            "DisplayQuantity": str(order.amount),
            "Instrument": 5,
            "Account": 528,
            "AccountName": "hbot",
            "OrderType": "Limit",
            "ClientOrderId": 0,
            "OrderState": "Working",
            "ReceiveTime": 1627380780887,
            "ReceiveTimeTicks": 637629775808866338,
            "LastUpdatedTime": 1627380783860,
            "LastUpdatedTimeTicks": 637629775838598558,
            "OrigQuantity": 1.0000000000000000000000000000,
            "QuantityExecuted": 0.0000000000000000000000000000,
            "GrossValueExecuted": 41720.830000000000000000000000,
            "ExecutableValue": 0.0000000000000000000000000000,
            "AvgPrice": 41720.830000000000000000000000,
            "CounterPartyId": 0,
            "ChangeReason": "Trade",
            "OrigOrderId": order.client_order_id,
            "OrigClOrdId": order.client_order_id,
            "EnteredBy": 492,
            "UserName": "hbot",
            "IsQuote": False,
            "InsideAsk": 41720.830000000000000000000000,
            "InsideAskSize": 0.9329960000000000000000000000,
            "InsideBid": 41718.340000000000000000000000,
            "InsideBidSize": 0.0632560000000000000000000000,
            "LastTradePrice": 41720.830000000000000000000000,
            "RejectReason": "",
            "IsLockedIn": False,
            "CancelReason": "",
            "OrderFlag": "AddedToBook, RemovedFromBook",
            "UseMargin": False,
            "StopPrice": 0.0000000000000000000000000000,
            "PegPriceType": "Last",
            "PegOffset": 0.0000000000000000000000000000,
            "PegLimitOffset": 0.0000000000000000000000000000,
            "IpAddress": "103.6.151.12",
            "ClientOrderIdUuid": None,
            "OMSId": 1,
        }

    def _order_status_request_partially_filled_mock_response(self, order: InFlightOrder) -> Any:
        return {
            "Side": "Sell",
            "OrderId": order.exchange_order_id,
            "Price": str(order.price),
            "Quantity": str(order.amount),
            "DisplayQuantity": str(order.amount),
            "Instrument": 5,
            "Account": 528,
            "AccountName": "hbot",
            "OrderType": "Limit",
            "ClientOrderId": 0,
            "OrderState": "Working",
            "ReceiveTime": 1627380780887,
            "ReceiveTimeTicks": 637629775808866338,
            "LastUpdatedTime": 1627380783860,
            "LastUpdatedTimeTicks": 637629775838598558,
            "OrigQuantity": 1.0000000000000000000000000000,
            "QuantityExecuted": 1.0000000000000000000000000000,
            "GrossValueExecuted": 41720.830000000000000000000000,
            "ExecutableValue": 0.0000000000000000000000000000,
            "AvgPrice": 41720.830000000000000000000000,
            "CounterPartyId": 0,
            "ChangeReason": "Trade",
            "OrigOrderId": order.client_order_id,
            "OrigClOrdId": order.client_order_id,
            "EnteredBy": 492,
            "UserName": "hbot",
            "IsQuote": False,
            "InsideAsk": 41720.830000000000000000000000,
            "InsideAskSize": 0.9329960000000000000000000000,
            "InsideBid": 41718.340000000000000000000000,
            "InsideBidSize": 0.0632560000000000000000000000,
            "LastTradePrice": 41720.830000000000000000000000,
            "RejectReason": "",
            "IsLockedIn": False,
            "CancelReason": "",
            "OrderFlag": "AddedToBook, RemovedFromBook",
            "UseMargin": False,
            "StopPrice": 0.0000000000000000000000000000,
            "PegPriceType": "Last",
            "PegOffset": 0.0000000000000000000000000000,
            "PegLimitOffset": 0.0000000000000000000000000000,
            "IpAddress": "103.6.151.12",
            "ClientOrderIdUuid": None,
            "OMSId": 1,
        }

    def _order_fills_request_partial_fill_mock_response(self, order: InFlightOrder):
        return {
            "Side": "Sell",
            "OrderId": order.exchange_order_id,
            "Price": str(order.price),
            "Quantity": str(order.amount),
            "DisplayQuantity": str(order.amount),
            "Instrument": 5,
            "Account": 528,
            "AccountName": "hbot",
            "OrderType": "Limit",
            "ClientOrderId": 0,
            "OrderState": "FullyExecuted",
            "ReceiveTime": 1627380780887,
            "ReceiveTimeTicks": 637629775808866338,
            "LastUpdatedTime": 1627380783860,
            "LastUpdatedTimeTicks": 637629775838598558,
            "OrigQuantity": 1.0000000000000000000000000000,
            "QuantityExecuted": 1.0000000000000000000000000000,
            "GrossValueExecuted": 41720.830000000000000000000000,
            "ExecutableValue": 0.0000000000000000000000000000,
            "AvgPrice": 41720.830000000000000000000000,
            "CounterPartyId": 0,
            "ChangeReason": "Trade",
            "OrigOrderId": order.client_order_id,
            "OrigClOrdId": order.client_order_id,
            "EnteredBy": 492,
            "UserName": "hbot",
            "IsQuote": False,
            "InsideAsk": 41720.830000000000000000000000,
            "InsideAskSize": 0.9329960000000000000000000000,
            "InsideBid": 41718.340000000000000000000000,
            "InsideBidSize": 0.0632560000000000000000000000,
            "LastTradePrice": 41720.830000000000000000000000,
            "RejectReason": "",
            "IsLockedIn": False,
            "CancelReason": "",
            "OrderFlag": "AddedToBook, RemovedFromBook",
            "UseMargin": False,
            "StopPrice": 0.0000000000000000000000000000,
            "PegPriceType": "Last",
            "PegOffset": 0.0000000000000000000000000000,
            "PegLimitOffset": 0.0000000000000000000000000000,
            "IpAddress": "103.6.151.12",
            "ClientOrderIdUuid": None,
            "OMSId": 1,
        }

    def _order_fills_request_full_fill_mock_response(self, order: InFlightOrder):
        return [
            {
                "omsId": 1,
                "executionId": 0,
                "TradeId": 0,
                "orderId": order.exchange_order_id,
                "accountId": 1,
                "subAccountId": 0,
                "clientOrderId": order.client_order_id,
                "instrumentId": 0,
                "side": order.order_type.name.capitalize(),
                "Quantity": str(order.amount),
                "remainingQuantity": 0,
                "Price": str(order.price),
                "value": 0.0,
                "TradeTime": 0,
                "counterParty": 0,
                "orderTradeRevision": 0,
                "direction": 0,
                "isBlockTrade": False,
                "tradeTimeMS": 0,
                "fee": 0.0,
                "feeProductId": 0,
                "orderOriginator": 0,
            }
        ]

    def test_user_stream_balance_update(self):
        return {
            "Hold": 1,
            "Amount": 1,
            "ProductSymbol": "BTC",
        }

    def test_get_fee_default(self):
        expected_maker_fee = DeductedFromReturnsTradeFee(percent=self.exchange.estimate_fee_pct(True))
        maker_fee = self.exchange._get_fee(
            self.base_asset, self.quote_asset, OrderType.LIMIT, TradeType.BUY, 1, 2, is_maker=True
        )

        exptected_taker_fee = DeductedFromReturnsTradeFee(percent=self.exchange.estimate_fee_pct(False))
        taker_fee = self.exchange._get_fee(
            self.base_asset, self.quote_asset, OrderType.MARKET, TradeType.BUY, 1, 2, is_maker=False
        )

        self.assertEqual(expected_maker_fee, maker_fee)
        self.assertEqual(exptected_taker_fee, taker_fee)

    def _get_error_response(self, error_code, error_reason):
        return {"result": False, "errormsg": error_reason, "errorcode": error_code}
