# AI 策略路由器工程蓝图

> 本文记录第一版单账户规则路由器及其落地过程。多账户、主账户/子账户、并行资金槽、AI 有界评分和安全切换的 V2 目标设计见 [`strategy_router_v2_design.md`](strategy_router_v2_design.md)，账户配置示例见 [`examples/strategy_router_accounts.example.yml`](examples/strategy_router_accounts.example.yml)。

本文档用于把“覆盖主流策略 + AI 根据盘面切换策略”的想法落成工程蓝图。核心结论是：不要让 AI 直接预测买卖点，而是让 AI 做市场状态识别、策略适配评分、策略失效预警和仓位渐进切换；具体下单继续交给 Hummingbot 的控制器与执行器。

## 1. 核心定位

目标不是一次性写出“万能策略”，而是构建一个上层调度系统：

```text
市场数据
  -> 特征引擎
  -> 行情状态识别
  -> 策略评分
  -> 风险门禁
  -> 策略路由器
  -> Hummingbot 控制器／执行器
  -> 订单
```

AI 路由器每个周期回答的不是“现在买还是卖”，而是：

```text
当前市场属于什么状态？
当前正在运行的策略还能不能继续跑？
哪个策略家族更适合现在？
是否需要降仓、停止、切换或只观察？
```

这比直接预测涨跌更现实，也更适合作为产品竞争力。

## 2. 当前仓库已有能力

Hummingbot 官方文档把 V2 分为执行器、脚本和控制器。控制器是生产级模块，可同时运行多个策略；执行器负责具体订单工作流。当前仓库也符合这个结构。

### 2.1 V2 控制器

| 类型 | 本地模块 | 可用策略能力 | 适合行情 | Router 复用方式 |
|---|---|---|---|---|
| 网格 | `controllers/generic/grid_strike.py` | 单区间网格 | 震荡、均值回归 | 直接作为震荡策略候选 |
| 多网格 | `controllers/generic/multi_grid_strike.py` | 多区间/多配置网格 | 分层震荡区间 | 可作为高级网格候选 |
| 布林网格 | `controllers/directional_trading/bollingrid.py` | 布林信号 + 网格执行 | 波动回归、局部超买超卖 | 可作为“带方向过滤的网格” |
| 组合网格 | `controllers/generic/quantum_grid_allocator.py` | 按组合偏离生成买/卖网格 | 组合再平衡 + 震荡 | 可作为组合型路由候选 |
| 做市 | `controllers/market_making/pmm_simple.py` | 简单双边挂单 | 低波动、有盘口深度 | 做市候选 |
| 动态做市 | `controllers/market_making/pmm_dynamic.py` | 动态 spread / amount | 低中波动 | 做市候选 |
| D-Man 做市 | `controllers/market_making/dman_maker_v2.py` | DCA/分层做市 | 波动中等、需要分批 | 做市/网格混合候选 |
| PMM 复刻 | `controllers/generic/pmm_v1.py` | 复刻 legacy PMM | 低波动做市 | 兼容型候选 |
| 趋势 | `controllers/directional_trading/supertrend_v1.py` | Supertrend 信号 | 单边趋势 | 趋势策略候选 |
| 趋势/反转 | `controllers/directional_trading/macd_bb_v1.py` | MACD + Bollinger | 趋势或超买超卖过滤 | 趋势候选 |
| 布林 | `controllers/directional_trading/bollinger_v1.py` / `bollinger_v2.py` | 布林带信号 | 震荡或突破前后 | 均值回归/突破候选 |
| D-Man 趋势 | `controllers/directional_trading/dman_v3.py` | DCA 方向交易 | 趋势回撤入场 | 趋势/分批入场候选 |
| 套利 | `controllers/generic/arbitrage_controller.py` | 套利执行 | 跨市场价差 | 套利候选 |
| XEMM | `controllers/generic/xemm_multiple_levels.py` | 跨交易所做市/对冲 | 价差 + 做市 | 套利/做市候选 |
| 统计套利 | `controllers/generic/stat_arb.py` | 价差偏离回归 | 协整/相关品种 | 统计套利候选 |
| 对冲 | `controllers/generic/hedge_asset.py` | 资产风险对冲 | 风险敞口管理 | 风控动作 |
| LP | `controllers/generic/lp_rebalancer/lp_rebalancer.py` | CLMM LP + 再平衡 | DEX LP 收费 | LP 候选 |

