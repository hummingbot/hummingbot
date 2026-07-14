from __future__ import annotations

from pathlib import Path
import re
from typing import Dict, List, Literal, Optional

import yaml
from pydantic import Field, ValidationError, field_validator, model_validator

from hummingbot.strategy_v2.routing.data_types import (
    AccountKind,
    CompatibilityRelation,
    Environment,
    StrategySleeve,
    StrictModel,
)


class ScoreWeights(StrictModel):
    regime_fit: float = Field(ge=0.0, le=1.0)
    expected_edge_after_cost: float = Field(ge=0.0, le=1.0)
    execution_quality: float = Field(ge=0.0, le=1.0)
    strategy_health: float = Field(ge=0.0, le=1.0)
    ai_adjustment: float = Field(ge=0.0, le=1.0)

    @model_validator(mode="after")
    def weights_sum_to_one(self):
        total = (
            self.regime_fit
            + self.expected_edge_after_cost
            + self.execution_quality
            + self.strategy_health
            + self.ai_adjustment
        )
        if abs(total - 1.0) > 1e-9:
            raise ValueError("score weights must sum to 1")
        return self


class SwitchPolicy(StrictModel):
    minimum_score_delta: float = Field(default=0.08, ge=0.0, le=1.0)
    confirmation_cycles: int = Field(default=3, ge=1)
    minimum_dwell_seconds: int = Field(default=1800, ge=0)
    cooldown_seconds: int = Field(default=900, ge=0)
    drain_timeout_seconds: int = Field(default=300, ge=1)
    canary_seconds: int = Field(default=600, ge=1)


class RouterSettings(StrictModel):
    route_interval_seconds: int = Field(default=300, ge=1)
    require_closed_candle: bool = True
    reserve_quote_pct: float = Field(default=0.25, ge=0.0, le=1.0)
    minimum_candidate_score: float = Field(default=0.50, ge=0.0, le=1.0)
    score_weights: ScoreWeights
    switch_policy: SwitchPolicy = Field(default_factory=SwitchPolicy)


class AISettings(StrictModel):
    enabled: bool = False
    mode: Literal["disabled", "shadow", "active"] = "shadow"
    provider: str = "deepseek"
    base_url: str
    credential_ref: str
    primary_model: str
    review_model: Optional[str] = None
    request_timeout_seconds: int = Field(default=12, ge=1)
    max_adjustment: float = Field(default=0.10, ge=0.0, le=1.0)
    response_ttl_seconds: int = Field(default=300, ge=1)
    circuit_breaker_failures: int = Field(default=3, ge=1)
    circuit_breaker_cooldown_seconds: int = Field(default=900, ge=1)


class GlobalRiskSettings(StrictModel):
    maximum_total_allocation_pct: float = Field(ge=0.0, le=1.0)
    minimum_reserve_quote_pct: float = Field(ge=0.0, le=1.0)
    maximum_exchange_allocation_pct: float = Field(ge=0.0, le=1.0)
    maximum_symbol_gross_exposure_pct: float = Field(ge=0.0, le=1.0)
    maximum_symbol_net_exposure_pct: float = Field(ge=0.0, le=1.0)
    maximum_directional_sleeve_pct: float = Field(ge=0.0, le=1.0)
    maximum_market_making_sleeve_pct: float = Field(ge=0.0, le=1.0)
    maximum_relative_value_sleeve_pct: float = Field(ge=0.0, le=1.0)
    maximum_hedge_sleeve_pct: float = Field(ge=0.0, le=1.0)
    maximum_global_drawdown_quote: float = Field(ge=0.0)
    snapshot_stale_after_seconds: int = Field(default=20, ge=1)

    @model_validator(mode="after")
    def allocation_and_reserve_fit(self):
        if (
            self.maximum_total_allocation_pct + self.minimum_reserve_quote_pct
            > 1.0 + 1e-9
        ):
            raise ValueError(
                "maximum allocation and minimum reserve exceed total equity"
            )
        return self


class AccountPermissions(StrictModel):
    account_read: bool = True
    trade: bool = False
    internal_transfer: bool = False
    withdraw: bool = False

    @model_validator(mode="after")
    def prohibit_withdrawal(self):
        if self.withdraw:
            raise ValueError("routing accounts must not have withdrawal permission")
        return self


class AccountAllocation(StrictModel):
    minimum_reserve_quote: float = Field(default=0.0, ge=0.0)
    maximum_capital_quote: float = Field(ge=0.0)

    @model_validator(mode="after")
    def reserve_not_above_capital(self):
        if self.minimum_reserve_quote > self.maximum_capital_quote:
            raise ValueError("account reserve exceeds maximum capital")
        return self


