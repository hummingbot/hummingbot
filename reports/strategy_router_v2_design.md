# 多策略账户路由器 V2 设计

> 状态：纸盘端到端控制链路已经实现：Evolution 发布物、固定特征候选、多账户路由、DeepSeek 有界接口、Worker 生命周期、运行快照回读、模拟划拨和审计均已接通。实盘交易、真实交易所划拨和自动划拨仍被硬关闭。

## 1. 目标与边界

V2 路由器不是一个“让大模型看 K 线并选择策略”的简单组件，而是账户、资金、策略、风控和执行之间的上层控制平面。

它需要回答五类问题：

1. 当前市场和账户处于哪些可同时成立的状态。
2. 哪些策略当前具备运行资格。
3. 多个兼容策略应该分配多少资金，并落在哪个账户。
4. 旧策略如何安全排空，新策略如何启动、验证和回滚。
5. 数据、模型、账户或执行异常时，系统如何降级并保护资金。

永久边界：

- AI 只提供有界的路由评分，不直接生成订单、仓位、杠杆或资金划拨指令。
- 固定特征、费用模型、策略健康和风险门禁始终存在；AI 不可绕过。
- 风险门禁是硬否决，不参与“加权后被抵消”。
- 账户密钥不进入仓库配置；配置只保存环境变量或外部 Secret 引用。
- 纸盘、灰度和实盘是不同发布阶段；实盘和资金划拨必须有独立人工授权。
- 一个策略的故障不得污染其他账户、策略状态或证据。

## 2. 当前实现与 V2 差距

当前第一版已经验证了以下最小闭环：

```text
单市场 K 线
  -> 固定特征
  -> 单一 MarketRegime
  -> 固定优先级策略
  -> GridExecutor / PositionExecutor
```

它适合证明路由架构能运行，但存在以下生产化缺口：

- `MarketRegime` 是互斥单标签，无法同时表达趋势、波动率、流动性和套利机会。
- 候选评分主要来自行情标签和静态优先级，没有费用后优势、盘口执行质量、策略健康和切换成本。
- 策略注册表覆盖多个家族，但当前 Controller 只硬编码创建网格和趋势 Executor。
- 当前 Adapter 负责策略晋级证据，不负责运行期启动、排空、健康检查和回滚。
- 当前 Controller 只能管理自己创建的 Executor，不能安全管理兄弟 Controller 和多个账户。
- 当前输出是单一推荐策略，无法表达多账户、多资金槽和兼容策略并行。

因此 V2 不应继续把所有职责塞进 `AIStrategyRouter` Controller，而应新增顶层 `StrategyRoutingSupervisor`。

## 3. 核心设计决策

### 3.1 控制平面与执行平面分离

```text
控制平面
  StrategyRoutingSupervisor
    ├── FeatureService
    ├── AccountRegistry
    ├── StrategyRegistry
    ├── EligibilityEngine
    ├── DeterministicScorer
    ├── AIRoutingProvider
    ├── PortfolioAllocator
    ├── RiskGate
    ├── TransitionCoordinator
    └── DecisionLedger

执行平面
  AccountWorker / Hummingbot Instance
    ├── Connector
    ├── Controller
    ├── Executor
    └── Local Account Risk Guard
```

Supervisor 只输出目标状态和生命周期命令；每个账户 Worker 负责订单执行和本账户硬风控。

### 3.2 账户是一级路由资源

路由目标必须从：

```text
strategy
```

升级为：

```text
(account_id, strategy_id, trading_pair, allocation, lifecycle_state)
```

系统统一支持两类账户：

- 独立账户：不同登录账户和 API Key。
- 主账户下的子账户：共享运营主体，但拥有独立 API Key、余额、仓位和订单。

上层通过统一 `TradingAccount` 协议访问，避免为两类账户写两套 Router。

推荐部署：

```text
主账户 / Treasury
  ├── 子账户 market-making
  ├── 子账户 directional
  ├── 子账户 arbitrage
  └── 子账户 hedge
```

