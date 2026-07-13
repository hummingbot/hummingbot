#!/usr/bin/env python3
"""Synchronize Binance Spot fees for the paper-trading cost model.

This script only calls Binance's signed USER_DATA account endpoint. It never
places, cancels, or modifies an exchange order. When read-only credentials are
not configured, it writes the documented standard fee fallback so a paper run
still has a conservative, explicit cost model.
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import re
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path


DEFAULT_GROSS_FEE_BPS = Decimal("10")
DEFAULT_REBATE_RATE = Decimal("0.40")
BINANCE_ACCOUNT_URL = "https://api.binance.com/api/v3/account"


@dataclass(frozen=True)
class FeeProfile:
    exchange: str
    source: str
    checked_at: str
    maker_fee_bps_gross: str
    taker_fee_bps_gross: str
    rebate_rate: str
    maker_fee_bps_net: str
    taker_fee_bps_net: str
    query_error: str | None = None


def decimal(value: object, field: str) -> Decimal:
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"Binance returned an invalid {field} value") from exc
    if parsed < 0:
        raise ValueError(f"Binance returned a negative {field} value")
    return parsed


def bps_from_account(payload: dict[str, object]) -> tuple[Decimal, Decimal]:
    """Read current account commission rates without guessing VIP or BNB tiers."""
    rates = payload.get("commissionRates")
    if isinstance(rates, dict) and "maker" in rates and "taker" in rates:
        return decimal(rates["maker"], "maker commission") * Decimal("10000"), decimal(rates["taker"], "taker commission") * Decimal("10000")

    # Older Binance account responses use integer commission values in 1/10,000ths.
    if "makerCommission" in payload and "takerCommission" in payload:
        return decimal(payload["makerCommission"], "maker commission"), decimal(payload["takerCommission"], "taker commission")
    raise ValueError("Binance account response did not contain commission rates")


def query_account_rates(api_key: str, api_secret: str) -> tuple[Decimal, Decimal]:
    params = {
        "omitZeroBalances": "true",
        "recvWindow": "5000",
        "timestamp": str(int(time.time() * 1000)),
    }
    query = urllib.parse.urlencode(params)
    signature = hmac.new(api_secret.encode(), query.encode(), hashlib.sha256).hexdigest()
    request = urllib.request.Request(
        f"{BINANCE_ACCOUNT_URL}?{query}&signature={signature}",
        headers={"X-MBX-APIKEY": api_key},
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            payload = json.loads(response.read().decode())
    except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Binance fee query failed: {exc}") from exc
    if not isinstance(payload, dict):
        raise RuntimeError("Binance fee query returned an unexpected payload")
    return bps_from_account(payload)


def atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        handle.write(content)
        temporary_path = Path(handle.name)
    temporary_path.replace(path)


def update_override(path: Path, maker_bps_net: Decimal, taker_bps_net: Decimal) -> None:
    text = path.read_text(encoding="utf-8")
    values = {
        "binance_maker_percent_fee": maker_bps_net / Decimal("100"),
        "binance_taker_percent_fee": taker_bps_net / Decimal("100"),
    }
    for field, value in values.items():
        replacement = f"{field}: {value.normalize():f}"
        text, count = re.subn(rf"(?m)^{re.escape(field)}:\s*.*$", replacement, text, count=1)
        if count != 1:
            raise RuntimeError(f"Could not update {field} in {path}")
    atomic_write(path, text)


def build_profile(maker_bps_gross: Decimal, taker_bps_gross: Decimal, rebate_rate: Decimal, source: str, query_error: str | None) -> FeeProfile:
    multiplier = Decimal("1") - rebate_rate
    return FeeProfile(
        exchange="binance",
        source=source,
        checked_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        maker_fee_bps_gross=f"{maker_bps_gross:f}",
        taker_fee_bps_gross=f"{taker_bps_gross:f}",
        rebate_rate=f"{rebate_rate:f}",
        maker_fee_bps_net=f"{(maker_bps_gross * multiplier):f}",
        taker_fee_bps_net=f"{(taker_bps_gross * multiplier):f}",
        query_error=query_error,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync Binance paper-trading fee profile with a 40% rebate model")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--rebate-rate", type=Decimal, default=DEFAULT_REBATE_RATE)
    parser.add_argument("--api-key-env", default="BINANCE_FEE_API_KEY")
    parser.add_argument("--api-secret-env", default="BINANCE_FEE_API_SECRET")
    parser.add_argument("--require-account-query", action="store_true")
    args = parser.parse_args()
    if not Decimal("0") <= args.rebate_rate < Decimal("1"):
        parser.error("--rebate-rate must be greater than or equal to 0 and less than 1")

    api_key = os.environ.get(args.api_key_env, "").strip()
    api_secret = os.environ.get(args.api_secret_env, "").strip()
    source = "binance_account"
    query_error: str | None = None
    try:
        if not api_key or not api_secret:
            raise RuntimeError(f"set {args.api_key_env} and {args.api_secret_env} to query the Binance account fee")
        maker_bps, taker_bps = query_account_rates(api_key, api_secret)
    except (RuntimeError, ValueError) as exc:
        if args.require_account_query:
            raise SystemExit(str(exc))
        maker_bps = taker_bps = DEFAULT_GROSS_FEE_BPS
        source = "documented_standard_fallback"
        query_error = str(exc)

    profile = build_profile(maker_bps, taker_bps, args.rebate_rate, source, query_error)
    update_override(args.root / "conf/conf_fee_overrides.yml", Decimal(profile.maker_fee_bps_net), Decimal(profile.taker_fee_bps_net))
    atomic_write(args.root / "data/binance_fee_profile.json", json.dumps(asdict(profile), ensure_ascii=False, indent=2) + "\n")
    print(
        f"Binance fee profile: {profile.source}; gross maker/taker "
        f"{profile.maker_fee_bps_gross}/{profile.taker_fee_bps_gross} bps; "
        f"rebate {profile.rebate_rate}; net {profile.maker_fee_bps_net}/{profile.taker_fee_bps_net} bps"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
