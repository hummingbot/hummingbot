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
from hummingbot.client.config.security import Security
from hummingbot.user.user_balances import UserBalances
from hummingbot.core.data_type.common import OpenOrder
from hummingbot.core.utils.market_price import usd_value
from hummingbot.connector.exchange.binance.binance_api_order_book_data_source import BinanceAPIOrderBookDataSource

s_float_0 = float(0)
s_decimal_0 = Decimal("0")

if TYPE_CHECKING:
    from hummingbot.client.hummingbot_application import HummingbotApplication


class OpenOrdersCommand:
    def open_orders(self,  # type: HummingbotApplication
                    exchange: str):
        if exchange is None:
            exchange = "binance"
        if threading.current_thread() != threading.main_thread():
            self.ev_loop.call_soon_threadsafe(self.open_orders)
            return
        safe_ensure_future(self.open_orders_report(exchange))

    async def open_orders_report(self,  # type: HummingbotApplication
                                 exchange: str = "binance"):
        api_keys = await Security.api_keys(exchange)
        if not api_keys:
            return
        data = []
        columns = ["Market", " Side", " Spread", " Size(USD)", " Age"]
        mid_prices = await BinanceAPIOrderBookDataSource.get_all_mid_prices()
        connector = UserBalances.connect_market(exchange, **api_keys)
        orders: List[OpenOrder] = await connector.get_open_orders()
        orders = sorted(orders, key=lambda x: (x.trading_pair, x.is_buy))
        for order in orders:
            side = "buy" if order.is_buy else "sell"
            spread = abs(order.price - mid_prices[order.trading_pair]) / mid_prices[order.trading_pair]
            usd = await usd_value(order.trading_pair.split("-")[0], order.amount)
            age = pd.Timestamp((datetime.utcnow().replace(tzinfo=timezone.utc).timestamp() * 1e3 - order.time) / 1e3,
                               unit='s').strftime('%H:%M:%S')
            data.append([order.trading_pair, side, f"{spread:.2%}", round(usd), age])
        lines = []
        orders_df: pd.DataFrame = pd.DataFrame(data=data, columns=columns)
        lines.extend(["    " + line for line in orders_df.to_string(index=False).split("\n")])
        self._notify("\n" + "\n".join(lines))
        self._notify(f"\n  Total: $ {orders_df[' Size(USD)'].sum():.0f}")
