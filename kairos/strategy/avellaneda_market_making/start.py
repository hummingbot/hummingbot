import os.path
from typing import List, Tuple

import pandas as pd

from kairos import data_path
from kairos.client.kairos_application import KairosApplication
from kairos.strategy.avellaneda_market_making import AvellanedaMarketMakingStrategy
from kairos.strategy.market_trading_pair_tuple import MarketTradingPairTuple


async def start(self):
    try:
        c_map = self.strategy_config_map
        exchange = c_map.exchange
        raw_trading_pair = c_map.market

        trading_pair: str = raw_trading_pair
        base, quote = trading_pair.split("-")
        maker_assets: Tuple[str, str] = (base, quote)
        market_names: List[Tuple[str, List[str]]] = [(exchange, [trading_pair])]
        await self.initialize_markets(market_names)
        maker_data = [self.markets[exchange], trading_pair] + list(maker_assets)
        self.market_trading_pair_tuples = [MarketTradingPairTuple(*maker_data)]

        strategy_logging_options = AvellanedaMarketMakingStrategy.OPTION_LOG_ALL

        debug_csv_path = os.path.join(data_path(),
                                      KairosApplication.main_application().strategy_file_name.rsplit('.', 1)[0] +
                                      f"_{pd.Timestamp.now().strftime('%Y-%m-%d_%H-%M-%S')}.csv")

        self.strategy = AvellanedaMarketMakingStrategy()
        self.strategy.init_params(
            config_map=c_map,
            market_info=MarketTradingPairTuple(*maker_data),
            logging_options=strategy_logging_options,
            hb_app_notification=True,
            debug_csv_path=debug_csv_path,
            is_debug=False
        )
    except Exception as e:
        self.notify(str(e))
        self.logger().error("Unknown error during initialization.", exc_info=True)
