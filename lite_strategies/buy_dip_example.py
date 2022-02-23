from decimal import Decimal
from statistics import mean
from typing import List
import aiohttp
import logging
import time

from hummingbot.connector.exchange_base import ExchangeBase
from hummingbot.core.data_type.order_candidate import OrderCandidate
from hummingbot.core.event.events import OrderType, TradeType, OrderFilledEvent
from hummingbot.core.rate_oracle.rate_oracle import RateOracle
from hummingbot.strategy.lite_strategy_base import LiteStrategyBase


class BuyDipExample(LiteStrategyBase):
    """
    THis strategy buys ETH (with BTC) when the ETH-BTC drops 5% below 50 days moving average (of a previous candle)
    This example demonstrates:
      - How to call Binance REST API for candle stick data
      - How to incorporate external pricing source (Coingecko) into the strategy
      - How to structure order execution on a more complex strategy
    Before running this example, make sure you run `config rate_oracle_source coingecko'
    """
    connector_name = "binance_paper_trade"
    trading_pair = "ETH-BTC"
    base_asset, quote_asset = trading_pair.split("-")
    conversion_pair = f"{quote_asset}-USD"
    buy_usd_amount = Decimal("100")
    cool_off_interval = 60. * 60. * 24.
    last_ordered_ts = 0.

    markets = {connector_name: {trading_pair}}
    shared_client: aiohttp.ClientSession = None

    @classmethod
    async def http_client(cls) -> aiohttp.ClientSession:
        if cls.shared_client is None:
            cls.shared_client = aiohttp.ClientSession()
        return cls.shared_client

    @classmethod
    async def get_daily_close_list(cls, trading_pair: str) -> List[Decimal]:
        """
        Fetches binance candle stick data and returns a list daily close
        :param trading_pair: A market trading pair to
        :return: A list of daily close
        """
        url = "https://api.binance.com/api/v3/klines"
        client = await cls.http_client()
        params = {"symbol": trading_pair.replace("-", ""),
                  "interval": "1d"}
        async with client.request("GET", url, params=params) as resp:
            records = await resp.json()
            return [Decimal(str(record[4])) for record in records]

    @property
    def connector(self) -> ExchangeBase:
        return self.connectors[self.connector_name]

    async def on_tick(self):
        proposal: List[OrderCandidate] = await self.create_proposal()
        proposal = self.connector.budget_checker.adjust_candidates(proposal)
        if proposal:
            self.execute_proposal(proposal)

    async def create_proposal(self) -> List[OrderCandidate]:
        daily_closes = await self.get_daily_close_list(self.trading_pair)
        avg_close = mean(daily_closes[-51:-2])
        proposal = []
        if daily_closes[-1] < avg_close * Decimal("0.99"):
            order_price = self.connector.get_price(self.trading_pair, False)
            usd_conversion_rate = await RateOracle.rate_async(self.conversion_pair)
            amount = (self.buy_usd_amount / usd_conversion_rate) / order_price
            proposal.append(OrderCandidate(self.trading_pair, False, OrderType.LIMIT, TradeType.BUY, amount,
                                           order_price))
        return proposal

    def execute_proposal(self, proposal: List[OrderCandidate]):
        if self.last_ordered_ts > time.time() - self.cool_off_interval:
            return
        for order_candidate in proposal:
            if order_candidate.amount > Decimal("0"):
                self.buy(self.connector_name, self.trading_pair, order_candidate.amount, order_candidate.order_type,
                         order_candidate.price)
                self.last_ordered_ts = time.time()

    def did_fill_order(self, event: OrderFilledEvent):
        """
        Check if order has been completed, log it, notify the hummingbot application.
        """
        msg = f"({event.trading_pair}) {event.trade_type.name} order (price: {event.price}) of {event.amount} " \
              f"{event.trading_pair.split('-')[0]} is filled."
        self.log_with_clock(logging.INFO, msg)
        self.notify_hb_app_with_timestamp(msg)
