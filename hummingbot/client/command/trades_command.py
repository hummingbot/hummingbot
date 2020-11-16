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
from hummingbot.core.utils.market_price import usd_value
from hummingbot.core.data_type.trade import Trade, TradeType

s_float_0 = float(0)
s_decimal_0 = Decimal("0")

if TYPE_CHECKING:
    from hummingbot.client.hummingbot_application import HummingbotApplication


def get_utc_timestamp(days_ago: float = 0.) -> float:
    return datetime.utcnow().replace(tzinfo=timezone.utc).timestamp() - (60. * 60. * 24. * days_ago)


class TradesCommand:
    def trades(self,  # type: HummingbotApplication
               days: float,
               market: str):
        if market is None:
            market = "HARD-USDT"
        market = market.upper()
        if threading.current_thread() != threading.main_thread():
            self.ev_loop.call_soon_threadsafe(self.trades)
            return
        safe_ensure_future(self.trades_report(days, market))

    async def trades_report(self,  # type: HummingbotApplication
                            days: float,
                            market: str):
        exchange = "binance"
        api_keys = await Security.api_keys(exchange)
        if not api_keys:
            return
        data = []
        columns = ["Side", " Price", "Amount", " Amount(USD)"]
        connector = UserBalances.connect_market(exchange, **api_keys)
        timestamp = get_utc_timestamp(days) * 1e3
        trades: List[Trade] = await connector.get_my_trades(market, int(timestamp))
        trades = sorted(trades, key=lambda x: (x.trading_pair, x.timestamp))
        for trade in trades:
            side = "buy" if trade.side is TradeType.BUY else "sell"
            usd = await usd_value(trade.trading_pair.split("-")[0], trade.amount)
            data.append([side, f"{trade.price:.4f}", f"{trade.amount:.4f}", round(usd)])
        lines = []
        df: pd.DataFrame = pd.DataFrame(data=data, columns=columns)
        lines.extend([f"    {market.upper()}"])
        lines.extend(["    " + line for line in df.to_string(index=False).split("\n")])
        self._notify("\n" + "\n".join(lines))
        self._notify(f"\n  Total: $ {df[' Amount(USD)'].sum():.0f}")
