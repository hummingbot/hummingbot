import asyncio
import json
import math
import re
from decimal import Decimal
from typing import Any, Dict, List, Union
from unittest.mock import AsyncMock, patch

import pandas as pd
from aioresponses import aioresponses

from hummingbot.connector.gateway.clob_spot.data_sources.dexalot import dexalot_constants as CONSTANTS
from hummingbot.connector.gateway.clob_spot.data_sources.dexalot.dexalot_api_data_source import DexalotAPIDataSource
from hummingbot.connector.gateway.clob_spot.data_sources.dexalot.dexalot_constants import (
    HB_TO_DEXALOT_NUMERIC_STATUS_MAP,
    HB_TO_DEXALOT_STATUS_MAP,
)
from hummingbot.connector.gateway.gateway_in_flight_order import GatewayInFlightOrder
from hummingbot.connector.test_support.gateway_clob_api_data_source_test import AbstractGatewayCLOBAPIDataSourceTests
from hummingbot.connector.test_support.network_mocking_assistant import NetworkMockingAssistant
from hummingbot.connector.utils import split_hb_trading_pair
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import OrderState, OrderUpdate
from hummingbot.core.data_type.trade_fee import TradeFeeBase


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

    def setUp(self) -> None:
        self.domain = "dexalot"
        self.mock_api = aioresponses()
        self.mock_api.start()
        self.get_api_key_patch = patch(
            target=(
                "hummingbot.connector.gateway.clob_spot.data_sources.dexalot.dexalot_api_data_source"
                ".DexalotAPIDataSource._get_api_key"
            ),
            autospec=True,
        )
        self.get_api_key_mock = self.get_api_key_patch.start()
        self.api_key_mock = "someAPIKey"
        self.wallet_sign_mock = "DD5113FEDED638E5500E65779613BDD3BDDBEB8EB5D86CDD3370E629B02E92CD"  # noqa: mock
        self.get_api_key_mock.return_value = self.api_key_mock

        self.mocking_assistant = NetworkMockingAssistant()
        super().setUp()
        self.configure_signature_response()
        self.configure_ws_auth_response()

    def tearDown(self) -> None:
        self.mock_api.stop()
        self.get_api_key_patch.stop()
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
                "baseDecimals": 18,
                "baseDisplayDecimals": int(math.log10(1 / self.expected_min_price_increment)),
                "quoteDecimals": 16,
                "quoteDisplayDecimals": 3,
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

    def configure_last_traded_price(
        self, trading_pair: str, last_traded_price: Decimal, mock_ws: NetworkMockingAssistant
    ):
        mock_ws.return_value = self.mocking_assistant.create_websocket_mock()
        resp = {"data": [{"execId": 1675046315,
                          "price": str(self.expected_last_traded_price),
                          "quantity": "951.14",
                          "takerSide": 1,
                          "ts": "2023-03-07T14:17:52.000Z"}],
                "pair": self.exchange_trading_pair,
                "type": "lastTrade"}
        self.mocking_assistant.add_websocket_aiohttp_message(
            mock_ws.return_value, json.dumps(resp)
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
            if status != OrderState.OPEN:  # the order is not new and it will have exchange order ID
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
            else:  # order is being created and it doesn"t have an exchange order ID
                regex_url = re.compile(f"^{base_url}?".replace(".", r"\.").replace("?", r"\?"))
                response = {
                    "count": len(orders),
                    "rows": [
                        self.get_order_status_response_row(
                            timestamp=timestamp,
                            trading_pair=order.trading_pair,
                            exchange_order_id=order.exchange_order_id or "",
                            client_order_id=order.client_order_id,
                            status=status,
                        ) for order, status in zip(orders, statuses)
                    ]
                }

            callback = None if i != len(orders) - 1 else lambda *_, **__: update_delivered_event.set()
            self.mock_api.get(regex_url, body=json.dumps(response), callback=callback)

        return update_delivered_event

    def get_order_status_response_row(
        self,
        timestamp: float,
        trading_pair: str,
        exchange_order_id: str,
        client_order_id: str,
        status: OrderState,
    ):
        dexalot_timestamp_str = pd.Timestamp.utcfromtimestamp(timestamp).strftime(format="%Y-%m-%dT%H:%M:%S") + ".000Z"
        return {
            "clientordid": client_order_id,
            "env": "production-multi-subnet",
            "id": exchange_order_id,
            "pair": self.exchange_trading_pair_from_hb_trading_pair(trading_pair=trading_pair),
            "price": "17.570000000000000000",
            "quantity": "1.500000000000000000",
            "quantityfilled": "0.000000000000000000",
            "side": 0,  # buy
            "status": HB_TO_DEXALOT_NUMERIC_STATUS_MAP[status],
            "totalamount": "26.355000000000000000",
            "totalfee": "0.070000000000000000",
            "traderaddress": self.account_id,
            "ts": dexalot_timestamp_str,
            "tx": "0xa0b9af42887ddafcf80e94412601ca6b6850d3b8c7b5295ddeb2d98aee5f1c84",  # noqa: mock
            "type": 1,  # limit
            "type2": 0,  # GTC
            "update_ts": dexalot_timestamp_str,
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

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_get_last_traded_price(self, mock_ws: AsyncMock):
        self.configure_last_traded_price(
            trading_pair=self.trading_pair,
            last_traded_price=self.expected_last_traded_price,
            mock_ws=mock_ws,
        )
        self.mocking_assistant.run_until_all_aiohttp_messages_delivered(
            websocket_mock=mock_ws.return_value,
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