### 2.2 V2 执行器

| Executor | 本地模块 | 作用 | Router 价值 |
|---|---|---|---|
| GridExecutor | `hummingbot/strategy_v2/executors/grid_executor/` | 开仓网格、止盈平仓、网格循环 | 震荡策略的核心执行器 |
| PositionExecutor | `hummingbot/strategy_v2/executors/position_executor/` | 带止盈/止损/时间限制的方向仓位 | 趋势、突破、均值回归都可复用 |
| DCAExecutor | `hummingbot/strategy_v2/executors/dca_executor/` | 分批建仓/平仓 | 定额分批执行与受控仓位调整 |
| OrderExecutor | `hummingbot/strategy_v2/executors/order_executor/` | 单笔订单、限价追踪等 | 通用下单执行 |
| ArbitrageExecutor | `hummingbot/strategy_v2/executors/arbitrage_executor/` | 两腿套利 | 价差策略 |
| XEMMExecutor | `hummingbot/strategy_v2/executors/xemm_executor/` | maker-taker 对冲 | 跨所做市 |
| TWAPExecutor | `hummingbot/strategy_v2/executors/twap_executor/` | 时间加权执行 | 大单拆分、再平衡 |
| LPExecutor | `hummingbot/strategy_v2/executors/lp_executor/` | LP 头寸 | DEX LP |

### 2.3 V1 旧版策略

官方文档说明 V1 策略仍支持，但新功能主要集中到 V2。可作为成熟逻辑参考，不建议作为新路由核心。

| V1 策略 | 本地模块 | 借鉴价值 |
|---|---|---|
| Pure Market Making | `hummingbot/strategy/pure_market_making/` | spread、inventory skew、hanging orders |
| Avellaneda Market Making | `hummingbot/strategy/avellaneda_market_making/` | 经典库存风险做市模型 |
| Cross Exchange Market Making | `hummingbot/strategy/cross_exchange_market_making/` | maker-taker 对冲结构 |
| AMM Arbitrage | `hummingbot/strategy/amm_arb/` | DEX/CEX 价差套利 |
| Spot Perpetual Arbitrage | `hummingbot/strategy/spot_perpetual_arbitrage/` | 现货/永续价差 |
| Hedge | `hummingbot/strategy/hedge/` | 风险敞口对冲 |
| Liquidity Mining | `hummingbot/strategy/liquidity_mining/` | 多交易对做市资金分配 |

## 3. 开源项目参考

| 项目 | 官方来源 | 成熟能力 | 对本系统的用法 |
|---|---|---|---|
| Hummingbot | https://hummingbot.org/strategies/ | 交易所连接、做市、套利、V2 Controller/Executor | 实盘执行底座 |
| Freqtrade / FreqAI | https://www.freqtrade.io/en/stable/freqai/ | 机器学习预测、在线再训练、特征工程、模型推理 | 借鉴 AI 特征与训练流程 |
| Freqtrade Callbacks | https://www.freqtrade.io/en/stable/strategy-callbacks/ | custom stoploss、custom ROI、position adjustment、order callbacks | 借鉴策略生命周期回调和失效控制 |
| QuantConnect LEAN | https://www.quantconnect.com/docs/v2/writing-algorithms/key-concepts/algorithm-engine | Algorithm Engine、Alpha、Portfolio、Risk、Execution 分层思想 | 借鉴路由器分层架构 |
| Microsoft Qlib | https://qlib.readthedocs.io/en/latest/introduction/introduction.html | 因子、模型训练、组合回测、在线 serving、强化学习研究 | 借鉴多因子 AI 研究平台 |
| NautilusTrader | https://nautilustrader.io/docs/latest/ | 生产级事件驱动、回测实盘一致性、风险/组合/执行建模 | 借鉴工程可靠性 |
| VectorBT | https://vectorbt.dev/ | 高速批量回测、参数扫描、特征分析 | 用于离线筛选策略参数 |
| vn.py / VeighNa | https://github.com/vnpy/vnpy | CTA、套利、组合、AI Alpha、多因子机器学习 | 借鉴中文量化生态和 AI Alpha 模块 |

## 4. 主流策略家族覆盖图

“涵盖所有市面策略”不应理解为收集无限变体，而是覆盖策略家族。

