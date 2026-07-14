from __future__ import annotations

import fcntl
import json
import os
import time
from pathlib import Path
from typing import Callable

from pydantic import Field, model_validator

from hummingbot.strategy_v2.routing.config import RoutingConfig
from hummingbot.strategy_v2.routing.data_types import Environment, StrictModel


class PaperTransferRequest(StrictModel):
    transfer_id: str
    source_account_id: str
    target_account_id: str
    amount_quote: float = Field(gt=0)
    approved_by: str | None = None
    requested_at: float

    @model_validator(mode="after")
    def different_accounts(self):
        if self.source_account_id == self.target_account_id:
            raise ValueError("transfer source and target must differ")
        return self


class PaperTransferSimulator:
    """Idempotent balance simulator. It cannot call an exchange transfer API."""

    def __init__(
        self,
        config: RoutingConfig,
        state_path: Path,
        ledger_path: Path,
        *,
        clock: Callable[[], float] = time.time,
    ):
        self.config = config
        self.state_path = state_path
        self.ledger_path = ledger_path
        self.clock = clock

    def seed(self, balances: dict[str, float]) -> None:
        unknown = set(balances) - set(self.config.accounts_by_id)
        if unknown:
            raise ValueError(f"unknown paper transfer accounts: {sorted(unknown)}")
        self._save_state({"version": 1, "balances": balances, "last_transfer": {}})

    def execute(self, request: PaperTransferRequest) -> dict:
        if self.config.environment != Environment.PAPER:
            raise ValueError("transfer simulator only works in paper environment")
        source = self.config.accounts_by_id.get(request.source_account_id)
        target = self.config.accounts_by_id.get(request.target_account_id)
        if source is None or target is None:
            raise ValueError("transfer references an unknown account")
        if target.id not in source.transfer_policy.allowed_counterparties:
            raise ValueError("transfer target is not allowlisted")
        policy = source.transfer_policy
        if not policy.enabled:
            raise ValueError("paper transfer policy is disabled")
        if policy.require_manual_approval and not request.approved_by:
            raise ValueError("paper transfer requires manual approval")
        if (
            not policy.minimum_transfer_quote
            <= request.amount_quote
            <= policy.maximum_transfer_quote
        ):
            raise ValueError("paper transfer violates single-transfer limits")

        self.ledger_path.parent.mkdir(parents=True, exist_ok=True)
        with self.ledger_path.open("a+", encoding="utf-8") as ledger:
            fcntl.flock(ledger.fileno(), fcntl.LOCK_EX)
            ledger.seek(0)
            events = [json.loads(line) for line in ledger if line.strip()]
            previous = next(
                (
                    row
                    for row in events
                    if row.get("transfer_id") == request.transfer_id
                ),
                None,
            )
            if previous:
                return previous
            today_total = sum(
                float(row.get("amount_quote", 0))
                for row in events
                if row.get("source_account_id") == source.id
                and self.clock() - float(row.get("executed_at", 0)) < 86400
            )
            if today_total + request.amount_quote > policy.maximum_daily_transfer_quote:
                raise ValueError("paper transfer exceeds daily limit")
            state = self._state()
            balances = state.setdefault("balances", {})
            source_balance = float(balances.get(source.id, 0))
            if (
                source_balance - request.amount_quote
                < source.allocation.minimum_reserve_quote
            ):
                raise ValueError("paper transfer would violate source reserve")
            last = float(state.setdefault("last_transfer", {}).get(source.id, 0))
            if self.clock() - last < policy.cooldown_seconds:
                raise ValueError("paper transfer is in cooldown")
            balances[source.id] = source_balance - request.amount_quote
            balances[target.id] = (
                float(balances.get(target.id, 0)) + request.amount_quote
            )
            state["last_transfer"][source.id] = self.clock()
            self._save_state(state)
            event = {
                **request.model_dump(mode="json"),
                "status": "simulated",
                "executed_at": self.clock(),
                "balances_after": {
                    source.id: balances[source.id],
                    target.id: balances[target.id],
                },
            }
            ledger.seek(0, os.SEEK_END)
            ledger.write(json.dumps(event, sort_keys=True) + "\n")
            ledger.flush()
            os.fsync(ledger.fileno())
            return event

    def _state(self) -> dict:
        try:
            payload = json.loads(self.state_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {"version": 1, "balances": {}, "last_transfer": {}}
        return payload if isinstance(payload, dict) else {}

    def _save_state(self, payload: dict) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.state_path.with_suffix(f"{self.state_path.suffix}.tmp")
        temporary.write_text(
            json.dumps(payload, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
        temporary.replace(self.state_path)
