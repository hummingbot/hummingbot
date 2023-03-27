import asyncio
import json
from decimal import Decimal
from typing import Any, List, Optional, Tuple, Type
from unittest.mock import AsyncMock, patch

import grpc
import pandas as pd
from pyinjective.orderhash import OrderHashResponse
from pyinjective.proto.exchange.injective_accounts_rpc_pb2 import SubaccountDeposit
from pyinjective.proto.exchange.injective_derivative_exchange_rpc_pb2 import (
    DerivativeLimitOrderbook,
    DerivativeMarketInfo,
    DerivativeOrderHistory,
    DerivativeTrade,
    MarketsResponse,
    OrderbookResponse,
    OrdersHistoryResponse,
    Paging,
    PerpetualMarketFunding,
    PerpetualMarketInfo,
    PositionDelta,
    PriceLevel,
    StreamOrderbookResponse,
    StreamOrdersHistoryResponse,
    StreamTradesResponse,
    TokenMeta,
    TradesResponse,
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
    StreamAccountPortfolioResponse,
    SubaccountBalanceV2,
)

from hummingbot.connector.constants import s_decimal_0
from hummingbot.connector.gateway.clob_perp.data_sources.injective_perpetual.injective_perpetual_constants import (
    BASE_GAS,
    DERIVATIVE_CANCEL_ORDER_GAS,
    DERIVATIVE_SUBMIT_ORDER_GAS,
    GAS_BUFFER,
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


class InjectivePerpetualClientMock:
    def __init__(
        self,
        initial_timestamp: float,
        sub_account_id: str,
        base: str,
        quote: str,
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
                "hummingbot.connector.gateway.clob_perp.data_sources.injective_perpetual.injective_perpetual_api_data_source.AsyncClient"
            ),
            autospec=True,
        )
        self.injective_async_client_mock: Optional[AsyncMock] = None
        self.gateway_instance_mock_patch = patch(
            target=(
                "hummingbot.connector.gateway.clob_perp.data_sources.injective_perpetual.injective_perpetual_api_data_source"
                ".GatewayHttpClient"
            ),
            autospec=True,
        )
        self.gateway_instance_mock: Optional[AsyncMock] = None
        self.injective_order_hash_manager_start_patch = patch(
            target=(
                "hummingbot.connector.gateway.clob_perp.data_sources.injective_perpetual.injective_perpetual_api_data_source"
                ".OrderHashManager.start"
            ),
            autospec=True,
        )
        self.injective_composer_patch = patch(
            target="hummingbot.connector.gateway.clob_perp.data_sources.injective_perpetual.injective_perpetual_api_data_source"
            ".ProtoMsgComposer",
            autospec=True,
        )
        self.injective_compute_order_hashes_patch = patch(
            target=(
                "hummingbot.connector.gateway.clob_perp.data_sources.injective_perpetual.injective_perpetual_api_data_source"
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

        self.injective_async_client_mock.stream_derivative_trades.return_value = StreamMock()
        self.injective_async_client_mock.stream_historical_derivative_orders.return_value = StreamMock()
        self.injective_async_client_mock.stream_derivative_orderbooks.return_value = StreamMock()
        self.injective_async_client_mock.stream_account_portfolio.return_value = StreamMock()
        self.injective_async_client_mock.stream_txs.return_value = StreamMock()

        self.configure_active_derivative_markets_response(timestamp=self.initial_timestamp)

    def stop(self):
        self.injective_async_client_mock_patch.stop()
        self.gateway_instance_mock_patch.stop()
        self.injective_order_hash_manager_start_patch.stop()
        self.injective_composer_patch.stop()
        self.injective_compute_order_hashes_patch.stop()

    def run_until_all_items_delivered(self, timeout: float = 1):
        self.injective_async_client_mock.stream_derivative_trades.return_value.run_until_all_items_delivered(
            timeout=timeout
        )
        self.injective_async_client_mock.stream_historical_derivative_orders.return_value.run_until_all_items_delivered(
            timeout=timeout
        )
        self.injective_async_client_mock.stream_derivative_orderbooks.return_value.run_until_all_items_delivered(
            timeout=timeout
        )
        self.injective_async_client_mock.stream_account_portfolio.return_value.run_until_all_items_delivered(
            timeout=timeout
        )
        self.injective_async_client_mock.stream_txs.return_value.run_until_all_items_delivered(timeout=timeout)

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

        self.gateway_instance_mock.clob_perp_batch_order_modify.side_effect = update_and_return
        self.configure_get_tx_by_hash_creation_response(
            timestamp=timestamp, success=True, order_hashes=[order.exchange_order_id for order in created_orders]
        )
        for order in created_orders:
            self.configure_get_historical_perp_orders_response_for_in_flight_order(
                timestamp=timestamp,
                in_flight_order=order,
            )
        self.injective_compute_order_hashes_mock.return_value = OrderHashResponse(
            spot=[], derivative=[order.exchange_order_id for order in created_orders]
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

        self.gateway_instance_mock.clob_perp_batch_order_modify.side_effect = update_and_return
        for order in canceled_orders:
            self.configure_get_historical_perp_orders_response_for_in_flight_order(
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
        self.configure_get_historical_perp_orders_response(
            timestamp=timestamp,
            order_hash=exchange_order_id,
            state="booked",
            execution_type="limit",
            order_type="buy" if trade_type == TradeType.BUY else "sell",
            price=price,
            size=size,
            filled_size=Decimal("0"),
            direction="buy" if trade_type == TradeType.BUY else "sell",
            leverage=Decimal(1),
        )
        self.injective_compute_order_hashes_mock.return_value = OrderHashResponse(
            spot=[], derivative=[exchange_order_id]
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
        self,
        success_timestamp: int,
        success_transaction_hash: str,
        failure_exception: Exception,
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
            self.configure_get_historical_derivative_orders_empty_response()
        elif not is_canceled:
            self.configure_get_historical_perp_orders_response_for_in_flight_order(
                timestamp=timestamp,
                in_flight_order=order,
                order_hash=exchange_order_id,
                filled_size=filled_size,
            )
        else:
            self.configure_get_historical_perp_orders_response_for_in_flight_order(
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
        price_level = PriceLevel(price=str(scaled_price), quantity=str(scaled_size), timestamp=timestamp_ms)
        scaled_fee = fee.flat_fees[0].amount * Decimal(f"1e{self.quote_decimals}")
        trade = DerivativeTrade(
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

        if self.injective_async_client_mock.get_derivative_trades.side_effect is None:
            self.injective_async_client_mock.get_derivative_trades.side_effect = [trades, TradesResponse()]
        else:
            self.injective_async_client_mock.get_derivative_trades.side_effect = list(
                self.injective_async_client_mock.get_derivative_trades.side_effect
            ) + [trades, TradesResponse()]

    def configure_trades_response_no_trades(self):
        """This method appends mocks if previously queued mocks already exist."""
        trades = TradesResponse()

        if self.injective_async_client_mock.get_derivative_trades.side_effect is None:
            self.injective_async_client_mock.get_derivative_trades.side_effect = [trades, TradesResponse()]
        else:
            self.injective_async_client_mock.get_derivative_trades.side_effect = list(
                self.injective_async_client_mock.get_derivative_trades.side_effect
            ) + [trades, TradesResponse()]

    def configure_trades_response_fails(self):
        self.injective_async_client_mock.get_derivative_trades.side_effect = RuntimeError

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
            leverage=in_flight_order.leverage,
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
        self.injective_async_client_mock.stream_derivative_trades.return_value.add(maker_trade_response)
        self.injective_async_client_mock.stream_derivative_trades.return_value.add(taker_trade_response)

    def configure_bank_account_portfolio_balance_stream_event(self, denom: str, amount: Decimal):
        balance_event = StreamAccountPortfolioResponse(type="bank", denom=denom, amount=amount)
        self.injective_async_client_mock.stream_account_portfolio.return_value.add(balance_event)

    def configure_perp_trades_response_to_request_without_exchange_order_id(
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

        self.injective_async_client_mock.get_derivative_trades.return_value = trades

    def configure_orderbook_snapshot(
        self,
        timestamp: float,
        bids: List[Tuple[float, float]],
        asks: List[Tuple[float, float]],
    ):
        timestamp_ms = int(timestamp * 1e3)
        orderbook = self.create_orderbook_mock(timestamp_ms=timestamp_ms, bids=bids, asks=asks)
        orderbook_response = OrderbookResponse(orderbook=orderbook)

        self.injective_async_client_mock.get_derivative_orderbook.return_value = orderbook_response

    def configure_orderbook_snapshot_stream_event(
        self, timestamp: float, bids: List[Tuple[float, float]], asks: List[Tuple[float, float]]
    ):
        timestamp_ms = int(timestamp * 1e3)
        orderbook = self.create_orderbook_mock(timestamp_ms=timestamp_ms, bids=bids, asks=asks)
        orderbook_response = StreamOrderbookResponse(
            orderbook=orderbook,
            operation_type="update",
            timestamp=timestamp_ms,
            market_id=self.market_id,
        )

        self.injective_async_client_mock.stream_derivative_orderbooks.return_value.add(orderbook_response)

    def create_orderbook_mock(
        self, timestamp_ms: float, bids: List[Tuple[float, float]], asks: List[Tuple[float, float]]
    ) -> DerivativeLimitOrderbook:
        orderbook = DerivativeLimitOrderbook()

        for price, size in bids:
            scaled_price = price * Decimal(f"1e{self.quote_decimals - self.base_decimals}")
            scaled_size = size * Decimal(f"1e{self.base_decimals}")
            bid = PriceLevel(price=str(scaled_price), quantity=str(scaled_size), timestamp=timestamp_ms)
            orderbook.buys.append(bid)

        for price, size in asks:
            scaled_price = price * Decimal(f"1e{self.quote_decimals - self.base_decimals}")
            scaled_size = size * Decimal(f"1e{self.base_decimals}")
            ask = PriceLevel(price=str(scaled_price), quantity=str(scaled_size), timestamp=timestamp_ms)
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
    ) -> Tuple[DerivativeTrade, DerivativeTrade]:
        """The taker is a buy."""
        timestamp_ms = int(timestamp * 1e3)
        scaled_price = price * Decimal(f"1e{self.quote_decimals - self.base_decimals}")
        scaled_size = size * Decimal(f"1e{self.base_decimals}")
        price_level = PriceLevel(price=str(scaled_price), quantity=str(scaled_size), timestamp=timestamp_ms)
        scaled_maker_fee = maker_fee * Decimal(f"1e{self.quote_decimals}")
        scaled_taker_fee = taker_fee * Decimal(f"1e{self.quote_decimals}")
        assert len(taker_trade_id.split("_")) == 2
        trade_id_prefix = taker_trade_id.split("_")[0]

        taker_position_delta = PositionDelta(
            trade_direction="buy",
            execution_price=price_level,
            execution_quantity=scaled_size,
            execution_margin=str(scaled_price * scaled_size),
        )

        maker_position_delta = PositionDelta(
            trade_direction="sell",
            execution_price=price_level,
            execution_quantity=scaled_size,
            execution_margin=str(scaled_price * scaled_size),
        )

        taker_trade = DerivativeTrade(
            order_hash=order_hash,
            subaccount_id="sumSubAccountId",
            market_id=self.market_id,
            trade_execution_type="limitMatchNewOrder",
            is_liquidation=False,
            position_delta=taker_position_delta,
            payout="",
            fee=str(scaled_taker_fee),
            executed_at=timestamp_ms,
            fee_recipient="anotherRecipientAddress",
            trade_id=taker_trade_id,
            execution_side="taker",
        )
        maker_trade = DerivativeTrade(
            order_hash="anotherOrderHash",
            subaccount_id="anotherSubAccountId",
            market_id=self.market_id,
            trade_execution_type="limitMatchRestingOrder",
            is_liquidation=False,
            position_delta=maker_position_delta,
            payout="",
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
        leverage: float,
    ):
        """
        order {
            order_hash: "0xfb526d72b85e9ffb4426c37bf332403fb6fb48709fb5d7ca3be7b8232cd10292"  # noqa: documentation
            market_id: "0x90e662193fa29a3a7e6c07be4407c94833e762d9ee82136a2cc712d6b87d7de3"  # noqa: documentation
            is_active: true
            subaccount_id: "0xc6fe5d33615a1c52c08018c47e8bc53646a0e101000000000000000000000000"  # noqa: documentation
            execution_type: "limit"
            order_type: "sell_po"
            price: "274310000"
            trigger_price: "0"
            quantity: "144"
            filled_quantity: "0"
            state: "booked"
            created_at: 1665487076373
            updated_at: 1665487076373
            direction: "sell"
            margin: "3950170000"
        }
        operation_type: "update"
        timestamp: 1669198784000
        """
        order = self.get_derivative_order_history(
            timestamp=timestamp,
            order_hash=order_hash,
            state=state,
            execution_type=execution_type,
            order_type=order_type,
            price=price,
            size=size,
            filled_size=filled_size,
            direction=direction,
            leverage=leverage,
        )
        timestamp_ms = int(timestamp * 1e3)
        order_response = StreamOrdersHistoryResponse(
            order=order,
            operation_type="update",
            timestamp=timestamp_ms,
        )
        self.injective_async_client_mock.stream_historical_derivative_orders.return_value.add(order_response)

    def configure_get_historical_perp_orders_response_for_in_flight_order(
        self,
        timestamp: float,
        in_flight_order: InFlightOrder,
        filled_size: Decimal = Decimal("0"),
        is_canceled: bool = False,
        order_hash: Optional[str] = None,  # overwrites in_flight_order.exchange_order_id
    ):
        """
        orders {
            order_hash: "0x10c4cd0c744c08d38920d063ad5f811b97fd9f5d59224814ad9a02bdffb4c0bd"  # noqa: documentation
            market_id: "0x90e662193fa29a3a7e6c07be4407c94833e762d9ee82136a2cc712d6b87d7de3"  # noqa: documentation
            subaccount_id: "0x295639d56c987f0e24d21bb167872b3542a6e05a000000000000000000000000"  # noqa: documentation
            execution_type: "limit"
            order_type: "sell"
            price: "21876100000"
            trigger_price: "0"
            quantity: "0.001"
            filled_quantity: "0"
            state: "canceled"
            created_at: 1676268856766
            updated_at: 1676268924613
            direction: "sell"
            margin: "21900000"
        }
        paging {
            total: 32
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
        self.configure_get_historical_perp_orders_response(
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
            leverage=in_flight_order.leverage,
        )

    def configure_get_historical_derivative_orders_empty_response(self):
        paging = Paging(total=1)
        mock_response = OrdersHistoryResponse(paging=paging)
        self.injective_async_client_mock.get_historical_derivative_orders.return_value = mock_response

    def configure_get_historical_perp_orders_response(
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
        leverage: float,
    ):
        """
        orders {
            order_hash: "0x06a9b81441b4fd38bc9da9b928007286b340407481f41398daab291cde2bd6dc"  # noqa: documentation
            market_id: "0x90e662193fa29a3a7e6c07be4407c94833e762d9ee82136a2cc712d6b87d7de3"  # noqa: documentation
            subaccount_id: "0x295639d56c987f0e24d21bb167872b3542a6e05a000000000000000000000000"  # noqa: documentation
            execution_type: "limit"
            order_type: "sell"
            price: "21805600000"
            trigger_price: "0"
            quantity: "0.001"
            filled_quantity: "0.001"
            state: "filled"
            created_at: 1676269001530
            updated_at: 1676269001530
            direction: "sell"
            margin: "21800000"
        }
        paging {
          total: 1000
        }
        """
        order = self.get_derivative_order_history(
            timestamp=timestamp,
            order_hash=order_hash,
            state=state,
            execution_type=execution_type,
            order_type=order_type,
            price=price,
            size=size,
            filled_size=filled_size,
            direction=direction,
            leverage=leverage,
        )
        paging = Paging(total=1)
        mock_response = OrdersHistoryResponse(paging=paging)
        mock_response.orders.append(order)
        self.injective_async_client_mock.get_historical_derivative_orders.return_value = mock_response

    def get_derivative_order_history(
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
        leverage: float,
    ) -> DerivativeOrderHistory:
        timestamp_ms = int(timestamp * 1e3)
        order = DerivativeOrderHistory(
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
            margin=Decimal(leverage) * size * price,
        )
        return order

    def configure_get_account_balances_list_response(
        self,
        bank_base_available_balance: Decimal,
        bank_quote_available_balance: Decimal,
        subaccount_base_total_balance: Decimal,
        subaccount_quote_total_balance: Decimal,
    ):
        account_portfolio_response = AccountPortfolioResponse()

        if bank_base_available_balance != s_decimal_0:
            base_coin = Coin(denom=self.base_denom, amount=str(bank_base_available_balance))
        if bank_quote_available_balance != s_decimal_0:
            quote_coin = Coin(denom=self.quote_denom, amount=str(bank_quote_available_balance))

        if subaccount_base_total_balance != s_decimal_0:
            base_deposit = SubaccountDeposit(
                total_balance=str(subaccount_base_total_balance * Decimal(f"1e{self.base_decimals}")),
                available_balance="",
            )
            base_subaccount = SubaccountBalanceV2(
                subaccount_id=self.sub_account_id, denom=self.base_denom, deposit=base_deposit
            )

        if subaccount_quote_total_balance != s_decimal_0:
            quote_deposit = SubaccountDeposit(
                total_balance=str(subaccount_quote_total_balance * Decimal(f"1e{self.base_decimals}")),
                available_balance="",
            )
            quote_subaccount = SubaccountBalanceV2(
                subaccount_id=self.sub_account_id, denom=self.base_denom, deposit=quote_deposit
            )

        portfolio = Portfolio(
            account_address="someInjAddress",
            bank_balances=[base_coin, quote_coin],
            subaccounts=[base_subaccount, quote_subaccount],
        )
        account_portfolio_response.portfolio = portfolio

        self.injective_async_client_mock.get_account_portfolio.return_value = account_portfolio_response

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
        gas_wanted = int(BASE_GAS + DERIVATIVE_SUBMIT_ORDER_GAS + GAS_BUFFER)
        gas_amount_scaled = self.order_creation_gas_estimate * Decimal("1e18")
        gas_amount = CosmosCoin(denom="inj", amount=str(int(gas_amount_scaled)))
        gas_fee = GasFee(gas_limit=gas_wanted, payer="")
        gas_fee.amount.append(gas_amount)
        messages_data = [
            {
                "type": "/injective.exchange.v1beta1.MsgBatchUpdateOrders",
                "value": {
                    "order": {
                        "market_id": self.market_id,
                        "order_info": {
                            "fee_recipient": "inj1hkhdaj2a2clmq5jq6mspsggqs32vynpk228q3r",  # noqa: mock
                            "price": "0.000000000007523000",
                            "quantity": "10000000000000000.000000000000000000",
                            "subaccount_id": self.sub_account_id,
                        },
                        "order_type": "BUY" if trade_type == TradeType.BUY else "SELL",
                        "trigger_price": "0.000000000000000000",
                    },
                    "sender": "inj1hkhdaj2a2clmq5jq6mspsggqs32vynpk228q3r",  # noqa: mock
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
        data_data = "\n0\n./injective.exchange.v1beta1.MsgCancelDerivativeOrder"
        gas_wanted = int(BASE_GAS + DERIVATIVE_CANCEL_ORDER_GAS + GAS_BUFFER)
        gas_amount_scaled = self.order_cancelation_gas_estimate * Decimal("1e18")
        gas_amount = CosmosCoin(denom="inj", amount=str(int(gas_amount_scaled)))
        gas_fee = GasFee(gas_limit=gas_wanted, payer="")
        gas_fee.amount.append(gas_amount)
        messages_data = [
            {
                "type": "/injective.exchange.v1beta1.MsgCancelDerivativeOrder",
                "value": {
                    "market_id": self.market_id,
                    "order_hash": order_hash,
                    "sender": "inj1hkhdaj2a2clmq5jq6mspsggqs32vynpk228q3r",  # noqa: mock
                    "subaccount_id": self.sub_account_id,
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
        block_number: 29339622
        block_timestamp: "2023-03-23 12:32:36.4 +0000 UTC"
        hash: "0xfdb58d83b16caf9a64e8818b31eb27f1cadebd2590c98178e4452ed255fd10de"  # noqa: mock
        messages: "[{\"type\":\"/injective.exchange.v1beta1.MsgCreateDerivativeLimitOrder\",\"value\":{\"order\":{\"margin\":\"8000000.000000000000000000\",\"market_id\":\"0x9b9980167ecc3645ff1a5517886652d94a0825e54a77d2057cbbe3ebee015963\",\"order_info\":{\"fee_recipient\":\"inj1zyg3zyg3zyg3zyg3zyg3zyg3zyg3zyg3t5qxqh\",\"price\":\"4000000.000000000000000000\",\"quantity\":\"2.000000000000000000\",\"subaccount_id\":\"0x72b52e007d01cc5ac36349288f24ce1bd912cedf000000000000000000000000\"},\"order_type\":\"BUY\",\"trigger_price\":\"0.000000000000000000\"},\"sender\":\"inj1w26juqraq8x94smrfy5g7fxwr0v39nkluxrq07\"}}]"  # noqa: documentation
        tx_number: 185354499
        """
        message = [
            {
                "type": "/injective.exchange.v1beta1.MsgCreateDerivativeLimitOrder",
                "value": {
                    "order": {
                        "margin": "8000000.000000000000000000",
                        "market_id": self.market_id,
                        "order_info": {
                            "fee_recipient": "inj1zyg3zyg3zyg3zyg3zyg3zyg3zyg3zyg3t5qxqh",  # noqa: mock
                            "price": "4000000.000000000000000000",
                            "quantity": "2.000000000000000000",
                            "subaccount_id": self.sub_account_id,
                        },
                        "order_type": "BUY" if trade_type == TradeType.BUY else "SELL",
                        "trigger_price": "0.000000000000000000",
                    },
                    "sender": "inj1w26juqraq8x94smrfy5g7fxwr0v39nkluxrq07",  # noqa: mock
                },
            },
        ]
        transaction_event = StreamTxsResponse(
            block_number=29339622,
            block_timestamp=f"{pd.Timestamp.utcfromtimestamp(timestamp / 1e3).strftime('%Y-%m-%d %H:%M:%S.%f')} +0000 UTC",
            hash=transaction_hash,
            messages=json.dumps(message),
            tx_number=185354499,
        )
        self.injective_async_client_mock.stream_txs.return_value.add(transaction_event)

    def configure_cancelation_transaction_stream_event(self, timestamp: float, transaction_hash: str, order_hash: str):
        """
        block_number: 29339532
        block_timestamp: "2023-03-23 12:30:56.689 +0000 UTC"
        hash: "0xac84bc1734e49b0a1a2e7e5b3eb020ef5ee16429fbd7b9012b9a3b3c8e5d27a5"  # noqa: mock
        messages: "[{\"type\":\"/injective.exchange.v1beta1.MsgCancelDerivativeOrder\",\"value\":{\"market_id\":\"0x9b9980167ecc3645ff1a5517886652d94a0825e54a77d2057cbbe3ebee015963\",\"order_hash\":\"0x9118645b214027341d1f5be3af9edd5dc25bd12505e30e10f1323dd6e4532976\",\"order_mask\":1,\"sender\":\"inj1w26juqraq8x94smrfy5g7fxwr0v39nkluxrq07\",\"subaccount_id\":\"0x72b52e007d01cc5ac36349288f24ce1bd912cedf000000000000000000000000\"}}]"   # noqa: documentation
        tx_number: 185353585
        """
        message = [
            {
                "type": "/injective.exchange.v1beta1.MsgCancelDerivativeOrder",
                "value": {
                    "market_id": "0x9b9980167ecc3645ff1a5517886652d94a0825e54a77d2057cbbe3ebee015963",  # noqa: mock
                    "order_hash": "0x9118645b214027341d1f5be3af9edd5dc25bd12505e30e10f1323dd6e4532976",  # noqa: mock
                    "order_mask": 1,
                    "sender": "inj1w26juqraq8x94smrfy5g7fxwr0v39nkluxrq07",  # noqa: mock
                    "subaccount_id": "0x72b52e007d01cc5ac36349288f24ce1bd912cedf000000000000000000000000",  # noqa: mock
                },
            }
        ]
        transaction_event = StreamTxsResponse(
            block_number=29339532,
            block_timestamp=f"{pd.Timestamp.utcfromtimestamp(timestamp / 1e3).strftime('%Y-%m-%d %H:%M:%S.%f')} +0000 UTC",
            hash=transaction_hash,
            messages=json.dumps(message),
            tx_number=185353585,
        )
        self.injective_async_client_mock.stream_txs.return_value.add(transaction_event)

    def configure_active_derivative_markets_response(self, timestamp: float):
        quote_token_meta = TokenMeta(
            name="Alpha",
            address=self.quote_coin_address,
            symbol=self.quote,
            decimals=self.quote_decimals,
            updated_at=int(timestamp * 1e3),
        )
        min_price_tick_size = str(self.min_price_tick_size * Decimal(f"1e{self.quote_decimals - self.base_decimals}"))
        min_quantity_tick_size = str(self.min_quantity_tick_size * Decimal(f"1e{self.base_decimals}"))
        custom_perpetual_market_info = PerpetualMarketInfo(
            hourly_funding_rate_cap="0.0000625",
            hourly_interest_rate="0.00000416666",
            next_funding_timestamp=1677661200,
            funding_interval=3600,
        )
        custom_perpetual_market_funding = PerpetualMarketFunding(
            cumulative_funding="6749828879.286921884648585187",
            cumulative_price="1.502338165156193724",
            last_timestamp=1677660809,
        )
        custom_market = DerivativeMarketInfo(
            market_id=self.market_id,
            market_status="active",
            ticker=f"{self.base}/{self.quote} PERP",
            oracle_base=self.base,
            oracle_quote=self.quote,
            oracle_type="bandibc",
            oracle_scale_factor=6,
            initial_margin_ratio="0.095",
            maintenance_margin_ratio="0.05",
            quote_denom=self.quote_coin_address,
            quote_token_meta=quote_token_meta,
            maker_fee_rate=str(self.maker_fee_rate),
            taker_fee_rate=str(self.taker_fee_rate),
            service_provider_fee="0.4",
            is_perpetual=True,
            min_price_tick_size=min_price_tick_size,
            min_quantity_tick_size=min_quantity_tick_size,
            perpetual_market_info=custom_perpetual_market_info,
            perpetual_market_funding=custom_perpetual_market_funding,
        )
        inj_pair_min_price_tick_size = str(self.min_price_tick_size * Decimal(f"1e{18 - self.base_decimals}"))
        inj_pair_min_quantity_tick_size = str(self.min_quantity_tick_size * Decimal(f"1e{self.base_decimals}"))

        inj_perpetual_market_info = PerpetualMarketInfo(
            hourly_funding_rate_cap="0.000625",
            hourly_interest_rate="0.00000416666",
            next_funding_timestamp=1676340000,
            funding_interval=3600,
        )
        inj_perpetual_market_funding = PerpetualMarketFunding(
            cumulative_funding="30750.538513128695953648",
            cumulative_price="793.433131392911165592",
            last_timestamp=1674712474,
        )

        inj_pair_market = DerivativeMarketInfo(
            market_id="anotherMarketId",
            market_status="active",
            ticker=f"INJ/{self.quote} PERP",
            oracle_base="INJ",
            oracle_quote=self.quote,
            oracle_type="bandibc",
            oracle_scale_factor=6,
            initial_margin_ratio="0.095",
            maintenance_margin_ratio="0.05",
            quote_denom=self.quote_coin_address,
            quote_token_meta=quote_token_meta,
            maker_fee_rate=str(self.maker_fee_rate),
            taker_fee_rate=str(self.taker_fee_rate),
            service_provider_fee="0.4",
            min_price_tick_size=inj_pair_min_price_tick_size,
            min_quantity_tick_size=inj_pair_min_quantity_tick_size,
            perpetual_market_info=inj_perpetual_market_info,
            perpetual_market_funding=inj_perpetual_market_funding,
        )
        markets = MarketsResponse()
        markets.markets.append(custom_market)
        markets.markets.append(inj_pair_market)

        self.injective_async_client_mock.get_derivative_markets.return_value = markets
