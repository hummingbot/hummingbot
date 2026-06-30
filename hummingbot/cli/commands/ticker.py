"""``hbot ticker`` — best bid/ask/mid/last for a pair on an exchange.

Read-only public market data, fetched ad-hoc (no running bot): builds a connector, waits for the
order book, reads the prices, tears down. The pair is fuzzy-matched against the exchange's universe.
Price fetching is reused from the interactive ``ticker`` command (``get_ticker_prices``); rendering
is hbot's compact Markdown.
"""
import asyncio
from typing import List, Tuple

import typer

from hummingbot.cli.output import ExitCode, echo, fail, render_kv


async def _run(ccm, exchange: str, pair: str, timeout: float) -> Tuple[dict, str, List[str]]:
    from hummingbot.cli.commands._market_data import all_pairs, fetch_order_book, make_connector, resolve_or_fail
    conn = await make_connector(ccm, exchange, [])
    matched, alts = resolve_or_fail(await asyncio.wait_for(all_pairs(conn), timeout), pair)
    ob = await fetch_order_book(conn, matched, timeout)

    bids, asks = ob.snapshot[0], ob.snapshot[1]
    best_bid = float(bids.iloc[0]["price"]) if len(bids) else None
    best_ask = float(asks.iloc[0]["price"]) if len(asks) else None
    mid = (best_bid + best_ask) / 2 if best_bid is not None and best_ask is not None else None
    # last_trade is a streaming value; a one-shot REST snapshot may not carry it (then None).
    last = None
    try:
        v = float(ob.last_trade_price)
        if v and v == v:  # exclude 0 and NaN (NaN != NaN)
            last = v
    except Exception:
        pass
    prices = {"best_bid": best_bid, "best_ask": best_ask, "mid_price": mid, "last_trade": last}
    return prices, matched, alts


def ticker(
    exchange: str = typer.Argument(..., help="Exchange, e.g. hyperliquid_perpetual or binance."),
    pair: str = typer.Argument(..., help="Trading pair (fuzzy), e.g. ETH-USD, btc/usdt."),
) -> None:
    """Show best bid, ask, mid, and last price for a pair on an exchange."""
    from hummingbot.cli.commands._market_data import _norm
    from hummingbot.client.config.config_helpers import load_client_config_map_from_file
    ccm = load_client_config_map_from_file()  # public market data — no keystore needed
    timeout = float(ccm.commands_timeout.other_commands_timeout)
    try:
        prices, matched, alts = asyncio.run(_run(ccm, exchange, pair, timeout))
    except asyncio.TimeoutError:
        fail("timed out waiting for the order book", ExitCode.TIMEOUT)

    title = f"ticker {matched} ({exchange})"
    if matched.upper() != _norm(pair):
        title += f" — fuzzy-matched from '{pair}'"
    out = render_kv(prices, title=title)
    if alts:
        out += f"\n\nalso matched: {', '.join(alts)}"
    echo(out)
