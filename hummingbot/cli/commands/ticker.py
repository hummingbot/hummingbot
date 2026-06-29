"""``hbot ticker`` — best bid/ask/mid/last for a pair on an exchange.

Read-only public market data, fetched ad-hoc (no running bot): builds a connector, waits for the
order book, reads the prices, tears down. The pair is fuzzy-matched against the exchange's universe.
Price fetching and table rendering are reused from the interactive ``ticker`` command
(``hummingbot.client.command.ticker_command``).
"""
import asyncio
from typing import List, Tuple

import typer

from hummingbot.cli.output import ExitCode, fail, print_json
from hummingbot.cli.password import login


async def _run(ccm, exchange: str, pair: str, timeout: float, json_output: bool) -> Tuple[dict, str, str, List[str]]:
    from hummingbot.cli.commands._market_data import all_pairs, make_connector, resolve_or_fail, wait_orderbook_ready
    from hummingbot.client.command.ticker_command import format_ticker, get_ticker_prices
    lister = await make_connector(ccm, exchange, [], json_output)
    matched, alts = resolve_or_fail(await asyncio.wait_for(all_pairs(lister), timeout), pair, json_output)

    conn = await make_connector(ccm, exchange, [matched], json_output)
    try:
        await asyncio.wait_for(wait_orderbook_ready(conn, timeout), timeout)
        prices = get_ticker_prices(conn, matched)
        text = format_ticker(conn, matched, ccm.tables_format)
    finally:
        await conn.stop_network()
    return prices, text, matched, alts


def ticker(
    exchange: str = typer.Argument(..., help="Exchange, e.g. hyperliquid_perpetual or binance."),
    pair: str = typer.Argument(..., help="Trading pair (fuzzy), e.g. ETH-USD, btc/usdt."),
    password_stdin: bool = typer.Option(
        False, "--password-stdin", help="Read the keystore password from stdin (else $HBOT_PASSWORD or a prompt)."),
    json_output: bool = typer.Option(False, "--json", help="Machine-readable JSON output."),
) -> None:
    """Show best bid, ask, mid, and last price for a pair on an exchange."""
    from hummingbot.cli.commands._market_data import _norm
    ccm, _ = login(password_stdin=password_stdin, json_output=json_output)
    timeout = float(ccm.commands_timeout.other_commands_timeout)
    try:
        prices, text, matched, alts = asyncio.run(_run(ccm, exchange, pair, timeout, json_output))
    except asyncio.TimeoutError:
        fail("timed out waiting for the order book", ExitCode.TIMEOUT, json_output=json_output)

    if json_output:
        print_json({"ok": True, "exchange": exchange, "query": pair, "matched": matched,
                    "alternatives": alts, "ticker": prices})
    else:
        header = f"  pair: {matched}"
        if matched.upper() != _norm(pair):
            header += f"   [fuzzy-matched from '{pair}']"
        out = f"{header}\n{text}"
        if alts:
            out += f"\n  also matched: {', '.join(alts)}"
        typer.echo(out)
