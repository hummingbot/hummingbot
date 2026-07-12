#!/usr/bin/env python3
import argparse
import json
import subprocess
import sys
import time
from collections import Counter
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Dict, List, Optional

from ai_router_monitor import (
    db_counts,
    db_recent_orders,
    db_status_counts,
    docker_status,
    estimate_pnl,
    latest_event_price,
    parse_fill_events,
    parse_router_decisions,
    render_report,
    repo_root,
    tail_lines,
)


CORE_COMPILE_TARGETS = [
    "controllers/generic/ai_strategy_router.py",
    "hummingbot/strategy_v2/routers/__init__.py",
    "hummingbot/strategy_v2/routers/adapters.py",
    "hummingbot/strategy_v2/routers/data_types.py",
    "hummingbot/strategy_v2/routers/feature_engine.py",
    "hummingbot/strategy_v2/routers/promotion.py",
    "hummingbot/strategy_v2/routers/router.py",
    "hummingbot/strategy_v2/routers/strategy_registry.py",
    "hummingbot/strategy_v2/executors/executor_base.py",
    "hummingbot/strategy_v2/executors/grid_executor/grid_executor.py",
    "hummingbot/strategy_v2/executors/position_executor/position_executor.py",
    "hummingbot/strategy_v2/backtesting/walk_forward.py",
    "hummingbot/strategy_v2/backtesting/funding_arbitrage.py",
    "scripts/ai_router_monitor.py",
    "scripts/ai_router_iteration_loop.py",
    "scripts/walk_forward_supertrend.py",
    "scripts/walk_forward_pmm_mister.py",
    "scripts/walk_forward_funding_arb.py",
]

DECISION_LABELS = {
    "unknown": "未知行情",
    "range_low_vol": "低波动震荡",
    "range_high_vol": "高波动震荡",
    "trend_up": "上升趋势",
    "trend_down": "下降趋势",
    "breakout_up": "向上突破",
    "breakout_down": "向下突破",
    "extreme": "极端风险",
    "arbitrage": "套利机会",
    "continue": "继续运行",
    "reduce": "降低仓位",
    "stop": "停止",
    "switch": "切换策略",
    "protect": "保护模式",
    "observe": "仅观察",
    "low_vol_range": "低波动震荡",
    "high_vol_range": "高波动震荡",
    "volume_spike": "成交量突增",
    "atr_spike": "平均真实波幅突增",
    "active_loss_limit": "主动亏损达到上限",
}


def localized_decision(decision) -> Optional[Dict]:
    if decision is None:
        return None
    payload = decision.__dict__.copy()
    payload["regime_label"] = DECISION_LABELS.get(decision.regime, decision.regime)
    payload["action_label"] = DECISION_LABELS.get(decision.action, decision.action)
    reason_codes = decision.reasons.replace("[", "").replace("]", "").replace("'", "").split(",")
    payload["reason_labels"] = [DECISION_LABELS.get(code.strip(), code.strip()) for code in reason_codes if code.strip()]
    return payload


def run_command(command: List[str], cwd: Path, timeout: int = 60) -> Dict:
    started = time.time()
    result = subprocess.run(
        command,
        cwd=str(cwd),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
        check=False,
    )
    return {
        "command": command,
        "returncode": result.returncode,
        "stdout": result.stdout.strip(),
        "stderr": result.stderr.strip(),
        "elapsed_sec": round(time.time() - started, 3),
        "ok": result.returncode == 0,
    }


def run_py_compile(root: Path) -> Dict:
    return run_command([sys.executable, "-m", "py_compile", *CORE_COMPILE_TARGETS], cwd=root, timeout=90)


