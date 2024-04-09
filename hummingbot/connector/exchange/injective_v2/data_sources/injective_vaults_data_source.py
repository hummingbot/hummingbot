import asyncio
import json
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, List, Mapping, Optional

from google.protobuf import any_pb2, json_format
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

if TYPE_CHECKING:
    from hummingbot.connector.exchange.injective_v2.injective_v2_utils import InjectiveFeeCalculatorMode


class InjectiveVaultsDataSource(InjectiveDataSource):
    _logger: Optional[HummingbotLogger] = None

    def __init__(
            self,
            private_key: str,
            subaccount_index: int,
            vault_contract_address: str,
            vault_subaccount_index: int,
            network: Network,
            rate_limits: List[RateLimit],
            fee_calculator_mode: "InjectiveFeeCalculatorMode",
            use_secure_connection: bool = True):
        self._network = network
        self._client = AsyncClient(
            network=self._network,
            insecure=not use_secure_connection,
        )
        self._composer = None
        self._query_executor = PythonSDKInjectiveQueryExecutor(sdk_client=self._client)
        self._fee_calculator_mode = fee_calculator_mode
        self._fee_calculator = None

        self._private_key = None
        self._public_key = None
        self._vault_admin_address = ""
        self._vault_admin_subaccount_index = subaccount_index
        self._vault_admin_subaccount_id = ""
        if private_key:
            self._private_key = PrivateKey.from_hex(private_key)
            self._public_key = self._private_key.to_public_key()
            self._vault_admin_address = self._public_key.to_address()
            self._vault_admin_subaccount_id = self._vault_admin_address.get_subaccount_id(index=subaccount_index)

        self._vault_contract_address = None
        self._vault_subaccount_id = ""
        self._vault_subaccount_index = vault_subaccount_index
        if vault_contract_address:
            self._vault_contract_address = Address.from_acc_bech32(vault_contract_address)
            self._vault_subaccount_id = self._vault_contract_address.get_subaccount_id(index=vault_subaccount_index)

        self._publisher = PubSub()
        self._last_received_message_timestamp = 0
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
        return self._vault_contract_address.to_acc_bech32()

    @property
    def portfolio_account_subaccount_id(self) -> str:
        return self._vault_subaccount_id

    @property
    def trading_account_injective_address(self) -> str:
        return self._vault_admin_address.to_acc_bech32()

    @property
    def injective_chain_id(self) -> str:
        return self._network.chain_id

    @property
    def fee_denom(self) -> str:
        return self._network.fee_denom

    @property
    def portfolio_account_subaccount_index(self) -> int:
        return self._vault_subaccount_index

    @property
    def network_name(self) -> str:
        return self._network.string()

    @property
    def last_received_message_timestamp(self) -> float:
        return self._last_received_message_timestamp

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
        await self._client.fetch_account(address=self.trading_account_injective_address)
        self._is_trading_account_initialized = True

    def supported_order_types(self) -> List[OrderType]:
        return [OrderType.LIMIT, OrderType.LIMIT_MAKER]

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
        order_updates = []

        async with self.throttler.execute_task(limit_id=CONSTANTS.GET_TRANSACTION_LIMIT_ID):
            transaction_info = await self.query_executor.get_tx(tx_hash=transaction_hash)

        if transaction_info["txResponse"]["code"] != CONSTANTS.TRANSACTION_SUCCEEDED_CODE:
            # The transaction failed. All orders should be marked as failed
            for order in (spot_orders + perpetual_orders):
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
        return self._vault_subaccount_index == CONSTANTS.DEFAULT_SUBACCOUNT_INDEX

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
        spot_order_definitions = []
        derivative_order_definitions = []

        for order in spot_orders_to_create:
            order_definition = await self._create_spot_order_definition(order=order)
            spot_order_definitions.append(order_definition)

        for order in derivative_orders_to_create:
            order_definition = await self._create_derivative_order_definition(order=order)
            derivative_order_definitions.append(order_definition)

        message = composer.msg_batch_update_orders(
            sender=self.portfolio_account_injective_address,
            spot_orders_to_create=spot_order_definitions,
            derivative_orders_to_create=derivative_order_definitions,
        )

        message_as_dictionary = json_format.MessageToDict(
            message=message,
            including_default_value_fields=True,
            preserving_proto_field_name=True,
            use_integers_for_enums=True,
        )
        del message_as_dictionary["subaccount_id"]

        execute_message_parameter = self._create_execute_contract_internal_message(batch_update_orders_params=message_as_dictionary)

        execute_contract_message = composer.MsgExecuteContract(
            sender=self._vault_admin_address.to_acc_bech32(),
            contract=self._vault_contract_address.to_acc_bech32(),
            msg=json.dumps(execute_message_parameter),
        )

        return [execute_contract_message]

    async def _order_cancel_message(
            self,
            spot_orders_to_cancel: List[injective_exchange_tx_pb.OrderData],
            derivative_orders_to_cancel: List[injective_exchange_tx_pb.OrderData]
    ) -> any_pb2.Any:
        composer = await self.composer()

        message = composer.msg_batch_update_orders(
            sender=self.portfolio_account_injective_address,
            spot_orders_to_cancel=spot_orders_to_cancel,
            derivative_orders_to_cancel=derivative_orders_to_cancel,
        )

        message_as_dictionary = json_format.MessageToDict(
            message=message,
            including_default_value_fields=True,
            preserving_proto_field_name=True,
            use_integers_for_enums=True,
        )
        del message_as_dictionary["subaccount_id"]

        execute_message_parameter = self._create_execute_contract_internal_message(batch_update_orders_params=message_as_dictionary)

        execute_contract_message = composer.MsgExecuteContract(
            sender=self._vault_admin_address.to_acc_bech32(),
            contract=self._vault_contract_address.to_acc_bech32(),
            msg=json.dumps(execute_message_parameter),
        )

        return execute_contract_message

    async def _all_subaccount_orders_cancel_message(
            self,
            spot_markets_ids: List[str],
            derivative_markets_ids: List[str]
    ) -> any_pb2.Any:
        composer = await self.composer()

        message = composer.msg_batch_update_orders(
            sender=self.portfolio_account_injective_address,
            subaccount_id=self.portfolio_account_subaccount_id,
            spot_market_ids_to_cancel_all=spot_markets_ids,
            derivative_market_ids_to_cancel_all=derivative_markets_ids,
        )

        message_as_dictionary = json_format.MessageToDict(
            message=message,
            including_default_value_fields=True,
            preserving_proto_field_name=True,
            use_integers_for_enums=True,
        )

        execute_message_parameter = self._create_execute_contract_internal_message(
            batch_update_orders_params=message_as_dictionary)

        execute_contract_message = composer.MsgExecuteContract(
            sender=self._vault_admin_address.to_acc_bech32(),
            contract=self._vault_contract_address.to_acc_bech32(),
            msg=json.dumps(execute_message_parameter),
        )

        return execute_contract_message

    async def _generate_injective_order_data(self, order: GatewayInFlightOrder, market_id: str) -> injective_exchange_tx_pb.OrderData:
        composer = await self.composer()
        order_hash = order.exchange_order_id
        cid = order.client_order_id if order_hash is None else None
        order_data = composer.order_data(
            market_id=market_id,
            subaccount_id=str(self.portfolio_account_subaccount_index),
            order_hash=order_hash,
            cid=cid,
            is_buy=order.trade_type == TradeType.BUY,
            is_market_order=order.order_type == OrderType.MARKET,
        )

        return order_data

    async def _create_spot_order_definition(self, order: GatewayInFlightOrder):
        # Both price and quantity have to be adjusted because the vaults expect to receive those values without
        # the extra 18 zeros that the chain backend expects for direct trading messages
        order_type = "BUY" if order.trade_type == TradeType.BUY else "SELL"
        if order.order_type == OrderType.LIMIT_MAKER:
            order_type = order_type + "_PO"
        market_id = await self.market_id_for_spot_trading_pair(order.trading_pair)
        composer = await self.composer()
        definition = composer.spot_order(
            market_id=market_id,
            subaccount_id=str(self.portfolio_account_subaccount_index),
            fee_recipient=self.portfolio_account_injective_address,
            price=order.price,
            quantity=order.amount,
            order_type=order_type,
            cid=order.client_order_id,
        )

        definition.order_info.quantity = f"{(Decimal(definition.order_info.quantity) * Decimal('1e-18')).normalize():f}"
        definition.order_info.price = f"{(Decimal(definition.order_info.price) * Decimal('1e-18')).normalize():f}"
        return definition

    async def _create_derivative_order_definition(self, order: GatewayPerpetualInFlightOrder):
        # Price, quantity and margin have to be adjusted because the vaults expect to receive those values without
        # the extra 18 zeros that the chain backend expects for direct trading messages
        order_type = "BUY" if order.trade_type == TradeType.BUY else "SELL"
        if order.order_type == OrderType.LIMIT_MAKER:
            order_type = order_type + "_PO"
        market_id = await self.market_id_for_derivative_trading_pair(order.trading_pair)
        composer = await self.composer()
        definition = composer.derivative_order(
            market_id=market_id,
            subaccount_id=str(self.portfolio_account_subaccount_index),
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

        definition.order_info.quantity = f"{(Decimal(definition.order_info.quantity) * Decimal('1e-18')).normalize():f}"
        definition.order_info.price = f"{(Decimal(definition.order_info.price) * Decimal('1e-18')).normalize():f}"
        definition.margin = f"{(Decimal(definition.margin) * Decimal('1e-18')).normalize():f}"
        return definition

    def _create_execute_contract_internal_message(self, batch_update_orders_params: Dict) -> Dict[str, Any]:
        return {
            "admin_execute_message": {
                "injective_message": {
                    "custom": {
                        "route": "exchange",
                        "msg_data": {
                            "batch_update_orders": batch_update_orders_params
                        }
                    }
                }
            }
        }

    async def _process_chain_stream_update(
            self, chain_stream_update: Dict[str, Any], derivative_markets: List[InjectiveDerivativeMarket],
    ):
        self._last_received_message_timestamp = self._time()
        await super()._process_chain_stream_update(
            chain_stream_update=chain_stream_update,
            derivative_markets=derivative_markets,
        )

    async def _process_transaction_update(self, transaction_event: Dict[str, Any]):
        self._last_received_message_timestamp = self._time()
        await super()._process_transaction_update(transaction_event=transaction_event)

    async def _configure_gas_fee_for_transaction(self, transaction: Transaction):
        multiplier = (None
                      if CONSTANTS.GAS_LIMIT_ADJUSTMENT_MULTIPLIER is None
                      else Decimal(str(CONSTANTS.GAS_LIMIT_ADJUSTMENT_MULTIPLIER)))
        if self._fee_calculator is None:
            self._fee_calculator = self._fee_calculator_mode.create_calculator(
                client=self._client,
                composer=await self.composer(),
                gas_price=CONSTANTS.TX_GAS_PRICE,
                gas_limit_adjustment_multiplier=multiplier,
            )

        await self._fee_calculator.configure_gas_fee_for_transaction(
            transaction=transaction,
            private_key=self._private_key,
            public_key=self._public_key,
        )
