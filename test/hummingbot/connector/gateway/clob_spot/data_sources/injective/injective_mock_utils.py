import asyncio
import json
from decimal import Decimal
from typing import Any, List, Optional, Tuple, Type
from unittest.mock import AsyncMock, patch

import grpc
import pandas as pd
from pyinjective.orderhash import OrderHashResponse
from pyinjective.proto.exchange.injective_accounts_rpc_pb2 import (
    StreamSubaccountBalanceResponse,
    SubaccountBalance,
    SubaccountDeposit as Account_SubaccountDeposit,
)
from pyinjective.proto.exchange.injective_explorer_rpc_pb2 import (
    CosmosCoin,
    GasFee,
    GetTxByTxHashResponse,
    StreamTxsResponse,
    TxDetailData,
)
from pyinjective.proto.exchange.injective_portfolio_rpc_pb2 import (
    AccountPortfolioResponse,
    Coin,
    Portfolio,
    SubaccountBalanceV2,
    SubaccountDeposit,
)
from pyinjective.proto.exchange.injective_spot_exchange_rpc_pb2 import (
    MarketsResponse,
    OrderbooksV2Response,
    OrdersHistoryResponse,
    Paging,
    PriceLevel,
    SingleSpotLimitOrderbookV2,
    SpotLimitOrderbookV2,
    SpotMarketInfo,
    SpotOrderHistory,
    SpotTrade,
    StreamOrderbookV2Response,
    StreamOrdersHistoryResponse,
    StreamTradesResponse,
    TokenMeta,
    TradesResponse,
)

from hummingbot.connector.constants import s_decimal_0
from hummingbot.connector.gateway.clob_spot.data_sources.injective.injective_constants import (
    BASE_GAS,
    GAS_BUFFER,
    SPOT_CANCEL_ORDER_GAS,
    SPOT_SUBMIT_ORDER_GAS,
)
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder
from hummingbot.core.data_type.trade_fee import TradeFeeBase


class StreamMock:
    def __init__(self):
        self.queue = asyncio.Queue()

    def add(self, item: Any):
        self.queue.put_nowait(item=item)

    def run_until_all_items_delivered(self, timeout: float = 1):
        asyncio.get_event_loop().run_until_complete(asyncio.wait_for(fut=self.queue.join(), timeout=timeout))

    def cancel(self):
        pass

    def __aiter__(self):
        return self

    async def __anext__(self):
        el = await self.queue.get()
        self.queue.task_done()
        return el


