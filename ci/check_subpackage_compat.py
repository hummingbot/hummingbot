"""Sub-package compatibility checks for CI.

Validates that sub-packages (e.g., candles-feed) remain compatible with
hummingbot's expected interfaces. Three check levels:

1. Import smoke test - packages import without errors
2. Interface contract - expected public API classes/methods exist
3. Integration tests - run sub-package's own compatibility tests (separate pixi task)
"""

import importlib
import sys
from inspect import iscoroutinefunction


def check_imports():
    """Verify all sub-package imports resolve."""
    failures = []

    packages = [
        ("candles_feed", ["__version__"]),
        ("candles_feed.core.candle_data", ["CandleData"]),
        ("candles_feed.core.candles_feed", ["CandlesFeed"]),
        ("candles_feed.core.exchange_registry", ["ExchangeRegistry"]),
        ("candles_feed.core.network_client", ["NetworkClient"]),
        ("candles_feed.core.data_processor", ["DataProcessor"]),
        ("candles_feed.core.collection_strategies", ["WebSocketStrategy", "RESTPollingStrategy"]),
        ("candles_feed.adapters.base_adapter", ["BaseAdapter"]),
        ("candles_feed.integration", ["create_candles_feed_with_hummingbot"]),
    ]

    for module_name, expected_attrs in packages:
        try:
            module = importlib.import_module(module_name)
        except ImportError as e:
            failures.append(f"FAIL: Cannot import {module_name}: {e}")
            continue

        for attr in expected_attrs:
            if not hasattr(module, attr):
                failures.append(f"FAIL: {module_name} missing attribute '{attr}'")

    return failures


def check_contracts():
    """Verify expected public API classes have required methods/attributes."""
    failures = []

    # --- CandlesFeed contract ---
    from candles_feed.core.candles_feed import CandlesFeed

    required_methods = {
        "start": {"async": True},
        "stop": {"async": True},
        "fetch_candles": {"async": True},
        "get_candles_df": {"async": False},
        "add_candle": {"async": False},
    }
    required_attrs = ["trading_pair", "interval", "max_records", "ready", "first_timestamp", "last_timestamp"]

    for method, props in required_methods.items():
        if not hasattr(CandlesFeed, method):
            failures.append(f"FAIL: CandlesFeed missing method '{method}'")
        elif props.get("async") and not iscoroutinefunction(getattr(CandlesFeed, method)):
            failures.append(f"FAIL: CandlesFeed.{method} should be async")

    for attr in required_attrs:
        # Check class or instance-level (properties count)
        if not hasattr(CandlesFeed, attr) and attr not in CandlesFeed.__init__.__code__.co_varnames:
            failures.append(f"FAIL: CandlesFeed missing attribute '{attr}'")

    # --- CandleData contract ---
    from candles_feed.core.candle_data import CandleData

    candle_fields = [
        "timestamp_raw",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "quote_asset_volume",
        "n_trades",
        "taker_buy_base_volume",
        "taker_buy_quote_volume",
    ]
    for field in candle_fields:
        if field not in CandleData.__dataclass_fields__:
            failures.append(f"FAIL: CandleData missing field '{field}'")

    # --- ExchangeRegistry contract ---
    from candles_feed.core.exchange_registry import ExchangeRegistry

    for method in ["get_adapter_instance", "get_registered_exchanges", "discover_adapters"]:
        if not hasattr(ExchangeRegistry, method):
            failures.append(f"FAIL: ExchangeRegistry missing method '{method}'")

    # --- Integration helper contract ---
    import inspect

    from candles_feed.integration import create_candles_feed_with_hummingbot

    sig = inspect.signature(create_candles_feed_with_hummingbot)
    required_params = ["exchange", "trading_pair"]
    for param in required_params:
        if param not in sig.parameters:
            failures.append(f"FAIL: create_candles_feed_with_hummingbot missing param '{param}'")

    # --- DataFrame output contract ---
    from unittest.mock import MagicMock, patch

    mock_adapter = MagicMock()
    mock_adapter.get_trading_pair_format.return_value = "BTCUSDT"
    mock_adapter.get_ws_supported_intervals.return_value = ["1m"]
    mock_adapter.get_supported_intervals.return_value = {"1m": 60}
    mock_adapter.ensure_timestamp_in_seconds = MagicMock(side_effect=lambda x: float(x))

    with patch(
        "candles_feed.core.exchange_registry.ExchangeRegistry.get_adapter_instance",
        return_value=mock_adapter,
    ):
        feed = CandlesFeed(exchange="test", trading_pair="BTC-USDT", interval="1m", max_records=100)
        feed.add_candle(
            CandleData(
                timestamp_raw=1609459200,
                open=40000.0,
                high=41000.0,
                low=39000.0,
                close=40500.0,
                volume=100.0,
                quote_asset_volume=4000000.0,
                n_trades=1000,
                taker_buy_base_volume=50.0,
                taker_buy_quote_volume=2000000.0,
            )
        )
        df = feed.get_candles_df()
        expected_columns = [
            "timestamp",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "quote_asset_volume",
            "n_trades",
            "taker_buy_base_volume",
            "taker_buy_quote_volume",
        ]
        for col in expected_columns:
            if col not in df.columns:
                failures.append(f"FAIL: CandlesFeed.get_candles_df() missing column '{col}'")

    return failures


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "all"

    all_failures = []

    if mode in ("import", "all"):
        print("=" * 60)
        print("Sub-package import smoke test")
        print("=" * 60)
        failures = check_imports()
        all_failures.extend(failures)
        if failures:
            for f in failures:
                print(f"  {f}")
        else:
            print("  OK: All sub-package imports resolved")

    if mode in ("contract", "all"):
        print("=" * 60)
        print("Sub-package interface contract check")
        print("=" * 60)
        failures = check_contracts()
        all_failures.extend(failures)
        if failures:
            for f in failures:
                print(f"  {f}")
        else:
            print("  OK: All interface contracts satisfied")

    if all_failures:
        print(f"\n{'=' * 60}")
        print(f"FAILED: {len(all_failures)} compatibility check(s) failed")
        print(f"{'=' * 60}")
        sys.exit(1)
    else:
        print(f"\n{'=' * 60}")
        print("PASSED: All compatibility checks passed")
        print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