class AccountRisk(StrictModel):
    maximum_drawdown_quote: float = Field(default=0.0, ge=0.0)
    maximum_gross_exposure_quote: float = Field(default=0.0, ge=0.0)
    maximum_unhedged_exposure_quote: Optional[float] = Field(default=None, ge=0.0)
    maximum_open_orders: int = Field(default=0, ge=0)
    maximum_leverage: Optional[float] = Field(default=None, ge=1.0)
    market_data_stale_after_seconds: int = Field(default=20, ge=1)


class TransferPolicy(StrictModel):
    enabled: bool = False
    require_manual_approval: bool = True
    allowed_counterparties: List[str] = Field(default_factory=list)
    minimum_transfer_quote: float = Field(default=0.0, ge=0.0)
    maximum_transfer_quote: float = Field(default=0.0, ge=0.0)
    maximum_daily_transfer_quote: float = Field(default=0.0, ge=0.0)
    cooldown_seconds: int = Field(default=3600, ge=0)

    @model_validator(mode="after")
    def transfer_limits_are_ordered(self):
        if self.minimum_transfer_quote > self.maximum_transfer_quote:
            raise ValueError("minimum transfer exceeds maximum transfer")
        if self.maximum_transfer_quote > self.maximum_daily_transfer_quote:
            raise ValueError("single transfer exceeds daily transfer limit")
        return self


class TradingAccountConfig(StrictModel):
    id: str
    kind: AccountKind
    parent_id: Optional[str] = None
    exchange: str
    exchange_account_ref: str
    connector: str
    connector_alias: Optional[str] = None
    credential_ref: str
    environment: Environment
    worker_id: Optional[str] = None
    trading_enabled: bool = False
    settlement_asset: str
    allowed_sleeves: List[StrategySleeve]
    allowed_pairs: List[str]
    position_mode: str
    margin_mode: str
    permissions: AccountPermissions
    allocation: AccountAllocation
    risk: AccountRisk
    transfer_policy: TransferPolicy

    @field_validator("id", "worker_id")
    @classmethod
    def validate_runtime_identifier(cls, value: str | None):
        if value is None:
            return value
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}", value):
            raise ValueError(
                "account and worker identifiers must be safe runtime names"
            )
        return value

    @field_validator("credential_ref")
    @classmethod
    def validate_credential_reference(cls, value: str):
        allowed = ("paper:", "env:", "env-prefix:", "secret:")
        if not value.startswith(allowed):
            raise ValueError("credential_ref must be an external reference")
        return value

    @model_validator(mode="after")
    def validate_account_mode(self):
        if (
            self.environment == Environment.PAPER
            and self.credential_ref != "paper:none"
        ):
            raise ValueError("paper accounts must not reference live credentials")
        if (
            self.environment != Environment.PAPER
            and self.credential_ref == "paper:none"
        ):
            raise ValueError(
                "canary/live accounts require an external credential reference"
            )
        if self.kind == AccountKind.SUBACCOUNT and not self.parent_id:
            raise ValueError("subaccounts require parent_id")
        if self.kind != AccountKind.SUBACCOUNT and self.parent_id:
            raise ValueError("only subaccounts may declare parent_id")
        if self.trading_enabled:
            if not self.worker_id:
                raise ValueError("trading accounts require worker_id")
            if not self.permissions.trade:
                raise ValueError("trading account permissions must allow trade")
        elif self.permissions.trade:
            raise ValueError("non-trading accounts cannot have trade permission")
        if self.kind == AccountKind.MASTER and self.trading_enabled:
            raise ValueError("master treasury accounts must not trade")
        return self


class AccountSelector(StrictModel):
    account_ids: List[str]


class StrategyBinding(StrictModel):
    strategy_id: str
    sleeve: StrategySleeve
    account_selector: AccountSelector
    allowed_pairs: List[str]
    compatibility_group: str
    maximum_instances_per_account: int = Field(default=1, ge=1)


