"""``hbot rules`` — show an exchange's trading rules for a pair.

Fetches the connector's trading rules (min order size, min notional, tick/step sizes, supported order
types) for a fuzzy-matched pair — read-only, no running bot. This is the data you need to size a
strategy's orders correctly (e.g. so each order clears the minimum notional).
"""
import asyncio
from typing import List, Tuple

import typer

from hummingbot.cli.output import ExitCode, echo, fail, render_kv


def _rule_dict(rule) -> dict:
    def f(v):
        return float(v) if v is not None else None
    return {
        "trading_pair": rule.trading_pair,
        "min_order_size": f(rule.min_order_size),
        "max_order_size": f(rule.max_order_size),
        "min_notional_size": f(rule.min_notional_size),
        "min_order_value": f(rule.min_order_value),
        "min_price_increment": f(rule.min_price_increment),
        "min_base_amount_increment": f(rule.min_base_amount_increment),
        "min_quote_amount_increment": f(rule.min_quote_amount_increment),
        "supports_limit_orders": bool(rule.supports_limit_orders),
        "supports_market_orders": bool(rule.supports_market_orders),
    }


async def _run(ccm, exchange: str, pair: str, timeout: float) -> Tuple[dict, str, List[str]]:
    from hummingbot.cli.commands._market_data import make_connector, resolve_or_fail, trading_rules_universe
    conn = await make_connector(ccm, exchange, [])
    rules = await asyncio.wait_for(trading_rules_universe(conn), timeout)
    if not rules:
        fail(f"{exchange} returned no trading rules", ExitCode.ERROR)
    matched, alts = resolve_or_fail(list(rules.keys()), pair)
    return _rule_dict(rules[matched]), matched, alts


def rules(
    exchange: str = typer.Argument(..., help="Exchange, e.g. hyperliquid_perpetual or binance."),
    pair: str = typer.Argument(..., help="Trading pair (fuzzy), e.g. ETH-USD, spcx/usd, xyz:tsla-usd."),
) -> None:
    """Show an exchange's trading rules for a pair (min size, min notional, tick/step sizes)."""
    from hummingbot.cli.commands._market_data import _norm
    from hummingbot.client.config.config_helpers import load_client_config_map_from_file
    ccm = load_client_config_map_from_file()  # public market data — no keystore needed
    timeout = float(ccm.commands_timeout.other_commands_timeout)
    try:
        rule, matched, alts = asyncio.run(_run(ccm, exchange, pair, timeout))
    except asyncio.TimeoutError:
        fail("network timeout fetching trading rules", ExitCode.TIMEOUT)

    title = f"rules {matched} ({exchange})"
    if matched.upper() != _norm(pair):
        title += f" — fuzzy-matched from '{pair}'"
    out = render_kv(rule, title=title)
    if alts:
        out += f"\n\nalso matched: {', '.join(alts)}"
    echo(out)
