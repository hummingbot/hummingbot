from decimal import Decimal
import time
import logging
import asyncio
import pandas as pd
from hummingbot.core.clock import Clock
from hummingbot.logger import HummingbotLogger
from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple
from hummingbot.strategy.strategy_py_base import StrategyPyBase
from hummingbot.connector.connector_base import ConnectorBase
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.core.data_type.limit_order import LimitOrder
from hummingbot.core.data_type.market_order import MarketOrder
from typing import (
    Dict,
    List,
    Tuple,
)

ulp_logger = None


class UniswapV3LpStrategy(StrategyPyBase):

    @classmethod
    def logger(cls) -> HummingbotLogger:
        global ulp_logger
        if ulp_logger is None:
            ulp_logger = logging.getLogger(__name__)
        return ulp_logger

    def __init__(self,
                 market_info: MarketTradingPairTuple,
                 fee_tier: str,
                 buy_position_spread: Decimal,
                 sell_position_spread: Decimal,
                 buy_position_price_spread: Decimal,
                 sell_position_price_spread: Decimal,
                 token_amount: Decimal,
                 status_report_interval: float = 900):
        super().__init__()
        self._market_info = market_info
        self._fee_tier = fee_tier
        self._buy_position_spread = buy_position_spread
        self._sell_position_spread = sell_position_spread
        self._buy_position_price_spread = buy_position_price_spread
        self._sell_position_price_spread = sell_position_price_spread
        self._token_amount = token_amount

        self._ev_loop = asyncio.get_event_loop()
        self._last_timestamp = 0
        self._status_report_interval = status_report_interval
        self.add_markets([market_info.market])
        self._connector_ready = False
        self._session_positions = []
        self._last_price = Decimal("0")
        self._pending_execution_completion = 0
        self._pending_swap_completion = False
        self._main_task = None
        self._range_order_ids = []

    @property
    def base_asset(self):
        return self._market_info.base_asset

    @property
    def quote_asset(self):
        return self._market_info.quote_asset

    @property
    def trading_pair(self):
        return self._market_info.trading_pair

    @property
    def market_info_to_active_positions(self) -> Dict[MarketTradingPairTuple, List[LimitOrder]]:
        return self._sb_order_tracker.market_pair_to_active_orders

    @property
    def active_positions(self) -> List[LimitOrder]:
        if self._market_info not in self.market_info_to_active_positions:
            return []
        return self.market_info_to_active_positions[self._market_info]

    @property
    def active_buys(self) -> List[LimitOrder]:  # only one active buy position for the first iteration of this strategy
        return [o for o in self.active_positions if o.is_buy and o.client_order_id in self._range_order_ids]

    @property
    def active_sells(self) -> List[LimitOrder]:  # only one active sell position for the first iteration of this strategy
        return [o for o in self.active_positions if not o.is_buy and o.client_order_id in self._range_order_ids]

    async def get_current_price(self) -> float:
        return await self._market_info.market.get_price_by_fee_tier(self.trading_pair, self._fee_tier)

    def active_positions_df(self) -> pd.DataFrame:
        columns = ["Symbol", "Type", "Fee Tier", "Amount", "Upper Price", "Lower Price"]
        data = []
        if len(self.active_buys) > 0:
            data.append([
                self.trading_pair,
                "Buy",
                self._fee_tier,
                self.active_buys[0].quantity,
                self.active_buys[0].price * (Decimal("1") + self._buy_position_price_spread),
                self.active_buys[0].price
            ])
        if len(self.active_sells) > 0:
            data.append([
                self.trading_pair,
                "Sell",
                self._fee_tier,
                self.active_sells[0].quantity,
                self.active_sells[0].price,
                self.active_sells[0].price * (Decimal("1") - self._sell_position_price_spread)
            ])

        return pd.DataFrame(data=data, columns=columns)

    async def format_status(self) -> str:
        """
        Returns a status string formatted to display nicely on terminal. The strings composes of 4 parts: market,
        assets, spread and warnings(if any).
        """
        if not self._connector_ready:
            return "UniswapV3 connector not ready."

        columns = ["Exchange", "Market", "Current Price"]
        data = []
        market, trading_pair, base_asset, quote_asset = self._market_info
        data.append([
            market.display_name,
            trading_pair,
            float(self._last_price)
        ])
        markets_df = pd.DataFrame(data=data, columns=columns)
        lines = []
        lines.extend(["", "  Markets:"] + ["    " + line for line in markets_df.to_string(index=False).split("\n")])

        # See if there're any active positions.
        if (len(self.active_buys) + len(self.active_sells)) > 0:
            df = self.active_positions_df()
            lines.extend(["", "  Positions:"] + ["    " + line for line in df.to_string(index=False).split("\n")])
        else:
            lines.extend(["", "  No active positions."])

        assets_df = self.wallet_balance_data_frame([self._market_info])
        lines.extend(["", "  Assets:"] +
                     ["    " + line for line in str(assets_df).split("\n")])

        warning_lines = self.network_warning([self._market_info])
        warning_lines.extend(self.balance_warning([self._market_info]))
        if len(warning_lines) > 0:
            lines.extend(["", "*** WARNINGS ***"] + warning_lines)

        return "\n".join(lines)

    def tick(self, timestamp: float):
        """
        Clock tick entry point, is run every second (on normal tick setting).
        :param timestamp: current tick timestamp
        """
        if not self._connector_ready:
            self._connector_ready = self._market_info.market.ready
            if not self._connector_ready:
                self.logger().warning("Uniswap v3 connector is not ready. Please wait...")
                return
            else:
                self.logger().info("Uniswap v3 connector is ready. Trading started.")
        if self._main_task is None or self._main_task.done():
            self._main_task = safe_ensure_future(self.main())

    async def main(self):
        if self._pending_execution_completion == 0:
            proposal = await self.propose_position_creation_and_removal()
            if len(proposal) > 0:
                await self.execute_proposal(proposal)

    def generate_proposal(self, is_buy):
        if is_buy:
            upper_price = (Decimal("1") - self._buy_position_spread) * self._last_price
            lower_price = (Decimal("1") - self._buy_position_spread - self._buy_position_price_spread) * self._last_price
        else:
            lower_price = (Decimal("1") + self._sell_position_spread) * self._last_price
            upper_price = (Decimal("1") + self._sell_position_spread + self._sell_position_price_spread) * self._last_price
        return [lower_price, upper_price]

    async def propose_position_creation_and_removal(self):
        buy_prices = sell_prices = []  # [lower_price, upper_price, token_id(to be removed)]
        current_price = await self.get_current_price()
        if self._last_price != current_price:
            self._last_price = current_price
            if len(self.active_buys) == 0 and len(self.active_sells) == 0:
                buy_prices = self.generate_proposal(True)
                sell_prices = self.generate_proposal(False)
                buy_prices.append(0)
                sell_prices.append(0)
            elif self.active_buys[0].price > current_price:
                buy_prices = self.generate_proposal(True)
                token_id = self._market_info.market.get_token_id(self.active_sells[0].client_order_id)
                buy_prices.append(token_id)
            elif self.active_sells[0].price < current_price:
                sell_prices = self.generate_proposal(False)
                token_id = self._market_info.market.get_token_id(self.active_buys[0].client_order_id)
                sell_prices.append(token_id)
        return [buy_prices, sell_prices]

    async def execute_proposal(self, proposal):
        if self._pending_swap_completion <= time.time():
            if len(proposal[0]) > 0:
                if proposal[0][-1] != 0:
                    if self._market_info.market.get_available_balance(self.base_asset) >= self._token_amount:
                        self.logger().info(f"Cancelling position with ID - {proposal[0][-1]} and "
                                           f" creating new buy position over {proposal[0][0]}"
                                           f" to {proposal[0][1]}.")
                        order_id = await self._market_info.market.replace_position(proposal[0][-1],
                                                                                   self.trading_pair,
                                                                                   self._fee_tier,
                                                                                   self._token_amount,
                                                                                   self._token_amount * self._last_price,
                                                                                   proposal[0][0],
                                                                                   proposal[0][1])
                        self.start_tracking_limit_order(self._market_info, order_id, True, proposal[0][0], self._token_amount * self._last_price)
                        self._range_order_ids.append(order_id)
                        self._pending_execution_completion += 1
                    else:
                        self.logger().info(f"Cancelling position with ID - {proposal[1][-1]}")
                        self._market_info.market.remove_position(self.active_sells[0].client_order_id, proposal[0][-1])  # no need to track position removal at strategy level.
                        self.log_with_clock(logging.INFO,
                                            f"Executing sell order for {self._token_amount * self._last_price} {self._market_info.quote_asset} "
                                            f"at {self._last_price} price")
                        self.sell_with_specific_market(self._market_info,
                                                       self._token_amount,
                                                       self._market_info.market.get_taker_order_type(),
                                                       self._last_price,
                                                       )
                        self._pending_swap_completion = time.time() + 13  # wait for about 13 secs in order to give enough time for swap to complete
                else:
                    self.logger().info(f"Creating new buy position over {proposal[0][0]}"
                                       f" to {proposal[0][1]}.")
                    order_id = self._market_info.market.add_position(self.trading_pair,
                                                                     self._fee_tier,
                                                                     self._token_amount,
                                                                     self._token_amount * self._last_price,
                                                                     proposal[0][0],
                                                                     proposal[0][1])
                    self.start_tracking_limit_order(self._market_info, order_id, True, proposal[0][0], self._token_amount * self._last_price)
                    self._range_order_ids.append(order_id)
                    self._pending_execution_completion += 1
            if len(proposal[1]) > 0:
                if proposal[1][-1] != 0:
                    if self._market_info.market.get_available_balance(self.quote_asset) >= (self._token_amount * self._last_price):
                        self.logger().info(f"Cancelling position with ID - {proposal[1][-1]} and "
                                           f" creating new sell position over {proposal[1][0]}"
                                           f" to {proposal[1][1]}.")
                        order_id = self._market_info.market.replace_position(proposal[1][-1],
                                                                             self.trading_pair,
                                                                             self._fee_tier,
                                                                             self._token_amount,
                                                                             self._token_amount * self._last_price,
                                                                             proposal[1][0],
                                                                             proposal[1][1])
                        self.start_tracking_limit_order(self._market_info, order_id, False, proposal[1][1], self._token_amount)
                        self._range_order_ids.append(order_id)
                        self._pending_execution_completion += 1

                    else:
                        self.logger().info(f"Cancelling position with ID - {proposal[1][-1]}")
                        self._market_info.market.remove_position(self.active_buys[0].client_order_id, proposal[1][-1])  # no need to track position removal at strategy level.
                        self.log_with_clock(logging.INFO,
                                            f"Executing buy order for {self._token_amount} {self._market_info.base_asset} "
                                            f"at {self._last_price} price")
                        self.buy_with_specific_market(self._market_info,
                                                      self._token_amount,
                                                      self._market_info.market.get_taker_order_type(),
                                                      self._last_price,
                                                      )
                        self._pending_swap_completion = time.time() + 13  # wait for about 13 secs in order to give enough time for swap to complete
                else:
                    self.logger().info(f"Creating new sell position over {proposal[1][0]}"
                                       f" to {proposal[1][1]}.")
                    order_id = self._market_info.market.add_position(self.trading_pair,
                                                                     self._fee_tier,
                                                                     self._token_amount,
                                                                     self._token_amount * self._last_price,
                                                                     proposal[1][0],
                                                                     proposal[1][1])
                    self.start_tracking_limit_order(self._market_info, order_id, False, proposal[1][1], self._token_amount)
                    self._range_order_ids.append(order_id)
                    self._pending_execution_completion += 1

    def did_create_range_position_order(self, create_event):
        self._pending_execution_completion -= 1

    def did_remove_range_position_order(self, close_event):
        # we only stop tracking range orders at this point
        self.stop_tracking_limit_order(self._market_info, close_event.hb_id)
        if close_event.hb_id in self._range_order_ids:
            self._range_order_ids.remove(close_event.hb_id)
            self._pending_execution_completion -= 1

    @property
    def tracked_limit_orders(self) -> List[Tuple[ConnectorBase, LimitOrder]]:
        return self._sb_order_tracker.tracked_limit_orders

    @property
    def tracked_market_orders(self) -> List[Tuple[ConnectorBase, MarketOrder]]:
        return self._sb_order_tracker.tracked_market_orders

    def start(self, clock: Clock, timestamp: float):
        # Restore all positions ever created by user and filter those related to current market
        # restored_order_ids = self.track_restored_orders(self._market_info)
        # self.logger().info(f"Restored positions with the following client Ids - {restored_order_ids}")
        return

    def stop(self, clock: Clock):
        if self._main_task is not None:
            self._main_task.cancel()
            self._main_task = None
