from typing import Dict, Optional

from hummingbot.connector.connector_base import ConnectorBase
from hummingbot.core.data_type.common import TradeType
from hummingbot.core.gateway.gateway_http_client import GatewayHttpClient
from hummingbot.core.gateway.types import Transaction
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.data_feed.amm_data_feed import AmmDataFeed
from hummingbot.data_feed.balance_data_feed import BalanceDataFeed
from hummingbot.data_feed.utils import split_base_quote
from hummingbot.strategy.script_strategy_base import Decimal, ScriptStrategyBase

UNKNONW = -1


class SlippagePriceError(Exception):
    pass


class CrossDexArb(ScriptStrategyBase):
    # define markets
    chain = "binance-smart-chain"
    network = "mainnet"
    connector_a = "pancakeswap"
    connector_b = "sushiswap"
    connector_chain_network_a = f"{connector_a}_{chain}_{network}"
    connector_chain_network_b = f"{connector_b}_{chain}_{network}"
    trading_pair = "USDT-WBNB"
    markets = {
        connector_chain_network_a: {trading_pair},
        connector_chain_network_b: {trading_pair},
    }

    # set up data feed for 2 DEXs
    dex_update_interval = 0.0
    order_amount_in_base: Decimal = Decimal("50")
    dex_data_feed_a = AmmDataFeed(
        connector_chain_network_a,
        {trading_pair},
        order_amount_in_base,
        dex_update_interval,
    )
    dex_data_feed_b = AmmDataFeed(
        connector_chain_network_b,
        {trading_pair},
        order_amount_in_base,
        dex_update_interval,
    )

    # set up data feed for wallet balances
    balance_update_interval = 5.0
    balance_data_feed = BalanceDataFeed([chain], network, {trading_pair}, balance_update_interval)

    # for execute trade
    gateway_client = GatewayHttpClient.get_instance()
    gas_token = "BNB"
    min_gas_fee_reserve = Decimal("0.001")
    min_profit_bp = 10
    is_submit_tx_incomplete = False
    is_poll_tx_incomplete = False
    transaction_a: Optional[Transaction] = None
    transaction_b: Optional[Transaction] = None
    last_trade_timestamp: int = UNKNONW

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
        if not self.is_precheck():
            return

        if self.is_transactions_in_progress():
            safe_ensure_future(self.poll_transaction_status())
        elif self.transaction_a is None and self.transaction_b is None:
            safe_ensure_future(self.decide_trade())
        else:
            self.logger().warning(
                f"Either transaction_a ({self.transaction_a}) "
                f"or transaction_b ({self.transaction_b}) is None."
                "This should not happen. Please review the code!"
            )
        return

    def is_precheck(self) -> bool:
        _is_precheck = False
        if not self.is_wallet_address_set():
            self.logger().warning(
                "Wallet address is not found. " "Please check if your wallet is connected to Gateway!"
            )
        elif not self.is_amm_data_feeds_ready():
            self.logger().info(f"AmmDataFeeds are NOT ready. Skip this on_tick.")
        elif not self.is_balance_data_feed_ready():
            self.logger().info(f"BalanceDataFeed is NOT ready. Skip this on_tick.")
        elif not self.is_balance_updated_after_last_trade():
            self.logger().info(f"Balance is not yet updated after last trade. Skip this on_tick.")
        elif self.is_out_of_gas_fee_reserve():
            self.logger().warning(f"Gas token: {self.gas_token} is running out. " "Please manually top up!")
        elif self.is_submit_tx_incomplete:
            self.logger().info("Submit AMM trade requests are in progress. Skip this on_tick")
        elif self.is_poll_tx_incomplete:
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
            _is_precheck = True
        return _is_precheck

    async def poll_transaction_status(self) -> None:
        self.transaction_a = None
        self.transaction_b = None
        raise NotImplementedError

    async def decide_trade(self) -> None:
        # TODO: handle the case when one-leg fail
        # e.g. insufficient balance on 1 leg/ slippage limit succeeded
        if self.should_base_buy_a_sell_b():
            if self.is_enough_balance_for_trade(buy_exchange=self.connector_a, sell_exchange=self.connector_b):
                self.base_buy_a_sell_b()
            else:
                self.logger().warning(f"Insufficient balance for trade. Skip this on_tick.")
        elif self.should_base_buy_b_sell_a():
            if self.is_enough_balance_for_trade(buy_exchange=self.connector_b, sell_exchange=self.connector_a):
                self.base_buy_b_sell_a()
            else:
                self.logger().warning(f"Insufficient balance for trade. Skip this on_tick.")
        return

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

    def base_buy_a_sell_b(self) -> None:
        self.is_submit_tx_incomplete = True
        trading_pair = self.trading_pair
        pass
        self.is_submit_tx_incomplete = False
        raise NotImplementedError

    def base_buy_b_sell_a(self) -> None:
        self.is_submit_tx_incomplete = True
        trading_pair = self.trading_pair
        pass
        self.is_submit_tx_incomplete = False
        raise NotImplementedError

    def is_enough_balance_for_trade(self, buy_exchange: str, sell_exchange: str) -> bool:
        buy_side_data_feed = self.dex_data_feed_a if buy_exchange == self.connector_a else self.dex_data_feed_b
        sell_side_data_feed = self.dex_data_feed_a if sell_exchange == self.connector_a else self.dex_data_feed_b
        assert (
            buy_side_data_feed is not sell_side_data_feed
        ), "buy_side_data_feed should not be the same as sell_side_data_feed."
        base, quote = split_base_quote(self.trading_pair)
        base_required = float(sell_side_data_feed.price_dict[self.trading_pair].sell.amount)
        is_base_enough = float(self.balance_data_feed.balances[self.chain][base]) >= base_required
        quote_required = float(buy_side_data_feed.price_dict[self.trading_pair].buy.expectedAmount)
        is_quote_enough = float(self.balance_data_feed.balances[self.chain][quote]) >= quote_required
        return is_quote_enough and is_base_enough

    def is_balance_updated_after_last_trade(self) -> bool:
        return self.balance_data_feed.balances[self.chain].timestamp > self.last_trade_timestamp

    def is_out_of_balance(self) -> bool:
        raise NotImplementedError

    def is_out_of_gas_fee_reserve(self) -> bool:
        return float(self.balance_data_feed.balances[self.chain].balances[self.gas_token]) > self.min_gas_fee_reserve

    def is_amm_data_feeds_ready(self) -> bool:
        return self.dex_data_feed_a.is_ready() and self.dex_data_feed_b.is_ready()

    def is_balance_data_feed_ready(self) -> bool:
        return self.balance_data_feed.is_ready()

    def is_wallet_address_set(self) -> bool:
        return self.balance_data_feed.is_wallet_address_set

    def is_transactions_in_progress(self) -> bool:
        return self.transaction_a is not None and self.transaction_b is not None
