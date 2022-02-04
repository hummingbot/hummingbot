from hummingbot.strategy.lite_strategy_base import LiteStrategyBase


class DCAStrategy(LiteStrategyBase):
    markets = {"binance_paper_trade": {"BTC-USDT"}}
