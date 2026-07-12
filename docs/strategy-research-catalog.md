# 策略研究目录

本目录严格区分**来源成熟度**与**已证明盈利能力**。任何 GitHub 策略都不会因为受欢迎、做过一次回测或被成熟框架收录，就被视为可以盈利。

## 收录规则

所有策略都遵循以下晋级路径：

```text
已收集 -> 影子评估 -> 回测通过 -> 纸面运行 -> 小额灰度 -> 实盘启用
```

晋级必须具备适配器、成本模型、停止与保护路径、滚动验证证据、纸面运行证据和有边界的风险配置。GPL 与 LGPL 来源默认只用于研究，除非已经明确接受其许可证影响；不兼容的代码不得复制进采用 Apache-2.0 的 Hummingbot 核心。

## 研究来源

| 来源 | 可复用内容 | 使用边界 |
|---|---|---|
| [Hummingbot](https://github.com/hummingbot/hummingbot) | 控制器、执行器、纯做市、网格、套利、对冲与流动性模式 | 原生事实来源 |
| [Hummingbot Dashboard](https://github.com/hummingbot/dashboard) | 回测与实例管理流程 | 界面与产品参考 |
| [Freqtrade Strategies](https://github.com/freqtrade/freqtrade-strategies) | 指标组合与研究检查清单 | 示例不保证盈利，不复制 GPL 代码 |
| [Jesse Examples](https://github.com/jesse-ai/example-strategies) | 唐奇安、海龟、双重推力、短周期相对强弱指标和均线交叉 | 示例不宣称盈利 |
| [NautilusTrader](https://github.com/nautechsystems/nautilus_trader) | 订单簿失衡、做市及研究与实盘一致性思路 | 未完成许可证审查前只作设计参考 |
| [QuantConnect LEAN](https://github.com/QuantConnect/Lean) | 期货动量与组合算法 | 跨资产研究参考 |
| [VeighNa](https://github.com/vnpy/vnpy) | CTA 生命周期与运营模式 | 框架参考 |

机器可读目录位于 [`reports/strategy_catalog.json`](../reports/strategy_catalog.json)。管理后台直接读取该文件，展示策略家族、来源、证据等级、适用行情、风险、适配器和晋级状态。

## 核心晋级适配器

第一批可执行晋级队列刻意保持精简：

- `supertrend_v1` 通过 `supertrend_adapter` 覆盖趋势与突破行情。
- `pmm_mister` 通过 `pmm_mister_adapter` 覆盖震荡行情。
- `funding_rate_arb` 通过 `funding_rate_arb_adapter` 覆盖结构性资金费率机会。

三者共用 `hummingbot/strategy_v2/routers/promotion.py` 中失败即关闭的门禁引擎。证据记录在 `reports/strategy_promotion_evidence.json`，`scripts/strategy_promotion_report.py` 生成管理后台使用的晋级状态。没有计费滚动验证、最低纸面观察窗口以及明确的小额灰度和实盘审批，任何适配器都不能进入实盘阶段。

## 当前覆盖范围

目录覆盖结构性套利、网格、趋势、均值回归、做市、流动性提供、组合对冲、执行算法和观察特征。不具备独立市场优势的仓位放大方式不属于产品范围。

## 产品原则

系统优化目标是**扣除切换成本后的样本外净风险调整收益**。策略数量不是关键指标；少量经过验证的策略，比大量未经验证的实现更有价值。
