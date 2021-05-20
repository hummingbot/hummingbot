from decimal import Decimal
import pandas as pd
import threading
from typing import (
    TYPE_CHECKING,
    List,
)
from datetime import datetime
from datetime import timezone
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.core.data_type.common import OpenOrder
from hummingbot.core.utils.market_price import get_binance_mid_price
from hummingbot.core.rate_oracle.rate_oracle import RateOracle

s_float_0 = float(0)
s_decimal_0 = Decimal("0")

if TYPE_CHECKING:
    from hummingbot.client.hummingbot_application import HummingbotApplication


class OpenOrdersCommand:
    def open_orders(self,  # type: HummingbotApplication
                    full_report: bool):
        if threading.current_thread() != threading.main_thread():
            self.ev_loop.call_soon_threadsafe(self.open_orders, full_report)
            return
        safe_ensure_future(self.open_orders_report(full_report))

    async def open_orders_report(self,  # type: HummingbotApplication
                                 full_report: bool):
        exchange = "binance"
        connector = await self.get_binance_connector()
        g_sym = RateOracle.global_token_symbol
        if connector is None:
            self._notify("This command supports only binance (for now), please first connect to binance.")
            return
        orders: List[OpenOrder] = await connector.get_open_orders()
        if not orders:
            self._notify("There is currently no open orders on binance.")
            return
        orders = sorted(orders, key=lambda x: (x.trading_pair, x.is_buy))
        data = []
        columns = ["Market", " Side", " Spread", f" Size ({g_sym})", " Age"]
        if full_report:
            columns.extend(["   Allocation", "   Per Total"])
        cur_balances = await self.get_current_balances(exchange)
        total_value = 0
        for o in orders:
            total_value += await RateOracle.global_value(o.trading_pair.split("-")[0], o.amount)
        for order in orders:
            base, quote = order.trading_pair.split("-")
            side = "buy" if order.is_buy else "sell"
            mid_price = await get_binance_mid_price(order.trading_pair)
            spread = abs(order.price - mid_price) / mid_price
            size_global = await RateOracle.global_value(order.trading_pair.split("-")[0], order.amount)
            age = pd.Timestamp((datetime.utcnow().replace(tzinfo=timezone.utc).timestamp() * 1e3 - order.time) / 1e3,
                               unit='s').strftime('%H:%M:%S')
            data_row = [order.trading_pair, side, f"{spread:.2%}", round(size_global), age]
            if full_report:
                token = quote if order.is_buy else base
                token_value = order.amount * order.price if order.is_buy else order.amount
                per_bal = token_value / cur_balances[token]
                token_txt = f"({token})"
                data_row.extend([f"{per_bal:.0%} {token_txt:>6}", f"{size_global / total_value:.0%}"])
            data.append(data_row)
        lines = []
        orders_df: pd.DataFrame = pd.DataFrame(data=data, columns=columns)
        lines.extend(["    " + line for line in orders_df.to_string(index=False).split("\n")])
        self._notify("\n" + "\n".join(lines))
        self._notify(f"\n  Total: {g_sym} {total_value:.0f}")