class CompatibilityRule(StrictModel):
    left: str
    right: str
    relation: CompatibilityRelation
    conditions: List[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def different_strategies(self):
        if self.left == self.right:
            raise ValueError("compatibility rule must reference two strategies")
        if self.relation == CompatibilityRelation.CONDITIONAL and not self.conditions:
            raise ValueError("conditional compatibility requires conditions")
        return self


class CompatibilitySettings(StrictModel):
    default_same_account_pair: CompatibilityRelation = CompatibilityRelation.EXCLUSIVE
    rules: List[CompatibilityRule] = Field(default_factory=list)


class ReleaseSettings(StrictModel):
    allow_live_actions: bool = False
    allow_automatic_transfers: bool = False
    require_manual_canary_approval: bool = True
    require_manual_live_release: bool = True
    require_manual_transfer_approval: bool = True


class EvolutionIntegrationSettings(StrictModel):
    enabled: bool = False
    evolution_config_path: str = "conf/strategy_evolution.json"
    release_manifest_glob: str = (
        "data/strategy-evolution/strategies/*/paper/release-manifest.json"
    )
    fail_closed_without_manifest: bool = True
    allow_evolution_auto_start: bool = False

    @model_validator(mode="after")
    def enforce_single_runtime_writer(self):
        if self.allow_evolution_auto_start:
            raise ValueError(
                "Evolution cannot auto-start candidates when Routing owns runtime state"
            )
        return self


class IntegrationSettings(StrictModel):
    evolution: EvolutionIntegrationSettings = Field(
        default_factory=EvolutionIntegrationSettings
    )


class RoutingConfig(StrictModel):
    version: int = Field(ge=1)
    environment: Environment
    router: RouterSettings
    ai: AISettings
    global_risk: GlobalRiskSettings
    accounts: List[TradingAccountConfig]
    strategy_bindings: List[StrategyBinding]
    compatibility: CompatibilitySettings
    integration: IntegrationSettings = Field(default_factory=IntegrationSettings)
    release: ReleaseSettings

    @model_validator(mode="after")
    def validate_graph_and_references(self):
        accounts = _unique_by_id(self.accounts, "account")
        bindings = _unique_by_id(
            self.strategy_bindings, "strategy binding", key="strategy_id"
        )

        worker_ids = [
            account.worker_id for account in self.accounts if account.worker_id
        ]
        if len(worker_ids) != len(set(worker_ids)):
            raise ValueError("worker_id values must be unique")
        refs = [account.exchange_account_ref for account in self.accounts]
        if len(refs) != len(set(refs)):
            raise ValueError("exchange_account_ref values must be unique")

        for account in self.accounts:
            if account.environment != self.environment:
                raise ValueError(
                    f"account environment does not match routing environment: {account.id}"
                )
            if account.parent_id and account.parent_id not in accounts:
                raise ValueError(f"unknown parent account: {account.parent_id}")
            for counterparty in account.transfer_policy.allowed_counterparties:
                if counterparty not in accounts:
                    raise ValueError(f"unknown transfer counterparty: {counterparty}")
        _validate_parent_cycles(accounts)

        for binding in self.strategy_bindings:
            if not binding.account_selector.account_ids:
                raise ValueError(f"strategy has no accounts: {binding.strategy_id}")
            for account_id in binding.account_selector.account_ids:
                account = accounts.get(account_id)
                if account is None:
                    raise ValueError(f"unknown strategy account: {account_id}")
                if binding.sleeve not in account.allowed_sleeves:
                    raise ValueError(
                        f"strategy sleeve {binding.sleeve.value} is not allowed by {account_id}"
                    )
                if not set(binding.allowed_pairs).intersection(account.allowed_pairs):
                    raise ValueError(
                        f"strategy {binding.strategy_id} has no allowed pair on {account_id}"
                    )

        seen_rules = set()
        for rule in self.compatibility.rules:
            if rule.left not in bindings or rule.right not in bindings:
                raise ValueError("compatibility rule references unknown strategy")
            key = tuple(sorted((rule.left, rule.right)))
            if key in seen_rules:
                raise ValueError("duplicate compatibility rule")
            seen_rules.add(key)

        if self.environment == Environment.LIVE and not self.release.allow_live_actions:
            raise ValueError("live environment requires allow_live_actions")
        if (
            self.release.allow_automatic_transfers
            and self.release.require_manual_transfer_approval
        ):
            raise ValueError(
                "automatic transfers conflict with manual transfer approval"
            )
        return self

    @property
    def accounts_by_id(self) -> Dict[str, TradingAccountConfig]:
        return {account.id: account for account in self.accounts}

    @property
    def bindings_by_id(self) -> Dict[str, StrategyBinding]:
        return {binding.strategy_id: binding for binding in self.strategy_bindings}


def load_routing_config(path: Path) -> RoutingConfig:
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ValueError(f"cannot read routing config: {path}") from exc
    except yaml.YAMLError as exc:
        raise ValueError(f"invalid routing YAML: {path}") from exc
    if not isinstance(payload, dict):
        raise ValueError("routing config must be a YAML object")
    try:
        return RoutingConfig.model_validate(payload)
    except ValidationError as exc:
        raise ValueError(f"invalid routing config: {exc}") from exc


def _unique_by_id(rows, label: str, *, key: str = "id"):
    result = {}
    for row in rows:
        value = getattr(row, key)
        if value in result:
            raise ValueError(f"duplicate {label}: {value}")
        result[value] = row
    return result


def _validate_parent_cycles(accounts: Dict[str, TradingAccountConfig]):
    for account_id in accounts:
        seen = set()
        current = account_id
        while current is not None:
            if current in seen:
                raise ValueError(f"account parent cycle: {account_id}")
            seen.add(current)
            current = accounts[current].parent_id
