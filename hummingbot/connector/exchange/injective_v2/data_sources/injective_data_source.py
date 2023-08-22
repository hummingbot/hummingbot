import asyncio
import logging
import os
import time
from abc import ABC, abstractmethod
from decimal import Decimal
from enum import Enum
from functools import partial
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

from google.protobuf import any_pb2
from pyinjective import Transaction
from pyinjective.composer import Composer, injective_exchange_tx_pb

from hummingbot.connector.derivative.position import Position
from hummingbot.connector.exchange.injective_v2 import injective_constants as CONSTANTS
from hummingbot.connector.exchange.injective_v2.injective_events import InjectiveEvent
from hummingbot.connector.exchange.injective_v2.injective_market import (
    InjectiveDerivativeMarket,
    InjectiveSpotMarket,
    InjectiveToken,
)
from hummingbot.connector.gateway.common_types import CancelOrderResult, PlaceOrderResult
from hummingbot.connector.gateway.gateway_in_flight_order import GatewayInFlightOrder, GatewayPerpetualInFlightOrder
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.core.api_throttler.async_throttler_base import AsyncThrottlerBase
from hummingbot.core.data_type.common import OrderType, PositionAction, PositionSide, TradeType
from hummingbot.core.data_type.funding_info import FundingInfo, FundingInfoUpdate
from hummingbot.core.data_type.in_flight_order import OrderState, OrderUpdate, TradeUpdate
from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType
from hummingbot.core.data_type.trade_fee import TokenAmount, TradeFeeBase, TradeFeeSchema
from hummingbot.core.event.event_listener import EventListener
from hummingbot.core.event.events import (
    AccountEvent,
    BalanceUpdateEvent,
    MarketEvent,
    OrderBookDataSourceEvent,
    PositionUpdateEvent,
)
from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.core.utils.async_utils import safe_gather
from hummingbot.logger import HummingbotLogger


