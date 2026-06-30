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


def _public_dummy_keys(conn_setting) -> dict:
    """A throwaway key set so a connector can be CONSTRUCTED for PUBLIC reads without the user's
    keystore — market data (order book, trading rules, ticker) is public and needs no auth.

    The keys are never used to sign (``trading_required=False``); they only satisfy connectors that
    require a valid-format key just to build their auth object (e.g. Hyperliquid wants an eth key).
    A freshly generated, immediately-discarded eth key covers that; other fields get their default or
    a benign placeholder.
    """
    cfg = conn_setting.config_keys
    if cfg is None:
        return {}
    from eth_account import Account
    acct = Account.create()
    keys = {}
    for name, field in cfg.__class__.model_fields.items():
        if name == "connector":
            continue
        low = name.lower()
        default = field.default
        if "secret" in low or "private" in low or ("key" in low and "api" in low):
            keys[name] = acct.key.hex()
        elif "address" in low or "account" in low or "wallet" in low:
            keys[name] = acct.address
        elif default is not None and str(default) != "PydanticUndefined":
            keys[name] = default
        else:
            keys[name] = "0"
    return keys


async def make_connector(ccm, exchange: str, trading_pairs: List[str]):
    """Build a read-only connector for PUBLIC market data — no keystore required.

    Market data is public, so this never unlocks the user's keystore: it constructs the connector
    with throwaway keys and ``trading_required=False``. Only ``hbot connect`` (which *stores* keys)
    needs the keystore.
    """
    from hummingbot.client.settings import AllConnectorSettings
    from hummingbot.core.connector_manager import ConnectorManager
    settings = AllConnectorSettings.get_connector_settings()
    if exchange not in settings:
        fail(f"unknown exchange '{exchange}'", ExitCode.CONFIG_ERROR)
    try:
        return ConnectorManager(ccm).create_connector(
            exchange, trading_pairs, trading_required=False, api_keys=_public_dummy_keys(settings[exchange]))
    except Exception as e:
        fail(f"could not open a read-only connector for '{exchange}': {e}", ExitCode.ERROR)


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
