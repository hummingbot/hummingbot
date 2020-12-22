from decimal import Decimal
import logging
import asyncio
import pandas as pd
from typing import List
from hummingbot.core.clock import Clock
from hummingbot.logger import HummingbotLogger
from hummingbot.strategy.strategy_py_base import StrategyPyBase
from hummingbot.connector.exchange_base import ExchangeBase
from hummingbot.client.settings import ETH_WALLET_CONNECTORS
from hummingbot.connector.connector.uniswap.uniswap_connector import UniswapConnector


NaN = float("nan")
s_decimal_zero = Decimal(0)
amm_logger = None


class LiquidityMiningStrategy(StrategyPyBase):
    """
    This is a basic arbitrage strategy which can be used for most types of connectors (CEX, DEX or AMM).
    For a given order amount, the strategy checks both sides of the trade (market_1 and market_2) for arb opportunity.
    If presents, the strategy submits taker orders to both market.
    """

    @classmethod
    def logger(cls) -> HummingbotLogger:
        global amm_logger
        if amm_logger is None:
            amm_logger = logging.getLogger(__name__)
        return amm_logger

    def __init__(self,
                 exchange: ExchangeBase,
                 markets: List[str],
                 initial_spread: Decimal,
                 order_refresh_time: float,
                 order_refresh_tolerance_pct: Decimal,
                 status_report_interval: float = 900):
        super().__init__()
        self._exchange = exchange
        self._markets = markets
        self._initial_spread = initial_spread
        self._order_refresh_time = order_refresh_time
        self._order_refresh_tolerance_pct = order_refresh_tolerance_pct
        self._ev_loop = asyncio.get_event_loop()
        self._last_timestamp = 0
        self._status_report_interval = status_report_interval

    def tick(self, timestamp: float):
        """
        Clock tick entry point, is run every second (on normal tick setting).
        :param timestamp: current tick timestamp
        """
        if not self._all_markets_ready:
            self._all_markets_ready = all([market.ready for market in self.active_markets])
            if not self._all_markets_ready:
                self.logger().warning("Markets are not ready. Please wait...")
                return
            else:
                self.logger().info("Markets are ready. Trading started.")
        if self._create_timestamp <= self._current_timestamp:
            # 1. Create base order proposals
            proposal = self.create_base_proposal()
            # 2. Apply functions that limit numbers of buys and sells proposal
            # self.c_apply_order_levels_modifiers(proposal)
            # 3. Apply functions that modify orders price
            # self.c_apply_order_price_modifiers(proposal)
            # 4. Apply functions that modify orders size
            # self.c_apply_order_size_modifiers(proposal)
            # 5. Apply budget constraint, i.e. can't buy/sell more than what you have.
            # self.c_apply_budget_constraint(proposal)

        self.cancel_active_orders(proposal)
        if self.c_to_create_orders(proposal):
            self.c_execute_orders_proposal(proposal)

        self._last_timestamp = timestamp

    async def format_status(self) -> str:
        """
        Returns a status string formatted to display nicely on terminal. The strings composes of 4 parts: markets,
        assets, profitability and warnings(if any).
        """

        if self._arb_proposals is None:
            return "  The strategy is not ready, please try again later."
        # active_orders = self.market_info_to_active_orders.get(self._market_info, [])
        columns = ["Exchange", "Market", "Sell Price", "Buy Price", "Mid Price"]
        data = []
        for market_info in [self._market_info_1, self._market_info_2]:
            market, trading_pair, base_asset, quote_asset = market_info
            buy_price = await market.get_quote_price(trading_pair, True, self._order_amount)
            sell_price = await market.get_quote_price(trading_pair, False, self._order_amount)
            mid_price = (buy_price + sell_price) / 2
            data.append([
                market.display_name,
                trading_pair,
                float(sell_price),
                float(buy_price),
                float(mid_price)
            ])
        markets_df = pd.DataFrame(data=data, columns=columns)
        lines = []
        lines.extend(["", "  Markets:"] + ["    " + line for line in markets_df.to_string(index=False).split("\n")])

        assets_df = self.wallet_balance_data_frame([self._market_info_1, self._market_info_2])
        lines.extend(["", "  Assets:"] +
                     ["    " + line for line in str(assets_df).split("\n")])

        lines.extend(["", "  Profitability:"] + self.short_proposal_msg(self._arb_proposals))

        warning_lines = self.network_warning([self._market_info_1])
        warning_lines.extend(self.network_warning([self._market_info_2]))
        warning_lines.extend(self.balance_warning([self._market_info_1]))
        warning_lines.extend(self.balance_warning([self._market_info_2]))
        if len(warning_lines) > 0:
            lines.extend(["", "*** WARNINGS ***"] + warning_lines)

        return "\n".join(lines)

    def start(self, clock: Clock, timestamp: float):
        pass

    def stop(self, clock: Clock):
        pass

    async def quote_in_eth_rate_fetch_loop(self):
        while True:
            try:
                if self._market_info_1.market.name in ETH_WALLET_CONNECTORS and \
                        "WETH" not in self._market_info_1.trading_pair.split("-"):
                    self._market_1_quote_eth_rate = await self.request_rate_in_eth(self._market_info_1.quote_asset)
                if self._market_info_2.market.name in ETH_WALLET_CONNECTORS and \
                        "WETH" not in self._market_info_2.trading_pair.split("-"):
                    self._market_2_quote_eth_rate = await self.request_rate_in_eth(self._market_info_2.quote_asset)
                await asyncio.sleep(60 * 5)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                self.logger().error(str(e), exc_info=True)
                self.logger().network("Unexpected error while fetching account updates.",
                                      exc_info=True,
                                      app_warning_msg="Could not fetch balances from Gateway API.")
                await asyncio.sleep(0.5)

    async def request_rate_in_eth(self, quote: str) -> int:
        if self._uniswap is None:
            self._uniswap = UniswapConnector([f"{quote}-WETH"], "", None)
        return await self._uniswap.get_quote_price(f"{quote}-WETH", True, 1)
