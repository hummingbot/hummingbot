"""``hbot trades`` — recorded trade fills from the bot's own SQLite.

  hbot trades --json --since 1754270000

The supervisor-side ingestion feed: lossless by construction (the SQLite is
the engine's own trade record, read through hummingbot's model — the file
itself stays behind this CLI contract), cheap to poll (no balance fetches,
unlike ``history``), newest-last. ``--since`` takes a unix timestamp in
SECONDS (fractions allowed) and is inclusive, so a poller resuming from its
last-seen trade re-reads the boundary row and dedups on ``trade_id``.
"""
from typing import Optional

import typer

from hummingbot.cli.output import emit, json_option, render_table


def _row(t) -> dict:
    fee = t.trade_fee if isinstance(t.trade_fee, dict) else {}
    return {
        "ts": t.timestamp / 1000.0,
        "market": t.market,
        "pair": t.symbol,
        "base_asset": t.base_asset,
        "quote_asset": t.quote_asset,
        "side": str(t.trade_type).lower(),
        "order_type": str(t.order_type).lower(),
        "price": str(t.price),
        "amount": str(t.amount),
        "leverage": t.leverage,
        "position": t.position,
        "fee": fee,
        "fee_in_quote": str(t.trade_fee_in_quote) if t.trade_fee_in_quote is not None else None,
        "trade_id": t.exchange_trade_id,
        "order_id": t.order_id,
        "strategy": t.strategy,
        "config_file_path": t.config_file_path,
    }


def trades(
    name: Optional[str] = typer.Argument(
        None, help="Bot name to read (a past/stopped bot). Omit for the current bot."),
    since: Optional[float] = typer.Option(
        None, "--since", help="Only trades at/after this unix timestamp (seconds; inclusive)."),
    limit: Optional[int] = typer.Option(None, "--limit", help="At most N newest trades."),
    as_json: bool = json_option(),
) -> None:
    """List recorded trades (newest last) — the machine-readable ingestion feed."""
    from hummingbot.cli.commands._common import resolve_db_for_command
    from hummingbot.cli.data import get_trades

    db_path, config_filter, _running = resolve_db_for_command(name)
    fills = get_trades(
        db_path,
        config_file_path=config_filter,
        since_ms=int(since * 1000) if since is not None else None,
        limit=limit,
    )
    rows = [_row(t) for t in fills]
    payload = {"count": len(rows), "trades": rows}
    table_cols = ["ts", "market", "pair", "side", "price", "amount", "position", "trade_id"]
    emit(payload, render_table(rows, columns=table_cols, title="trades"), as_json)
