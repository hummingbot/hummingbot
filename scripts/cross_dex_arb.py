import asyncio
import logging
from typing import Any, Coroutine, Dict, Optional, Set, Tuple

from pydantic import BaseModel

from hummingbot.connector.connector_base import ConnectorBase
from hummingbot.core.data_type.common import TradeType
from hummingbot.core.gateway.gateway_http_client import GatewayHttpClient
from hummingbot.core.network_base import NetworkBase
from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.logger import HummingbotLogger
from hummingbot.strategy.script_strategy_base import Decimal, ScriptStrategyBase


# TODO: move data type conversion logic in BaseModel (e.g. parse price from str to float)
class TokenPrice(BaseModel):
    network: str
    timestamp: int
    latency: float
    base: str
    quote: str
    amount: str
    rawAmount: str
    expectedAmount: str
    price: str
    gasPrice: int
    gasPriceToken: str
    gasLimit: int
    gasCost: str


class TokenBuySellPrice(BaseModel):
    base: str
    quote: str
    connector: str
    chain: str
    network: str
    order_amount: Decimal
    buy: TokenPrice
    sell: TokenPrice


class DexDataFeed(NetworkBase):
    dex_logger: Optional[HummingbotLogger] = None
    gateway_client = GatewayHttpClient.get_instance()

    def __init__(
        self,
        connector_chain_network: str,
        trading_pairs: Set[str],
        order_amount: Decimal,
        update_interval: float,
    ) -> None:
        super().__init__()
        self._ev_loop = asyncio.get_event_loop()
        self._price_dict: Dict[str, TokenBuySellPrice] = {}
        self._update_interval = update_interval
        self.fetch_data_loop_task: Optional[asyncio.Task] = None
        # param required for DEX API request
        self.connector_chain_network = connector_chain_network
        self.trading_pairs = trading_pairs
        self.order_amount = order_amount

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls.dex_logger is None:
            cls.dex_logger = logging.getLogger(__name__)
        return cls.dex_logger

    @property
    def name(self) -> str:
        return f"DexDataFeed[{self.connector_chain_network}]"

    @property
    def connector(self) -> str:
        return self.connector_chain_network.split("_")[0]

    @property
    def chain(self) -> str:
        return self.connector_chain_network.split("_")[1]

    @property
    def network(self) -> str:
        return self.connector_chain_network.split("_")[2]

    async def check_network(self) -> NetworkStatus:
        is_gateway_online = await self.gateway_client.ping_gateway()
        return (
            NetworkStatus.CONNECTED
            if is_gateway_online
            else NetworkStatus.NOT_CONNECTED
        )

    async def start_network(self) -> None:
        await self.stop_network()
        self.fetch_data_loop_task = safe_ensure_future(self._fetch_data_loop())

    async def stop_network(self) -> None:
        if self.fetch_data_loop_task is not None:
            self.fetch_data_loop_task.cancel()
            self.fetch_data_loop_task = None

    @property
    def price_dict(self) -> Dict[str, TokenBuySellPrice]:
        return self._price_dict

    async def _fetch_data_loop(self) -> None:
        while True:
            try:
                await self._fetch_data()
            except asyncio.CancelledError:
                raise
            except Exception as e:
                self.logger().network(
                    f"Error getting data from {self.name}",
                    exc_info=True,
                    app_warning_msg=f"Couldn't fetch newest prices from {self.name}. "
                    f"Check network connection. Error: {e}",
                )
            await self._async_sleep(self._update_interval)

    async def _fetch_data(self) -> None:
        await self._update_price_dict()

    async def _update_price_dict(self) -> None:
        token_price_tasks = [
            asyncio.create_task(self._register_token_buy_sell_price(trading_pair))
            for trading_pair in self.trading_pairs
        ]
        await asyncio.gather(*token_price_tasks)

    async def _register_token_buy_sell_price(self, trading_pair: str) -> None:
        base, quote = split_base_quote(trading_pair)
        token_buy_price_task = asyncio.create_task(
            self._request_token_price(trading_pair, TradeType.BUY)
        )
        token_sell_price_task = asyncio.create_task(
            self._request_token_price(trading_pair, TradeType.SELL)
        )
        self._price_dict[trading_pair] = TokenBuySellPrice(
            base=base,
            quote=quote,
            connector=self.connector,
            chain=self.chain,
            network=self.network,
            order_amount=self.order_amount,
            buy=await token_buy_price_task,
            sell=await token_sell_price_task,
        )

    async def _request_token_price(
        self, trading_pair: str, trade_type: TradeType
    ) -> TokenPrice:
        base, quote = split_base_quote(trading_pair)
        connector, chain, network = self.connector_chain_network.split("_")
        token_price = await self.gateway_client.get_price(
            chain, network, connector, base, quote, self.order_amount, trade_type
        )
        return TokenPrice(**token_price)

    @staticmethod
    async def _async_sleep(delay: float) -> None:
        """Used to mock in test cases."""
        await asyncio.sleep(delay)


