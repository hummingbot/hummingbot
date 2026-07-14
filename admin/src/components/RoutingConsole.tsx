"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { MetricCard, StatusPill } from "@/components/StatusPill";
import { zhExchange, zhLabel, zhText } from "@/lib/i18n";
import type {
  RoutingAdminSnapshot,
  RoutingStrategySnapshot,
} from "@/lib/types";

type Tone = "green" | "amber" | "red" | "blue" | "neutral";

const conflictLabels: Record<string, string> = {
  evolution_readiness_degraded: "策略进化就绪状态降级",
  "funding_rate_arb:circuit_open": "资金费率套利已熔断",
  "pmm_mister:paper_rollback_blocked_open_exposure": "高级纯做市回滚请求被未平持仓阻挡",
  route_expired: "当前路由决策已过期",
  worker_state_container_mismatch: "执行实例状态与容器事实不一致",
  release_not_active_verified: "当前发布清单不再是已验证激活态",
  admin_snapshot_unavailable: "路由聚合状态不可用",
};

function zh(value: string | null | undefined): string {
  if (!value) return "—";
  return zhLabel(value);
}

function money(value: number | null | undefined): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return "—";
  return new Intl.NumberFormat("zh-CN", { maximumFractionDigits: 2 }).format(value);
}

function dateTime(value: string | number | null | undefined): string {
  if (!value) return "—";
  const date = new Date(typeof value === "number" ? value * 1000 : value);
  return Number.isNaN(date.getTime()) ? "—" : date.toLocaleString("zh-CN", { hour12: false });
}

function statusTone(value: string | null | undefined): Tone {
  if (["running", "stable", "active_verified", "healthy", "paper_running"].includes(value || "")) return "green";
  if (["blocked", "circuit_open", "degraded", "unsafe", "rollback_blocked_open_exposure", "missing"].includes(value || "")) return "red";
  if (["observing", "shadow", "starting", "stopped"].includes(value || "")) return "amber";
  return "neutral";
}

function strategyTone(strategy: RoutingStrategySnapshot): Tone {
  if (strategy.evolutionStatus === "circuit_open" || strategy.evolutionStatus === "blocked") return "red";
  if (strategy.evolutionRunStatus === "paper_running") return "green";
  return "amber";
}

