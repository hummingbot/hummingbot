from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

import yaml

from hummingbot.strategy_v2.routing.config import RoutingConfig
from hummingbot.strategy_v2.routing.data_types import (
    AccountSnapshot,
    CandidateSignal,
    FixedScoreComponents,
    MarketState,
    StrategySleeve,
)
from hummingbot.strategy_v2.routing.release import ReleaseManifest, StrategyRelease


def load_market_state(path: Path) -> MarketState:
    return MarketState.model_validate(_read_json_object(path))


def market_state_from_runtime(path: Path, *, symbol: str | None = None) -> MarketState:
    payload = _read_json_object(path)
    generated_at = _iso_timestamp(payload.get("generated_at"))
    prices = [row for row in payload.get("mark_prices", []) if isinstance(row, dict)]
    if symbol:
        prices = [row for row in prices if row.get("symbol") == symbol]
    if not prices:
        raise ValueError("runtime snapshot has no matching mark price")
    price = prices[0]
    selected_symbol = str(price.get("symbol", ""))
    if not selected_symbol:
        raise ValueError("runtime mark price has no symbol")
    stale = bool(price.get("stale", True))
    mark_price = _number(price.get("price"))
    return MarketState(
        timestamp=generated_at,
        symbol=selected_symbol,
        direction="flat",
        trend_strength=0.0,
        volatility_bucket="unknown",
        realized_volatility=0.0,
        liquidity_bucket="stale" if stale else "healthy",
        data_fresh=not stale,
        features={"mark_price": mark_price},
    )


def load_account_snapshots(path: Path) -> dict[str, AccountSnapshot]:
    payload = _read_json_object(path)
    rows = payload.get("accounts")
    if not isinstance(rows, list):
        raise ValueError("account snapshot file must contain an accounts list")
    snapshots = [AccountSnapshot.model_validate(row) for row in rows]
    result = {row.account_id: row for row in snapshots}
    if len(result) != len(snapshots):
        raise ValueError("account snapshot file contains duplicate account_id")
    return result


def merge_runtime_account_snapshots(
    root: Path,
    mapping_path: Path,
    snapshots: dict[str, AccountSnapshot],
) -> dict[str, AccountSnapshot]:
    merged = dict(snapshots)
    for account_id, (runtime_path, settlement_asset) in load_runtime_mapping(
        root, mapping_path
    ).items():
        merged[account_id] = account_snapshot_from_runtime(
            account_id,
            runtime_path,
            settlement_asset=settlement_asset,
        )
    return merged


def load_runtime_mapping(
    root: Path,
    mapping_path: Path,
) -> dict[str, tuple[Path, str]]:
    payload = _read_json_object(mapping_path)
    mappings = payload.get("runtime_snapshots")
    if not isinstance(mappings, dict):
        raise ValueError("runtime mapping must contain a runtime_snapshots object")
    root = root.resolve()
    result = {}
    for account_id, row in mappings.items():
        if not isinstance(row, dict) or not isinstance(row.get("path"), str):
            raise ValueError(f"invalid runtime mapping for account: {account_id}")
        runtime_path = (root / row["path"]).resolve()
        if root not in runtime_path.parents:
            raise ValueError("runtime snapshot path escapes repository root")
        result[account_id] = (
            runtime_path,
            str(row.get("settlement_asset", "USDT")),
        )
    return result


def account_snapshot_from_runtime(
    account_id: str,
    runtime_path: Path,
    *,
    settlement_asset: str = "USDT",
) -> AccountSnapshot:
    payload = _read_json_object(runtime_path)
    generated_at = _iso_timestamp(payload.get("generated_at"))
    balances = payload.get("balances") or []
    positions = payload.get("positions") or []
    open_orders = payload.get("open_orders") or []
    market_data = payload.get("market_data") or []
    if not all(isinstance(row, dict) and row.get("paper") is True for row in balances):
        raise ValueError("runtime snapshot is not entirely paper-only")
    quote_rows = [row for row in balances if row.get("asset") == settlement_asset]
    equity = sum(_number(row.get("total")) for row in quote_rows)
    available = sum(_number(row.get("available")) for row in quote_rows)
    gross = sum(abs(_number(row.get("notional"))) for row in positions)
    net = sum(
        _signed_notional(row.get("side"), _number(row.get("notional")))
        for row in positions
    )
    pnl = sum(_number(row.get("pnl")) for row in positions)
    candidate_id = payload.get("evolution_candidate_id")
    config_hash = payload.get("evolution_config_hash")
    data_fresh = bool(market_data) and not any(
        row.get("stale", True) for row in market_data if isinstance(row, dict)
    )
    return AccountSnapshot(
        account_id=account_id,
        observed_at=generated_at,
        equity_quote=max(0.0, equity + pnl),
        available_quote=max(0.0, available),
        gross_exposure_quote=gross,
        net_exposure_quote=net,
        drawdown_quote=max(0.0, -pnl),
        open_orders=len(open_orders),
        data_fresh=data_fresh,
        balances_fresh=True,
        positions_fresh=True,
        unreconciled_orders=False,
        active_strategy_ids=[
            value for value in [candidate_id] if isinstance(value, str) and value
        ],
        runtime_managed=bool(candidate_id and config_hash),
    )


