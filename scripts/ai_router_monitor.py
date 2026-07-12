#!/usr/bin/env python3
import argparse
import json
import re
import sqlite3
import subprocess
import time
from collections import Counter, deque
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple


DECIMAL_SCALE = Decimal("1000000")


@dataclass
class RouterDecision:
    log_time: str
    regime: str
    action: str
    active: str
    recommended: str
    confidence: Decimal
    scale: Decimal
    reasons: str


@dataclass
class FillEvent:
    timestamp: Decimal
    side: str
    order_type: str
    price: Decimal
    amount: Decimal
    fee_quote: Decimal
    order_id: str
    trade_id: str


DECISION_RE = re.compile(
    r"^(?P<time>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3}).*AI Router decision: "
    r"regime=(?P<regime>[^,]+), action=(?P<action>[^,]+), active=(?P<active>[^,]+), "
    r"recommended=(?P<recommended>[^,]+), confidence=(?P<confidence>[0-9.]+), "
    r"scale=(?P<scale>[0-9.]+), reasons=(?P<reasons>.*)$"
)


def decimal_from_db(value) -> Decimal:
    if value is None:
        return Decimal("0")
    return Decimal(value) / DECIMAL_SCALE


def decimal_from_json(value, default: str = "0") -> Decimal:
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError):
        return Decimal(default)


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def tail_lines(path: Path, max_lines: int) -> List[str]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", errors="replace") as file:
        return list(deque(file, maxlen=max_lines))


def parse_router_decisions(lines: Iterable[str]) -> List[RouterDecision]:
    decisions = []
    for line in lines:
        match = DECISION_RE.search(line)
        if not match:
            continue
        decisions.append(RouterDecision(
            log_time=match.group("time"),
            regime=match.group("regime"),
            action=match.group("action"),
            active=match.group("active"),
            recommended=match.group("recommended"),
            confidence=decimal_from_json(match.group("confidence")),
            scale=decimal_from_json(match.group("scale")),
            reasons=match.group("reasons"),
        ))
    return decisions


def parse_event_json(line: str) -> Optional[dict]:
    marker = "EVENT_LOG - "
    if marker not in line:
        return None
    raw = line.split(marker, 1)[1].strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


def fee_in_quote(event: dict) -> Decimal:
    trade_fee = event.get("trade_fee") or {}
    percent = decimal_from_json(trade_fee.get("percent"))
    price = decimal_from_json(event.get("price"))
    amount = decimal_from_json(event.get("amount"))
    flat_total = Decimal("0")
    for flat_fee in trade_fee.get("flat_fees") or []:
        flat_total += decimal_from_json(flat_fee.get("amount"))
    return price * amount * percent + flat_total


def parse_fill_events(lines: Iterable[str]) -> List[FillEvent]:
    fills = []
    for line in lines:
        event = parse_event_json(line)
        if not event or event.get("event_name") != "OrderFilledEvent":
            continue
        fills.append(FillEvent(
            timestamp=decimal_from_json(event.get("timestamp")),
            side=str(event.get("trade_type", "")).replace("TradeType.", ""),
            order_type=str(event.get("order_type", "")).replace("OrderType.", ""),
            price=decimal_from_json(event.get("price")),
            amount=decimal_from_json(event.get("amount")),
            fee_quote=fee_in_quote(event),
            order_id=str(event.get("order_id", "")),
            trade_id=str(event.get("exchange_trade_id", "")),
        ))
    return fills


def latest_event_price(lines: Iterable[str]) -> Optional[Decimal]:
    latest = None
    for line in lines:
        event = parse_event_json(line)
        if not event:
            continue
        price = decimal_from_json(event.get("price"))
        if price > 0:
            latest = price
    return latest


def db_query(db_path: Path, sql: str, params: Tuple = ()) -> List[tuple]:
    if not db_path.exists():
        return []
    with sqlite3.connect(db_path) as conn:
        return conn.execute(sql, params).fetchall()