主账户默认不交易，只承担资金归集、人工批准后的划拨和全局只读汇总。

### 3.3 多资金槽而非全局单赢家

并非所有策略互斥。V2 把策略分到独立资金槽：

| 资金槽 | 典型策略 | 并行规则 |
|---|---|---|
| `market_making` | PMM、Grid、Bollingrid | 同账户同交易对默认单主策略；不同账户可并行 |
| `directional` | SuperTrend、MACD、突破、均值回归 | 同账户同交易对方向冲突时互斥 |
| `relative_value` | Funding、Basis、XEMM、Stat Arb | 机会驱动，可与行情型策略并行 |
| `hedge` | Hedge、Protect | 覆盖层，不作为普通收益候选 |
| `liquidity` | LP、再平衡 | 独立链上资金和 Gateway 上下文 |
| `reserve` | 现金 | 永远保留最低安全储备 |

Router 输出各资金槽的目标账户、策略和资金比例，而不是只输出一个 `recommended_strategy`。

### 3.4 Evolution 与 Routing 单一写入者

策略进化 Loop 和运行路由器必须保持明确边界：

| 组件 | 唯一职责 | 禁止行为 |
|---|---|---|
| Evolution Loop | 实验、证据、champion/challenger、不可变候选版本 | 直接启停 Account Worker、修改活动部署 |
| Routing Supervisor | 消费 Release Manifest、选择账户、生成 RoutePlan、管理 desired state | 修改研究 champion 或伪造策略证据 |
| Account Worker | 执行幂等 desired state、回读余额/订单/仓位 | 自主选择候选或自动恢复被 Router 停止的策略 |

交接协议：

```text
Evolution
  -> Release Manifest(candidate_id, config_hash, artifact_ref, allowed_environments)
  -> Routing Supervisor
  -> RoutePlan(account_id, candidate_id, lifecycle target)
  -> Account Worker
  -> Runtime Evidence
  -> Evolution
```

Routing 配置强制 `allow_evolution_auto_start=false`，启用集成时还会读取 `conf/strategy_evolution.json`，要求 `policy.auto_start_paper_candidates=false`。路由侧可聚合 Evolution 实际产出的 `data/strategy-evolution/strategies/*/paper/release-manifest.json`；没有 Manifest、候选 ID 不一致、配置 Hash 不一致、环境不允许或发布过期都会关闭候选准入。

## 4. 多维市场与账户快照

### 4.1 市场状态

底层不再用单一枚举保存全部行情事实：

```yaml
market_state:
  timestamp: 1783887600
  symbol: BTC-USDT
  direction: up
  trend_strength: 0.72
  volatility_bucket: high
  realized_volatility: 0.031
  liquidity_bucket: healthy
  spread_bps: 1.8
  depth_10bps_quote: 420000
  breakout_up_probability: 0.35
  breakout_down_probability: 0.04
  mean_reversion_score: 0.22
  funding_opportunity: true
  basis_edge_bps_after_cost: 8.4
  data_fresh: true
  risk_flags: []
```

界面可以继续显示“上涨趋势”主标签，但评分器必须使用完整状态向量。

### 4.2 固定特征分组

固定特征是可复算的事实层：

- 多周期：1m、5m、15m、1h 的 OHLCV、趋势和波动。
- 盘口：spread、深度、imbalance、成交冲击、数据年龄。
- 衍生品：资金费率、基差、OI、强平和多空比。
- 执行成本：maker/taker 费率、滑点、退出缓冲和资金占用。
- 策略状态：订单年龄、成交质量、库存、PnL、回撤和异常率。
- 账户状态：余额、可用保证金、仓位、挂单、风险率和划拨状态。

任何特征必须带：

```text
value + observed_at + source + quality + stale_after
```

没有时间和质量信息的特征不得进入自动路由。

## 5. 账户配置模型

完整示例见：

```text
reports/examples/strategy_router_accounts.example.yml
```

