"""``hbot order-book`` — bid/ask depth for a pair on an exchange.

Read-only public market data, fetched ad-hoc (no running bot): builds a connector, waits for the
order book, reads the top-N levels, tears down. The pair is fuzzy-matched against the exchange's
universe. Snapshot extraction is reused from the interactive ``order_book`` command
(``order_book_rows``); rendering is hbot's compact Markdown table.
"""
import asyncio
from typing import List, Tuple

import typer

from hummingbot.cli.output import ExitCode, echo, fail, render_table


async def _run(ccm, exchange: str, pair: str, lines: int, timeout: float) -> Tuple[List[dict], str, List[str]]:
    from hummingbot.cli.commands._market_data import all_pairs, fetch_order_book, make_connector, resolve_or_fail
    from hummingbot.client.command.order_book_command import order_book_rows
    conn = await make_connector(ccm, exchange, [])
    matched, alts = resolve_or_fail(await asyncio.wait_for(all_pairs(conn), timeout), pair)
    ob = await fetch_order_book(conn, matched, timeout)

    bids, asks = order_book_rows(ob, lines)
    bids, asks = bids.reset_index(drop=True), asks.reset_index(drop=True)
    rows = []
    for i in range(max(len(bids), len(asks))):
        row = {}
        if i < len(bids):
            row["bid_px"] = float(bids.iloc[i]["price"])
            row["bid_amt"] = float(bids.iloc[i]["amount"])
        if i < len(asks):
            row["ask_px"] = float(asks.iloc[i]["price"])
            row["ask_amt"] = float(asks.iloc[i]["amount"])
        rows.append(row)
    return rows, matched, alts


def order_book(
    exchange: str = typer.Argument(..., help="Exchange, e.g. hyperliquid_perpetual or binance."),
    pair: str = typer.Argument(..., help="Trading pair (fuzzy), e.g. ETH-USD, btc/usdt."),
    lines: int = typer.Option(5, "-n", "--lines", help="Number of price levels per side (default 5)."),
) -> None:
    """Show the order-book depth (top levels of bids and asks) for a pair on an exchange."""
    from hummingbot.cli.commands._market_data import _norm
    from hummingbot.client.config.config_helpers import load_client_config_map_from_file
    ccm = load_client_config_map_from_file()  # public market data — no keystore needed
    timeout = float(ccm.commands_timeout.other_commands_timeout)
    try:
        rows, matched, alts = asyncio.run(_run(ccm, exchange, pair, lines, timeout))
    except asyncio.TimeoutError:
        fail("timed out waiting for the order book", ExitCode.TIMEOUT)

    title = f"book {matched} ({exchange})"
    if matched.upper() != _norm(pair):
        title += f" — fuzzy-matched from '{pair}'"
    out = render_table(rows, columns=["bid_px", "bid_amt", "ask_px", "ask_amt"], title=title)
    if alts:
        out += f"\n\nalso matched: {', '.join(alts)}"
    echo(out)