class EvolutionCandidateAdapter:
    """Turns immutable Evolution releases into deterministic router candidates."""

    def __init__(self, root: Path, config: RoutingConfig):
        self.root = root.resolve()
        self.config = config

    def build(
        self,
        manifest: ReleaseManifest,
        market: MarketState,
    ) -> list[CandidateSignal]:
        candidates = []
        for release in manifest.releases:
            binding = self.config.bindings_by_id.get(release.strategy_id)
            if binding is None:
                continue
            controller_path = self._controller_path(release)
            controller = _read_yaml_object(controller_path)
            pair = str(controller.get("trading_pair", ""))
            connector = str(controller.get("connector_name", ""))
            if not pair or not connector:
                raise ValueError(
                    f"release controller is missing connector/pair: {release.strategy_id}"
                )
            requested = _number(controller.get("total_amount_quote", 0))
            if requested <= 0:
                raise ValueError(
                    f"release controller has invalid capital: {release.strategy_id}"
                )
            candidates.append(
                CandidateSignal(
                    strategy_id=release.strategy_id,
                    candidate_id=release.candidate_id,
                    config_hash=release.config_hash,
                    connector=connector,
                    trading_pair=pair,
                    requested_capital_quote=requested,
                    score_components=_score_components(
                        binding.sleeve,
                        controller,
                        market,
                        release,
                    ),
                    position_side=str(controller.get("position_side", "BOTH")),
                )
            )
        return candidates

    def _controller_path(self, release: StrategyRelease) -> Path:
        if not release.evidence_refs:
            raise ValueError(
                f"release has no controller artifact: {release.strategy_id}"
            )
        path = (self.root / release.evidence_refs[0]).resolve()
        if self.root not in path.parents:
            raise ValueError("release controller escapes repository root")
        return path


def _score_components(
    sleeve: StrategySleeve,
    controller: dict[str, Any],
    market: MarketState,
    release: StrategyRelease,
) -> FixedScoreComponents:
    regime = {
        StrategySleeve.MARKET_MAKING: max(
            0.0,
            1.0 - market.trend_strength - min(market.realized_volatility, 1.0) * 0.25,
        ),
        StrategySleeve.DIRECTIONAL: market.trend_strength,
        StrategySleeve.RELATIVE_VALUE: 0.8 if market.funding_opportunity else 0.35,
        StrategySleeve.HEDGE: 0.75 if market.risk_flags else 0.45,
    }.get(sleeve, 0.5)
    spread = max(
        _number(controller.get("buy_spreads", 0)),
        _number(controller.get("sell_spreads", 0)),
    )
    edge = min(1.0, max(0.0, spread * 250)) if spread else 0.5
    execution = (
        0.9 if market.data_fresh and market.liquidity_bucket == "healthy" else 0.4
    )
    health = 0.9 if release.stage in {"active_verified", "paper_champion"} else 0.75
    return FixedScoreComponents(
        regime_fit=min(1.0, regime),
        expected_edge_after_cost=edge,
        execution_quality=execution,
        strategy_health=health,
    )


def _read_json_object(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ValueError(f"cannot read JSON file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON file: {path}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"JSON file must contain an object: {path}")
    return payload


def _read_yaml_object(path: Path) -> dict[str, Any]:
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ValueError(f"cannot read YAML file: {path}") from exc
    except yaml.YAMLError as exc:
        raise ValueError(f"invalid YAML file: {path}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"YAML file must contain an object: {path}")
    return payload


def _iso_timestamp(value: Any) -> float:
    if not isinstance(value, str):
        raise ValueError("runtime snapshot has no generated_at timestamp")
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except ValueError as exc:
        raise ValueError(f"invalid runtime timestamp: {value}") from exc


def _number(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _signed_notional(side: Any, value: float) -> float:
    return -value if str(side).upper() in {"SHORT", "SELL"} else value


def dump_account_snapshots(rows: Iterable[AccountSnapshot]) -> dict[str, Any]:
    return {"accounts": [row.model_dump(mode="json") for row in rows]}
