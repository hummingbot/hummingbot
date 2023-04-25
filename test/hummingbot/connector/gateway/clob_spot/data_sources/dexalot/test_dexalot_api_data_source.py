import asyncio
import json
import math
import re
from decimal import Decimal
from typing import Any, Dict, List, Union
from unittest.mock import AsyncMock, MagicMock, patch

import pandas as pd
from aioresponses import aioresponses

from hummingbot.connector.gateway.clob_spot.data_sources.dexalot import dexalot_constants as CONSTANTS
from hummingbot.connector.gateway.clob_spot.data_sources.dexalot.dexalot_api_data_source import DexalotAPIDataSource
from hummingbot.connector.gateway.clob_spot.data_sources.dexalot.dexalot_constants import HB_TO_DEXALOT_STATUS_MAP
from hummingbot.connector.gateway.common_types import PlaceOrderResult
from hummingbot.connector.gateway.gateway_in_flight_order import GatewayInFlightOrder
from hummingbot.connector.test_support.gateway_clob_api_data_source_test import AbstractGatewayCLOBAPIDataSourceTests
from hummingbot.connector.test_support.network_mocking_assistant import NetworkMockingAssistant
from hummingbot.connector.utils import split_hb_trading_pair
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import OrderState, OrderUpdate
from hummingbot.core.data_type.order_book_message import OrderBookMessage
from hummingbot.core.data_type.trade_fee import TradeFeeBase
from hummingbot.core.event.event_logger import EventLogger
from hummingbot.core.event.events import OrderBookDataSourceEvent