def run_router_synthetic_tests(root: Path) -> Dict:
    code = r"""
from hummingbot.strategy_v2.routers.data_types import MarketFeatures, MarketRegime, RouterAction
from hummingbot.strategy_v2.routers.router import RuleBasedRouterThresholds, RuleBasedStrategyRouter
from hummingbot.strategy_v2.routers.strategy_registry import default_strategy_registry

router = RuleBasedStrategyRouter(default_strategy_registry(), RuleBasedRouterThresholds())

cases = [
    ("not_enough_data", MarketFeatures(enough_data=False), MarketRegime.UNKNOWN, RouterAction.OBSERVE, "protect_mode"),
    ("range", MarketFeatures(enough_data=True, timestamp=1, mid_price=100, close_price=100, atr_pct=0.002, bb_width_pct=0.005, ema_fast=100, ema_slow=100, ema_slope_pct=0, volume_zscore=0, range_high=102, range_low=98), MarketRegime.RANGE_LOW_VOL, RouterAction.SWITCH, "grid_strike"),
    ("trend_up", MarketFeatures(enough_data=True, timestamp=1, mid_price=100, close_price=101, atr_pct=0.002, bb_width_pct=0.02, ema_fast=101, ema_slow=100, ema_slope_pct=0.002, volume_zscore=0, range_high=104, range_low=96), MarketRegime.TREND_UP, RouterAction.SWITCH, "trend_long"),
    ("trend_down", MarketFeatures(enough_data=True, timestamp=1, mid_price=100, close_price=99, atr_pct=0.002, bb_width_pct=0.02, ema_fast=99, ema_slow=100, ema_slope_pct=-0.002, volume_zscore=0, range_high=104, range_low=96), MarketRegime.TREND_DOWN, RouterAction.SWITCH, "trend_short"),
    ("extreme_volume", MarketFeatures(enough_data=True, timestamp=1, mid_price=100, close_price=100, atr_pct=0.002, bb_width_pct=0.005, ema_fast=100, ema_slow=100, ema_slope_pct=0, volume_zscore=5, range_high=102, range_low=98, active_strategy="grid_strike"), MarketRegime.EXTREME, RouterAction.PROTECT, "protect_mode"),
]

for name, features, regime, action, strategy in cases:
    decision = router.decide(features)
    assert decision.regime == regime, (name, decision.regime, regime)
    assert decision.action == action, (name, decision.action, action)
    assert decision.recommended_strategy == strategy, (name, decision.recommended_strategy, strategy)

registry = default_strategy_registry()
assert len(registry) >= 26, len(registry)
assert {"grid_strike", "bollingrid", "trend_long", "trend_short", "protect_mode"}.issubset(registry)
assert all(registry[name].enabled for name in ["grid_strike", "bollingrid", "trend_long", "trend_short", "protect_mode"])
assert any(not candidate.enabled for candidate in registry.values())
print("router_synthetic_tests=ok")
"""
    return run_command([sys.executable, "-c", code], cwd=root, timeout=90)


def registry_snapshot(root: Path) -> Dict:
    sys.path.insert(0, str(root))
    from hummingbot.strategy_v2.routers.strategy_registry import default_strategy_registry

    registry = default_strategy_registry()
    families = Counter(candidate.family.value for candidate in registry.values())
    enabled = [candidate.name for candidate in registry.values() if candidate.enabled]
    disabled = [candidate.name for candidate in registry.values() if not candidate.enabled]
    return {
        "total": len(registry),
        "enabled_count": len(enabled),
        "disabled_count": len(disabled),
        "families": dict(sorted(families.items())),
        "enabled": enabled,
        "disabled_sample": disabled[:10],
    }


def git_snapshot(root: Path) -> Dict:
    result = run_command(["git", "status", "--short"], cwd=root, timeout=20)
    lines = result["stdout"].splitlines() if result["stdout"] else []
    relevant = [
        line for line in lines
        if any(token in line for token in [
            "ai_strategy_router",
            "strategy_v2/routers",
            "ai_router_monitor",
            "ai_router_iteration_loop",
            "executor_base.py",
            "grid_executor.py",
            "position_executor.py",
        ])
    ]
    return {
        "dirty_count": len(lines),
        "relevant_changes": relevant,
    }


def read_simple_yaml(path: Path) -> Dict[str, str]:
    values = {}
    if not path.exists():
        return values
    for raw_line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, value = line.split(":", 1)
        values[key.strip()] = value.strip().strip("\"'")
    return values


def bool_config(config: Dict[str, str], key: str, default: bool = False) -> bool:
    value = config.get(key)
    if value is None:
        return default
    return value.lower() in {"true", "yes", "1", "on"}


def live_snapshot(root: Path, args) -> Dict:
    db_path = Path(args.db).expanduser().resolve()
    log_path = Path(args.log).expanduser().resolve()
    controller_config = read_simple_yaml(Path(args.controller_config).expanduser().resolve())
    lines = tail_lines(log_path, args.log_lines)
    decisions = parse_router_decisions(lines)
    fills = parse_fill_events(lines)
    mark_price = latest_event_price(lines)
    pnl = estimate_pnl(fills, mark_price)
    counts = db_counts(db_path)
    status_counts = db_status_counts(db_path)
    latest_decision = decisions[-1] if decisions else None
    latest_protect = next((decision for decision in reversed(decisions) if decision.action == "protect"), None)
    recent_orders = db_recent_orders(db_path, 5)
    return {
        "container": args.container,
        "container_status": docker_status(args.container),
        "orders": counts["orders"],
        "fills": counts["fills"],
        "parsed_fills": len(fills),
        "status_counts": dict(status_counts),
        "latest_decision": localized_decision(latest_decision),
        "latest_protect": localized_decision(latest_protect),
        "recent_orders": [
            {
                **order,
                "amount": str(order["amount"]),
                "price": str(order["price"]),
            }
            for order in recent_orders
        ],
        "controller_config": controller_config,
        "pnl": {key: str(value) for key, value in pnl.items()},
    }