### 5.1 TradingAccountConfig

| 字段 | 含义 |
|---|---|
| `id` | 内部稳定账户 ID，不使用交易所 UID |
| `kind` | `master`、`subaccount` 或 `independent` |
| `parent_id` | 子账户对应的主账户；独立账户为空 |
| `exchange` | 交易所标识 |
| `exchange_account_ref` | 交易所账户/子账户身份引用；纸盘使用本地别名 |
| `connector` | Hummingbot Connector 名称 |
| `credential_ref` | 环境变量前缀或外部 Secret 引用，不是密钥本身 |
| `environment` | `paper`、`canary` 或 `live` |
| `worker_id` | 独立 Hummingbot 实例或容器 ID |
| `position_mode` | `ONEWAY`、`HEDGE`；扩展连接器后可支持 `SPLIT` |
| `margin_mode` | `ISOLATED` 或 `CROSS` |
| `settlement_asset` | USDT、USDC 等结算资产 |
| `allowed_sleeves` | 该账户允许承载的资金槽 |
| `allowed_pairs` | 允许交易的白名单 |
| `allocation` | 资金上限、最低储备和目标区间 |
| `risk` | 本账户硬风控限额 |
| `transfer_policy` | 是否允许划拨、审批要求、冷却和日限额 |

示例中的资金、回撤、分数差和冷却参数只是用于验证配置关系的纸盘初值，不是经过实盘校准的默认值。

### 5.2 密钥约束

配置只允许引用：

```yaml
credential_ref: env-prefix:GATE_MM
```

纸盘账户必须使用：

```yaml
credential_ref: paper:none
```

运行环境再提供：

```text
GATE_MM_API_KEY
GATE_MM_API_SECRET
```

禁止出现：

- 明文 API Key、Secret、密码或助记词。
- 主账户密钥复用于交易子账户。
- Router 进程读取不需要的提现或资金管理权限。
- 纸盘 Worker 挂载实盘密钥。

最小权限建议：

- 交易子账户：只读账户、读取行情、下单和撤单；禁止提现和内部划拨。
- 主账户 Treasury：只读账户和内部划拨；禁止交易和提现。
- Router：不直接持有任何交易所密钥，只调用 Account Worker 的受限控制协议。
- TransferExecutor：与交易 Worker 分离，并使用独立审批和审计。

### 5.3 账户健康

账户进入候选池前必须满足：

```text
credentials_ready
connector_ready
market_data_fresh
balances_fresh
position_snapshot_fresh
no_unreconciled_orders
not_transfer_locked
not_risk_halted
```

任何一项失败，账户只能保持现状、排空或保护，不能承接新策略。

## 6. 策略配置与运行适配器

现有 Promotion Adapter 保留，用于验证策略是否能从 shadow 晋级。另建 `RuntimeStrategyAdapter` 管理运行期：

```python
class RuntimeStrategyAdapter:
    def eligible(self, snapshot, account) -> GateResult: ...
    def score(self, snapshot, account) -> ScoreComponents: ...
    def build_target(self, allocation) -> StrategyTarget: ...
    def start(self, target) -> LifecycleResult: ...
    def quiesce(self) -> LifecycleResult: ...
    def is_drained(self) -> bool: ...
    def health(self) -> StrategyHealth: ...
    def rollback(self) -> LifecycleResult: ...
```

每个策略声明：

- 必需特征和最大数据年龄。
- 可运行账户类型和资金槽。
- 支持的交易对、方向和 Margin/Position Mode。
- 与其他策略的兼容关系。
- 最低资金、最大资金、最大仓位和最大订单数。
- 停止、排空、超时和回滚方式。
- 发布阶段：shadow、paper、canary、live。

## 7. 策略准入和评分

### 7.1 先准入，后评分

准入门禁包括：

