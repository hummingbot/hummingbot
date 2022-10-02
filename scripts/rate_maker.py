from decimal import Decimal

from hummingbot.connector.exchange_base import ExchangeBase, PriceType
from hummingbot.connector.utils import split_hb_trading_pair
from hummingbot.core.event.events import (
    BuyOrderCompletedEvent,
    BuyOrderCreatedEvent,
    MarketOrderFailureEvent,
    OrderCancelledEvent,
    OrderFilledEvent,
    OrderType,
    SellOrderCompletedEvent,
    SellOrderCreatedEvent,
)
from hummingbot.core.rate_oracle.rate_oracle import RateOracle
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase


class RateMaker(ScriptStrategyBase):
    """
    THis strategy buys ETH (with BTC) when the ETH-BTC drops 5% below 50 days moving average (of a previous candle)
    This example demonstrates:
      - How to call Binance REST API for candle stick data
      - How to incorporate external pricing source (Coingecko) into the strategy
      - How to listen to order filled event
      - How to structure order execution on a more complex strategy
    Before running this example, make sure you run `config rate_oracle_source coingecko`
    """

    maker_source_name: str = "coinhub"
    maker_trading_pair: str = "SHIB-MNT"
    maker_base_asset, maker_quote_asset = split_hb_trading_pair(maker_trading_pair)
    taker_source_name: str = "binance_paper_trade"
    taker_trading_pair: str = "SHIB-USDT"
    taker_base_asset, taker_quote_asset = split_hb_trading_pair(taker_trading_pair)

    conversion_pair: str = f"{taker_quote_asset}-{maker_quote_asset}"
    markets = {maker_source_name: {maker_trading_pair}, taker_source_name: {taker_trading_pair}}

    # 0.5%
    _spread = 0.05

    _all_markets_ready = False
    #: The last time the strategy places a buy order
    last_ordered_ts = 0.0
    buy_interval = 3.0

    ignore_list = []

    previous_last_trade_price = 0

    should_use_mid_price = False

    cancel_last_task = None
    _rate_oracle_ready = False

    _rate_oracle_task = None

    @property
    def spread(self) -> Decimal:
        return Decimal(self._spread) / Decimal("100")

    @property
    def maker(self) -> ExchangeBase:
        """
        The only connector in this strategy, define it here for easy access
        """
        return self.connectors[self.maker_source_name]

    @property
    def taker(self) -> ExchangeBase:
        """
        The only connector in this strategy, define it here for easy access
        """
        return self.connectors[self.taker_source_name]

    def on_tick(self):
        """
        Runs every tick_size seconds, this is the main operation of the strategy.
        - Create proposal (a list of order candidates)
        - Check the account balance and adjust the proposal accordingly (lower order amount if needed)
        - Lastly, execute the proposal on the exchange
        """
        if not self._all_markets_ready or not self._rate_oracle_ready:
            self._all_markets_ready = all([market.ready for market in [self.maker, self.taker]])
            self._rate_oracle_ready = RateOracle.get_instance().ready
            if not self._rate_oracle_ready:
                # Rate oracle not ready yet. Don't do anything.
                self.logger().warning("Rate oracle is not ready. No market making trades are permitted.")
                if self._rate_oracle_task is None:
                    self._rate_oracle_task = safe_ensure_future(RateOracle.get_instance().start_network())
                return
            if not self._all_markets_ready:
                # Markets not ready yet. Don't do anything.
                self.logger().warning("Markets are not ready. No market making trades are permitted.")
                return
            else:
                self.logger().info("Markets are ready. Trading started.")
        if self.last_ordered_ts < (self.current_timestamp - self.buy_interval):
            self.logger().info("##################################")
            if len(self.ignore_list) > 0:
                self.cancel_last_task = safe_ensure_future(self.maker.cancel(self.maker_trading_pair, self.ignore_list[-1]))
                self.ignore_list.pop()
            if not self.ignore_list or (len(self.ignore_list) > 0 and self.cancel_last_task is not None and self.cancel_last_task.done()):
                maker_trading_rule = self.maker.trading_rules[self.maker_trading_pair]
                min_order_size = maker_trading_rule.min_order_size + maker_trading_rule.min_base_amount_increment

                quote_conversion_rate = RateOracle.get_instance().rate(self.conversion_pair)
                taker_last_price = self.taker.get_price_by_type(self.taker_trading_pair, PriceType.LastTrade)
                maker_mid_price = self.maker.get_price_by_type(self.maker_trading_pair, PriceType.MidPrice)
                taker_price_in_maker_quote = taker_last_price * quote_conversion_rate
                taker_price_change_pct = 1 - (self.previous_last_trade_price / taker_last_price)
                price = maker_mid_price * (1 + taker_price_change_pct)

                self.logger().info(f"Taker previous last trade price: {self.previous_last_trade_price}")
                self.logger().info(f"Price change percentage: {taker_price_change_pct}")
                self.logger().info(f"Taker last trade price: {taker_last_price}")
                self.logger().info(f"Maker mid price: {maker_mid_price}")

                # if price is different from taker price by 1%, we should take taker price as our order price
                if not self.should_use_mid_price or (abs(price / taker_price_in_maker_quote) * 100 > 1 or self.previous_last_trade_price == 0):
                    self.logger().info("Should take as taker price")
                    price = taker_price_in_maker_quote
                self.logger().info(f"Order price: {price}")
                if taker_price_change_pct > 0:
                    # BUY
                    self.logger().info("### BUY ###")
                    self.maker.buy(self.maker_trading_pair, min_order_size, OrderType.LIMIT, price)
                else:
                    # SELL
                    self.logger().info("### SELL ###")
                    self.maker.sell(self.maker_trading_pair, min_order_size, OrderType.LIMIT, price)

                self.previous_last_trade_price = taker_last_price
            self.last_ordered_ts = self.current_timestamp

    def did_create_buy_order(self, event: BuyOrderCreatedEvent):
        """
        Method called when the connector notifies a buy order has been created
        """
        # self.logger().info(logging.INFO, f"The buy order {event.order_id} has been created")
        if event.order_id not in self.ignore_list:
            client_order_id = self.maker.sell(self.maker_trading_pair, event.amount, OrderType.LIMIT, event.price)
            self.ignore_list.append(client_order_id)

    def did_create_sell_order(self, event: SellOrderCreatedEvent):
        """
        Method called when the connector notifies a sell order has been created
        """
        # self.logger().info(logging.INFO, f"The sell order {event.order_id} has been created")
        if event.order_id not in self.ignore_list:
            client_order_id = self.maker.buy(self.maker_trading_pair, event.amount, OrderType.LIMIT, event.price)
            self.ignore_list.append(client_order_id)

    def did_fill_order(self, event: OrderFilledEvent):
        """
        Method called when the connector notifies that an order has been partially or totally filled (a trade happened)
        """
        # self.logger().info(logging.INFO, f"The order {event.order_id} has been filled")

    def did_fail_order(self, event: MarketOrderFailureEvent):
        """
        Method called when the connector notifies an order has failed
        """
        # self.logger().info(logging.INFO, f"The order {event.order_id} failed")

    def did_cancel_order(self, event: OrderCancelledEvent):
        """
        Method called when the connector notifies an order has been cancelled
        """
        self.ignore_list.append(event.exchange_order_id)
        # self.logger().info(f"The order {event.order_id} has been cancelled")

    def did_complete_buy_order(self, event: BuyOrderCompletedEvent):
        """
        Method called when the connector notifies a buy order has been completed (fully filled)
        """
        self.ignore_list.append(event.exchange_order_id)
        # self.logger().info(f"The buy order {event.order_id} has been completed")

    def did_complete_sell_order(self, event: SellOrderCompletedEvent):
        """
        Method called when the connector notifies a sell order has been completed (fully filled)
        """
        self.ignore_list.append(event.exchange_order_id)
        # self.logger().info(f"The sell order {event.order_id} has been completed")
