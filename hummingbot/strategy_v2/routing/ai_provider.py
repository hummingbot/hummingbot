from __future__ import annotations

import hashlib
import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Callable

from hummingbot.strategy_v2.routing.config import AISettings
from hummingbot.strategy_v2.routing.data_types import (
    AIRoutingSignal,
    CandidateSignal,
    MarketState,
)


Transport = Callable[[str, dict[str, str], bytes, int], dict[str, Any]]


class DeepSeekRoutingClient:
    """Bounded JSON-only DeepSeek adapter with a persistent circuit breaker."""

    def __init__(
        self,
        settings: AISettings,
        state_path: Path,
        *,
        transport: Transport | None = None,
        clock: Callable[[], float] = time.time,
    ):
        self.settings = settings
        self.state_path = state_path
        self.transport = transport or _http_transport
        self.clock = clock

    def evaluate(
        self,
        market: MarketState,
        candidates: list[CandidateSignal],
    ) -> AIRoutingSignal | None:
        if not self.settings.enabled or not candidates:
            return None
        now = self.clock()
        state = self._state()
        if float(state.get("open_until", 0)) > now:
            return AIRoutingSignal(
                observed_at=now,
                abstain=True,
                reason_codes=["ai_circuit_open"],
                model=self.settings.primary_model,
            )
        api_key = self._api_key()
        if not api_key:
            return AIRoutingSignal(
                observed_at=now,
                abstain=True,
                reason_codes=["ai_credentials_missing"],
                model=self.settings.primary_model,
            )
        prompt = _prompt(market, candidates)
        prompt_hash = hashlib.sha256(prompt.encode()).hexdigest()
        request = {
            "model": self.settings.primary_model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a bounded strategy-routing reviewer. Return JSON only. "
                        "Never request trades, transfers, leverage, or new strategies."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            "response_format": {"type": "json_object"},
            "stream": False,
        }
        try:
            response = self.transport(
                f"{self.settings.base_url.rstrip('/')}/chat/completions",
                {
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json.dumps(request, separators=(",", ":")).encode(),
                self.settings.request_timeout_seconds,
            )
            signal = self._parse(response, candidates, now, prompt_hash)
        except (OSError, ValueError, KeyError, TypeError, urllib.error.URLError):
            failures = int(state.get("failures", 0)) + 1
            updated = {"failures": failures, "open_until": 0.0}
            if failures >= self.settings.circuit_breaker_failures:
                updated["open_until"] = (
                    now + self.settings.circuit_breaker_cooldown_seconds
                )
            self._save_state(updated)
            return AIRoutingSignal(
                observed_at=now,
                abstain=True,
                reason_codes=["ai_request_failed"],
                model=self.settings.primary_model,
                prompt_hash=prompt_hash,
            )
        self._save_state({"failures": 0, "open_until": 0.0})
        return signal

    def _parse(
        self,
        response: dict[str, Any],
        candidates: list[CandidateSignal],
        now: float,
        prompt_hash: str,
    ) -> AIRoutingSignal:
        content = response["choices"][0]["message"]["content"]
        payload = json.loads(content)
        allowed = {row.strategy_id for row in candidates}
        adjustments = payload.get("strategy_adjustments") or {}
        if not isinstance(adjustments, dict) or not set(adjustments).issubset(allowed):
            raise ValueError("AI response contains unknown strategies")
        normalized = {
            key: max(
                -self.settings.max_adjustment,
                min(self.settings.max_adjustment, float(value)),
            )
            for key, value in adjustments.items()
        }
        response_hash = hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        return AIRoutingSignal(
            observed_at=now,
            ttl_seconds=min(
                int(payload.get("ttl_seconds", self.settings.response_ttl_seconds)),
                self.settings.response_ttl_seconds,
            ),
            confidence=float(payload.get("confidence", 0.0)),
            abstain=bool(payload.get("abstain", False)),
            strategy_adjustments=normalized,
            reason_codes=[str(row) for row in payload.get("reason_codes", [])],
            model=self.settings.primary_model,
            prompt_hash=prompt_hash,
            response_hash=response_hash,
        )

    def _api_key(self) -> str | None:
        prefix = "env:"
        if not self.settings.credential_ref.startswith(prefix):
            return None
        return os.environ.get(self.settings.credential_ref.removeprefix(prefix))

    def _state(self) -> dict[str, Any]:
        try:
            payload = json.loads(self.state_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        return payload if isinstance(payload, dict) else {}

    def _save_state(self, payload: dict[str, Any]) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.state_path.with_suffix(f"{self.state_path.suffix}.tmp")
        temporary.write_text(
            json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8"
        )
        temporary.replace(self.state_path)


def _prompt(market: MarketState, candidates: list[CandidateSignal]) -> str:
    payload = {
        "contract": {
            "output": {
                "abstain": "boolean",
                "ttl_seconds": "integer",
                "confidence": "0..1",
                "strategy_adjustments": "map candidate strategy_id to bounded decimal",
                "reason_codes": "short string list",
            }
        },
        "market": market.model_dump(mode="json"),
        "candidates": [
            {
                "strategy_id": row.strategy_id,
                "trading_pair": row.trading_pair,
                "fixed_components": row.score_components.model_dump(mode="json"),
            }
            for row in candidates
        ],
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def _http_transport(
    url: str,
    headers: dict[str, str],
    body: bytes,
    timeout: int,
) -> dict[str, Any]:
    request = urllib.request.Request(url, data=body, headers=headers, method="POST")
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = json.loads(response.read().decode())
    if not isinstance(payload, dict):
        raise ValueError("AI response is not a JSON object")
    return payload