| 策略家族 | 典型策略 | 当前仓库状态 | 外部参考 | 优先级 |
|---|---|---|---|---|
| 网格 | 固定网格、动态网格、多区间网格 | 已有 | Hummingbot V2 | P0 |
| 均值回归 | Bollinger、RSI、z-score | 部分已有 | Freqtrade、Qlib | P0 |
| 趋势跟随 | Supertrend、MACD、均线突破、动量 | 已有部分 | Freqtrade、LEAN | P0 |
| 做市 | PMM、动态 spread、库存倾斜 | 已有 | Hummingbot、Avellaneda | P0 |
| 套利 | 跨所、AMM、现货永续、三角套利 | 已有部分 | Hummingbot、vn.py | P1 |
| 统计套利 | pair trading、协整、价差回归 | 已有基础 | Qlib、LEAN | P1 |
| DCA / 分批执行 | DCA、TWAP、VWAP | 已有 DCA/TWAP，VWAP script 有示例 | Hummingbot、LEAN | P1 |
| 组合再平衡 | 固定权重、风险平价、波动目标 | 部分已有 | Qlib、vn.py | P1 |
| LP / 收费策略 | CLMM 做 LP、区间管理 | 已有 LP Rebalancer | Hummingbot | P1 |
| 事件驱动 | 新闻、资金费率、清算、OI | 监控基础不足 | FreqAI、自建数据源 | P2 |
| 期权/波动率 | Delta hedge、vol arb | 当前不足 | LEAN、Nautilus | P3 |
| 强化学习 | 执行优化、仓位控制 | 当前不足 | Qlib、FreqAI RL | P3 |

## 5. 市场状态矩阵

AI 路由器的第一层是识别行情状态。状态不是单一标签，可多标签叠加。

| 市场状态 | 识别特征 | 首选策略 | 禁用/降权策略 | 关键风控 |
|---|---|---|---|---|
| 低波动震荡 | ATR 低、布林宽度窄、价格在区间内反复 | 网格、PMM、均值回归 | 趋势突破 | 控制网格密度，避免手续费侵蚀 |
| 高波动震荡 | ATR 高但无方向、影线长 | 宽网格、轻仓做市 | 密集网格、高杠杆 | 降低杠杆，扩大间距 |
| 上升趋势 | ADX/动量上升、均线多头、回撤浅 | 趋势多、DCA 多、突破多 | 做空网格、均值做空 | trailing stop，趋势衰减退出 |
| 下降趋势 | 动量下行、均线空头、反弹弱 | 趋势空、DCA 空 | 买入网格、抄底均值回归 | 限制逆势补仓 |
| 区间突破 | 价格突破区间、ATR 放大、成交量放大 | 趋势/突破 | 原区间网格 | 自动停网格或转保护 |
| 价差扩大 | 两市场价差超过成本，深度足够 | 套利、XEMM | 单边方向策略 | 成本、滑点、腿风险 |
| 极端清算 | 清算量暴增、OI 急降、成交量异常 | 保护模式、观望、短周期反转小仓 | 高杠杆、密集挂单 | 自动降仓/暂停 |
| 低流动性 | 深度薄、spread 扩大、成交减少 | 观望、小额被动单 | 高频网格、套利 | 最小成交深度阈值 |

## 6. 策略失效预警

截图里提到的信号应成为第一批路由器风控输入。

| 失效信号 | 对网格的含义 | 对趋势的含义 | Router 动作 |
|---|---|---|---|
| 网格浮亏扩大 | 可能跳出震荡 | 趋势可能成立 | 降网格仓位，评估转趋势 |
| 价格突破区间 | 原区间假设失效 | 可能进入趋势 | 停旧网格，启动突破/趋势候选 |
| ATR 突然放大 | 网格间距可能过窄 | 趋势/事件驱动增强 | 扩间距、降杠杆或暂停 |
| 成交量异常 | 趋势或清算开始 | 趋势可信度提高 | 提高突破信号权重 |
| OI 快速变化 | 杠杆资金进出 | 趋势/挤压风险 | 降杠杆，降低逆势策略 |
| 清算区被扫完 | 短期反转或继续瀑布 | 需结合价格恢复 | 进入保护模式，等确认 |
| maker fill 质量变差 | 做市被逆向选择 | 趋势可能增强 | 提高 spread 或停止做市 |
| 策略盈亏偏离历史分布 | 策略环境变化 | 模型可能失效 | 冻结加仓，触发回测/复盘 |