class InjectiveDataSource(ABC):
    _logger: Optional[HummingbotLogger] = None

    TRANSACTIONS_LOOKUP_TIMEOUT = CONSTANTS.EXPECTED_BLOCK_TIME * 3

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(HummingbotLogger.logger_name_for_class(cls))
        return cls._logger

    @property
    @abstractmethod
    def publisher(self):
        raise NotImplementedError

    @property
    @abstractmethod
    def query_executor(self):
        raise NotImplementedError

    @property
    @abstractmethod
    def composer(self) -> Composer:
        raise NotImplementedError

    @property
    @abstractmethod
    def order_creation_lock(self) -> asyncio.Lock:
        raise NotImplementedError

    @property
    @abstractmethod
    def throttler(self):
        raise NotImplementedError

    @property
    @abstractmethod
    def portfolio_account_injective_address(self) -> str:
        raise NotImplementedError

    @property
    @abstractmethod
    def portfolio_account_subaccount_id(self) -> str:
        raise NotImplementedError

    @property
    @abstractmethod
    def trading_account_injective_address(self) -> str:
        raise NotImplementedError

    @property
    @abstractmethod
    def injective_chain_id(self) -> str:
        raise NotImplementedError

    @property
    @abstractmethod
    def fee_denom(self) -> str:
        raise NotImplementedError

    @property
    @abstractmethod
    def portfolio_account_subaccount_index(self) -> int:
        raise NotImplementedError

    @property
    @abstractmethod
    def network_name(self) -> str:
        raise NotImplementedError

    @abstractmethod
    async def timeout_height(self) -> int:
        raise NotImplementedError

    @abstractmethod
    async def spot_market_and_trading_pair_map(self):
        raise NotImplementedError

    @abstractmethod
    async def spot_market_info_for_id(self, market_id: str):
        raise NotImplementedError

    @abstractmethod
    async def derivative_market_and_trading_pair_map(self):
        raise NotImplementedError

    @abstractmethod
    async def derivative_market_info_for_id(self, market_id: str):
        raise NotImplementedError

    @abstractmethod
    async def trading_pair_for_market(self, market_id: str):
        raise NotImplementedError

    @abstractmethod
    async def market_id_for_spot_trading_pair(self, trading_pair: str) -> str:
        raise NotImplementedError

    @abstractmethod
    async def market_id_for_derivative_trading_pair(self, trading_pair: str) -> str:
        raise NotImplementedError

    @abstractmethod
    async def spot_markets(self):
        raise NotImplementedError

    @abstractmethod
    async def derivative_markets(self):
        raise NotImplementedError

    @abstractmethod
    async def token(self, denom: str) -> InjectiveToken:
        raise NotImplementedError

    @abstractmethod
    def events_listening_tasks(self) -> List[asyncio.Task]:
        raise NotImplementedError

    @abstractmethod
    def add_listening_task(self, task: asyncio.Task):
        raise NotImplementedError

    @abstractmethod
    def configure_throttler(self, throttler: AsyncThrottlerBase):
        raise NotImplementedError

    @abstractmethod
    async def trading_account_sequence(self) -> int:
        raise NotImplementedError

    @abstractmethod
    async def trading_account_number(self) -> int:
        raise NotImplementedError

    @abstractmethod
    async def initialize_trading_account(self):
        raise NotImplementedError

    @abstractmethod
    async def update_markets(self):
        raise NotImplementedError

    @abstractmethod
    def real_tokens_spot_trading_pair(self, unique_trading_pair: str) -> str:
        raise NotImplementedError

    @abstractmethod
    def real_tokens_perpetual_trading_pair(self, unique_trading_pair: str) -> str:
        raise NotImplementedError

    @abstractmethod
    async def order_updates_for_transaction(
            self,
            transaction_hash: str,
            spot_orders: Optional[List[GatewayInFlightOrder]] = None,
            perpetual_orders: Optional[List[GatewayPerpetualInFlightOrder]] = None,
    ) -> List[OrderUpdate]:
        raise NotImplementedError

    @abstractmethod
    def supported_order_types(self) -> List[OrderType]:
        raise NotImplementedError

    def is_started(self):
        return len(self.events_listening_tasks()) > 0

    async def check_network(self) -> NetworkStatus:
        try:
            await self.query_executor.ping()
            status = NetworkStatus.CONNECTED
        except asyncio.CancelledError:
            raise
        except Exception:
            status = NetworkStatus.NOT_CONNECTED
        return status

    async def start(self, market_ids: List[str]):
        if not self.is_started():
            await self.initialize_trading_account()
            if not self.is_started():
                spot_markets = []
                derivative_markets = []
                for market_id in market_ids:
                    if market_id in await self.spot_market_and_trading_pair_map():
                        spot_markets.append(market_id)
                    else:
                        derivative_markets.append(market_id)

                if len(spot_markets) > 0:
                    self.add_listening_task(asyncio.create_task(self._listen_to_public_spot_trades(market_ids=spot_markets)))
                    self.add_listening_task(asyncio.create_task(self._listen_to_spot_order_book_updates(market_ids=spot_markets)))
                    for market_id in spot_markets:
                        self.add_listening_task(asyncio.create_task(
                            self._listen_to_subaccount_spot_order_updates(market_id=market_id))
                        )
                        self.add_listening_task(asyncio.create_task(
                            self._listen_to_subaccount_spot_order_updates(market_id=market_id))
                        )
                if len(derivative_markets) > 0:
                    self.add_listening_task(
                        asyncio.create_task(self._listen_to_public_derivative_trades(market_ids=derivative_markets)))
                    self.add_listening_task(
                        asyncio.create_task(self._listen_to_derivative_order_book_updates(market_ids=derivative_markets)))
                    self.add_listening_task(
                        asyncio.create_task(self._listen_to_positions_updates())
                    )
                    for market_id in derivative_markets:
                        self.add_listening_task(asyncio.create_task(
                            self._listen_to_subaccount_derivative_order_updates(market_id=market_id))
                        )
                        self.add_listening_task(
                            asyncio.create_task(self._listen_to_funding_info_updates(market_id=market_id))
                        )
                self.add_listening_task(asyncio.create_task(self._listen_to_account_balance_updates()))
                self.add_listening_task(asyncio.create_task(self._listen_to_chain_transactions()))

                await self._initialize_timeout_height()

    async def stop(self):
        for task in self.events_listening_tasks():
            task.cancel()
        cookie_file_path = Path(self._chain_cookie_file_path())
        cookie_file_path.unlink(missing_ok=True)

    def add_listener(self, event_tag: Enum, listener: EventListener):
        self.publisher.add_listener(event_tag=event_tag, listener=listener)

    def remove_listener(self, event_tag: Enum, listener: EventListener):
        self.publisher.remove_listener(event_tag=event_tag, listener=listener)

    async def spot_trading_rules(self) -> List[TradingRule]:
        markets = await self.spot_markets()
        trading_rules = self._create_trading_rules(markets=markets)

        return trading_rules

    async def derivative_trading_rules(self) -> List[TradingRule]:
        markets = await self.derivative_markets()
        trading_rules = self._create_trading_rules(markets=markets)

        return trading_rules

    async def spot_order_book_snapshot(self, market_id: str, trading_pair: str) -> OrderBookMessage:
        async with self.throttler.execute_task(limit_id=CONSTANTS.SPOT_ORDERBOOK_LIMIT_ID):
            snapshot_data = await self.query_executor.get_spot_orderbook(market_id=market_id)

        market = await self.spot_market_info_for_id(market_id=market_id)
        bids = [(market.price_from_chain_format(chain_price=Decimal(price)),
                 market.quantity_from_chain_format(chain_quantity=Decimal(quantity)))
                for price, quantity, _ in snapshot_data["buys"]]
        asks = [(market.price_from_chain_format(chain_price=Decimal(price)),
                 market.quantity_from_chain_format(chain_quantity=Decimal(quantity)))
                for price, quantity, _ in snapshot_data["sells"]]
        snapshot_msg = OrderBookMessage(
            message_type=OrderBookMessageType.SNAPSHOT,
            content={
                "trading_pair": trading_pair,
                "update_id": snapshot_data["sequence"],
                "bids": bids,
                "asks": asks,
            },
            timestamp=snapshot_data["timestamp"] * 1e-3,
        )
        return snapshot_msg

    async def perpetual_order_book_snapshot(self, market_id: str, trading_pair: str) -> OrderBookMessage:
        async with self.throttler.execute_task(limit_id=CONSTANTS.DERIVATIVE_ORDERBOOK_LIMIT_ID):
            snapshot_data = await self.query_executor.get_derivative_orderbook(market_id=market_id)

        market = await self.derivative_market_info_for_id(market_id=market_id)
        bids = [(market.price_from_chain_format(chain_price=Decimal(price)),
                 market.quantity_from_chain_format(chain_quantity=Decimal(quantity)))
                for price, quantity, _ in snapshot_data["buys"]]
        asks = [(market.price_from_chain_format(chain_price=Decimal(price)),
                 market.quantity_from_chain_format(chain_quantity=Decimal(quantity)))
                for price, quantity, _ in snapshot_data["sells"]]
        snapshot_msg = OrderBookMessage(
            message_type=OrderBookMessageType.SNAPSHOT,
            content={
                "trading_pair": trading_pair,
                "update_id": snapshot_data["sequence"],
                "bids": bids,
                "asks": asks,
            },
            timestamp=snapshot_data["timestamp"] * 1e-3,
        )
        return snapshot_msg

    async def last_traded_price(self, market_id: str) -> Decimal:
        price = await self._last_traded_price(market_id=market_id)
        return price

    async def all_account_balances(self) -> Dict[str, Dict[str, Decimal]]:
        account_address = self.portfolio_account_injective_address

        async with self.throttler.execute_task(limit_id=CONSTANTS.PORTFOLIO_BALANCES_LIMIT_ID):
            portfolio_response = await self.query_executor.account_portfolio(account_address=account_address)

        bank_balances = portfolio_response["bankBalances"]
        sub_account_balances = portfolio_response.get("subaccounts", [])

        balances_dict: Dict[str, Dict[str, Decimal]] = {}

        if self._uses_default_portfolio_subaccount():
            for bank_entry in bank_balances:
                token = await self.token(denom=bank_entry["denom"])
                if token is not None:
                    asset_name: str = token.unique_symbol

                    available_balance = token.value_from_chain_format(chain_value=Decimal(bank_entry["amount"]))
                    total_balance = available_balance
                    balances_dict[asset_name] = {
                        "total_balance": total_balance,
                        "available_balance": available_balance,
                    }

        for entry in sub_account_balances:
            if entry["subaccountId"] == self.portfolio_account_subaccount_id:
                token = await self.token(denom=entry["denom"])
                if token is not None:
                    asset_name: str = token.unique_symbol

                    total_balance = token.value_from_chain_format(chain_value=Decimal(entry["deposit"]["totalBalance"]))
                    available_balance = token.value_from_chain_format(
                        chain_value=Decimal(entry["deposit"]["availableBalance"]))

                    balance_element = balances_dict.get(
                        asset_name, {"total_balance": Decimal("0"), "available_balance": Decimal("0")}
                    )
                    balance_element["total_balance"] += total_balance
                    balance_element["available_balance"] += available_balance
                    balances_dict[asset_name] = balance_element

        return balances_dict

    async def account_positions(self) -> List[Position]:
        done = False
        skip = 0
        position_entries = []

        while not done:
            async with self.throttler.execute_task(limit_id=CONSTANTS.POSITIONS_LIMIT_ID):
                positions_response = await self.query_executor.get_derivative_positions(
                    subaccount_id=self.portfolio_account_subaccount_id,
                    skip=skip,
                )
            if "positions" in positions_response:
                total = int(positions_response["paging"]["total"])
                entries = positions_response["positions"]

                position_entries.extend(entries)
                done = len(position_entries) >= total
                skip += len(entries)
            else:
                done = True

        positions = []
        for position_entry in position_entries:
            position_update = await self._parse_position_update_event(event=position_entry)

            position = Position(
                trading_pair=position_update.trading_pair,
                position_side=position_update.position_side,
                unrealized_pnl=position_update.unrealized_pnl,
                entry_price=position_update.entry_price,
                amount=position_update.amount,
                leverage=position_update.leverage,
            )

            positions.append(position)

        return positions

    async def create_orders(
            self,
            spot_orders: Optional[List[GatewayInFlightOrder]] = None,
            perpetual_orders: Optional[List[GatewayPerpetualInFlightOrder]] = None,
    ) -> List[PlaceOrderResult]:
        spot_orders = spot_orders or []
        perpetual_orders = perpetual_orders or []
        results = []
        if self.order_creation_lock.locked():
            raise RuntimeError("It is not possible to create new orders because the hash manager is not synchronized")

        if len(spot_orders) > 0 or len(perpetual_orders) > 0:
            async with self.order_creation_lock:

                order_creation_messages, spot_order_hashes, derivative_order_hashes = await self._order_creation_messages(
                    spot_orders_to_create=spot_orders,
                    derivative_orders_to_create=perpetual_orders,
                )

                try:
                    result = await self._send_in_transaction(messages=order_creation_messages)
                    if result["rawLog"] != "[]" or result["txhash"] in [None, ""]:
                        raise ValueError(f"Error sending the order creation transaction ({result['rawLog']})")
                    else:
                        transaction_hash = result["txhash"]
                        results = self._place_order_results(
                            orders_to_create=spot_orders + perpetual_orders,
                            order_hashes=spot_order_hashes + derivative_order_hashes,
                            misc_updates={
                                "creation_transaction_hash": transaction_hash,
                            },
                        )
                except asyncio.CancelledError:
                    raise
                except Exception as ex:
                    results = self._place_order_results(
                        orders_to_create=spot_orders + perpetual_orders,
                        order_hashes=spot_order_hashes + derivative_order_hashes,
                        misc_updates={},
                        exception=ex,
                    )

        return results

    async def cancel_orders(
            self,
            spot_orders: Optional[List[GatewayInFlightOrder]] = None,
            perpetual_orders: Optional[List[GatewayPerpetualInFlightOrder]] = None,
    ) -> List[CancelOrderResult]:
        spot_orders = spot_orders or []
        perpetual_orders = perpetual_orders or []

        orders_with_hash = []
        spot_orders_data = []
        derivative_orders_data = []
        results = []

        if len(spot_orders) > 0 or len(perpetual_orders) > 0:
            for order in spot_orders:
                if order.exchange_order_id is None:
                    results.append(CancelOrderResult(
                        client_order_id=order.client_order_id,
                        trading_pair=order.trading_pair,
                        not_found=True,
                    ))
                else:
                    market_id = await self.market_id_for_spot_trading_pair(trading_pair=order.trading_pair)
                    order_data = self._generate_injective_order_data(order=order, market_id=market_id)
                    spot_orders_data.append(order_data)
                    orders_with_hash.append(order)

            for order in perpetual_orders:
                if order.exchange_order_id is None:
                    results.append(CancelOrderResult(
                        client_order_id=order.client_order_id,
                        trading_pair=order.trading_pair,
                        not_found=True,
                    ))
                else:
                    market_id = await self.market_id_for_derivative_trading_pair(trading_pair=order.trading_pair)
                    order_data = self._generate_injective_order_data(order=order, market_id=market_id)
                    derivative_orders_data.append(order_data)
                    orders_with_hash.append(order)

            delegated_message = self._order_cancel_message(
                spot_orders_to_cancel=spot_orders_data,
                derivative_orders_to_cancel=derivative_orders_data,
            )

            try:
                result = await self._send_in_transaction(messages=[delegated_message])
                if result["rawLog"] != "[]":
                    raise ValueError(f"Error sending the order cancel transaction ({result['rawLog']})")
                else:
                    cancel_transaction_hash = result.get("txhash", "")
                    results.extend([
                        CancelOrderResult(
                            client_order_id=order.client_order_id,
                            trading_pair=order.trading_pair,
                            misc_updates={"cancelation_transaction_hash": cancel_transaction_hash},
                        ) for order in orders_with_hash
                    ])
            except asyncio.CancelledError:
                raise
            except Exception as ex:
                results.extend([
                    CancelOrderResult(
                        client_order_id=order.client_order_id,
                        trading_pair=order.trading_pair,
                        exception=ex,
                    ) for order in orders_with_hash
                ])

        return results

    async def cancel_all_subaccount_orders(
            self,
            spot_markets_ids: Optional[List[str]] = None,
            perpetual_markets_ids: Optional[List[str]] = None,
    ):
        spot_markets_ids = spot_markets_ids or []
        perpetual_markets_ids = perpetual_markets_ids or []

        delegated_message = self._all_subaccount_orders_cancel_message(
            spot_markets_ids=spot_markets_ids,
            derivative_markets_ids=perpetual_markets_ids,
        )

        result = await self._send_in_transaction(messages=[delegated_message])
        if result["rawLog"] != "[]":
            raise ValueError(f"Error sending the order cancel transaction ({result['rawLog']})")

    async def spot_trade_updates(self, market_ids: List[str], start_time: float) -> List[TradeUpdate]:
        done = False
        skip = 0
        trade_entries = []

        while not done:
            async with self.throttler.execute_task(limit_id=CONSTANTS.SPOT_TRADES_LIMIT_ID):
                trades_response = await self.query_executor.get_spot_trades(
                    market_ids=market_ids,
                    subaccount_id=self.portfolio_account_subaccount_id,
                    start_time=int(start_time * 1e3),
                    skip=skip,
                )
            if "trades" in trades_response:
                total = int(trades_response["paging"]["total"])
                entries = trades_response["trades"]

                trade_entries.extend(entries)
                done = len(trade_entries) >= total
                skip += len(entries)
            else:
                done = True

        trade_updates = [await self._parse_spot_trade_entry(trade_info=trade_info) for trade_info in trade_entries]

        return trade_updates

    async def perpetual_trade_updates(self, market_ids: List[str], start_time: float) -> List[TradeUpdate]:
        done = False
        skip = 0
        trade_entries = []

        while not done:
            async with self.throttler.execute_task(limit_id=CONSTANTS.DERIVATIVE_TRADES_LIMIT_ID):
                trades_response = await self.query_executor.get_derivative_trades(
                    market_ids=market_ids,
                    subaccount_id=self.portfolio_account_subaccount_id,
                    start_time=int(start_time * 1e3),
                    skip=skip,
                )
            if "trades" in trades_response:
                total = int(trades_response["paging"]["total"])
                entries = trades_response["trades"]

                trade_entries.extend(entries)
                done = len(trade_entries) >= total
                skip += len(entries)
            else:
                done = True

        trade_updates = [await self._parse_derivative_trade_entry(trade_info=trade_info) for trade_info in trade_entries]

        return trade_updates

    async def spot_order_updates(self, market_ids: List[str], start_time: float) -> List[OrderUpdate]:
        done = False
        skip = 0
        order_entries = []

        while not done:
            async with self.throttler.execute_task(limit_id=CONSTANTS.SPOT_ORDERS_HISTORY_LIMIT_ID):
                orders_response = await self.query_executor.get_historical_spot_orders(
                    market_ids=market_ids,
                    subaccount_id=self.portfolio_account_subaccount_id,
                    start_time=int(start_time * 1e3),
                    skip=skip,
                )
            if "orders" in orders_response:
                total = int(orders_response["paging"]["total"])
                entries = orders_response["orders"]

                order_entries.extend(entries)
                done = len(order_entries) >= total
                skip += len(entries)
            else:
                done = True

        order_updates = [await self._parse_order_entry(order_info=order_info) for order_info in order_entries]

        return order_updates

    async def perpetual_order_updates(self, market_ids: List[str], start_time: float) -> List[OrderUpdate]:
        done = False
        skip = 0
        order_entries = []

        while not done:
            async with self.throttler.execute_task(limit_id=CONSTANTS.DERIVATIVE_ORDERS_HISTORY_LIMIT_ID):
                orders_response = await self.query_executor.get_historical_derivative_orders(
                    market_ids=market_ids,
                    subaccount_id=self.portfolio_account_subaccount_id,
                    start_time=int(start_time * 1e3),
                    skip=skip,
                )
            if "orders" in orders_response:
                total = int(orders_response["paging"]["total"])
                entries = orders_response["orders"]

                order_entries.extend(entries)
                done = len(order_entries) >= total
                skip += len(entries)
            else:
                done = True

        order_updates = [await self._parse_order_entry(order_info=order_info) for order_info in order_entries]

        return order_updates

    async def reset_order_hash_generator(self, active_orders: List[GatewayInFlightOrder]):
        if not self.order_creation_lock.locked:
            raise RuntimeError("The order creation lock should be acquired before resetting the order hash manager")
        transactions_to_wait_before_reset = set()
        for order in active_orders:
            if order.creation_transaction_hash is not None and order.current_state == OrderState.PENDING_CREATE:
                transactions_to_wait_before_reset.add(order.creation_transaction_hash)
        transaction_wait_tasks = [
            asyncio.wait_for(
                self._transaction_from_chain(tx_hash=transaction_hash, retries=2),
                timeout=self.TRANSACTIONS_LOOKUP_TIMEOUT
            )
            for transaction_hash in transactions_to_wait_before_reset
        ]
        await safe_gather(*transaction_wait_tasks, return_exceptions=True)
        self._reset_order_hash_manager()

    async def get_spot_trading_fees(self) -> Dict[str, TradeFeeSchema]:
        markets = await self.spot_markets()
        fees = await self._create_trading_fees(markets=markets)

        return fees

    async def get_derivative_trading_fees(self) -> Dict[str, TradeFeeSchema]:
        markets = await self.derivative_markets()
        fees = await self._create_trading_fees(markets=markets)

        return fees

    async def funding_info(self, market_id: str) -> FundingInfo:
        funding_rate = await self.last_funding_rate(market_id=market_id)
        oracle_price = await self._oracle_price(market_id=market_id)
        last_traded_price = await self.last_traded_price(market_id=market_id)
        updated_market_info = await self._updated_derivative_market_info_for_id(market_id=market_id)

        funding_info = FundingInfo(
            trading_pair=await self.trading_pair_for_market(market_id=market_id),
            index_price=last_traded_price,  # Use the last traded price as the index_price
            mark_price=oracle_price,
            next_funding_utc_timestamp=updated_market_info.next_funding_timestamp(),
            rate=funding_rate,
        )
        return funding_info

    async def last_funding_rate(self, market_id: str) -> Decimal:
        async with self.throttler.execute_task(limit_id=CONSTANTS.FUNDING_RATES_LIMIT_ID):
            response = await self.query_executor.get_funding_rates(market_id=market_id, limit=1)
        rate = Decimal(response["fundingRates"][0]["rate"])

        return rate

    async def last_funding_payment(self, market_id: str) -> Tuple[Decimal, float]:
        async with self.throttler.execute_task(limit_id=CONSTANTS.FUNDING_PAYMENTS_LIMIT_ID):
            response = await self.query_executor.get_funding_payments(
                subaccount_id=self.portfolio_account_subaccount_id,
                market_id=market_id,
                limit=1
            )

        last_payment = Decimal(-1)
        last_timestamp = 0
        payments = response.get("payments", [])

        if len(payments) > 0:
            last_payment = Decimal(payments[0]["amount"])
            last_timestamp = int(payments[0]["timestamp"]) * 1e-3

        return last_payment, last_timestamp

    @abstractmethod
    async def _initialize_timeout_height(self):
        raise NotImplementedError

    @abstractmethod
    def _sign_and_encode(self, transaction: Transaction) -> bytes:
        raise NotImplementedError

    @abstractmethod
    def _uses_default_portfolio_subaccount(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    def _calculate_order_hashes(
            self,
            spot_orders: List[GatewayInFlightOrder],
            derivative_orders: [GatewayPerpetualInFlightOrder]
    ) -> Tuple[List[str], List[str]]:
        raise NotImplementedError

    @abstractmethod
    def _reset_order_hash_manager(self):
        raise NotImplementedError

    @abstractmethod
    async def _order_creation_messages(
            self,
            spot_orders_to_create: List[GatewayInFlightOrder],
            derivative_orders_to_create: List[GatewayPerpetualInFlightOrder],
    ) -> Tuple[List[any_pb2.Any], List[str], List[str]]:
        raise NotImplementedError

    @abstractmethod
    def _order_cancel_message(
            self,
            spot_orders_to_cancel: List[injective_exchange_tx_pb.OrderData],
            derivative_orders_to_cancel: List[injective_exchange_tx_pb.OrderData]
    ) -> any_pb2.Any:
        raise NotImplementedError

    @abstractmethod
    def _all_subaccount_orders_cancel_message(
            self,
            spot_markets_ids: List[str],
            derivative_markets_ids: List[str]
    ) -> any_pb2.Any:
        raise NotImplementedError

    @abstractmethod
    def _generate_injective_order_data(self, order: GatewayInFlightOrder, market_id: str) -> injective_exchange_tx_pb.OrderData:
        raise NotImplementedError

    @abstractmethod
    async def _updated_derivative_market_info_for_id(self, market_id: str) -> InjectiveDerivativeMarket:
        raise NotImplementedError

    @abstractmethod
    def _place_order_results(
            self,
            orders_to_create: List[GatewayInFlightOrder],
            order_hashes: List[str],
            misc_updates: Dict[str, Any],
            exception: Optional[Exception] = None,
    ) -> List[PlaceOrderResult]:
        raise NotImplementedError

    def _chain_cookie_file_path(self) -> str:
        return f"{os.path.join(os.path.dirname(__file__), '../.injective_cookie')}"

    async def _last_traded_price(self, market_id: str) -> Decimal:
        price = Decimal("nan")
        if market_id in await self.spot_market_and_trading_pair_map():
            market = await self.spot_market_info_for_id(market_id=market_id)
            async with self.throttler.execute_task(limit_id=CONSTANTS.SPOT_TRADES_LIMIT_ID):
                trades_response = await self.query_executor.get_spot_trades(
                    market_ids=[market_id],
                    limit=1,
                )
            if len(trades_response["trades"]) > 0:
                price = market.price_from_chain_format(
                    chain_price=Decimal(trades_response["trades"][0]["price"]["price"]))

        else:
            market = await self.derivative_market_info_for_id(market_id=market_id)
            async with self.throttler.execute_task(limit_id=CONSTANTS.DERIVATIVE_TRADES_LIMIT_ID):
                trades_response = await self.query_executor.get_derivative_trades(
                    market_ids=[market_id],
                    limit=1,
                )
            if len(trades_response["trades"]) > 0:
                price = market.price_from_chain_format(
                    chain_price=Decimal(trades_response["trades"][0]["positionDelta"]["executionPrice"]))

        return price

    async def _transaction_from_chain(self, tx_hash: str, retries: int) -> int:
        executed_tries = 0
        found = False
        block_height = None

        while executed_tries < retries and not found:
            executed_tries += 1
            try:
                async with self.throttler.execute_task(limit_id=CONSTANTS.SPOT_ORDERS_HISTORY_LIMIT_ID):
                    block_height = await self.query_executor.get_tx_block_height(tx_hash=tx_hash)
                found = True
            except ValueError:
                # No block found containing the transaction, continue the search
                raise NotImplementedError
            if executed_tries < retries and not found:
                await self._sleep(CONSTANTS.EXPECTED_BLOCK_TIME)

        if not found:
            raise ValueError(f"The transaction {tx_hash} is not included in any mined block")

        return block_height

    async def _oracle_price(self, market_id: str) -> Decimal:
        market = await self.derivative_market_info_for_id(market_id=market_id)
        async with self.throttler.execute_task(limit_id=CONSTANTS.ORACLE_PRICES_LIMIT_ID):
            response = await self.query_executor.get_oracle_prices(
                base_symbol=market.oracle_base(),
                quote_symbol=market.oracle_quote(),
                oracle_type=market.oracle_type(),
                oracle_scale_factor=0,
            )
        price = Decimal(response["price"])

        return price

    def _spot_order_book_updates_stream(self, market_ids: List[str]):
        stream = self.query_executor.spot_order_book_updates_stream(market_ids=market_ids)
        return stream

    def _public_spot_trades_stream(self, market_ids: List[str]):
        stream = self.query_executor.public_spot_trades_stream(market_ids=market_ids)
        return stream

    def _derivative_order_book_updates_stream(self, market_ids: List[str]):
        stream = self.query_executor.derivative_order_book_updates_stream(market_ids=market_ids)
        return stream

    def _public_derivative_trades_stream(self, market_ids: List[str]):
        stream = self.query_executor.public_derivative_trades_stream(market_ids=market_ids)
        return stream

    def _oracle_prices_stream(self, oracle_base: str, oracle_quote: str, oracle_type: str):
        stream = self.query_executor.oracle_prices_stream(
            oracle_base=oracle_base, oracle_quote=oracle_quote, oracle_type=oracle_type
        )
        return stream

    def _subaccount_positions_stream(self):
        stream = self.query_executor.subaccount_positions_stream(subaccount_id=self.portfolio_account_subaccount_id)
        return stream

    def _subaccount_balance_stream(self):
        stream = self.query_executor.subaccount_balance_stream(subaccount_id=self.portfolio_account_subaccount_id)
        return stream

    def _subaccount_spot_orders_stream(self, market_id: str):
        stream = self.query_executor.subaccount_historical_spot_orders_stream(
            market_id=market_id, subaccount_id=self.portfolio_account_subaccount_id
        )
        return stream

    def _subaccount_derivative_orders_stream(self, market_id: str):
        stream = self.query_executor.subaccount_historical_derivative_orders_stream(
            market_id=market_id, subaccount_id=self.portfolio_account_subaccount_id
        )
        return stream

    def _transactions_stream(self):
        stream = self.query_executor.transactions_stream()
        return stream

    async def _parse_spot_trade_entry(self, trade_info: Dict[str, Any]) -> TradeUpdate:
        exchange_order_id: str = trade_info["orderHash"]
        market = await self.spot_market_info_for_id(market_id=trade_info["marketId"])
        trading_pair = await self.trading_pair_for_market(market_id=trade_info["marketId"])
        trade_id: str = trade_info["tradeId"]

        price = market.price_from_chain_format(chain_price=Decimal(trade_info["price"]["price"]))
        size = market.quantity_from_chain_format(chain_quantity=Decimal(trade_info["price"]["quantity"]))
        trade_type = TradeType.BUY if trade_info["tradeDirection"] == "buy" else TradeType.SELL
        is_taker: bool = trade_info["executionSide"] == "taker"
        trade_time = int(trade_info["executedAt"]) * 1e-3

        fee_amount = market.quote_token.value_from_chain_format(chain_value=Decimal(trade_info["fee"]))
        fee = TradeFeeBase.new_spot_fee(
            fee_schema=TradeFeeSchema(),
            trade_type=trade_type,
            percent_token=market.quote_token.symbol,
            flat_fees=[TokenAmount(amount=fee_amount, token=market.quote_token.symbol)]
        )

        trade_update = TradeUpdate(
            trade_id=trade_id,
            client_order_id=None,
            exchange_order_id=exchange_order_id,
            trading_pair=trading_pair,
            fill_timestamp=trade_time,
            fill_price=price,
            fill_base_amount=size,
            fill_quote_amount=size * price,
            fee=fee,
            is_taker=is_taker,
        )

        return trade_update

    async def _parse_derivative_trade_entry(self, trade_info: Dict[str, Any]) -> TradeUpdate:
        exchange_order_id: str = trade_info["orderHash"]
        market = await self.derivative_market_info_for_id(market_id=trade_info["marketId"])
        trading_pair = await self.trading_pair_for_market(market_id=trade_info["marketId"])
        trade_id: str = trade_info["tradeId"]

        price = market.price_from_chain_format(chain_price=Decimal(trade_info["positionDelta"]["executionPrice"]))
        size = market.quantity_from_chain_format(chain_quantity=Decimal(trade_info["positionDelta"]["executionQuantity"]))
        is_taker: bool = trade_info["executionSide"] == "taker"
        trade_time = int(trade_info["executedAt"]) * 1e-3

        fee_amount = market.quote_token.value_from_chain_format(chain_value=Decimal(trade_info["fee"]))
        fee = TradeFeeBase.new_perpetual_fee(
            fee_schema=TradeFeeSchema(),
            position_action=PositionAction.OPEN,  # will be changed by the exchange class
            percent_token=market.quote_token.symbol,
            flat_fees=[TokenAmount(amount=fee_amount, token=market.quote_token.symbol)]
        )

        trade_update = TradeUpdate(
            trade_id=trade_id,
            client_order_id=None,
            exchange_order_id=exchange_order_id,
            trading_pair=trading_pair,
            fill_timestamp=trade_time,
            fill_price=price,
            fill_base_amount=size,
            fill_quote_amount=size * price,
            fee=fee,
            is_taker=is_taker,
        )

        return trade_update

    async def _parse_order_entry(self, order_info: Dict[str, Any]) -> OrderUpdate:
        exchange_order_id: str = order_info["orderHash"]
        trading_pair = await self.trading_pair_for_market(market_id=order_info["marketId"])

        status_update = OrderUpdate(
            trading_pair=trading_pair,
            update_timestamp=int(order_info["updatedAt"]) * 1e-3,
            new_state=CONSTANTS.ORDER_STATE_MAP[order_info["state"]],
            client_order_id=None,
            exchange_order_id=exchange_order_id,
        )

        return status_update

    async def _parse_position_update_event(self, event: Dict[str, Any]) -> PositionUpdateEvent:
        market = await self.derivative_market_info_for_id(market_id=event["marketId"])
        trading_pair = await self.trading_pair_for_market(market_id=event["marketId"])

        if "direction" in event:
            position_side = PositionSide[event["direction"].upper()]
            amount_sign = Decimal(-1) if position_side == PositionSide.SHORT else Decimal(1)
            chain_entry_price = Decimal(event["entryPrice"])
            chain_mark_price = Decimal(event["markPrice"])
            chain_amount = Decimal(event["quantity"])
            chain_margin = Decimal(event["margin"])
            entry_price = market.price_from_chain_format(chain_price=chain_entry_price)
            mark_price = market.price_from_chain_format(chain_price=chain_mark_price)
            amount = market.quantity_from_chain_format(chain_quantity=chain_amount)
            leverage = (chain_amount * chain_entry_price) / chain_margin
            unrealized_pnl = (mark_price - entry_price) * amount * amount_sign
        else:
            position_side = None
            entry_price = unrealized_pnl = amount = Decimal("0")
            leverage = amount_sign = Decimal("1")

        parsed_event = PositionUpdateEvent(
            timestamp=int(event["updatedAt"]) * 1e-3,
            trading_pair=trading_pair,
            position_side=position_side,
            unrealized_pnl=unrealized_pnl,
            entry_price=entry_price,
            amount=amount * amount_sign,
            leverage=leverage,
        )

        return parsed_event

    async def _send_in_transaction(self, messages: List[any_pb2.Any]) -> Dict[str, Any]:
        transaction = Transaction()
        transaction.with_messages(*messages)
        transaction.with_sequence(await self.trading_account_sequence())
        transaction.with_account_num(await self.trading_account_number())
        transaction.with_chain_id(self.injective_chain_id)

        signed_transaction_data = self._sign_and_encode(transaction=transaction)

        async with self.throttler.execute_task(limit_id=CONSTANTS.SIMULATE_TRANSACTION_LIMIT_ID):
            try:
                simulation_result = await self.query_executor.simulate_tx(tx_byte=signed_transaction_data)
            except RuntimeError as simulation_ex:
                if CONSTANTS.ACCOUNT_SEQUENCE_MISMATCH_ERROR in str(simulation_ex):
                    await self.initialize_trading_account()
                raise

        gas_limit = int(simulation_result["gasInfo"]["gasUsed"]) + CONSTANTS.EXTRA_TRANSACTION_GAS
        fee = [self.composer.Coin(
            amount=gas_limit * CONSTANTS.DEFAULT_GAS_PRICE,
            denom=self.fee_denom,
        )]

        transaction.with_gas(gas_limit)
        transaction.with_fee(fee)
        transaction.with_memo("")
        transaction.with_timeout_height(await self.timeout_height())

        signed_transaction_data = self._sign_and_encode(transaction=transaction)

        async with self.throttler.execute_task(limit_id=CONSTANTS.SEND_TRANSACTION):
            result = await self.query_executor.send_tx_sync_mode(tx_byte=signed_transaction_data)

        if CONSTANTS.ACCOUNT_SEQUENCE_MISMATCH_ERROR in result.get("rawLog", ""):
            await self.initialize_trading_account()

        return result

    async def _listen_to_spot_order_book_updates(self, market_ids: List[str]):
        await self._listen_stream_events(
            stream_provider=partial(self._spot_order_book_updates_stream, market_ids=market_ids),
            event_processor=self._process_order_book_update,
            event_name_for_errors="spot order book",
        )

    async def _listen_to_public_spot_trades(self, market_ids: List[str]):
        await self._listen_stream_events(
            stream_provider=partial(self._public_spot_trades_stream, market_ids=market_ids),
            event_processor=self._process_public_spot_trade_update,
            event_name_for_errors="public spot trade",
        )

    async def _listen_to_derivative_order_book_updates(self, market_ids: List[str]):
        await self._listen_stream_events(
            stream_provider=partial(self._derivative_order_book_updates_stream, market_ids=market_ids),
            event_processor=self._process_order_book_update,
            event_name_for_errors="derivative order book",
        )

    async def _listen_to_public_derivative_trades(self, market_ids: List[str]):
        await self._listen_stream_events(
            stream_provider=partial(self._public_derivative_trades_stream, market_ids=market_ids),
            event_processor=self._process_public_derivative_trade_update,
            event_name_for_errors="public derivative trade",
        )

    async def _listen_to_funding_info_updates(self, market_id: str):
        market = await self.derivative_market_info_for_id(market_id=market_id)
        await self._listen_stream_events(
            stream_provider=partial(
                self._oracle_prices_stream,
                oracle_base=market.oracle_base(),
                oracle_quote=market.oracle_quote(),
                oracle_type=market.oracle_type()
            ),
            event_processor=self._process_oracle_price_update,
            event_name_for_errors="funding info",
            market_id=market_id,
        )

    async def _listen_to_positions_updates(self):
        await self._listen_stream_events(
            stream_provider=self._subaccount_positions_stream,
            event_processor=self._process_position_update,
            event_name_for_errors="position",
        )

    async def _listen_to_account_balance_updates(self):
        await self._listen_stream_events(
            stream_provider=self._subaccount_balance_stream,
            event_processor=self._process_subaccount_balance_update,
            event_name_for_errors="balance",
        )

    async def _listen_to_subaccount_spot_order_updates(self, market_id: str):
        await self._listen_stream_events(
            stream_provider=partial(self._subaccount_spot_orders_stream, market_id=market_id),
            event_processor=self._process_subaccount_order_update,
            event_name_for_errors="subaccount spot order",
        )

    async def _listen_to_subaccount_derivative_order_updates(self, market_id: str):
        await self._listen_stream_events(
            stream_provider=partial(self._subaccount_derivative_orders_stream, market_id=market_id),
            event_processor=self._process_subaccount_order_update,
            event_name_for_errors="subaccount derivative order",
        )

    async def _listen_to_chain_transactions(self):
        await self._listen_stream_events(
            stream_provider=self._transactions_stream,
            event_processor=self._process_transaction_update,
            event_name_for_errors="transaction",
        )

    async def _listen_stream_events(
            self,
            stream_provider: Callable,
            event_processor: Callable,
            event_name_for_errors: str,
            **kwargs):
        while True:
            self.logger().debug(f"Starting stream for {event_name_for_errors}")
            try:
                stream = stream_provider()
                async for event in stream:
                    try:
                        await event_processor(event, **kwargs)
                    except asyncio.CancelledError:
                        raise
                    except Exception as ex:
                        self.logger().warning(f"Invalid {event_name_for_errors} event format ({ex})\n{event}")
            except asyncio.CancelledError:
                raise
            except Exception as ex:
                self.logger().error(f"Error while listening to {event_name_for_errors} stream, reconnecting ... ({ex})")
            self.logger().debug(f"Reconnecting stream for {event_name_for_errors}")

    async def _process_order_book_update(self, order_book_update: Dict[str, Any]):
        market_id = order_book_update["marketId"]
        if market_id in await self.spot_market_and_trading_pair_map():
            market_info = await self.spot_market_info_for_id(market_id=market_id)
        else:
            market_info = await self.derivative_market_info_for_id(market_id=market_id)

        trading_pair = await self.trading_pair_for_market(market_id=market_id)
        bids = [(market_info.price_from_chain_format(chain_price=Decimal(bid["price"])),
                 market_info.quantity_from_chain_format(chain_quantity=Decimal(bid["quantity"])))
                for bid in order_book_update.get("buys", [])]
        asks = [(market_info.price_from_chain_format(chain_price=Decimal(ask["price"])),
                 market_info.quantity_from_chain_format(chain_quantity=Decimal(ask["quantity"])))
                for ask in order_book_update.get("sells", [])]

        order_book_message_content = {
            "trading_pair": trading_pair,
            "update_id": int(order_book_update["sequence"]),
            "bids": bids,
            "asks": asks,
        }
        diff_message = OrderBookMessage(
            message_type=OrderBookMessageType.DIFF,
            content=order_book_message_content,
            timestamp=int(order_book_update["updatedAt"]) * 1e-3,
        )
        self.publisher.trigger_event(
            event_tag=OrderBookDataSourceEvent.DIFF_EVENT, message=diff_message
        )

    async def _process_public_spot_trade_update(self, trade_update: Dict[str, Any]):
        market_id = trade_update["marketId"]
        market_info = await self.spot_market_info_for_id(market_id=market_id)

        trading_pair = await self.trading_pair_for_market(market_id=market_id)
        timestamp = int(trade_update["executedAt"]) * 1e-3
        trade_type = float(TradeType.BUY.value) if trade_update["tradeDirection"] == "buy" else float(
            TradeType.SELL.value)
        message_content = {
            "trade_id": trade_update["tradeId"],
            "trading_pair": trading_pair,
            "trade_type": trade_type,
            "amount": market_info.quantity_from_chain_format(
                chain_quantity=Decimal(str(trade_update["price"]["quantity"]))),
            "price": market_info.price_from_chain_format(chain_price=Decimal(str(trade_update["price"]["price"]))),
        }
        trade_message = OrderBookMessage(
            message_type=OrderBookMessageType.TRADE,
            content=message_content,
            timestamp=timestamp,
        )
        self.publisher.trigger_event(
            event_tag=OrderBookDataSourceEvent.TRADE_EVENT, message=trade_message
        )

        update = await self._parse_spot_trade_entry(trade_info=trade_update)
        self.publisher.trigger_event(event_tag=MarketEvent.TradeUpdate, message=update)

    async def _process_public_derivative_trade_update(self, trade_update: Dict[str, Any]):
        market_id = trade_update["marketId"]
        market_info = await self.derivative_market_info_for_id(market_id=market_id)

        trading_pair = await self.trading_pair_for_market(market_id=market_id)
        timestamp = int(trade_update["executedAt"]) * 1e-3
        trade_type = (float(TradeType.BUY.value)
                      if trade_update["positionDelta"]["tradeDirection"] == "buy"
                      else float(TradeType.SELL.value))
        message_content = {
            "trade_id": trade_update["tradeId"],
            "trading_pair": trading_pair,
            "trade_type": trade_type,
            "amount": market_info.quantity_from_chain_format(
                chain_quantity=Decimal(str(trade_update["positionDelta"]["executionQuantity"]))),
            "price": market_info.price_from_chain_format(
                chain_price=Decimal(str(trade_update["positionDelta"]["executionPrice"]))),
        }
        trade_message = OrderBookMessage(
            message_type=OrderBookMessageType.TRADE,
            content=message_content,
            timestamp=timestamp,
        )
        self.publisher.trigger_event(
            event_tag=OrderBookDataSourceEvent.TRADE_EVENT, message=trade_message
        )

        update = await self._parse_derivative_trade_entry(trade_info=trade_update)
        self.publisher.trigger_event(event_tag=MarketEvent.TradeUpdate, message=update)

    async def _process_oracle_price_update(self, oracle_price_update: Dict[str, Any], market_id: str):
        trading_pair = await self.trading_pair_for_market(market_id=market_id)
        funding_info = await self.funding_info(market_id=market_id)
        funding_info_update = FundingInfoUpdate(
            trading_pair=trading_pair,
            index_price=funding_info.index_price,
            mark_price=funding_info.mark_price,
            next_funding_utc_timestamp=funding_info.next_funding_utc_timestamp,
            rate=funding_info.rate,
        )
        self.publisher.trigger_event(event_tag=MarketEvent.FundingInfo, message=funding_info_update)

    async def _process_position_update(self, position_event: Dict[str, Any]):
        parsed_event = await self._parse_position_update_event(event=position_event)
        self.publisher.trigger_event(event_tag=AccountEvent.PositionUpdate, message=parsed_event)

    async def _process_subaccount_balance_update(self, balance_event: Dict[str, Any]):
        updated_token = await self.token(denom=balance_event["balance"]["denom"])
        if updated_token is not None:
            if self._uses_default_portfolio_subaccount():
                token_balances = await self.all_account_balances()
                total_balance = token_balances[updated_token.unique_symbol]["total_balance"]
                available_balance = token_balances[updated_token.unique_symbol]["available_balance"]
            else:
                updated_total = balance_event["balance"]["deposit"].get("totalBalance")
                total_balance = (updated_token.value_from_chain_format(chain_value=Decimal(updated_total))
                                 if updated_total is not None
                                 else None)
                updated_available = balance_event["balance"]["deposit"].get("availableBalance")
                available_balance = (updated_token.value_from_chain_format(chain_value=Decimal(updated_available))
                                     if updated_available is not None
                                     else None)

            balance_msg = BalanceUpdateEvent(
                timestamp=int(balance_event["timestamp"]) * 1e3,
                asset_name=updated_token.unique_symbol,
                total_balance=total_balance,
                available_balance=available_balance,
            )
            self.publisher.trigger_event(event_tag=AccountEvent.BalanceEvent, message=balance_msg)

    async def _process_subaccount_order_update(self, order_event: Dict[str, Any]):
        order_update = await self._parse_order_entry(order_info=order_event)
        self.publisher.trigger_event(event_tag=MarketEvent.OrderUpdate, message=order_update)

    async def _process_transaction_update(self, transaction_event: Dict[str, Any]):
        self.publisher.trigger_event(event_tag=InjectiveEvent.ChainTransactionEvent, message=transaction_event)

    async def _create_spot_order_definition(self, order: GatewayInFlightOrder):
        market_id = await self.market_id_for_spot_trading_pair(order.trading_pair)
        definition = self.composer.SpotOrder(
            market_id=market_id,
            subaccount_id=self.portfolio_account_subaccount_id,
            fee_recipient=self.portfolio_account_injective_address,
            price=order.price,
            quantity=order.amount,
            is_buy=order.trade_type == TradeType.BUY,
            is_po=order.order_type == OrderType.LIMIT_MAKER
        )
        return definition

    async def _create_derivative_order_definition(self, order: GatewayPerpetualInFlightOrder):
        market_id = await self.market_id_for_derivative_trading_pair(order.trading_pair)
        definition = self.composer.DerivativeOrder(
            market_id=market_id,
            subaccount_id=self.portfolio_account_subaccount_id,
            fee_recipient=self.portfolio_account_injective_address,
            price=order.price,
            quantity=order.amount,
            leverage=order.leverage,
            is_buy=order.trade_type == TradeType.BUY,
            is_po=order.order_type == OrderType.LIMIT_MAKER,
            is_reduce_only = order.position == PositionAction.CLOSE,
        )
        return definition

    def _create_trading_rules(
            self, markets: List[Union[InjectiveSpotMarket, InjectiveDerivativeMarket]]
    ) -> List[TradingRule]:
        trading_rules = []
        for market in markets:
            try:
                min_price_tick_size = market.min_price_tick_size()
                min_quantity_tick_size = market.min_quantity_tick_size()
                trading_rule = TradingRule(
                    trading_pair=market.trading_pair(),
                    min_order_size=min_quantity_tick_size,
                    min_price_increment=min_price_tick_size,
                    min_base_amount_increment=min_quantity_tick_size,
                    min_quote_amount_increment=min_price_tick_size,
                )
                trading_rules.append(trading_rule)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().exception(f"Error parsing the trading pair rule: {market.market_info}. Skipping...")

        return trading_rules

    async def _create_trading_fees(
            self, markets: List[Union[InjectiveSpotMarket, InjectiveDerivativeMarket]]
    ) -> Dict[str, TradeFeeSchema]:
        fees = {}
        for market in markets:
            trading_pair = await self.trading_pair_for_market(market_id=market.market_id)
            fees[trading_pair] = TradeFeeSchema(
                percent_fee_token=market.quote_token.unique_symbol,
                maker_percent_fee_decimal=market.maker_fee_rate(),
                taker_percent_fee_decimal=market.taker_fee_rate(),
            )

        return fees

    def _time(self):
        return time.time()

    async def _sleep(self, delay: float):
        """
        Method created to enable tests to prevent processes from sleeping
        """
        await asyncio.sleep(delay)