- 策略 Promotion Stage 允许当前环境运行。
- 必需特征完整且新鲜。
- Account Worker 健康。
- 交易对、资金槽和账户白名单匹配。
- 预期优势能够覆盖费用、滑点和退出缓冲。
- 账户与全局风险预算均有余量。
- 兼容矩阵允许与现有策略共存。

不满足准入的策略没有分数，不能被 AI 重新激活。

### 7.2 初始评分结构

建议纸盘第一版采用以下可解释权重：

| 评分项 | 初始权重 | 来源 |
|---|---:|---|
| 行情与策略适配 | 0.35 | 固定特征 |
| 费用后预期优势 | 0.25 | 回测、盘口、费率 |
| 流动性与执行质量 | 0.15 | 盘口和历史成交 |
| 策略近期健康度 | 0.15 | 纸盘运行证据 |
| AI 路由调整 | 0.10 | 结构化 AI 输出 |

这些是影子期起始权重，不是永久参数。权重只能通过含成本 walk-forward 和纸盘证据调整。

```text
base_score =
    0.35 * regime_fit
  + 0.25 * expected_edge_after_cost
  + 0.15 * execution_quality
  + 0.15 * strategy_health

final_score =
    base_score
  + bounded_ai_adjustment
  - switch_cost_penalty
  - concentration_penalty
  - correlation_penalty
```

风险门禁不进入该公式；触发风险时直接 veto 或 `PROTECT`。

## 8. AI 路由协议

### 8.1 AI 的唯一职责

AI 接收：

- 多维市场状态摘要。
- 已通过硬准入的候选策略。
- 每个候选的固定评分分解。
- 当前账户、资金槽和正在运行的策略。
- 最近路由历史和切换成本。

AI 只返回：

```json
{
  "abstain": false,
  "ttl_seconds": 300,
  "confidence": 0.79,
  "strategy_adjustments": {
    "pmm_mister": 0.06,
    "grid_strike": -0.02,
    "supertrend_v1": 0.03
  },
  "reason_codes": [
    "range_structure_stable",
    "maker_edge_positive"
  ]
}
```

约束：

- 调整值被配置限制在 `[-max_adjustment, +max_adjustment]`。
- 只允许返回请求中的候选 ID。
- `ttl_seconds` 过期后不能复用。
- JSON、枚举、范围和候选集合全部使用本地 Schema 校验。
- 超时、空内容、格式错误、未知候选或熔断时，AI 分数记为 0。
- AI 缺失不会停止固定路由；它也不会自动触发保护，保护由硬规则判断。

推荐模型策略：

- 常规影子评分：`deepseek-v4-flash`，非思考模式。
- 争议复核：`deepseek-v4-pro`，仅在固定评分接近或信号冲突时调用。
- 模型名、请求版本、Prompt Hash 和响应指纹必须进入决策账本。

## 9. 组合路由输出

Router 输出 `RoutePlan`，而不是直接调用交易接口：

```yaml
route_plan:
  decision_id: route-20260713-0001
  effective_at: 2026-07-13T06:30:00Z
  expires_at: 2026-07-13T06:35:00Z
  environment: paper
  allocations:
    - account_id: subaccount-market-making
      sleeve: market_making
      strategy_id: pmm_mister
      trading_pair: BTC-USDT
      target_capital_quote: 3000
      lifecycle_action: continue
    - account_id: subaccount-arbitrage
      sleeve: relative_value
      strategy_id: funding_rate_arb
      trading_pair: BTC-USDT
      target_capital_quote: 2500
      lifecycle_action: start
  reserve_quote: 2500
  blocked_candidates:
    - strategy_id: supertrend_v1
      reason_codes: [score_delta_too_small]
```

RoutePlan 必须满足：

- 所有账户分配之和不超过可路由净资产。
- 每个账户和资金槽满足上下限。
- 全局现金储备不低于配置。
- 每个目标都能追溯到固定分数、AI 调整和风险结果。
- 重复处理同一 `decision_id` 必须幂等。

## 10. 策略兼容与订单所有权

兼容性分为：

