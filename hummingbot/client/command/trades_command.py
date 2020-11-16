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
from hummingbot.core.utils.market_price import usd_value
from hummingbot.core.data_type.trade import Trade, TradeType
from hummingbot.core.data_type.common import OpenOrder
from hummingbot.client.performance import smart_round

s_float_0 = float(0)
s_decimal_0 = Decimal("0")

if TYPE_CHECKING:
    from hummingbot.client.hummingbot_application import HummingbotApplication


class TradesCommand:
    def trades(self,  # type: HummingbotApplication
               days: float,
               market: str):
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
        connector = UserBalances.connect_market(exchange, **api_keys)
        if market is None:
            orders: List[OpenOrder] = await connector.get_open_orders()
            markets = {o.trading_pair for o in orders}
        else:
            markets = {market.upper()}
        for market in markets:
            await self.market_trades_report(connector, days, market)

    async def market_trades_report(self,  # type: HummingbotApplication
                                   connector,
                                   days: float,
                                   market: str):
        data = []
        columns = ["Time", " Side", " Price", "Amount", " Amount(USD)"]
        trades: List[Trade] = await connector.get_my_trades(market, days)
        trades = sorted(trades, key=lambda x: (x.trading_pair, x.timestamp))
        fees = {}  # a dict of token and total fee amount
        fee_usd = 0
        for trade in trades:
            time = f"{datetime.fromtimestamp(trade.timestamp / 1e3).strftime('%Y-%m-%d %H:%M:%S')} "
            side = "buy" if trade.side is TradeType.BUY else "sell"
            usd = await usd_value(trade.trading_pair.split("-")[0], trade.amount)
            data.append([time, side, smart_round(trade.price), smart_round(trade.amount), round(usd)])
            for fee in trade.trade_fee.flat_fees:
                if fee[0] not in fees:
                    fees[fee[0]] = fee[1]
                else:
                    fees[fee[0]] += fee[1]
                fee_usd += await usd_value(fee[0], fee[1])
        lines = []
        df: pd.DataFrame = pd.DataFrame(data=data, columns=columns)
        lines.extend([f"  {market.upper()}"])
        lines.extend(["    " + line for line in df.to_string(index=False).split("\n")])
        self._notify("\n" + "\n".join(lines))
        fee_text = ",".join(k + ": " + f"{v:.4f}" for k, v in fees.items())
        self._notify(f"\n  Total Amount: $ {df[' Amount(USD)'].sum():.0f}    Fees: {fee_text} ($ {fee_usd:.2f})")