## 7. AI 路由器输入特征

### 7.1 基础行情

- OHLCV 多周期：1m、5m、15m、1h。
- order book：bid/ask spread、depth imbalance、top N 深度。
- trades：主动买卖量、成交冲击。
- volatility：ATR、realized volatility、Bollinger width。
- trend：EMA slope、ADX、MACD、Supertrend。
- mean reversion：z-score、RSI、BBP。

### 7.2 衍生品特征

- funding rate。
- open interest。
- long/short ratio。
- liquidation data。
- basis：spot-perp premium。

### 7.3 策略自身状态

- 当前策略类型。
- 持仓方向、仓位价值、杠杆。
- realized PnL、unrealized PnL、fees。
- 最近 N 次交易胜率、平均滑点、maker/taker 比例。
- 当前挂单数量、被撤单数量、成交等待时间。
- 策略是否触发过 stop loss / time limit / limit price。

## 8. 路由器输出动作

路由器不直接发交易订单，而是输出标准决策：

```yaml
decision:
  regime: range_low_vol | range_high_vol | trend_up | trend_down | breakout | extreme | arbitrage
  active_strategy: grid_strike
  recommended_strategy: supertrend_v1
  action: continue | reduce | stop | switch | protect | observe
  confidence: 0.0-1.0
  risk_level: low | medium | high | extreme
  position_scale: 0.0-1.0
  reason_codes:
    - ATR_SPIKE
    - RANGE_BREAK
    - GRID_FLOATING_LOSS_EXPANDING
  cooldown_seconds: 300
```

路由器的动作语义：

| 动作 | 含义 | 执行方式 |
|---|---|---|
| `continue` | 策略继续运行 | 不改动 |
| `reduce` | 降仓或减少挂单 | 停止部分执行器或降低配置 |
| `stop` | 停止当前策略 | 发出停止执行器动作并撤单 |
| `switch` | 切换策略 | 先降低旧仓，再启动新控制器 |
| `protect` | 保护模式 | 停止新开仓，只处理风险 |
| `observe` | 观察 | 不启动策略，只收集信号 |

## 9. 策略切换原则

不能“一刀切”切换，否则会产生滑点、双向打架和过拟合。

### 9.1 渐进切换

```text
旧策略 100% -> 70% -> 30% -> 0%
新策略   0% -> 30% -> 70% -> 100%
```

要求：

- 有 cooldown，避免来回切。
- 新旧策略不能在同一交易对上持有互相冲突的风险敞口，除非显式对冲。
- 切换时先处理风险，再追求收益。

### 9.2 策略互斥

| 当前策略 | 禁止同时运行 | 原因 |
|---|---|---|
| 买入网格 | 强趋势做空 | 方向冲突 |
| 做空网格 | 强趋势做多 | 方向冲突 |
| PMM | 高波动突破策略满仓 | 双边挂单易被逆向选择 |
| 套利 | 同资产大方向仓位 | 干扰套利风险统计 |
| LP | 大额单边趋势仓位 | LP 本身已有库存风险 |

## 10. MVP 分期

### 阶段 0：文档与接口冻结

交付：

- 策略能力地图。
- 市场状态矩阵。
- 路由器输入／输出结构。
- 策略失效信号字典。

目标：先让团队知道“AI 控什么，不控什么”。

### 阶段 1：规则型路由器

先不用大模型，写确定性规则：

- 震荡：启用 grid / PMM。
- 趋势：启用 supertrend / MACD。
- 突破：停网格，转趋势或保护。
- 极端：保护模式。

目标：验证路由架构是否能跑通。

### 阶段 2：评分型路由器

每个策略生成分数：

```text
strategy_score =
  regime_fit_score
  + expected_edge_score
  - risk_score
  - cost_score
  - conflict_penalty
```

目标：允许多个候选策略排序，而不是硬规则。

### 阶段 3：AI 辅助路由器

引入 ML / LLM：

- ML 模型预测市场状态和策略适配概率。
- LLM 负责解释、异常摘要和人工可读决策。
- 重要交易动作仍经过规则风控门。

目标：AI 参与判断，但不绕过风控。

