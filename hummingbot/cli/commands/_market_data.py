"""Shared helpers for the public market-data commands (``rules`` / ``ticker`` / ``order-book``).

These commands fetch public exchange data ad-hoc — without a running strategy — by building a
connector with ``trading_required=False`` (read-only), querying it, and tearing it down. Stored API
keys are used if the exchange is connected (some connectors, e.g. Hyperliquid, need a key just to
construct); otherwise a clear "connect first" error is raised.

Pair resolution is **fuzzy**: a loose query like ``xyz:spcx-usd`` / ``spcx/usd`` / ``ETHUSD`` is
matched against the exchange's real pair universe (which, for Hyperliquid, includes HIP-3
dex-prefixed markets like ``XYZ:TSLA-USD``).
"""
import asyncio
import difflib
from typing import List, Optional, Tuple

from hummingbot.cli.output import ExitCode, fail


def _norm(s: str) -> str:
    """Normalize separators/case so 'xyz:spcx-usd', 'XYZ;SPCX/USD', 'spcx_usd' compare alike."""
    return s.upper().replace(";", ":").replace("_", "-").replace("/", "-").strip()


def _flat(s: str) -> str:
    return s.replace(":", "").replace("-", "")


def fuzzy_match_pair(candidates: List[str], query: str) -> Tuple[Optional[str], List[str]]:
    """Match ``query`` against ``candidates``. Returns (best, alternatives).

    Order of preference: exact (normalized) → substring (also separator-insensitive) → difflib.
    ``alternatives`` holds other plausible matches to suggest when the result is ambiguous.
    """
    qn = _norm(query)
    by_norm = {_norm(c): c for c in candidates}
    if qn in by_norm:
        return by_norm[qn], []
    subs = {orig for n, orig in by_norm.items() if qn in n or _flat(qn) in _flat(n)}
    ranked = sorted(subs, key=lambda c: difflib.SequenceMatcher(None, qn, _norm(c)).ratio(), reverse=True)
    if ranked:
        return ranked[0], ranked[1:8]
    close = difflib.get_close_matches(qn, list(by_norm), n=8, cutoff=0.5)
    if close:
        return by_norm[close[0]], [by_norm[c] for c in close[1:]]
    return None, []


async def make_connector(ccm, exchange: str, trading_pairs: List[str]):
    """Build a read-only connector for ``exchange``, using stored keys if the exchange is connected."""
    from hummingbot.client.config.security import Security
    from hummingbot.client.settings import AllConnectorSettings
    from hummingbot.core.connector_manager import ConnectorManager
    if exchange not in AllConnectorSettings.get_connector_settings():
        fail(f"unknown exchange '{exchange}'", ExitCode.CONFIG_ERROR)
    await Security.wait_til_decryption_done()
    try:
        return ConnectorManager(ccm).create_connector(exchange, trading_pairs, trading_required=False)
    except ValueError:
        fail(f"no API keys stored for '{exchange}' — run `hbot connect {exchange}` first",
             ExitCode.CONFIG_ERROR)


async def trading_rules_universe(connector) -> dict:
    """Fetch the exchange's trading rules (one entry per pair) without starting the network."""
    await connector._update_trading_rules()
    return connector.trading_rules


async def all_pairs(connector) -> List[str]:
    """The exchange's full tradable-pair list (a public REST fetch; no network start needed)."""
    return await connector.all_trading_pairs()


def resolve_or_fail(candidates: List[str], query: str) -> Tuple[str, List[str]]:
    """Fuzzy-resolve ``query`` to a real pair, or fail NOT_FOUND with the closest suggestions."""
    best, alts = fuzzy_match_pair(candidates, query)
    if best is None:
        close = ", ".join(difflib.get_close_matches(_norm(query), [_norm(c) for c in candidates], n=6, cutoff=0.3))
        msg = f"no trading pair matches '{query}'"
        if close:
            msg += f" (closest: {close})"
        fail(msg, ExitCode.NOT_FOUND)
    return best, alts


async def fetch_order_book(connector, trading_pair: str, timeout: float):
    """One-shot order-book snapshot via a single REST call (``get_new_order_book``) — no websocket
    tracker, no ``start_network``.

    Standalone ticker/order-book queries only need a current snapshot, not a streaming book. Warming
    the full order-book tracker (websocket subscribe + readiness poll) cost ~4-9s; the direct snapshot
    is ~0.2s once the symbol map is warm (the caller fetches the pair universe first for fuzzy match,
    which warms it). Returns an ``OrderBook`` so the existing snapshot rendering is unchanged.
    """
    ds = connector.order_book_tracker.data_source
    return await asyncio.wait_for(ds.get_new_order_book(trading_pair), timeout)
