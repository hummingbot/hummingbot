from decimal import Decimal
from typing import List

from hummingbot.strategy.hedge.hedge import HedgeStrategy
from hummingbot.strategy.hedge.hedge_config_map import MAX_CONNECTOR, hedge_config_map as c_map
from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple

from ...core.data_type.common import PositionMode


def validate_offsets(markets: List[str], offsets: List[str]) -> List[str]:
    """checks and correct offsets to a valid value"""
    if len(offsets) >= len(markets):
        return offsets[:len(markets)]
    return offsets + ["0"] * (len(markets) - len(offsets))


def start(self):
    hedge_connector = c_map["hedge_connector"].value.lower()
    hedge_markets = c_map["hedge_markets"].value.split(",")
    hedge_offsets = c_map["hedge_offsets"].value.split(",")
    hedge_offsets = validate_offsets(hedge_markets, hedge_offsets)
    hedge_leverage = c_map["hedge_leverage"].value
    hedge_interval = c_map["hedge_interval"].value
    hedge_ratio = c_map["hedge_ratio"].value
    hedge_position_mode = PositionMode.HEDGE if c_map["hedge_position_mode"].value.lower() == "hedge" else PositionMode.ONEWAY
    min_trade_size = c_map["min_trade_size"].value
    max_order_age = c_map["max_order_age"].value
    slippage = c_map["slippage"].value
    value_mode = c_map["value_mode"].value

    initialize_markets = [(hedge_connector, hedge_markets)]
    offsets_dict = {hedge_connector: hedge_offsets}
    for i in range(MAX_CONNECTOR):
        if not c_map[f"enable_connector_{i}"].value:
            continue
        connector = c_map[f"connector_{i}"].value.lower()
        markets = c_map[f"markets_{i}"].value.split(",")
        offsets = c_map[f"offsets_{i}"].value.split(",")
        offsets_dict[connector] = validate_offsets(markets, offsets)
        initialize_markets.append((connector, markets))
    self._initialize_markets(initialize_markets)
    self.market_trading_pair_tuples = []
    offsets_market_dict = {}
    for connector, markets in initialize_markets:
        offsets = offsets_dict[connector]
        for market, offset in zip(markets, offsets):
            base, quote = market.split("-")
            market_info = MarketTradingPairTuple(self.markets[connector], market, base, quote)
            self.market_trading_pair_tuples.append(market_info)
            offsets_market_dict[market_info] = Decimal(offset)

    index = len(hedge_markets)
    hedge_market_pair = self.market_trading_pair_tuples[0:index]
    market_pairs = self.market_trading_pair_tuples[index:]
    self.strategy = HedgeStrategy(
        hedge_market_pairs=hedge_market_pair,
        market_pairs = market_pairs,
        hedge_leverage = hedge_leverage,
        hedge_interval = hedge_interval,
        hedge_ratio = hedge_ratio,
        min_trade_size = min_trade_size,
        max_order_age = max_order_age,
        slippage = slippage,
        value_mode = value_mode,
        hedge_position_mode=hedge_position_mode,
        offsets = offsets_market_dict
    )
