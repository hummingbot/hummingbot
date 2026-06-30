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
from hummingbot.cli.password import login


async def _run(ccm, exchange: str, pair: str, timeout: float) -> Tuple[dict, str, List[str]]:
    from hummingbot.cli.commands._market_data import all_pairs, make_connector, resolve_or_fail, wait_orderbook_ready
    from hummingbot.client.command.ticker_command import get_ticker_prices
    lister = await make_connector(ccm, exchange, [])
    matched, alts = resolve_or_fail(await asyncio.wait_for(all_pairs(lister), timeout), pair)

    conn = await make_connector(ccm, exchange, [matched])
    try:
        await asyncio.wait_for(wait_orderbook_ready(conn, timeout), timeout)
        prices = get_ticker_prices(conn, matched)
    finally:
        await conn.stop_network()
    return prices, matched, alts


def ticker(
    exchange: str = typer.Argument(..., help="Exchange, e.g. hyperliquid_perpetual or binance."),
    pair: str = typer.Argument(..., help="Trading pair (fuzzy), e.g. ETH-USD, btc/usdt."),
    password_stdin: bool = typer.Option(
        False, "--password-stdin", help="Read the keystore password from stdin (else $HBOT_PASSWORD or a prompt)."),
) -> None:
    """Show best bid, ask, mid, and last price for a pair on an exchange."""
    from hummingbot.cli.commands._market_data import _norm
    ccm, _ = login(password_stdin=password_stdin)
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