def evaluate_gaps(snapshot: Dict, registry: Dict, tests: Dict[str, Dict], git: Dict, args) -> List[Dict]:
    gaps = []
    compile_ok = tests["py_compile"]["ok"]
    synthetic_ok = tests["router_synthetic"]["ok"]
    live = snapshot
    pnl = {key: Decimal(value) for key, value in live["pnl"].items()}
    latest_decision = live.get("latest_decision") or {}
    status_counts = live.get("status_counts") or {}
    controller_config = live.get("controller_config") or {}

    if not compile_ok or not synthetic_ok:
        gaps.append({
            "severity": "blocker",
            "area": "code",
            "title": "测试失败，阻止部署。",
            "action": "修复 Python 编译检查或路由器合成测试后，才能重启纸面或实盘实例。",
        })

    if "Up" not in live.get("container_status", ""):
        gaps.append({
            "severity": "high",
            "area": "deployment",
            "title": "纸面容器未运行。",
            "action": "测试通过后重启纸面容器。",
        })

    if live["orders"] == 0 or live["fills"] == 0:
        gaps.append({
            "severity": "high",
            "area": "execution",
            "title": "没有检测到订单或成交。",
            "action": "检查连接器就绪状态、交易规则、纸面余额和执行器创建日志。",
        })

    if pnl["equity_quote"] <= Decimal(str(args.max_paper_loss_quote)):
        gaps.append({
            "severity": "high",
            "area": "risk",
            "title": f"纸面权益估算低于亏损门禁：{pnl['equity_quote']} USDT。",
            "action": "降低网格规模、放宽止盈，或暂停部署直至查明亏损来源。",
        })

    open_orders = sum(count for status, count in status_counts.items() if status.endswith("Created"))
    if open_orders > args.max_open_orders_warning:
        gaps.append({
            "severity": "medium",
            "area": "execution",
            "title": f"纸面挂单数量偏高：{open_orders}。",
            "action": "增加策略前先检查陈旧订单和执行器状态。",
        })

    if latest_decision.get("action") == "protect":
        gaps.append({
            "severity": "medium",
            "area": "router",
            "title": "路由器当前处于保护模式。",
            "action": "保护状态解除并复核原因前，不得部署新策略候选。",
        })

    if latest_decision.get("recommended") == "trend_short" and not bool_config(controller_config, "allow_short"):
        gaps.append({
            "severity": "high",
            "area": "config_constraints",
            "title": "做空权限关闭时，路由器仍推荐了趋势做空。",
            "action": "部署配置约束修复；只有经过明确风险审批后才能开启做空。",
        })

    if registry["disabled_count"] > registry["enabled_count"]:
        gaps.append({
            "severity": "medium",
            "area": "strategy_adapters",
            "title": f"仍有 {registry['disabled_count']} 个影子策略需要适配器。",
            "action": "按照影子评分和行情覆盖优先级实现适配器。",
        })

    if git["relevant_changes"]:
        gaps.append({
            "severity": "low",
            "area": "release",
            "title": "路由器相关代码存在未提交或未固定的变更。",
            "action": "在纸面阶段之后晋级前提交或标记发布快照；后续代码变更后重新执行纸面部署。",
        })

    if not gaps:
        gaps.append({
            "severity": "info",
            "area": "system",
            "title": "未检测到阻断性缺口。",
            "action": "继续收集纸面数据，只有完成干净观察窗口后才能晋级下一个适配器。",
        })

    return gaps


