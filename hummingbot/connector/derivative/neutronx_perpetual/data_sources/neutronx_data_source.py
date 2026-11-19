import asyncio
import logging
import time
from decimal import Decimal
from typing import Optional, Tuple

from neutronx_sdk import (
    ClientIdAllocator,
    FeePolicy,
    Network,
    NeutronXError,
    NodeClient,
    OrderRequest,
    PrivateKey,
    TxSender,
    Wallet,
)
from neutronx_sdk.models import (
    POSITION_STATUS_OPEN,
    FeeTier,
    Market,
    Order,
    OrderbookParams,
    Position,
    SubaccountBalance,
    agent_key_problem,
)

from hummingbot.connector.derivative.neutronx_perpetual import neutronx_perpetual_constants as CONSTANTS
from hummingbot.connector.derivative.neutronx_perpetual.data_sources.tx_queue import (
    CancelledOrder,
    OrderTxQueue,
    PlacedOrder,
)
from hummingbot.logger import HummingbotLogger

OPEN_STATUS_FILTER = "open"
REGULAR_ORDERS = "regular"


def build_wallet(network: Network, account_address: str, private_key: str, agent_key_id: int) -> Wallet:
    key = PrivateKey.from_hex(private_key)
    if agent_key_id > 0:
        return Wallet.agent(key, account=account_address, key_id=agent_key_id, prefix=network.bech32_prefix)
    return Wallet(key, prefix=network.bech32_prefix, account=account_address)


class NeutronxDataSource:
    _logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(HummingbotLogger.logger_name_for_class(cls))
        return cls._logger

    def __init__(
        self,
        network: Network,
        account_address: str,
        subaccount_id: int = 0,
        wallet: Optional[Wallet] = None,
        client: Optional[NodeClient] = None,
    ) -> None:
        self._network = network
        self._account_address = account_address
        self._subaccount_id = subaccount_id
        self._wallet = wallet
        self._client = client or NodeClient(network)
        self._client_ids = ClientIdAllocator(start=int(time.time()))
        self._params: Optional[OrderbookParams] = None
        self._sender: Optional[TxSender] = None
        self._queue: Optional[OrderTxQueue] = None
        self._lifecycle = asyncio.Lock()

    @property
    def network(self) -> Network:
        return self._network

    @property
    def account_address(self) -> str:
        return self._account_address

    @property
    def subaccount_id(self) -> int:
        return self._subaccount_id

    @property
    def client(self) -> NodeClient:
        return self._client

    @property
    def client_ids(self) -> ClientIdAllocator:
        return self._client_ids

    @property
    def trading_ready(self) -> bool:
        return self._queue is not None and self._queue.running

    async def start_trading(self) -> None:
        if self._wallet is None:
            raise NeutronXError("trading needs a signing key")
        async with self._lifecycle:
            await self._stop_queue()
            if self._wallet.is_agent:
                await self._check_agent_key(self._wallet)
            params = await self.orderbook_params(refresh=True)
            perps = await self._client.perps.params()
            self._sender = TxSender(self._client, self._wallet, fee=FeePolicy.for_trading(params, perps.margin_denom))
            await self._warn_on_low_fee_balance(perps.margin_denom)
            self._client_ids.seed(order.client_id for order in await self.open_orders() if order.client_id)
            gas_ceiling = params.max_gas_wanted or CONSTANTS.DEFAULT_TX_GAS_CEILING
            self._queue = OrderTxQueue(
                self._sender,
                max_places_per_tx=params.rate_limit_per_block,
                gas_ceiling=min(gas_ceiling, CONSTANTS.DEFAULT_TX_GAS_CEILING),
            )
            self._queue.start()

    async def stop(self) -> None:
        async with self._lifecycle:
            await self._stop_queue()

    async def _stop_queue(self) -> None:
        queue, self._queue = self._queue, None
        if queue is not None:
            await queue.stop()

    async def close(self) -> None:
        await self.stop()
        await self._client.close()

    async def check_node(self) -> int:
        return (await self._client.node.status()).height

    async def markets(self) -> Tuple[Market, ...]:
        return await self._client.perps.markets()

    async def orderbook_params(self, refresh: bool = False) -> OrderbookParams:
        if self._params is None or refresh:
            self._params = await self._client.orderbook.params()
        return self._params

    async def open_orders(self) -> Tuple[Order, ...]:
        orders = await self._client.orderbook.all_user_orders(
            self._account_address, status_filter=OPEN_STATUS_FILTER, include=REGULAR_ORDERS
        )
        return tuple(order for order in orders if order.subaccount_id == self._subaccount_id)

    async def order(self, order_id: int) -> Optional[Order]:
        return await self._client.orderbook.order(order_id)

    async def balance(self) -> SubaccountBalance:
        return await self._client.perps.subaccount_balance(self._account_address, self._subaccount_id)

    async def positions(self) -> Tuple[Position, ...]:
        positions = []
        page = 1
        while True:
            result = await self._client.perps.positions(self._account_address, page=page)
            positions.extend(p for p in result.positions if p.subaccount_id == self._subaccount_id)
            if not result.has_next:
                return tuple(p for p in positions if p.status == POSITION_STATUS_OPEN)
            page += 1

    async def fee_tier(self) -> FeeTier:
        return await self._client.orderbook.fee_tier(self._account_address)

    async def place(self, request: OrderRequest) -> PlacedOrder:
        return await self._trading_queue().place(request)

    async def cancel(self, order_id: int) -> CancelledOrder:
        return await self._trading_queue().cancel(order_id)

    def _trading_queue(self) -> OrderTxQueue:
        if self._queue is None:
            raise ConnectionError("NeutronX trading has not started")
        return self._queue

    async def _warn_on_low_fee_balance(self, denom: str) -> None:
        coins = await self._client.bank.balances(self._account_address)
        held = Decimal(sum(coin.amount for coin in coins if coin.denom == denom)).scaleb(-self._network.margin_decimals)
        if held < CONSTANTS.LOW_FEE_BALANCE:
            self.logger().warning(
                f"The wallet of {self._account_address} holds {held} {CONSTANTS.QUOTE_ASSET} for transaction fees. "
                "Fees are paid from the wallet, not from the trading account, and orders fail once it is empty."
            )

    async def _check_agent_key(self, wallet: Wallet) -> None:
        enabled = await self._client.agentkeys.enabled()
        key = await self._client.agentkeys.agent_key(wallet.address, wallet.agent_key_id) if enabled else None
        problem = agent_key_problem(enabled, key, wallet.public_key.compressed, time.time())
        if problem is not None:
            raise NeutronXError(f"agent key {wallet.agent_key_id} of {wallet.address} cannot trade: {problem.value}")
