import logging
from decimal import Decimal
from typing import Dict, List

from hummingbot.core.data_type.common import OrderType, PriceType, TradeType
from hummingbot.core.data_type.order_candidate import OrderCandidate
from hummingbot.core.event.events import OrderFilledEvent
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase
from hummingbot.data_feed.candles_feed.candles_factory import CandlesFactory, CandlesConfig
from hummingbot.connector.connector_base import ConnectorBase

class PMMPriceShift(ScriptStrategyBase):
    """
    BotCamp Module 3 - Market Making Strategies
    Description:
    The bot extends the PMM Volatility Spread script by shifting the reference price based on trend as measured by RSI.
    """
    bid_spread = 0.0001
    ask_spread = 0.0001
    order_refresh_time = 15
    order_amount = 0.01
    create_timestamp = 0
    trading_pair = "ETH-USDT"
    exchange = "binance_paper_trade"
    # Here you can use for example the LastTrade price to use in your strategy
    price_source = PriceType.MidPrice

    # Candles params
    candle_exchange = "binance"
    candles_interval = "1m"
    candles_length = 30
    max_records = 1000

    # Spread params
    # Define spreads dynamically as (NATR over candles_length) * spread_scalar
    bid_spread_scalar = 120
    ask_spread_scalar = 60

    # Max range of shift for Price
    # max_shift_spread = max(bid_spread, ask_spread) # for illiquid pairs
    max_shift_spread = 0.000001 # for highly liquid pairs

    # Price shift params
    orig_price = 1
    reference_price = 1
    price_multiplier = 1
    trend_scalar = -1

    # Initializes candles
    candles = CandlesFactory.get_candle(CandlesConfig(connector=candle_exchange,
                                                      trading_pair=trading_pair,
                                                      interval=candles_interval,
                                                      max_records=max_records))

    # markets defines which order books (exchange / pair) to connect to. At least one exchange/pair needs to be instantiated
    markets = {exchange: {trading_pair}}

    # start the candles when the script starts
    def __init__(self, connectors: Dict[str, ConnectorBase]):
        super().__init__(connectors)
        self.candles.start()

    # stop the candles when the script stops
    def on_stop(self):
        self.candles.stop()

    def on_tick(self):
        if self.create_timestamp <= self.current_timestamp:
            self.cancel_all_orders()
            self.update_multipliers()
            proposal: List[OrderCandidate] = self.create_proposal()
            proposal_adjusted: List[OrderCandidate] = self.adjust_proposal_to_budget(proposal)
            self.place_orders(proposal_adjusted)
            self.create_timestamp = self.order_refresh_time + self.current_timestamp

    def get_candles_with_features(self):
        candles_df = self.candles.candles_df
        candles_df.ta.natr(length = self.candles_length, scalar=1, append=True)
        candles_df['bid_spread_bps'] = candles_df[f"NATR_{self.candles_length}"] * self.bid_spread_scalar * 10000
        candles_df['ask_spread_bps'] = candles_df[f"NATR_{self.candles_length}"] * self.ask_spread_scalar * 10000
        candles_df.ta.rsi(length=self.candles_length, append=True)
        return candles_df

    def update_multipliers(self):
        candles_df = self.get_candles_with_features()
        self.bid_spread = candles_df[f"NATR_{self.candles_length}"].iloc[-1] * self.bid_spread_scalar
        self.ask_spread = candles_df[f"NATR_{self.candles_length}"].iloc[-1] * self.ask_spread_scalar

        # Trend Shift
        rsi = candles_df[f"RSI_{self.candles_length}"].iloc[-1]
        self.price_multiplier = (rsi - 50) / 50 * self.max_shift_spread * self.trend_scalar

        # Define shifted reference price
        self.orig_price = self.connectors[self.exchange].get_price_by_type(self.trading_pair, self.price_source)
        self.reference_price = self.orig_price * Decimal(str(1 + self.price_multiplier))


    def create_proposal(self) -> List[OrderCandidate]:
        # Make sure your order spreads are not tighter that the best bid/ask orders on the book
        best_bid = self.connectors[self.exchange].get_price(self.trading_pair, False)
        best_ask = self.connectors[self.exchange].get_price(self.trading_pair, True)
        buy_price = min(self.reference_price * Decimal(1 - self.bid_spread), best_bid)
        sell_price = max(self.reference_price * Decimal(1 + self.ask_spread), best_ask)
        
        # Create order candidates
        buy_order = OrderCandidate(trading_pair=self.trading_pair, is_maker=True, order_type=OrderType.LIMIT,
                                   order_side=TradeType.BUY, amount=Decimal(self.order_amount), price=buy_price)

        sell_order = OrderCandidate(trading_pair=self.trading_pair, is_maker=True, order_type=OrderType.LIMIT,
                                    order_side=TradeType.SELL, amount=Decimal(self.order_amount), price=sell_price)

        return [buy_order, sell_order]

    def adjust_proposal_to_budget(self, proposal: List[OrderCandidate]) -> List[OrderCandidate]:
        proposal_adjusted = self.connectors[self.exchange].budget_checker.adjust_candidates(proposal, all_or_none=True)
        return proposal_adjusted

    def place_orders(self, proposal: List[OrderCandidate]) -> None:
        for order in proposal:
            self.place_order(connector_name=self.exchange, order=order)

    def place_order(self, connector_name: str, order: OrderCandidate):
        if order.order_side == TradeType.SELL:
            self.sell(connector_name=connector_name, trading_pair=order.trading_pair, amount=order.amount,
                      order_type=order.order_type, price=order.price)
        elif order.order_side == TradeType.BUY:
            self.buy(connector_name=connector_name, trading_pair=order.trading_pair, amount=order.amount,
                     order_type=order.order_type, price=order.price)

    def cancel_all_orders(self):
        for order in self.get_active_orders(connector_name=self.exchange):
            self.cancel(self.exchange, order.trading_pair, order.client_order_id)

    def did_fill_order(self, event: OrderFilledEvent):
        msg = (f"{event.trade_type.name} {round(event.amount, 2)} {event.trading_pair} {self.exchange} at {round(event.price, 2)}")
        self.log_with_clock(logging.INFO, msg)
        self.notify_hb_app_with_timestamp(msg)

    def format_status(self) -> str:
        """
        Returns status of the current strategy and displays candles feed info
        """
        if not self.ready_to_trade:
            return "Market connectors are not ready."
        lines = []

        balance_df = self.get_balance_df()
        lines.extend(["", "  Balances:"] + ["    " + line for line in balance_df.to_string(index=False).split("\n")])

        try:
            df = self.active_orders_df()
            lines.extend(["", "  Orders:"] + ["    " + line for line in df.to_string(index=False).split("\n")])
        except ValueError:
            lines.extend(["", "  No active maker orders."])

        ref_price = self.reference_price
        best_bid = self.connectors[self.exchange].get_price(self.trading_pair, False)
        best_ask = self.connectors[self.exchange].get_price(self.trading_pair, True)
        best_bid_spread = (ref_price - best_bid) / ref_price
        best_ask_spread = (best_ask - ref_price) / ref_price

        trend_price_shift = Decimal(self.price_multiplier) * Decimal(self.reference_price)

        lines.extend(["\n----------------------------------------------------------------------\n"])
        lines.extend(["  Spreads:"])
        lines.extend([f"  Bid Spread (bps): {self.bid_spread * 10000:.4f} | Best Bid Spread (bps): {best_bid_spread * 10000:.4f}"])
        lines.extend([f"  Ask Spread (bps): {self.ask_spread * 10000:.4f} | Best Ask Spread (bps): {best_ask_spread * 10000:.4f}"])
        lines.extend(["\n----------------------------------------------------------------------\n"])
        lines.extend(["  Price Shifts:"])
        lines.extend([f"  Max Shift (bps): {self.max_shift_spread * 10000:.4f}"])
        lines.extend([f"  Trend Scalar: {self.trend_scalar:.1f} | Trend Multiplier (bps): {self.price_multiplier * 10000:.4f} | Trend Price Shift: {trend_price_shift:.4f}"])
        lines.extend([f"  Orig Price: {self.orig_price:.4f} | Reference Price: {self.reference_price:.4f}"])
        lines.extend(["\n----------------------------------------------------------------------\n"])
        candles_df = self.get_candles_with_features()
        lines.extend([f"  Candles: {self.candles.name} | Interval: {self.candles.interval}", ""])
        lines.extend(["    " + line for line in candles_df.tail().iloc[::-1].to_string(index=False).split("\n")])

        return "\n".join(lines)
    