import logging
import time
from decimal import Decimal
from statistics import mean
from typing import List

import requests

from hummingbot.connector.exchange_base import ExchangeBase
from hummingbot.connector.utils import split_hb_trading_pair
from hummingbot.core.data_type.order_candidate import OrderCandidate
from hummingbot.core.event.events import OrderFilledEvent, OrderType, TradeType
from hummingbot.core.rate_oracle.rate_oracle import RateOracle
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase


class BuyDipExample(ScriptStrategyBase):
    """
    THis strategy buys ETH (with BTC) when the ETH-BTC drops 5% below 50 days moving average (of a previous candle)
    This example demonstrates:
      - How to call Binance REST API for candle stick data
      - How to incorporate external pricing source (Coingecko) into the strategy
      - How to listen to order filled event
      - How to structure order execution on a more complex strategy
    Before running this example, make sure you run `config rate_oracle_source coingecko`
    """
    connector_name: str = "binance_paper_trade"
    trading_pair: str = "ETH-BTC"
    base_asset, quote_asset = split_hb_trading_pair(trading_pair)
    conversion_pair: str = f"{quote_asset}-USD"
    buy_usd_amount: Decimal = Decimal("100")
    moving_avg_period: int = 50
    dip_percentage: Decimal = Decimal("0.05")
    #: A cool off period before the next buy (in seconds)
    cool_off_interval: float = 10.
    #: The last buy timestamp
    last_ordered_ts: float = 0.

    markets = {connector_name: {trading_pair}}

    @property
    def connector(self) -> ExchangeBase:
        """
        The only connector in this strategy, define it here for easy access
        """
        return self.connectors[self.connector_name]

    def on_tick(self):
        """
        Runs every tick_size seconds, this is the main operation of the strategy.
        - Create proposal (a list of order candidates)
        - Check the account balance and adjust the proposal accordingly (lower order amount if needed)
        - Lastly, execute the proposal on the exchange
        """
        proposal: List[OrderCandidate] = self.create_proposal()
        proposal = self.connector.budget_checker.adjust_candidates(proposal, all_or_none=False)
        if proposal:
            self.execute_proposal(proposal)

    def create_proposal(self) -> List[OrderCandidate]:
        """
        Creates and returns a proposal (a list of order candidate), in this strategy the list has 1 element at most.
        """
        daily_closes = self._get_daily_close_list(self.trading_pair)
        start_index = (-1 * self.moving_avg_period) - 1
        # Calculate the average of the 50 element prior to the last element
        avg_close = mean(daily_closes[start_index:-1])
        proposal = []
        # If the current price (the last close) is below the dip, add a new order candidate to the proposal
        if daily_closes[-1] < avg_close * (Decimal("1") - self.dip_percentage):
            order_price = self.connector.get_price(self.trading_pair, False) * Decimal("0.9")
            usd_conversion_rate = RateOracle.get_instance().get_pair_rate(self.conversion_pair)
            amount = (self.buy_usd_amount / usd_conversion_rate) / order_price
            proposal.append(OrderCandidate(self.trading_pair, False, OrderType.LIMIT, TradeType.BUY, amount,
                                           order_price))
        return proposal

    def execute_proposal(self, proposal: List[OrderCandidate]):
        """
        Places the order candidates on the exchange, if it is not within cool off period and order candidate is valid.
        """
        if self.last_ordered_ts > time.time() - self.cool_off_interval:
            return
        for order_candidate in proposal:
            if order_candidate.amount > Decimal("0"):
                self.buy(self.connector_name, self.trading_pair, order_candidate.amount, order_candidate.order_type,
                         order_candidate.price)
                self.last_ordered_ts = time.time()

    def did_fill_order(self, event: OrderFilledEvent):
        """
        Listens to fill order event to log it and notify the hummingbot application.
        If you set up Telegram bot, you will get notification there as well.
        """
        msg = (f"({event.trading_pair}) {event.trade_type.name} order (price: {event.price}) of {event.amount} "
               f"{split_hb_trading_pair(event.trading_pair)[0]} is filled.")
        self.log_with_clock(logging.INFO, msg)
        self.notify_hb_app_with_timestamp(msg)

    def _get_daily_close_list(self, trading_pair: str) -> List[Decimal]:
        """
        Fetches binance candle stick data and returns a list daily close
        This is the API response data structure:
        [
          [
            1499040000000,      // Open time
            "0.01634790",       // Open
            "0.80000000",       // High
            "0.01575800",       // Low
            "0.01577100",       // Close
            "148976.11427815",  // Volume
            1499644799999,      // Close time
            "2434.19055334",    // Quote asset volume
            308,                // Number of trades
            "1756.87402397",    // Taker buy base asset volume
            "28.46694368",      // Taker buy quote asset volume
            "17928899.62484339" // Ignore.
          ]
        ]

        :param trading_pair: A market trading pair to

        :return: A list of daily close
        """

        url = "https://api.binance.com/api/v3/klines"
        params = {"symbol": trading_pair.replace("-", ""),
                  "interval": "1d"}
        records = requests.get(url=url, params=params).json()
        return [Decimal(str(record[4])) for record in records]