class DexalotAPIDataSourceTest(AbstractGatewayCLOBAPIDataSourceTests.GatewayCLOBAPIDataSourceTests):
    @property
    def expected_buy_exchange_order_id(self) -> str:
        return "0x0000000000000000000000000000000000000000000000000000000063cd59f3"  # noqa: mock

    @property
    def expected_sell_exchange_order_id(self) -> str:
        return "0x0000000000000000000000000000000000000000000000000000000063cd59f4"  # noqa: mock

    @property
    def expected_fill_trade_id(self) -> Union[str, int]:
        return 12340

    @property
    def exchange_base(self) -> str:
        return self.hb_token_to_exchange_token(hb_token=self.base)

    @property
    def exchange_quote(self) -> str:
        return self.hb_token_to_exchange_token(hb_token=self.quote)

    @property
    def expected_quote_decimals(self) -> int:
        return 6

    @property
    def expected_base_decimals(self) -> int:
        return 18

    @property
    def expected_event_counts_per_new_order(self) -> int:
        return 2

    def setUp(self) -> None:
        self.domain = "dexalot"
        self.mock_api = aioresponses()
        self.mock_api.start()
        self.api_key_mock = "someAPIKey"
        self.wallet_sign_mock = "DD5113FEDED638E5500E65779613BDD3BDDBEB8EB5D86CDD3370E629B02E92CD"  # noqa: mock

        self.mocking_assistant = NetworkMockingAssistant()
        self.ws_connect_patch = patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
        self.ws_connect_mock = self.ws_connect_patch.start()
        super().setUp()
        self.configure_signature_response()
        self.configure_ws_auth_response()

    def tearDown(self) -> None:
        self.mock_api.stop()
        self.ws_connect_patch.stop()
        super().tearDown()

    def configure_signature_response(self):
        response = {
            "signature": self.wallet_sign_mock,
        }
        self.gateway_instance_mock.wallet_sign.return_value = response

    def configure_ws_auth_response(self):
        response = {"token": "someToken"}
        url = CONSTANTS.BASE_PATH_URL[self.domain] + CONSTANTS.WS_AUTH_PATH
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        self.mock_api.get(regex_url, body=json.dumps(response))

    def build_api_data_source(self) -> DexalotAPIDataSource:
        connector_spec = {
            "api_key": "someAPIKey",
            "chain": "avalanche",
            "network": "dexalot",
            "wallet_address": self.account_id,
            "additional_prompt_values": {"api_key": self.api_key_mock},
        }
        data_source = DexalotAPIDataSource(
            trading_pairs=[self.trading_pair],
            connector_spec=connector_spec,
            client_config_map=self.client_config_map,
        )
        return data_source

    def exchange_symbol_for_tokens(self, base_token: str, quote_token: str) -> str:
        exchange_base_token = self.hb_token_to_exchange_token(hb_token=base_token)
        exchange_quote_token = self.hb_token_to_exchange_token(hb_token=quote_token)
        exchange_trading_pair = f"{exchange_base_token}/{exchange_quote_token}"
        return exchange_trading_pair

    @staticmethod
    def hb_token_to_exchange_token(hb_token: str) -> str:
        """To simulate cases with differing symbols (e.g. USDt)."""
        return hb_token[:-1] + hb_token[-1].lower()

    def get_trading_pairs_info_response(self) -> List[Dict[str, Any]]:
        return [
            {
                "baseSymbol": self.exchange_base,
                "quoteSymbol": self.exchange_quote,
                "buyBookId": "someId",
                "sellBookId": "anotherId",
                "minTradeAmount": 5000000,
                "maxTradeAmount": 50000000000,
                "auctionPrice": 6,
                "auctionMode": 1,
                "makerRate": float(self.expected_maker_taker_fee_rates.maker),
                "takerRate": float(self.expected_maker_taker_fee_rates.taker),
                "baseDecimals": self.expected_base_decimals,
                "baseDisplayDecimals": 3,
                "quoteDecimals": self.expected_quote_decimals,
                "quoteDisplayDecimals": int(math.log10(1 / self.expected_min_price_increment)),
                "allowedSlippagePercent": 1,
                "addOrderPaused": False,
                "pairPaused": False,
                "postOnly": False,
            },
            {
                "baseSymbol": "ANOTHER",
                "quoteSymbol": "PAIR",
                "buyBookId": "someId",
                "sellBookId": "anotherId",
                "minTradeAmount": 5000000,
                "maxTradeAmount": 50000000000,
                "auctionPrice": 6,
                "auctionMode": 1,
                "makerRate": float(self.expected_maker_taker_fee_rates.maker),
                "takerRate": float(self.expected_maker_taker_fee_rates.taker),
                "baseDecimals": 18,
                "baseDisplayDecimals": 6,
                "quoteDecimals": 16,
                "quoteDisplayDecimals": 4,
                "allowedSlippagePercent": 2,
                "addOrderPaused": False,
                "pairPaused": False,
                "postOnly": False,
            }
        ]

    def get_clob_ticker_response(self, trading_pair: str, last_traded_price: Decimal) -> List[Dict[str, Any]]:
        raise NotImplementedError

    def configure_place_order_response(
        self,
        timestamp: float,
        transaction_hash: str,
        exchange_order_id: str,
        trade_type: TradeType,
        price: Decimal,
        size: Decimal,
    ):
        super().configure_batch_order_create_response(
            timestamp=timestamp,
            transaction_hash=transaction_hash,
            created_orders=[
                GatewayInFlightOrder(
                    client_order_id=self.expected_buy_client_order_id,
                    trading_pair=self.trading_pair,
                    order_type=OrderType.LIMIT,
                    trade_type=trade_type,
                    creation_timestamp=timestamp,
                    price=price,
                    amount=size,
                    exchange_order_id=exchange_order_id,
                    creation_transaction_hash=transaction_hash,
                )
            ]
        )

    def configure_place_order_failure_response(self):
        self.gateway_instance_mock.clob_batch_order_modify.return_value = {
            "network": self.data_source.network,
            "timestamp": self.initial_timestamp,
            "latency": 2,
            "txHash": None,
        }

    def configure_cancel_order_response(self, timestamp: float, transaction_hash: str):
        super().configure_batch_order_cancel_response(
            timestamp=timestamp, transaction_hash=transaction_hash, canceled_orders=[]
        )

    def configure_cancel_order_failure_response(self):
        self.gateway_instance_mock.clob_batch_order_modify.return_value = {
            "network": self.data_source.network,
            "timestamp": self.initial_timestamp,
            "latency": 2,
            "txHash": None,
        }

    def configure_account_balances_response(
        self,
        base_total_balance: Decimal,
        base_available_balance: Decimal,
        quote_total_balance: Decimal,
        quote_available_balance: Decimal,
    ):
        response = {
            "balances": {
                "available": {
                    self.exchange_base: self.expected_base_available_balance,
                    self.exchange_quote: self.expected_quote_available_balance,
                },
                "total": {
                    self.exchange_base: self.expected_base_total_balance,
                    self.exchange_quote: self.expected_quote_total_balance,
                },
            }
        }
        self.gateway_instance_mock.get_balances.return_value = response

    def configure_empty_order_fills_response(self):
        url = CONSTANTS.BASE_PATH_URL[self.domain] + CONSTANTS.EXECUTIONS_PATH
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        markets_resp = []
        self.mock_api.get(regex_url, body=json.dumps(markets_resp))

    def configure_trade_fill_response(
        self,
        timestamp: float,
        exchange_order_id: str,
        price: Decimal,
        size: Decimal,
        fee: TradeFeeBase,
        trade_id: Union[str, int],
        is_taker: bool,
    ):
        url = CONSTANTS.BASE_PATH_URL[self.domain] + CONSTANTS.EXECUTIONS_PATH
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        fee_token = self.hb_token_to_exchange_token(hb_token=fee.flat_fees[0].token)
        markets_resp = [
            {
                "env": "production-multi-subnet",
                "execid": trade_id,
                "fee": str(fee.flat_fees[0].amount),
                "feeunit": fee_token,
                "orderid": exchange_order_id,
                "pair": self.exchange_trading_pair,
                "price": str(price),
                "quantity": str(size),
                "side": 0,
                "traderaddress": self.account_id,
                "ts": self.data_source._timestamp_to_dexalot_timestamp(timestamp=timestamp),
                "tx": "0xe7c7a9b32607d0bf3c9aa4f39069f5a31b1dc9fdde6dbe95f8dbee255e4869dc",  # noqa: mock
                "type": "T" if is_taker else "M",
            }
        ]
        self.mock_api.get(regex_url, body=json.dumps(markets_resp))

    def configure_orderbook_snapshot_event(
        self, bids: List[List[float]], asks: List[List[float]], latency: float = 0
    ):
        self.ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()
        price_scaler = Decimal(f"1e{self.expected_quote_decimals}")
        size_scaler = Decimal(f"1e{self.expected_base_decimals}")
        resp = {  # abbreviated response
            "data": {
                "buyBook": [
                    {
                        "prices": ",".join([str(int(price * price_scaler)) for price, _ in bids]),
                        "quantities": ",".join([str(int(size * size_scaler)) for _, size in bids]),
                    }
                ],
                "sellBook": [
                    {
                        "prices": ",".join([str(int(price * price_scaler)) for price, _ in asks]),
                        "quantities": ",".join([str(int(size * size_scaler)) for _, size in asks]),
                    }
                ],
            },
            "pair": self.exchange_trading_pair,
            "type": "orderBooks",
        }
        self.mocking_assistant.add_websocket_aiohttp_message(
            self.ws_connect_mock.return_value, json.dumps(resp)
        )

    def configure_last_traded_price(self, trading_pair: str, last_traded_price: Decimal):
        self.ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()
        resp = {"data": [{"execId": 1675046315,
                          "price": str(self.expected_last_traded_price),
                          "quantity": "951.14",
                          "takerSide": 1,
                          "ts": "2023-03-07T14:17:52.000Z"}],
                "pair": self.exchange_trading_pair,
                "type": "lastTrade"}
        self.mocking_assistant.add_websocket_aiohttp_message(
            self.ws_connect_mock.return_value, json.dumps(resp)
        )

    def enqueue_order_status_response(
        self,
        timestamp: float,
        trading_pair: str,
        exchange_order_id: str,
        client_order_id: str,
        status: OrderState,
    ) -> asyncio.Event:
        order = GatewayInFlightOrder(
            client_order_id=client_order_id,
            trading_pair=trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            creation_timestamp=timestamp,
            price=self.expected_buy_order_price,
            amount=self.expected_buy_order_size,
            exchange_order_id=exchange_order_id,
            creation_transaction_hash=self.expected_transaction_hash,
        )
        return self.enqueue_order_status_responses_for_batch_order_create(
            timestamp=timestamp, orders=[order], statuses=[status]
        )

    def enqueue_order_status_responses_for_batch_order_create(
        self, timestamp: float, orders: List[GatewayInFlightOrder], statuses: List[OrderState]
    ) -> asyncio.Event:
        update_delivered_event = asyncio.Event()
        base_url = CONSTANTS.BASE_PATH_URL[self.domain] + CONSTANTS.ORDERS_PATH
        for order, status, i in zip(orders, statuses, range(len(orders))):
            if status == OrderState.OPEN:  # order is being created, and it doesn't have an exchange order ID
                response = self.get_transaction_status_update(
                    timestamp=timestamp, orders=orders, statuses=statuses
                )
                self.gateway_instance_mock.get_transaction_status.return_value = response
            regex_url = re.compile(
                f"^{base_url}/{order.exchange_order_id}".replace(".", r"\.").replace("?", r"\?")
            )
            response = self.get_order_status_response(
                timestamp=timestamp,
                trading_pair=order.trading_pair,
                exchange_order_id=order.exchange_order_id or "",
                client_order_id=order.client_order_id,
                status=status,
            )

            callback = None if i != len(orders) - 1 else lambda *_, **__: update_delivered_event.set()
            self.mock_api.get(regex_url, body=json.dumps(response), callback=callback)

        return update_delivered_event

    def get_transaction_status_update(
        self, timestamp: float, orders: List[GatewayInFlightOrder], statuses: List[OrderState]
    ):
        return {
            "txStatus": 1,
            "timestamp": int(timestamp * 1e3),
            "txHash": self.expected_transaction_hash,
            "txData": {},
            "txReceipt": {
                "transactionHash": self.expected_transaction_hash,
                "logs": [
                    {
                        "name": "OrderStatusChanged",
                        "events": [
                            {},  # version
                            {},  # traderaddress
                            {},  # pair
                            {
                                "name": "orderId",
                                "type": "bytes32",
                                "value": order.exchange_order_id,
                            },
                            {
                                "name": "clientOrderId",
                                "type": "bytes32",
                                "value": order.client_order_id,
                            },
                            {
                                "name": "price",
                                "type": "uint256",
                                "value": "15000000"
                            },
                            {},  # totalamount
                            {
                                "name": "quantity",
                                "type": "uint256",
                                "value": "500000000000000000"
                            },
                            {},  # side
                            {},  # type1
                            {},  # type2
                            {
                                "name": "status",
                                "type": "uint8",
                                "value": str(CONSTANTS.HB_TO_DEXALOT_NUMERIC_STATUS_MAP[status])
                            },
                            {},  # quantityfilled
                            {},  # totalfee
                            {},  # code
                        ],
                        "address": "0x09383137C1eEe3E1A8bc781228E4199f6b4A9bbf"
                    } for order, status in zip(orders, statuses)
                ],
                "status": 1,
            },
        }

    def get_order_status_response(
        self,
        timestamp: float,
        trading_pair: str,
        exchange_order_id: str,
        client_order_id: str,
        status: OrderState,
    ) -> Dict[str, Any]:
        """
        Example response:

        { "id": "0x0000000000000000000000000000000000000000000000000000000063d4909e",  # noqa: mock
          "price": "22.000000000000000000",
          "quantity": "0.800000000000000000",
          "quantityFilled": "0.000000000000000000",
          "side": "SELL",
          "status": "CANCELED",
          "timestamp": "2023-02-27T04:49:40.000Z",
          "totalAmount": "0.000000000000000000",
          "totalFee": "0.000000000000000000",
          "tradePair": "AVAX/USDC",
          "tx": "0xc9468f344cfe9917e692afecb2b81e89b807394a0ac873db9ee1417297a5f869",  # noqa: mock
          "type1": "LIMIT",
          "type2": "GTC",
          "updateTs": "2023-02-27T05:04:25.000Z"}
        """
        dexalot_timestamp_str = pd.Timestamp.utcfromtimestamp(timestamp).strftime(format="%Y-%m-%dT%H:%M:%S") + ".000Z"
        response = {
            "id": exchange_order_id,
            "price": "22.000000000000000000",
            "quantity": "0.800000000000000000",
            "quantityFilled": "0.000000000000000000",
            "side": "SELL",
            "status": HB_TO_DEXALOT_STATUS_MAP[status],
            "timestamp": dexalot_timestamp_str,
            "totalAmount": "0.000000000000000000",
            "totalFee": "0.000000000000000000",
            "tradePair": self.exchange_trading_pair_from_hb_trading_pair(trading_pair=trading_pair),
            "tx": "0xc9468f344cfe9917e692afecb2b81e89b807394a0ac873db9ee1417297a5f869",  # noqa: mock
            "type1": "LIMIT",
            "type2": "GTC",
            "updateTs": dexalot_timestamp_str,
        }
        return response

    @staticmethod
    def exchange_trading_pair_from_hb_trading_pair(trading_pair: str) -> str:
        base, quote = split_hb_trading_pair(trading_pair=trading_pair)
        return f"{base[:-1] + base[-1].lower()}/{quote[:-1] + quote[-1].lower()}"

    @patch(
        "hummingbot.connector.gateway.clob_spot.data_sources.dexalot.dexalot_api_data_source"
        ".DexalotAPIDataSource._time"
    )
    def test_delivers_order_book_snapshot_events(self, time_mock: MagicMock):
        self.async_run_with_timeout(self.data_source.stop())

        data_source = self.build_api_data_source()
        self.additional_data_sources_to_stop_on_tear_down.append(data_source)
        data_source.min_snapshots_update_interval = 0
        data_source.max_snapshots_update_interval = 0

        snapshots_logger = EventLogger()

        data_source.add_listener(
            event_tag=OrderBookDataSourceEvent.SNAPSHOT_EVENT, listener=snapshots_logger
        )

        self.configure_orderbook_snapshot_event(bids=[[9, 1], [8, 2]], asks=[[11, 3]])
        time_mock.return_value = self.initial_timestamp
        data_source.gateway_order_tracker = self.tracker

        task = asyncio.get_event_loop().create_task(coro=snapshots_logger.wait_for(event_type=OrderBookMessage))
        self.async_tasks.append(task)
        self.async_run_with_timeout(coro=data_source.start())
        self.mocking_assistant.run_until_all_aiohttp_messages_delivered(
            websocket_mock=self.ws_connect_mock.return_value
        )
        self.async_run_with_timeout(coro=task)

        self.assertEqual(1, len(snapshots_logger.event_log))

        snapshot_event: OrderBookMessage = snapshots_logger.event_log[0]

        self.assertEqual(self.initial_timestamp, snapshot_event.timestamp)
        self.assertEqual(2, len(snapshot_event.bids))
        self.assertEqual(9, snapshot_event.bids[0].price)
        self.assertEqual(1, snapshot_event.bids[0].amount)
        self.assertEqual(1, len(snapshot_event.asks))
        self.assertEqual(11, snapshot_event.asks[0].price)
        self.assertEqual(3, snapshot_event.asks[0].amount)

    def test_minimum_delay_between_requests_for_snapshot_events(self):
        pass  # Dexalot streams the snapshots

    def test_maximum_delay_between_requests_for_snapshot_events(self):
        pass  # Dexalot streams the snapshots

    def test_get_last_traded_price(self):
        self.configure_last_traded_price(
            trading_pair=self.trading_pair, last_traded_price=self.expected_last_traded_price,
        )
        self.mocking_assistant.run_until_all_aiohttp_messages_delivered(
            websocket_mock=self.ws_connect_mock.return_value,
        )
        last_trade_price = self.async_run_with_timeout(
            coro=self.data_source.get_last_traded_price(trading_pair=self.trading_pair)
        )

        self.assertEqual(self.expected_last_traded_price, last_trade_price)

    def test_get_order_status_update_from_closed_order(self):
        creation_transaction_hash = "0x7cb2eafc389349f86da901cdcbfd9119425a2ea84d61c17b6ded778b6fd2g81d"  # noqa: mock
        in_flight_order = GatewayInFlightOrder(
            client_order_id=self.expected_sell_client_order_id,
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            creation_timestamp=self.initial_timestamp,
            price=self.expected_sell_order_price,
            amount=self.expected_sell_order_size,
            creation_transaction_hash=creation_transaction_hash,
            exchange_order_id=self.expected_buy_exchange_order_id,
        )
        self.enqueue_order_status_response(
            timestamp=self.initial_timestamp + 1,
            trading_pair=in_flight_order.trading_pair,
            exchange_order_id=self.expected_buy_exchange_order_id,
            client_order_id=in_flight_order.client_order_id,
            status=OrderState.FILLED,
        )

        status_update: OrderUpdate = self.async_run_with_timeout(
            coro=self.data_source.get_order_status_update(in_flight_order=in_flight_order)
        )

        self.assertEqual(self.trading_pair, status_update.trading_pair)
        self.assertEqual(self.initial_timestamp + 1, status_update.update_timestamp)
        self.assertEqual(OrderState.FILLED, status_update.new_state)
        self.assertEqual(in_flight_order.client_order_id, status_update.client_order_id)
        self.assertEqual(self.expected_buy_exchange_order_id, status_update.exchange_order_id)

    @patch(
        "hummingbot.connector.gateway.clob_spot.data_sources.gateway_clob_api_data_source_base"
        ".GatewayCLOBAPIDataSourceBase._sleep",
        new_callable=AsyncMock,
    )
    def test_batch_order_create_splits_order_by_max_order_create_per_batch(self, sleep_mock: AsyncMock):
        mock_max_order_create_per_batch = 2

        def sleep_mock_side_effect(delay):
            raise Exception

        sleep_mock.side_effect = sleep_mock_side_effect

        orders_to_create = []
        for i in range(mock_max_order_create_per_batch + 1):
            orders_to_create.append(
                GatewayInFlightOrder(
                    client_order_id=f"someCOID{i}",
                    trading_pair=self.trading_pair,
                    order_type=OrderType.LIMIT,
                    trade_type=TradeType.BUY,
                    creation_timestamp=self.initial_timestamp,
                    price=self.expected_buy_order_price + Decimal("1") * i,
                    amount=self.expected_buy_order_size,
                    exchange_order_id=hex(int(self.expected_buy_exchange_order_id, 16) + i),
                )
            )
        self.configure_batch_order_create_response(
            timestamp=self.initial_timestamp,
            transaction_hash=self.expected_transaction_hash,
            created_orders=orders_to_create,
        )

        for order in orders_to_create:
            order.exchange_order_id = None  # the orders are new

        CONSTANTS.MAX_ORDER_CREATIONS_PER_BATCH = mock_max_order_create_per_batch
        result: List[PlaceOrderResult] = self.async_run_with_timeout(
            coro=self.data_source.batch_order_create(orders_to_create=orders_to_create)
        )

        self.assertEqual(len(orders_to_create), len(result))
        self.assertEqual(
            math.ceil(len(orders_to_create) / mock_max_order_create_per_batch),
            len(self.gateway_instance_mock.clob_batch_order_modify.mock_calls),
        )

        first_call = self.gateway_instance_mock.clob_batch_order_modify.mock_calls[0]
        second_call = self.gateway_instance_mock.clob_batch_order_modify.mock_calls[1]

        self.assertEqual(
            orders_to_create[:mock_max_order_create_per_batch], first_call.kwargs["orders_to_create"]
        )
        self.assertEqual(
            orders_to_create[mock_max_order_create_per_batch:], second_call.kwargs["orders_to_create"]
        )

    @patch(
        "hummingbot.connector.gateway.clob_spot.data_sources.gateway_clob_api_data_source_base"
        ".GatewayCLOBAPIDataSourceBase._sleep",
        new_callable=AsyncMock,
    )
    def test_batch_order_cancel_splits_order_by_max_order_cancel_per_batch(self, sleep_mock: AsyncMock):
        mock_max_order_cancelations_per_batch = 2

        orders_to_cancel = []
        for i in range(mock_max_order_cancelations_per_batch + 1):
            orders_to_cancel.append(
                GatewayInFlightOrder(
                    client_order_id=f"someCOID{i}",
                    trading_pair=self.trading_pair,
                    order_type=OrderType.LIMIT,
                    trade_type=TradeType.BUY,
                    creation_timestamp=self.initial_timestamp,
                    price=self.expected_buy_order_price + Decimal("1") * i,
                    amount=self.expected_buy_order_size,
                    exchange_order_id=hex(int(self.expected_buy_exchange_order_id, 16) + i),
                    creation_transaction_hash=f"someCreationHash{i}"
                )
            )
            self.data_source.gateway_order_tracker.start_tracking_order(order=orders_to_cancel[-1])
        self.configure_batch_order_cancel_response(
            timestamp=self.initial_timestamp,
            transaction_hash=self.expected_transaction_hash,
            canceled_orders=orders_to_cancel,
        )

        CONSTANTS.MAX_ORDER_CANCELATIONS_PER_BATCH = mock_max_order_cancelations_per_batch
        result: List[PlaceOrderResult] = self.async_run_with_timeout(
            coro=self.data_source.batch_order_cancel(orders_to_cancel=orders_to_cancel)
        )

        self.assertEqual(len(orders_to_cancel), len(result))
        self.assertEqual(
            math.ceil(len(orders_to_cancel) / mock_max_order_cancelations_per_batch),
            len(self.gateway_instance_mock.clob_batch_order_modify.mock_calls),
        )

        first_call = self.gateway_instance_mock.clob_batch_order_modify.mock_calls[0]
        second_call = self.gateway_instance_mock.clob_batch_order_modify.mock_calls[1]

        self.assertEqual(
            orders_to_cancel[:mock_max_order_cancelations_per_batch], first_call.kwargs["orders_to_cancel"]
        )
        self.assertEqual(
            orders_to_cancel[mock_max_order_cancelations_per_batch:], second_call.kwargs["orders_to_cancel"]
        )
