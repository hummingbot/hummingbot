import { StatusPill } from "@/components/StatusPill";
import { PaperExecutionControls } from "@/components/PaperExecutionControls";
import { PaperPerformanceSummary, TradingTerminal } from "@/components/TradingTerminal";
import { getUnifiedOperationsSnapshot } from "@/lib/data";

export const dynamic = "force-dynamic";

export default function TradingPage() {
  const { trading: snapshot, execution, runtime } = getUnifiedOperationsSnapshot();
  return <div className="page-stack">
    <section className="page-hero"><div><span className="eyebrow">交易执行</span><h1>交易账本</h1><p>{execution.scopeLabel} 的当前持仓、活动委托、委托历史、成交历史与盈亏共用同一份运行快照和成交库；其他实例仅在你主动切换筛选后显示。</p></div><StatusPill tone={execution.tone}>{execution.stateLabel}</StatusPill></section>
    <PaperExecutionControls state={runtime.containerState} />
    <PaperPerformanceSummary snapshot={snapshot} instance={execution.instance ?? undefined} />
    <TradingTerminal snapshot={snapshot} showPerformance={false} />
  </div>;
}