- `compatible`：允许同时运行。
- `conditional`：满足账户、交易对、方向或资金条件后允许。
- `exclusive`：不得同时运行。

默认纪律：

```text
同一 account_id + connector + trading_pair + position_side
只能有一个 position owner
```

跨子账户可以同时运行同一交易对的不同策略，但全局风险仍需聚合净敞口和相关性。

初始兼容矩阵：

| 策略组合 | 默认关系 | 说明 |
|---|---|---|
| PMM + Funding Arb | compatible | 收益来源不同，仍需总敞口限制 |
| Grid + Funding Arb | compatible | 套利独立资金槽 |
| Trend + Hedge | compatible | Hedge 是风险覆盖层 |
| PMM + Grid | conditional | 同账户同交易对默认互斥；独立子账户可并行 |
| Trend Long + Trend Short | exclusive | 同资金槽方向冲突 |
| 两个同类 Grid | exclusive | 避免重复挂单和费用竞争 |
| PMM + 同交易对方向策略 | conditional | 必须独立账户并纳入全局净敞口 |

## 11. 安全切换状态机

```text
STABLE
  -> CANDIDATE
  -> CONFIRMING
  -> DRAINING_OLD
  -> STARTING_NEW
  -> CANARY
  -> STABLE
```

异常分支：

```text
任意状态 -> PROTECT
STARTING_NEW -> ROLLBACK
DRAINING_OLD -> DRAIN_TIMEOUT -> PROTECT
CANARY -> HEALTH_FAILED -> ROLLBACK
```

切换前至少验证：

- 新候选连续多个闭合路由周期领先。
- 新旧分数差超过配置阈值。
- 当前策略满足最短驻留时间。
- 账户不在冷却、划拨、对账或风险锁定状态。
- 旧策略能够停止新建订单并撤销未成交单。
- 旧仓位已按策略声明完成平仓、转交或保留。
- 新 Worker 配置、资金和 Connector 均已就绪。

切换过程不能依赖“停止后下一个 tick 自动重启”的通用 Controller 行为。Supervisor 必须保存显式 `desired_state`，只有目标状态为 `RUNNING` 的 Controller 才允许恢复。

## 12. 资金划拨

资金划拨是独立工作流，不是普通 Router 动作。

```text
RoutePlan 提出资金缺口
  -> TransferPlanner
  -> GlobalRisk 审核
  -> 人工批准或预授权策略
  -> TransferExecutor
  -> 余额回读
  -> 对账完成
  -> Account 可用于新策略
```

默认规则：

- 纸盘可以模拟划拨，实盘第一阶段禁止自动划拨。
- 主账户仅向白名单子账户划拨。
- 有持仓、未完成订单或未对账状态时不得抽走保证金。
- 配置最小转账额、单次上限、每日上限和冷却时间。
- 失败、超时或回读不一致进入 `transfer_locked`，不得重试轰炸。
- 划拨操作使用独立权限和审计，不复用只交易 API Key。
- AI 只能提出目标资金比例，不能调用 TransferExecutor。

## 13. 两层风控

### 13.1 账户本地硬风控

每个 Worker 独立执行：

- 最大仓位、最大订单和最大挂单年龄。
- 最大单策略回撤和日亏损。
- 市场数据陈旧、Connector 断线和订单状态不一致。
- 逐仓/全仓、杠杆、方向和交易对白名单。
- Stop、Cancel、Reduce-only 和紧急排空。

### 13.2 全局组合风控

Supervisor 聚合所有独立账户和子账户：

- 交易所、币种、方向和策略家族净敞口。
- 相关资产集中度。
- 同一收益来源的策略重复暴露。
- 总保证金占用、现金储备和最大回撤。
- 交易所或 Connector 单点故障暴露。
- 账户状态和余额快照新鲜度。

本地风控和全局风控任何一层拒绝，RoutePlan 都不能执行。

## 14. 故障与降级

