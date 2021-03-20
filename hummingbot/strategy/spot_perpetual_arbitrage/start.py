from decimal import Decimal
from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple
from hummingbot.strategy.spot_perpetual_arbitrage.spot_perpetual_arbitrage import SpotPerpetualArbitrageStrategy
from hummingbot.strategy.spot_perpetual_arbitrage.spot_perpetual_arbitrage_config_map import spot_perpetual_arbitrage_config_map


def start(self):
    spot_connector = spot_perpetual_arbitrage_config_map.get("spot_connector").value.lower()
    spot_market = spot_perpetual_arbitrage_config_map.get("spot_market").value
    derivative_connector = spot_perpetual_arbitrage_config_map.get("derivative_connector").value.lower()
    derivative_market = spot_perpetual_arbitrage_config_map.get("derivative_market").value
    order_amount = spot_perpetual_arbitrage_config_map.get("order_amount").value
    derivative_leverage = spot_perpetual_arbitrage_config_map.get("derivative_leverage").value
    min_divergence = spot_perpetual_arbitrage_config_map.get("min_divergence").value / Decimal("100")
    min_convergence = spot_perpetual_arbitrage_config_map.get("min_convergence").value / Decimal("100")
    spot_market_slippage_buffer = spot_perpetual_arbitrage_config_map.get("spot_market_slippage_buffer").value / Decimal("100")
    derivative_market_slippage_buffer = spot_perpetual_arbitrage_config_map.get("derivative_market_slippage_buffer").value / Decimal("100")
    maximize_funding_rate = spot_perpetual_arbitrage_config_map.get("maximize_funding_rate").value

    self._initialize_markets([(spot_connector, [spot_market]), (derivative_connector, [derivative_market])])
    base_1, quote_1 = spot_market.split("-")
    base_2, quote_2 = derivative_market.split("-")
    self.assets = {base_1, quote_1, base_2, quote_2}

    spot_market_info = MarketTradingPairTuple(self.markets[spot_connector], spot_market, base_1, quote_1)
    derivative_market_info = MarketTradingPairTuple(self.markets[derivative_connector], derivative_market, base_2, quote_2)

    self.market_trading_pair_tuples = [spot_market_info, derivative_market_info]
    self.strategy = SpotPerpetualArbitrageStrategy(spot_market_info,
                                                   derivative_market_info,
                                                   order_amount,
                                                   derivative_leverage,
                                                   min_divergence,
                                                   min_convergence,
                                                   spot_market_slippage_buffer,
                                                   derivative_market_slippage_buffer,
                                                   maximize_funding_rate)
