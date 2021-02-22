from decimal import Decimal
from datetime import datetime, timezone
from hummingbot.core.data_type.trade import Trade, TradeType, TradeFee
from hummingbot.connector.exchange.binance.binance_utils import (
    convert_from_exchange_trading_pair,
)


def get_utc_timestamp(days_ago: float = 0.) -> float:
    return datetime.utcnow().replace(tzinfo=timezone.utc).timestamp() - (60. * 60. * 24. * days_ago)


def format_trades(trades):
    ret_val = []
    for trade in trades:
        sum_trades = [t for t in trades if t["symbol"] == trade["symbol"] and t["orderId"] == trade["orderId"]
                      and t["price"] == trade["price"]]
        if not sum_trades:
            continue
        amount = sum(Decimal(str(t["qty"])) for t in sum_trades)
        time = sum_trades[-1]["time"]
        commission = sum(Decimal(str(t["commission"])) for t in sum_trades)

        ret_val.append(
            Trade(
                trading_pair=convert_from_exchange_trading_pair(trade["symbol"]),
                side=TradeType.BUY if trade["isBuyer"] else TradeType.SELL,
                price=Decimal(str(trade["price"])),
                amount=amount,
                order_type=None,
                market=convert_from_exchange_trading_pair(trade["symbol"]),
                timestamp=int(time),
                trade_fee=TradeFee(0.0, [(trade["commissionAsset"], commission)]),
            )
        )
        trades = [t for t in trades if t not in sum_trades]
    return ret_val
