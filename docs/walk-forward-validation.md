# 计费滚动验证框架

该框架用于验证策略在样本外区间、真实成本假设下是否仍有正向优势。它不会因为单次回测盈利就自动晋级策略。

## 验证流程

每一折都严格执行：

1. 使用固定长度训练窗口比较候选参数。
2. 在训练窗口结束后保留隔离窗口，减少边界泄漏。
3. 只把训练期最佳参数用于紧随其后的样本外窗口。
4. 样本外结果不参与当前折参数选择。
5. 聚合所有样本外折，统一检查盈利折比例、费用后净收益、最大回撤和最低折数。

## 成本模型

- Hummingbot 回测引擎直接扣除手续费。
- 根据往返成交额额外扣除滑点。
- 每次建立持仓额外扣除策略切换成本。
- 按资金规模与窗口长度扣除资金费率成本。

默认假设为手续费 4 基点、滑点 2 基点、切换成本 1 基点、每日资金费率成本 0.01%。这些参数都可以通过命令行覆盖。

## 超级趋势验证

运行完整默认验证：

```bash
python scripts/walk_forward_supertrend.py
```

当前已执行的快速实证验证：

```bash
python scripts/walk_forward_supertrend.py \
  --days 7 \
  --train-days 3 \
  --test-days 1 \
  --candidate-count 3 \
  --minimum-folds 3
```

结果写入：

- `reports/supertrend_walk_forward_latest.json`
- `reports/supertrend_walk_forward_latest.md`

当前 7 天快速验证完成 3 个样本外折，3 折均未盈利，费用后净收益为负。因此 `supertrend_v1` 必须继续保持影子状态，不能进入纸面晋级。

## 高级纯做市验证

```bash
python scripts/walk_forward_pmm_mister.py
```

结果写入：

- `reports/pmm_mister_walk_forward_latest.json`
- `reports/pmm_mister_walk_forward_latest.md`

当前 ETH-USDT 永续 7 天验证完成 3 个样本外折，3 折均盈利，费用后净收益为正，保护性停止路径也已通过单元验证。策略已晋级到“回测通过”，但 72 小时纸面评分和人工灰度批准仍未完成，因此不会自动进入实盘。

## 资金费率套利验证

```bash
python scripts/walk_forward_funding_arb.py
```

验证器直接读取 Binance 资金费率与标记价格历史，以及 Hyperliquid 小时资金费率与 K 线历史。模拟同时计入双腿资金费率现金流、基差变化、两边开平仓手续费和滑点，并根据 Binance 历史结算时间动态推断 4 小时或 8 小时结算周期。

结果写入：

- `reports/funding_arb_walk_forward_latest.json`
- `reports/funding_arb_walk_forward_latest.md`

当前 WIF 60 天验证完成 6 个样本外折，没有盈利折，费用后净收益为负，因此继续保持影子状态。

## 使用边界

- 短窗口结果只用于验证框架和发现明显问题，不代表长期策略结论。
- 只有更长时间、多市场和多行情状态验证通过后，才能把 `backtest_passed` 和 `walk_forward_passed` 改为真。
- 修改证据后必须重新运行 `scripts/strategy_promotion_report.py`。
