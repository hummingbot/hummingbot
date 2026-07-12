#!/usr/bin/env python3
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from hummingbot.strategy_v2.routers.adapters import default_adapter_registry  # noqa: E402
from hummingbot.strategy_v2.routers.promotion import PromotionEvidence, assess_registry  # noqa: E402


ZH_LABELS = {
    "supertrend_v1": "超级趋势",
    "pmm_mister": "高级纯做市",
    "funding_rate_arb": "资金费率套利",
    "shadow": "影子评估",
    "backtest_passed": "回测已通过",
    "paper_enabled": "纸面运行已启用",
    "live_canary": "小额灰度",
    "live_enabled": "实盘已启用",
    "controller_profile": "控制器配置",
    "strategy_script": "策略脚本",
    "adapter_tests_passed": "适配器测试通过",
    "stop_path_verified": "停止路径已验证",
    "backtest_and_walk_forward_passed": "回测与滚动验证通过",
    "paper_scorecard_passed": "纸面评分通过",
    "canary_approved": "小额灰度已批准",
    "live_release_approved": "实盘发布已批准",
    "adapter_tests_required": "需要通过适配器测试",
    "stop_path_verification_required": "需要验证停止路径",
    "cost_adjusted_walk_forward_required": "需要完成计费滚动验证",
    "manual_canary_approval_required": "需要人工批准小额灰度",
    "manual_live_release_approval_required": "需要人工批准实盘发布",
    "range_low_vol": "低波动震荡",
    "range_high_vol": "高波动震荡",
    "trend_up": "上升趋势",
    "trend_down": "下降趋势",
    "breakout_up": "向上突破",
    "breakout_down": "向下突破",
    "arbitrage": "套利机会",
    "supertrend_direction": "超级趋势方向",
    "atr": "平均真实波幅",
    "trend_strength": "趋势强度",
    "mid_price": "中间价",
    "spread": "买卖价差",
    "inventory_pct": "库存比例",
    "realized_volatility": "已实现波动率",
    "normalized_funding_rate": "标准化资金费率",
    "executable_basis": "可执行基差",
    "entry_fees": "入场费用",
    "exit_cost_buffer": "退出成本缓冲",
    "allow_short_gate": "做空权限门禁",
    "stop_loss": "止损",
    "take_profit": "止盈",
    "time_limit": "持仓时间限制",
    "protect_stop": "保护模式停止路径",
    "maker_only": "仅挂单成交",
    "portfolio_allocation_cap": "组合资金分配上限",
    "max_active_executors_by_level": "每层活动执行器上限",
    "global_stop_loss": "全局止损",
    "two_leg_balance": "双腿平衡",
    "single_leg_timeout": "单腿超时",
    "max_entry_basis_loss": "最大入场基差损失",
    "funding_stop_loss": "资金费率止损",
    "protect_unwind": "保护性平仓",
}


def zh_label(value: str) -> str:
    if value.startswith("paper_scorecard_") and value.endswith("h_required"):
        hours = value.removeprefix("paper_scorecard_").removesuffix("h_required")
        return f"需要通过至少 {hours} 小时纸面评分"
    return ZH_LABELS.get(value, value)


def build_report(evidence_path: Path) -> dict:
    payload = json.loads(evidence_path.read_text(encoding="utf-8"))
    evidence = {
        name: PromotionEvidence.model_validate(values)
        for name, values in payload.get("strategies", {}).items()
    }
    adapters = default_adapter_registry()
    assessments = assess_registry(adapters, evidence)
    return {
        "version": "1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "default_live_state": "disabled",
        "strategies": [
            {
                **assessment.model_dump(mode="json"),
                "strategy_label": zh_label(name),
                "stage_label": zh_label(assessment.stage.value),
                "completed_gate_labels": [zh_label(value) for value in assessment.completed_gates],
                "blocking_gate_labels": [zh_label(value) for value in assessment.blocking_gates],
                "target": adapters[name].spec.target,
                "execution_mode": adapters[name].spec.execution_mode.value,
                "execution_mode_label": zh_label(adapters[name].spec.execution_mode.value),
                "intended_regimes": adapters[name].spec.intended_regimes,
                "intended_regime_labels": [zh_label(value) for value in adapters[name].spec.intended_regimes],
                "minimum_paper_hours": adapters[name].spec.minimum_paper_hours,
                "required_features": adapters[name].spec.required_features,
                "required_feature_labels": [zh_label(value) for value in adapters[name].spec.required_features],
                "risk_controls": adapters[name].spec.risk_controls,
                "risk_control_labels": [zh_label(value) for value in adapters[name].spec.risk_controls],
                "evidence_refs": evidence.get(name, PromotionEvidence()).evidence_refs,
            }
            for name, assessment in assessments.items()
        ],
    }


def main():
    parser = argparse.ArgumentParser(description="生成失败即关闭的策略晋级状态。")
    parser.add_argument(
        "--evidence",
        default=str(ROOT / "reports" / "strategy_promotion_evidence.json"),
    )
    parser.add_argument(
        "--output",
        default=str(ROOT / "reports" / "strategy_promotion_state.json"),
    )
    args = parser.parse_args()
    report = build_report(Path(args.evidence).expanduser().resolve())
    output = Path(args.output).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"已向 {output} 写入 {len(report['strategies'])} 条策略晋级评估")


if __name__ == "__main__":
    main()
