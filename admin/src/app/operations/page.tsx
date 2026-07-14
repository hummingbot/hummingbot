import { MetricCard, StatusPill } from "@/components/StatusPill";
import { getIterationSnapshot, getUnifiedOperationsSnapshot } from "@/lib/data";
import { zhLabel } from "@/lib/i18n";

export const dynamic = "force-dynamic";

export default function OperationsPage() {
  const unified = getUnifiedOperationsSnapshot();
  const { runtime, execution } = unified;
  const iteration = getIterationSnapshot();
  const tests = Object.entries(iteration.tests ?? {});
  const runtimeEvidence = runtime.containerEvidence === "docker" ? "容器引擎直接读取" : runtime.containerEvidence === "runtime_snapshot" ? "纸面进程心跳" : "当前无可验证运行信号";
  return <div className="page-stack">
    <section className="page-hero"><div><span className="eyebrow">发布运营</span><h1>迭代与部署</h1><p>本页只说明部署与验证事实；持仓、委托、成交和盈亏统一在交易账本查看。</p></div><StatusPill tone={execution.tone}>{execution.stateLabel}</StatusPill></section>
    <section className="metric-grid">
      <MetricCard label="当前纸盘实例" value={execution.scopeLabel} hint={execution.stateDetail} tone={execution.tone} />
      <MetricCard label="运行快照" value={execution.snapshotAgeSeconds === null ? "等待数据" : `${execution.snapshotAgeSeconds} 秒前`} hint="交易账本与此处共用同一快照" tone={execution.snapshotAgeSeconds !== null && execution.snapshotAgeSeconds <= 30 ? "green" : "amber"} />
      <MetricCard label="容器状态" value={zhLabel(runtime.containerState)} hint={runtimeEvidence} tone={runtime.containerState === "running" ? "green" : runtime.containerState === "unknown" ? "amber" : "red"} />
      <MetricCard label="代码版本" value={runtime.gitHead} hint={`${runtime.gitDirtyCount} 个工作树变更`} tone={runtime.gitDirtyCount ? "amber" : "green"} />
    </section>
    <section className="two-column"><div className="panel"><div className="panel-head"><div><span className="eyebrow">检查项</span><h2>测试门禁</h2></div></div><div className="check-rows">{tests.length ? tests.map(([name, result]) => <div key={name}><StatusPill tone={result.ok ? "green" : "red"}>{result.ok ? "通过" : "失败"}</StatusPill><strong>{zhLabel(name)}</strong></div>) : <div className="empty-state">尚无测试快照</div>}</div></div><div className="panel"><div className="panel-head"><div><span className="eyebrow">运行状态</span><h2>部署事实</h2></div></div><dl className="facts"><div><dt>项目根目录</dt><dd>{runtime.root}</dd></div><div><dt>容器</dt><dd>{runtime.container}</dd></div><div><dt>当前账本范围</dt><dd>{execution.scopeLabel}</dd></div><div><dt>运行依据</dt><dd>{runtimeEvidence}</dd></div><div><dt>路由报告</dt><dd>{runtime.reportStale ? "已过期，仅作历史参考" : "当前有效"}</dd></div><div><dt>实盘权限</dt><dd>默认关闭，需要显式审批</dd></div></dl></div></section><section className="panel"><div className="panel-head"><div><span className="eyebrow">自动迭代</span><h2>自动迭代闭环</h2></div></div><div className="pipeline">{["观察","测试","评估","制定修复计划","部署纸面实例","验证","晋级或回滚"].map((step, index) => <div className="pipeline-step" key={step}><span>{index + 1}</span><strong>{step}</strong></div>)}</div></section></div>;
}
