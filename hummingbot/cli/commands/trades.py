"""``hbot trades`` — list the bot's recorded fills from its sqlite DB."""
from typing import Optional

import typer

from hummingbot.cli.output import echo, render_table


def _trade_to_dict(t) -> dict:
    return {
        "id": t.exchange_trade_id,
        "timestamp": t.timestamp,
        "market": t.market,
        "trading_pair": t.symbol,
        "side": t.trade_type,
        "order_type": t.order_type,
        "price": float(t.price),
        "amount": float(t.amount),
        "leverage": t.leverage,
        "position": t.position,
    }


def trades(
    name: Optional[str] = typer.Argument(None, help="Bot name to view (a past/stopped bot). Omit for the current bot."),
    limit: Optional[int] = typer.Option(None, "--limit", help="Max trades to return (most recent)."),
    days: Optional[float] = typer.Option(None, "--days", help="Only trades from the last N days."),
) -> None:
    """List the trades the bot has made."""
    from hummingbot.cli.commands._common import resolve_db_for_command
    from hummingbot.cli.data import get_trades
    db_path, config_filter, _running = resolve_db_for_command(name)
    fills = get_trades(db_path, config_file_path=config_filter, days=days, limit=limit)

    title = f"trades {name}" if name else "trades"
    echo(render_table([_trade_to_dict(t) for t in fills], title=title))
