from hummingbot.connector.exchange_base import ExchangeBase
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
    maker_trading_pair: str = "ETH-MNT"
    taker_source_name: str = "coinhub_paper_trade"
    maker_source_name: str = "coinhub_sandbox"
    maker_base_asset, maker_quote_asset = split_hb_trading_pair(maker_trading_pair)
    markets = {maker_source_name: {maker_trading_pair}, taker_source_name: {maker_trading_pair}}

    _all_markets_ready = False
    check_interval = 3.0

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
        if not self._all_markets_ready:
            self._all_markets_ready = all([market.ready for market in [self.maker, self.taker]])
            if not RateOracle.get_instance().ready:
                # Rate oracle not ready yet. Don't do anything.
                self.logger().warning("Rate oracle is not ready. No market making trades are permitted.")
                return
            if not self._all_markets_ready:
                # Markets not ready yet. Don't do anything.
                self.logger().warning("Markets are not ready. No market making trades are permitted.")
                return
            else:
                self.logger().info("Markets are ready. Trading started.")
        self._clone()

    def _clone(self):
        print(self.taker.order_book_tracker.data_source.get_new_order_book())

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
