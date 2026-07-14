"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

type ContainerState = "running" | "stopped" | "missing" | "unknown";
type Action = "start" | "stop" | "fresh";

const labels: Record<Action, string> = {
  start: "启动纸盘",
  stop: "停止纸盘",
  fresh: "新建观察期",
};

export function PaperExecutionControls({ state }: { state: ContainerState }) {
  const router = useRouter();
  const [busy, setBusy] = useState<Action | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  async function execute(action: Action) {
    if (action === "fresh" && !window.confirm("将停止纸盘、归档当前纸盘账本，并以空账本重新启动。历史记录不会删除。确定继续吗？")) return;
    setBusy(action);
    setMessage(null);
    try {
      const result = await fetch("/admin/api/paper", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ action }),
      });
      const payload = await result.json() as { message?: string };
      if (!result.ok) throw new Error(payload.message || "纸盘控制失败");
      setMessage(payload.message || "操作已提交");
      router.refresh();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "纸盘控制失败");
    } finally {
      setBusy(null);
    }
  }

  const isRunning = state === "running";
  const isMissing = state === "missing";
  return <section className="paper-control-panel" aria-label="纸盘策略控制">
    <div><span className="eyebrow">纸盘控制</span><strong>高级纯做市（纸盘）</strong><small>只控制当前币安纸盘容器；不提供实盘下单、撤单或资金操作。</small></div>
    <div className="paper-control-actions">
      <button type="button" onClick={() => execute("start")} disabled={isRunning || isMissing || busy !== null}>{busy === "start" ? "启动中…" : labels.start}</button>
      <button type="button" className="paper-stop" onClick={() => execute("stop")} disabled={!isRunning || busy !== null}>{busy === "stop" ? "停止中…" : labels.stop}</button>
      <button type="button" className="paper-fresh" onClick={() => execute("fresh")} disabled={isMissing || busy !== null}>{busy === "fresh" ? "归档并启动中…" : labels.fresh}</button>
    </div>
    {message && <p className="paper-control-message" role="status">{message}</p>}
  </section>;
}
