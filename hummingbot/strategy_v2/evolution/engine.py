from __future__ import annotations

from datetime import datetime, timezone

from hummingbot.strategy_v2.evolution.models import (
    CycleResult,
    CycleStatus,
    EvidenceSnapshot,
    EvolutionPolicy,
    EvolutionStage,
    ExperimentPlan,
    GateResult,
    GateStatus,
    StrategyRunStatus,
    StrategySpec,
    StrategyState,
)


STAGE_RANK = {
    EvolutionStage.COLLECTED: 0,
    EvolutionStage.SHADOW: 1,
    EvolutionStage.BACKTEST_PASSED: 2,
    EvolutionStage.PAPER_RUNNING: 3,
    EvolutionStage.PAPER_PASSED: 4,
    EvolutionStage.LIVE_CANARY: 5,
    EvolutionStage.LIVE_ENABLED: 6,
    EvolutionStage.ARCHIVED: 99,
}

OPERATIONAL_FAILURES = {
    "evidence_integrity",
    "configured_checks",
    "paper_runtime_safety",
    "paper_runtime_freshness",
    "paper_candidate_binding",
    "paper_loss_limit",
}

IMMEDIATE_CIRCUIT_FAILURES = {
    "paper_runtime_safety",
    "paper_loss_limit",
}


