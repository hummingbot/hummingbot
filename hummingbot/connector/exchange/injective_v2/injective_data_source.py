import asyncio
import base64
import logging
import time
from abc import ABC, abstractmethod
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Mapping, Optional

from bidict import bidict
from google.protobuf import any_pb2
from pyinjective import Transaction
from pyinjective.async_client import AsyncClient
from pyinjective.composer import Composer
from pyinjective.constant import Network
from pyinjective.orderhash import OrderHashManager
from pyinjective.wallet import Address, PrivateKey

from hummingbot.connector.exchange.injective_v2 import injective_constants as CONSTANTS
from hummingbot.connector.exchange.injective_v2.injective_market import InjectiveSpotMarket, InjectiveToken
from hummingbot.connector.exchange.injective_v2.injective_query_executor import PythonSDKInjectiveQueryExecutor
from hummingbot.connector.gateway.common_types import CancelOrderResult, PlaceOrderResult
from hummingbot.connector.gateway.gateway_in_flight_order import GatewayInFlightOrder
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.connector.utils import combine_to_hb_trading_pair
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.api_throttler.async_throttler_base import AsyncThrottlerBase
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import OrderState, OrderUpdate, TradeUpdate
from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType
from hummingbot.core.data_type.trade_fee import TokenAmount, TradeFeeBase, TradeFeeSchema
from hummingbot.core.event.event_listener import EventListener
from hummingbot.core.event.events import AccountEvent, BalanceUpdateEvent, MarketEvent, OrderBookDataSourceEvent
from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.core.pubsub import PubSub
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

    @classmethod
    def for_grantee(
            cls,
            private_key: str,
            subaccount_index: int,
            granter_address: str,
            granter_subaccount_index: int,
            domain: Optional[str] = CONSTANTS.DEFAULT_DOMAIN):
        return InjectiveGranteeDataSource(
            private_key=private_key,
            subaccount_index=subaccount_index,
            granter_address=granter_address,
            granter_subaccount_index=granter_subaccount_index,
            domain=domain,
        )

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
    async def transaction_result_data(self, transaction_hash: str) -> str:
        raise NotImplementedError

    @abstractmethod
    def real_tokens_trading_pair(self, unique_trading_pair: str) -> str:
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

                for market_id in market_ids:
                    self.add_listening_task(asyncio.create_task(
                        self._listen_to_subaccount_order_updates(market_id=market_id))
                    )
                await self._initialize_timeout_height()

    async def stop(self):
        for task in self.events_listening_tasks():
            task.cancel()

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
            composer = self.composer
            order_definitions = []
            results = []

            for order in orders_to_create:
                order_definition = await self._create_order_definition(order=order)
                order_definitions.append(order_definition)

            order_hashes = self._calculate_order_hashes(orders=order_definitions)

            message = composer.MsgBatchUpdateOrders(
                sender=self.portfolio_account_injective_address,
                spot_orders_to_create=order_definitions,
            )
            delegated_message = composer.MsgExec(
                grantee=self.trading_account_injective_address,
                msgs=[message]
            )

            try:
                result = await self._send_in_transaction(message=delegated_message)
                if result["rawLog"] != "[]" or result["txhash"] in [None, ""]:
                    raise ValueError(f"Error sending the order creation transaction ({result['rawLog']})")
                else:
                    transaction_hash = result["txhash"]
                    results = [
                        PlaceOrderResult(
                            update_timestamp=self._time(),
                            client_order_id=order.client_order_id,
                            exchange_order_id=order_hash,
                            trading_pair=order.trading_pair,
                            misc_updates={
                                "creation_transaction_hash": transaction_hash,
                            },
                        ) for order, order_hash in zip(orders_to_create, order_hashes)
                    ]
            except asyncio.CancelledError:
                raise
            except Exception as ex:
                results = [
                    PlaceOrderResult(
                        update_timestamp=self._time(),
                        client_order_id=order.client_order_id,
                        exchange_order_id=order_hash,
                        trading_pair=order.trading_pair,
                        exception=ex,
                    ) for order, order_hash in zip(orders_to_create, order_hashes)
                ]

        return results

    async def cancel_orders(self, orders_to_cancel: List[GatewayInFlightOrder]) -> List[CancelOrderResult]:
        composer = self.composer
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
                market_id = await self.market_id_for_trading_pair(trading_pair=order.trading_pair)
                order_data = composer.OrderData(
                    market_id=market_id,
                    subaccount_id=self.portfolio_account_subaccount_id,
                    order_hash=order.exchange_order_id,
                )
                orders_data.append(order_data)
                orders_with_hash.append(order)

        message = composer.MsgBatchUpdateOrders(
            sender=self.portfolio_account_injective_address,
            spot_orders_to_cancel=orders_data,
        )
        delegated_message = composer.MsgExec(
            grantee=self.trading_account_injective_address,
            msgs=[message]
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
    async def _create_order_definition(self, order: GatewayInFlightOrder):
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
                pass
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
        transaction.with_memo('')
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

    def _time(self):
        return time.time()

    async def _sleep(self, delay: float):
        """
        Method created to enable tests to prevent processes from sleeping
        """
        await asyncio.sleep(delay)


class InjectiveGranteeDataSource(InjectiveDataSource):
    _logger: Optional[HummingbotLogger] = None

    def __init__(
            self,
            private_key: str,
            subaccount_index: int,
            granter_address: str,
            granter_subaccount_index: int,
            domain: Optional[str] = CONSTANTS.DEFAULT_DOMAIN):
        self._network = Network.testnet() if domain == CONSTANTS.TESTNET_DOMAIN else Network.mainnet()
        self._client = AsyncClient(network=self._network, insecure=False)
        self._composer = Composer(network=self._network.string())
        self._query_executor = PythonSDKInjectiveQueryExecutor(sdk_client=self._client)

        self._private_key = None
        self._public_key = None
        self._grantee_address = ""
        self._grantee_subaccount_index = subaccount_index
        self._granter_subaccount_id = ""
        if private_key:
            self._private_key = PrivateKey.from_hex(private_key)
            self._public_key = self._private_key.to_public_key()
            self._grantee_address = self._public_key.to_address()
            self._grantee_subaccount_id = self._grantee_address.get_subaccount_id(index=subaccount_index)

        self._granter_address = None
        self._granter_subaccount_id = ""
        self._granter_subaccount_index = granter_subaccount_index
        if granter_address:
            self._granter_address = Address.from_acc_bech32(granter_address)
            self._granter_subaccount_id = self._granter_address.get_subaccount_id(index=granter_subaccount_index)

        self._order_hash_manager: Optional[OrderHashManager] = None
        self._publisher = PubSub()
        self._last_received_message_time = 0
        self._order_creation_lock = asyncio.Lock()
        # We create a throttler instance here just to have a fully valid instance from the first moment.
        # The connector using this data source should replace the throttler with the one used by the connector.
        self._throttler = AsyncThrottler(rate_limits=CONSTANTS.RATE_LIMITS)

        self._is_timeout_height_initialized = False
        self._is_trading_account_initialized = False
        self._markets_initialization_lock = asyncio.Lock()
        self._market_info_map: Optional[Dict[str, InjectiveSpotMarket]] = None
        self._market_and_trading_pair_map: Optional[Mapping[str, str]] = None
        self._tokens_map: Optional[Dict[str, InjectiveToken]] = None
        self._token_symbol_symbol_and_denom_map: Optional[Mapping[str, str]] = None

        self._events_listening_tasks: List[asyncio.Task] = []

    @property
    def publisher(self):
        return self._publisher

    @property
    def query_executor(self):
        return self._query_executor

    @property
    def composer(self) -> Composer:
        return self._composer

    @property
    def order_creation_lock(self) -> asyncio.Lock:
        return self._order_creation_lock

    @property
    def throttler(self):
        return self._throttler

    @property
    def portfolio_account_injective_address(self) -> str:
        return self._granter_address.to_acc_bech32()

    @property
    def portfolio_account_subaccount_id(self) -> str:
        return self._granter_subaccount_id

    @property
    def trading_account_injective_address(self) -> str:
        return self._grantee_address.to_acc_bech32()

    @property
    def injective_chain_id(self) -> str:
        return self._network.chain_id

    @property
    def fee_denom(self) -> str:
        return self._network.fee_denom

    def events_listening_tasks(self) -> List[asyncio.Task]:
        return self._events_listening_tasks.copy()

    def add_listening_task(self, task: asyncio.Task):
        self._events_listening_tasks.append(task)

    async def market_and_trading_pair_map(self):
        if self._market_and_trading_pair_map is None:
            async with self._markets_initialization_lock:
                if self._market_and_trading_pair_map is None:
                    await self.update_markets()
        return self._market_and_trading_pair_map.copy()

    async def market_info_for_id(self, market_id: str):
        if self._market_info_map is None:
            async with self._markets_initialization_lock:
                if self._market_info_map is None:
                    await self.update_markets()

        return self._market_info_map[market_id]

    async def trading_pair_for_market(self, market_id: str):
        if self._market_and_trading_pair_map is None:
            async with self._markets_initialization_lock:
                if self._market_and_trading_pair_map is None:
                    await self.update_markets()

        return self._market_and_trading_pair_map[market_id]

    async def market_id_for_trading_pair(self, trading_pair: str) -> str:
        if self._market_and_trading_pair_map is None:
            async with self._markets_initialization_lock:
                if self._market_and_trading_pair_map is None:
                    await self.update_markets()

        return self._market_and_trading_pair_map.inverse[trading_pair]

    async def all_markets(self):
        if self._market_info_map is None:
            async with self._markets_initialization_lock:
                if self._market_info_map is None:
                    await self.update_markets()

        return list(self._market_info_map.values())

    async def token(self, denom: str) -> InjectiveToken:
        if self._tokens_map is None:
            async with self._markets_initialization_lock:
                if self._tokens_map is None:
                    await self.update_markets()

        return self._tokens_map.get(denom)

    def configure_throttler(self, throttler: AsyncThrottlerBase):
        self._throttler = throttler

    async def trading_account_sequence(self) -> int:
        if not self._is_trading_account_initialized:
            await self.initialize_trading_account()
        return self._client.get_sequence()

    async def trading_account_number(self) -> int:
        if not self._is_trading_account_initialized:
            await self.initialize_trading_account()
        return self._client.get_number()

    async def stop(self):
        await super().stop()
        self._events_listening_tasks = []

    async def initialize_trading_account(self):
        await self._client.get_account(address=self.trading_account_injective_address)
        self._is_trading_account_initialized = True

    def order_hash_manager(self) -> OrderHashManager:
        if self._order_hash_manager is None:
            self._order_hash_manager = OrderHashManager(
                address=self._granter_address,
                network=self._network,
                subaccount_indexes=[self._granter_subaccount_index]
            )
        return self._order_hash_manager

    async def update_markets(self):
        self._tokens_map = {}
        self._token_symbol_symbol_and_denom_map = bidict()
        markets = await self._query_executor.spot_markets(status="active")
        markets_map = {}
        market_id_to_trading_pair = bidict()

        for market_info in markets:
            try:
                ticker_base, ticker_quote = market_info["ticker"].split("/")
                base_token = self._token_from_market_info(
                    denom=market_info["baseDenom"],
                    token_meta=market_info["baseTokenMeta"],
                    candidate_symbol=ticker_base,
                )
                quote_token = self._token_from_market_info(
                    denom=market_info["quoteDenom"],
                    token_meta=market_info["quoteTokenMeta"],
                    candidate_symbol=ticker_quote,
                )
                market = InjectiveSpotMarket(
                    market_id=market_info["marketId"],
                    base_token=base_token,
                    quote_token=quote_token,
                    market_info=market_info
                )
                market_id_to_trading_pair[market.market_id] = market.trading_pair()
                markets_map[market.market_id] = market
            except KeyError:
                self.logger().debug(f"The market {market_info['marketId']} will be excluded because it could not be "
                                    f"parsed ({market_info})")
                continue

        self._market_info_map = markets_map
        self._market_and_trading_pair_map = market_id_to_trading_pair

    async def transaction_result_data(self, transaction_hash: str) -> str:
        async with self.throttler.execute_task(limit_id=CONSTANTS.GET_TRANSACTION_LIMIT_ID):
            transaction_info = await self.query_executor.get_tx_by_hash(tx_hash=transaction_hash)

        return str(base64.b64decode(transaction_info["data"]["logs"]))

    async def timeout_height(self) -> int:
        if not self._is_timeout_height_initialized:
            await self._initialize_timeout_height()
        return self._client.timeout_height

    def real_tokens_trading_pair(self, unique_trading_pair: str) -> str:
        resulting_trading_pair = unique_trading_pair
        if (self._market_and_trading_pair_map is not None
                and self._market_info_map is not None):
            market_id = self._market_and_trading_pair_map.inverse.get(unique_trading_pair)
            market = self._market_info_map.get(market_id)
            if market is not None:
                resulting_trading_pair = combine_to_hb_trading_pair(
                    base=market.base_token.symbol,
                    quote=market.quote_token.symbol,
                )

        return resulting_trading_pair

    async def _initialize_timeout_height(self):
        await self._client.sync_timeout_height()
        self._is_timeout_height_initialized = True

    def _reset_order_hash_manager(self):
        self._order_hash_manager = None

    def _sign_and_encode(self, transaction: Transaction) -> bytes:
        sign_doc = transaction.get_sign_doc(self._public_key)
        sig = self._private_key.sign(sign_doc.SerializeToString())
        tx_raw_bytes = transaction.get_tx_data(sig, self._public_key)
        return tx_raw_bytes

    def _uses_default_portfolio_subaccount(self) -> bool:
        return self._granter_subaccount_index == CONSTANTS.DEFAULT_SUBACCOUNT_INDEX

    def _token_from_market_info(self, denom: str, token_meta: Dict[str, Any], candidate_symbol: str) -> InjectiveToken:
        token = self._tokens_map.get(denom)
        if token is None:
            unique_symbol = token_meta["symbol"]
            if unique_symbol in self._token_symbol_symbol_and_denom_map:
                if candidate_symbol not in self._token_symbol_symbol_and_denom_map:
                    unique_symbol = candidate_symbol
                else:
                    unique_symbol = token_meta["name"]
            token = InjectiveToken(
                denom=denom,
                symbol=token_meta["symbol"],
                unique_symbol=unique_symbol,
                name=token_meta["name"],
                decimals=token_meta["decimals"]
            )
            self._tokens_map[denom] = token
            self._token_symbol_symbol_and_denom_map[unique_symbol] = denom

        return token

    async def _last_traded_price(self, market_id: str) -> Decimal:
        async with self.throttler.execute_task(limit_id=CONSTANTS.SPOT_TRADES_LIMIT_ID):
            trades_response = await self.query_executor.get_spot_trades(
                market_ids=[market_id],
                limit=1,
            )

        price = Decimal("nan")
        if len(trades_response["trades"]) > 0:
            market = await self.market_info_for_id(market_id=market_id)
            price = market.price_from_chain_format(chain_price=Decimal(trades_response["trades"][0]["price"]["price"]))

        return price

    async def _create_order_definition(self, order: GatewayInFlightOrder):
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

    def _calculate_order_hashes(self, orders) -> List[str]:
        hash_manager = self.order_hash_manager()
        hash_manager_result = hash_manager.compute_order_hashes(
            spot_orders=orders, derivative_orders=[], subaccount_index=self._grantee_subaccount_index
        )
        return hash_manager_result.spot

    def _order_book_updates_stream(self, market_ids: List[str]):
        stream = self._query_executor.spot_order_book_updates_stream(market_ids=market_ids)
        return stream

    def _public_trades_stream(self, market_ids: List[str]):
        stream = self._query_executor.public_spot_trades_stream(market_ids=market_ids)
        return stream

    def _subaccount_balance_stream(self):
        stream = self._query_executor.subaccount_balance_stream(subaccount_id=self.portfolio_account_subaccount_id)
        return stream

    def _subaccount_orders_stream(self, market_id: str):
        stream = self._query_executor.subaccount_historical_spot_orders_stream(
            market_id=market_id, subaccount_id=self.portfolio_account_subaccount_id
        )
        return stream
