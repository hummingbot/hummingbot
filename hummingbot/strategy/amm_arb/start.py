from decimal import Decimal
from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple
from hummingbot.strategy.amm_arb.amm_arb import AmmArbStrategy
from hummingbot.strategy.amm_arb.amm_arb_config_map import amm_arb_config_map
import ast


def start(self):
    market_tuples = amm_arb_config_map.get("market_list").value
    if isinstance(market_tuples, str):
        market_tuples = ast.literal_eval(market_tuples)  # Loading from config file
    order_amount = amm_arb_config_map.get("order_amount").value
    min_profitability = amm_arb_config_map.get("min_profitability").value / Decimal("100")
    concurrent_orders_submission = amm_arb_config_map.get("concurrent_orders_submission").value

    self._initialize_markets([(connector.lower(), [market]) for (connector, market, _) in market_tuples])
    bases = [market.split("-")[0] for (_, market, _) in market_tuples]
    quotes = [market.split("-")[1] for (_, market, _) in market_tuples]
    market_slippage_buffers = [splippage_buffer / Decimal("100") for (_, _, splippage_buffer) in market_tuples]  # TODO eventually check if not decimal, coming from yml
    self.assets = set(bases + quotes)

    markets_info = [MarketTradingPairTuple(self.markets[connector.lower()], market, base, quote) for ((connector, market, _), base, quote) in zip(market_tuples, bases, quotes)]

    self.market_trading_pair_tuples = markets_info
    self.strategy = AmmArbStrategy(markets_info, min_profitability, order_amount,
                                   market_slippage_buffers, concurrent_orders_submission)
