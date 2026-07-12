const labels: Record<string, string> = {
  enabled: "已启用",
  shadow: "影子评估",
  research: "研究池",
  blocked: "禁止晋级",
  collected: "已收集",
  backtest_passed: "回测已通过",
  paper_enabled: "纸面运行已启用",
  live_canary: "小额灰度",
  live_enabled: "实盘已启用",
  disabled: "已关闭",
  running: "运行中",
  stopped: "已停止",
  missing: "未找到",
  unknown: "未知",
  continue: "继续运行",
  reduce: "降低仓位",
  stop: "停止",
  switch: "切换策略",
  protect: "保护模式",
  observe: "仅观察",
  low: "低",
  medium: "中",
  high: "高",
  blocker: "阻断",
  info: "提示",
  grid: "网格",
  market_making: "做市",
  trend: "趋势",
  mean_reversion: "均值回归",
  arbitrage: "套利",
  hedge: "对冲",
  liquidity: "流动性",
  lp: "流动性做市",
  execution: "执行算法",
  position_sizing: "仓位管理",
  observe_only: "仅观察",
  paper_executed: "已有纸面成交",
  implementation_only: "仅有实现",
  risk_control: "风险控制",
  structural_edge: "结构性优势",
  model_dependent: "依赖模型",
  mature_implementation: "成熟实现",
  published_model: "公开模型",
  production_example: "生产级示例",
  canonical_pattern: "经典模式",
  baseline_only: "基准策略",
  reference_implementation: "参考实现",
  example_only: "示例级证据",
  not_alpha: "非独立收益来源",
  risk_feature: "风险特征",
  native: "原生接入",
  missing_adapter: "缺少适配器",
  native_executor: "原生执行器",
  standalone: "独立运行",
  controller_profile: "控制器配置",
  strategy_script: "策略脚本",
  range_low_vol: "低波动震荡",
  range_high_vol: "高波动震荡",
  trend_up: "上升趋势",
  trend_down: "下降趋势",
  breakout_up: "向上突破",
  breakout_down: "向下突破",
  breakout: "区间突破",
  extreme: "极端风险",
  adapter_tests_passed: "适配器测试通过",
  stop_path_verified: "停止路径已验证",
  backtest_and_walk_forward_passed: "回测与滚动验证通过",
  paper_scorecard_passed: "纸面评分通过",
  canary_approved: "小额灰度已批准",
  live_release_approved: "实盘发布已批准",
  adapter_tests_required: "需要通过适配器测试",
  stop_path_verification_required: "需要验证停止路径",
  cost_adjusted_walk_forward_required: "需要完成计费滚动验证",
  manual_canary_approval_required: "需要人工批准小额灰度",
  manual_live_release_approval_required: "需要人工批准实盘发布",
  py_compile: "Python 编译检查",
  router_synthetic: "路由器合成测试",
  low_vol_range: "低波动震荡",
  high_vol_range: "高波动震荡",
  range_break_up: "向上突破区间",
  range_break_down: "向下突破区间",
  atr_spike: "ATR 波动率突增",
  volume_spike: "成交量突增",
  active_loss_limit: "主动亏损达到上限",
  strategy_mismatch: "当前策略与行情不匹配",
  no_active_strategy: "当前没有活动策略",
  cooldown: "策略冷却中",
  short_disabled: "做空权限未开启",
};

const riskLabels: Record<string, string> = {
  high_in_breakout: "突破行情中的高风险",
  trend_inventory: "趋势行情中的库存风险",
  directional_drawdown: "方向性回撤",
  short_and_leverage: "做空与杠杆风险",
  opportunity_cost: "机会成本",
  single_leg_basis_funding: "单腿、基差与资金费率风险",
  basis_and_borrow: "基差与借贷风险",
  maker_fill_hedge_latency: "挂单成交与对冲延迟",
  latency_slippage_conversion: "延迟、滑点与换算风险",
  gas_finality_mev: "Gas、终局性与 MEV 风险",
  relationship_breakdown: "统计关系失效",
  adverse_selection_inventory: "逆向选择与库存风险",
  inventory_and_spread: "库存与价差风险",
  model_calibration_inventory: "模型校准与库存风险",
  toxic_flow_latency: "有毒流量与延迟风险",
  whipsaw: "震荡反复止损",
  lag_and_whipsaw: "指标滞后与反复止损",
  false_breakout: "假突破风险",
  gap_and_whipsaw: "跳空与反复止损",
  lag_and_churn: "滞后与频繁换手",
  roll_leverage_correlation: "换月、杠杆与相关性风险",
  trend_breakout: "趋势突破风险",
  persistent_oversold: "持续超卖风险",
  impermanent_loss_gas: "无常损失与 Gas 风险",
  basis_and_overhedge: "基差与过度对冲",
  layered_exposure: "分层敞口风险",
  market_drift: "市场漂移风险",
  data_quality: "数据质量风险",
};

export function zhLabel(value?: string): string {
  if (!value) return "未知";
  if (value.startsWith("paper_scorecard_") && value.endsWith("h_required")) {
    const hours = value.match(/paper_scorecard_(\d+)h_required/)?.[1] ?? "—";
    return `需要通过至少 ${hours} 小时纸面评分`;
  }
  return labels[value] ?? value;
}

export function zhRisk(value: string): string {
  return riskLabels[value] ?? value;
}

export function zhAdapter(value: string): string {
  if (value === "missing") return labels.missing_adapter;
  return labels[value] ?? value;
}

export function zhReasons(value?: string): string {
  if (!value) return "等待新的纸面运行数据";
  const codes = value.match(/[a-z][a-z0-9_]+/g) ?? [];
  const translated = codes.map(zhLabel).filter((item, index, all) => all.indexOf(item) === index);
  return translated.length ? translated.join("、") : value;
}
