import asyncio
import logging
import os
import time
from abc import ABC, abstractmethod
from decimal import Decimal
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from google.protobuf import any_pb2
from pyinjective import Transaction
from pyinjective.composer import Composer, injective_exchange_tx_pb

from hummingbot.connector.exchange.injective_v2 import injective_constants as CONSTANTS
from hummingbot.connector.exchange.injective_v2.injective_events import InjectiveEvent
from hummingbot.connector.exchange.injective_v2.injective_market import InjectiveToken
from hummingbot.connector.gateway.common_types import CancelOrderResult, PlaceOrderResult
from hummingbot.connector.gateway.gateway_in_flight_order import GatewayInFlightOrder
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.core.api_throttler.async_throttler_base import AsyncThrottlerBase
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import OrderState, OrderUpdate, TradeUpdate
from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType
from hummingbot.core.data_type.trade_fee import TokenAmount, TradeFeeBase, TradeFeeSchema
from hummingbot.core.event.event_listener import EventListener
from hummingbot.core.event.events import AccountEvent, BalanceUpdateEvent, MarketEvent, OrderBookDataSourceEvent
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
    async def market_and_trading_pair_map(self):
        raise NotImplementedError

    @abstractmethod
    async def market_info_for_id(self, market_id: str):
        raise NotImplementedError

    @abstractmethod
    async def trading_pair_for_market(self, market_id: str):
        raise NotImplementedError

    @abstractmethod
    async def market_id_for_trading_pair(self, trading_pair: str) -> str:
        raise NotImplementedError

    @abstractmethod
    async def all_markets(self):
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
    def real_tokens_trading_pair(self, unique_trading_pair: str) -> str:
        raise NotImplementedError

    @abstractmethod
    async def order_updates_for_transaction(
            self, transaction_hash: str, transaction_orders: List[GatewayInFlightOrder]
    ) -> List[OrderUpdate]:
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
                self.add_listening_task(asyncio.create_task(self._listen_to_public_trades(market_ids=market_ids)))
                self.add_listening_task(asyncio.create_task(self._listen_to_order_book_updates(market_ids=market_ids)))
                self.add_listening_task(asyncio.create_task(self._listen_to_account_balance_updates()))
                self.add_listening_task(asyncio.create_task(self._listen_to_chain_transactions()))

                for market_id in market_ids:
                    self.add_listening_task(asyncio.create_task(
                        self._listen_to_subaccount_order_updates(market_id=market_id))
                    )
                await self._initialize_timeout_height()

    async def stop(self):
        for task in self.events_listening_tasks():
            task.cancel()
        cookie_file_path = Path(self._chain_cookie_file_path())
        cookie_file_path.unlink()

    def add_listener(self, event_tag: Enum, listener: EventListener):
        self.publisher.add_listener(event_tag=event_tag, listener=listener)

    def remove_listener(self, event_tag: Enum, listener: EventListener):
        self.publisher.remove_listener(event_tag=event_tag, listener=listener)

    async def all_trading_rules(self) -> List[TradingRule]:
        all_markets = await self.all_markets()
        trading_rules = []

        for market in all_markets:
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

    async def order_book_snapshot(self, market_id: str, trading_pair: str) -> OrderBookMessage:
        async with self.throttler.execute_task(limit_id=CONSTANTS.ORDERBOOK_LIMIT_ID):
            snapshot_data = await self.query_executor.get_spot_orderbook(market_id=market_id)

        market = await self.market_info_for_id(market_id=market_id)
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

    async def create_orders(self, orders_to_create: List[GatewayInFlightOrder]) -> List[PlaceOrderResult]:
        if self.order_creation_lock.locked():
            raise RuntimeError("It is not possible to create new orders because the hash manager is not synchronized")
        async with self.order_creation_lock:
            results = []

            order_creation_message, order_hashes = await self._order_creation_message(
                spot_orders_to_create=orders_to_create)

            try:
                result = await self._send_in_transaction(message=order_creation_message)
                if result["rawLog"] != "[]" or result["txhash"] in [None, ""]:
                    raise ValueError(f"Error sending the order creation transaction ({result['rawLog']})")
                else:
                    transaction_hash = result["txhash"]
                    results = self._place_order_results(
                        orders_to_create=orders_to_create,
                        order_hashes=order_hashes,
                        misc_updates={
                            "creation_transaction_hash": transaction_hash,
                        },
                    )
            except asyncio.CancelledError:
                raise
            except Exception as ex:
                results = self._place_order_results(
                    orders_to_create=orders_to_create,
                    order_hashes=order_hashes,
                    misc_updates={},
                    exception=ex,
                )

        return results

    async def cancel_orders(self, orders_to_cancel: List[GatewayInFlightOrder]) -> List[CancelOrderResult]:
        orders_with_hash = []
        orders_data = []
        results = []

        for order in orders_to_cancel:
            if order.exchange_order_id is None:
                results.append(CancelOrderResult(
                    client_order_id=order.client_order_id,
                    trading_pair=order.trading_pair,
                    not_found=True,
                ))
            else:
                order_data = await self._generate_injective_order_data(order=order)
                orders_data.append(order_data)
                orders_with_hash.append(order)

        delegated_message = self._order_cancel_message(
            spot_orders_to_cancel=orders_data
        )

        try:
            result = await self._send_in_transaction(message=delegated_message)
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

        trade_updates = [await self._parse_trade_entry(trade_info=trade_info) for trade_info in trade_entries]

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

    async def get_trading_fees(self) -> Dict[str, TradeFeeSchema]:
        markets = await self.all_markets()
        fees = {}
        for market in markets:
            trading_pair = await self.trading_pair_for_market(market_id=market.market_id)
            fees[trading_pair] = TradeFeeSchema(
                percent_fee_token=market.quote_token.unique_symbol,
                maker_percent_fee_decimal=market.maker_fee_rate(),
                taker_percent_fee_decimal=market.taker_fee_rate(),
            )

        return fees

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
    def _order_book_updates_stream(self, market_ids: List[str]):
        raise NotImplementedError

    @abstractmethod
    def _public_trades_stream(self, market_ids: List[str]):
        raise NotImplementedError

    @abstractmethod
    def _subaccount_balance_stream(self):
        raise NotImplementedError

    @abstractmethod
    def _subaccount_orders_stream(self, market_id: str):
        raise NotImplementedError

    @abstractmethod
    def _transactions_stream(self):
        raise NotImplementedError

    @abstractmethod
    def _calculate_order_hashes(self, orders: List[GatewayInFlightOrder]) -> List[str]:
        raise NotImplementedError

    @abstractmethod
    def _reset_order_hash_manager(self):
        raise NotImplementedError

    @abstractmethod
    async def _last_traded_price(self, market_id: str) -> Decimal:
        raise NotImplementedError

    @abstractmethod
    async def _order_creation_message(
            self, spot_orders_to_create: List[GatewayInFlightOrder]
    ) -> Tuple[any_pb2.Any, List[str]]:
        raise NotImplementedError

    @abstractmethod
    def _order_cancel_message(self, spot_orders_to_cancel: List[injective_exchange_tx_pb.OrderData]) -> any_pb2.Any:
        raise NotImplementedError

    @abstractmethod
    def _generate_injective_order_data(self, order: GatewayInFlightOrder) -> injective_exchange_tx_pb.OrderData:
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

    async def _parse_trade_entry(self, trade_info: Dict[str, Any]) -> TradeUpdate:
        exchange_order_id: str = trade_info["orderHash"]
        market = await self.market_info_for_id(market_id=trade_info["marketId"])
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

    async def _send_in_transaction(self, message: any_pb2.Any) -> Dict[str, Any]:
        transaction = Transaction()
        transaction.with_messages(message)
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

    async def _listen_to_order_book_updates(self, market_ids: List[str]):
        while True:
            try:
                updates_stream = self._order_book_updates_stream(market_ids=market_ids)
                async for update in updates_stream:
                    try:
                        await self._process_order_book_update(order_book_update=update)
                    except asyncio.CancelledError:
                        raise
                    except Exception as ex:
                        self.logger().warning(f"Invalid orderbook diff event format ({ex})\n{update}")
            except asyncio.CancelledError:
                raise
            except Exception as ex:
                self.logger().error(f"Error while listening to order book updates, reconnecting ... ({ex})")

    async def _listen_to_public_trades(self, market_ids: List[str]):
        while True:
            try:
                public_trades_stream = self._public_trades_stream(market_ids=market_ids)
                async for trade in public_trades_stream:
                    try:
                        await self._process_public_trade_update(trade_update=trade)
                    except asyncio.CancelledError:
                        raise
                    except Exception as ex:
                        self.logger().warning(f"Invalid public trade event format ({ex})\n{trade}")
            except asyncio.CancelledError:
                raise
            except Exception as ex:
                self.logger().error(f"Error while listening to public trades, reconnecting ... ({ex})")

    async def _listen_to_account_balance_updates(self):
        while True:
            try:
                balance_stream = self._subaccount_balance_stream()
                async for balance_event in balance_stream:
                    try:
                        await self._process_subaccount_balance_update(balance_event=balance_event)
                    except asyncio.CancelledError:
                        raise
                    except Exception as ex:
                        self.logger().warning(f"Invalid balance event format ({ex})\n{balance_event}")
            except asyncio.CancelledError:
                raise
            except Exception as ex:
                self.logger().error(f"Error while listening to balance updates, reconnecting ... ({ex})")

    async def _listen_to_subaccount_order_updates(self, market_id: str):
        while True:
            try:
                orders_stream = self._subaccount_orders_stream(market_id=market_id)
                async for order_event in orders_stream:
                    try:
                        await self._process_subaccount_order_update(order_event=order_event)
                    except asyncio.CancelledError:
                        raise
                    except Exception as ex:
                        self.logger().warning(f"Invalid order event format ({ex})\n{order_event}")
            except asyncio.CancelledError:
                raise
            except Exception as ex:
                self.logger().error(f"Error while listening to subaccount orders updates, reconnecting ... ({ex})")

    async def _listen_to_chain_transactions(self):
        while True:
            try:
                transactions_stream = self._transactions_stream()
                async for transaction_event in transactions_stream:
                    try:
                        await self._process_transaction_update(transaction_event=transaction_event)
                    except asyncio.CancelledError:
                        raise
                    except Exception as ex:
                        self.logger().warning(f"Invalid transaction event format ({ex})\n{transaction_event}")
            except asyncio.CancelledError:
                raise
            except Exception as ex:
                self.logger().error(f"Error while listening to transactions stream, reconnecting ... ({ex})")

    async def _process_order_book_update(self, order_book_update: Dict[str, Any]):
        market_id = order_book_update["marketId"]
        market_info = await self.market_info_for_id(market_id=market_id)

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

    async def _process_public_trade_update(self, trade_update: Dict[str, Any]):
        market_id = trade_update["marketId"]
        market_info = await self.market_info_for_id(market_id=market_id)

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

        update = await self._parse_trade_entry(trade_info=trade_update)
        self.publisher.trigger_event(event_tag=MarketEvent.TradeUpdate, message=update)

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
        market_id = await self.market_id_for_trading_pair(order.trading_pair)
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

    def _time(self):
        return time.time()

    async def _sleep(self, delay: float):
        """
        Method created to enable tests to prevent processes from sleeping
        """
        await asyncio.sleep(delay)
