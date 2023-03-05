from typing import Dict, Optional

from hummingbot.client.settings import GatewayConnectionSetting
from hummingbot.connector.connector_base import ConnectorBase
from hummingbot.core.data_type.common import TradeType
from hummingbot.core.gateway.gateway_http_client import GatewayHttpClient
from hummingbot.core.gateway.types import Transaction
from hummingbot.core.utils import split_base_quote
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.data_feed.amm_data_feed import AmmDataFeed
from hummingbot.strategy.script_strategy_base import Decimal, ScriptStrategyBase

UNKNONW = -1


class SlippagePriceError(Exception):
    pass


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
    trading_pair = "USDT-WBNB"
    markets = {
        connector_chain_network_a: {trading_pair},
        connector_chain_network_b: {trading_pair},
    }

    # set up data feed for 2 DEXs
    update_interval = 0.0
    order_amount_in_base: Decimal = Decimal("50")
    dex_data_feed_a = AmmDataFeed(connector_chain_network_a, {trading_pair}, order_amount_in_base, update_interval)
    dex_data_feed_b = AmmDataFeed(connector_chain_network_b, {trading_pair}, order_amount_in_base, update_interval)

    # for execute trade
    gateway_client = GatewayHttpClient.get_instance()
    gas_token = "BNB"
    min_gas_token_amount = Decimal("0.001")
    min_profit_bp = 5
    is_submit_tx_incomplete = False
    is_poll_tx_incomplete = False
    transaction_a: Optional[Transaction] = None
    transaction_b: Optional[Transaction] = None
    last_trade_timestamp: int = UNKNONW
    last_query_balance_timestamp: int = UNKNONW

    def __init__(self, connectors: Dict[str, ConnectorBase]) -> None:
        # Is necessary to start the Candles Feed.
        super().__init__(connectors)
        self.dex_data_feed_a.start()
        self.dex_data_feed_b.start()
        self.logger().info(f"{self.dex_data_feed_a.name} and {self.dex_data_feed_b.name} started...")
        self._load_wallet_address()

    def on_stop(self) -> None:
        """
        Without this functionality, the network iterator will continue running forever after stopping the strategy
        That's why is necessary to introduce this new feature to make a custom stop with the strategy.
        """
        self.dex_data_feed_a.stop()
        self.dex_data_feed_b.stop()
        self.logger().info(f"{self.dex_data_feed_a.name} and {self.dex_data_feed_b.name} terminated...")

    def on_tick(self) -> None:
        is_precheck_pass = self.precheck()
        if not is_precheck_pass:
            return

        if self.transaction_a and self.transaction_b:
            safe_ensure_future(self.poll_transaction_status())
        elif self.transaction_a or self.transaction_b:
            self.logger().warning(
                f"Either transaction_a ({self.transaction_a}) "
                f"or transaction_b ({self.transaction_b}) is None."
                "This should not happen. Please review the code!"
            )
        else:
            safe_ensure_future(self.async_on_tick())
        return

    def precheck(self) -> bool:
        is_precheck_pass = False
        if not self.is_wallet_address_set():
            self.logger().warning(
                "Wallet address is not found. " "Please check if your wallet is connected to Gateway!"
            )
        if not self.is_amm_data_feeds_initialised():
            self.logger().info(f"Not All AmmDataFeeds are initialised. Skip this on_tick.")
        if self.is_submit_tx_incomplete:
            self.logger().info("Submit AMM trade requests are in progress. Skip this on_tick")
        if self.is_poll_tx_incomplete:
            assert (
                self.transaction_a and self.transaction_b
            ), "transaction_a and transaction_b should not be None when is_poll_tx_incomplete is True."
            tx_hash_a = self.transaction_a.txHash
            tx_hash_b = self.transaction_b.txHash
            self.logger().info(
                f"Poll transaction are in progress. Skip this on_tick.\n"
                f"txHash for {self.connector_chain_network_a}: {tx_hash_a}.\n"
                f"txHash_b for {self.connector_chain_network_b}: {tx_hash_b}."
            )
        else:
            is_precheck_pass = True
        return is_precheck_pass

    async def async_on_tick(self) -> None:
        balances = await self._update_wallet_balance()
        self.logger().info(f"balances: {balances}")

        if self.is_out_of_balance():
            self.logger().warning(f"Trading pair ({self.trading_pair}) is out of balance. Please manually rebalance...")
            return
        if self.is_out_of_gas_reserve():
            self.logger().warning(f"Gas token: {self.gas_token} is out of reserve. Please manually top up...")
            return

        if self.should_base_buy_a_sell_b():
            self.base_buy_a_sell_b()
        if self.should_base_buy_b_sell_a():
            self.base_buy_b_sell_a()

    # TODO: now assume gas fee and quote token is in same currency (i.e. WBNB & BNB)
    def should_base_buy_a_sell_b(self) -> bool:
        trading_pair = self.trading_pair
        quote_amount_out = float(self.dex_data_feed_a.price_dict[trading_pair].buy.expectedAmount)
        a_gas_fee = float(self.dex_data_feed_a.price_dict[trading_pair].buy.gasCost)
        quote_amount_in = float(self.dex_data_feed_b.price_dict[trading_pair].sell.expectedAmount)
        b_gas_fee = float(self.dex_data_feed_b.price_dict[trading_pair].sell.gasCost)
        profit_pb = (quote_amount_in - quote_amount_out - a_gas_fee - b_gas_fee) / quote_amount_in * 10000
        return profit_pb >= self.min_profit_bp

    def should_base_buy_b_sell_a(self) -> bool:
        trading_pair = self.trading_pair
        quote_amount_out = float(self.dex_data_feed_b.price_dict[trading_pair].buy.expectedAmount)
        b_gas_fee = float(self.dex_data_feed_b.price_dict[trading_pair].buy.gasCost)
        quote_amount_in = float(self.dex_data_feed_a.price_dict[trading_pair].sell.expectedAmount)
        a_gas_fee = float(self.dex_data_feed_a.price_dict[trading_pair].sell.gasCost)
        profit_pb = (quote_amount_in - quote_amount_out - b_gas_fee - a_gas_fee) / quote_amount_in * 10000
        return profit_pb >= self.min_profit_bp

    def is_out_of_balance(self) -> bool:
        return False

    def is_out_of_gas_reserve(self) -> bool:
        return False

    def is_amm_data_feeds_initialised(self) -> bool:
        return len(self.dex_data_feed_b.price_dict) > 0 and len(self.dex_data_feed_b.price_dict) > 0

    def is_wallet_address_set(self) -> bool:
        raise NotImplementedError

    # TODO: one-leg may fail due to insufficient balance
    def base_buy_a_sell_b(self) -> None:
        self.is_submit_tx_incomplete = True
        trading_pair = self.trading_pair
        pass
        self.is_submit_tx_incomplete = False
        return

    def base_buy_b_sell_a(self) -> None:
        self.is_submit_tx_incomplete = True
        trading_pair = self.trading_pair
        pass
        self.is_submit_tx_incomplete = False
        return
