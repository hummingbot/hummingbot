from __future__ import annotations

from typing import Iterable, Set

from hummingbot.strategy_v2.routing.config import (
    CompatibilityRule,
    CompatibilitySettings,
)
from hummingbot.strategy_v2.routing.data_types import CompatibilityRelation, RouteTarget


class CompatibilityEngine:
    def __init__(self, settings: CompatibilitySettings):
        self.settings = settings
        self.rules = {
            frozenset((rule.left, rule.right)): rule for rule in settings.rules
        }

    def assess(
        self,
        strategy_id: str,
        account_id: str,
        trading_pair: str,
        selected: Iterable[RouteTarget],
        *,
        supplied_conditions: Iterable[str] = (),
    ) -> list[str]:
        blockers = []
        supplied = set(supplied_conditions)
        for existing in selected:
            same_account_pair = (
                existing.account_id == account_id
                and existing.trading_pair == trading_pair
            )
            conditions = set(supplied)
            if existing.account_id != account_id:
                conditions.add("different_accounts")
            rule = self._rule(strategy_id, existing.strategy_id)
            if rule is None:
                if same_account_pair and (
                    self.settings.default_same_account_pair
                    == CompatibilityRelation.EXCLUSIVE
                ):
                    blockers.append(
                        f"compatibility_exclusive:{strategy_id}:{existing.strategy_id}"
                    )
                continue
            blocker = self._rule_blocker(rule, conditions)
            if blocker:
                blockers.append(blocker)
        return blockers

    def _rule(self, left: str, right: str) -> CompatibilityRule | None:
        return self.rules.get(frozenset((left, right)))

    @staticmethod
    def _rule_blocker(rule: CompatibilityRule, conditions: Set[str]) -> str | None:
        if rule.relation == CompatibilityRelation.COMPATIBLE:
            return None
        if rule.relation == CompatibilityRelation.EXCLUSIVE:
            return f"compatibility_exclusive:{rule.left}:{rule.right}"
        missing = sorted(set(rule.conditions) - conditions)
        if missing:
            return f"compatibility_conditions_missing:{rule.left}:{rule.right}:{','.join(missing)}"
        return None
