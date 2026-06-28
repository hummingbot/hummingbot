"""``hbot trades`` — list the bot's recorded fills from its sqlite DB."""
from typing import Optional

import typer

from hummingbot.cli import bot
from hummingbot.cli.output import ExitCode, fail, print_json


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
    json_output: bool = typer.Option(False, "--json", help="Machine-readable JSON output."),
) -> None:
    """List the bot's fills (newest first when limited). Pass a name to view a past/stopped bot."""
    from hummingbot.cli.data import get_trades
    from hummingbot.model.trade_fill import TradeFill
    if name:
        db_path = bot.db_path_for(name)
        if db_path is None:
            fail(f"no trades database for '{name}' (available: {', '.join(bot.list_bots()) or 'none'})",
                 ExitCode.NOT_FOUND, json_output=json_output)
        config_filter = None  # one bot per DB now, so no config_file_path filter needed
    else:
        if not bot.exists():
            fail("no bot has been started (pass a name to view a past bot)",
                 ExitCode.NOT_FOUND, json_output=json_output)
        db_path = bot.resolve_db_path()
        if db_path is None:
            fail("no trades database yet (no fills?)", ExitCode.ERROR, json_output=json_output)
        config_filter = bot.config_file_path()

    fills = get_trades(db_path, config_file_path=config_filter, days=days, limit=limit)

    if json_output:
        print_json({"ok": True, "count": len(fills), "trades": [_trade_to_dict(t) for t in fills]})
        return

    if not fills:
        typer.echo("No trades found.")
        return
    typer.echo(TradeFill.to_pandas(fills).to_string(index=False))
