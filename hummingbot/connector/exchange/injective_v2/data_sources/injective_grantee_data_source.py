import asyncio
from typing import Any, Dict, List, Mapping, Optional

from google.protobuf import any_pb2
from pyinjective import Transaction
from pyinjective.async_client import AsyncClient
from pyinjective.composer import Composer, injective_exchange_tx_pb
from pyinjective.core.network import Network
from pyinjective.wallet import Address, PrivateKey

from hummingbot.connector.exchange.injective_v2 import injective_constants as CONSTANTS
from hummingbot.connector.exchange.injective_v2.data_sources.injective_data_source import InjectiveDataSource
from hummingbot.connector.exchange.injective_v2.injective_market import (
    InjectiveDerivativeMarket,
    InjectiveSpotMarket,
    InjectiveToken,
)
from hummingbot.connector.exchange.injective_v2.injective_query_executor import PythonSDKInjectiveQueryExecutor
from hummingbot.connector.gateway.gateway_in_flight_order import GatewayInFlightOrder, GatewayPerpetualInFlightOrder
from hummingbot.connector.utils import combine_to_hb_trading_pair
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.api_throttler.async_throttler_base import AsyncThrottlerBase
from hummingbot.core.api_throttler.data_types import RateLimit
from hummingbot.core.data_type.common import OrderType, PositionAction, TradeType
from hummingbot.core.data_type.in_flight_order import OrderState, OrderUpdate
from hummingbot.core.pubsub import PubSub
from hummingbot.logger import HummingbotLogger