def deploy_paper(root: Path, args) -> Dict:
    if not (root / "conf" / ".password_verification").exists():
        return {
            "ok": False,
            "stdout": "",
            "stderr": "缺少 conf/.password_verification，请在部署前创建。",
            "returncode": 1,
        }

    command = [
        "docker", "rm", "-f", args.container,
    ]
    remove_result = run_command(command, cwd=root, timeout=30)
    run_args = [
        "docker", "run", "-dit",
        "--name", args.container,
        "--network", "host",
        "-e", f"CONFIG_PASSWORD={args.config_password}",
        "-e", "SCRIPT_CONFIG=conf_ai_strategy_router_paper.yml",
        "-v", f"{root / 'conf'}:/home/hummingbot/conf",
        "-v", f"{root / 'logs'}:/home/hummingbot/logs",
        "-v", f"{root / 'data'}:/home/hummingbot/data",
        "-v", f"{root / 'certs'}:/home/hummingbot/certs",
        "-v", f"{root / 'scripts'}:/home/hummingbot/scripts",
        "-v", f"{root / 'controllers'}:/home/hummingbot/controllers",
        "-v", f"{root / 'hummingbot/strategy_v2/routers'}:/home/hummingbot/hummingbot/strategy_v2/routers",
        "-v", f"{root / 'hummingbot/strategy_v2/executors/executor_base.py'}:/home/hummingbot/hummingbot/strategy_v2/executors/executor_base.py",
        "-v", f"{root / 'hummingbot/strategy_v2/executors/grid_executor/grid_executor.py'}:/home/hummingbot/hummingbot/strategy_v2/executors/grid_executor/grid_executor.py",
        "-v", f"{root / 'hummingbot/strategy_v2/executors/position_executor/position_executor.py'}:/home/hummingbot/hummingbot/strategy_v2/executors/position_executor/position_executor.py",
        args.image,
        "bash", "-lc",
        'conda activate hummingbot && ./bin/hummingbot_quickstart.py --v2 conf_ai_strategy_router_paper.yml -p "$CONFIG_PASSWORD"',
    ]
    deploy_result = run_command(run_args, cwd=root, timeout=60)
    deploy_result["remove"] = remove_result
    return deploy_result


def recent_error_lines(log_path: Path, max_lines: int = 500) -> List[str]:
    return [
        line.strip()
        for line in tail_lines(log_path, max_lines)
        if "ERROR" in line or "Traceback" in line
    ][-20:]


def post_deploy_verify(root: Path, args) -> Dict:
    if args.deploy_verify_seconds > 0:
        time.sleep(args.deploy_verify_seconds)
    live = live_snapshot(root, args)
    errors = recent_error_lines(Path(args.log).expanduser().resolve(), args.deploy_verify_log_lines)
    latest_decision = live.get("latest_decision")
    ok = (
        "Up" in live.get("container_status", "")
        and latest_decision is not None
        and len(errors) == 0
    )
    return {
        "ok": ok,
        "container_status": live.get("container_status"),
        "latest_decision": latest_decision,
        "orders": live.get("orders"),
        "fills": live.get("fills"),
        "errors": errors,
    }


def write_iteration_reports(root: Path, payload: Dict, markdown: str, json_path: Path, md_path: Path):
    json_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8")
    md_path.write_text(markdown + "\n", encoding="utf-8")


def render_iteration_markdown(payload: Dict) -> str:
    live = payload["live"]
    registry = payload["registry"]
    tests = payload["tests"]
    gaps = payload["gaps"]
    deploy = payload.get("deploy")
    pnl = live["pnl"]
    latest_decision = live.get("latest_decision") or {}

    lines = [
        "# AI 路由器迭代报告",
        "",
        f"- 生成时间：{payload['generated_at']}",
        f"- 循环轮次：{payload['iteration']}",
        f"- 容器：{live['container']} | {live['container_status']}",
        f"- 路由：{latest_decision.get('regime', '无')} / {latest_decision.get('action', '无')} -> {latest_decision.get('recommended', '无')}",
        f"- 订单／成交：{live['orders']} / {live['fills']}",
        f"- 权益估算：{pnl['equity_quote']} USDT | 基础资产={pnl['base']} BTC | 费用={pnl['fees_quote']} USDT",
        "",
        "## 测试",
        "",
        f"- Python 编译检查：{'通过' if tests['py_compile']['ok'] else '失败'}",
        f"- 路由器合成测试：{'通过' if tests['router_synthetic']['ok'] else '失败'}",
        "",
        "## 策略集合",
        "",
        f"- 总数：{registry['total']}",
        f"- 已启用：{registry['enabled_count']} | {', '.join(registry['enabled'])}",
        f"- 影子策略：{registry['disabled_count']}",
        f"- 策略家族：{registry['families']}",
        "",
        "## 缺口与下一步",
        "",
    ]
    for gap in gaps:
        lines.append(f"- [{gap['severity']}] {gap['area']}：{gap['title']} 下一步：{gap['action']}")

    if deploy is not None:
        post_verify = deploy.get("post_verify") or {}
        lines.extend([
            "",
            "## 部署",
            "",
            f"- 结果：{'通过' if deploy.get('ok') else '失败'}",
            f"- 标准输出：`{deploy.get('stdout', '')[:300]}`",
            f"- 错误输出：`{deploy.get('stderr', '')[:300]}`",
            f"- 部署后验证：{'通过' if post_verify.get('ok') else '跳过或失败'}",
        ])
        if post_verify:
            lines.append(f"- 部署后容器：{post_verify.get('container_status')}")
            lines.append(f"- 部署后最新决策：{post_verify.get('latest_decision')}")
            if post_verify.get("errors"):
                lines.append(f"- 部署后错误：{post_verify.get('errors')}")
    return "\n".join(lines)


