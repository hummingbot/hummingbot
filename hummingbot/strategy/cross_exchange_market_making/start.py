from typing import List, Tuple

import hummingbot.client.settings as settings
from hummingbot.strategy.cross_exchange_market_making.cross_exchange_market_making import (
    CrossExchangeMarketMakingStrategy,
    LogOption,
)
from hummingbot.strategy.maker_taker_market_pair import MakerTakerMarketPair
from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple


def start(self):
    c_map = self.strategy_config_map
    maker_market = c_map.maker_market.lower()
    taker_market = c_map.taker_market.lower()
    raw_maker_trading_pair = c_map.maker_market_trading_pair
    raw_taker_trading_pair = c_map.taker_market_trading_pair
    status_report_interval = self.client_config_map.strategy_report_interval

    # Post validation logic moved from pydantic config
    settings.required_exchanges.add(c_map.maker_market)
    settings.required_exchanges.add(c_map.taker_market)

    first_base, first_quote = c_map.maker_market_trading_pair.split("-")
    second_base, second_quote = c_map.taker_market_trading_pair.split("-")
    if first_base != second_base or first_quote != second_quote:
        settings.required_rate_oracle = True
        settings.rate_oracle_pairs = []
        if first_base != second_base:
            settings.rate_oracle_pairs.append(f"{second_base}-{first_base}")
        if first_quote != second_quote:
            settings.rate_oracle_pairs.append(f"{second_quote}-{first_quote}")
    else:
        settings.required_rate_oracle = False
        settings.rate_oracle_pairs = []

    try:
        maker_trading_pair: str = raw_maker_trading_pair
        taker_trading_pair: str = raw_taker_trading_pair
        maker_base, maker_quote = maker_trading_pair.split("-")
        taker_base, taker_quote = taker_trading_pair.split("-")
        maker_assets: Tuple[str, str] = (maker_base, maker_quote)
        taker_assets: Tuple[str, str] = (taker_base, taker_quote)
    except ValueError as e:
        self.notify(str(e))
        return

    market_names: List[Tuple[str, List[str]]] = [
        (maker_market, [maker_trading_pair]),
        (taker_market, [taker_trading_pair]),
    ]

    self.initialize_markets(market_names)
    maker_data = [self.markets[maker_market], maker_trading_pair] + list(maker_assets)
    taker_data = [self.markets[taker_market], taker_trading_pair] + list(taker_assets)
    maker_market_trading_pair_tuple = MarketTradingPairTuple(*maker_data)
    taker_market_trading_pair_tuple = MarketTradingPairTuple(*taker_data)
    self.market_trading_pair_tuples = [maker_market_trading_pair_tuple, taker_market_trading_pair_tuple]
    self.market_pair = MakerTakerMarketPair(maker=maker_market_trading_pair_tuple,
                                            taker=taker_market_trading_pair_tuple)

    strategy_logging_options = (
        LogOption.CREATE_ORDER,
        LogOption.ADJUST_ORDER,
        LogOption.MAKER_ORDER_FILLED,
        LogOption.REMOVING_ORDER,
        LogOption.STATUS_REPORT,
        LogOption.MAKER_ORDER_HEDGED
    )
    self.strategy = CrossExchangeMarketMakingStrategy()
    self.strategy.init_params(
        config_map=c_map,
        market_pairs=[self.market_pair],
        status_report_interval=status_report_interval,
        logging_options=strategy_logging_options,
        hb_app_notification=True,
    )
