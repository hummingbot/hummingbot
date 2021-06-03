from decimal import Decimal
import pandas as pd
import threading
from typing import (
    TYPE_CHECKING,
    List,
)
from datetime import datetime
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.client.config.security import Security
from hummingbot.user.user_balances import UserBalances
from hummingbot.core.data_type.trade import Trade
from hummingbot.core.data_type.common import OpenOrder
from hummingbot.client.performance import PerformanceMetrics
from hummingbot.client.command.history_command import get_timestamp
from hummingbot.client.config.global_config_map import global_config_map
from hummingbot.core.rate_oracle.rate_oracle import RateOracle

s_float_0 = float(0)
s_decimal_0 = Decimal("0")

if TYPE_CHECKING:
    from hummingbot.client.hummingbot_application import HummingbotApplication


class PnlCommand:
    def pnl(self,  # type: HummingbotApplication
            days: float,
            market: str,
            open_order_markets: bool
            ):
        if threading.current_thread() != threading.main_thread():
            self.ev_loop.call_soon_threadsafe(self.trades)
            return
        safe_ensure_future(self.pnl_report(days, market, open_order_markets))

    async def get_binance_connector(self):
        if self._binance_connector is not None:
            return self._binance_connector
        api_keys = await Security.api_keys("binance")
        if not api_keys:
            return None
        self._binance_connector = UserBalances.connect_market("binance", **api_keys)
        return self._binance_connector

    async def pnl_report(self,  # type: HummingbotApplication
                         days: float,
                         market: str,
                         open_order_markets: bool
                         ):
        exchange = "binance"
        connector = await self.get_binance_connector()
        cur_balances = await self.get_current_balances(exchange)
        if connector is None:
            self._notify("This command supports only binance (for now), please first connect to binance.")
            return
        if market is not None:
            market = market.upper()
            trades: List[Trade] = await connector.get_my_trades(market, days)
            perf = await PerformanceMetrics.create(exchange, market, trades, cur_balances)
            self.report_performance_by_market(exchange, market, perf, precision=None)
            return
        self._notify(f"Starting: {datetime.fromtimestamp(get_timestamp(days)).strftime('%Y-%m-%d %H:%M:%S')}"
                     f"    Ending: {datetime.fromtimestamp(get_timestamp(0)).strftime('%Y-%m-%d %H:%M:%S')}")
        self._notify("Calculating profit and losses....")
        if open_order_markets:
            orders: List[OpenOrder] = await connector.get_open_orders()
            markets = {o.trading_pair for o in orders}
        else:
            if self.strategy_config_map is not None and "markets" in self.strategy_config_map:
                markets = set(self.strategy_config_map["markets"].value.split(","))
            else:
                markets = set(global_config_map["binance_markets"].value.split(","))
        markets = sorted(markets)
        data = []
        g_sym = RateOracle.global_token_symbol
        columns = ["Market", f" Traded ({g_sym})", f" Fee ({g_sym})", f" PnL ({g_sym})", " Return %"]
        for market in markets:
            base, quote = market.split("-")
            trades: List[Trade] = await connector.get_my_trades(market, days)
            if not trades:
                continue
            perf = await PerformanceMetrics.create(exchange, market, trades, cur_balances)
            volume = await RateOracle.global_value(quote, abs(perf.b_vol_quote) + abs(perf.s_vol_quote))
            fee = await RateOracle.global_value(quote, perf.fee_in_quote)
            pnl = await RateOracle.global_value(quote, perf.total_pnl)
            data.append([market, round(volume, 2), round(fee, 2), round(pnl, 2), f"{perf.return_pct:.2%}"])
        if not data:
            self._notify(f"No trades during the last {days} day(s).")
            return
        lines = []
        df: pd.DataFrame = pd.DataFrame(data=data, columns=columns)
        lines.extend(["    " + line for line in df.to_string(index=False).split("\n")])
        self._notify("\n" + "\n".join(lines))
        self._notify(f"\n  Total PnL: {g_sym} {df[f' PnL ({g_sym})'].sum():.2f}    "
                     f"Total fee: {g_sym} {df[f' Fee ({g_sym})'].sum():.2f}")
