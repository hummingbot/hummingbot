import hashlib
import hmac
import json
import re
from abc import ABC, abstractmethod
from decimal import Decimal
from typing import Any, Callable, Dict, List, Optional, Pattern, Tuple, Union

from aioresponses.core import RequestCall, aioresponses

from hummingbot.connector.test_support.exchange_connector_test import AbstractExchangeConnectorTests
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.connector.utilities.oms_connector import oms_connector_constants as CONSTANTS
from hummingbot.connector.utilities.oms_connector.oms_connector_auth import OMSConnectorAuth
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder
from hummingbot.core.data_type.trade_fee import AddedToCostTradeFee, TokenAmount, TradeFeeBase


class OMSExchangeTests:
    class ExchangeTests(AbstractExchangeConnectorTests.ExchangeConnectorTests, ABC):
        @classmethod
        def setUpClass(cls) -> None:
            super().setUpClass()
            cls.api_key = "someApiKey"
            cls.secret = "someSecret"
            cls.user_id = 20
            cls.time_mock = 1655283229.419752
            cls.nonce = str(int(cls.time_mock * 1e3))
            auth_concat = f"{cls.nonce}{cls.user_id}{cls.api_key}"
            cls.signature = hmac.new(
                key=cls.secret.encode("utf-8"),
                msg=auth_concat.encode("utf-8"),
                digestmod=hashlib.sha256,
            ).hexdigest()
            cls.user_name = "someUserName"
            cls.oms_id = 1
            cls.account_id = 3
            cls.pair_id = 1
            cls.base_asset = "COINALPHA"
            cls.base_id = 26
            cls.quote_asset = "HBOT"
            cls.quote_id = 2
            cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
            cls.exchange_trading_pair = f"{cls.base_asset}{cls.quote_asset}"

        def setUp(self) -> None:
            super().setUp()
            self.exchange._token_id_map[self.quote_id] = self.quote_asset
            self.exchange._token_id_map[self.base_id] = self.base_asset

        @property
        @abstractmethod
        def url_creator(self):
            raise NotImplementedError

        @property
        def all_symbols_url(self):
            url = self.url_creator.get_rest_url(path_url=CONSTANTS.REST_PRODUCTS_ENDPOINT)
            regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
            return regex_url

        @property
        def latest_prices_url(self) -> Pattern[str]:
            url = self.url_creator.get_rest_url(path_url=CONSTANTS.REST_GET_L1_ENDPOINT)
            regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
            return regex_url

        @property
        def network_status_url(self) -> Pattern[str]:
            url = self.url_creator.get_rest_url(path_url=CONSTANTS.REST_PING_ENDPOINT)
            regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
            return regex_url

        @property
        def trading_rules_url(self) -> Pattern[str]:
            url = self.url_creator.get_rest_url(path_url=CONSTANTS.REST_PRODUCTS_ENDPOINT)
            regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
            return regex_url

        @property
        def order_creation_url(self) -> str:
            url = self.url_creator.get_rest_url(path_url=CONSTANTS.REST_ORDER_CREATION_ENDPOINT)
            return url

        @property
        def balance_url(self) -> str:
            url = self.url_creator.get_rest_url(path_url=CONSTANTS.REST_ACC_POSITIONS_ENDPOINT)
            return url

        @property
        def all_symbols_request_mock_response(self) -> List[Dict[str, Any]]:
            return self.get_products_resp()

        @property
        def all_symbols_including_invalid_pair_mock_response(self) -> Tuple[str, List[Dict[str, Any]]]:
            resp = self.get_products_resp()
            resp[0]["IsDisable"] = True
            return self.trading_pair, resp

        @property
        def latest_prices_request_mock_response(self) -> Dict[str, Union[int, float]]:
            return {
                "AskOrderCt": 0,
                "AskQty": 1,
                "BestBid": 0.382882,
                "BestOffer": 0.38345,
                "BidOrderCt": 0,
                "BidQty": 0,
                "CurrentDayNotional": 0,
                "CurrentDayNumTrades": 0,
                "CurrentDayPxChange": 0,
                "CurrentDayVolume": 0,
                "InstrumentId": self.pair_id,
                "LastTradeTime": 0,
                "LastTradedPx": float(self.expected_latest_price),
                "LastTradedQty": 0,
                "OMSId": self.oms_id,
                "Rolling24HrNotional": 0,
                "Rolling24HrPxChange": 0,
                "Rolling24HrPxChangePercent": 0,
                "Rolling24HrVolume": 0,
                "Rolling24NumTrades": 0,
                "SessionClose": 0,
                "SessionHigh": 0,
                "SessionLow": 0,
                "SessionOpen": 0,
                "TimeStamp": "0",
                "Volume": 0,
            }

        @property
        def network_status_request_successful_mock_response(self) -> Dict[str, str]:
            return {"msg": "PONG"}

        @property
        def trading_rules_request_mock_response(self) -> List[Dict[str, Any]]:
            return self.get_products_resp()

        @property
        def trading_rules_request_erroneous_mock_response(self):
            resp = self.get_products_resp()
            resp[0].pop("MinimumQuantity")
            return resp

        def get_auth_success_response(self) -> Dict[str, Any]:
            auth_resp = {
                "Authenticated": True,
                "SessionToken": "0e8bbcbc-6ada-482a-a9b4-5d9218ada3f9",
                "User": {
                    "UserId": self.user_id,
                    "UserName": self.user_name,
                    "Email": "",
                    "EmailVerified": True,
                    "AccountId": self.account_id,
                    "OMSId": self.oms_id,
                    "Use2FA": False,
                },
                "Locked": False,
                "Requires2FA": False,
                "EnforceEnable2FA": False,
                "TwoFAType": None,
                "TwoFAToken": None,
                "errormsg": None,
            }
            return auth_resp

        @staticmethod
        def get_auth_failure_response() -> Dict[str, Any]:
            auth_resp = {
                "Authenticated": False,
                "EnforceEnable2FA": False,
                "Locked": False,
                "Requires2FA": False,
                "SessionToken": None,
                "TwoFAToken": None,
                "TwoFAType": None,
                "User": {
                    "AccountId": 0,
                    "Email": None,
                    "EmailVerified": False,
                    "OMSId": 0,
                    "Use2FA": False,
                    "UserId": 0,
                    "UserName": None,
                },
                "errormsg": "User api key not found",
            }
            return auth_resp

        def get_products_resp(self) -> List[Dict[str, Any]]:
            return [
                {
                    "AllowOnlyMarketMakerCounterParty": False,
                    "CreateWithMarketRunning": True,
                    "InstrumentId": self.pair_id,
                    "InstrumentType": "Standard",
                    "IsDisable": False,
                    "MasterDataId": 0,
                    "MinimumPrice": 0.9,
                    "MinimumQuantity": 0.01,
                    "OMSId": self.oms_id,
                    "OtcConvertSizeEnabled": False,
                    "OtcConvertSizeThreshold": 0.0,
                    "OtcTradesPublic": True,
                    "PreviousSessionStatus": "Stopped",
                    "PriceCeilingLimit": 0.0,
                    "PriceCeilingLimitEnabled": False,
                    "PriceCollarConvertToOtcAccountId": 0,
                    "PriceCollarConvertToOtcClientUserId": 0,
                    "PriceCollarConvertToOtcEnabled": False,
                    "PriceCollarConvertToOtcThreshold": 0.0,
                    "PriceCollarEnabled": False,
                    "PriceCollarIndexDifference": 0.0,
                    "PriceCollarPercent": 0.0,
                    "PriceCollarThreshold": 0.0,
                    "PriceFloorLimit": 0.0,
                    "PriceFloorLimitEnabled": False,
                    "PriceIncrement": 1e-05,
                    "PriceTier": 0,
                    "Product1": self.base_id,
                    "Product1Symbol": self.base_asset,
                    "Product2": self.quote_id,
                    "Product2Symbol": self.quote_asset,
                    "QuantityIncrement": 0.0001,
                    "SelfTradePrevention": True,
                    "SessionStatus": "Running",
                    "SessionStatusDateTime": "2022-05-23T17:11:16.422Z",
                    "SortIndex": 0,
                    "Symbol": self.exchange_trading_pair,
                    "VenueId": 1,
                    "VenueInstrumentId": 11,
                    "VenueSymbol": self.exchange_trading_pair,
                }
            ]

        @property
        def order_creation_request_successful_mock_response(self) -> Dict[str, Union[str, int]]:
            return {
                "status": "Accepted",
                "errormsg": "",
                "OrderId": self.expected_exchange_order_id,
            }

        @property
        def balance_request_mock_response_for_base_and_quote(self) -> List[Dict[str, Union[str, int]]]:
            return [
                self.get_mock_balance_base(),
                self.get_mock_balance_quote(),
            ]

        @property
        def balance_request_mock_response_only_base(self) -> List[Dict[str, Union[str, int]]]:
            return [self.get_mock_balance_base()]

        def get_mock_balance_base(self) -> Dict[str, Union[str, int]]:
            return {
                "AccountId": self.account_id,
                "Amount": 15,
                "Hold": 5,
                "NotionalHoldAmount": 0,
                "NotionalProductId": 0,
                "NotionalProductSymbol": self.base_asset,
                "NotionalRate": 1,
                "NotionalValue": 0,
                "OMSId": self.oms_id,
                "PendingDeposits": 0,
                "PendingWithdraws": 0,
                "ProductId": self.pair_id + 1,
                "ProductSymbol": self.base_asset,
                "TotalDayDepositNotional": 0,
                "TotalDayDeposits": 0,
                "TotalDayTransferNotional": 0,
                "TotalDayWithdrawNotional": 0,
                "TotalDayWithdraws": 0,
                "TotalMonthDepositNotional": 0,
                "TotalMonthDeposits": 0,
                "TotalMonthWithdrawNotional": 0,
                "TotalMonthWithdraws": 0,
                "TotalYearDepositNotional": 0,
                "TotalYearDeposits": 0,
                "TotalYearWithdrawNotional": 0,
                "TotalYearWithdraws": 0
            }

        def get_mock_balance_quote(self) -> Dict[str, Union[str, int]]:
            return {
                "AccountId": self.account_id,
                "Amount": 2000,
                "Hold": 0,
                "NotionalHoldAmount": 0,
                "NotionalProductId": 0,
                "NotionalProductSymbol": self.quote_asset,
                "NotionalRate": 1,
                "NotionalValue": 0,
                "OMSId": self.oms_id,
                "PendingDeposits": 0,
                "PendingWithdraws": 0,
                "ProductId": self.pair_id + 2,
                "ProductSymbol": self.quote_asset,
                "TotalDayDepositNotional": 0,
                "TotalDayDeposits": 0,
                "TotalDayTransferNotional": 0,
                "TotalDayWithdrawNotional": 0,
                "TotalDayWithdraws": 0,
                "TotalMonthDepositNotional": 0,
                "TotalMonthDeposits": 0,
                "TotalMonthWithdrawNotional": 0,
                "TotalMonthWithdraws": 0,
                "TotalYearDepositNotional": 0,
                "TotalYearDeposits": 0,
                "TotalYearWithdrawNotional": 0,
                "TotalYearWithdraws": 0,
            }

        @property
        def balance_event_websocket_update(self) -> Dict[str, Union[str, int, float]]:
            return {
                "i": 10,
                "m": 3,
                "n": CONSTANTS.WS_ACC_POS_EVENT,
                "o": self.get_mock_balance_base(),
            }

        @property
        def expected_latest_price(self) -> float:
            return 0.390718

        @property
        def expected_supported_order_types(self) -> List[OrderType]:
            return [OrderType.LIMIT]

        @property
        def expected_trading_rule(self):
            trading_rule_resp = self.trading_rules_request_mock_response[0]
            return TradingRule(
                trading_pair=self.trading_pair,
                min_order_size=Decimal(str(trading_rule_resp["MinimumQuantity"])),
                min_price_increment=Decimal(str(trading_rule_resp["PriceIncrement"])),
                min_base_amount_increment=Decimal(str(trading_rule_resp["QuantityIncrement"])),
            )

        @property
        def expected_logged_error_for_erroneous_trading_rule(self):
            erroneous_rule = self.trading_rules_request_erroneous_mock_response[0]
            return f"Error parsing the trading pair rule {erroneous_rule}. Skipping."

        @property
        def expected_exchange_order_id(self):
            return "312269865356374016"

        @property
        def expected_partial_fill_price(self) -> Decimal:
            return Decimal("0.390234")

        @property
        def expected_partial_fill_amount(self) -> Decimal:
            return Decimal("0.5")

        @property
        def expected_fill_fee(self) -> TradeFeeBase:
            return AddedToCostTradeFee(
                percent_token=self.quote_asset,
                flat_fees=[TokenAmount(token=self.quote_asset, amount=Decimal("0.075"))]
            )

        @property
        def expected_fill_trade_id(self) -> int:
            return 123

        @property
        def is_cancel_request_executed_synchronously_by_server(self) -> bool:
            return True

        @property
        def is_order_fill_http_update_included_in_status_update(self) -> bool:
            return True

        @property
        def is_order_fill_http_update_executed_during_websocket_order_event_processing(self) -> bool:
            return False

        def exchange_symbol_for_tokens(self, base_token: str, quote_token: str) -> str:
            return str(self.pair_id)

        def validate_auth_credentials_present(self, request_call: RequestCall):
            request_headers = request_call.kwargs["headers"]
            self.assertEqual(request_headers[CONSTANTS.API_KEY_FIELD], self.api_key)
            self.assertEqual(request_headers[CONSTANTS.SIGNATURE_FIELD], self.signature)
            self.assertEqual(request_headers[CONSTANTS.USER_ID_FIELD], str(self.user_id))
            self.assertEqual(request_headers[CONSTANTS.NONCE_FIELD], self.nonce)

        def validate_order_creation_request(self, order: InFlightOrder, request_call: RequestCall):
            request_data = json.loads(request_call.kwargs["data"])
            self.assertEqual(request_data[CONSTANTS.INSTRUMENT_ID_FIELD], self.pair_id)
            self.assertEqual(request_data[CONSTANTS.OMS_ID_FIELD], self.oms_id)
            self.assertEqual(request_data[CONSTANTS.ACCOUNT_ID_FIELD], self.account_id)
            self.assertEqual(request_data[CONSTANTS.TIME_IN_FORCE_FIELD], CONSTANTS.GTC_TIF)
            self.assertEqual(request_data[CONSTANTS.CLIENT_ORDER_ID_FIELD], int(order.client_order_id))
            self.assertEqual(request_data[CONSTANTS.QUANTITY_FIELD], Decimal("100"))
            self.assertEqual(request_data[CONSTANTS.LIMIT_PRICE_FIELD], Decimal("10000"))
            self.assertEqual(request_data[CONSTANTS.ORDER_TYPE_FIELD], CONSTANTS.LIMIT_ORDER_TYPE)

        def validate_order_status_request(self, order: InFlightOrder, request_call: RequestCall):
            request_data = request_call.kwargs["params"]
            self.assertEqual(request_data[CONSTANTS.OMS_ID_FIELD], self.oms_id)
            self.assertEqual(request_data[CONSTANTS.ACCOUNT_ID_FIELD], self.account_id)
            self.assertEqual(request_data[CONSTANTS.ORDER_ID_FIELD], int(order.exchange_order_id))

        def validate_order_cancelation_request(self, order: InFlightOrder, request_call: RequestCall):
            request_data = json.loads(request_call.kwargs["data"])
            self.assertEqual(request_data[CONSTANTS.OMS_ID_FIELD], self.oms_id)
            self.assertEqual(request_data[CONSTANTS.ACCOUNT_ID_FIELD], self.account_id)
            self.assertEqual(request_data[CONSTANTS.CL_ORDER_ID_FIELD], int(order.client_order_id))

        def validate_trades_request(self, order: InFlightOrder, request_call: RequestCall):
            request_data = request_call.kwargs["params"]
            self.assertEqual(request_data[CONSTANTS.OMS_ID_FIELD], self.oms_id)
            self.assertEqual(request_data[CONSTANTS.ACCOUNT_ID_FIELD], self.account_id)
            self.assertEqual(request_data[CONSTANTS.USER_ID_FIELD], self.user_id)
            self.assertEqual(request_data[CONSTANTS.ORDER_ID_FIELD], int(order.exchange_order_id))

        def configure_successful_cancelation_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None,
        ) -> str:
            url = self.url_creator.get_rest_url(path_url=CONSTANTS.REST_ORDER_CANCELATION_ENDPOINT)
            regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
            response = {"detail": None, "errorcode": 0, "errormsg": None, "result": True}
            mock_api.post(regex_url, body=json.dumps(response), callback=callback)
            return url

        def configure_erroneous_cancelation_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None,
        ) -> str:
            url = self.url_creator.get_rest_url(path_url=CONSTANTS.REST_ORDER_CANCELATION_ENDPOINT)
            regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
            response = {"detail": None, "errorcode": 102, "errormsg": "Server Error", "result": False}
            mock_api.post(regex_url, body=json.dumps(response), callback=callback)
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
            callback: Optional[Callable] = lambda *args, **kwargs: None,
        ) -> str:
            url = self.url_creator.get_rest_url(path_url=CONSTANTS.REST_ORDER_STATUS_ENDPOINT)
            regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
            response = self._order_status_request_completely_filled_mock_response(order)
            mock_api.get(regex_url, body=json.dumps(response), callback=callback)
            return url

        def configure_canceled_order_status_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None,
        ) -> str:
            url = self.url_creator.get_rest_url(path_url=CONSTANTS.REST_ORDER_STATUS_ENDPOINT)
            regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
            response = self._order_status_request_canceled_mock_response(order=order)
            mock_api.get(regex_url, body=json.dumps(response), callback=callback)
            return url

        def configure_open_order_status_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None,
        ) -> str:
            url = self.url_creator.get_rest_url(path_url=CONSTANTS.REST_ORDER_STATUS_ENDPOINT)
            regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
            response = self._order_status_request_open_mock_response(order=order)
            mock_api.get(regex_url, body=json.dumps(response), callback=callback)
            return url

        def configure_http_error_order_status_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None,
        ) -> str:
            url = self.url_creator.get_rest_url(path_url=CONSTANTS.REST_ORDER_STATUS_ENDPOINT)
            regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
            response = {"detail": None, "errorcode": 104, "errormsg": "Resource Not Found", "result": False}
            mock_api.get(regex_url, body=json.dumps(response), callback=callback)
            return url

        def configure_partially_filled_order_status_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None,
        ) -> str:
            url = self.url_creator.get_rest_url(path_url=CONSTANTS.REST_ORDER_STATUS_ENDPOINT)
            regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
            response = self._order_status_request_partially_filled_mock_response(order=order)
            mock_api.get(regex_url, body=json.dumps(response), callback=callback)
            return url

        def configure_partial_fill_trade_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None,
        ) -> str:
            url = self.url_creator.get_rest_url(path_url=CONSTANTS.REST_TRADE_HISTORY_ENDPOINT)
            regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
            response = self._order_fills_request_partial_fill_mock_response(order=order)
            mock_api.get(regex_url, body=json.dumps(response), callback=callback)
            return url

        def configure_full_fill_trade_response(
                self,
                order: InFlightOrder,
                mock_api: aioresponses,
                callback: Optional[Callable] = lambda *args, **kwargs: None,
        ) -> str:
            url = self.url_creator.get_rest_url(path_url=CONSTANTS.REST_TRADE_HISTORY_ENDPOINT)
            regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
            response = self._order_fills_request_full_fill_mock_response(order=order)
            mock_api.get(regex_url, body=json.dumps(response), callback=callback)
            return url

        def configure_erroneous_http_fill_trade_response(
                self,
                order: InFlightOrder,
                mock_api: aioresponses,
                callback: Optional[Callable] = lambda *args, **kwargs: None,
        ) -> str:
            url = self.url_creator.get_rest_url(path_url=CONSTANTS.REST_TRADE_HISTORY_ENDPOINT)
            regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
            response = {"detail": None, "errorcode": 20, "errormsg": "Not Authorized", "result": False}
            mock_api.get(regex_url, body=json.dumps(response), callback=callback)
            return url

        def order_event_for_new_order_websocket_update(self, order: InFlightOrder) -> Dict:
            return {
                "i": 2,
                "m": 3,
                "n": CONSTANTS.WS_ORDER_STATE_EVENT,
                "o": {
                    "Account": self.account_id,
                    "AccountName": self.user_name,
                    "AvgPrice": 0,
                    "CancelReason": None,
                    "ChangeReason": "NewInputAccepted",
                    "ClientOrderId": int(order.client_order_id),
                    "ClientOrderIdUuid": None,
                    "CounterPartyId": 0,
                    "DisplayQuantity": float(order.amount),
                    "EnteredBy": 169072,
                    "ExecutableValue": 0,
                    "GrossValueExecuted": 0,
                    "InsideAsk": 1455.51,
                    "InsideAskSize": 0.0455,
                    "InsideBid": 1446.28,
                    "InsideBidSize": 1.3325,
                    "Instrument": self.pair_id,
                    "IpAddress": None,
                    "IsLockedIn": False,
                    "IsQuote": False,
                    "LastTradePrice": 1457.34,
                    "LastUpdatedTime": 1655381197195,
                    "LastUpdatedTimeTicks": 637909779971950125,
                    "OMSId": self.oms_id,
                    "OrderFlag": "0",
                    "OrderId": int(order.exchange_order_id),
                    "OrderState": CONSTANTS.ACTIVE_ORDER_STATE,
                    "OrderType": "Limit",
                    "OrigClOrdId": 3,
                    "OrigOrderId": 18846132298,
                    "OrigQuantity": float(order.amount),
                    "PegLimitOffset": 0,
                    "PegOffset": 0,
                    "PegPriceType": "Unknown",
                    "Price": float(order.price),
                    "Quantity": float(order.amount),
                    "QuantityExecuted": 0,
                    "ReceiveTime": 1655381197195,
                    "ReceiveTimeTicks": 637909779971946403,
                    "RejectReason": None,
                    "Side": "Buy" if order.trade_type == TradeType.BUY else "Sell",
                    "StopPrice": 0,
                    "UseMargin": False,
                    "UserName": self.user_name,
                },
            }

        def order_event_for_canceled_order_websocket_update(self, order: InFlightOrder) -> Dict:
            return {
                "i": 6,
                "m": 3,
                "n": CONSTANTS.WS_ORDER_STATE_EVENT,
                "o": {
                    "Account": self.account_id,
                    "AccountName": self.user_name,
                    "AvgPrice": 0,
                    "CancelReason": None,
                    "ChangeReason": "UserModified",
                    "ClientOrderId": int(order.client_order_id),
                    "ClientOrderIdUuid": None,
                    "CounterPartyId": 0,
                    "DisplayQuantity": 0,
                    "EnteredBy": 169072,
                    "ExecutableValue": 0,
                    "GrossValueExecuted": 0,
                    "InsideAsk": 1455.51,
                    "InsideAskSize": 0.0455,
                    "InsideBid": 1446.28,
                    "InsideBidSize": 1.3325,
                    "Instrument": self.pair_id,
                    "IpAddress": None,
                    "IsLockedIn": False,
                    "IsQuote": False,
                    "LastTradePrice": 1457.34,
                    "LastUpdatedTime": 1655381197195,
                    "LastUpdatedTimeTicks": 637909779971950125,
                    "OMSId": self.oms_id,
                    "OrderFlag": "0",
                    "OrderId": int(order.exchange_order_id),
                    "OrderState": CONSTANTS.CANCELED_ORDER_STATE,
                    "OrderType": "Limit",
                    "OrigClOrdId": 3,
                    "OrigOrderId": 18846132298,
                    "OrigQuantity": float(order.amount),
                    "PegLimitOffset": 0,
                    "PegOffset": 0,
                    "PegPriceType": "Unknown",
                    "Price": float(order.price),
                    "Quantity": 0,
                    "QuantityExecuted": 0,
                    "ReceiveTime": 1655381197195,
                    "ReceiveTimeTicks": 637909779971946403,
                    "RejectReason": None,
                    "Side": "Buy" if order.trade_type == TradeType.BUY else "Sell",
                    "StopPrice": 0,
                    "UseMargin": False,
                    "UserName": self.user_name,
                },
            }

        def order_event_for_full_fill_websocket_update(self, order: InFlightOrder) -> Dict:
            return {
                "i": 4,
                "m": 3,
                "n": CONSTANTS.WS_ORDER_TRADE_EVENT,
                "o": self._order_fills_request_full_fill_mock_response(order)[0],
            }

        def trade_event_for_full_fill_websocket_update(self, order: InFlightOrder) -> Dict:
            return {
                "i": 6,
                "m": 3,
                "n": CONSTANTS.WS_ORDER_STATE_EVENT,
                "o": self._order_status_request_completely_filled_mock_response(order),
            }

        def _initialize_auth(self, auth: OMSConnectorAuth):
            auth_resp = self.get_auth_success_response()
            auth.update_with_rest_response(auth_resp)

        def _order_status_request_completely_filled_mock_response(self, order: InFlightOrder) -> Any:
            return {
                "Account": self.account_id,
                "AccountName": self.user_name,
                "AvgPrice": float(order.price),
                "CancelReason": "UserModified",
                "ChangeReason": "UserModified",
                "ClientOrderId": int(order.client_order_id),
                "ClientOrderIdUuid": None,
                "CounterPartyId": 0,
                "DisplayQuantity": 0,
                "EnteredBy": 169072,
                "ExecutableValue": 0.0,
                "GrossValueExecuted": 0.0,
                "InsideAsk": 1452.6,
                "InsideAskSize": 0.0268,
                "InsideBid": 1444.71,
                "InsideBidSize": 0.1185,
                "Instrument": self.pair_id,
                "IpAddress": "85.54.187.233",
                "IsLockedIn": False,
                "IsQuote": False,
                "LastTradePrice": 1444.47,
                "LastUpdatedTime": 1655295880854,
                "LastUpdatedTimeTicks": 637908926808535532,
                "OMSId": self.oms_id,
                "OrderFlag": "AddedToBook, RemovedFromBook",
                "OrderId": order.exchange_order_id,
                "OrderState": CONSTANTS.FULLY_EXECUTED_ORDER_STATE,
                "OrderType": "Limit",
                "OrigClOrdId": 1,
                "OrigOrderId": 18830582877,
                "OrigQuantity": float(order.amount),
                "PegLimitOffset": 0.0,
                "PegOffset": 0.0,
                "PegPriceType": "Unknown",
                "Price": float(order.price),
                "Quantity": 0,
                "QuantityExecuted": float(order.amount),
                "ReceiveTime": 1655295879486,
                "ReceiveTimeTicks": 637908926794855285,
                "RejectReason": None,
                "Side": "Buy" if order.trade_type == TradeType.BUY else "Sell",
                "StopPrice": 0.0,
                "UseMargin": False,
                "UserName": self.user_name,
            }

        def _order_status_request_canceled_mock_response(self, order: InFlightOrder) -> Any:
            return {
                "Account": self.account_id,
                "AccountName": self.user_name,
                "AvgPrice": 0.0,
                "CancelReason": "UserModified",
                "ChangeReason": "UserModified",
                "ClientOrderId": order.client_order_id,
                "ClientOrderIdUuid": None,
                "CounterPartyId": 0,
                "DisplayQuantity": 0,
                "EnteredBy": 169072,
                "ExecutableValue": 0.0,
                "GrossValueExecuted": 0.0,
                "InsideAsk": 1452.6,
                "InsideAskSize": 0.0268,
                "InsideBid": 1444.71,
                "InsideBidSize": 0.1185,
                "Instrument": self.pair_id,
                "IpAddress": "85.54.187.233",
                "IsLockedIn": False,
                "IsQuote": False,
                "LastTradePrice": 1444.47,
                "LastUpdatedTime": 1655295880854,
                "LastUpdatedTimeTicks": 637908926808535532,
                "OMSId": self.oms_id,
                "OrderFlag": "AddedToBook, RemovedFromBook",
                "OrderId": order.exchange_order_id,
                "OrderState": CONSTANTS.CANCELED_ORDER_STATE,
                "OrderType": "Limit",
                "OrigClOrdId": 1,
                "OrigOrderId": 18830582877,
                "OrigQuantity": 0,
                "PegLimitOffset": 0.0,
                "PegOffset": 0.0,
                "PegPriceType": "Unknown",
                "Price": float(order.price),
                "Quantity": float(order.amount),
                "QuantityExecuted": 0.0,
                "ReceiveTime": 1655295879486,
                "ReceiveTimeTicks": 637908926794855285,
                "RejectReason": None,
                "Side": "Buy" if order.trade_type == TradeType.BUY else "Sell",
                "StopPrice": 0.0,
                "UseMargin": False,
                "UserName": self.user_name,
            }

        def _order_status_request_open_mock_response(self, order: InFlightOrder) -> Any:
            return {
                "Account": self.account_id,
                "AccountName": self.user_name,
                "AvgPrice": 0.0,
                "CancelReason": "UserModified",
                "ChangeReason": "UserModified",
                "ClientOrderId": order.client_order_id,
                "ClientOrderIdUuid": None,
                "CounterPartyId": 0,
                "DisplayQuantity": float(order.amount),
                "EnteredBy": 169072,
                "ExecutableValue": 0.0,
                "GrossValueExecuted": 0.0,
                "InsideAsk": 1452.6,
                "InsideAskSize": 0.0268,
                "InsideBid": 1444.71,
                "InsideBidSize": 0.1185,
                "Instrument": self.pair_id,
                "IpAddress": "85.54.187.233",
                "IsLockedIn": False,
                "IsQuote": False,
                "LastTradePrice": 1444.47,
                "LastUpdatedTime": 1655295880854,
                "LastUpdatedTimeTicks": 637908926808535532,
                "OMSId": self.oms_id,
                "OrderFlag": "AddedToBook, RemovedFromBook",
                "OrderId": order.exchange_order_id,
                "OrderState": CONSTANTS.ACTIVE_ORDER_STATE,
                "OrderType": "Limit",
                "OrigClOrdId": 1,
                "OrigOrderId": 18830582877,
                "OrigQuantity": float(order.amount),
                "PegLimitOffset": 0.0,
                "PegOffset": 0.0,
                "PegPriceType": "Unknown",
                "Price": float(order.price),
                "Quantity": float(order.amount),
                "QuantityExecuted": 0.0,
                "ReceiveTime": 1655295879486,
                "ReceiveTimeTicks": 637908926794855285,
                "RejectReason": None,
                "Side": "Buy" if order.trade_type == TradeType.BUY else "Sell",
                "StopPrice": 0.0,
                "UseMargin": False,
                "UserName": self.user_name,
            }

        def _order_status_request_partially_filled_mock_response(self, order: InFlightOrder) -> Any:
            return {
                "Account": self.account_id,
                "AccountName": self.user_name,
                "AvgPrice": float(self.expected_partial_fill_price),
                "CancelReason": "UserModified",
                "ChangeReason": "UserModified",
                "ClientOrderId": order.client_order_id,
                "ClientOrderIdUuid": None,
                "CounterPartyId": 0,
                "DisplayQuantity": float(order.amount),
                "EnteredBy": 169072,
                "ExecutableValue": 0.0,
                "GrossValueExecuted": 0.0,
                "InsideAsk": 1452.6,
                "InsideAskSize": 0.0268,
                "InsideBid": 1444.71,
                "InsideBidSize": 0.1185,
                "Instrument": self.pair_id,
                "IpAddress": "85.54.187.233",
                "IsLockedIn": False,
                "IsQuote": False,
                "LastTradePrice": 1444.47,
                "LastUpdatedTime": 1655295880854,
                "LastUpdatedTimeTicks": 637908926808535532,
                "OMSId": self.oms_id,
                "OrderFlag": "AddedToBook, RemovedFromBook",
                "OrderId": order.exchange_order_id,
                "OrderState": CONSTANTS.ACTIVE_ORDER_STATE,
                "OrderType": "Limit",
                "OrigClOrdId": 1,
                "OrigOrderId": 18830582877,
                "OrigQuantity": float(order.amount),
                "PegLimitOffset": 0.0,
                "PegOffset": 0.0,
                "PegPriceType": "Last",
                "Price": float(order.price),
                "Quantity": float(order.amount),
                "QuantityExecuted": float(self.expected_partial_fill_amount),
                "ReceiveTime": 1655295879486,
                "ReceiveTimeTicks": 637908926794855285,
                "RejectReason": "",
                "Side": "Buy" if order.trade_type == TradeType.BUY else "Sell",
                "StopPrice": 0.0,
                "UseMargin": False,
                "UserName": self.user_name,
            }

        def _order_fills_request_partial_fill_mock_response(self, order: InFlightOrder):
            return [
                {
                    "AccountId": self.account_id,
                    "AccountName": self.user_name,
                    "AdapterTradeId": 0,
                    "ClientOrderId": 0,
                    "CounterParty": "61125",
                    "CounterPartyClientUserId": 1,
                    "Direction": "NoChange",
                    "ExecutionId": 4713579,
                    "Fee": float(self.expected_fill_fee.flat_fees[0].amount),
                    "FeeProductId": self.quote_id,
                    "InsideAsk": 3195.72,
                    "InsideAskSize": 0.0,
                    "InsideBid": 3172.31,
                    "InsideBidSize": 0.0119,
                    "InstrumentId": self.pair_id,
                    "IsBlockTrade": False,
                    "IsQuote": False,
                    "MakerTaker": "Taker",
                    "NotionalHoldAmount": 0,
                    "NotionalProductId": 6,
                    "NotionalRate": 0.8016636123283036,
                    "NotionalValue": 21.34669866907807,
                    "OMSId": self.oms_id,
                    "OrderId": int(order.exchange_order_id),
                    "OrderOriginator": 169072,
                    "OrderTradeRevision": 1,
                    "OrderType": "Market",
                    "Price": float(self.expected_partial_fill_price),
                    "Quantity": float(self.expected_partial_fill_amount),
                    "RemainingQuantity": float(order.amount - self.expected_partial_fill_amount),
                    "Side": "Buy" if order.trade_type == TradeType.BUY else "Sell",
                    "SubAccountId": 0,
                    "TradeId": int(self.expected_fill_trade_id),
                    "TradeTime": 637634811411180462,
                    "TradeTimeMS": 1627884341118,
                    "UserName": self.user_name,
                    "Value": 26.628,
                },
            ]

        def _order_fills_request_full_fill_mock_response(self, order: InFlightOrder):
            return [
                {
                    "AccountId": self.user_id,
                    "AccountName": self.user_name,
                    "AdapterTradeId": 0,
                    "ClientOrderId": int(order.client_order_id),
                    "CounterParty": "61125",
                    "CounterPartyClientUserId": 1,
                    "Direction": "NoChange",
                    "ExecutionId": 4713579,
                    "Fee": float(self.expected_fill_fee.flat_fees[0].amount),
                    "FeeProductId": self.quote_id,
                    "InsideAsk": 3195.72,
                    "InsideAskSize": 0.0,
                    "InsideBid": 3172.31,
                    "InsideBidSize": 0.0119,
                    "InstrumentId": self.pair_id,
                    "IsBlockTrade": False,
                    "IsQuote": False,
                    "MakerTaker": "Taker",
                    "NotionalHoldAmount": 0,
                    "NotionalProductId": 6,
                    "NotionalRate": 0.8016636123283036,
                    "NotionalValue": 21.34669866907807,
                    "OMSId": self.oms_id,
                    "OrderId": int(order.exchange_order_id),
                    "OrderOriginator": 169072,
                    "OrderTradeRevision": 1,
                    "OrderType": "Market",
                    "Price": float(order.price),
                    "Quantity": float(order.amount),
                    "RemainingQuantity": 0.0,
                    "Side": "Buy" if order.trade_type == TradeType.BUY else "Sell",
                    "SubAccountId": 0,
                    "TradeId": int(self.expected_fill_trade_id),
                    "TradeTime": 637634811411180462,
                    "TradeTimeMS": 1627884341118,
                    "UserName": self.user_name,
                    "Value": 26.628,
                },
            ]

        @aioresponses()
        def test_exchange_authenticates(self, mock_api):
            url = self.url_creator.get_rest_url(path_url=CONSTANTS.REST_AUTH_ENDPOINT)
            url_regex = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
            auth_resp = self.get_auth_success_response()
            mock_api.get(url_regex, body=json.dumps(auth_resp))

            self.async_run_with_timeout(self.exchange.start_network())

            self.assertTrue(self.exchange.authenticator.initialized)

        @aioresponses()
        def test_failure_to_authenticate(self, mock_api):
            url = self.url_creator.get_rest_url(path_url=CONSTANTS.REST_AUTH_ENDPOINT)
            url_regex = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
            auth_resp = self.get_auth_failure_response()
            mock_api.get(url_regex, body=json.dumps(auth_resp))
            exchange = self.create_exchange_instance(authenticated=False)

            with self.assertRaises(IOError):
                self.async_run_with_timeout(exchange.start_network())

            self.assertFalse(exchange.authenticator.initialized)
