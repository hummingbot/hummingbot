from decimal import Decimal
import pandas as pd
import threading
from typing import (
    TYPE_CHECKING,
    List,
)
from datetime import datetime
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.core.data_type.trade import Trade, TradeType
from hummingbot.core.data_type.common import OpenOrder
from hummingbot.client.performance import PerformanceMetrics
from hummingbot.client.command.history_command import get_timestamp
from hummingbot.client.config.global_config_map import global_config_map
from hummingbot.core.rate_oracle.rate_oracle import RateOracle

s_float_0 = float(0)
s_decimal_0 = Decimal("0")

if TYPE_CHECKING:
    from hummingbot.client.hummingbot_application import HummingbotApplication


class TradesCommand:
    def trades(self,  # type: HummingbotApplication
               days: float,
               market: str,
               open_order_markets: bool):
        if threading.current_thread() != threading.main_thread():
            self.ev_loop.call_soon_threadsafe(self.trades)
            return
        safe_ensure_future(self.trades_report(days, market, open_order_markets))

    async def trades_report(self,  # type: HummingbotApplication
                            days: float,
                            market: str,
                            open_order_markets: bool):
        connector = await self.get_binance_connector()
        if connector is None:
            self._notify("This command supports only binance (for now), please first connect to binance.")
            return
        self._notify(f"Starting: {datetime.fromtimestamp(get_timestamp(days)).strftime('%Y-%m-%d %H:%M:%S')}"
                     f"    Ending: {datetime.fromtimestamp(get_timestamp(0)).strftime('%Y-%m-%d %H:%M:%S')}")
        self._notify("Retrieving trades....")
        if market is not None:
            markets = {market.upper()}
        elif open_order_markets:
            orders: List[OpenOrder] = await connector.get_open_orders()
            markets = {o.trading_pair for o in orders}
        else:
            markets = set(global_config_map["binance_markets"].value.split(","))
        markets = sorted(markets)
        for market in markets:
            await self.market_trades_report(connector, days, market)

    async def market_trades_report(self,  # type: HummingbotApplication
                                   connector,
                                   days: float,
                                   market: str):
        trades: List[Trade] = await connector.get_my_trades(market, days)
        g_sym = RateOracle.global_token_symbol
        if not trades:
            self._notify(f"There is no trade on {market}.")
            return
        data = []
        amount_g_col_name = f" Amount ({g_sym})"
        columns = ["Time", " Side", " Price", "Amount", amount_g_col_name]
        trades = sorted(trades, key=lambda x: (x.trading_pair, x.timestamp))
        fees = {}  # a dict of token and total fee amount
        fee_usd = 0

        for trade in trades:
            time = f"{datetime.fromtimestamp(trade.timestamp / 1e3).strftime('%Y-%m-%d %H:%M:%S')} "
            side = "buy" if trade.side is TradeType.BUY else "sell"
            usd = await RateOracle.global_value(trade.trading_pair.split("-")[0], trade.amount)
            data.append([time, side, PerformanceMetrics.smart_round(trade.price), PerformanceMetrics.smart_round(trade.amount), round(usd)])
            for fee in trade.trade_fee.flat_fees:
                if fee[0] not in fees:
                    fees[fee[0]] = fee[1]
                else:
                    fees[fee[0]] += fee[1]
                fee_usd += await RateOracle.global_value(fee[0], fee[1])

        lines = []
        df: pd.DataFrame = pd.DataFrame(data=data, columns=columns)
        lines.extend([f"  {market.upper()}"])
        lines.extend(["    " + line for line in df.to_string(index=False).split("\n")])
        self._notify("\n" + "\n".join(lines))
        fee_text = ",".join(k + ": " + f"{v:.4f}" for k, v in fees.items())
        self._notify(f"\n  Total traded: {g_sym} {df[amount_g_col_name].sum():.0f}    "
                     f"Fees: {fee_text} ({g_sym} {fee_usd:.2f})")
