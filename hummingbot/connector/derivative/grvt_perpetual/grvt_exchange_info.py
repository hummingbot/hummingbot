from typing import Any, Dict, Iterable, Mapping


def instrument_is_active(instrument: Mapping[str, Any]) -> bool:
    status = str(instrument.get("status", "")).strip().lower()
    if status in {"", "active", "trading", "online", "enabled"}:
        return True
    return False


def normalize_trading_pair(base: str, quote: str) -> str:
    base_norm = str(base or "").strip().upper()
    quote_norm = str(quote or "").strip().upper()
    return f"{base_norm}-{quote_norm}" if base_norm and quote_norm else ""


def exchange_symbol_to_hb_trading_pair(symbol: str) -> str:
    text = str(symbol or "").strip().upper()
    if "/" in text:
        parts = text.split("/", 1)
        return normalize_trading_pair(parts[0], parts[1])
    if "-" in text:
        parts = text.split("-", 1)
        return normalize_trading_pair(parts[0], parts[1])
    return text


def extract_symbol_map(exchange_info: Iterable[Mapping[str, Any]]) -> Dict[str, str]:
    symbol_map: Dict[str, str] = {}
    for item in exchange_info:
        symbol = str(item.get("symbol") or item.get("market") or item.get("instrument") or "").strip()
        if not symbol:
            continue
        if not instrument_is_active(item):
            continue
        base = item.get("baseAsset") or item.get("base") or item.get("baseCurrency")
        quote = item.get("quoteAsset") or item.get("quote") or item.get("quoteCurrency")
        hb_pair = normalize_trading_pair(base, quote) if base and quote else exchange_symbol_to_hb_trading_pair(symbol)
        if hb_pair:
            symbol_map[symbol] = hb_pair
    return symbol_map