# TODO: generalise on multiple trading pairs on the same chain
# TODO: hedging gas-token, and pair inventories
# TODO: rebalancing when base/ quote/ gas-token is running out
# TODO: integrate with postgres
# TODO: integrate with telegram bot
class CrossDexArb(ScriptStrategyBase):
    # define markets
    chain = "binance-smart-chain"
    network = "mainnet"
    connector_chain_network_a = f"pancakeswap_{chain}_{network}"
    connector_chain_network_b = f"sushiswap_{chain}_{network}"
    trading_pairs = {"USDT-WBNB"}
    markets = {
        connector_chain_network_a: trading_pairs,
        connector_chain_network_b: trading_pairs,
    }

    # set up data feed for 2 DEXs
    update_interval = 0.0
    order_amount: Decimal = Decimal("50")
    dex_data_feed_a = DexDataFeed(
        connector_chain_network_a, trading_pairs, order_amount, update_interval
    )
    dex_data_feed_b = DexDataFeed(
        connector_chain_network_b, trading_pairs, order_amount, update_interval
    )

    # for execute trade
    wallet_address = "0xe871bc4D06E9337fD5611c28812e7E29478E9145"
    gateway_client = GatewayHttpClient.get_instance()
    gas_token = "BNB"
    min_gas_token_amount = Decimal("0.001")
    min_profit_bp = 5

    def __init__(self, connectors: Dict[str, ConnectorBase]) -> None:
        # Is necessary to start the Candles Feed.
        super().__init__(connectors)
        self.dex_data_feed_a.start()
        self.dex_data_feed_b.start()
        self.logger().info(
            f"{self.dex_data_feed_a.name} and {self.dex_data_feed_b.name} started..."
        )

    def on_stop(self) -> None:
        """
        Without this functionality, the network iterator will continue running forever after stopping the strategy
        That's why is necessary to introduce this new feature to make a custom stop with the strategy.
        """
        self.dex_data_feed_a.stop()
        self.dex_data_feed_b.stop()
        self.logger().info(
            f"{self.dex_data_feed_a.name} and {self.dex_data_feed_b.name} terminated..."
        )

    def on_tick(self) -> None:
        safe_ensure_future(self.async_on_tick())

    async def async_on_tick(self) -> None:
        if not self.is_dex_data_feeds_initialised():
            self.logger().info(
                f"Not All DexDataFeeds are initialised. Skip this on_tick."
            )
            return
        balances = await self._update_wallet_balance()
        self.logger().info(f"balances: {balances}")

        if self.is_out_of_balance():
            self.logger().warning(
                f"Trading pairs: {self.trading_pairs} are out of balance. Please manually rebalance..."
            )
            return
        if self.is_out_of_gas_reserve():
            self.logger().warning(
                f"Gas token: {self.gas_token} is out of reserve. Please manually top up..."
            )
            return

        for trading_pair in self.trading_pairs:
            if self.should_base_buy_a_sell_b(trading_pair):
                self.base_buy_a_sell_b(trading_pair)
            if self.should_base_buy_b_sell_a(trading_pair):
                self.base_buy_b_sell_a(trading_pair)

    # TODO: now assume gas fee and quote token is in same currency (i.e. WBNB & BNB)
    def should_base_buy_a_sell_b(self, trading_pair: str) -> bool:
        quote_amount_out = float(
            self.dex_data_feed_a.price_dict[trading_pair].buy.expectedAmount
        )
        a_gas_fee = float(self.dex_data_feed_a.price_dict[trading_pair].buy.gasCost)
        quote_amount_in = float(
            self.dex_data_feed_b.price_dict[trading_pair].sell.expectedAmount
        )
        b_gas_fee = float(self.dex_data_feed_b.price_dict[trading_pair].sell.gasCost)
        profit_pb = (
            (quote_amount_in - quote_amount_out - a_gas_fee - b_gas_fee)
            / quote_amount_in
            * 10000
        )
        return profit_pb >= self.min_profit_bp

    def should_base_buy_b_sell_a(self, trading_pair: str) -> bool:
        quote_amount_out = float(
            self.dex_data_feed_b.price_dict[trading_pair].buy.expectedAmount
        )
        b_gas_fee = float(self.dex_data_feed_b.price_dict[trading_pair].buy.gasCost)
        quote_amount_in = float(
            self.dex_data_feed_a.price_dict[trading_pair].sell.expectedAmount
        )
        a_gas_fee = float(self.dex_data_feed_a.price_dict[trading_pair].sell.gasCost)
        profit_pb = (
            (quote_amount_in - quote_amount_out - b_gas_fee - a_gas_fee)
            / quote_amount_in
            * 10000
        )
        return profit_pb >= self.min_profit_bp

    def is_out_of_balance(self) -> bool:
        return False

    def is_out_of_gas_reserve(self) -> bool:
        return False

    def is_dex_data_feeds_initialised(self) -> bool:
        return (
            len(self.dex_data_feed_b.price_dict) > 0
            and len(self.dex_data_feed_b.price_dict) > 0
        )

    def base_buy_a_sell_b(self, trading_pair: str) -> None:
        return

    def base_buy_b_sell_a(self, trading_pair: str) -> None:
        return

    async def _update_wallet_balance(self):
        token_symbols = set()
        for trading_pair in self.trading_pairs:
            base_token, quote_token = split_base_quote(trading_pair)
            token_symbols.add(base_token)
            token_symbols.add(quote_token)
        balances = await self.gateway_client.get_balances(
            self.chain,
            self.network,
            self.wallet_address,
            token_symbols=list(token_symbols),
        )
        return balances


def split_base_quote(trading_pair: str) -> Tuple[str, str]:
    base, quote = trading_pair.split("-")
    return base, quote
