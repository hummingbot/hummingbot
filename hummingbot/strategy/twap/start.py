from datetime import datetime
from typing import (
    List,
    Tuple,
)

from hummingbot.strategy.conditional_execution_state import (
    RunAlwaysExecutionState,
    RunInTimeConditionalExecutionState)
from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple
from hummingbot.strategy.twap import (
    TwapTradeStrategy
)
from hummingbot.strategy.twap.twap_config_map import twap_config_map


def start(self):
    try:
        order_step_size = twap_config_map.get("order_step_size").value
        trade_side = twap_config_map.get("trade_side").value
        target_asset_amount = twap_config_map.get("target_asset_amount").value
        is_time_span_execution = twap_config_map.get("is_time_span_execution").value
        is_delayed_start_execution = twap_config_map.get("is_delayed_start_execution").value
        exchange = twap_config_map.get("connector").value.lower()
        raw_market_trading_pair = twap_config_map.get("trading_pair").value
        order_price = twap_config_map.get("order_price").value
        cancel_order_wait_time = twap_config_map.get("cancel_order_wait_time").value

        try:
            assets: Tuple[str, str] = self._initialize_market_assets(exchange, [raw_market_trading_pair])[0]
        except ValueError as e:
            self.notify(str(e))
            return

        market_names: List[Tuple[str, List[str]]] = [(exchange, [raw_market_trading_pair])]

        self._initialize_markets(market_names)
        maker_data = [self.markets[exchange], raw_market_trading_pair] + list(assets)
        self.market_trading_pair_tuples = [MarketTradingPairTuple(*maker_data)]

        is_buy = trade_side == "buy"

        if is_time_span_execution:
            start_datetime_string = twap_config_map.get("start_datetime").value
            end_datetime_string = twap_config_map.get("end_datetime").value
            start_time = datetime.fromisoformat(start_datetime_string)
            end_time = datetime.fromisoformat(end_datetime_string)

            order_delay_time = twap_config_map.get("order_delay_time").value
            execution_state = RunInTimeConditionalExecutionState(start_timestamp=start_time, end_timestamp=end_time)
        elif is_delayed_start_execution:
            start_datetime_string = twap_config_map.get("start_datetime").value
            start_time = datetime.fromisoformat(start_datetime_string)

            order_delay_time = twap_config_map.get("order_delay_time").value
            execution_state = RunInTimeConditionalExecutionState(start_timestamp=start_time)
        else:
            order_delay_time = twap_config_map.get("order_delay_time").value
            execution_state = RunAlwaysExecutionState()

        self.strategy = TwapTradeStrategy(market_infos=[MarketTradingPairTuple(*maker_data)],
                                          is_buy=is_buy,
                                          target_asset_amount=target_asset_amount,
                                          order_step_size=order_step_size,
                                          order_price=order_price,
                                          order_delay_time=order_delay_time,
                                          execution_state=execution_state,
                                          cancel_order_wait_time=cancel_order_wait_time)
    except Exception as e:
        self.notify(str(e))
        self.logger().error("Unknown error during initialization.", exc_info=True)
