import decimal
import itertools
import logging

from hummingbot.client.config.trade_fee_schema_loader import TradeFeeSchemaLoader
from hummingbot.core.data_type.trade_fee import TradeFeeSchema
from hummingbot.logger import HummingbotLogger
from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple
from hummingbot.strategy.strategy_py_base import StrategyPyBase

from .utils import calculate_spread

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
        for market_1, market_2 in itertools.combinations(self._market_infos, 2):
            self._main_for_two_exchanges(market_1, market_2)

    def _main_for_two_exchanges(self, market_1: MarketTradingPairTuple, market_2: MarketTradingPairTuple):
        market_1_fee, market_2_fee = decimal.Decimal("0"), decimal.Decimal("0")
        if self._with_fees:
            trade_fee_schema_1: TradeFeeSchema = TradeFeeSchemaLoader.configured_schema_for_exchange(
                exchange_name=market_1.market.name,
            )
            market_1_fee = trade_fee_schema_1.taker_percent_fee_decimal  # assuming market order

            trade_fee_schema_2: TradeFeeSchema = TradeFeeSchemaLoader.configured_schema_for_exchange(
                exchange_name=market_2.market.name,
            )
            market_2_fee = trade_fee_schema_2.taker_percent_fee_decimal  # assuming market order

        m_1_b, m_1_a = market_1.get_price(is_buy=False), market_1.get_price(is_buy=True)
        m_2_b, m_2_a = market_2.get_price(is_buy=False), market_2.get_price(is_buy=True)

        # The get_price method return type hint is decimal.Decimal, implying that a price
        # will always be returned. In reality, there could be no bid or ask. Let's assume
        # get_price returns None or decimal.Decimal("0") in this case, and log it
        if any(p is None or p == decimal.Decimal("0") for p in (m_1_b, m_1_a, m_2_b, m_2_a)):
            self.logger().warning(
                f"\nOne or more prices could not be retrieved.\n"
                f"{market_1.market.name} - Bid: {m_1_b}, Ask: {m_1_a}\n"
                f"{market_2.market.name} - Bid: {m_2_b}, Ask: {m_2_a}\n"
                f"Prices may be None or zero if no order is present."
            )
            return

        forward_spead = calculate_spread(
            m_1_b,
            m_2_a,
            market_1_fee,
            market_2_fee,
        )

        reverse_spread = calculate_spread(
            m_2_b,
            m_1_a,
            market_2_fee,
            market_1_fee,
        )

        log_lines = [
            self._format_orderbook_line(market_1.market.name, market_1.trading_pair, m_1_b, m_1_a),
            self._format_orderbook_line(market_2.market.name, market_2.trading_pair, m_2_b, m_2_a),
            self._format_arb_opportunity_line(True, market_1.market.name, market_2.market.name, forward_spead),
            self._format_arb_opportunity_line(False, market_2.market.name, market_1.market.name, reverse_spread),
            f"Fees{'' if self._with_fees else ' not'} included.",
        ]
        self.logger().info("\n" + "\n".join(log_lines))

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
