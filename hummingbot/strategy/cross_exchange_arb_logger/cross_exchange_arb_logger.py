import decimal
import itertools
import logging

from hummingbot.logger import HummingbotLogger
from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple
from hummingbot.strategy.strategy_py_base import StrategyPyBase

from .data_types import TopOfBookPrices

hws_logger = None


class CrossExchangeArbLogger(StrategyPyBase):
    @classmethod
    def logger(cls) -> HummingbotLogger:
        global hws_logger
        if hws_logger is None:
            hws_logger = logging.getLogger(__name__)
        return hws_logger

    def __init__(
        self,
        market_infos: list[MarketTradingPairTuple],
        with_fees: bool,
    ):
        super().__init__()
        self._market_infos = market_infos
        self._with_fees = with_fees
        self._all_markets_ready = False
        self.add_markets([market_info.market for market_info in market_infos])

    @property
    def all_markets_ready(self) -> bool:
        return self._all_markets_ready

    @all_markets_ready.setter
    def all_markets_ready(self, value: bool):
        self._all_markets_ready = value

    def tick(self, timestamp: float):
        if not self.all_markets_ready:
            self.all_markets_ready = all([market.ready for market in self.active_markets])
            if not self.all_markets_ready:
                if int(timestamp) % 10 == 0:  # prevent spamming by logging every 10 secs
                    unready_markets = [market for market in self.active_markets if market.ready is False]
                    for market in unready_markets:
                        msg = ', '.join([k for k, v in market.status_dict.items() if v is False])
                        self.logger().warning(f"{market.name} not ready: waiting for {msg}.")
                return
            else:
                self.logger().info("Markets are ready. Logging started.")

        self._main()

    def _main(self):
        # TODO replace self._market_info
        # Get prices once
        top_of_books: dict[MarketTradingPairTuple, TopOfBookPrices] = {}
        for market_info in self._market_infos:
            top_of_books[market_info] = TopOfBookPrices(
                bid=market_info.get_price(is_buy=False),
                ask=market_info.get_price(is_buy=True),
            )

        for market_1, market_2 in itertools.combinations(self._market_infos, 2):
            forward_spead = calculate_spread(top_of_books[market_1].bid, top_of_books[market_2].ask)
            reverse_spread = calculate_spread(top_of_books[market_2].bid, top_of_books[market_1].ask)
            log_lines = [
                self._format_orderbook_line(market_1.market.name, market_1.trading_pair, top_of_books[market_1].bid, top_of_books[market_1].ask),
                self._format_orderbook_line(market_2.market.name, market_2.trading_pair, top_of_books[market_2].bid, top_of_books[market_2].ask),
                self._format_arb_opportunity_line(True, market_1.market.name, market_2.market.name, forward_spead),
                self._format_arb_opportunity_line(False, market_2.market.name, market_1.market.name, reverse_spread),
            ]
            self.logger().info("\n" + "\n".join(log_lines))

    def _calculate_arb(self, bid_price, ask_price, bid_fee, ask_fee):
        return 0.001

    @staticmethod
    def _format_orderbook_line(exchange: str, instrument: str, best_bid: float, best_ask: float) -> str:
        return (
            f"{exchange} ({instrument}):\n"
            f"   Best Bid: {best_bid:,.2f} | Best Ask: {best_ask:,.2f}"
        )

    @staticmethod
    def _format_arb_opportunity_line(
        is_forward: bool,
        bid_exchange: str,
        ask_exchange: str,
        pct: float
    ) -> str:
        direction = "forward" if is_forward else "reverse"
        sign = "+" if pct >= 0 else "-"
        return (
            f"Potential {direction} arb: "
            f"({bid_exchange} bid) - ({ask_exchange} ask) / "
            f"({ask_exchange} ask) = {sign}{abs(pct):.2f}%"
        )


def calculate_spread(
    bid_price: decimal.Decimal,
    ask_price: decimal.Decimal,
    bid_fee: decimal.Decimal | None = None,
    ask_fee: decimal.Decimal | None = None
) -> decimal.Decimal:
    """
    Calculate arbitrage spread between a bid and ask price:
    Spread = ((bid - ask) / ask) * 100

    Fees are expected as decimals (e.g., 0.001 for 0.1%).
    Applies fees as:
        - bid_price reduced by bid_fee
        - ask_price increased by ask_fee
    """
    bid_fee = bid_fee or decimal.Decimal("0")
    ask_fee = ask_fee or decimal.Decimal("0")

    adj_bid = bid_price * (decimal.Decimal("1") - bid_fee)
    adj_ask = ask_price * (decimal.Decimal("1") + ask_fee)

    spread = ((adj_bid - adj_ask) / adj_ask) * decimal.Decimal("100")
    return spread
