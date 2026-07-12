import { StrategyTable } from "@/components/StrategyTable";
import { MetricCard, StatusPill } from "@/components/StatusPill";
import { getStrategyCatalog, getStrategyPromotionState } from "@/lib/data";
import { zhLabel } from "@/lib/i18n";

export const dynamic = "force-dynamic";

export default function StrategiesPage() {
  const catalog = getStrategyCatalog();
  const promotion = getStrategyPromotionState();
  const statusCount = (status: string) => catalog.strategies.filter((item) => item.status === status).length;
  return <div className="page-stack"><section className="page-hero"><div><span className="eyebrow">策略资产</span><h1>策略资产库</h1><p>收集不等于启用。每个策略都保留来源、许可证、收益证据、适用行情、风险与适配器状态。</p></div></section><section className="metric-grid"><MetricCard label="已启用" value={String(statusCount("enabled"))} hint="路由器可直接执行" tone="green" /><MetricCard label="影子评估" value={String(statusCount("shadow"))} hint="已有实现，等待验证证据" tone="blue" /><MetricCard label="研究池" value={String(statusCount("research"))} hint="只收集机制与来源" /><MetricCard label="核心晋级链" value={String(promotion.strategies.length)} hint="趋势、震荡、套利" tone="amber" /></section><div className="alert-banner alert-info"><strong>盈利声明规则</strong><span>{catalog.policy.profitability_claim}</span></div><section className="panel"><div className="panel-head"><div><span className="eyebrow">核心晋级</span><h2>核心策略晋级状态</h2></div><StatusPill tone="green">实盘默认关闭</StatusPill></div><div className="source-grid">{promotion.strategies.map((item) => <div className="source-card" key={item.strategy}><strong>{item.strategy_label || item.strategy}</strong><code>{item.strategy} · {item.adapter}</code><span>{item.intended_regimes.map(zhLabel).join(" · ")}</span><StatusPill tone={item.stage === "live_enabled" ? "green" : item.stage === "paper_enabled" ? "blue" : "amber"}>{item.stage_label || zhLabel(item.stage)}</StatusPill><small>{item.blocking_gates.length} 个门禁待完成 · 纸面运行至少 {item.minimum_paper_hours} 小时</small></div>)}</div></section><StrategyTable strategies={catalog.strategies} /><section className="panel"><div className="panel-head"><div><span className="eyebrow">开源研究</span><h2>研究来源与许可证边界</h2></div></div><div className="source-grid">{catalog.sources.map((source) => <a className="source-card" href={source.url} target="_blank" rel="noreferrer" key={source.repo}><strong>{source.name}</strong><code>{source.repo}</code><span>{source.role}</span><small>{source.license}</small></a>)}</div></section></div>;
}
