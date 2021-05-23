from typing import (
    List,
    Tuple,
)

from hummingbot import data_path
import os.path
from hummingbot.client.hummingbot_application import HummingbotApplication
from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple
from hummingbot.strategy.bbo import (
    BBOStrategy,
)
from hummingbot.strategy.bbo.bbo_config_map import bbo_config_map as c_map
from decimal import Decimal
import pandas as pd


def start(self):
    try:
        order_amount = c_map.get("order_amount").value
        exchange = c_map.get("exchange").value.lower()
        raw_trading_pair = c_map.get("market").value
        volatility_days = c_map.get("volatility_days").value
        entry_band = c_map.get("entry_band").value
        exit_band = c_map.get("exit_band").value
        
        trading_pair: str = raw_trading_pair
        maker_assets: Tuple[str, str] = self._initialize_market_assets(exchange, [trading_pair])[0]
        market_names: List[Tuple[str, List[str]]] = [(exchange, [trading_pair])]
        self._initialize_wallet(token_trading_pairs=list(set(maker_assets)))
        self._initialize_markets(market_names)
        self.assets = set(maker_assets)
        maker_data = [self.markets[exchange], trading_pair] + list(maker_assets)
        self.market_trading_pair_tuples = [MarketTradingPairTuple(*maker_data)]

        strategy_logging_options = BBOStrategy.OPTION_LOG_ALL
        debug_csv_path = os.path.join(data_path(),
                                      HummingbotApplication.main_application().strategy_file_name.rsplit('.', 1)[0] +
                                      f"_{pd.Timestamp.now().strftime('%Y-%m-%d_%H-%M-%S')}.csv")

        self.strategy = BBOStrategy(
            market_info=MarketTradingPairTuple(*maker_data),
            order_amount=order_amount,
            logging_options=strategy_logging_options,
            hb_app_notification=True,
            debug_csv_path=debug_csv_path,
            volatility_days=volatility_days,
            entry_band=Decimal(entry_band),
            exit_band=Decimal(exit_band),
            is_debug=False
        )
    except Exception as e:
        self._notify(str(e))
        self.logger().error("Unknown error during initialization.", exc_info=True)
