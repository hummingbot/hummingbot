import { StatusPill } from "@/components/StatusPill";
import { getIterationSnapshot } from "@/lib/data";
import { zhLabel, zhReasons } from "@/lib/i18n";

export const dynamic = "force-dynamic";

const matrix = [
  ["低波动震荡", "range_low_vol", "网格 / 纯做市", "控制密度、库存和手续费"],
  ["高波动震荡", "range_high_vol", "宽网格 / 均值回归", "降杠杆，突破即停"],
  ["上升趋势", "trend_up", "趋势做多", "回撤止损与时间退出"],
  ["下降趋势", "trend_down", "趋势做空", "必须显式批准做空"],
  ["区间突破", "breakout", "唐奇安突破 / 趋势", "停止原区间网格"],
  ["价差机会", "arbitrage", "资金费率 / 基差 / 跨所做市", "计入费用、滑点与腿风险"],
  ["极端风险", "extreme", "保护模式", "停止新增风险并处理敞口"],
];

export default function RouterPage() {
  const snapshot = getIterationSnapshot();
  const decision = snapshot.live?.latest_decision;
  return <div className="page-stack"><section className="page-hero"><div><span className="eyebrow">行情智能</span><h1>行情与路由</h1><p>AI 层负责识别状态、给策略评分和分配风险，不直接绕过执行器下单。</p></div><StatusPill tone={decision?.action === "protect" ? "red" : "blue"}>{decision?.action_label || zhLabel(decision?.action || "observe")}</StatusPill></section><section className="router-visual"><div className="router-node"><span>01</span><strong>市场数据</strong><small>K 线 · 成交量 · 盈亏</small></div><b>→</b><div className="router-node active"><span>02</span><strong>特征与行情状态</strong><small>{decision?.regime_label || zhLabel(decision?.regime)}</small></div><b>→</b><div className="router-node"><span>03</span><strong>风险门禁</strong><small>{decision?.reason_labels?.join("、") || zhReasons(decision?.reasons)}</small></div><b>→</b><div className="router-node active"><span>04</span><strong>策略路由</strong><small>{decision?.recommended || "protect_mode"}</small></div><b>→</b><div className="router-node"><span>05</span><strong>执行器</strong><small>网格 · 仓位 · 套利</small></div></section><section className="panel"><div className="panel-head"><div><span className="eyebrow">行情矩阵</span><h2>行情—策略适配矩阵</h2></div></div><div className="table-shell"><table><thead><tr><th>行情</th><th>状态编码</th><th>首选家族</th><th>硬风控</th></tr></thead><tbody>{matrix.map((row) => <tr key={row[1]}><td><strong>{row[0]}</strong></td><td><code>{row[1]}</code></td><td>{row[2]}</td><td className="risk-text">{row[3]}</td></tr>)}</tbody></table></div></section><section className="two-column"><div className="panel"><h2>当前实现</h2><ul className="check-list"><li>ATR、布林宽度、EMA 斜率、成交量标准分</li><li>突破使用前序区间，避免当前 K 线污染</li><li>亏损、ATR、成交量触发保护模式</li><li>冷却期与单执行器上限</li></ul></div><div className="panel"><h2>下一阶段</h2><ul className="todo-list"><li>状态概率而非单标签硬切换</li><li>费用后策略预期收益评分</li><li>兼容策略渐进资金分配</li><li>多周期与订单簿特征</li></ul></div></section></div>;
}