| 故障 | 默认动作 |
|---|---|
| AI 超时、空响应、Schema 错误 | AI 调整归零，继续固定路由 |
| 固定特征不完整 | 禁止新切换；按风险状态保持或保护 |
| 市场数据陈旧 | 停止新增风险，撤销陈旧挂单，必要时保护 |
| Account Worker 离线 | 账户移出候选池，保留恢复和人工排查任务 |
| 余额/仓位对账失败 | 锁定账户，不启动新策略 |
| 旧策略无法排空 | 超时后保护，不强行启动新策略 |
| 新策略启动失败 | 回滚旧策略或进入保护 |
| 主账户划拨失败 | 锁定划拨，不影响其他健康账户继续运行 |
| 全局风险快照过期 | 禁止扩仓和资金划拨 |

## 15. 决策账本与后验评估

每个路由周期追加一条不可覆盖记录：

```text
decision_id
market_snapshot_hash
account_snapshot_hashes
feature_versions
eligible_candidates
fixed_score_components
ai_provider/model/prompt_hash/response_hash
ai_adjustments
risk_gate_results
compatibility_results
switch_costs
selected_allocations
blocked_candidates
transition_events
realized_outcomes_5m/30m/4h/24h
```

后验评估至少包含：

- AI 加入前后的路由差异。
- 费用后收益、回撤、换手率和切换成本。
- 各行情维度下的策略胜率与校准误差。
- AI abstain、失败、空响应和被风控否决的比例。
- 多账户总敞口与单账户事实是否一致。

只有证明“固定评分 + AI”优于固定评分基线，才允许提高 AI 影响上限。

## 16. 代码落点与当前状态

已实现：

```text
hummingbot/strategy_v2/routing/
  __init__.py            纯领域包入口
  data_types.py          MarketState、AccountSnapshot、候选和 RoutePlan
  config.py              YAML Schema、账户图、权限和单一写入者校验
  account_registry.py    账户健康与策略准入
  scoring.py             固定评分和有界 AI 调整接口
  compatibility.py       策略兼容矩阵
  allocator.py           多账户、多资金槽分配
  risk.py                全局资金、敞口、回撤和储备门禁
  release.py             Evolution 单策略 Manifest 适配、聚合与准入契约
  transition.py          确认、排空、启动、灰度、回滚状态机
  ledger.py              幂等、只追加 RoutePlan 账本
  supervisor.py          无副作用 RoutePlan 编排
  adapters.py            Evolution Controller、市场和账户运行快照适配
  ai_provider.py         DeepSeek JSON、超时、边界校验和持久熔断
  worker.py              纸盘 Worker 计划、白名单启动、停止和回读对账
  transfer.py            人工批准、幂等的纸盘划拨模拟器
  service.py             一次性或持续运行的端到端路由服务

scripts/validate_strategy_routing_config.py
scripts/run_strategy_router.py
scripts/adopt_strategy_router_worker.py
scripts/simulate_strategy_router_transfer.py
test/hummingbot/strategy_v2/routing/
```

接入新策略时只需要 Evolution 产出同一 Release Manifest，并提供白名单
`run_*_paper.sh`；Worker 不再硬编码 PMM 策略名。当前仓库已有可实际配对的
PMM paper release，SuperTrend 和 Funding 尚无 paper release，因此不会被伪造为可启动候选。

仍被硬关闭：

```text
真实交易所下单
真实主账户/子账户资金划拨
无人工授权的 canary/live 发布
AI 直接控制订单、杠杆或资金
```

现有模块迁移建议：

- `routers/feature_engine.py`：保留为单市场特征实现，逐步被 `FeatureService` 调用。
- `routers/router.py`：保留为断网和 AI 故障时的确定性基线。
- `routers/adapters.py`：继续承担 Promotion Adapter；运行适配器放入新目录。
- `controllers/generic/ai_strategy_router.py`：保留纸盘兼容入口，不再作为最终多账户 Supervisor。
- `scripts/v2_with_controllers.py`：抽取账户 Worker 的数据健康、回撤和 desired-state 生命周期能力。

