from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple
from hummingbot.strategy.hedge.hedge_config_map import hedge_config_map as c_map
from hummingbot.strategy.hedge.hedge import HedgeStrategy
from hummingbot.strategy.hedge.exchange_pair import ExchangePairTuple


def start(self):
    maker_exchange = c_map.get("maker_exchange").value.lower()
    taker_exchange = c_map.get("taker_exchange").value.lower()
    maker_markets = list(c_map.get("maker_markets").value.split(","))
    taker_markets = list(c_map.get("maker_markets").value.split(","))
    hedge_asset = c_map.get("hedge_asset").value
    maker_markets = [m.strip().upper() for m in maker_markets]
    taker_markets = [m.strip().upper() for m in taker_markets]
    hedge_ratio = c_map.get("hedge_ratio").value
    leverage = c_map.get("leverage").value
    minimum_trade = c_map.get("minimum_trade").value
    self._initialize_markets([(maker_exchange, maker_markets), (taker_exchange, taker_markets)])
    exchanges = ExchangePairTuple(maker=self.markets[maker_exchange], taker=self.markets[taker_exchange])

    market_infos = {}
    assets = {}
    for i, maker_market in enumerate(maker_markets):
        base, quote = maker_market.split("-")
        assets[maker_market] = base if quote == hedge_asset else quote
        taker_market = taker_markets[i]
        t_base, t_quote = taker_market.split("-")
        taker = MarketTradingPairTuple(self.markets[taker_exchange], taker_market, t_base, t_quote)
        market_infos[maker_market] = taker

    self.strategy = HedgeStrategy()
    self.strategy.init_params(
        exchanges = exchanges,
        assets = assets,
        market_infos = market_infos,
        hedge_ratio = hedge_ratio,
        leverage = leverage,
        minimum_trade = minimum_trade
    )