class InjectiveGranteeDataSource(InjectiveDataSource):
    _logger: Optional[HummingbotLogger] = None

    def __init__(
            self,
            private_key: str,
            subaccount_index: int,
            granter_address: str,
            granter_subaccount_index: int,
            network: Network,
            rate_limits: List[RateLimit],
            use_secure_connection: bool = True):
        self._network = network
        self._client = AsyncClient(
            network=self._network,
            insecure=not use_secure_connection,
        )
        self._composer = None
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

        self._publisher = PubSub()
        self._last_received_message_time = 0
        self._throttler = AsyncThrottler(rate_limits=rate_limits)

        self._is_timeout_height_initialized = False
        self._is_trading_account_initialized = False
        self._markets_initialization_lock = asyncio.Lock()
        self._spot_market_info_map: Optional[Dict[str, InjectiveSpotMarket]] = None
        self._derivative_market_info_map: Optional[Dict[str, InjectiveDerivativeMarket]] = None
        self._spot_market_and_trading_pair_map: Optional[Mapping[str, str]] = None
        self._derivative_market_and_trading_pair_map: Optional[Mapping[str, str]] = None
        self._tokens_map: Optional[Dict[str, InjectiveToken]] = None
        self._token_symbol_and_denom_map: Optional[Mapping[str, str]] = None

        self._events_listening_tasks: List[asyncio.Task] = []

    @property
    def publisher(self):
        return self._publisher

    @property
    def query_executor(self):
        return self._query_executor

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

    @property
    def portfolio_account_subaccount_index(self) -> int:
        return self._granter_subaccount_index

    @property
    def network_name(self) -> str:
        return self._network.string()

    async def composer(self) -> Composer:
        if self._composer is None:
            self._composer = await self._client.composer()
        return self._composer

    def events_listening_tasks(self) -> List[asyncio.Task]:
        return self._events_listening_tasks.copy()

    def add_listening_task(self, task: asyncio.Task):
        self._events_listening_tasks.append(task)

    async def timeout_height(self) -> int:
        if not self._is_timeout_height_initialized:
            await self._initialize_timeout_height()
        return self._client.timeout_height

    async def spot_market_and_trading_pair_map(self):
        if self._spot_market_and_trading_pair_map is None:
            async with self._markets_initialization_lock:
                if self._spot_market_and_trading_pair_map is None:
                    await self.update_markets()
        return self._spot_market_and_trading_pair_map.copy()

    async def spot_market_info_for_id(self, market_id: str):
        if self._spot_market_info_map is None:
            async with self._markets_initialization_lock:
                if self._spot_market_info_map is None:
                    await self.update_markets()

        return self._spot_market_info_map[market_id]

    async def derivative_market_and_trading_pair_map(self):
        if self._derivative_market_and_trading_pair_map is None:
            async with self._markets_initialization_lock:
                if self._derivative_market_and_trading_pair_map is None:
                    await self.update_markets()
        return self._derivative_market_and_trading_pair_map.copy()

    async def derivative_market_info_for_id(self, market_id: str):
        if self._derivative_market_info_map is None:
            async with self._markets_initialization_lock:
                if self._derivative_market_info_map is None:
                    await self.update_markets()

        return self._derivative_market_info_map[market_id]

    async def trading_pair_for_market(self, market_id: str):
        if self._spot_market_and_trading_pair_map is None or self._derivative_market_and_trading_pair_map is None:
            async with self._markets_initialization_lock:
                if self._spot_market_and_trading_pair_map is None or self._derivative_market_and_trading_pair_map is None:
                    await self.update_markets()

        trading_pair = self._spot_market_and_trading_pair_map.get(market_id)

        if trading_pair is None:
            trading_pair = self._derivative_market_and_trading_pair_map[market_id]
        return trading_pair

    async def market_id_for_spot_trading_pair(self, trading_pair: str) -> str:
        if self._spot_market_and_trading_pair_map is None:
            async with self._markets_initialization_lock:
                if self._spot_market_and_trading_pair_map is None:
                    await self.update_markets()

        return self._spot_market_and_trading_pair_map.inverse[trading_pair]

    async def market_id_for_derivative_trading_pair(self, trading_pair: str) -> str:
        if self._derivative_market_and_trading_pair_map is None:
            async with self._markets_initialization_lock:
                if self._derivative_market_and_trading_pair_map is None:
                    await self.update_markets()

        return self._derivative_market_and_trading_pair_map.inverse[trading_pair]

    async def spot_markets(self):
        if self._spot_market_and_trading_pair_map is None:
            async with self._markets_initialization_lock:
                if self._spot_market_and_trading_pair_map is None:
                    await self.update_markets()

        return list(self._spot_market_info_map.values())

    async def derivative_markets(self):
        if self._derivative_market_and_trading_pair_map is None:
            async with self._markets_initialization_lock:
                if self._derivative_market_and_trading_pair_map is None:
                    await self.update_markets()

        return list(self._derivative_market_info_map.values())

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

    def supported_order_types(self) -> List[OrderType]:
        return [OrderType.LIMIT, OrderType.LIMIT_MAKER, OrderType.MARKET]

    async def update_markets(self):
        (
            self._tokens_map,
            self._token_symbol_and_denom_map,
            self._spot_market_info_map,
            self._spot_market_and_trading_pair_map,
            self._derivative_market_info_map,
            self._derivative_market_and_trading_pair_map,
        ) = await self._get_markets_and_tokens()

    async def order_updates_for_transaction(
            self,
            transaction_hash: str,
            spot_orders: Optional[List[GatewayInFlightOrder]] = None,
            perpetual_orders: Optional[List[GatewayPerpetualInFlightOrder]] = None,
    ) -> List[OrderUpdate]:
        spot_orders = spot_orders or []
        perpetual_orders = perpetual_orders or []
        transaction_orders = spot_orders + perpetual_orders

        order_updates = []

        async with self.throttler.execute_task(limit_id=CONSTANTS.GET_TRANSACTION_INDEXER_LIMIT_ID):
            transaction_info = await self.query_executor.get_tx_by_hash(tx_hash=transaction_hash)

        if transaction_info["data"].get("errorLog", "") != "":
            # The transaction failed. All orders should be marked as failed
            for order in transaction_orders:
                order_update = OrderUpdate(
                    trading_pair=order.trading_pair,
                    update_timestamp=self._time(),
                    new_state=OrderState.FAILED,
                    client_order_id=order.client_order_id,
                )
                order_updates.append(order_update)

        return order_updates

    def real_tokens_spot_trading_pair(self, unique_trading_pair: str) -> str:
        resulting_trading_pair = unique_trading_pair
        if (self._spot_market_and_trading_pair_map is not None
                and self._spot_market_info_map is not None):
            market_id = self._spot_market_and_trading_pair_map.inverse.get(unique_trading_pair)
            market = self._spot_market_info_map.get(market_id)
            if market is not None:
                resulting_trading_pair = combine_to_hb_trading_pair(
                    base=market.base_token.symbol,
                    quote=market.quote_token.symbol,
                )

        return resulting_trading_pair

    def real_tokens_perpetual_trading_pair(self, unique_trading_pair: str) -> str:
        resulting_trading_pair = unique_trading_pair
        if (self._derivative_market_and_trading_pair_map is not None
                and self._derivative_market_info_map is not None):
            market_id = self._derivative_market_and_trading_pair_map.inverse.get(unique_trading_pair)
            market = self._derivative_market_info_map.get(market_id)
            if market is not None:
                resulting_trading_pair = combine_to_hb_trading_pair(
                    base=market.base_token_symbol(),
                    quote=market.quote_token.symbol,
                )

        return resulting_trading_pair

    async def _initialize_timeout_height(self):
        await self._client.sync_timeout_height()
        self._is_timeout_height_initialized = True

    def _sign_and_encode(self, transaction: Transaction) -> bytes:
        sign_doc = transaction.get_sign_doc(self._public_key)
        sig = self._private_key.sign(sign_doc.SerializeToString())
        tx_raw_bytes = transaction.get_tx_data(sig, self._public_key)
        return tx_raw_bytes

    def _uses_default_portfolio_subaccount(self) -> bool:
        return self._granter_subaccount_index == CONSTANTS.DEFAULT_SUBACCOUNT_INDEX

    def _token_from_market_info(
            self, denom: str, token_meta: Dict[str, Any], candidate_symbol: Optional[str] = None
    ) -> InjectiveToken:
        token = self._tokens_map.get(denom)
        if token is None:
            unique_symbol = token_meta["symbol"]
            if unique_symbol in self._token_symbol_and_denom_map:
                if candidate_symbol is not None and candidate_symbol not in self._token_symbol_and_denom_map:
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
            self._token_symbol_and_denom_map[unique_symbol] = denom

        return token

    async def _updated_derivative_market_info_for_id(self, market_id: str) -> Dict[str, Any]:
        async with self.throttler.execute_task(limit_id=CONSTANTS.DERIVATIVE_MARKETS_LIMIT_ID):
            market_info = await self._query_executor.derivative_market(market_id=market_id)

        return market_info

    async def _order_creation_messages(
            self,
            spot_orders_to_create: List[GatewayInFlightOrder],
            derivative_orders_to_create: List[GatewayPerpetualInFlightOrder],
    ) -> List[any_pb2.Any]:
        composer = await self.composer()
        spot_market_order_definitions = []
        derivative_market_order_definitions = []
        spot_order_definitions = []
        derivative_order_definitions = []
        all_messages = []

        for order in spot_orders_to_create:
            if order.order_type == OrderType.MARKET:
                market_id = await self.market_id_for_spot_trading_pair(order.trading_pair)
                creation_message = composer.MsgCreateSpotMarketOrder(
                    sender=self.portfolio_account_injective_address,
                    market_id=market_id,
                    subaccount_id=self.portfolio_account_subaccount_id,
                    fee_recipient=self.portfolio_account_injective_address,
                    price=order.price,
                    quantity=order.amount,
                    cid=order.client_order_id,
                    is_buy=order.trade_type == TradeType.BUY,
                )
                spot_market_order_definitions.append(creation_message.order)
                all_messages.append(creation_message)
            else:
                order_definition = await self._create_spot_order_definition(order=order)
                spot_order_definitions.append(order_definition)

        for order in derivative_orders_to_create:
            if order.order_type == OrderType.MARKET:
                market_id = await self.market_id_for_derivative_trading_pair(order.trading_pair)
                creation_message = composer.MsgCreateDerivativeMarketOrder(
                    sender=self.portfolio_account_injective_address,
                    market_id=market_id,
                    subaccount_id=self.portfolio_account_subaccount_id,
                    fee_recipient=self.portfolio_account_injective_address,
                    price=order.price,
                    quantity=order.amount,
                    cid=order.client_order_id,
                    leverage=order.leverage,
                    is_buy=order.trade_type == TradeType.BUY,
                    is_reduce_only=order.position == PositionAction.CLOSE,
                )
                derivative_market_order_definitions.append(creation_message.order)
                all_messages.append(creation_message)
            else:
                order_definition = await self._create_derivative_order_definition(order=order)
                derivative_order_definitions.append(order_definition)

        if len(spot_order_definitions) > 0 or len(derivative_order_definitions) > 0:
            message = composer.MsgBatchUpdateOrders(
                sender=self.portfolio_account_injective_address,
                spot_orders_to_create=spot_order_definitions,
                derivative_orders_to_create=derivative_order_definitions,
            )
            all_messages.append(message)

        delegated_message = composer.MsgExec(
            grantee=self.trading_account_injective_address,
            msgs=all_messages
        )

        return [delegated_message]

    async def _order_cancel_message(
            self,
            spot_orders_to_cancel: List[injective_exchange_tx_pb.OrderData],
            derivative_orders_to_cancel: List[injective_exchange_tx_pb.OrderData]
    ) -> any_pb2.Any:
        composer = await self.composer()

        message = composer.MsgBatchUpdateOrders(
            sender=self.portfolio_account_injective_address,
            spot_orders_to_cancel=spot_orders_to_cancel,
            derivative_orders_to_cancel=derivative_orders_to_cancel,
        )
        delegated_message = composer.MsgExec(
            grantee=self.trading_account_injective_address,
            msgs=[message]
        )
        return delegated_message

    async def _all_subaccount_orders_cancel_message(
            self,
            spot_markets_ids: List[str],
            derivative_markets_ids: List[str]
    ) -> any_pb2.Any:
        composer = await self.composer()

        message = composer.MsgBatchUpdateOrders(
            sender=self.portfolio_account_injective_address,
            subaccount_id=self.portfolio_account_subaccount_id,
            spot_market_ids_to_cancel_all=spot_markets_ids,
            derivative_market_ids_to_cancel_all=derivative_markets_ids,
        )
        delegated_message = composer.MsgExec(
            grantee=self.trading_account_injective_address,
            msgs=[message]
        )
        return delegated_message

    async def _generate_injective_order_data(self, order: GatewayInFlightOrder, market_id: str) -> injective_exchange_tx_pb.OrderData:
        composer = await self.composer()
        order_hash = order.exchange_order_id
        cid = order.client_order_id if order_hash is None else None
        order_data = composer.OrderData(
            market_id=market_id,
            subaccount_id=self.portfolio_account_subaccount_id,
            order_hash=order_hash,
            cid=cid,
            order_direction="buy" if order.trade_type == TradeType.BUY else "sell",
            order_type="market" if order.order_type == OrderType.MARKET else "limit",
        )

        return order_data