### 阶段 4：自动再训练与策略实验室

参考 FreqAI、Qlib、VectorBT：

- 自动训练市场状态识别模型。
- 批量回测策略参数。
- 记录每次路由器决策和后验表现。
- 定期淘汰失效策略。

目标：形成策略进化闭环。

## 11. 推荐第一版实现范围

第一版不要覆盖所有策略，先覆盖最关键三种行情：

| 行情 | 策略 | 本地模块 |
|---|---|---|
| 震荡 | 网格 | `grid_strike` / `bollingrid` |
| 趋势 | Supertrend / MACD | `supertrend_v1` / `macd_bb_v1` |
| 极端风险 | 保护模式 | 新建 `risk_guard` 或 Router 内置 |

第一版路由器只做三件事：

1. 判断网格还能不能继续跑。
2. 判断是否进入趋势行情。
3. 判断是否进入保护模式。

这就已经能覆盖截图里的核心诉求。

## 12. 建议代码落点

建议新建：

```text
controllers/generic/ai_strategy_router.py
hummingbot/strategy_v2/routers/
  __init__.py
  data_types.py
  feature_engine.py
  regime_detector.py
  strategy_scorer.py
  risk_gate.py
  router.py
```

更稳妥的路径是先做控制器：

```text
controllers/generic/ai_strategy_router.py
```

原因：

- 控制器天然可以读取市场数据提供器。
- 控制器可以发出创建执行器和停止执行器动作。
- 控制器适合生产级多策略调度。
- 不需要改交易所连接器。

## 13. 成败关键

这个系统能不能赚钱，不取决于“策略数量多”，而取决于：

1. 市场状态识别是否稳定。
2. 策略失效能否及时识别。
3. 切换是否渐进，避免反复横跳。
4. 风控是否硬约束，AI 不能越权。
5. 每次决策是否记录，能否后验复盘。

如果只把很多策略堆起来，没有路由纪律，反而会变成多策略互相打架。真正的竞争力是：

```text
策略库覆盖面 + AI 路由判断 + 风控硬门 + 持续复盘进化
```

## 14. 下一步开发建议

建议下一步直接实现阶段 1：

1. 新建 `ai_strategy_router` 控制器。
2. 定义 `MarketRegime`、`RouterDecision`、`StrategyCandidate` 数据结构。
3. 实现第一批特征：ATR、BB width、EMA slope、volume z-score、price range break、grid floating loss。
4. 实现规则路由：range -> grid，trend -> supertrend，extreme -> protect。
5. 先用纸面交易和回测验证路由日志，不急着实盘自动切换。

第一版不要追求“AI 很聪明”，先追求“路由不会乱来”。

## 15. 阶段 1 当前落地状态

已经新增第一版规则型路由器骨架：

```text
hummingbot/strategy_v2/routers/
  __init__.py
  data_types.py
  feature_engine.py
  strategy_registry.py
  router.py

controllers/generic/ai_strategy_router.py
```

当前能力：

- `strategy_registry.py` 登记 26 个候选策略，覆盖 grid、trend、mean reversion、market making、arbitrage、hedge、LP、observe、protect。
- 当前直接启用 5 个：`grid_strike`、`bollingrid`、`trend_long`、`trend_short`、`protect_mode`。
- 其余 21 个先作为 shadow candidates 纳入策略宇宙，但 `enabled=False`，需要特征输入和适配器补齐后再逐个打开。
- `feature_engine.py` 从 K 线和活跃 executor 中计算第一批特征：ATR%、BB width%、EMA slope、volume z-score、区间高低点、活跃策略、活跃 PnL。
- `router.py` 用规则识别低波动震荡、高波动震荡、上涨趋势、下跌趋势、向上突破、向下突破、极端风险。
- `router.py` 还会对全量策略宇宙输出 candidate scores。`enabled=False` 的 shadow candidate 会被降权，只用于观察和复盘，不会直接触发交易。
- `ai_strategy_router.py` 是可加载的 V2 Controller。它默认 `enable_trading=False`，只输出决策状态；显式打开后才会创建或停止 executor。

策略注册状态：

