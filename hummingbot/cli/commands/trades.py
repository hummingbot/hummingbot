"""``hbot trades`` — list a bot's recorded fills from its sqlite DB."""
from pathlib import Path
from typing import Optional

import typer

from hummingbot import data_path
from hummingbot.cli.data import get_trades
from hummingbot.cli.instances import Instance
from hummingbot.cli.output import ExitCode, fail, print_json
from hummingbot.model.trade_fill import TradeFill


def _resolve_db_path(instance: Instance) -> Optional[str]:
    db_path = instance.db_path()
    if db_path and Path(db_path).exists():
        return db_path
    fallback = Path(data_path()) / f"{instance.name}.sqlite"
    return str(fallback) if fallback.exists() else None


def _trade_to_dict(t: TradeFill) -> dict:
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
    name: str = typer.Argument(..., help="Instance id."),
    limit: Optional[int] = typer.Option(None, "--limit", help="Max trades to return (most recent)."),
    days: Optional[float] = typer.Option(None, "--days", help="Only trades from the last N days."),
    json_output: bool = typer.Option(False, "--json", help="Machine-readable JSON output."),
) -> None:
    """List the bot's fills, newest first when limited."""
    instance = Instance(name)
    if not instance.exists():
        fail(f"instance '{name}' not found", ExitCode.NOT_FOUND, json_output=json_output)

    db_path = _resolve_db_path(instance)
    if db_path is None:
        fail(f"no trades database found for '{name}' (no fills yet?)",
             ExitCode.ERROR, json_output=json_output)

    fills = get_trades(db_path, config_file_path=instance.config_file_path(), days=days, limit=limit)

    if json_output:
        print_json({"ok": True, "name": name, "count": len(fills),
                    "trades": [_trade_to_dict(t) for t in fills]})
        return

    if not fills:
        typer.echo("No trades found.")
        return
    typer.echo(TradeFill.to_pandas(fills).to_string(index=False))
