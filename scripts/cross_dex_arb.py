import asyncio
from typing import Dict, Optional

import pandas as pd

from hummingbot.connector.connector_base import ConnectorBase  # type: ignore
from hummingbot.core.data_type.common import TradeType
from hummingbot.core.gateway.gateway_http_client import GatewayHttpClient
from hummingbot.core.gateway.types import Transaction, TransactionStatus
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.data_feed.amm_data_feed import AmmDataFeed
from hummingbot.data_feed.balance_data_feed import BalanceDataFeed
from hummingbot.data_feed.utils import split_base_quote
from hummingbot.strategy.script_strategy_base import Decimal, ScriptStrategyBase

UNKNOWN_TIMESTAMP: int = -1
TRANSACTION_COMPLETED: int = 1


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
    base = "USDT"
    quote = "WBNB"
    gas_token = "BNB"
    trading_pair = f"{base}-{quote}"
    markets = {
        connector_chain_network_a: {trading_pair},
        connector_chain_network_b: {trading_pair},
    }

    # set up data feed for 2 DEXs
    price_update_interval = 0.0
    order_amount_in_base: Decimal = Decimal("50")
    amm_data_feed_a = AmmDataFeed(
        connector_chain_network_a,
        {trading_pair},
        order_amount_in_base,
        price_update_interval,
    )
    amm_data_feed_b = AmmDataFeed(
        connector_chain_network_b,
        {trading_pair},
        order_amount_in_base,
        price_update_interval,
    )

    # set up data feed for wallet balances on a single chain
    balance_update_interval = 5.0
    balance_data_feed = BalanceDataFeed([chain], network, {base, quote, gas_token}, balance_update_interval)

    # param for execute trade
    gateway_client = GatewayHttpClient.get_instance()
    min_gas_fee_reserve = Decimal("0.001")
    min_profit_bp = 10
    slippage_tolerance = 0.05
    is_submit_tx_incomplete = False
    is_poll_tx_incomplete = False

    # state for trade execution
    transaction_a: Optional[Transaction] = None
    transaction_b: Optional[Transaction] = None
    last_trade_timestamp: int = UNKNOWN_TIMESTAMP

    def __init__(self, connectors: Dict[str, ConnectorBase]) -> None:
        super().__init__(connectors)
        self.amm_data_feed_a.start()
        self.amm_data_feed_b.start()
        self.balance_data_feed.start()
        self.logger().info(f"{self.amm_data_feed_a.name}, {self.amm_data_feed_b.name} and BalanceDataFeed started...")

    def on_stop(self) -> None:
        self.amm_data_feed_a.stop()
        self.amm_data_feed_b.stop()
        self.balance_data_feed.stop()
        self.logger().info(
            f"{self.amm_data_feed_a.name}, {self.amm_data_feed_b.name} amd BalanceDataFeed terminated..."
        )
        return

    def format_status(self) -> str:
        if not self.ready_to_trade:
            return "Market Connectors are not ready"

        if not self.is_amm_data_feeds_ready():
            return "AmmDataFeeds are not ready."

        lines = []

        # header
        chain = self.amm_data_feed_a.chain
        network = self.amm_data_feed_a.network
        lines.extend(["", f"Chain: {chain}", f"Network: {network}", "", ""])

        # metrics for buy base in exchange a and sell base in exchange b
        buy_a_sell_b_profit_pb = self._compute_arb_profit_pb(
            trading_pair=self.trading_pair,
            buy_data_feed=self.amm_data_feed_a,
            sell_data_feed=self.amm_data_feed_b,
        )
        lines.extend(["", f"Profit (Pb): {buy_a_sell_b_profit_pb:.0f}"])
        buy_a_sell_b_df = self._get_arb_monitor_df(
            self.trading_pair,
            buy_data_feed=self.amm_data_feed_a,
            sell_data_feed=self.amm_data_feed_b,
        )
        lines.extend([""] + ["    " + line for line in buy_a_sell_b_df.to_string(index=False).split("\n")])

        # metrics for buy base in exchange b and sell base in exchange a
        lines.extend(["", ""])
        buy_b_sell_a_profit_pb = self._compute_arb_profit_pb(
            trading_pair=self.trading_pair,
            buy_data_feed=self.amm_data_feed_b,
            sell_data_feed=self.amm_data_feed_a,
        )
        lines.extend(["", f"Profit (Pb): {buy_b_sell_a_profit_pb:.0f}"])
        buy_b_sell_a_df = self._get_arb_monitor_df(
            self.trading_pair,
            buy_data_feed=self.amm_data_feed_b,
            sell_data_feed=self.amm_data_feed_a,
        )
        lines.extend([""] + ["    " + line for line in buy_b_sell_a_df.to_string(index=False).split("\n")])
        return "\n".join(lines)

    def _get_arb_monitor_df(
        self, trading_pair: str, buy_data_feed: AmmDataFeed, sell_data_feed: AmmDataFeed
    ) -> pd.DataFrame:
        buy_price_response = buy_data_feed.price_dict[trading_pair].buy
        sell_price_response = sell_data_feed.price_dict[trading_pair].sell
        buy_dict = {
            "timestamp": buy_price_response.timestamp,
            "connector": buy_data_feed.connector,
            "base": buy_data_feed.price_dict[trading_pair].base,
            "quote": buy_data_feed.price_dict[trading_pair].quote,
            "trade_type": "BUY",
            "order_amount_in_base": buy_data_feed.order_amount_in_base,
            "expected_amount": buy_price_response.expectedAmount,
            "price": buy_price_response.price,
            "gas_token": buy_price_response.gasPriceToken,
            "gas_fee": buy_price_response.gasCost,
        }
        sell_dict = {
            "timestamp": sell_price_response.timestamp,
            "connector": sell_data_feed.connector,
            "base": sell_data_feed.price_dict[trading_pair].base,
            "quote": sell_data_feed.price_dict[trading_pair].quote,
            "trade_type": "SELL",
            "order_amount_in_base": sell_data_feed.order_amount_in_base,
            "expected_amount": sell_price_response.expectedAmount,
            "price": sell_price_response.price,
            "gas_token": buy_price_response.gasPriceToken,
            "gas_fee": buy_price_response.gasCost,
        }
        ordered_cols = [
            "timestamp",
            "connector",
            "base",
            "quote",
            "trade_type",
            "order_amount_in_base",
            "expected_amount",
            "price",
            "gas_token",
            "gas_fee",
        ]
        df = pd.DataFrame([buy_dict, sell_dict])[ordered_cols]
        return df

    def on_tick(self) -> None:
        if not self.is_precheck():
            return

        if self.is_transactions_in_progress():
            safe_ensure_future(self.reset_state_if_transactions_complete())  # type: ignore
        elif self.is_bot_idle():
            safe_ensure_future(self.decide_and_trade())  # type: ignore
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

    # TODO: how to get executed price and amounted received?
    async def reset_state_if_transactions_complete(self) -> None:
        assert self.transaction_a and self.transaction_b, "transaction_a and transaction_b should not be None."
        self.is_poll_tx_incomplete = True
        tx_hash_a = self.transaction_a.txHash
        tx_hash_b = self.transaction_b.txHash
        tx_status_a_task = asyncio.create_task(self._poll_transaction_status(tx_hash_a))
        tx_status_b_task = asyncio.create_task(self._poll_transaction_status(tx_hash_b))
        tx_status_a = await tx_status_a_task
        tx_status_b = await tx_status_b_task
        if tx_status_a.txStatus == TRANSACTION_COMPLETED and tx_status_b.txStatus == TRANSACTION_COMPLETED:
            self.logger().info(
                f"Both transactions ({tx_hash_a} and {tx_hash_b}) are completed. "
                "Reset self.transaction_a and self.transaction_b and update self.last_trade_timestamp."
            )
            last_trade_timestamp = max(tx_status_a.timestamp, tx_status_b.timestamp)
            self.last_trade_timestamp = last_trade_timestamp
            self.transaction_a = None
            self.transaction_b = None
        self.is_poll_tx_incomplete = False
        return

    async def decide_and_trade(self) -> None:
        # TODO: handle the case when one-leg fail
        # e.g. insufficient balance on 1 leg/ slippage limit succeeded
        if self.should_base_buy_a_sell_b():
            if self.is_enough_balance_for_trade(buy_exchange=self.connector_a, sell_exchange=self.connector_b):
                await self.base_buy_a_sell_b()
            else:
                self.logger().warning(f"Insufficient balance for trade. Skip this on_tick.")
        elif self.should_base_buy_b_sell_a():
            if self.is_enough_balance_for_trade(buy_exchange=self.connector_b, sell_exchange=self.connector_a):
                await self.base_buy_b_sell_a()
            else:
                self.logger().warning(f"Insufficient balance for trade. Skip this on_tick.")
        return

    # TODO: now assume gas fee and quote token is in same currency (i.e. WBNB & BNB)
    def should_base_buy_a_sell_b(self) -> bool:
        profit_pb = self._compute_arb_profit_pb(
            self.trading_pair,
            buy_data_feed=self.amm_data_feed_a,
            sell_data_feed=self.amm_data_feed_b,
        )
        return profit_pb >= self.min_profit_bp

    def should_base_buy_b_sell_a(self) -> bool:
        profit_pb = self._compute_arb_profit_pb(
            self.trading_pair,
            buy_data_feed=self.amm_data_feed_b,
            sell_data_feed=self.amm_data_feed_a,
        )
        return profit_pb >= self.min_profit_bp

    async def base_buy_a_sell_b(self) -> None:
        assert self.balance_data_feed.wallet_address is not None, "wallet_address should not be None."
        self.is_submit_tx_incomplete = True
        await self._trade_two_legs(
            self.trading_pair,
            buy_data_feed=self.amm_data_feed_a,
            sell_data_feed=self.amm_data_feed_b,
            slippage_tolerance=self.slippage_tolerance,
        )
        self.is_submit_tx_incomplete = False
        return

    async def base_buy_b_sell_a(self) -> None:
        self.is_submit_tx_incomplete = True
        await self._trade_two_legs(
            self.trading_pair,
            buy_data_feed=self.amm_data_feed_b,
            sell_data_feed=self.amm_data_feed_a,
            slippage_tolerance=self.slippage_tolerance,
        )
        self.is_submit_tx_incomplete = False
        return

    def _compute_arb_profit_pb(
        self, trading_pair: str, buy_data_feed: AmmDataFeed, sell_data_feed: AmmDataFeed
    ) -> float:
        quote_amount_out = float(buy_data_feed.price_dict[trading_pair].buy.expectedAmount)
        buy_gas_fee = float(buy_data_feed.price_dict[trading_pair].buy.gasCost)
        quote_amount_in = float(sell_data_feed.price_dict[trading_pair].sell.expectedAmount)
        sell_gas_fee = float(sell_data_feed.price_dict[trading_pair].sell.gasCost)
        profit_pb = (quote_amount_in - quote_amount_out - buy_gas_fee - sell_gas_fee) / quote_amount_in * 10000
        return profit_pb

    async def _poll_transaction_status(self, transaction_hash: str) -> TransactionStatus:
        transaction_status = await self.gateway_client.get_transaction_status(
            self.chain, self.network, transaction_hash
        )
        return TransactionStatus(**transaction_status)

    async def _trade_two_legs(
        self,
        trading_pair: str,
        buy_data_feed: AmmDataFeed,
        sell_data_feed: AmmDataFeed,
        slippage_tolerance: float,
    ) -> None:
        assert self.balance_data_feed.wallet_address is not None, "wallet_address should not be None."
        base, quote = split_base_quote(trading_pair)
        buy_price_slippage_limit = float(buy_data_feed.price_dict[trading_pair].buy.price) * (1 + slippage_tolerance)
        buy_base_in_b_task = asyncio.create_task(
            self.gateway_client.amm_trade(
                self.chain,
                self.network,
                buy_data_feed.connector,
                self.balance_data_feed.wallet_address,
                base,
                quote,
                TradeType.BUY,
                self.order_amount,
                Decimal(buy_price_slippage_limit),
            )
        )
        sell_price_slippage_limit = float(sell_data_feed.price_dict[trading_pair].sell.price) * (1 - slippage_tolerance)
        sell_base_in_a_task = asyncio.create_task(
            self.gateway_client.amm_trade(
                self.chain,
                self.network,
                sell_data_feed.connector,
                self.balance_data_feed.wallet_address,
                base,
                quote,
                TradeType.SELL,
                self.order_amount,
                Decimal(sell_price_slippage_limit),
            )
        )
        transaction_a = await sell_base_in_a_task
        transaction_b = await buy_base_in_b_task
        self.transaction_a = Transaction(**transaction_a)
        self.transaction_b = Transaction(**transaction_b)

        expected_buy_quote_amount = float(buy_data_feed.price_dict[trading_pair].buy.expectedAmount)
        expected_sell_quote_amount = float(sell_data_feed.price_dict[trading_pair].sell.expectedAmount)
        self.logger().info(
            f"Submitted sell order for {self.order_amount_in_base} of {base} token in {sell_data_feed.connector} at slippage limit of {sell_price_slippage_limit:.5f}. "
            f"Expected receive {expected_buy_quote_amount:.5f} of {quote} token.\n"
            f"Submitted buy order for {self.order_amount_in_base} of {base} token in {buy_data_feed.connector} at slippage limit of {buy_price_slippage_limit:.5f}. "
            f"Expected spend {expected_sell_quote_amount:.5f} of {quote} token."
        )
        return

    def is_bot_idle(self) -> bool:
        return self.transaction_a is None and self.transaction_b is None

    def is_enough_balance_for_trade(self, buy_exchange: str, sell_exchange: str) -> bool:
        buy_side_data_feed = self.amm_data_feed_a if buy_exchange == self.connector_a else self.amm_data_feed_b
        sell_side_data_feed = self.amm_data_feed_a if sell_exchange == self.connector_a else self.amm_data_feed_b
        assert (
            buy_side_data_feed is not sell_side_data_feed
        ), "buy_side_data_feed should not be the same as sell_side_data_feed."
        base, quote = split_base_quote(self.trading_pair)
        base_required = float(sell_side_data_feed.price_dict[self.trading_pair].sell.amount)
        is_base_enough = float(self.balance_data_feed.balances[self.chain].balances[base]) >= base_required
        quote_required = float(buy_side_data_feed.price_dict[self.trading_pair].buy.expectedAmount)
        is_quote_enough = float(self.balance_data_feed.balances[self.chain].balances[quote]) >= quote_required
        return is_quote_enough and is_base_enough

    def is_balance_updated_after_last_trade(self) -> bool:
        return self.balance_data_feed.balances[self.chain].timestamp > self.last_trade_timestamp

    def is_out_of_gas_fee_reserve(self) -> bool:
        return float(self.balance_data_feed.balances[self.chain].balances[self.gas_token]) > self.min_gas_fee_reserve

    def is_amm_data_feeds_ready(self) -> bool:
        return self.amm_data_feed_a.is_ready() and self.amm_data_feed_b.is_ready()

    def is_balance_data_feed_ready(self) -> bool:
        return self.balance_data_feed.is_ready()

    def is_wallet_address_set(self) -> bool:
        return self.balance_data_feed.is_wallet_address_set

    def is_transactions_in_progress(self) -> bool:
        return self.transaction_a is not None and self.transaction_b is not None