| Family | Candidates | 当前状态 |
|---|---:|---|
| grid | 4 | `grid_strike`、`bollingrid` 已启用；多网格/分配器为 shadow |
| trend | 6 | `trend_long`、`trend_short` 已启用；SuperTrend/MACD/DMAN/AI 信号为 shadow |
| mean_reversion | 2 | Bollinger v1/v2 为 shadow |
| market_making | 5 | PMM/DMAN maker 为 shadow |
| arbitrage | 3 | arbitrage、XEMM、stat arb 为 shadow |
| hedge | 2 | hedge asset、funding arb 为 shadow |
| lp | 1 | LP rebalancer 为 shadow |
| observe | 2 | market/liquidation monitor 为 shadow |
| protect | 1 | `protect_mode` 已启用 |

示例评分逻辑：

```text
range_low_vol:
  grid_strike      0.79 enabled
  bollingrid       0.78 enabled
  pmm_dynamic      0.27 shadow
  pmm_simple       0.27 shadow
  multi_grid       0.26 shadow
```

这让系统先具备“知道市面有哪些策略、当前哪些可能适合”的能力，再逐个补适配器；不会因为策略名已经在注册表里，就直接拿真钱或纸盘去试错。

默认动作：

| Regime | 推荐策略 | Executor |
|---|---|---|
| `range_low_vol` / `range_high_vol` | `grid_strike` | `GridExecutor` |
| `trend_up` / `breakout_up` | `trend_long` | `PositionExecutor` |
| `trend_down` / `breakout_down` | `trend_short` | `PositionExecutor` |
| `extreme` / `unknown` | `protect_mode` | 停止/观察 |

当前设计边界：

- 第一版 Router 不直接管理其他 Controller，只管理自己创建的 Executors。
- 要做“多个 Controller 之间真正切换”，后续应扩展 `v2_with_controllers.py` 或新增 orchestrator script。
- 重要交易动作仍经过硬规则，AI/ML 后续只能作为评分输入，不能绕过 `protect_mode`。

## 16. 纸盘监控入口

当前纸盘实例：

```text
container: hummingbot-ai-router-paper
script config: conf/scripts/conf_ai_strategy_router_paper.yml
controller config: conf/controllers/conf_ai_strategy_router_paper.yml
database: data/conf_ai_strategy_router_paper.sqlite
log: logs/logs_conf_ai_strategy_router_paper.log
```

监控命令：

```bash
python3 scripts/ai_router_monitor.py
```

生成快照报告：

```bash
python3 scripts/ai_router_monitor.py --report reports/ai_strategy_router_live_status.md
```

持续刷新：

```bash
python3 scripts/ai_router_monitor.py --watch 30
```

监控脚本当前会输出：

- Docker 容器状态。
- 最新 Router 决策和最近一次 `protect` 触发原因。
- 订单数、成交数、订单状态分布。
- 从成交日志估算的 BTC 库存、USDT cash、手续费、mark-to-market equity。
- 最近订单和最近成交。

注意：当前 PnL 是纸盘估算值，使用日志中的成交价格、数量和纸盘手续费计算。它适合观察路由和风控闭环，不应直接作为实盘收益结论。

## 17. 自动迭代 Loop

当前自动迭代入口：

```bash
python3 scripts/ai_router_iteration_loop.py
```

持续运行：

```bash
python3 scripts/ai_router_iteration_loop.py --watch 300 --max-iterations 999
```

测试通过后自动重启纸盘并做 post-deploy verify：

```bash
python3 scripts/ai_router_iteration_loop.py --deploy-paper
```

输出：

```text
reports/ai_strategy_router_iteration_latest.md
reports/ai_strategy_router_iteration_latest.json
```

当前 loop 覆盖：

- observe：读取纸盘容器、日志、SQLite、PnL 估算。
- test：编译检查、Router synthetic tests、registry integrity。
- evaluate：识别风险、配置冲突、策略适配 backlog、发布未固化问题。
- deploy：可选重启纸盘容器。
- verify：部署后等待行情初始化，检查容器、最新决策、错误日志。

详细设计：

```text
reports/ai_strategy_router_autonomous_loop.md
reports/ai_strategy_router_strategy_adapter_backlog.md
```

当前边界：

- 自动部署仅限纸盘。
- 自动改代码尚未启用；当前是自动发现问题并生成下一步任务。
- `allow_short=false` 时，`trend_short` 会被配置硬门拦截为 `protect_mode` / `observe`。
- 21 个 shadow 策略需要 adapter 和 paper scorecard 后才能转正。
