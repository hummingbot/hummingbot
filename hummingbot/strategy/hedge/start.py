from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple
from hummingbot.strategy.hedge.hedge_config_map import hedge_config_map as c_map
from hummingbot.strategy.hedge.hedge import HedgeStrategy
from hummingbot.strategy.hedge.exchange_pair import ExchangePairTuple


def start(self):
    maker_exchange = c_map.get("maker_exchange").value.lower()
    taker_exchange = c_map.get("taker_exchange").value.lower()
    maker_assets = list(c_map.get("maker_assets").value.split(","))
    taker_markets = list(c_map.get("taker_markets").value.split(","))
    maker_assets = [m.strip().upper() for m in maker_assets]
    taker_markets = [m.strip().upper() for m in taker_markets]
    hedge_ratio = c_map.get("hedge_ratio").value
    leverage = c_map.get("leverage").value
    slippage = c_map.get("slippage").value
    max_order_age = c_map.get("max_order_age").value
    minimum_trade = c_map.get("minimum_trade").value
    hedge_interval = c_map.get("hedge_interval").value
    self._initialize_markets([(maker_exchange, []), (taker_exchange, taker_markets)])
    exchanges = ExchangePairTuple(maker=self.markets[maker_exchange], taker=self.markets[taker_exchange])

    market_infos = {}
    for i, maker_asset in enumerate(maker_assets):
        taker_market = taker_markets[i]
        t_base, t_quote = taker_market.split("-")
        taker = MarketTradingPairTuple(self.markets[taker_exchange], taker_market, t_base, t_quote)
        market_infos[maker_asset] = taker

    self.strategy = HedgeStrategy()
    self.strategy.init_params(
        exchanges = exchanges,
        market_infos = market_infos,
        hedge_ratio = hedge_ratio,
        leverage = leverage,
        minimum_trade = minimum_trade,
        slippage = slippage,
        max_order_age = max_order_age,
        hedge_interval = hedge_interval,
    )