class InjectiveClientMock:
    def __init__(
        self, initial_timestamp: float, sub_account_id: str, base: str, quote: str,
    ):
        self.initial_timestamp = initial_timestamp
        self.base = base
        self.base_coin_address = "someBaseCoinAddress"
        self.base_denom = self.base_coin_address
        self.base_decimals = 18
        self.quote = quote
        self.quote_coin_address = "someQuoteCoinAddress"
        self.quote_denom = self.quote_coin_address
        self.quote_decimals = 8  # usually set to 6, but for the sake of differing minimum price/size increments
        self.market_id = "someMarketId"
        self.sub_account_id = sub_account_id
        self.service_provider_fee = Decimal("0.4")
        self.order_creation_gas_estimate = Decimal("0.0000825")
        self.order_cancelation_gas_estimate = Decimal("0.0000725")
        self.order_gas_estimate = Decimal("0.000155")  # gas to both submit and cancel an order in INJ

        self.injective_async_client_mock_patch = patch(
            target=(
                "hummingbot.connector.gateway.clob_spot.data_sources.injective.injective_api_data_source.AsyncClient"
            ),
            autospec=True,
        )
        self.injective_async_client_mock: Optional[AsyncMock] = None
        self.gateway_instance_mock_patch = patch(
            target=(
                "hummingbot.connector.gateway.clob_spot.data_sources.injective.injective_api_data_source"
                ".GatewayHttpClient"
            ),
            autospec=True,
        )
        self.gateway_instance_mock: Optional[AsyncMock] = None
        self.injective_order_hash_manager_start_patch = patch(
            target=(
                "hummingbot.connector.gateway.clob_spot.data_sources.injective.injective_api_data_source"
                ".OrderHashManager.start"
            ),
            autospec=True,
        )
        self.injective_composer_patch = patch(
            target="hummingbot.connector.gateway.clob_spot.data_sources.injective.injective_api_data_source"
                   ".ProtoMsgComposer",
            autospec=True,
        )
        self.injective_compute_order_hashes_patch = patch(
            target=(
                "hummingbot.connector.gateway.clob_spot.data_sources.injective.injective_api_data_source"
                ".OrderHashManager.compute_order_hashes"
            ),
            autospec=True,
        )
        self.injective_compute_order_hashes_mock: Optional[AsyncMock] = None

        self.place_order_called_event = asyncio.Event()
        self.cancel_order_called_event = asyncio.Event()

    @property
    def min_quantity_tick_size(self) -> Decimal:
        return Decimal("0.001")

    @property
    def min_price_tick_size(self) -> Decimal:
        return Decimal("0.00001")

    @property
    def maker_fee_rate(self) -> Decimal:
        return Decimal("-0.0001")

    @property
    def taker_fee_rate(self) -> Decimal:
        return Decimal("0.001")

    @property
    def exchange_trading_pair(self) -> str:
        return self.market_id

    def start(self):
        self.injective_async_client_mock = self.injective_async_client_mock_patch.start()
        self.injective_async_client_mock.return_value = self.injective_async_client_mock
        self.gateway_instance_mock = self.gateway_instance_mock_patch.start()
        self.gateway_instance_mock.get_instance.return_value = self.gateway_instance_mock
        self.injective_order_hash_manager_start_patch.start()
        self.injective_composer_patch.start()
        self.injective_compute_order_hashes_mock = self.injective_compute_order_hashes_patch.start()

        self.injective_async_client_mock.stream_spot_trades.return_value = StreamMock()
        self.injective_async_client_mock.stream_historical_spot_orders.return_value = StreamMock()
        self.injective_async_client_mock.stream_spot_orderbook_snapshot.return_value = StreamMock()
        self.injective_async_client_mock.stream_account_portfolio.return_value = StreamMock()
        self.injective_async_client_mock.stream_subaccount_balance.return_value = StreamMock()
        self.injective_async_client_mock.stream_txs.return_value = StreamMock()

        self.configure_active_spot_markets_response(timestamp=self.initial_timestamp)

    def stop(self):
        self.injective_async_client_mock_patch.stop()
        self.gateway_instance_mock_patch.stop()
        self.injective_order_hash_manager_start_patch.stop()
        self.injective_composer_patch.stop()
        self.injective_compute_order_hashes_patch.stop()

    def run_until_all_items_delivered(self, timeout: float = 1):
        self.injective_async_client_mock.stream_spot_trades.return_value.run_until_all_items_delivered(timeout=timeout)
        self.injective_async_client_mock.stream_historical_spot_orders.return_value.run_until_all_items_delivered(
            timeout=timeout
        )
        self.injective_async_client_mock.stream_spot_orderbooks.return_value.run_until_all_items_delivered(
            timeout=timeout
        )
        self.injective_async_client_mock.stream_subaccount_balance.return_value.run_until_all_items_delivered(
            timeout=timeout
        )
        self.injective_async_client_mock.stream_txs.return_value.run_until_all_items_delivered(
            timeout=timeout
        )

    def run_until_place_order_called(self, timeout: float = 1):
        asyncio.get_event_loop().run_until_complete(
            asyncio.wait_for(fut=self.place_order_called_event.wait(), timeout=timeout)
        )

    def run_until_cancel_order_called(self, timeout: float = 1):
        asyncio.get_event_loop().run_until_complete(
            asyncio.wait_for(fut=self.cancel_order_called_event.wait(), timeout=timeout)
        )

    def configure_batch_order_create_response(
        self,
        timestamp: int,
        transaction_hash: str,
        created_orders: List[InFlightOrder],
    ):
        def update_and_return(*_, **__):
            self.place_order_called_event.set()
            return {
                "network": "injective",
                "timestamp": timestamp,
                "latency": 2,
                "txHash": transaction_hash if not transaction_hash.startswith("0x") else transaction_hash[2:],
            }

        self.gateway_instance_mock.clob_batch_order_modify.side_effect = update_and_return
        self.configure_get_tx_by_hash_creation_response(
            timestamp=timestamp, success=True, order_hashes=[order.exchange_order_id for order in created_orders]
        )
        for order in created_orders:
            self.configure_get_historical_spot_orders_response_for_in_flight_order(
                timestamp=timestamp,
                in_flight_order=order,
            )
        self.injective_compute_order_hashes_mock.return_value = OrderHashResponse(
            spot=[order.exchange_order_id for order in created_orders], derivative=[]
        )

    def configure_batch_order_cancel_response(
        self,
        timestamp: int,
        transaction_hash: str,
        canceled_orders: List[InFlightOrder],
    ):
        def update_and_return(*_, **__):
            self.place_order_called_event.set()
            return {
                "network": "injective",
                "timestamp": timestamp,
                "latency": 2,
                "txHash": transaction_hash if not transaction_hash.startswith("0x") else transaction_hash[2:],
            }

        self.gateway_instance_mock.clob_batch_order_modify.side_effect = update_and_return
        for order in canceled_orders:
            self.configure_get_historical_spot_orders_response_for_in_flight_order(
                timestamp=timestamp,
                in_flight_order=order,
                is_canceled=True,
            )

    def configure_place_order_response(
        self,
        timestamp: int,
        transaction_hash: str,
        exchange_order_id: str,
        trade_type: TradeType,
        price: Decimal,
        size: Decimal,
    ):

        def place_and_return(*_, **__):
            self.place_order_called_event.set()
            return {
                "network": "injective",
                "timestamp": timestamp,
                "latency": 2,
                "txHash": transaction_hash[2:].lower(),
            }

        self.gateway_instance_mock.clob_place_order.side_effect = place_and_return
        self.configure_get_tx_by_hash_creation_response(
            timestamp=timestamp, success=True, order_hashes=[exchange_order_id]
        )
        self.configure_get_historical_spot_orders_response(
            timestamp=timestamp,
            order_hash=exchange_order_id,
            state="booked",
            execution_type="limit",
            order_type="buy" if trade_type == TradeType.BUY else "sell",
            price=price,
            size=size,
            filled_size=Decimal("0"),
            direction="buy" if trade_type == TradeType.BUY else "sell",
        )
        self.injective_compute_order_hashes_mock.return_value = OrderHashResponse(
            spot=[exchange_order_id], derivative=[]
        )

    def configure_place_order_fails_response(self, exception: Exception):

        def place_and_raise(*_, **__):
            self.place_order_called_event.set()
            raise exception

        self.gateway_instance_mock.clob_place_order.side_effect = place_and_raise

    def configure_cancel_order_response(self, timestamp: int, transaction_hash: str):

        def cancel_and_return(*_, **__):
            self.cancel_order_called_event.set()
            return {
                "network": "injective",
                "timestamp": timestamp,
                "latency": 2,
                "txHash": transaction_hash if not transaction_hash.startswith("0x") else transaction_hash[2:],
            }

        self.gateway_instance_mock.clob_cancel_order.side_effect = cancel_and_return

    def configure_cancel_order_fails_response(self, exception: Exception):

        def cancel_and_raise(*_, **__):
            self.cancel_order_called_event.set()
            raise exception

        self.gateway_instance_mock.clob_cancel_order.side_effect = cancel_and_raise

    def configure_one_success_one_failure_order_cancelation_responses(
        self, success_timestamp: int, success_transaction_hash: str, failure_exception: Exception,
    ):
        called_once = False

        def cancel_and_return(*_, **__):
            nonlocal called_once
            if called_once:
                self.cancel_order_called_event.set()
                raise failure_exception
            called_once = True
            return {
                "network": "injective",
                "timestamp": success_timestamp,
                "latency": 2,
                "txHash": success_transaction_hash,
            }

        self.gateway_instance_mock.clob_cancel_order.side_effect = cancel_and_return

    def configure_check_network_success(self):
        self.injective_async_client_mock.ping.side_effect = None

    def configure_check_network_failure(self, exc: Type[Exception] = grpc.RpcError):
        self.injective_async_client_mock.ping.side_effect = exc

    def configure_order_status_update_response(
        self,
        timestamp: int,
        order: InFlightOrder,
        creation_transaction_hash: Optional[str] = None,
        creation_transaction_success: bool = True,
        cancelation_transaction_hash: Optional[str] = None,
        filled_size: Decimal = s_decimal_0,
        is_canceled: bool = False,
        is_failed: bool = False,
    ):
        exchange_order_id = order.exchange_order_id
        if creation_transaction_hash is not None:
            if creation_transaction_success:
                self.configure_creation_transaction_stream_event(
                    timestamp=timestamp, transaction_hash=creation_transaction_hash
                )
            self.configure_get_tx_by_hash_creation_response(
                timestamp=timestamp,
                success=creation_transaction_success,
                order_hashes=[exchange_order_id],
                transaction_hash=creation_transaction_hash,
                is_order_failed=is_failed,
            )
        if cancelation_transaction_hash is not None:
            self.configure_cancelation_transaction_stream_event(
                timestamp=timestamp,
                transaction_hash=cancelation_transaction_hash,
                order_hash=exchange_order_id,
            )
            self.configure_get_tx_by_hash_cancelation_response(
                timestamp=timestamp,
                order_hash=exchange_order_id,
                transaction_hash=cancelation_transaction_hash,
            )
        if is_failed:
            self.configure_get_historical_spot_orders_empty_response()
        elif not is_canceled:
            self.configure_get_historical_spot_orders_response_for_in_flight_order(
                timestamp=timestamp,
                in_flight_order=order,
                order_hash=exchange_order_id,
                filled_size=filled_size,
            )
        else:
            self.configure_get_historical_spot_orders_response_for_in_flight_order(
                timestamp=timestamp, in_flight_order=order, is_canceled=True
            )

    def configure_trades_response_with_exchange_order_id(
        self,
        timestamp: float,
        exchange_order_id: str,
        price: Decimal,
        size: Decimal,
        fee: TradeFeeBase,
        trade_id: str,
    ):
        """This method appends mocks if previously queued mocks already exist."""
        timestamp_ms = int(timestamp * 1e3)
        scaled_price = price * Decimal(f"1e{self.quote_decimals - self.base_decimals}")
        scaled_size = size * Decimal(f"1e{self.base_decimals}")
        price_level = PriceLevel(
            price=str(scaled_price), quantity=str(scaled_size), timestamp=timestamp_ms
        )
        scaled_fee = fee.flat_fees[0].amount * Decimal(f"1e{self.quote_decimals}")
        trade = SpotTrade(
            order_hash=exchange_order_id,
            subaccount_id=self.sub_account_id,
            market_id=self.market_id,
            trade_execution_type="limitMatchNewOrder",
            trade_direction="buy",
            price=price_level,
            fee=str(scaled_fee),
            executed_at=timestamp_ms,
            fee_recipient="anotherRecipientAddress",
            trade_id=trade_id,
            execution_side="taker",
        )
        trades = TradesResponse()
        trades.trades.append(trade)

        if self.injective_async_client_mock.get_spot_trades.side_effect is None:
            self.injective_async_client_mock.get_spot_trades.side_effect = [trades, TradesResponse()]
        else:
            self.injective_async_client_mock.get_spot_trades.side_effect = (
                list(self.injective_async_client_mock.get_spot_trades.side_effect) + [trades, TradesResponse()]
            )

    def configure_trades_response_no_trades(self):
        """This method appends mocks if previously queued mocks already exist."""
        trades = TradesResponse()

        if self.injective_async_client_mock.get_spot_trades.side_effect is None:
            self.injective_async_client_mock.get_spot_trades.side_effect = [trades, TradesResponse()]
        else:
            self.injective_async_client_mock.get_spot_trades.side_effect = (
                list(self.injective_async_client_mock.get_spot_trades.side_effect) + [trades, TradesResponse()]
            )

    def configure_trades_response_fails(self):
        self.injective_async_client_mock.get_spot_trades.side_effect = RuntimeError

    def configure_order_stream_event_for_in_flight_order(
        self,
        timestamp: float,
        in_flight_order: InFlightOrder,
        filled_size: Decimal = Decimal("0"),
        is_canceled: bool = False,
    ):
        if is_canceled:
            state = "canceled"
        elif filled_size == Decimal("0"):
            state = "booked"
        elif filled_size == in_flight_order.amount:
            state = "filled"
        else:
            state = "partial_filled"
        self.configure_order_stream_event(
            timestamp=timestamp,
            order_hash=in_flight_order.exchange_order_id,
            state=state,
            execution_type="market" if in_flight_order.order_type == OrderType.MARKET else "limit",
            order_type=(
                in_flight_order.trade_type.name.lower()
                + ("_po" if in_flight_order.order_type == OrderType.LIMIT_MAKER else "")
            ),
            price=in_flight_order.price,
            size=in_flight_order.amount,
            filled_size=filled_size,
            direction=in_flight_order.trade_type.name.lower(),
        )

    def configure_trade_stream_event(
        self,
        timestamp: float,
        price: Decimal,
        size: Decimal,
        maker_fee: TradeFeeBase,
        taker_fee: TradeFeeBase,
        exchange_order_id: str = "0x6df823e0adc0d4811e8d25d7380c1b45e43b16b0eea6f109cc1fb31d31aeddc7",  # noqa: mock
        taker_trade_id: str = "19889401_someTradeId",
    ):
        """The taker is a buy."""
        maker_trade, taker_trade = self.get_maker_taker_trades_pair(
            timestamp=timestamp,
            price=price,
            size=size,
            maker_fee=maker_fee.flat_fees[0].amount,
            taker_fee=taker_fee.flat_fees[0].amount,
            order_hash=exchange_order_id,
            taker_trade_id=taker_trade_id,
        )
        maker_trade_response = StreamTradesResponse(trade=maker_trade)
        taker_trade_response = StreamTradesResponse(trade=taker_trade)
        self.injective_async_client_mock.stream_spot_trades.return_value.add(maker_trade_response)
        self.injective_async_client_mock.stream_spot_trades.return_value.add(taker_trade_response)

    def configure_account_base_balance_stream_event(
        self, timestamp: float, total_balance: Decimal, available_balance: Decimal
    ):
        timestamp_ms = int(timestamp * 1e3)
        deposit = Account_SubaccountDeposit(
            total_balance=str(total_balance * Decimal(f"1e{self.base_decimals}")),
            available_balance=str(available_balance * Decimal(f"1e{self.base_decimals}")),
        )
        balance = SubaccountBalance(
            subaccount_id=self.sub_account_id,
            account_address="someAccountAddress",
            denom=self.base_denom,
            deposit=deposit,
        )
        balance_event = StreamSubaccountBalanceResponse(
            balance=balance,
            timestamp=timestamp_ms,
        )
        self.injective_async_client_mock.stream_subaccount_balance.return_value.add(balance_event)

        self.configure_get_account_balances_response(
            quote_total_balance=total_balance, quote_available_balance=available_balance,
        )

    def configure_faulty_base_balance_stream_event(self, timestamp: float):
        timestamp_ms = int(timestamp * 1e3)
        deposit = Account_SubaccountDeposit(
            total_balance="",
            available_balance="",
        )
        balance = SubaccountBalance(
            subaccount_id=self.sub_account_id,
            account_address="someAccountAddress",
            denom="wrongCoinAddress",
            deposit=deposit,
        )
        balance_event = StreamSubaccountBalanceResponse(
            balance=balance,
            timestamp=timestamp_ms,
        )
        self.injective_async_client_mock.stream_subaccount_balance.return_value.add(balance_event)

    def configure_spot_trades_response_to_request_without_exchange_order_id(
        self,
        timestamp: float,
        price: Decimal,
        size: Decimal,
        maker_fee: TradeFeeBase,
        taker_fee: TradeFeeBase,
    ):
        """The taker is a buy."""
        maker_trade, taker_trade = self.get_maker_taker_trades_pair(
            timestamp=timestamp,
            price=price,
            size=size,
            maker_fee=maker_fee.flat_fees[0].amount,
            taker_fee=taker_fee.flat_fees[0].amount,
        )
        trades = TradesResponse()
        trades.trades.append(maker_trade)
        trades.trades.append(taker_trade)

        self.injective_async_client_mock.get_spot_trades.return_value = trades

    def configure_orderbook_snapshot(
        self, timestamp: float, bids: List[Tuple[float, float]], asks: List[Tuple[float, float]],
    ):
        timestamp_ms = int(timestamp * 1e3)
        orderbook = self.create_orderbook_mock(timestamp_ms=timestamp_ms, bids=bids, asks=asks)
        single_orderbook = SingleSpotLimitOrderbookV2(market_id=self.market_id, orderbook=orderbook)
        orderbook_response = OrderbooksV2Response()
        orderbook_response.orderbooks.append(single_orderbook)

        self.injective_async_client_mock.get_spot_orderbooksV2.return_value = orderbook_response

    def configure_orderbook_snapshot_stream_event(
        self, timestamp: float, bids: List[Tuple[float, float]], asks: List[Tuple[float, float]]
    ):
        timestamp_ms = int(timestamp * 1e3)
        orderbook = self.create_orderbook_mock(timestamp_ms=timestamp_ms, bids=bids, asks=asks)
        orderbook_response = StreamOrderbookV2Response(
            orderbook=orderbook,
            operation_type="update",
            timestamp=timestamp_ms,
            market_id=self.market_id,
        )

        self.injective_async_client_mock.stream_spot_orderbook_snapshot.return_value.add(orderbook_response)

    def create_orderbook_mock(
        self, timestamp_ms: float, bids: List[Tuple[float, float]], asks: List[Tuple[float, float]]
    ) -> SpotLimitOrderbookV2:
        orderbook = SpotLimitOrderbookV2()

        for price, size in bids:
            scaled_price = price * Decimal(f"1e{self.quote_decimals - self.base_decimals}")
            scaled_size = size * Decimal(f"1e{self.base_decimals}")
            bid = PriceLevel(
                price=str(scaled_price), quantity=str(scaled_size), timestamp=timestamp_ms
            )
            orderbook.buys.append(bid)

        for price, size in asks:
            scaled_price = price * Decimal(f"1e{self.quote_decimals - self.base_decimals}")
            scaled_size = size * Decimal(f"1e{self.base_decimals}")
            ask = PriceLevel(
                price=str(scaled_price), quantity=str(scaled_size), timestamp=timestamp_ms
            )
            orderbook.sells.append(ask)

        return orderbook

    def get_maker_taker_trades_pair(
        self,
        timestamp: float,
        price: Decimal,
        size: Decimal,
        maker_fee: Decimal,
        taker_fee: Decimal,
        order_hash: str = "0x6df823e0adc0d4811e8d25d7380c1b45e43b16b0eea6f109cc1fb31d31aeddc7",  # noqa: mock
        taker_trade_id: str = "19889401_someTradeId",
    ) -> Tuple[SpotTrade, SpotTrade]:
        """The taker is a buy."""
        timestamp_ms = int(timestamp * 1e3)
        scaled_price = price * Decimal(f"1e{self.quote_decimals - self.base_decimals}")
        scaled_size = size * Decimal(f"1e{self.base_decimals}")
        price_level = PriceLevel(
            price=str(scaled_price), quantity=str(scaled_size), timestamp=timestamp_ms
        )
        scaled_maker_fee = maker_fee * Decimal(f"1e{self.quote_decimals}")
        scaled_taker_fee = taker_fee * Decimal(f"1e{self.quote_decimals}")
        assert len(taker_trade_id.split("_")) == 2
        trade_id_prefix = taker_trade_id.split("_")[0]
        taker_trade = SpotTrade(
            order_hash=order_hash,
            subaccount_id="sumSubAccountId",
            market_id=self.market_id,
            trade_execution_type="limitMatchNewOrder",
            trade_direction="buy",
            price=price_level,
            fee=str(scaled_taker_fee),
            executed_at=timestamp_ms,
            fee_recipient="anotherRecipientAddress",
            trade_id=taker_trade_id,
            execution_side="taker",
        )
        maker_trade = SpotTrade(
            order_hash="anotherOrderHash",
            subaccount_id="anotherSubAccountId",
            market_id=self.market_id,
            trade_execution_type="limitMatchRestingOrder",
            trade_direction="sell",
            price=price_level,
            fee=str(scaled_maker_fee),
            executed_at=timestamp_ms,
            fee_recipient="someRecipientAddress",
            trade_id=f"{trade_id_prefix}_anotherTradeId",  # trade IDs for each side have same prefix, different suffix
            execution_side="maker",
        )
        return maker_trade, taker_trade

    def configure_order_stream_event(
        self,
        timestamp: float,
        order_hash: str,
        state: str,
        execution_type: str,
        order_type: str,
        price: Decimal,
        size: Decimal,
        filled_size: Decimal,
        direction: str,
    ):
        """
        order {
          order_hash: "0x6df823e0adc0d4811e8d25d7380c1b45e43b16b0eea6f109cc1fb31d31aeddc7"  # noqa: documentation
          market_id: "0xd1956e20d74eeb1febe31cd37060781ff1cb266f49e0512b446a5fafa9a16034"  # noqa: documentation
          subaccount_id: "0x32b16783ea9a08602dc792f24c3d78bba6e333d3000000000000000000000000"  # noqa: documentation
          execution_type: "limit"
          order_type: "buy_po"
          price: "0.00000000116023"
          trigger_price: "0"
          quantity: "2000000000000000"
          filled_quantity: "0"
          state: "canceled"
          created_at: 1669198777253
          updated_at: 1669198783253
          direction: "buy"
        }
        operation_type: "update"
        timestamp: 1669198784000
        """
        order = self.get_spot_order_history(
            timestamp=timestamp,
            order_hash=order_hash,
            state=state,
            execution_type=execution_type,
            order_type=order_type,
            price=price,
            size=size,
            filled_size=filled_size,
            direction=direction,
        )
        timestamp_ms = int(timestamp * 1e3)
        order_response = StreamOrdersHistoryResponse(
            order=order,
            operation_type="update",
            timestamp=timestamp_ms,
        )
        self.injective_async_client_mock.stream_historical_spot_orders.return_value.add(order_response)

    def configure_get_historical_spot_orders_response_for_in_flight_order(
        self,
        timestamp: float,
        in_flight_order: InFlightOrder,
        filled_size: Decimal = Decimal("0"),
        is_canceled: bool = False,
        order_hash: Optional[str] = None,  # overwrites in_flight_order.exchange_order_id
    ):
        """
        orders {
          order_hash: "0x0f62edfb64644762c20490d9573034c2f319e87e857401c41eea1fe373045dd7"  # noqa: documentation
          market_id: "0xa508cb32923323679f29a032c70342c147c17d0145625922b0ef22e955c844c0"  # noqa: documentation
          subaccount_id: "0x1b99514e320ae0087be7f87b1e3057853c43b799000000000000000000000000"  # noqa: documentation
          execution_type: "limit"
          order_type: "sell_po"
          price: "1887550000"
          trigger_price: "0"
          quantity: "14.66"
          filled_quantity: "0"
          state: "canceled"
          created_at: 1660245368028
          updated_at: 1660245374789
          direction: "sell"
        }
        paging {
          total: 1000
        }
        """
        if is_canceled:
            state = "canceled"
        elif filled_size == Decimal("0"):
            state = "booked"
        elif filled_size == in_flight_order.amount:
            state = "filled"
        else:
            state = "partial_filled"
        self.configure_get_historical_spot_orders_response(
            timestamp=timestamp,
            order_hash=order_hash or in_flight_order.exchange_order_id,
            state=state,
            execution_type="market" if in_flight_order.order_type == OrderType.MARKET else "limit",
            order_type=(
                in_flight_order.trade_type.name.lower()
                + ("_po" if in_flight_order.order_type == OrderType.LIMIT_MAKER else "")
            ),
            price=in_flight_order.price,
            size=in_flight_order.amount,
            filled_size=filled_size,
            direction=in_flight_order.trade_type.name.lower(),
        )

    def configure_get_historical_spot_orders_empty_response(self):
        paging = Paging(total=1)
        mock_response = OrdersHistoryResponse(paging=paging)
        self.injective_async_client_mock.get_historical_spot_orders.return_value = mock_response

    def configure_get_historical_spot_orders_response(
        self,
        timestamp: float,
        order_hash: str,
        state: str,
        execution_type: str,
        order_type: str,
        price: Decimal,
        size: Decimal,
        filled_size: Decimal,
        direction: str,
    ):
        """
        orders {
          order_hash: "0x0f62edfb64644762c20490d9573034c2f319e87e857401c41eea1fe373045dd7"  # noqa: documentation
          market_id: "0xa508cb32923323679f29a032c70342c147c17d0145625922b0ef22e955c844c0"  # noqa: documentation
          subaccount_id: "0x1b99514e320ae0087be7f87b1e3057853c43b799000000000000000000000000"  # noqa: documentation
          execution_type: "limit"
          order_type: "sell_po"
          price: "1887550000"
          trigger_price: "0"
          quantity: "14.66"
          filled_quantity: "0"
          state: "canceled"
          created_at: 1660245368028
          updated_at: 1660245374789
          direction: "sell"
        }
        paging {
          total: 1000
        }
        """
        order = self.get_spot_order_history(
            timestamp=timestamp,
            order_hash=order_hash,
            state=state,
            execution_type=execution_type,
            order_type=order_type,
            price=price,
            size=size,
            filled_size=filled_size,
            direction=direction,
        )
        paging = Paging(total=1)
        mock_response = OrdersHistoryResponse(paging=paging)
        mock_response.orders.append(order)
        self.injective_async_client_mock.get_historical_spot_orders.return_value = mock_response

    def configure_account_quote_balance_stream_event(
        self, timestamp: float, total_balance: Decimal, available_balance: Decimal
    ):
        timestamp_ms = int(timestamp * 1e3)
        deposit = Account_SubaccountDeposit(
            total_balance=str(total_balance * Decimal(f"1e{self.quote_decimals}")),
            available_balance=str(available_balance * Decimal(f"1e{self.quote_decimals}")),
        )
        balance = SubaccountBalance(
            subaccount_id=self.sub_account_id,
            account_address="someAccountAddress",
            denom=self.quote_denom,
            deposit=deposit,
        )
        balance_event = StreamSubaccountBalanceResponse(
            balance=balance,
            timestamp=timestamp_ms,
        )
        self.injective_async_client_mock.stream_subaccount_balance.return_value.add(balance_event)

        self.configure_get_account_balances_response(
            quote_total_balance=total_balance, quote_available_balance=available_balance,
        )

    def get_spot_order_history(
        self,
        timestamp: float,
        order_hash: str,
        state: str,
        execution_type: str,
        order_type: str,
        price: Decimal,
        size: Decimal,
        filled_size: Decimal,
        direction: str,
    ) -> SpotOrderHistory:
        timestamp_ms = int(timestamp * 1e3)
        order = SpotOrderHistory(
            order_hash=order_hash,
            market_id=self.market_id,
            subaccount_id="someSubAccountId",
            execution_type=execution_type,
            order_type=order_type,
            price=str(price * Decimal(f"1e{self.quote_decimals - self.base_decimals}")),
            trigger_price="0",
            quantity=str(size * Decimal(f"1e{self.base_decimals}")),
            filled_quantity=str(filled_size * Decimal(f"1e{self.base_decimals}")),
            state=state,
            created_at=timestamp_ms,
            updated_at=timestamp_ms,
            direction=direction,
        )
        return order

    def configure_get_account_portfolio_response(
            self,
            base_total_balance: Decimal,
            base_available_balance: Decimal,
            quote_total_balance: Decimal,
            quote_available_balance: Decimal,
    ):
        pass

    def configure_get_account_balances_response(
            self,
            base_bank_balance: Decimal = s_decimal_0,
            quote_bank_balance: Decimal = s_decimal_0,
            base_total_balance: Decimal = s_decimal_0,
            base_available_balance: Decimal = s_decimal_0,
            quote_total_balance: Decimal = s_decimal_0,
            quote_available_balance: Decimal = s_decimal_0,
            sub_account_id: Optional[str] = None,
    ):
        sub_account_id = sub_account_id or self.sub_account_id
        subaccount_list = []
        bank_coin_list = []

        if base_total_balance != s_decimal_0:
            base_deposit = SubaccountDeposit(
                total_balance=str(base_total_balance * Decimal(f"1e{self.base_decimals}")),
                available_balance=str(base_available_balance * Decimal(f"1e{self.base_decimals}")),
            )
            base_balance = SubaccountBalanceV2(
                subaccount_id=sub_account_id,
                denom=self.base_denom,
                deposit=base_deposit
            )
            subaccount_list.append(base_balance)

        if quote_total_balance != s_decimal_0:
            quote_deposit = SubaccountDeposit(
                total_balance=str(quote_total_balance * Decimal(f"1e{self.quote_decimals}")),
                available_balance=str(quote_available_balance * Decimal(f"1e{self.quote_decimals}")),
            )
            quote_balance = SubaccountBalanceV2(
                subaccount_id=sub_account_id,
                denom=self.quote_denom,
                deposit=quote_deposit,
            )
            subaccount_list.append(quote_balance)

        if base_bank_balance != s_decimal_0:
            base_scaled_amount = str(base_bank_balance * Decimal(f"1e{self.base_decimals}"))
            coin = Coin(amount=base_scaled_amount, denom=self.base_denom)
            bank_coin_list.append(coin)

        if quote_bank_balance != s_decimal_0:
            quote_scaled_amount = str(quote_bank_balance * Decimal(f"1e{self.quote_decimals}"))
            coin = Coin(amount=quote_scaled_amount, denom=self.quote_denom)
            bank_coin_list.append(coin)

        portfolio = Portfolio(account_address="someAccountAddress", bank_balances=bank_coin_list,
                              subaccounts=subaccount_list)

        self.injective_async_client_mock.get_account_portfolio.return_value = AccountPortfolioResponse(
            portfolio=portfolio)

    def configure_get_tx_by_hash_creation_response(
        self,
        timestamp: float,
        success: bool,
        order_hashes: Optional[List[str]] = None,
        transaction_hash: str = "",
        trade_type: TradeType = TradeType.BUY,
        is_order_failed: bool = False,
    ):
        order_hashes = order_hashes or []
        data_data = "\n\275\001\n0/injective.exchange.v1beta1.MsgBatchUpdateOrders"
        if success and not is_order_failed:
            data_data += "\022\210\001\032B" + "\032B".join(order_hashes)
        gas_wanted = int(BASE_GAS + SPOT_SUBMIT_ORDER_GAS + GAS_BUFFER)
        gas_amount_scaled = self.order_creation_gas_estimate * Decimal("1e18")
        gas_amount = CosmosCoin(denom="inj", amount=str(int(gas_amount_scaled)))
        gas_fee = GasFee(gas_limit=gas_wanted, payer="")
        gas_fee.amount.append(gas_amount)
        messages_data = [
            {
                'type': '/injective.exchange.v1beta1.MsgBatchUpdateOrders',
                'value': {
                    'order': {
                        'market_id': self.market_id,
                        'order_info': {
                            'fee_recipient': 'inj1hkhdaj2a2clmq5jq6mspsggqs32vynpk228q3r',
                            'price': '0.000000000007523000',
                            'quantity': '10000000000000000.000000000000000000',
                            'subaccount_id': self.sub_account_id,
                        },
                        'order_type': "BUY" if trade_type == TradeType.BUY else "SELL",
                        'trigger_price': '0.000000000000000000',
                    },
                    'sender': 'inj1hkhdaj2a2clmq5jq6mspsggqs32vynpk228q3r',
                },
            }
        ]
        data = TxDetailData(
            hash=transaction_hash,
            data=data_data.encode(),
            gas_wanted=gas_wanted,
            gas_used=int(gas_wanted * Decimal("0.9")),
            gas_fee=gas_fee,
            code=0 if success else 6,
            block_unix_timestamp=int(timestamp * 1e3),
            messages=json.dumps(messages_data).encode(),
        )
        self.injective_async_client_mock.get_tx_by_hash.return_value = GetTxByTxHashResponse(data=data)

    def configure_get_tx_by_hash_cancelation_response(
        self,
        timestamp: float,
        order_hash: str = "",
        transaction_hash: str = "",
    ):
        data_data = "\n0\n./injective.exchange.v1beta1.MsgCancelSpotOrder"
        gas_wanted = int(BASE_GAS + SPOT_CANCEL_ORDER_GAS + GAS_BUFFER)
        gas_amount_scaled = self.order_cancelation_gas_estimate * Decimal("1e18")
        gas_amount = CosmosCoin(denom="inj", amount=str(int(gas_amount_scaled)))
        gas_fee = GasFee(gas_limit=gas_wanted, payer="")
        gas_fee.amount.append(gas_amount)
        messages_data = [
            {
                'type': '/injective.exchange.v1beta1.MsgCancelSpotOrder',
                'value': {
                    'market_id': self.market_id,
                    "order_hash": order_hash,
                    'sender': 'inj1hkhdaj2a2clmq5jq6mspsggqs32vynpk228q3r',
                    'subaccount_id': self.sub_account_id,
                },
            }
        ]
        data = TxDetailData(
            hash=transaction_hash,
            data=data_data.encode(),
            gas_wanted=gas_wanted,
            gas_used=int(gas_wanted * Decimal("0.9")),
            gas_fee=gas_fee,
            code=0,
            block_unix_timestamp=int(timestamp * 1e3),
            messages=json.dumps(messages_data).encode(),
        )
        self.injective_async_client_mock.get_tx_by_hash.return_value = GetTxByTxHashResponse(data=data)

    def configure_creation_transaction_stream_event(
        self, timestamp: float, transaction_hash: str, trade_type: TradeType = TradeType.BUY
    ):
        """
        block_number: 21394573
        block_timestamp: "2022-12-12 06:15:31.072 +0000 UTC"
        hash: "0x2956ee8cf58f2b19646d00d794bfa6a857fcb7a58f6cd0879de5b91e849f60bb"  # noqa: documentation
        messages: "[{\"type\":\"/injective.exchange.v1beta1.MsgCreateSpotLimitOrder\",\"value\":{\"order\":{\"market_id\":\"0x572f05fd93a6c2c4611b2eba1a0a36e102b6a592781956f0128a27662d84f112\",\"order_info\":{\"fee_recipient\":\"inj1yzmv3utcm0xx4ahsn7lyew0zzdjp4z7wlx44vx\",\"price\":\"0.000000000004500000\",\"quantity\":\"51110000000000000000.000000000000000000\",\"subaccount_id\":\"0x20b6c8f178dbcc6af6f09fbe4cb9e213641a8bce000000000000000000000000\"},\"order_type\":\"SELL_PO\",\"trigger_price\":null},\"sender\":\"inj1yzmv3utcm0xx4ahsn7lyew0zzdjp4z7wlx44vx\"}}]"  # noqa: documentation
        tx_number: 135730075
        """
        message = [
            {
                "type": "/injective.exchange.v1beta1.MsgCreateSpotLimitOrder",
                "value": {
                    "order": {
                        "market_id": self.market_id,
                        "order_info": {
                            "fee_recipient": "inj1yzmv3utcm0xx4ahsn7lyew0zzdjp4z7wlx44vx",
                            "price": "0.000000000004500000",
                            "quantity": "51110000000000000000.000000000000000000",
                            "subaccount_id": self.sub_account_id,
                        },
                        "order_type": "BUY" if trade_type == TradeType.BUY else "SELL",
                        "trigger_price": None,
                    },
                    "sender": "inj1yzmv3utcm0xx4ahsn7lyew0zzdjp4z7wlx44vx",
                },
            },
        ]
        transaction_event = StreamTxsResponse(
            block_number=21393769,
            block_timestamp=f"{pd.Timestamp.utcfromtimestamp(timestamp / 1e3).strftime('%Y-%m-%d %H:%M:%S.%f')} +0000 UTC",
            hash=transaction_hash,
            messages=json.dumps(message),
            tx_number=135726991,
        )
        self.injective_async_client_mock.stream_txs.return_value.add(transaction_event)

    def configure_cancelation_transaction_stream_event(self, timestamp: float, transaction_hash: str, order_hash: str):
        """
        block_number: 21393769
        block_timestamp: "2022-12-12 06:00:22.878 +0000 UTC"
        hash: "0xa3dbf1340278ef5c9443b88c992e715cc72140a79c6a961a2513a9ed8774afb8"  # noqa: documentation
        messages: "[{\"type\":\"/injective.exchange.v1beta1.MsgCancelSpotOrder\",\"value\":{\"market_id\":\"0xd1956e20d74eeb1febe31cd37060781ff1cb266f49e0512b446a5fafa9a16034\",\"order_hash\":\"0x0b7c4b6753c938e6ea994d77d6b2fa40b60bd949317e8f5f7a8f290e1925d303\",\"sender\":\"inj1yzmv3utcm0xx4ahsn7lyew0zzdjp4z7wlx44vx\",\"subaccount_id\":\"0x20b6c8f178dbcc6af6f09fbe4cb9e213641a8bce000000000000000000000000\"}}]"  # noqa: documentation
        tx_number: 135726991
        """
        message = [
            {
                "type": "/injective.exchange.v1beta1.MsgCancelSpotOrder",
                "value": {
                    "market_id": self.market_id,
                    "order_hash": order_hash,
                    "sender": "inj1yzmv3utcm0xx4ahsn7lyew0zzdjp4z7wlx44vx",
                    "subaccount_id": self.sub_account_id,
                },
            },
        ]
        transaction_event = StreamTxsResponse(
            block_number=21393769,
            block_timestamp=f"{pd.Timestamp.utcfromtimestamp(timestamp / 1e3).strftime('%Y-%m-%d %H:%M:%S.%f')} +0000 UTC",
            hash=transaction_hash,
            messages=json.dumps(message),
            tx_number=135726991,
        )
        self.injective_async_client_mock.stream_txs.return_value.add(transaction_event)

    def configure_active_spot_markets_response(self, timestamp: float):
        base_token_meta = TokenMeta(
            name="Coin",
            address=self.base_coin_address,
            symbol=self.base,
            decimals=self.base_decimals,
            updated_at=int(timestamp * 1e3),
        )
        quote_token_meta = TokenMeta(
            name="Alpha",
            address=self.quote_coin_address,
            symbol=self.quote,
            decimals=self.quote_decimals,
            updated_at=int(timestamp * 1e3),
        )
        inj_token_meta = TokenMeta(
            name="Injective Protocol",
            address="0xe28b3B32B6c345A34Ff64674606124Dd5Aceca30",  # noqa: mock
            symbol="INJ",
            decimals=18,
            updated_at=int(timestamp * 1e3),
        )
        min_price_tick_size = str(
            self.min_price_tick_size * Decimal(f"1e{self.quote_decimals - self.base_decimals}")
        )
        min_quantity_tick_size = str(self.min_quantity_tick_size * Decimal(f"1e{self.base_decimals}"))
        market = SpotMarketInfo(
            market_id=self.market_id,
            market_status="active",
            ticker=f"{self.base}/{self.quote}",
            base_denom=self.base_denom,
            base_token_meta=base_token_meta,
            quote_denom=self.quote_denom,
            quote_token_meta=quote_token_meta,
            maker_fee_rate=str(self.maker_fee_rate),
            taker_fee_rate=str(self.taker_fee_rate),
            service_provider_fee="0.4",
            min_price_tick_size=min_price_tick_size,
            min_quantity_tick_size=min_quantity_tick_size,
        )
        inj_pair_min_price_tick_size = str(
            self.min_price_tick_size * Decimal(f"1e{18 - self.base_decimals}")
        )
        inj_pair_min_quantity_tick_size = str(self.min_quantity_tick_size * Decimal(f"1e{self.base_decimals}"))
        inj_pair_market = SpotMarketInfo(
            market_id="anotherMarketId",
            market_status="active",
            ticker=f"INJ/{self.quote}",
            base_denom="inj",
            base_token_meta=inj_token_meta,
            quote_denom=self.quote_denom,
            quote_token_meta=quote_token_meta,
            maker_fee_rate=str(self.maker_fee_rate),
            taker_fee_rate=str(self.taker_fee_rate),
            service_provider_fee="0.4",
            min_price_tick_size=inj_pair_min_price_tick_size,
            min_quantity_tick_size=inj_pair_min_quantity_tick_size,
        )
        markets = MarketsResponse()
        markets.markets.append(market)
        markets.markets.append(inj_pair_market)

        self.injective_async_client_mock.get_spot_markets.return_value = markets
