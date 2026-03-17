"""Source-agnostic spot price feed. Binance primary, Pyth fallback."""
import logging

import requests

logger = logging.getLogger(__name__)


class SpotFeed:
    def __init__(self, config=None):
        self._hermes_url = "https://hermes.pyth.network/v2/updates/price/latest"
        self._cache: dict = {}
        self._cache_ttl = 3.0
        self._timeout = (2.0, 5.0)
        self.core_tickers: set = {"BTC"}

        self._pyth_consecutive_failures = 0
        self._pyth_cb_threshold = 2
        self._pyth_cb_skip_ticks = 10
        self._pyth_cb_ticks_skipped = 0
        self._pyth_cb_tripped = False

        self._binance_url = "https://api.binance.com/api/v3/ticker/price"
        self._binance_failures = 0
        self._binance_cb_threshold = 3
        self._binance_cb_tripped = False
        self._binance_unknown_symbols: set = set()

        self._binance_routed: set = set()
        self._pyth_retry_interval = 50
        self._tick_count = 0

        self._pyth_addresses: dict = {}

    def update_addresses(self, addresses: dict):
        self._pyth_addresses.update(addresses)
        for ticker in addresses:
            self._binance_routed.discard(ticker)

    def get_prices(self, now_ts: float) -> dict:
        self._tick_count += 1

        # Check if all cached prices are fresh
        if self._cache:
            all_fresh = all(now_ts - ts < self._cache_ttl for ts, _ in self._cache.values())
            if all_fresh:
                return {t: p for t, (ts, p) in self._cache.items()}

        all_tickers = set(self._pyth_addresses.keys())
        all_tickers.update(self.core_tickers)

        binance_prices = {}
        for t in all_tickers:
            p = self._fetch_binance(t)
            if p is not None:
                self._cache[t] = (now_ts, p)
                binance_prices[t] = p

        # Fetch Pyth only for tickers Binance did not return
        pyth_tickers = [t for t in all_tickers if t not in binance_prices]
        if pyth_tickers:
            pyth_prices = self._fetch_pyth(pyth_tickers)
            for t, p in pyth_prices.items():
                self._cache[t] = (now_ts, p)

        if not self._cache:
            return {}
        return {t: p for t, (ts, p) in self._cache.items()}

    def _fetch_pyth(self, tickers: list) -> dict:
        if self._pyth_cb_tripped:
            self._pyth_cb_ticks_skipped += 1
            if self._pyth_cb_ticks_skipped < self._pyth_cb_skip_ticks:
                return {}
            # Try recovery
            self._pyth_cb_tripped = False
            self._pyth_cb_ticks_skipped = 0

        feed_ids = []
        ticker_by_id = {}
        for t in tickers:
            fid = self._pyth_addresses.get(t)
            if fid:
                feed_ids.append(fid)
                ticker_by_id[fid] = t

        if not feed_ids:
            return {}

        try:
            params = [("ids[]", fid) for fid in feed_ids]
            resp = requests.get(self._hermes_url, params=params, timeout=self._timeout)
            resp.raise_for_status()
            data = resp.json()

            results = {}
            parsed = data.get("parsed", [])
            for entry in parsed:
                fid = "0x" + entry["id"]
                price_data = entry["price"]
                price = int(price_data["price"]) * (10 ** int(price_data["expo"]))
                ticker = ticker_by_id.get(fid)
                if ticker:
                    results[ticker] = price

            self._pyth_consecutive_failures = 0
            return results

        except Exception as e:
            logger.warning(f"Pyth fetch failed: {e}")
            self._pyth_consecutive_failures += 1
            if self._pyth_consecutive_failures >= self._pyth_cb_threshold:
                self._pyth_cb_tripped = True
                self._pyth_cb_ticks_skipped = 0
                logger.warning("Pyth circuit breaker tripped")
            return {}

    def _fetch_binance(self, ticker: str) -> float | None:
        if ticker in self._binance_unknown_symbols:
            return None
        if self._binance_cb_tripped:
            return None

        symbol = f"{ticker}USDT"
        try:
            resp = requests.get(self._binance_url, params={"symbol": symbol}, timeout=self._timeout)
            if resp.status_code == 400 or resp.status_code == 404:
                self._binance_unknown_symbols.add(ticker)
                return None
            resp.raise_for_status()
            data = resp.json()
            price = float(data["price"])
            self._binance_failures = 0
            return price
        except Exception as e:
            logger.warning(f"Binance fetch failed for {ticker}: {e}")
            self._binance_failures += 1
            if self._binance_failures >= self._binance_cb_threshold:
                self._binance_cb_tripped = True
                logger.warning("Binance circuit breaker tripped")
            return None

    @property
    def is_stale(self) -> bool:
        if not self._cache:
            return True
        import time
        now = time.time()
        return all(now - ts > 5.0 for ts, _ in self._cache.values())