## 17. 配置加载与验证

建议未来运行配置放在忽略提交的路径：

```text
conf/strategy_router_accounts.yml
```

仓库只提交：

```text
reports/examples/strategy_router_accounts.example.yml
```

启动前必须执行配置验证：

```bash
python3 scripts/validate_strategy_routing_config.py
```

- ID 唯一，`parent_id` 无环且存在。
- 每个交易账户有独立 `credential_ref` 和 `worker_id`。
- `paper` 账户不能引用 live credential namespace。
- 资金比例、限额和储备合法。
- 策略绑定只引用已注册策略和资金槽。
- 同账户同交易对的默认 position owner 唯一。
- 实盘账户必须声明人工批准和发布阶段。
- 所有外部 Secret 引用存在，但验证日志不得打印值。

## 18. 落地状态

### 阶段 A：纯确定性多账户骨架（完成）

- 已实现账户配置、账户快照、多资金槽和全局风险汇总。
- 已实现多维 MarketState、固定准入和固定评分。
- 已实现安全切换状态机和只追加 RoutePlan 账本。
- 已实现 Evolution 单策略 Release Manifest 适配、聚合和单一写入者门禁。
- RoutePlan 本身保持无交易副作用。

### 阶段 B：纸盘运行适配（完成通用协议）

- `pmm_mister` 已有真实 Release Manifest，可生成独立 Worker 启动目标。
- 运行器按 Release Manifest 和 `run_*_paper.sh` 通用协议工作。
- 没有 paper release 的策略保持不可启动，不用占位配置绕过发布门禁。
- 已实现独立 Worker、排空/停止动作、运行快照回读和全局净敞口校验。
- 已有旧纸盘容器可先验证 paper runtime 后收编；未收编容器会以 `unmanaged_running_worker` 阻止重复启动。
- 替换旧 Worker 前必须连续三个不同 `decision_id`；缺少重启密码时，系统在 Docker stop 之前拒绝 drain。

### 阶段 C：AI 影子路由（完成接口，默认关闭）

- 接入 DeepSeek，记录有界调整但不影响 RoutePlan。
- 建立固定基线与 AI 影子结果对照。
- 验证空响应、超时、熔断和 Prompt 版本。

### 阶段 D：AI 有界参与纸盘（完成接口，需显式启用）

- AI 调整上限初始不超过 0.10。
- 只影响通过准入的候选排序。
- 不允许 AI 触发资金划拨、改杠杆或绕过切换门槛。

### 阶段 E：人工批准的灰度（未授权，保持关闭）

- 账户、策略、交易对和金额逐项白名单。
- 独立人工批准 canary 和 live release。
- 任一证据过期自动退回 paper/shadow。

## 19. 纸盘验收标准

在接入 AI 前，必须满足：

1. 独立账户和主账户子账户可以使用同一配置协议加载。
2. 每个交易账户由独立 Worker/容器运行，密钥和状态不串用。
3. PMM、趋势和 Funding 三个资金槽可同时纸盘运行。
4. 同账户同交易对冲突策略会被兼容门禁拒绝。
5. 全局风险能聚合多个账户的净敞口、余额和回撤。
6. 数据陈旧、Worker 离线和对账失败会阻止新增风险。
7. 旧策略未排空时，新策略不会启动。
8. RoutePlan、生命周期和后验结果完整写入只追加账本。
9. 配置和日志中不存在密钥、密码或助记词。
10. 所有测试先在 paper 环境通过，自动划拨保持关闭。

## 20. 当前明确不做

- 不让 AI 直接生成交易动作。
- 不在一个全局单标签中强行表达所有市场机会。
- 不让所有策略争夺唯一全局席位。
- 不用同一个 API Key 驱动所有账户 Worker。
- 不在持仓和订单未对账时自动抽走保证金。
- 不在第一版实现实盘自动资金划拨。
- 不因为策略数量增加就默认提高总风险预算。