class StrategyEvolutionEngine:
    def __init__(self, policy: EvolutionPolicy):
        self.policy = policy

    def advance(
        self,
        spec: StrategySpec,
        evidence: EvidenceSnapshot,
        previous: StrategyState,
        *,
        now: datetime | None = None,
    ) -> tuple[StrategyState, CycleResult]:
        now = now or datetime.now(timezone.utc)
        gates = self._gates(spec, evidence)
        derived_stage = self._derive_stage(evidence, gates)
        signature = self._operational_signature(gates)
        same_problem = (
            signature != "healthy" and signature == previous.diagnostic_signature
        )
        repeated = (
            previous.consecutive_same_problem + 1
            if same_problem
            else (1 if signature != "healthy" else 0)
        )
        immediate_circuit = any(
            gate.key in IMMEDIATE_CIRCUIT_FAILURES and gate.status == GateStatus.FAIL
            for gate in gates
        )
        recovery_cycles = 0
        if previous.circuit_open:
            if evidence.recovery_verified and signature == "healthy":
                recovery_cycles = previous.recovery_healthy_cycles + 1
                circuit_open = recovery_cycles < self.policy.recovery_healthy_cycles
            else:
                circuit_open = True
        else:
            circuit_open = immediate_circuit or (
                repeated >= self.policy.same_problem_limit and signature != "healthy"
            )
        stage_after = self._transition_stage(previous, derived_stage, evidence, gates)
        run_status = self._run_status(stage_after, gates, circuit_open)
        experiment = self._plan_experiment(spec, gates, previous.iteration + 1)
        status = self._cycle_status(previous.stage, stage_after, gates, circuit_open)
        highest_ever_stage = max(
            (previous.highest_ever_stage, stage_after),
            key=lambda stage: STAGE_RANK.get(stage, 0),
        )
        updated = StrategyState(
            version=3,
            strategy_id=spec.strategy_id,
            iteration=previous.iteration + 1,
            stage=stage_after,
            highest_ever_stage=highest_ever_stage,
            run_status=run_status,
            diagnostic_signature=signature,
            consecutive_same_problem=repeated,
            circuit_open=circuit_open,
            recovery_healthy_cycles=recovery_cycles,
            champion_candidate_id=previous.champion_candidate_id,
            challenger_candidate_id=previous.challenger_candidate_id,
            active_paper_candidate_id=previous.active_paper_candidate_id,
            previous_good_candidate_id=previous.previous_good_candidate_id,
            in_flight_experiment_id=previous.in_flight_experiment_id,
            in_flight_started_at=previous.in_flight_started_at,
            last_experiment_id=previous.last_experiment_id,
            last_outcome_verdict=previous.last_outcome_verdict,
            experiment_failure_count=previous.experiment_failure_count,
            next_experiment_after=previous.next_experiment_after,
            updated_at=now.isoformat(),
        )
        result = CycleResult(
            strategy_id=spec.strategy_id,
            strategy_name=spec.name,
            iteration=updated.iteration,
            stage_before=previous.stage,
            stage_after=stage_after,
            run_status_before=previous.run_status,
            run_status_after=run_status,
            status=status,
            diagnostic_signature=signature,
            gates=gates,
            evidence=evidence,
            experiment=experiment,
            next_step=self._next_step(status, experiment, stage_after),
            generated_at=now.isoformat(),
        )
        return updated, result

    def _gates(
        self, spec: StrategySpec, evidence: EvidenceSnapshot
    ) -> list[GateResult]:
        checks_status = GateStatus.PASS if not spec.checks else GateStatus.MISSING
        if spec.checks and evidence.check_results:
            hard_failures = [
                row
                for row in evidence.check_results
                if not row.get("ok")
                and row.get("classification") != "environment_missing"
            ]
            if hard_failures:
                checks_status = GateStatus.FAIL
            elif all(row.get("ok") for row in evidence.check_results):
                checks_status = GateStatus.PASS
        walk_ready = (
            evidence.backtest_passed
            and evidence.walk_forward_passed
            and evidence.costs_included
        )
        walk_fresh = (
            evidence.walk_forward_age_hours is not None
            and evidence.walk_forward_age_hours <= spec.maximum_evidence_age_hours
        )
        sample_ready = (
            evidence.paper_hours >= spec.minimum_paper_hours
            and evidence.paper_fills >= spec.minimum_paper_fills
        )
        paper_scorecard_ready = bool(
            sample_ready
            and evidence.paper_scorecard_passed
            and evidence.accepted_candidate_id
            and evidence.paper_scorecard_candidate_id == evidence.accepted_candidate_id
        )
        observation_configured = bool(spec.runtime_file and spec.database_file)
        runtime_safety_status = (
            GateStatus.PASS
            if evidence.runtime_exists and evidence.paper_only
            else (GateStatus.FAIL if evidence.runtime_exists else GateStatus.MISSING)
        )
        runtime_fresh_status = (
            GateStatus.PASS
            if evidence.runtime_fresh
            else (GateStatus.FAIL if evidence.runtime_exists else GateStatus.MISSING)
        )
        if evidence.candidate_binding_valid:
            candidate_binding_status = GateStatus.PASS
        elif evidence.accepted_candidate_id and evidence.runtime_candidate_id:
            candidate_binding_status = GateStatus.FAIL
        else:
            candidate_binding_status = GateStatus.MISSING
        paper_loss_status = (
            GateStatus.MISSING
            if not evidence.runtime_exists
            else (
                GateStatus.PASS
                if evidence.paper_pnl_quote > spec.maximum_paper_loss_quote
                else GateStatus.FAIL
            )
        )

        gates = [
            self._gate(
                "evidence_integrity",
                "证据完整性",
                GateStatus.FAIL if evidence.source_errors else GateStatus.PASS,
                evidence.source_errors,
                [],
                "证据缺失、损坏、越界或哈希不一致时禁止晋级。",
                blocks=bool(evidence.source_errors),
            ),
            self._gate(
                "adapter_tests",
                "策略适配器测试",
                GateStatus.PASS if evidence.adapter_tests_passed else GateStatus.FAIL,
                evidence.adapter_tests_passed,
                True,
                "策略必须先有可执行适配器和确定性测试。",
            ),
            self._gate(
                "configured_checks",
                "本轮代码检查",
                checks_status,
                [
                    row.get("classification", row.get("ok"))
                    for row in evidence.check_results
                ],
                "all pass",
                "依赖缺失与策略测试失败分开处理，不能把环境问题误判成策略失败。",
                blocks=checks_status != GateStatus.PASS,
            ),
            self._gate(
                "stop_path",
                "停止与保护路径",
                GateStatus.PASS if evidence.stop_path_verified else GateStatus.FAIL,
                evidence.stop_path_verified,
                True,
                "停止、撤单和平仓路径必须先于收益优化验证。",
            ),
            self._gate(
                "cost_walk_forward",
                "计费滚动样本外验证",
                GateStatus.PASS if walk_ready else GateStatus.FAIL,
                {
                    "backtest": evidence.backtest_passed,
                    "walk_forward": evidence.walk_forward_passed,
                    "costs": evidence.costs_included,
                },
                "all true",
                "回测、滚动样本外和真实成本口径必须同时通过。",
            ),
            self._gate(
                "walk_forward_freshness",
                "验证证据新鲜度",
                GateStatus.PASS
                if walk_fresh
                else (
                    GateStatus.FAIL
                    if evidence.walk_forward_exists
                    else GateStatus.MISSING
                ),
                evidence.walk_forward_age_hours,
                spec.maximum_evidence_age_hours,
                "旧报告不能永久替代新的市场阶段验证。",
            ),
            self._gate(
                "research_candidate_lineage",
                "研究候选版本谱系",
                GateStatus.PASS
                if evidence.accepted_candidate_id
                else GateStatus.MISSING,
                evidence.accepted_candidate_id,
                "versioned candidate id",
                "通过的滚动验证必须生成不可变候选与研究冠军记录。",
            ),
            self._gate(
                "paper_observation_source",
                "纸盘事实源配置",
                GateStatus.PASS if observation_configured else GateStatus.MISSING,
                {
                    "runtime_file": spec.runtime_file,
                    "database_file": spec.database_file,
                },
                "runtime and database configured",
                "没有独立 runtime 与 SQLite 事实源的策略不得进入纸盘阶段。",
            ),
        ]

        gates.extend(
            [
                self._gate(
                    "paper_runtime_safety",
                    "纸盘运行边界",
                    runtime_safety_status,
                    evidence.paper_only,
                    True,
                    "自动循环只接受 *_paper_trade 运行证据。",
                    blocks=runtime_safety_status == GateStatus.FAIL,
                ),
                self._gate(
                    "paper_runtime_freshness",
                    "纸盘数据新鲜度",
                    runtime_fresh_status,
                    evidence.runtime_age_seconds,
                    spec.maximum_runtime_age_seconds,
                    "运行快照过期时禁止继续输出健康或晋级结论。",
                    blocks=runtime_fresh_status == GateStatus.FAIL,
                ),
                self._gate(
                    "paper_candidate_binding",
                    "纸盘候选版本绑定",
                    candidate_binding_status,
                    {
                        "accepted": evidence.accepted_candidate_id,
                        "runtime": evidence.runtime_candidate_id,
                    },
                    "same candidate id",
                    "纸盘事实必须明确属于当前接受的候选版本。",
                    blocks=candidate_binding_status == GateStatus.FAIL,
                ),
            ]
        )

        gates.extend(
            [
                self._gate(
                    "paper_sample",
                    "纸盘观察样本",
                    GateStatus.PASS if sample_ready else GateStatus.COLLECTING,
                    {
                        "hours": round(evidence.paper_hours, 2),
                        "fills": evidence.paper_fills,
                    },
                    {
                        "hours": spec.minimum_paper_hours,
                        "fills": spec.minimum_paper_fills,
                    },
                    "缺样本是继续观察，不通过调参制造虚假进展。",
                ),
                self._gate(
                    "paper_loss_limit",
                    "纸盘亏损熔断",
                    paper_loss_status,
                    evidence.paper_pnl_quote,
                    spec.maximum_paper_loss_quote,
                    "越过亏损线后只允许停止、复盘和修复。",
                    blocks=paper_loss_status == GateStatus.FAIL,
                ),
                self._gate(
                    "paper_scorecard",
                    "纸盘评分卡",
                    GateStatus.PASS if paper_scorecard_ready else GateStatus.COLLECTING,
                    {
                        "passed": evidence.paper_scorecard_passed,
                        "candidate_id": evidence.paper_scorecard_candidate_id,
                    },
                    True,
                    "纸盘时长和成交样本达标后仍需独立评分卡。",
                ),
                self._gate(
                    "manual_canary",
                    "小额灰度人工批准",
                    GateStatus.PASS
                    if evidence.canary_approved
                    and evidence.canary_candidate_id == evidence.accepted_candidate_id
                    else GateStatus.MANUAL,
                    {
                        "approved": evidence.canary_approved,
                        "candidate_id": evidence.canary_candidate_id,
                    },
                    True,
                    "Loop 无权自行进入小额实盘。",
                ),
                self._gate(
                    "manual_live_release",
                    "实盘发布人工批准",
                    GateStatus.PASS
                    if evidence.live_release_approved
                    and evidence.live_release_candidate_id
                    == evidence.accepted_candidate_id
                    else GateStatus.MANUAL,
                    {
                        "approved": evidence.live_release_approved,
                        "candidate_id": evidence.live_release_candidate_id,
                    },
                    True,
                    "实盘发布必须再次人工批准。",
                ),
                self._gate(
                    "live_actions_disabled",
                    "自动实盘动作永久关闭",
                    GateStatus.PASS
                    if not self.policy.allow_live_actions
                    else GateStatus.FAIL,
                    self.policy.allow_live_actions,
                    False,
                    "该监督器不包含实盘下单或实盘部署动作。",
                    blocks=self.policy.allow_live_actions,
                ),
            ]
        )
        return gates

    @staticmethod
    def _gate(
        key: str,
        label: str,
        status: GateStatus,
        actual,
        threshold,
        message: str,
        *,
        blocks: bool = False,
    ) -> GateResult:
        return GateResult(key, label, status, actual, threshold, message, blocks)

    @staticmethod
    def _derive_stage(
        evidence: EvidenceSnapshot, gates: list[GateResult]
    ) -> EvolutionStage:
        by_key = {gate.key: gate for gate in gates}
        if (
            by_key["evidence_integrity"].status != GateStatus.PASS
            or by_key["adapter_tests"].status != GateStatus.PASS
        ):
            return EvolutionStage.COLLECTED
        stage = EvolutionStage.SHADOW
        if (
            by_key["configured_checks"].status == GateStatus.PASS
            and by_key["stop_path"].status == GateStatus.PASS
            and by_key["cost_walk_forward"].status == GateStatus.PASS
            and by_key["walk_forward_freshness"].status == GateStatus.PASS
        ):
            stage = EvolutionStage.BACKTEST_PASSED
        paper_prerequisites = (
            stage == EvolutionStage.BACKTEST_PASSED
            and by_key["paper_observation_source"].status == GateStatus.PASS
            and by_key["paper_runtime_safety"].status == GateStatus.PASS
            and by_key["paper_runtime_freshness"].status == GateStatus.PASS
            and by_key["research_candidate_lineage"].status == GateStatus.PASS
            and by_key["paper_candidate_binding"].status == GateStatus.PASS
            and by_key["paper_loss_limit"].status == GateStatus.PASS
        )
        if paper_prerequisites:
            stage = EvolutionStage.PAPER_RUNNING
        if (
            stage == EvolutionStage.PAPER_RUNNING
            and by_key["paper_sample"].status == GateStatus.PASS
            and by_key["paper_scorecard"].status == GateStatus.PASS
        ):
            stage = EvolutionStage.PAPER_PASSED
        if (
            stage == EvolutionStage.PAPER_PASSED
            and evidence.canary_approved
            and evidence.canary_candidate_id == evidence.accepted_candidate_id
        ):
            stage = EvolutionStage.LIVE_CANARY
        if (
            stage == EvolutionStage.LIVE_CANARY
            and evidence.live_release_approved
            and evidence.live_release_candidate_id == evidence.accepted_candidate_id
        ):
            stage = EvolutionStage.LIVE_ENABLED
        return stage

    @staticmethod
    def _transition_stage(
        previous: StrategyState,
        derived: EvolutionStage,
        evidence: EvidenceSnapshot,
        gates: list[GateResult],
    ) -> EvolutionStage:
        if previous.stage == EvolutionStage.ARCHIVED:
            return EvolutionStage.ARCHIVED
        by_key = {gate.key: gate for gate in gates}
        checks_not_run = (
            by_key["configured_checks"].status == GateStatus.MISSING
            and not evidence.checks_executed
        )
        hard_failure = any(
            by_key[key].status == GateStatus.FAIL
            for key in (
                "evidence_integrity",
                "adapter_tests",
                "configured_checks",
                "stop_path",
                "cost_walk_forward",
                "walk_forward_freshness",
                "paper_runtime_safety",
                "paper_runtime_freshness",
                "paper_candidate_binding",
                "paper_loss_limit",
            )
        )
        if checks_not_run and not hard_failure:
            return previous.stage
        return derived

    @staticmethod
    def _run_status(
        stage: EvolutionStage,
        gates: list[GateResult],
        circuit_open: bool,
    ) -> StrategyRunStatus:
        if circuit_open:
            return StrategyRunStatus.CIRCUIT_OPEN
        if any(
            gate.blocks_automation
            and gate.status in {GateStatus.FAIL, GateStatus.MISSING}
            for gate in gates
        ):
            return StrategyRunStatus.PAUSED
        if stage in {EvolutionStage.PAPER_RUNNING, EvolutionStage.PAPER_PASSED}:
            return StrategyRunStatus.PAPER_RUNNING
        if any(gate.status == GateStatus.COLLECTING for gate in gates):
            return StrategyRunStatus.OBSERVING
        return StrategyRunStatus.IDLE

    @staticmethod
    def _operational_signature(gates: list[GateResult]) -> str:
        failures = sorted(
            gate.key
            for gate in gates
            if gate.key in OPERATIONAL_FAILURES and gate.status == GateStatus.FAIL
        )
        return ",".join(failures) or "healthy"

    @staticmethod
    def _cycle_status(
        before: EvolutionStage,
        after: EvolutionStage,
        gates: list[GateResult],
        circuit_open: bool,
    ) -> CycleStatus:
        if circuit_open:
            return CycleStatus.CIRCUIT_OPEN
        if any(
            gate.blocks_automation and gate.status == GateStatus.FAIL for gate in gates
        ):
            return CycleStatus.BLOCKED
        if STAGE_RANK.get(after, 0) < STAGE_RANK.get(before, 0):
            return CycleStatus.BLOCKED
        if any(gate.status == GateStatus.FAIL for gate in gates):
            return CycleStatus.BLOCKED
        if STAGE_RANK.get(after, 0) > STAGE_RANK.get(before, 0):
            return CycleStatus.ADVANCED
        by_key = {gate.key: gate for gate in gates}
        if (
            after == EvolutionStage.PAPER_PASSED
            and by_key["manual_canary"].status == GateStatus.MANUAL
        ):
            return CycleStatus.READY_FOR_REVIEW
        if by_key["configured_checks"].status == GateStatus.MISSING:
            return CycleStatus.BLOCKED
        if STAGE_RANK.get(after, 0) >= STAGE_RANK[EvolutionStage.BACKTEST_PASSED]:
            if any(
                by_key[key].status == GateStatus.MISSING
                for key in (
                    "paper_observation_source",
                    "research_candidate_lineage",
                    "paper_runtime_safety",
                    "paper_runtime_freshness",
                    "paper_candidate_binding",
                )
            ):
                return CycleStatus.BLOCKED
        return CycleStatus.OBSERVING

    def _plan_experiment(
        self,
        spec: StrategySpec,
        gates: list[GateResult],
        iteration: int,
    ) -> ExperimentPlan:
        priority = [
            "live_actions_disabled",
            "evidence_integrity",
            "configured_checks",
            "adapter_tests",
            "stop_path",
            "cost_walk_forward",
            "walk_forward_freshness",
            "research_candidate_lineage",
            "paper_observation_source",
            "paper_runtime_safety",
            "paper_runtime_freshness",
            "paper_loss_limit",
            "paper_candidate_binding",
            "paper_sample",
            "paper_scorecard",
            "manual_canary",
            "manual_live_release",
        ]
        by_key = {gate.key: gate for gate in gates}
        selected = next(
            (
                by_key[key]
                for key in priority
                if by_key.get(key) and by_key[key].status != GateStatus.PASS
            ),
            None,
        )
        key = selected.key if selected else "healthy_observation"
        plans = {
            "evidence_integrity": (
                "修复缺失、损坏或版本不一致的证据",
                "repair_evidence_chain",
                ("全部证据来源和哈希校验通过",),
                ("禁止使用无法归因的旧证据晋级",),
            ),
            "configured_checks": (
                "恢复并通过本轮确定性检查",
                "restore_and_run_checks",
                ("全部配置检查通过",),
                ("同一检查连续三轮失败",),
            ),
            "paper_runtime_safety": (
                "恢复纯纸盘运行边界",
                "stop_and_inspect_runtime",
                ("所有运行连接器均为 *_paper_trade",),
                ("检测到实盘连接器",),
            ),
            "paper_runtime_freshness": (
                "恢复纸盘事实流新鲜度",
                "restore_paper_observation",
                ("运行快照持续新鲜两个周期",),
                ("同一断流连续三轮",),
            ),
            "paper_loss_limit": (
                "解释并阻断纸盘亏损来源",
                "pause_and_autopsy",
                ("完成逐成交归因和修复验证",),
                ("不得放大仓位追回",),
            ),
            "adapter_tests": (
                "建立可执行适配器与测试",
                "implement_adapter_test",
                ("适配器测试通过",),
                ("目标执行原语与策略 edge 不匹配",),
            ),
            "stop_path": (
                "先证明停止、撤单和平仓路径",
                "verify_stop_path",
                ("停止路径测试通过",),
                ("存在无法收敛的敞口",),
            ),
            "cost_walk_forward": (
                "完成含费用的滚动样本外实验",
                "run_cost_walk_forward",
                ("至少三个样本外 fold 且总调整后收益为正",),
                ("连续样本外窗口失败",),
            ),
            "walk_forward_freshness": (
                "刷新当前市场阶段验证",
                "refresh_walk_forward",
                ("新证据在时限内",),
                ("新报告与旧结论方向相反",),
            ),
            "research_candidate_lineage": (
                "重新验证并建立不可变研究候选谱系",
                "refresh_walk_forward",
                ("生成 candidate_id、代码哈希、参数哈希和数据指纹",),
                ("参数跨 fold 不稳定时拒绝候选",),
            ),
            "paper_observation_source": (
                "建立独立纸盘 runtime 与 SQLite 事实源",
                "implement_paper_observer",
                ("运行快照、订单、成交和收益均可归因",),
                ("不得用静态声明替代运行事实",),
            ),
            "paper_candidate_binding": (
                "将接受候选版本化应用到隔离纸盘",
                "stage_paper_candidate",
                ("runtime candidate_id 与接受候选一致",),
                ("配置哈希不一致立即回滚",),
            ),
            "paper_sample": (
                "保持参数冻结并积累纸盘样本",
                "observe_only",
                ("达到时长与成交双门槛",),
                ("事实流断流或亏损越线",),
            ),
            "paper_scorecard": (
                "生成独立纸盘评分卡",
                "build_paper_scorecard",
                ("收益、回撤、费用、成交质量同时通过",),
                ("评分卡任一安全项失败",),
            ),
            "manual_canary": (
                "准备小额灰度评审材料",
                "request_manual_canary_review",
                ("获得明确人工批准",),
                ("不得自动批准",),
            ),
            "manual_live_release": (
                "准备实盘发布评审材料",
                "request_manual_live_review",
                ("获得第二次明确人工批准",),
                ("不得自动批准",),
            ),
            "live_actions_disabled": (
                "保持自动实盘动作关闭",
                "halt",
                ("allow_live_actions=false",),
                ("任何自动下单路径出现",),
            ),
            "healthy_observation": (
                "维持当前假设并等待新证据",
                "observe_only",
                ("新增可归因证据",),
                ("无新信息时停止空转",),
            ),
        }
        hypothesis, action, success, stops = plans[key]
        change_budget = (
            0
            if action
            in {
                "observe_only",
                "request_manual_canary_review",
                "request_manual_live_review",
                "halt",
            }
            else self.policy.max_parameter_changes_per_cycle
        )
        return ExperimentPlan(
            experiment_id=f"{spec.strategy_id}-i{iteration:04d}-{key}",
            strategy_id=spec.strategy_id,
            hypothesis=hypothesis,
            action=action,
            change_budget=change_budget,
            success_criteria=success,
            stop_conditions=stops,
            evidence_required=(selected.message if selected else "等待新事实",),
            auto_executable=spec.auto_action(action) is not None and change_budget <= 1,
        )

    @staticmethod
    def _next_step(
        status: CycleStatus,
        experiment: ExperimentPlan,
        stage_after: EvolutionStage,
    ) -> str:
        if status == CycleStatus.CIRCUIT_OPEN:
            return "熔断保持开启；完成回滚并连续健康验证后才能恢复。"
        if status == CycleStatus.READY_FOR_REVIEW:
            return "整理证据后等待人工小额灰度评审。"
        if status == CycleStatus.ADVANCED:
            return f"阶段已推进；下一实验：{experiment.hypothesis}。"
        if status == CycleStatus.BLOCKED:
            return f"当前有效阶段={stage_after.value}；先解除阻塞：{experiment.hypothesis}。"
        return f"继续观察；本轮实验：{experiment.hypothesis}。"
