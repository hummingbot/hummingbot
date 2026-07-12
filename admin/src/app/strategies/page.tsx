import { StrategyTable } from "@/components/StrategyTable";
import { MetricCard } from "@/components/StatusPill";
import { getStrategyCatalog } from "@/lib/data";

export const dynamic = "force-dynamic";

export default function StrategiesPage() {
  const catalog = getStrategyCatalog();
  const statusCount = (status: string) => catalog.strategies.filter((item) => item.status === status).length;
  return <div className="page-stack"><section className="page-hero"><div><span className="eyebrow">STRATEGY ASSETS</span><h1>策略资产库</h1><p>收集不等于启用。每个策略都保留来源、许可证、收益证据、适用行情、风险与 Adapter 状态。</p></div></section><section className="metric-grid"><MetricCard label="已启用" value={String(statusCount("enabled"))} hint="Router 可直接执行" tone="green" /><MetricCard label="影子评估" value={String(statusCount("shadow"))} hint="已有实现，等待证据或 Adapter" tone="blue" /><MetricCard label="研究池" value={String(statusCount("research"))} hint="只收集机制与来源" /><MetricCard label="禁止晋级" value={String(statusCount("blocked"))} hint="高风险策略默认封锁" tone="red" /></section><div className="alert-banner alert-info"><strong>盈利声明规则</strong><span>{catalog.policy.profitability_claim}</span></div><StrategyTable strategies={catalog.strategies} /><section className="panel"><div className="panel-head"><div><span className="eyebrow">OPEN SOURCE</span><h2>研究来源与许可证边界</h2></div></div><div className="source-grid">{catalog.sources.map((source) => <a className="source-card" href={source.url} target="_blank" rel="noreferrer" key={source.repo}><strong>{source.name}</strong><code>{source.repo}</code><span>{source.role}</span><small>{source.license}</small></a>)}</div></section></div>;
}
