from decimal import Decimal
from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple
from hummingbot.strategy.spot_perpetual_arbitrage.spot_perpetual_arbitrage import PerpetualArbitrageStrategy
from hummingbot.strategy.spot_perpetual_arbitrage.perpetual_arbitrage_config_map import perpetual_arbitrage_config_map


def start(self):
    primary_connector = perpetual_arbitrage_config_map.get("primary_connector").value.lower()
    primary_market = perpetual_arbitrage_config_map.get("primary_market").value
    secondary_connector = perpetual_arbitrage_config_map.get("secondary_connector").value.lower()
    secondary_market = perpetual_arbitrage_config_map.get("secondary_market").value
    order_amount = perpetual_arbitrage_config_map.get("order_amount").value
    derivative_leverage = perpetual_arbitrage_config_map.get("derivative_leverage").value
    min_divergence = perpetual_arbitrage_config_map.get("min_divergence").value / Decimal("100")
    min_convergence = perpetual_arbitrage_config_map.get("min_convergence").value / Decimal("100")
    primary_market_slippage_buffer = perpetual_arbitrage_config_map.get("primary_market_slippage_buffer").value / Decimal("100")
    secondary_market_slippage_buffer = perpetual_arbitrage_config_map.get("secondary_market_slippage_buffer").value / Decimal("100")
    maximize_funding_rate = perpetual_arbitrage_config_map.get("maximize_funding_rate").value
    next_arbitrage_cycle_delay = perpetual_arbitrage_config_map.get("next_arbitrage_cycle_delay").value

    self._initialize_markets([(primary_connector, [primary_market]), (secondary_connector, [secondary_market])])
    base_1, quote_1 = primary_market.split("-")
    base_2, quote_2 = secondary_market.split("-")
    self.assets = set([base_1, quote_1, base_2, quote_2])

    primary_market_info = MarketTradingPairTuple(self.markets[primary_connector], primary_market, base_1, quote_1)
    secondary_market_info = MarketTradingPairTuple(self.markets[secondary_connector], secondary_market, base_2, quote_2)

    self.market_trading_pair_tuples = [primary_market_info, secondary_market_info]
    self.strategy = PerpetualArbitrageStrategy()
    self.strategy.init_params(primary_market_info,
                              secondary_market_info,
                              order_amount,
                              derivative_leverage,
                              min_divergence,
                              min_convergence,
                              primary_market_slippage_buffer,
                              secondary_market_slippage_buffer,
                              maximize_funding_rate,
                              next_arbitrage_cycle_delay)