export function RoutingConsole({ initial }: { initial: RoutingAdminSnapshot }) {
  const [snapshot, setSnapshot] = useState(initial);
  const initialEditAccount = initial.accounts.find((row) => row.id === "binance-mm") ?? initial.accounts[0];
  const [busy, setBusy] = useState<"refresh" | "transfer" | "config" | null>(null);
  const [message, setMessage] = useState<{ tone: Tone; text: string } | null>(null);
  const [source, setSource] = useState("binance-treasury");
  const [target, setTarget] = useState("binance-mm");
  const [amount, setAmount] = useState("100");
  const [approvedBy, setApprovedBy] = useState("");
  const [editAccountId, setEditAccountId] = useState(initialEditAccount?.id || "");
  const [limits, setLimits] = useState(() => ({
    minimumReserveQuote: String(initialEditAccount?.allocation.minimumReserveQuote ?? 0),
    maximumCapitalQuote: String(initialEditAccount?.allocation.maximumCapitalQuote ?? 0),
    maximumDrawdownQuote: String(initialEditAccount?.risk.maximumDrawdownQuote ?? 0),
    maximumGrossExposureQuote: String(initialEditAccount?.risk.maximumGrossExposureQuote ?? 0),
    maximumOpenOrders: String(initialEditAccount?.risk.maximumOpenOrders ?? 0),
    marketDataStaleAfterSeconds: String(initialEditAccount?.risk.marketDataStaleAfterSeconds ?? 20),
  }));

  function selectEditAccount(accountId: string, sourceSnapshot = snapshot) {
    const account = sourceSnapshot.accounts.find((row) => row.id === accountId);
    if (!account) return;
    setEditAccountId(accountId);
    setLimits({
      minimumReserveQuote: String(account.allocation.minimumReserveQuote),
      maximumCapitalQuote: String(account.allocation.maximumCapitalQuote),
      maximumDrawdownQuote: String(account.risk.maximumDrawdownQuote),
      maximumGrossExposureQuote: String(account.risk.maximumGrossExposureQuote),
      maximumOpenOrders: String(account.risk.maximumOpenOrders),
      marketDataStaleAfterSeconds: String(account.risk.marketDataStaleAfterSeconds),
    });
  }

  async function load(showMessage = false) {
    try {
      const response = await fetch("/admin/api/routing", { cache: "no-store" });
      const payload = await response.json() as RoutingAdminSnapshot;
      if (!response.ok || !payload.ok) throw new Error(payload.error || "路由状态读取失败");
      setSnapshot(payload);
      if (showMessage) setMessage({ tone: "green", text: "状态已刷新。" });
    } catch (error) {
      if (showMessage) setMessage({ tone: "red", text: error instanceof Error ? error.message : "状态刷新失败" });
    }
  }

  useEffect(() => {
    const timer = window.setInterval(() => {
      if (document.visibilityState === "visible" && busy === null) void load(false);
    }, 5_000);
    return () => window.clearInterval(timer);
  }, [busy]);

  async function refreshRoute() {
    setBusy("refresh");
    setMessage(null);
    try {
      const response = await fetch("/admin/api/routing", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ action: "refresh_route" }),
      });
      const payload = await response.json() as { message?: string; snapshot?: RoutingAdminSnapshot };
      if (!response.ok) throw new Error(payload.message || "路由重算失败");
      if (payload.snapshot) setSnapshot(payload.snapshot);
      setMessage({ tone: "green", text: payload.message || "路由已重算。" });
    } catch (error) {
      setMessage({ tone: "red", text: error instanceof Error ? error.message : "路由重算失败" });
    } finally {
      setBusy(null);
    }
  }

  async function simulateTransfer(event: React.FormEvent) {
    event.preventDefault();
    const value = Number(amount);
    if (!approvedBy.trim()) {
      setMessage({ tone: "red", text: "请填写纸盘审批人。" });
      return;
    }
    if (!window.confirm(`确认模拟划转 ${money(value)} USDT：${source} → ${target}？\n该操作只改纸盘模拟余额，并写入审计账本。`)) return;
    setBusy("transfer");
    setMessage(null);
    try {
      const response = await fetch("/admin/api/routing", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ action: "simulate_transfer", source, target, amount: value, approvedBy }),
      });
      const payload = await response.json() as { message?: string; snapshot?: RoutingAdminSnapshot };
      if (!response.ok) throw new Error(payload.message || "模拟划转失败");
      if (payload.snapshot) setSnapshot(payload.snapshot);
      setMessage({ tone: "green", text: payload.message || "模拟划转完成。" });
    } catch (error) {
      setMessage({ tone: "red", text: error instanceof Error ? error.message : "模拟划转失败" });
    } finally {
      setBusy(null);
    }
  }

  async function saveAccountLimits(event: React.FormEvent) {
    event.preventDefault();
    if (!window.confirm(`确认更新 ${editAccountId} 的纸盘资金与风险限制？\n账户拓扑、凭据、提现和实盘权限不会改变。`)) return;
    setBusy("config");
    setMessage(null);
    try {
      const response = await fetch("/admin/api/routing", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          action: "update_account_limits",
          account: editAccountId,
          minimum_reserve_quote: Number(limits.minimumReserveQuote),
          maximum_capital_quote: Number(limits.maximumCapitalQuote),
          maximum_drawdown_quote: Number(limits.maximumDrawdownQuote),
          maximum_gross_exposure_quote: Number(limits.maximumGrossExposureQuote),
          maximum_open_orders: Number(limits.maximumOpenOrders),
          market_data_stale_after_seconds: Number(limits.marketDataStaleAfterSeconds),
        }),
      });
      const payload = await response.json() as { message?: string; snapshot?: RoutingAdminSnapshot };
      if (!response.ok) throw new Error(payload.message || "账户配置保存失败");
      if (payload.snapshot) {
        setSnapshot(payload.snapshot);
        selectEditAccount(editAccountId, payload.snapshot);
      }
      setMessage({ tone: "green", text: payload.message || "账户配置已保存。" });
    } catch (error) {
      setMessage({ tone: "red", text: error instanceof Error ? error.message : "账户配置保存失败" });
    } finally {
      setBusy(null);
    }
  }

  const plan = snapshot.route.plan;
  const allocated = plan.allocations.reduce((total, row) => total + row.target_capital_quote, 0);
  const running = snapshot.accounts.filter((row) => row.containerState === "running").length;
  const totalEquity = snapshot.accounts.reduce((total, row) => total + (row.snapshot?.equity_quote ?? 0), 0);
  const treasury = snapshot.accounts.find((row) => row.id === "binance-treasury");
  const transferTargets = treasury?.transferPolicy.allowedCounterparties ?? [];
  const selectedSource = snapshot.accounts.find((row) => row.id === source);
  const sourceBalance = snapshot.transfers.balances[source] ?? 0;
  const cooldownRemaining = useMemo(() => {
    const last = snapshot.transfers.lastTransfer[source] ?? 0;
    const seconds = selectedSource?.transferPolicy.cooldownSeconds ?? 0;
    return Math.max(0, Math.ceil(last + seconds - Date.now() / 1000));
  }, [selectedSource, snapshot.transfers.lastTransfer, source]);

  const routeTone: Tone = snapshot.route.fresh && plan.risk_blockers.length === 0 ? "green" : "red";
  const heartbeat = snapshot.evolution.heartbeat;
  const routerHeartbeat = snapshot.routerHeartbeat || {};

  return <div className="page-stack routing-console">
    <section className="page-hero">
      <div><span className="eyebrow">多账户策略控制平面</span><h1>策略路由与账户编排</h1><p>固定特征负责硬门禁，人工智能仅提供受限评分修正；最终由账户隔离、兼容矩阵、资金上限和执行实例生命周期共同决定。</p></div>
      <div className="hero-actions"><StatusPill tone={snapshot.safety.paperOnly ? "blue" : "red"}>{zh(snapshot.environment)}</StatusPill><StatusPill tone={routeTone}>路由：{snapshot.route.fresh ? "有效" : "已过期"}</StatusPill><button className="routing-primary" type="button" onClick={refreshRoute} disabled={busy !== null}>{busy === "refresh" ? "计算中…" : "按最新快照重算"}</button></div>
    </section>

    {!snapshot.ok && <div className="alert-banner alert-danger"><strong>路由状态不可用</strong><span>{zhText(snapshot.error)}</span></div>}
    {snapshot.conflicts.length > 0 && <section className="routing-conflict" role="alert"><div><span className="eyebrow">跨系统冲突</span><strong>{snapshot.conflicts.length} 项必须先处理</strong></div><ul>{snapshot.conflicts.map((item) => <li key={item}>{conflictLabels[item] || item}</li>)}</ul></section>}
    {message && <div className={`routing-message routing-message-${message.tone}`} role="status">{message.text}</div>}

    <section className="metric-grid">
      <MetricCard label="路由权益口径" value={`${money(totalEquity)} USDT`} hint={`保留资金 ${money(plan.reserve_quote)} USDT`} tone="blue" />
      <MetricCard label="当前目标分配" value={`${money(allocated)} USDT`} hint={`${plan.allocations.length} 个账户 × 策略实例`} tone={plan.risk_blockers.length ? "red" : "green"} />
      <MetricCard label="实际运行实例" value={`${running} / ${snapshot.accounts.filter((row) => row.workerId).length}`} hint="同时核对路由状态与容器事实" tone={running ? "green" : "amber"} />
      <MetricCard label="策略进化安全态" value={zh(heartbeat.safety_status)} hint={zhText(heartbeat.last_error) === "—" ? "无最新错误" : zhText(heartbeat.last_error)} tone={statusTone(heartbeat.safety_status)} />
    </section>

    <section className="routing-safety-grid">
      <div><StatusPill tone={statusTone(routerHeartbeat.status)}>路由守护：{zh(routerHeartbeat.status)}</StatusPill><strong>闭合 K 线 + 风险特征</strong><span>心跳 {dateTime(routerHeartbeat.updated_at)} · 每 {snapshot.router.routeIntervalSeconds / 2} 秒自动重算</span></div>
      <div><StatusPill tone={snapshot.safety.aiEnabled ? "amber" : "blue"}>人工智能{snapshot.safety.aiEnabled ? "启用" : "关闭"}</StatusPill><strong>{zh(snapshot.safety.aiProvider)} · {snapshot.safety.aiPrimaryModel}</strong><span>{zh(snapshot.safety.aiMode)}模式，人工智能不拥有资金与执行实例控制权</span></div>
      <div><StatusPill tone={snapshot.safety.liveActions ? "red" : "green"}>实盘动作关闭</StatusPill><strong>纸盘单写入者</strong><span>策略进化自动启动：{snapshot.safety.evolutionAutoStart ? "开启" : "关闭"}；策略路由管理运行态</span></div>
      <div><StatusPill tone={snapshot.safety.automaticTransfers ? "red" : "green"}>自动划转关闭</StatusPill><strong>仅人工纸盘模拟</strong><span>提现权限固定关闭，划转需要审批身份和白名单</span></div>
    </section>

    <section className="router-visual routing-flow">
      {["市场快照", "固定特征门禁", "策略进化候选", "人工智能受限修正", "兼容与资金分配", "账户执行实例", "纸盘账本"].map((item, index) => <div className={`router-node ${index === 4 || index === 5 ? "active" : ""}`} key={item}><span>{String(index + 1).padStart(2, "0")}</span><strong>{item}</strong><small>{index === 3 ? (snapshot.safety.aiEnabled ? "已应用" : "未参与当前决策") : index === 5 ? `${running} 个容器运行` : "确定性证据链"}</small></div>)}
    </section>

    <section className="panel">
      <div className="panel-head"><div><span className="eyebrow">账户配置</span><h2>主账户 / 子账户隔离</h2></div><span className="snapshot">已校验：{snapshot.configValidated ? "是" : "否"} · {snapshot.configPath}</span></div>
      <div className="table-shell"><table className="routing-account-table"><thead><tr><th>账户</th><th>职责与市场</th><th>资金配置</th><th>风险上限</th><th>执行实例 / 运行事实</th><th>权限</th></tr></thead><tbody>{snapshot.accounts.map((account) => {
        const accountTone: Tone = !account.workerId ? "blue" : account.containerState === "running" && account.runtimeFresh ? "green" : account.workerStatus === null ? "neutral" : "red";
        return <tr key={account.id}><td><strong>{account.id}</strong><small>{zh(account.kind)} · {zhExchange(account.exchange)}</small>{account.parentId && <small>父账户：{account.parentId}</small>}<StatusPill tone={accountTone}>{account.workerId ? zh(account.containerState) : "储备账户"}</StatusPill></td><td><strong>{account.allowedSleeves.map(zh).join("、")}</strong><small>{account.allowedPairs.join(" / ") || "不交易"}</small><small>{zh(account.positionMode)} · {zh(account.marginMode)}</small></td><td><strong>权益 {money(account.snapshot?.equity_quote)} USDT</strong><small>可用 {money(account.snapshot?.available_quote)} · 模拟划转余额 {money(account.paperBalance)}</small><small>保留 ≥ {money(account.allocation.minimumReserveQuote)} · 上限 {money(account.allocation.maximumCapitalQuote)}</small></td><td><strong>总敞口 ≤ {money(account.risk.maximumGrossExposureQuote)}</strong><small>回撤 ≤ {money(account.risk.maximumDrawdownQuote)} · 委托 ≤ {account.risk.maximumOpenOrders}</small><small>行情过期 {account.risk.marketDataStaleAfterSeconds} 秒</small></td><td><strong>{account.workerId || "—"}</strong><small>路由：{zh(account.workerStatus)}</small><small>{account.runtime ? `快照 ${Math.round(account.runtimeAgeSeconds ?? 0)} 秒 · ${account.runtime.paperOnly ? "纯纸盘" : "边界异常"}` : "无运行快照"}</small></td><td><StatusPill tone={account.permissions.trade ? "amber" : "neutral"}>交易 {account.permissions.trade ? "允许" : "禁止"}</StatusPill><small>内部划转 {account.permissions.internalTransfer ? "允许" : "禁止"}</small><small>提现 永久禁止</small></td></tr>;
      })}</tbody></table></div>
    </section>

    <form className="panel account-limit-form" onSubmit={saveAccountLimits}>
      <div className="panel-head"><div><span className="eyebrow">账户运行配置</span><h2>纸盘资金与风险限制</h2></div><StatusPill tone="green">全量校验后原子写入</StatusPill></div>
      <div className="account-config-warning"><strong>可编辑边界</strong><span>这里只允许调整纸盘数值限制。账户拓扑、交易所引用、凭据、执行实例标识、交易权限、内部划转和提现权限均不可从页面修改。</span></div>
      <label>账户<select value={editAccountId} onChange={(event) => selectEditAccount(event.target.value)}>{snapshot.accounts.map((account) => <option value={account.id} key={account.id}>{account.id} · {zh(account.kind)}</option>)}</select></label>
      <label>最低保留资金（USDT）<input type="number" min="0" step="0.01" value={limits.minimumReserveQuote} onChange={(event) => setLimits((row) => ({ ...row, minimumReserveQuote: event.target.value }))} required /></label>
      <label>最大可分配资金（USDT）<input type="number" min="0" step="0.01" value={limits.maximumCapitalQuote} onChange={(event) => setLimits((row) => ({ ...row, maximumCapitalQuote: event.target.value }))} required /></label>
      <label>最大回撤（USDT）<input type="number" min="0" step="0.01" value={limits.maximumDrawdownQuote} onChange={(event) => setLimits((row) => ({ ...row, maximumDrawdownQuote: event.target.value }))} required /></label>
      <label>最大总敞口（USDT）<input type="number" min="0" step="0.01" value={limits.maximumGrossExposureQuote} onChange={(event) => setLimits((row) => ({ ...row, maximumGrossExposureQuote: event.target.value }))} required /></label>
      <label>最大活动委托数<input type="number" min="0" step="1" value={limits.maximumOpenOrders} onChange={(event) => setLimits((row) => ({ ...row, maximumOpenOrders: event.target.value }))} required /></label>
      <label>行情过期阈值（秒）<input type="number" min="1" step="1" value={limits.marketDataStaleAfterSeconds} onChange={(event) => setLimits((row) => ({ ...row, marketDataStaleAfterSeconds: event.target.value }))} required /></label>
      <div className="account-limit-submit"><span>当前来源：{snapshot.configPath}</span><button className="routing-primary" type="submit" disabled={busy !== null}>{busy === "config" ? "校验并保存中…" : "保存纸盘账户限制"}</button></div>
    </form>

    <section className="two-column routing-main-grid">
      <div className="panel"><div className="panel-head"><div><span className="eyebrow">当前路由</span><h2>资金分配与执行动作</h2></div><StatusPill tone={routeTone}>{plan.decision_id ? plan.decision_id.slice(0, 18) : "无决策"}</StatusPill></div>
        {plan.allocations.length ? <div className="route-allocation-list">{plan.allocations.map((row) => {
          const action = snapshot.route.workerActions.find((item) => item.account_id === row.account_id);
          return <article key={`${row.account_id}:${row.strategy_id}`}><div><StatusPill tone={action?.action === "blocked" ? "red" : "green"}>{zh(action?.action || row.lifecycle_action)}</StatusPill><strong>{row.strategy_id} → {row.account_id}</strong><span>{row.trading_pair} · {zh(row.sleeve)} · {zh(row.position_side)}</span></div><div><b>{money(row.target_capital_quote)} USDT</b><span>综合分 {row.score.toFixed(3)}</span></div>{action?.reason_codes.length ? <small>{action.reason_codes.map(zh).join(" · ")}</small> : null}</article>;
        })}</div> : <div className="empty-state">当前没有可执行分配</div>}
        <dl className="facts routing-facts"><div><dt>决策生成</dt><dd>{dateTime(plan.generated_at)}</dd></div><div><dt>决策到期</dt><dd>{dateTime(plan.expires_at)}</dd></div><div><dt>人工智能应用</dt><dd>{plan.ai_applied ? "是" : "否"}</dd></div><div><dt>风险阻断</dt><dd>{plan.risk_blockers.map(zh).join("、") || "无"}</dd></div></dl>
      </div>
      <div className="panel"><div className="panel-head"><div><span className="eyebrow">发布与运行</span><h2>策略进化 / 策略路由一致性</h2></div><StatusPill tone={statusTone(heartbeat.readiness_status)}>{zh(heartbeat.readiness_status)}</StatusPill></div>
        <dl className="facts"><div><dt>策略进化心跳</dt><dd>{dateTime(heartbeat.last_activity)}</dd></div><div><dt>最近成功</dt><dd>{dateTime(heartbeat.last_success)}</dd></div><div><dt>当前发布</dt><dd>{snapshot.releases[0]?.candidate_id || "无"}</dd></div><div><dt>发布状态</dt><dd>{zh(snapshot.releases[0]?.status)}</dd></div><div><dt>观测恢复</dt><dd>{snapshot.releases[0]?.rollback_recovered_at ? `${dateTime(snapshot.releases[0].rollback_recovered_at)} · ${snapshot.releases[0].rollback_recovery?.reasons?.map(zh).join("、")}` : "无恢复事件"}</dd></div><div><dt>路由候选</dt><dd>{plan.allocations[0]?.candidate_id || "无"}</dd></div><div><dt>配置哈希</dt><dd>{plan.allocations[0]?.config_hash?.slice(0, 16) || "—"}</dd></div></dl>
        <Link className="routing-link" href="/operations">查看完整迭代与部署事实 →</Link>
      </div>
    </section>

    <section className="panel">
      <div className="panel-head"><div><span className="eyebrow">策略与兼容性</span><h2>同一交易所可并行，但按账户与持仓所有权隔离</h2></div><StatusPill tone="blue">{snapshot.strategies.length} 个策略槽位</StatusPill></div>
      <div className="table-shell"><table><thead><tr><th>策略</th><th>资金袖套</th><th>允许账户 / 交易对</th><th>兼容组</th><th>策略进化</th><th>下一步</th></tr></thead><tbody>{snapshot.strategies.map((strategy) => <tr key={strategy.strategyId}><td><strong>{strategy.strategyId}</strong><small>单账户最多 {strategy.maximumInstancesPerAccount} 实例</small></td><td><span className="family-tag">{zh(strategy.sleeve)}</span></td><td><strong>{strategy.accountIds.join("、")}</strong><small>{strategy.allowedPairs.join(" / ")}</small></td><td><code>{zh(strategy.compatibilityGroup)}</code></td><td><StatusPill tone={strategyTone(strategy)}>{zh(strategy.evolutionStatus)}</StatusPill><small>{zh(strategy.evolutionStage)}</small></td><td><small>{zhText(strategy.nextStep)}</small></td></tr>)}</tbody></table></div>
      <div className="compatibility-list">{snapshot.compatibility.map((rule) => <div key={`${rule.left}:${rule.right}`}><span>{rule.left}</span><b>↔</b><span>{rule.right}</span><StatusPill tone={rule.relation === "compatible" ? "green" : rule.relation === "exclusive" ? "red" : "amber"}>{zh(rule.relation)}</StatusPill><small>{rule.conditions.map(zh).join("、") || "无附加条件"}</small></div>)}</div>
    </section>

    <section className="two-column transfer-layout">
      <form className="panel transfer-form" onSubmit={simulateTransfer}><div className="panel-head"><div><span className="eyebrow">资金调度</span><h2>人工纸盘模拟划转</h2></div><StatusPill tone="blue">不调用交易所</StatusPill></div>
        <div className="alert-banner alert-info"><strong>安全边界</strong><span>自动划转关闭；只修改路由运行目录下的纸盘余额和审计流水。</span></div>
        <label>来源账户<select value={source} onChange={(event) => { setSource(event.target.value); setTarget(""); }}>{snapshot.accounts.filter((row) => row.transferPolicy.enabled).map((row) => <option key={row.id} value={row.id}>{row.id}</option>)}</select></label>
        <label>目标账户<select value={target} onChange={(event) => setTarget(event.target.value)} required><option value="" disabled>选择白名单账户</option>{(selectedSource?.transferPolicy.allowedCounterparties ?? transferTargets).map((id) => <option key={id} value={id}>{id}</option>)}</select></label>
        <label>金额（USDT）<input type="number" min={selectedSource?.transferPolicy.minimumTransferQuote || 0.01} max={selectedSource?.transferPolicy.maximumTransferQuote || undefined} step="0.01" value={amount} onChange={(event) => setAmount(event.target.value)} required /></label>
        <label>纸盘审批人<input type="text" maxLength={64} placeholder="输入操作人姓名或代号" value={approvedBy} onChange={(event) => setApprovedBy(event.target.value)} required /></label>
        <div className="transfer-policy"><span>当前余额 <b>{money(sourceBalance)}</b></span><span>单笔 {money(selectedSource?.transferPolicy.minimumTransferQuote)}–{money(selectedSource?.transferPolicy.maximumTransferQuote)}</span><span>日限额 {money(selectedSource?.transferPolicy.maximumDailyTransferQuote)}</span><span>冷却 {cooldownRemaining > 0 ? `${cooldownRemaining} 秒` : "已结束"}</span></div>
        <button className="routing-primary" type="submit" disabled={busy !== null || cooldownRemaining > 0}>{busy === "transfer" ? "写入中…" : cooldownRemaining > 0 ? "划转冷却中" : "审批并模拟划转"}</button>
      </form>
      <div className="panel"><div className="panel-head"><div><span className="eyebrow">划转审计</span><h2>最近事件</h2></div><StatusPill tone="green">幂等账本</StatusPill></div>{snapshot.transfers.events.length ? <div className="audit-list">{snapshot.transfers.events.map((event) => <article key={event.transfer_id}><div><strong>{event.source_account_id} → {event.target_account_id}</strong><small>{event.approved_by} · {dateTime(event.executed_at)}</small></div><div><b>{money(event.amount_quote)} USDT</b><StatusPill tone="blue">{zh(event.status)}</StatusPill></div></article>)}</div> : <div className="empty-state">暂无划转事件</div>}</div>
    </section>

    <section className="two-column">
      <div className="panel"><div className="panel-head"><div><span className="eyebrow">生命周期</span><h2>策略切换状态机</h2></div></div>{snapshot.lifecycle.length ? <div className="audit-list">{snapshot.lifecycle.map((entry, index) => <article key={entry.last_decision_id || index}><div><strong>{entry.record?.account_id} · {zh(entry.record?.sleeve)}</strong><small>{entry.record?.trading_pair} · {entry.record?.active_strategy_id || "无活动策略"}</small></div><StatusPill tone={statusTone(entry.record?.state)}>{zh(entry.record?.state)}</StatusPill></article>)}</div> : <div className="empty-state">尚无生命周期记录</div>}</div>
      <div className="panel"><div className="panel-head"><div><span className="eyebrow">决策审计</span><h2>最近路由</h2></div><StatusPill tone="blue">不可变追加账本</StatusPill></div><div className="audit-list">{snapshot.decisions.slice(0, 6).map((decision) => <article key={decision.decision_id}><div><strong>{decision.decision_id}</strong><small>{dateTime(decision.generated_at)} · {decision.allocations.map((row) => row.strategy_id).join("、") || "无分配"}</small></div><div><b>{decision.allocations[0]?.score?.toFixed(3) || "—"}</b><StatusPill tone={decision.risk_blockers.length ? "red" : "green"}>{decision.risk_blockers.length ? "阻断" : "通过"}</StatusPill></div></article>)}</div></div>
    </section>

    <section className="routing-footer-actions"><div><strong>执行实例启停与交易账本</strong><span>启停操作仍只针对已配置的纸盘容器；委托、成交与持仓使用交易页的唯一事实口径。</span></div><Link href="/trading">前往纸盘执行与账本 →</Link></section>
  </div>;
}
