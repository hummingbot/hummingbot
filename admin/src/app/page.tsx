import Link from "next/link";
import { MetricCard, StatusPill } from "@/components/StatusPill";
import { getIterationSnapshot, getRuntimeSnapshot, getStrategyCatalog } from "@/lib/data";

export const dynamic = "force-dynamic";

const gapTranslations: Record<string, { title: string; action: string }> = {
  "shadow strategies": {
    title: "影子策略尚未接入统一执行适配器",
    action: "按风险与行情覆盖优先级补齐 Adapter，并逐个通过回测、纸面和小额灰度门槛。",
  },
  "strategy adapters": {
    title: "影子策略尚未接入统一执行适配器",
    action: "按风险与证据优先级补齐 Adapter，并逐个通过回测、纸面和小额灰度门槛。",
  },
  "working tree": {
    title: "路由器相关变更尚未形成可追溯版本",
    action: "在下一轮纸面运行前固定提交版本，确保报告、参数与代码能够一一对应。",
  },
  "uncommitted or unpinned": {
    title: "路由器相关变更尚未形成可追溯版本",
    action: "在下一轮纸面运行前固定提交版本，确保报告、参数与代码能够一一对应。",
  },
};

function localizeGap(area: string, title: string, action: string) {
  const normalized = `${area} ${title}`.toLowerCase();
  const match = Object.entries(gapTranslations).find(([key]) => normalized.includes(key));
  return match?.[1] ?? { title, action };
}

export default function OverviewPage() {
  const catalog = getStrategyCatalog();
  const iteration = getIterationSnapshot();
  const runtime = getRuntimeSnapshot();
  const enabled = catalog.strategies.filter((item) => item.status === "enabled").length;
  const structural = catalog.strategies.filter((item) => item.evidence === "structural_edge").length;
  const decision = iteration.live?.latest_decision;
  const equity = Number(iteration.live?.pnl?.equity_quote ?? 0);
  const gaps = iteration.gaps ?? [];
  const runtimeTone = runtime.containerState === "running" ? "green" : runtime.containerState === "stopped" ? "red" : "amber";
  return (
    <div className="page-stack">
      <section className="page-hero"><div><span className="eyebrow">STRATEGY FLEET</span><h1>运营总览</h1><p>把行情判断、策略资产、执行状态和晋级风险放在同一个决策面板。</p></div><div className="hero-actions"><StatusPill tone={runtimeTone}>{runtime.containerState === "running" ? "纸面实例运行中" : "纸面实例未运行"}</StatusPill><span className="snapshot">HEAD {runtime.gitHead}</span></div></section>
      {runtime.reportStale && <div className="alert-banner alert-danger"><strong>运行数据已过期</strong><span>最近报告 {runtime.reportAgeHours === null ? "不可用" : `${runtime.reportAgeHours.toFixed(1)} 小时前`}；当前容器：{runtime.container}。历史盈亏不能当作当前状态。</span></div>}
      <section className="metric-grid">
        <MetricCard label="策略资产" value={String(catalog.strategies.length)} hint={`${enabled} 个已启用，其余需晋级`} tone="blue" />
        <MetricCard label="结构性收益候选" value={String(structural)} hint="资金费率、基差与跨市场价差" tone="green" />
        <MetricCard label="历史订单 / 成交" value={`${iteration.live?.orders ?? 0} / ${iteration.live?.fills ?? 0}`} hint="来自最近一次纸面快照" />
        <MetricCard label="历史估算权益" value={`${equity >= 0 ? "+" : ""}${equity.toFixed(3)} USDT`} hint="仅监控估算，不代表已证明收益" tone={equity >= 0 ? "green" : "red"} />
      </section>
      <section className="two-column">
        <div className="panel"><div className="panel-head"><div><span className="eyebrow">ROUTER</span><h2>最近路由决策</h2></div><Link href="/router">查看路由规则 →</Link></div><div className="decision-card"><div className="decision-route"><span>{decision?.active || "none"}</span><b>→</b><span>{decision?.recommended || "protect_mode"}</span></div><div className="decision-meta"><StatusPill tone="blue">{decision?.regime || "unknown"}</StatusPill><StatusPill tone={decision?.action === "protect" ? "red" : "green"}>{decision?.action || "observe"}</StatusPill><span>置信度 {decision?.confidence || "0"}</span><span>仓位系数 {decision?.scale || "0"}</span></div><p>{decision?.reasons || "等待新的纸面运行数据"}</p></div></div>
        <div className="panel"><div className="panel-head"><div><span className="eyebrow">GATES</span><h2>晋级与运营缺口</h2></div><Link href="/operations">进入迭代中心 →</Link></div><div className="gap-list">{gaps.length ? gaps.slice(0, 5).map((gap, index) => {
          const copy = localizeGap(gap.area, gap.title, gap.action);
          return <div className="gap-item" key={`${gap.area}-${index}`}><StatusPill tone={gap.severity === "high" || gap.severity === "blocker" ? "red" : gap.severity === "medium" ? "amber" : "neutral"}>{gap.severity}</StatusPill><div><strong>{copy.title}</strong><span>{copy.action}</span></div></div>;
        }) : <div className="empty-state">当前报告没有记录缺口，但仍需新的纸面观察窗口。</div>}</div></div>
      </section>
      <section className="panel"><div className="panel-head"><div><span className="eyebrow">PROMOTION PIPELINE</span><h2>策略晋级漏斗</h2></div><Link href="/strategies">管理策略资产 →</Link></div><div className="pipeline">{catalog.policy.promotion_path.map((step, index) => <div className="pipeline-step" key={step}><span>{index + 1}</span><strong>{step.replaceAll("_", " ")}</strong></div>)}</div></section>
    </div>
  );
}
