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
  grid_strike: "网格突击",
  multi_grid_strike: "多层网格突击",
  bollingrid: "布林网格",
  trend_long: "趋势做多",
  trend_short: "趋势做空",
  protect_mode: "保护模式",
  pmm_mister: "高级纯做市",
  supertrend_v1: "超级趋势",
  funding_rate_arb: "资金费率套利",
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
  paper: "纸盘",
  master: "主账户",
  subaccount: "子账户",
  independent: "独立账户",
  directional: "趋势",
  relative_value: "相对价值",
  reserve: "资金储备",
  unavailable: "不可读取",
  stable: "稳定",
  start: "启动候选",
  drain: "排空旧策略",
  observing: "观察中",
  circuit_open: "熔断中",
  paper_running: "纸盘运行",
  rollback_blocked_open_exposure: "回滚受持仓阻挡",
  active_verified: "已验证激活",
  paper_champion: "纸盘冠军版本",
  conditional: "有条件兼容",
  compatible: "兼容",
  exclusive: "互斥",
  healthy: "健康",
  unsafe: "不安全",
  degraded: "已降级",
  starting: "启动中",
  safe: "安全",
  ready: "已就绪",
  simulated: "已模拟",
  paper_plan: "纸盘计划",
  HEDGE: "双向持仓",
  ONEWAY: "单向持仓",
  ONE_WAY: "单向持仓",
  ISOLATED: "逐仓",
  CROSS: "全仓",
  BUY: "买入",
  SELL: "卖出",
  runtime_stale: "运行快照过期",
  different_accounts: "使用不同账户",
  global_net_exposure_within_limit: "全局净敞口保持在限制内",
  same_pair_position_owner: "同交易对单一持仓所有者",
  market_neutral_two_leg: "市场中性双腿",
  portfolio_overlay: "组合对冲覆盖",
  pass: "通过",
  passed: "已通过",
  collecting: "样本收集中",
  manual: "等待人工批准",
  active: "活动中",
  pending: "等待中",
  failed: "失败",
  deepseek: "DeepSeek",
  Gas: "链上手续费",
  MEV: "最大可提取价值",
  Dashboard: "控制面板",
  CTA: "商品交易顾问",
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
  gas_finality_mev: "链上手续费、终局性与最大可提取价值风险",
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
  impermanent_loss_gas: "无常损失与链上手续费风险",
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

export function zhText(value?: string | null): string {
  if (!value) return "—";
  return Object.entries(labels)
    .filter(([key]) => /[_A-Z]/.test(key) || ["shadow", "unsafe", "degraded", "healthy", "simulated"].includes(key))
    .sort(([left], [right]) => right.length - left.length)
    .reduce((text, [key, label]) => text.replaceAll(key, label), value);
}

export function zhExchange(value?: string): string {
  if (!value) return "未知交易所";
  return ({
    binance: "币安",
    binance_paper_trade: "币安纸盘",
    gate_io: "Gate.io",
    okx: "欧易",
    bybit: "Bybit",
  } as Record<string, string>)[value.toLowerCase()] ?? value;
}

export function zhInstance(value?: string): string {
  if (!value) return "未知实例";
  if (value === "pmm_mister_paper") return "高级纯做市纸盘实例";
  if (value === "ai_strategy_router_paper") return "智能策略路由纸盘实例";
  return value;
}

export function zhOrderType(value?: string): string {
  if (!value) return "—";
  return ({
    LIMIT: "限价单",
    LIMIT_MAKER: "只挂单限价单",
    MARKET: "市价单",
    IOC: "立即成交否则取消",
    FOK: "全部成交否则取消",
    POST_ONLY: "只挂单",
  } as Record<string, string>)[value.toUpperCase()] ?? value;
}

export function zhOrderStatus(value?: string): string {
  if (!value) return "—";
  return ({
    OPEN: "活动中",
    ACTIVE: "活动中",
    PENDING: "等待中",
    NEW: "已创建",
    PARTIALLY_FILLED: "部分成交",
    FILLED: "全部成交",
    COMPLETED: "已完成",
    CANCELED: "已取消",
    CANCELLED: "已取消",
    FAILED: "失败",
    EXPIRED: "已过期",
  } as Record<string, string>)[value.toUpperCase()] ?? value;
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