def db_counts(db_path: Path) -> Dict[str, int]:
    result = {
        "orders": 0,
        "fills": 0,
    }
    rows = db_query(db_path, 'select count(*) from "Order"')
    if rows:
        result["orders"] = int(rows[0][0])
    rows = db_query(db_path, "select count(*) from TradeFill")
    if rows:
        result["fills"] = int(rows[0][0])
    return result


def db_status_counts(db_path: Path) -> Counter:
    rows = db_query(db_path, 'select last_status, count(*) from "Order" group by last_status order by count(*) desc')
    return Counter({str(status): int(count) for status, count in rows})


def db_recent_orders(db_path: Path, limit: int) -> List[dict]:
    rows = db_query(
        db_path,
        """
        select creation_timestamp, id, order_type, amount, price, last_status
        from "Order"
        order by creation_timestamp desc
        limit ?
        """,
        (limit,),
    )
    return [
        {
            "time": datetime.fromtimestamp(ts / 1000).strftime("%Y-%m-%d %H:%M:%S"),
            "id": order_id,
            "order_type": order_type,
            "amount": decimal_from_db(amount),
            "price": decimal_from_db(price),
            "status": status,
        }
        for ts, order_id, order_type, amount, price, status in rows
    ]


def estimate_pnl(fills: List[FillEvent], mark_price: Optional[Decimal]) -> Dict[str, Decimal]:
    base = Decimal("0")
    quote = Decimal("0")
    fees = Decimal("0")
    buy_quote = Decimal("0")
    sell_quote = Decimal("0")
    for fill in fills:
        notional = fill.price * fill.amount
        fees += fill.fee_quote
        if fill.side == "BUY":
            base += fill.amount
            quote -= notional + fill.fee_quote
            buy_quote += notional
        elif fill.side == "SELL":
            base -= fill.amount
            quote += notional - fill.fee_quote
            sell_quote += notional
    mark = mark_price or Decimal("0")
    equity = quote + base * mark
    return {
        "base": base,
        "quote_cash": quote,
        "fees_quote": fees,
        "buy_quote": buy_quote,
        "sell_quote": sell_quote,
        "mark_price": mark,
        "equity_quote": equity,
    }


def docker_status(container: str) -> str:
    try:
        result = subprocess.run(
            ["docker", "ps", "-a", "--filter", f"name={container}", "--format", "{{.Status}}"],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=False,
            timeout=5,
        )
    except Exception:
        return "Docker 不可用"
    status = result.stdout.strip()
    return status or "未找到"


def fmt_decimal(value: Decimal, places: int = 6) -> str:
    quant = Decimal("1").scaleb(-places)
    return f"{value.quantize(quant):f}"


def fmt_money(value: Decimal) -> str:
    return fmt_decimal(value, 4)