def run_iteration(root: Path, args, iteration: int) -> Dict:
    tests = {
        "py_compile": run_py_compile(root),
        "router_synthetic": run_router_synthetic_tests(root),
    }
    registry = registry_snapshot(root)
    live = live_snapshot(root, args)
    git = git_snapshot(root)
    gaps = evaluate_gaps(live, registry, tests, git, args)
    should_deploy = args.deploy_paper and all(test["ok"] for test in tests.values())
    deploy = deploy_paper(root, args) if should_deploy else None
    if deploy is not None and deploy.get("ok"):
        deploy["post_verify"] = post_deploy_verify(root, args)

    payload = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "iteration": iteration,
        "tests": tests,
        "registry": registry,
        "live": live,
        "git": git,
        "gaps": gaps,
        "deploy": deploy,
        "deploy_requested": args.deploy_paper,
        "deploy_skipped_reason": None if should_deploy or not args.deploy_paper else "tests_failed",
    }

    if args.monitor_report:
        monitor_report = render_report(
            db_path=Path(args.db).expanduser().resolve(),
            log_path=Path(args.log).expanduser().resolve(),
            container=args.container,
            log_lines=args.log_lines,
            recent=args.recent,
        )
        Path(args.monitor_report).expanduser().resolve().write_text(monitor_report + "\n", encoding="utf-8")

    md = render_iteration_markdown(payload)
    write_iteration_reports(
        root=root,
        payload=payload,
        markdown=md,
        json_path=Path(args.json_report).expanduser().resolve(),
        md_path=Path(args.md_report).expanduser().resolve(),
    )
    return payload


def main():
    root = repo_root()
    parser = argparse.ArgumentParser(description="AI 路由器的观察、测试、评估与部署循环。")
    parser.add_argument("--db", default=str(root / "data" / "conf_ai_strategy_router_paper.sqlite"))
    parser.add_argument("--log", default=str(root / "logs" / "logs_conf_ai_strategy_router_paper.log"))
    parser.add_argument("--container", default="hummingbot-ai-router-paper")
    parser.add_argument("--controller-config", default=str(root / "conf" / "controllers" / "conf_ai_strategy_router_paper.yml"))
    parser.add_argument("--image", default="hummingbot/hummingbot:latest")
    parser.add_argument("--config-password", default="admin")
    parser.add_argument("--log-lines", type=int, default=100000)
    parser.add_argument("--recent", type=int, default=8)
    parser.add_argument("--watch", type=int, default=0, help="持续运行，每轮之间等待 N 秒。")
    parser.add_argument("--max-iterations", type=int, default=1)
    parser.add_argument("--deploy-paper", action="store_true", help="测试通过后重启纸面容器。")
    parser.add_argument("--deploy-verify-seconds", type=int, default=90)
    parser.add_argument("--deploy-verify-log-lines", type=int, default=500)
    parser.add_argument("--max-paper-loss-quote", type=Decimal, default=Decimal("-5"))
    parser.add_argument("--max-open-orders-warning", type=int, default=20)
    parser.add_argument("--json-report", default=str(root / "reports" / "ai_strategy_router_iteration_latest.json"))
    parser.add_argument("--md-report", default=str(root / "reports" / "ai_strategy_router_iteration_latest.md"))
    parser.add_argument("--monitor-report", default=str(root / "reports" / "ai_strategy_router_live_status.md"))
    args = parser.parse_args()

    iteration = 1
    while True:
        payload = run_iteration(root, args, iteration)
        print(render_iteration_markdown(payload))
        if args.watch <= 0 or iteration >= args.max_iterations:
            break
        iteration += 1
        print("\n" + "=" * 80 + "\n")
        time.sleep(args.watch)


if __name__ == "__main__":
    main()
