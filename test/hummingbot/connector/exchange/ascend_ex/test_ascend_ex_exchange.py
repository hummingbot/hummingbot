import asyncio
import unittest

from decimal import Decimal
from typing import Awaitable

from hummingbot.connector.exchange.ascend_ex.ascend_ex_exchange import (
    AscendExExchange,
    AscendExTradingRule,
    AscendExCommissionType,
)
from hummingbot.core.event.events import OrderType, TradeType
from test.hummingbot.connector.network_mocking_assistant import NetworkMockingAssistant


class TestAscendExExchange(unittest.TestCase):
    # logging.Level required to receive logs from the exchange
    level = 0

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.ev_loop = asyncio.get_event_loop()
        cls.base_asset = "COINALPHA"
        cls.quote_asset = "HBOT"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.ex_trading_pair = f"{cls.base_asset}/{cls.quote_asset}"
        cls.api_key = "someKey"
        cls.api_secret_key = "someSecretKey"

    def setUp(self) -> None:
        super().setUp()
        self.log_records = []

        self.exchange = AscendExExchange(self.api_key, self.api_secret_key, trading_pairs=[self.trading_pair])
        self.mocking_assistant = NetworkMockingAssistant()

    def tearDown(self) -> None:
        self.exchange._shared_client and self.exchange._shared_client.close()
        super().tearDown()

    def handle(self, record):
        self.log_records.append(record)

    def _is_logged(self, log_level: str, message: str) -> bool:
        return any(record.levelname == log_level and record.getMessage() == message for record in self.log_records)

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: int = 1):
        ret = self.ev_loop.run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    def simulate_trading_rules_initialized(self):
        self.exchange._trading_rules = {
            self.trading_pair: AscendExTradingRule(
                trading_pair=self.trading_pair,
                min_price_increment=Decimal(str(0.0001)),
                min_base_amount_increment=Decimal(str(0.000001)),
                min_notional_size=Decimal("0.001"),
                max_notional_size=Decimal("99999999"),
                commission_type=AscendExCommissionType.QUOTE,
                commission_reserve_rate=Decimal("0.002"),
            ),
        }

    def test_get_fee(self):
        self.simulate_trading_rules_initialized()
        trading_rule: AscendExTradingRule = self.exchange._trading_rules[self.trading_pair]
        amount = Decimal("1")
        price = Decimal("2")
        trading_rule.commission_reserve_rate = Decimal("0.002")

        trading_rule.commission_type = AscendExCommissionType.QUOTE
        buy_fee = self.exchange.get_fee(
            self.base_asset, self.quote_asset, OrderType.LIMIT, TradeType.BUY, amount, price
        )
        sell_fee = self.exchange.get_fee(
            self.base_asset, self.quote_asset, OrderType.LIMIT, TradeType.SELL, amount, price
        )

        self.assertEqual(Decimal("0.002"), buy_fee.percent)
        self.assertEqual(Decimal("0"), sell_fee.percent)

        trading_rule.commission_type = AscendExCommissionType.BASE
        buy_fee = self.exchange.get_fee(
            self.base_asset, self.quote_asset, OrderType.LIMIT, TradeType.BUY, amount, price
        )
        sell_fee = self.exchange.get_fee(
            self.base_asset, self.quote_asset, OrderType.LIMIT, TradeType.SELL, amount, price
        )

        self.assertEqual(Decimal("0"), buy_fee.percent)
        self.assertEqual(Decimal("0.002"), sell_fee.percent)

        trading_rule.commission_type = AscendExCommissionType.RECEIVED
        buy_fee = self.exchange.get_fee(
            self.base_asset, self.quote_asset, OrderType.LIMIT, TradeType.BUY, amount, price
        )
        sell_fee = self.exchange.get_fee(
            self.base_asset, self.quote_asset, OrderType.LIMIT, TradeType.SELL, amount, price
        )

        self.assertEqual(Decimal("0"), buy_fee.percent)
        self.assertEqual(Decimal("0"), sell_fee.percent)

    # def test_execute_cancel_order_not_found_exceed_limit(self):
    #     client_order_id = "ORDER_NOT_FOUND_ID"
    #     self.async_run_with_timeout(self.exchange._execute_cancel(self.trading_pair, client_order_id))
    #     self.assertIn(client_order_id, self.exchange._order_not_found_records)

    #     self.async_run_with_timeout(self.exchange._execute_cancel(self.trading_pair, client_order_id))
    #     self.assertNotIn(client_order_id, self.exchange._order_not_found_records)

    #     self._is_logged(
    #         "NETWORK",
    #         f"Failed to cancel the order {client_order_id} on AscendEx. Check API key and network connection.",
    #     )

    # def test_websocket_process_order_message_no_open_for_cancel(self):

    #     client_order_id = "someClientOrderId"
    #     ex_order_id = "HMBotExchangeOrderId1234"
    #     self.exchange._in_flight_orders[client_order_id] = AscendExInFlightOrder(
    #         client_order_id=client_order_id,
    #         exchange_order_id=ex_order_id,
    #         trading_pair=self.trading_pair,
    #         order_type=OrderType.LIMIT,
    #         trade_type=TradeType.BUY,
    #         price=Decimal("1"),
    #         amount=Decimal("10"),
    #     )

    #     ws_resp = {
    #         "m": "order",
    #         "accountId": "cshSomeAccountId",
    #         "ac": "CASH",
    #         "data": {
    #             "sn": 28361787015,
    #             "orderId": ex_order_id,
    #             "s": self.ex_trading_pair,
    #             "ot": "NULL_VAL",
    #             "t": 1638440160232,
    #             "p": "0",
    #             "q": "0",
    #             "sd": "NULL_VAL",
    #             "st": "Rejected",
    #             "ap": "0",
    #             "cfq": "0",
    #             "sp": "",
    #             "err": "NoOpenForCancel",
    #             "btb": "23",
    #             "bab": "23",
    #             "qtb": "51.99954056",
    #             "qab": "31.33329056",
    #             "cf": "0",
    #             "fa": "USDT",
    #             "ei": "NULL_VAL",
    #         },
    #     }

    #     parsed_order_message: AscendExOrder = AscendExOrder(
    #         self.ex_trading_pair,
    #         ws_resp["data"]["p"],
    #         ws_resp["data"]["q"],
    #         ws_resp["data"]["ot"],
    #         ws_resp["data"]["ap"],
    #         ws_resp["data"]["cf"],
    #         ws_resp["data"]["cfq"],
    #         ws_resp["data"]["err"],
    #         ws_resp["data"]["fa"],
    #         ws_resp["data"]["t"],
    #         ws_resp["data"]["orderId"],
    #         ws_resp["data"]["sn"],
    #         ws_resp["data"]["sd"],
    #         ws_resp["data"]["st"],
    #         ws_resp["data"]["sp"],
    #         ws_resp["data"]["ei"],
    #     )

    #     self.exchange._process_order_message(parsed_order_message)

    #     self.assertIn(client_order_id, self.exchange.in_flight_orders)
    #     self._is_logged(
    #         "INFO",
    #         f"Order {client_order_id} has failed according to order status API. API order response: {parsed_order_message}",
    #     )

    #     # Stops tracking order after a Failure message is received for more than STOP_TRACKING_ORDER_FAILURE_LIMIT
    #     self.exchange._process_order_message(parsed_order_message)
    #     self.assertNotIn(client_order_id, self.exchange.in_flight_orders)

    # def test_update_order_status_successful(self):

    #     mock_response = {
    #         "code": 0,
    #         "accountCategory": "CASH",
    #         "accountId": "cshQtyfq8XLAA9kcf19h8bXHbAwwoqDo",
    #         "data": [
    #             {
    #                 "symbol": "BTC/USDT",
    #                 "price": "8130.24",
    #                 "orderQty": "0.00082",
    #                 "orderType": "Limit",
    #                 "avgPx": "7391.13",
    #                 "cumFee": "0.005151618",
    #                 "cumFilledQty": "0.00082",
    #                 "errorCode": "",
    #                 "feeAsset": "USDT",
    #                 "lastExecTime": 1575953134011,
    #                 "orderId": "a16eee206d610866943712rPNknIyhH",
    #                 "seqNum": 2622058,
    #                 "side": "Buy",
    #                 "status": "Filled",
    #                 "stopPrice": "",
    #                 "execInst": "NULL_VAL",
    #             },
    #             {
    #                 "symbol": "BTC/USDT",
    #                 "price": "8131.22",
    #                 "orderQty": "0.00082",
    #                 "orderType": "Market",
    #                 "avgPx": "7392.02",
    #                 "cumFee": "0.005152238",
    #                 "cumFilledQty": "0.00082",
    #                 "errorCode": "",
    #                 "feeAsset": "USDT",
    #                 "lastExecTime": 1575953151764,
    #                 "orderId": "a16eee20b6750866943712zWEDdAjt3",
    #                 "seqNum": 2623469,
    #                 "side": "Buy",
    #                 "status": "Filled",
    #                 "stopPrice": "",
    #                 "execInst": "NULL_VAL",
    #             },
    #         ],
    #     }
