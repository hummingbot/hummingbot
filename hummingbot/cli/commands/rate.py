"""``hbot rate`` — the rate oracle's conversion rate for a trading pair.

Public data (no keystore): asks the configured rate oracle what 1 BASE is worth in QUOTE. The source
is the global ``rate_oracle_source`` setting (see ``hbot config``). Mirrors the interactive client's
``rate``.
"""
import asyncio

import typer

from hummingbot.cli.output import ExitCode, echo, fail, render_kv


async def _fetch_rate(pair: str, timeout: float):
    from hummingbot.core.rate_oracle.rate_oracle import RateOracle
    ro = RateOracle.get_instance()
    rate = await asyncio.wait_for(ro.rate_async(pair), timeout)
    return rate, ro.source.name


def rate(
    pair: str = typer.Argument(..., help="Trading pair, e.g. ETH-USDT or btc-usd."),
) -> None:
    """Show the rate oracle's conversion rate for a trading pair."""
    from hummingbot.client.config.config_helpers import load_client_config_map_from_file
    from hummingbot.connector.utils import split_hb_trading_pair, validate_trading_pair
    ccm = load_client_config_map_from_file()  # configures the rate-oracle source; public data, no keystore
    timeout = float(ccm.commands_timeout.other_commands_timeout)

    norm = pair.upper().strip('"').strip("'")
    if not validate_trading_pair(norm):
        fail(f"invalid trading pair '{pair}' (expected BASE-QUOTE)", ExitCode.CONFIG_ERROR)

    try:
        value, source = asyncio.run(_fetch_rate(norm, timeout))
    except asyncio.TimeoutError:
        fail("timed out fetching the rate", ExitCode.TIMEOUT)
    if value is None:
        fail(f"rate not available for {norm}", ExitCode.NOT_FOUND)

    base, quote = split_hb_trading_pair(norm)
    echo(render_kv({"pair": norm, "rate": f"1 {base} = {value} {quote}", "source": source},
                   title=f"rate {norm}"))
