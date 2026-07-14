import Link from "next/link";
import { MetricCard, StatusPill } from "@/components/StatusPill";
import { getIterationSnapshot, getStrategyCatalog, getUnifiedOperationsSnapshot } from "@/lib/data";
import { zhLabel, zhReasons } from "@/lib/i18n";

export const dynamic = "force-dynamic";

const gapTranslations: Record<string, { title: string; action: string }> = {
  "shadow strategies": {
    title: "影子策略尚未接入统一执行适配器",
    action: "按风险与行情覆盖优先级补齐适配器，并逐个通过回测、纸面和小额灰度门槛。",
  },
  "strategy adapters": {
    title: "影子策略尚未接入统一执行适配器",
    action: "按风险与证据优先级补齐适配器，并逐个通过回测、纸面和小额灰度门槛。",
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
  const unified = getUnifiedOperationsSnapshot();
  const { runtime, execution } = unified;
  const enabled = catalog.strategies.filter((item) => item.status === "enabled").length;
  const structural = catalog.strategies.filter((item) => item.evidence === "structural_edge").length;
  const decision = iteration.live?.latest_decision;
  const gaps = iteration.gaps ?? [];
  return (
    <div className="page-stack">
      <section className="page-hero"><div><span className="eyebrow">策略舰队</span><h1>运营总览</h1><p>策略目录、路由报告和交易账本各有边界；当前执行状态只取自同一份纸盘运行快照。</p></div><div className="hero-actions"><StatusPill tone={execution.tone}>{execution.stateLabel}</StatusPill><Link className="snapshot" href="/trading">查看交易账本 →</Link></div></section>
      {runtime.reportStale && <div className="alert-banner alert-danger"><strong>路由评估报告已过期</strong><span>最近报告 {runtime.reportAgeHours === null ? "不可用" : `${runtime.reportAgeHours.toFixed(1)} 小时前`}；不影响交易账本的实时口径。当前实例请以“交易账本”为准。</span></div>}
      <section className="metric-grid">
        <MetricCard label="策略资产" value={String(catalog.strategies.length)} hint={`${enabled} 个目录已启用，不等于当前容器运行`} tone="blue" />
        <MetricCard label="结构性收益候选" value={String(structural)} hint="资金费率、基差与跨市场价差" tone="green" />
        <MetricCard label="当前纸盘委托 / 成交" value={`${execution.activeOrderCount} / ${execution.fillCount}`} hint={execution.scopeLabel} tone="blue" />
        <MetricCard label="当前账本状态" value={execution.stateLabel} hint={execution.stateDetail} tone={execution.tone} />
      </section>
      <section className="two-column">
        <div className="panel"><div className="panel-head"><div><span className="eyebrow">策略路由</span><h2>最近记录的路由决策</h2></div><Link href="/router">查看路由规则 →</Link></div><div className="decision-card"><div className="decision-route"><span>{decision?.active && decision.active !== "none" ? zhLabel(decision.active) : "无活动策略"}</span><b>→</b><span>{zhLabel(decision?.recommended || "protect_mode")}</span></div><div className="decision-meta"><StatusPill tone="blue">{decision?.regime_label || zhLabel(decision?.regime)}</StatusPill><StatusPill tone={decision?.action === "protect" ? "red" : "green"}>{decision?.action_label || zhLabel(decision?.action || "observe")}</StatusPill><span>置信度 {decision?.confidence || "0"}</span><span>仓位系数 {decision?.scale || "0"}</span></div><p>{decision?.reason_labels?.join("、") || zhReasons(decision?.reasons)}</p></div></div>
        <div className="panel"><div className="panel-head"><div><span className="eyebrow">晋级门禁</span><h2>晋级与运营缺口</h2></div><Link href="/operations">进入迭代中心 →</Link></div><div className="gap-list">{gaps.length ? gaps.slice(0, 5).map((gap, index) => {
          const copy = localizeGap(gap.area, gap.title, gap.action);
          return <div className="gap-item" key={`${gap.area}-${index}`}><StatusPill tone={gap.severity === "high" || gap.severity === "blocker" ? "red" : gap.severity === "medium" ? "amber" : "neutral"}>{zhLabel(gap.severity)}</StatusPill><div><strong>{copy.title}</strong><span>{copy.action}</span></div></div>;
        }) : <div className="empty-state">当前报告没有记录缺口，但仍需新的纸面观察窗口。</div>}</div></div>
      </section>
      <section className="panel"><div className="panel-head"><div><span className="eyebrow">晋级流水线</span><h2>策略晋级漏斗</h2></div><Link href="/strategies">管理策略资产 →</Link></div><div className="pipeline">{catalog.policy.promotion_path.map((step, index) => <div className="pipeline-step" key={step}><span>{index + 1}</span><strong>{zhLabel(step)}</strong></div>)}</div></section>
    </div>
  );
}