def render_report(
    db_path: Path,
    log_path: Path,
    container: str,
    log_lines: int,
    recent: int,
) -> str:
    lines = tail_lines(log_path, log_lines)
    decisions = parse_router_decisions(lines)
    fills = parse_fill_events(lines)
    mark_price = latest_event_price(lines)
    pnl = estimate_pnl(fills, mark_price)
    counts = db_counts(db_path)
    status_counts = db_status_counts(db_path)
    recent_orders = db_recent_orders(db_path, recent)
    latest_decision = decisions[-1] if decisions else None
    latest_protect = next((d for d in reversed(decisions) if d.action == "protect"), None)
    fill_sides = Counter(fill.side for fill in fills)

    report = []
    report.append("AI 策略路由器监控")
    report.append(f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report.append(f"容器：{container} | {docker_status(container)}")
    report.append(f"数据库：{db_path}")
    report.append(f"日志：{log_path}")
    report.append("")

    if latest_decision:
        report.append(
            "路由器："
            f"{latest_decision.regime} / {latest_decision.action} -> {latest_decision.recommended} "
            f"（当前策略={latest_decision.active}，置信度={latest_decision.confidence}，"
            f"仓位系数={latest_decision.scale}，原因={latest_decision.reasons}）"
        )
    else:
        report.append("路由器：解析的日志窗口中没有找到决策")
    if latest_protect:
        report.append(
            "最近一次保护："
            f"{latest_protect.log_time} | 当前策略={latest_protect.active} | 原因={latest_protect.reasons}"
        )
    report.append("")

    status_text = ", ".join(f"{status}={count}" for status, count in status_counts.items()) or "无"
    report.append(
        f"订单／成交：订单={counts['orders']} | 成交={counts['fills']} | "
        f"已解析成交={len(fills)} | 买入={fill_sides.get('BUY', 0)} | 卖出={fill_sides.get('SELL', 0)}"
    )
    report.append(f"订单状态：{status_text}")
    report.append("")

    report.append(
        "根据成交估算盈亏："
        f"基础资产={fmt_decimal(pnl['base'], 8)} BTC | "
        f"计价现金={fmt_money(pnl['quote_cash'])} USDT | "
        f"费用={fmt_money(pnl['fees_quote'])} USDT | "
        f"标记价格={fmt_money(pnl['mark_price'])} | "
        f"权益={fmt_money(pnl['equity_quote'])} USDT"
    )
    report.append(
        f"成交额：买入={fmt_money(pnl['buy_quote'])} USDT | 卖出={fmt_money(pnl['sell_quote'])} USDT"
    )
    report.append("")

    report.append("最近订单：")
    if recent_orders:
        for order in recent_orders:
            report.append(
                f"- {order['time']} | {order['order_type']} | "
                f"{fmt_decimal(order['amount'], 8)} BTC @ {fmt_money(order['price'])} | {order['status']}"
            )
    else:
        report.append("- 无")

    report.append("")
    report.append("最近成交：")
    if fills:
        for fill in fills[-recent:][::-1]:
            report.append(
                f"- {datetime.fromtimestamp(float(fill.timestamp)).strftime('%Y-%m-%d %H:%M:%S')} | "
                f"{fill.side} {fill.order_type} | {fmt_decimal(fill.amount, 8)} BTC @ "
                f"{fmt_money(fill.price)} | fee={fmt_money(fill.fee_quote)}"
            )
    else:
        report.append("- 无")

    return "\n".join(report)


def main():
    root = repo_root()
    parser = argparse.ArgumentParser(description="监控 AI 策略路由器的纸面运行。")
    parser.add_argument("--db", default=str(root / "data" / "conf_ai_strategy_router_paper.sqlite"))
    parser.add_argument("--log", default=str(root / "logs" / "logs_conf_ai_strategy_router_paper.log"))
    parser.add_argument("--container", default="hummingbot-ai-router-paper")
    parser.add_argument("--log-lines", type=int, default=100000)
    parser.add_argument("--recent", type=int, default=8)
    parser.add_argument("--watch", type=int, default=0, help="每 N 秒刷新一次；0 表示只输出一次。")
    parser.add_argument("--report", default="", help="可选的 Markdown 或文本报告输出路径。")
    args = parser.parse_args()

    db_path = Path(args.db).expanduser().resolve()
    log_path = Path(args.log).expanduser().resolve()
    report_path = Path(args.report).expanduser().resolve() if args.report else None

    while True:
        output = render_report(
            db_path=db_path,
            log_path=log_path,
            container=args.container,
            log_lines=args.log_lines,
            recent=args.recent,
        )
        print(output)
        if report_path:
            report_path.parent.mkdir(parents=True, exist_ok=True)
            report_path.write_text(output + "\n", encoding="utf-8")
        if args.watch <= 0:
            break
        print("\n" + "=" * 80 + "\n")
        time.sleep(args.watch)


if __name__ == "__main__":
    main()
