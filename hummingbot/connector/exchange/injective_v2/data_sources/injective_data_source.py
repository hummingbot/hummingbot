import asyncio
import base64
import logging
import time
from abc import ABC, abstractmethod
from decimal import Decimal
from enum import Enum
from typing import Any, Callable, Dict, List, Mapping, Optional, Tuple, Union

from bidict import bidict
from google.protobuf import any_pb2
from grpc import RpcError
from pyinjective import Transaction
from pyinjective.composer import Composer, injective_exchange_tx_pb
from pyinjective.core.market import DerivativeMarket, SpotMarket
from pyinjective.core.token import Token

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
from hummingbot.core.data_type.in_flight_order import OrderUpdate, TradeUpdate
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

    @property
    @abstractmethod
    def last_received_message_timestamp(self):
        raise NotImplementedError

    @abstractmethod
    async def composer(self) -> Composer:
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
                spot_market_ids = []
                derivative_market_ids = []
                spot_markets = []
                derivative_markets = []
                for market_id in market_ids:
                    if market_id in await self.spot_market_and_trading_pair_map():
                        market = await self.spot_market_info_for_id(market_id=market_id)
                        spot_markets.append(market)
                        spot_market_ids.append(market_id)
                    else:
                        market = await self.derivative_market_info_for_id(market_id=market_id)
                        derivative_markets.append(market)
                        derivative_market_ids.append(market_id)

                self.add_listening_task(asyncio.create_task(self._listen_to_chain_transactions()))
                self.add_listening_task(asyncio.create_task(self._listen_to_chain_updates(
                    spot_markets=spot_markets,
                    derivative_markets=derivative_markets,
                    subaccount_ids=[self.portfolio_account_subaccount_id]
                )))

                await self._initialize_timeout_height()

    async def stop(self):
        for task in self.events_listening_tasks():
            task.cancel()

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

        bank_balances = portfolio_response["portfolio"]["bankBalances"]
        sub_account_balances = portfolio_response["portfolio"].get("subaccounts", [])

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
        if len(spot_orders) > 0 or len(perpetual_orders) > 0:
            order_creation_messages = await self._order_creation_messages(
                spot_orders_to_create=spot_orders,
                derivative_orders_to_create=perpetual_orders,
            )

            try:
                result = await self._send_in_transaction(messages=order_creation_messages)
                if result["code"] != 0 or result["txhash"] in [None, ""]:
                    raise ValueError(f"Error sending the order creation transaction ({result['rawLog']})")
                else:
                    transaction_hash = result["txhash"]
                    results = self._place_order_results(
                        orders_to_create=spot_orders + perpetual_orders,
                        misc_updates={
                            "creation_transaction_hash": transaction_hash,
                        },
                    )
            except asyncio.CancelledError:
                raise
            except Exception as ex:
                self.logger().debug(
                    f"Error broadcasting transaction to create orders (message: {order_creation_messages})")
                results = self._place_order_results(
                    orders_to_create=spot_orders + perpetual_orders,
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
                market_id = await self.market_id_for_spot_trading_pair(trading_pair=order.trading_pair)
                order_data = await self._generate_injective_order_data(order=order, market_id=market_id)
                spot_orders_data.append(order_data)
                orders_with_hash.append(order)

            for order in perpetual_orders:
                market_id = await self.market_id_for_derivative_trading_pair(trading_pair=order.trading_pair)
                order_data = await self._generate_injective_order_data(order=order, market_id=market_id)
                derivative_orders_data.append(order_data)
                orders_with_hash.append(order)

            if len(orders_with_hash) > 0:
                delegated_message = await self._order_cancel_message(
                    spot_orders_to_cancel=spot_orders_data,
                    derivative_orders_to_cancel=derivative_orders_data,
                )

                try:
                    result = await self._send_in_transaction(messages=[delegated_message])
                    if result["code"] != 0:
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
                    self.logger().debug(f"Error broadcasting transaction to cancel orders (message: {delegated_message})")
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

        delegated_message = await self._all_subaccount_orders_cancel_message(
            spot_markets_ids=spot_markets_ids,
            derivative_markets_ids=perpetual_markets_ids,
        )

        result = await self._send_in_transaction(messages=[delegated_message])
        if result["code"] != 0:
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
            next_funding_utc_timestamp=int(updated_market_info["market"]["perpetualMarketInfo"]["nextFundingTimestamp"]),
            rate=funding_rate,
        )
        return funding_info

    async def last_funding_rate(self, market_id: str) -> Decimal:
        async with self.throttler.execute_task(limit_id=CONSTANTS.FUNDING_RATES_LIMIT_ID):
            response = await self.query_executor.get_funding_rates(market_id=market_id, limit=1)
        funding_rates = response.get("fundingRates", [])
        if len(funding_rates) == 0:
            rate = Decimal("0")
        else:
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
    async def _order_creation_messages(
            self,
            spot_orders_to_create: List[GatewayInFlightOrder],
            derivative_orders_to_create: List[GatewayPerpetualInFlightOrder],
    ) -> List[any_pb2.Any]:
        raise NotImplementedError

    @abstractmethod
    async def _order_cancel_message(
            self,
            spot_orders_to_cancel: List[injective_exchange_tx_pb.OrderData],
            derivative_orders_to_cancel: List[injective_exchange_tx_pb.OrderData]
    ) -> any_pb2.Any:
        raise NotImplementedError

    @abstractmethod
    async def _all_subaccount_orders_cancel_message(
            self,
            spot_markets_ids: List[str],
            derivative_markets_ids: List[str]
    ) -> any_pb2.Any:
        raise NotImplementedError

    @abstractmethod
    async def _generate_injective_order_data(self, order: GatewayInFlightOrder, market_id: str) -> injective_exchange_tx_pb.OrderData:
        raise NotImplementedError

    @abstractmethod
    async def _updated_derivative_market_info_for_id(self, market_id: str) -> Dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    async def _configure_gas_fee_for_transaction(self, transaction: Transaction):
        raise NotImplementedError

    def _place_order_results(
            self,
            orders_to_create: List[GatewayInFlightOrder],
            misc_updates: Dict[str, Any],
            exception: Optional[Exception] = None,
    ) -> List[PlaceOrderResult]:
        return [
            PlaceOrderResult(
                update_timestamp=self._time(),
                client_order_id=order.client_order_id,
                exchange_order_id=None,
                trading_pair=order.trading_pair,
                misc_updates=misc_updates,
                exception=exception
            ) for order in orders_to_create
        ]

    async def _last_traded_price(self, market_id: str) -> Decimal:
        price = Decimal("nan")
        if market_id in await self.spot_market_and_trading_pair_map():
            market = await self.spot_market_info_for_id(market_id=market_id)
            async with self.throttler.execute_task(limit_id=CONSTANTS.SPOT_TRADES_LIMIT_ID):
                trades_response = await self.query_executor.get_spot_trades(
                    market_ids=[market_id],
                    limit=1,
                )
            trades = trades_response.get("trades", [])
            if len(trades) > 0:
                price = market.price_from_chain_format(
                    chain_price=Decimal(trades[0]["price"]["price"]))

        else:
            market = await self.derivative_market_info_for_id(market_id=market_id)
            async with self.throttler.execute_task(limit_id=CONSTANTS.DERIVATIVE_TRADES_LIMIT_ID):
                trades_response = await self.query_executor.get_derivative_trades(
                    market_ids=[market_id],
                    limit=1,
                )
            trades = trades_response.get("trades", [])
            if len(trades) > 0:
                price = market.price_from_chain_format(
                    chain_price=Decimal(trades_response["trades"][0]["positionDelta"]["executionPrice"]))

        return price

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

    async def _listen_chain_stream_updates(
            self,
            spot_markets: List[InjectiveSpotMarket],
            derivative_markets: List[InjectiveDerivativeMarket],
            subaccount_ids: List[str],
            composer: Composer,
            callback: Callable,
            on_end_callback: Optional[Callable] = None,
            on_status_callback: Optional[Callable] = None,
    ):
        spot_market_ids = [market_info.market_id for market_info in spot_markets]
        derivative_market_ids = []
        oracle_price_symbols = set()

        for derivative_market_info in derivative_markets:
            derivative_market_ids.append(derivative_market_info.market_id)
            oracle_price_symbols.add(derivative_market_info.oracle_base())
            oracle_price_symbols.add(derivative_market_info.oracle_quote())

        subaccount_deposits_filter = composer.chain_stream_subaccount_deposits_filter(subaccount_ids=subaccount_ids)
        if len(spot_market_ids) > 0:
            spot_orderbooks_filter = composer.chain_stream_orderbooks_filter(market_ids=spot_market_ids)
            spot_trades_filter = composer.chain_stream_trades_filter(market_ids=spot_market_ids)
            spot_orders_filter = composer.chain_stream_orders_filter(
                subaccount_ids=subaccount_ids, market_ids=spot_market_ids,
            )
        else:
            spot_orderbooks_filter = None
            spot_trades_filter = None
            spot_orders_filter = None

        if len(derivative_market_ids) > 0:
            derivative_orderbooks_filter = composer.chain_stream_orderbooks_filter(market_ids=derivative_market_ids)
            derivative_trades_filter = composer.chain_stream_trades_filter(market_ids=derivative_market_ids)
            derivative_orders_filter = composer.chain_stream_orders_filter(
                subaccount_ids=subaccount_ids, market_ids=derivative_market_ids
            )
            positions_filter = composer.chain_stream_positions_filter(
                subaccount_ids=subaccount_ids, market_ids=derivative_market_ids
            )
            oracle_price_filter = composer.chain_stream_oracle_price_filter(symbols=list(oracle_price_symbols))
        else:
            derivative_orderbooks_filter = None
            derivative_trades_filter = None
            derivative_orders_filter = None
            positions_filter = None
            oracle_price_filter = None

        await self.query_executor.listen_chain_stream_updates(
            callback=callback,
            on_end_callback=on_end_callback,
            on_status_callback=on_status_callback,
            subaccount_deposits_filter=subaccount_deposits_filter,
            spot_trades_filter=spot_trades_filter,
            derivative_trades_filter=derivative_trades_filter,
            spot_orders_filter=spot_orders_filter,
            derivative_orders_filter=derivative_orders_filter,
            spot_orderbooks_filter=spot_orderbooks_filter,
            derivative_orderbooks_filter=derivative_orderbooks_filter,
            positions_filter=positions_filter,
            oracle_price_filter=oracle_price_filter
        )

    async def _listen_transactions_updates(
        self,
        callback: Callable,
        on_end_callback: Callable,
        on_status_callback: Callable,
    ):
        await self.query_executor.listen_transactions_updates(
            callback=callback,
            on_end_callback=on_end_callback,
            on_status_callback=on_status_callback,
        )

    async def _parse_spot_trade_entry(self, trade_info: Dict[str, Any]) -> TradeUpdate:
        exchange_order_id: str = trade_info["orderHash"]
        client_order_id: str = trade_info.get("cid", "")
        market = await self.spot_market_info_for_id(market_id=trade_info["marketId"])
        trading_pair = await self.trading_pair_for_market(market_id=trade_info["marketId"])

        price = market.price_from_chain_format(chain_price=Decimal(trade_info["price"]["price"]))
        size = market.quantity_from_chain_format(chain_quantity=Decimal(trade_info["price"]["quantity"]))
        trade_type = TradeType.BUY if trade_info["tradeDirection"] == "buy" else TradeType.SELL
        is_taker: bool = trade_info["executionSide"] == "taker"
        trade_time = int(trade_info["executedAt"]) * 1e-3
        trade_id = trade_info["tradeId"]

        fee_amount = market.quote_token.value_from_chain_format(chain_value=Decimal(trade_info["fee"]))
        fee = TradeFeeBase.new_spot_fee(
            fee_schema=TradeFeeSchema(),
            trade_type=trade_type,
            percent_token=market.quote_token.symbol,
            flat_fees=[TokenAmount(amount=fee_amount, token=market.quote_token.symbol)]
        )

        trade_update = TradeUpdate(
            trade_id=trade_id,
            client_order_id=client_order_id,
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
        client_order_id: str = trade_info.get("cid", "")
        market = await self.derivative_market_info_for_id(market_id=trade_info["marketId"])
        trading_pair = await self.trading_pair_for_market(market_id=trade_info["marketId"])

        price = market.price_from_chain_format(chain_price=Decimal(trade_info["positionDelta"]["executionPrice"]))
        size = market.quantity_from_chain_format(chain_quantity=Decimal(trade_info["positionDelta"]["executionQuantity"]))
        is_taker: bool = trade_info["executionSide"] == "taker"
        trade_time = int(trade_info["executedAt"]) * 1e-3
        trade_id = trade_info["tradeId"]

        fee_amount = market.quote_token.value_from_chain_format(chain_value=Decimal(trade_info["fee"]))
        fee = TradeFeeBase.new_perpetual_fee(
            fee_schema=TradeFeeSchema(),
            position_action=PositionAction.OPEN,  # will be changed by the exchange class
            percent_token=market.quote_token.symbol,
            flat_fees=[TokenAmount(amount=fee_amount, token=market.quote_token.symbol)]
        )

        trade_update = TradeUpdate(
            trade_id=trade_id,
            client_order_id=client_order_id,
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
        client_order_id: str = order_info.get("cid", "")
        trading_pair = await self.trading_pair_for_market(market_id=order_info["marketId"])

        status_update = OrderUpdate(
            trading_pair=trading_pair,
            update_timestamp=int(order_info["updatedAt"]) * 1e-3,
            new_state=CONSTANTS.ORDER_STATE_MAP[order_info["state"]],
            client_order_id=client_order_id,
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

        async with self.throttler.execute_task(limit_id=CONSTANTS.SIMULATE_TRANSACTION_LIMIT_ID):
            try:
                await self._configure_gas_fee_for_transaction(transaction=transaction)
            except RuntimeError as simulation_ex:
                if CONSTANTS.ACCOUNT_SEQUENCE_MISMATCH_ERROR in str(simulation_ex):
                    await self.initialize_trading_account()
                raise

        transaction.with_memo("")
        transaction.with_timeout_height(await self.timeout_height())

        signed_transaction_data = self._sign_and_encode(transaction=transaction)

        async with self.throttler.execute_task(limit_id=CONSTANTS.SEND_TRANSACTION):
            result = await self.query_executor.send_tx_sync_mode(tx_byte=signed_transaction_data)

        if CONSTANTS.ACCOUNT_SEQUENCE_MISMATCH_ERROR in result.get("rawLog", ""):
            await self.initialize_trading_account()

        return result

    def _chain_stream_exception_handler(self, exception: RpcError):
        self.logger().warning(f"Error while listening to chain stream ({exception})")

    def _chain_stream_closed_handler(self):
        self.logger().debug("Reconnecting stream for chain stream")

    async def _listen_to_chain_updates(
            self,
            spot_markets: List[InjectiveSpotMarket],
            derivative_markets: List[InjectiveDerivativeMarket],
            subaccount_ids: List[str],
    ):
        composer = await self.composer()

        async def _chain_stream_event_handler(event: Dict[str, Any]):
            try:
                await self._process_chain_stream_update(
                    chain_stream_update=event, derivative_markets=derivative_markets,
                )
            except asyncio.CancelledError:
                raise
            except Exception as ex:
                self.logger().warning(f"Invalid chain stream event format ({ex})\n{event}")

        while True:
            # Running in a cycle to reconnect to the stream after connection errors
            await self._listen_chain_stream_updates(
                spot_markets=spot_markets,
                derivative_markets=derivative_markets,
                subaccount_ids=subaccount_ids,
                composer=composer,
                callback=_chain_stream_event_handler,
                on_end_callback=self._chain_stream_closed_handler,
                on_status_callback=self._chain_stream_exception_handler,
            )

    def _transaction_stream_exception_handler(self, exception: RpcError):
        self.logger().warning(f"Error while listening to transaction stream ({exception})")

    def _transaction_stream_closed_handler(self):
        self.logger().debug("Reconnecting stream for transaction stream")

    async def _listen_to_chain_transactions(self):
        while True:
            # Running in a cycle to reconnect to the stream after connection errors
            await self._listen_transactions_updates(
                callback=self._process_transaction_update,
                on_end_callback=self._transaction_stream_closed_handler,
                on_status_callback=self._transaction_stream_exception_handler,
            )

    async def _process_chain_stream_update(
        self, chain_stream_update: Dict[str, Any], derivative_markets: List[InjectiveDerivativeMarket],
    ):
        block_height = int(chain_stream_update["blockHeight"])
        block_timestamp = int(chain_stream_update["blockTime"]) * 1e-3
        tasks = []

        tasks.append(
            asyncio.create_task(
                self._process_subaccount_balance_update(
                    balance_events=chain_stream_update.get("subaccountDeposits", []),
                    block_height=block_height,
                    block_timestamp=block_timestamp,
                )
            )
        )
        tasks.append(
            asyncio.create_task(
                self._process_chain_spot_order_book_update(
                    order_book_updates=chain_stream_update.get("spotOrderbookUpdates", []),
                    block_height=block_height,
                    block_timestamp=block_timestamp,
                )
            )
        )
        tasks.append(
            asyncio.create_task(
                self._process_chain_spot_trade_update(
                    trade_updates=chain_stream_update.get("spotTrades", []),
                    block_height=block_height,
                    block_timestamp=block_timestamp,
                )
            )
        )
        tasks.append(
            asyncio.create_task(
                self._process_chain_derivative_order_book_update(
                    order_book_updates=chain_stream_update.get("derivativeOrderbookUpdates", []),
                    block_height=block_height,
                    block_timestamp=block_timestamp,
                )
            )
        )
        tasks.append(
            asyncio.create_task(
                self._process_chain_derivative_trade_update(
                    trade_updates=chain_stream_update.get("derivativeTrades", []),
                    block_height=block_height,
                    block_timestamp=block_timestamp,
                )
            )
        )
        tasks.append(
            asyncio.create_task(
                self._process_chain_order_update(
                    order_updates=chain_stream_update.get("spotOrders", []),
                    block_height = block_height,
                    block_timestamp = block_timestamp,
                )
            )
        )
        tasks.append(
            asyncio.create_task(
                self._process_chain_order_update(
                    order_updates=chain_stream_update.get("derivativeOrders", []),
                    block_height=block_height,
                    block_timestamp=block_timestamp,
                )
            )
        )
        tasks.append(
            asyncio.create_task(
                self._process_chain_position_updates(
                    position_updates=chain_stream_update.get("positions", []),
                    block_height=block_height,
                    block_timestamp=block_timestamp,
                )
            )
        )
        tasks.append(
            asyncio.create_task(
                self._process_oracle_price_updates(
                    oracle_price_updates=chain_stream_update.get("oraclePrices", []),
                    block_height=block_height,
                    block_timestamp=block_timestamp,
                    derivative_markets=derivative_markets,
                )
            )
        )

        await safe_gather(*tasks)

    async def _process_chain_spot_order_book_update(
            self,
            order_book_updates: List[Dict[str, Any]],
            block_height: int,
            block_timestamp: float
    ):
        for order_book_update in order_book_updates:
            try:
                market_id = order_book_update["orderbook"]["marketId"]
                market_info = await self.spot_market_info_for_id(market_id=market_id)
                await self._process_chain_order_book_update(
                    order_book_update=order_book_update,
                    block_height=block_height,
                    block_timestamp=block_timestamp,
                    market=market_info,
                )
            except asyncio.CancelledError:
                raise
            except Exception as ex:
                self.logger().warning(f"Error processing spot orderbook event ({ex})")
                self.logger().debug(f"Error processing the spot orderbook event {order_book_update}")

    async def _process_chain_derivative_order_book_update(
            self,
            order_book_updates: List[Dict[str, Any]],
            block_height: int,
            block_timestamp: float
    ):
        for order_book_update in order_book_updates:
            try:
                market_id = order_book_update["orderbook"]["marketId"]
                market_info = await self.derivative_market_info_for_id(market_id=market_id)
                await self._process_chain_order_book_update(
                    order_book_update=order_book_update,
                    block_height=block_height,
                    block_timestamp=block_timestamp,
                    market=market_info,
                )
            except asyncio.CancelledError:
                raise
            except Exception as ex:
                self.logger().warning(f"Error processing derivative orderbook event ({ex})")
                self.logger().debug(f"Error processing the derivative orderbook event {order_book_update}")

    async def _process_chain_order_book_update(
        self,
        order_book_update: Dict[str, Any],
        block_height: int,
        block_timestamp: float,
        market: Union[InjectiveSpotMarket, InjectiveDerivativeMarket],
    ):
        trading_pair = await self.trading_pair_for_market(market_id=market.market_id)
        buy_levels = sorted(
            order_book_update["orderbook"].get("buyLevels", []),
            key=lambda bid: int(bid["p"]),
            reverse=True
        )
        bids = [(market.price_from_special_chain_format(chain_price=Decimal(bid["p"])),
                 market.quantity_from_special_chain_format(chain_quantity=Decimal(bid["q"])))
                for bid in buy_levels]
        asks = [(market.price_from_special_chain_format(chain_price=Decimal(ask["p"])),
                 market.quantity_from_special_chain_format(chain_quantity=Decimal(ask["q"])))
                for ask in order_book_update["orderbook"].get("sellLevels", [])]

        order_book_message_content = {
            "trading_pair": trading_pair,
            "update_id": int(order_book_update["seq"]),
            "bids": bids,
            "asks": asks,
        }
        diff_message = OrderBookMessage(
            message_type=OrderBookMessageType.DIFF,
            content=order_book_message_content,
            timestamp=block_timestamp,
        )
        self.publisher.trigger_event(
            event_tag=OrderBookDataSourceEvent.DIFF_EVENT, message=diff_message
        )

    async def _process_chain_spot_trade_update(
        self,
        trade_updates: List[Dict[str, Any]],
        block_height: int,
        block_timestamp: float
    ):
        for trade_update in trade_updates:
            try:
                market_id = trade_update["marketId"]
                market_info = await self.spot_market_info_for_id(market_id=market_id)

                trading_pair = await self.trading_pair_for_market(market_id=market_id)
                timestamp = self._time()
                trade_type = TradeType.BUY if trade_update.get("isBuy", False) else TradeType.SELL
                amount = market_info.quantity_from_special_chain_format(
                    chain_quantity=Decimal(str(trade_update["quantity"]))
                )
                price = market_info.price_from_special_chain_format(chain_price=Decimal(str(trade_update["price"])))
                order_hash = "0x" + base64.b64decode(trade_update["orderHash"]).hex()
                client_order_id = trade_update.get("cid", "")
                trade_id = trade_update["tradeId"]
                message_content = {
                    "trade_id": trade_id,
                    "trading_pair": trading_pair,
                    "trade_type": float(trade_type.value),
                    "amount": amount,
                    "price": price,
                }
                trade_message = OrderBookMessage(
                    message_type=OrderBookMessageType.TRADE,
                    content=message_content,
                    timestamp=timestamp,
                )
                self.publisher.trigger_event(
                    event_tag=OrderBookDataSourceEvent.TRADE_EVENT, message=trade_message
                )

                fee_amount = market_info.quote_token.value_from_special_chain_format(chain_value=Decimal(trade_update["fee"]))
                fee = TradeFeeBase.new_spot_fee(
                    fee_schema=TradeFeeSchema(),
                    trade_type=trade_type,
                    percent_token=market_info.quote_token.symbol,
                    flat_fees=[TokenAmount(amount=fee_amount, token=market_info.quote_token.symbol)]
                )

                trade_update = TradeUpdate(
                    trade_id=trade_id,
                    client_order_id=client_order_id,
                    exchange_order_id=order_hash,
                    trading_pair=trading_pair,
                    fill_timestamp=timestamp,
                    fill_price=price,
                    fill_base_amount=amount,
                    fill_quote_amount=amount * price,
                    fee=fee,
                )
                self.publisher.trigger_event(event_tag=MarketEvent.TradeUpdate, message=trade_update)
            except asyncio.CancelledError:
                raise
            except Exception as ex:
                self.logger().warning(f"Error processing spot trade event ({ex})")
                self.logger().debug(f"Error processing the spot trade event {trade_update}")

    async def _process_chain_derivative_trade_update(
        self,
        trade_updates: List[Dict[str, Any]],
        block_height: int,
        block_timestamp: float
    ):
        for trade_update in trade_updates:
            try:
                market_id = trade_update["marketId"]
                market_info = await self.derivative_market_info_for_id(market_id=market_id)

                trading_pair = await self.trading_pair_for_market(market_id=market_id)
                trade_type = TradeType.BUY if trade_update.get("isBuy", False) else TradeType.SELL
                amount = market_info.quantity_from_special_chain_format(
                    chain_quantity=Decimal(str(trade_update["positionDelta"]["executionQuantity"]))
                )
                price = market_info.price_from_special_chain_format(
                    chain_price=Decimal(str(trade_update["positionDelta"]["executionPrice"])))
                order_hash = "0x" + base64.b64decode(trade_update["orderHash"]).hex()
                client_order_id = trade_update.get("cid", "")
                trade_id = trade_update["tradeId"]

                message_content = {
                    "trade_id": trade_id,
                    "trading_pair": trading_pair,
                    "trade_type": float(trade_type.value),
                    "amount": amount,
                    "price": price,
                }
                trade_message = OrderBookMessage(
                    message_type=OrderBookMessageType.TRADE,
                    content=message_content,
                    timestamp=block_timestamp,
                )
                self.publisher.trigger_event(
                    event_tag=OrderBookDataSourceEvent.TRADE_EVENT, message=trade_message
                )

                fee_amount = market_info.quote_token.value_from_special_chain_format(chain_value=Decimal(trade_update["fee"]))
                fee = TradeFeeBase.new_perpetual_fee(
                    fee_schema=TradeFeeSchema(),
                    position_action=PositionAction.OPEN,  # will be changed by the exchange class
                    percent_token=market_info.quote_token.symbol,
                    flat_fees=[TokenAmount(amount=fee_amount, token=market_info.quote_token.symbol)]
                )

                trade_update = TradeUpdate(
                    trade_id=trade_id,
                    client_order_id=client_order_id,
                    exchange_order_id=order_hash,
                    trading_pair=trading_pair,
                    fill_timestamp=block_timestamp,
                    fill_price=price,
                    fill_base_amount=amount,
                    fill_quote_amount=amount * price,
                    fee=fee,
                )
                self.publisher.trigger_event(event_tag=MarketEvent.TradeUpdate, message=trade_update)
            except asyncio.CancelledError:
                raise
            except Exception as ex:
                self.logger().warning(f"Error processing derivative trade event ({ex})")
                self.logger().debug(f"Error processing the derivative trade event {trade_update}")

    async def _process_chain_order_update(
            self,
            order_updates: List[Dict[str, Any]],
            block_height: int,
            block_timestamp: float,
    ):
        for order_update in order_updates:
            try:
                exchange_order_id = "0x" + base64.b64decode(order_update["orderHash"]).hex()
                client_order_id = order_update.get("cid", "")
                trading_pair = await self.trading_pair_for_market(market_id=order_update["order"]["marketId"])

                status_update = OrderUpdate(
                    trading_pair=trading_pair,
                    update_timestamp=block_timestamp,
                    new_state=CONSTANTS.STREAM_ORDER_STATE_MAP[order_update["status"]],
                    client_order_id=client_order_id,
                    exchange_order_id=exchange_order_id,
                )

                self.publisher.trigger_event(event_tag=MarketEvent.OrderUpdate, message=status_update)
            except asyncio.CancelledError:
                raise
            except Exception as ex:
                self.logger().warning(f"Error processing order event ({ex})")
                self.logger().debug(f"Error processing the order event {order_update}")

    async def _process_chain_position_updates(
            self,
            position_updates: List[Dict[str, Any]],
            block_height: int,
            block_timestamp: float,
    ):
        for event in position_updates:
            try:
                market_id = event["marketId"]
                market = await self.derivative_market_info_for_id(market_id=market_id)
                trading_pair = await self.trading_pair_for_market(market_id=market_id)

                position_side = PositionSide.LONG if event["isLong"] else PositionSide.SHORT
                amount_sign = Decimal(-1) if position_side == PositionSide.SHORT else Decimal(1)
                entry_price = (market.price_from_special_chain_format(chain_price=Decimal(event["entryPrice"])))
                amount = (market.quantity_from_special_chain_format(chain_quantity=Decimal(event["quantity"])))
                margin = (market.price_from_special_chain_format(chain_price=Decimal(event["margin"])))
                oracle_price = await self._oracle_price(market_id=market_id)
                leverage = (amount * entry_price) / margin
                unrealized_pnl = (oracle_price - entry_price) * amount * amount_sign

                parsed_event = PositionUpdateEvent(
                    timestamp=block_timestamp,
                    trading_pair=trading_pair,
                    position_side=position_side,
                    unrealized_pnl=unrealized_pnl,
                    entry_price=entry_price,
                    amount=amount * amount_sign,
                    leverage=leverage,
                )

                self.publisher.trigger_event(event_tag=AccountEvent.PositionUpdate, message=parsed_event)
            except asyncio.CancelledError:
                raise
            except Exception as ex:
                self.logger().warning(f"Error processing position event ({ex})")
                self.logger().debug(f"Error processing the position event {event}")

    async def _process_oracle_price_updates(
            self,
            oracle_price_updates: List[Dict[str, Any]],
            block_height: int,
            block_timestamp: float,
            derivative_markets: List[InjectiveDerivativeMarket],
    ):
        updated_symbols = {update["symbol"] for update in oracle_price_updates}
        for market in derivative_markets:
            try:
                if market.oracle_base() in updated_symbols or market.oracle_quote() in updated_symbols:
                    market_id = market.market_id
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
            except asyncio.CancelledError:
                raise
            except Exception as ex:
                self.logger().warning(
                    f"Error processing oracle price update for market {market.trading_pair()} ({ex})"
                )

    async def _process_position_update(self, position_event: Dict[str, Any]):
        parsed_event = await self._parse_position_update_event(event=position_event)
        self.publisher.trigger_event(event_tag=AccountEvent.PositionUpdate, message=parsed_event)

    async def _process_subaccount_balance_update(
            self,
            balance_events: List[Dict[str, Any]],
            block_height: int,
            block_timestamp: float
    ):
        if len(balance_events) > 0 and self._uses_default_portfolio_subaccount():
            token_balances = await self.all_account_balances()

        for balance_event in balance_events:
            try:
                for deposit in balance_event["deposits"]:
                    updated_token = await self.token(denom=deposit["denom"])
                    if updated_token is not None:
                        if self._uses_default_portfolio_subaccount():
                            total_balance = token_balances[updated_token.unique_symbol]["total_balance"]
                            available_balance = token_balances[updated_token.unique_symbol]["available_balance"]
                        else:
                            updated_total = deposit["deposit"].get("totalBalance")
                            total_balance = (updated_token.value_from_special_chain_format(chain_value=Decimal(updated_total))
                                             if updated_total is not None
                                             else None)
                            updated_available = deposit["deposit"].get("availableBalance")
                            available_balance = (updated_token.value_from_special_chain_format(chain_value=Decimal(updated_available))
                                                 if updated_available is not None
                                                 else None)

                        balance_msg = BalanceUpdateEvent(
                            timestamp=self._time(),
                            asset_name=updated_token.unique_symbol,
                            total_balance=total_balance,
                            available_balance=available_balance,
                        )
                        self.publisher.trigger_event(event_tag=AccountEvent.BalanceEvent, message=balance_msg)
            except asyncio.CancelledError:
                raise
            except Exception as ex:
                self.logger().warning(f"Error processing subaccount balance event ({ex})")
                self.logger().debug(f"Error processing the subaccount balance event {balance_event}")

    async def _process_transaction_update(self, transaction_event: Dict[str, Any]):
        self.publisher.trigger_event(event_tag=InjectiveEvent.ChainTransactionEvent, message=transaction_event)

    async def _create_spot_order_definition(self, order: GatewayInFlightOrder):
        order_type = "BUY" if order.trade_type == TradeType.BUY else "SELL"
        if order.order_type == OrderType.LIMIT_MAKER:
            order_type = order_type + "_PO"
        composer = await self.composer()
        market_id = await self.market_id_for_spot_trading_pair(order.trading_pair)
        definition = composer.spot_order(
            market_id=market_id,
            subaccount_id=self.portfolio_account_subaccount_id,
            fee_recipient=self.portfolio_account_injective_address,
            price=order.price,
            quantity=order.amount,
            order_type=order_type,
            cid=order.client_order_id,
        )
        return definition

    async def _create_derivative_order_definition(self, order: GatewayPerpetualInFlightOrder):
        order_type = "BUY" if order.trade_type == TradeType.BUY else "SELL"
        if order.order_type == OrderType.LIMIT_MAKER:
            order_type = order_type + "_PO"
        composer = await self.composer()
        market_id = await self.market_id_for_derivative_trading_pair(order.trading_pair)
        definition = composer.derivative_order(
            market_id=market_id,
            subaccount_id=self.portfolio_account_subaccount_id,
            fee_recipient=self.portfolio_account_injective_address,
            price=order.price,
            quantity=order.amount,
            margin=composer.calculate_margin(
                quantity=order.amount,
                price=order.price,
                leverage=Decimal(str(order.leverage)),
                is_reduce_only=order.position == PositionAction.CLOSE,
            ),
            order_type=order_type,
            cid=order.client_order_id,
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
                min_notional = market.min_notional()
                trading_rule = TradingRule(
                    trading_pair=market.trading_pair(),
                    min_order_size=min_quantity_tick_size,
                    min_price_increment=min_price_tick_size,
                    min_base_amount_increment=min_quantity_tick_size,
                    min_quote_amount_increment=min_price_tick_size,
                    min_notional_size=min_notional
                )
                trading_rules.append(trading_rule)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().exception(f"Error parsing the trading pair rule: {market.native_market}. Skipping...")

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

    async def _get_markets_and_tokens(
        self
    ) -> Tuple[
        Dict[str, InjectiveToken],
        Mapping[str, str],
        Dict[str, InjectiveSpotMarket],
        Mapping[str, str],
        Dict[str, InjectiveDerivativeMarket],
        Mapping[str, str]
    ]:
        tokens_map = {}
        token_symbol_and_denom_map = bidict()
        spot_markets_map = {}
        derivative_markets_map = {}
        spot_market_id_to_trading_pair = bidict()
        derivative_market_id_to_trading_pair = bidict()

        async with self.throttler.execute_task(limit_id=CONSTANTS.SPOT_MARKETS_LIMIT_ID):
            async with self.throttler.execute_task(limit_id=CONSTANTS.DERIVATIVE_MARKETS_LIMIT_ID):
                spot_markets: Dict[str, SpotMarket] = await self.query_executor.spot_markets()
                derivative_markets: Dict[str, DerivativeMarket] = await self.query_executor.derivative_markets()
                tokens: Dict[str, Token] = await self.query_executor.tokens()

        for unique_symbol, injective_native_token in tokens.items():
            token = InjectiveToken(
                unique_symbol=unique_symbol,
                native_token=injective_native_token
            )
            tokens_map[token.denom] = token
            token_symbol_and_denom_map[unique_symbol] = token.denom

        for market in spot_markets.values():
            try:
                parsed_market = InjectiveSpotMarket(
                    market_id=market.id,
                    base_token=tokens_map[market.base_token.denom],
                    quote_token=tokens_map[market.quote_token.denom],
                    native_market=market
                )

                spot_market_id_to_trading_pair[parsed_market.market_id] = parsed_market.trading_pair()
                spot_markets_map[parsed_market.market_id] = parsed_market
            except KeyError:
                self.logger().debug(f"The spot market {market.id} will be excluded because it could not "
                                    f"be parsed ({market})")
                continue

        for market in derivative_markets.values():
            try:
                parsed_market = InjectiveDerivativeMarket(
                    market_id=market.id,
                    quote_token=tokens_map[market.quote_token.denom],
                    native_market=market,
                )

                if parsed_market.trading_pair() in derivative_market_id_to_trading_pair.inverse:
                    self.logger().debug(
                        f"The derivative market {market.id} will be excluded because there is other"
                        f" market with trading pair {parsed_market.trading_pair()} ({market})")
                    continue
                derivative_market_id_to_trading_pair[parsed_market.market_id] = parsed_market.trading_pair()
                derivative_markets_map[parsed_market.market_id] = parsed_market
            except KeyError:
                self.logger().debug(f"The derivative market {market.id} will be excluded because it could"
                                    f" not be parsed ({market})")
                continue

        return (
            tokens_map,
            token_symbol_and_denom_map,
            spot_markets_map,
            spot_market_id_to_trading_pair,
            derivative_markets_map,
            derivative_market_id_to_trading_pair
        )

    def _time(self):
        return time.time()

    async def _sleep(self, delay: float):
        """
        Method created to enable tests to prevent processes from sleeping
        """
        await asyncio.sleep(delay)
