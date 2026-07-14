"use client";

import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { zhExchange, zhInstance, zhOrderStatus, zhOrderType } from "@/lib/i18n";
import type { PaperPerformance, TradingBalance, TradingFill, TradingOrder, TradingPosition, TradingSnapshot } from "@/lib/types";

type Tab = "positions" | "openOrders" | "orders" | "fills";

const tabs: Array<{ key: Tab; label: string }> = [
  { key: "positions", label: "持仓" },
  { key: "openOrders", label: "当前委托" },
  { key: "orders", label: "委托历史" },
  { key: "fills", label: "成交历史" },
];

function number(value: number, maximumFractionDigits = value < 1 ? 6 : 2): string {
  return new Intl.NumberFormat("zh-CN", { maximumFractionDigits, minimumFractionDigits: 0 }).format(value);
}

function timestamp(value: number): string {
  if (!value) return "—";
  return new Intl.DateTimeFormat("zh-CN", {
    timeZone: "Asia/Shanghai",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  }).format(new Date(value));
}

function Searchable({ value, exchange, instance, onValueChange, onExchangeChange, onInstanceChange, exchanges, instances }: {
  value: string;
  exchange: string;
  instance: string;
  onValueChange: (value: string) => void;
  onExchangeChange: (value: string) => void;
  onInstanceChange: (value: string) => void;
  exchanges: string[];
  instances: string[];
}) {
  return <div className="filterbar trading-filterbar">
    <input value={value} onChange={(event) => onValueChange(event.target.value)} placeholder="搜索交易对、委托编号、策略实例" aria-label="搜索交易记录" />
    <select value={exchange} onChange={(event) => onExchangeChange(event.target.value)} aria-label="筛选交易所">
      <option value="all">全部交易所（历史汇总）</option>
      {exchanges.map((item) => <option key={item} value={item}>{zhExchange(item)}</option>)}
    </select>
    <select value={instance} onChange={(event) => onInstanceChange(event.target.value)} aria-label="筛选策略实例">
      <option value="all">全部实例（历史汇总）</option>
      {instances.map((item) => <option key={item} value={item}>{zhInstance(item)}</option>)}
    </select>
  </div>;
}

function Side({ side }: { side: string }) {
  const normalized = side.toUpperCase();
  const buying = normalized === "BUY" || normalized === "LONG";
  const selling = normalized === "SELL" || normalized === "SHORT";
  const label = normalized === "BUY" ? "买入" : normalized === "SELL" ? "卖出" : normalized === "LONG" ? "多头" : normalized === "SHORT" ? "空头" : side || "—";
  return <span className={`trade-side ${buying ? "trade-buy" : selling ? "trade-sell" : ""}`}>{label}</span>;
}

function Paper({ paper }: { paper: boolean }) {
  return <span className={`mode-badge ${paper ? "mode-paper" : "mode-live"}`}>{paper ? "纸盘" : "实盘"}</span>;
}

function paperPerformanceName(item: PaperPerformance): string {
  const exchange = zhExchange(item.exchange);
  const strategy = zhInstance(item.instance);
  return `${exchange} · ${strategy}${item.paper ? "（纸盘）" : ""}`;
}

function Pnl({ value }: { value: number }) {
  return <span className={value > 0 ? "pnl-positive" : value < 0 ? "pnl-negative" : "pnl-neutral"}>{value > 0 ? "+" : ""}{number(value, 4)}</span>;
}

function QuoteValue({ value, quoteAsset, pnl = false }: { value: number; quoteAsset: string; pnl?: boolean }) {
  return <strong className="performance-value">{pnl ? <Pnl value={value} /> : number(value, 4)}<em>{quoteAsset}</em></strong>;
}

function feePolicy(item: PaperPerformance): string {
  const profile = item.feeProfile;
  if (!profile) return "手续费模型等待同步";
  const source = profile.source === "binance_account" ? "币安账户费率" : "币安标准费率兜底，待账户同步";
  return `${source} · 挂单费率 ${number(profile.makerFeeBpsGross, 2)} 基点 × ${(1 - profile.rebateRate) * 100}% = ${number(profile.makerFeeBpsNet, 2)} 基点`;
}

function Empty({ label }: { label: string }) {
  return <div className="empty-state">{label}</div>;
}

function Balances({ balances }: { balances: TradingBalance[] }) {
  if (!balances.length) return <Empty label="尚未收到运行时资产快照；纸盘实例启动后会自动显示余额。" />;
  return <div className="balance-grid">
    {balances.map((balance) => <div className="balance-card" key={`${balance.connector}-${balance.asset}`}>
      <div><strong>{balance.asset}</strong><span>{zhExchange(balance.exchange)}</span><Paper paper={balance.paper} /></div>
      <b>{number(balance.total, 6)}</b>
      <small>可用 {number(balance.available, 6)} · 冻结 {number(Math.max(0, balance.total - balance.available), 6)}</small>
    </div>)}
  </div>;
}

function PaperPerformancePanel({ performance }: { performance: PaperPerformance[] }) {
  if (!performance.length) return <section className="paper-performance-empty">尚未收到可用于估值的纸盘运行快照；不会用历史成交额代替当前盈亏。</section>;
  return <section className="paper-performance-grid">
    {performance.map((item) => {
      const waitingForFirstFill = item.fillCount === 0;
      const marketDataStale = item.marketDataStale;
      const market = item.symbols.join(" / ") || "—";
      const status = marketDataStale ? "行情中断，报价已暂停" : waitingForFirstFill ? "等待首笔成交" : "实时估值中";
      const statusDetail = marketDataStale
        ? item.marketDataAgeSeconds === null ? "未收到有效订单簿更新" : `${number(item.marketDataAgeSeconds, 0)} 秒未更新`
        : waitingForFirstFill ? "委托簿持续更新，等待市场成交" : `${item.fillCount} 笔成交，按中间价估值`;
      return <div className="paper-performance-card" key={`${item.instance}-${item.connector}-${item.quoteAsset}`}>
      <div className="paper-performance-head"><div><span className="eyebrow">当前纸盘绩效</span><h2>{paperPerformanceName(item)}</h2></div><Paper paper={item.paper} /></div>
      <div className={`paper-summary ${marketDataStale ? "is-stale" : waitingForFirstFill ? "is-waiting" : "is-active"}`}>
        <div className="paper-status"><span>策略状态</span><strong>{status}</strong><small>{statusDetail}</small></div>
        <div><span>市场</span><b>{market}</b><small className={marketDataStale ? "market-stale" : "market-price"}>{item.markPrice === null ? "等待行情" : `${number(item.markPrice, 4)} ${item.quoteAsset}`}</small></div>
        <div><span>活动委托</span><b className="pending-orders">{item.activeOrderCount} 笔</b><small>待成交 {number(item.pendingNotional, 2)} {item.quoteAsset}</small></div>
        <div className="paper-net-pnl"><span>当前净盈亏</span>{waitingForFirstFill ? <strong>待首笔成交</strong> : <QuoteValue value={item.netPnl} quoteAsset={item.quoteAsset} pnl />}</div>
      </div>
      <div className="paper-detail-line"><span>已实现 <Pnl value={item.realizedPnl} /> {item.quoteAsset}</span><span>持仓浮盈 <Pnl value={item.unrealizedPnl} /> {item.quoteAsset}</span><span>累计净手续费（返佣后） {number(item.fees, 4)} {item.quoteAsset}</span><span className="fee-policy">{feePolicy(item)}</span></div>
      <p className="paper-performance-note">{marketDataStale ? "行情源已过期，纸盘已保护性暂停；当前盈亏和待成交金额不应作为评估依据。" : waitingForFirstFill ? `目前 ${item.activeOrderCount} 笔限价委托均未成交；委托冻结资金不计作亏损。` : `${item.fillCount} 笔成交；${item.markAvailable ? "按当前中间价实时估值。" : "缺少当前标记价，仅显示已实现部分。"}`}</p>
    </div>})}
  </section>;
}

export function PaperPerformanceSummary({ snapshot, instance }: { snapshot: TradingSnapshot; instance?: string }) {
  return <PaperPerformancePanel performance={snapshot.paperPerformance.filter((item) => !instance || item.instance === instance)} />;
}

function Positions({ positions }: { positions: TradingPosition[] }) {
  if (!positions.length) return <Empty label="当前没有持仓。后续纸面成交形成未平仓头寸后会在这里实时展示。" />;
  return <div className="table-shell"><table><thead><tr><th>合约 / 交易所</th><th>方向</th><th>数量</th><th>开仓均价</th><th>名义价值</th><th>未实现盈亏</th><th>已实现盈亏</th><th>费用</th><th>策略</th></tr></thead><tbody>
    {positions.map((position) => <tr key={position.id}><td><strong>{position.symbol}</strong><small>{zhExchange(position.exchange)} · <Paper paper={position.paper} /></small></td><td><Side side={position.side} /></td><td>{number(position.amount, 6)}</td><td>{number(position.entryPrice, 6)}</td><td>{number(position.notional, 4)}</td><td><Pnl value={position.unrealizedPnl} /></td><td><Pnl value={position.realizedPnl} /></td><td>{number(position.fees, 4)}</td><td><code>{position.controllerId || "—"}</code></td></tr>)}
  </tbody></table></div>;
}

function OpenOrders({ orders }: { orders: TradingOrder[] }) {
  if (!orders.length) return <Empty label="当前没有活动委托。该列表直接来自运行中的连接器，不是历史状态推断。" />;
  return <div className="table-shell"><table><thead><tr><th>时间</th><th>合约 / 交易所</th><th>方向</th><th>类型</th><th>价格</th><th>数量</th><th>已成交</th><th>状态</th><th>委托编号</th></tr></thead><tbody>
    {orders.map((order) => <tr key={order.id}><td>{timestamp(order.createdAt)}</td><td><strong>{order.symbol}</strong><small>{zhExchange(order.exchange)} · <Paper paper={order.paper} /></small></td><td><Side side={order.side} /></td><td>{zhOrderType(order.orderType)}</td><td>{number(order.price, 6)}</td><td>{number(order.amount, 6)}</td><td>{number(order.filled, 6)}</td><td><span className="status-text">{zhOrderStatus(order.status)}</span></td><td><code title={order.id}>{order.id.slice(-20)}</code></td></tr>)}
  </tbody></table></div>;
}

function Orders({ orders }: { orders: TradingOrder[] }) {
  if (!orders.length) return <Empty label="暂时没有可读取的委托历史。" />;
  return <div className="table-shell"><table><thead><tr><th>更新时间</th><th>合约 / 交易所</th><th>方向</th><th>类型</th><th>价格</th><th>数量</th><th>名义价值</th><th>状态</th><th>策略实例 / 编号</th></tr></thead><tbody>
    {orders.map((order) => <tr key={order.id}><td>{timestamp(order.updatedAt)}</td><td><strong>{order.symbol}</strong><small>{zhExchange(order.exchange)} · <Paper paper={order.paper} /></small></td><td><Side side={order.side} /></td><td>{zhOrderType(order.orderType)}</td><td>{number(order.price, 6)}</td><td>{number(order.amount, 6)}</td><td>{number(order.notional, 4)}</td><td><span className="status-text">{zhOrderStatus(order.status)}</span></td><td><code title={order.id}>{zhInstance(order.instance)} · {order.id.slice(-12)}</code></td></tr>)}
  </tbody></table></div>;
}

function Fills({ fills }: { fills: TradingFill[] }) {
  if (!fills.length) return <Empty label="目前还没有成交记录；已完成的纸面成交会自动写入这里。" />;
  return <div className="table-shell"><table><thead><tr><th>成交时间</th><th>合约 / 交易所</th><th>方向</th><th>类型</th><th>成交价</th><th>成交量</th><th>成交额</th><th>费用</th><th>成交编号</th></tr></thead><tbody>
    {fills.map((fill) => <tr key={fill.id}><td>{timestamp(fill.timestamp)}</td><td><strong>{fill.symbol}</strong><small>{zhExchange(fill.exchange)} · <Paper paper={fill.paper} /></small></td><td><Side side={fill.side} /></td><td>{zhOrderType(fill.orderType)}</td><td>{number(fill.price, 6)}</td><td>{number(fill.amount, 6)}</td><td>{number(fill.notional, 4)}</td><td>{number(fill.fee, 5)}</td><td><code title={fill.id}>{fill.id.slice(-20)}</code></td></tr>)}
  </tbody></table></div>;
}

function Pagination({ totalItems, page, pageSize, onPageChange, onPageSizeChange }: {
  totalItems: number;
  page: number;
  pageSize: number;
  onPageChange: (page: number) => void;
  onPageSizeChange: (pageSize: number) => void;
}) {
  const totalPages = Math.max(1, Math.ceil(totalItems / pageSize));
  if (totalItems <= pageSize) return null;
  const start = (page - 1) * pageSize + 1;
  const end = Math.min(totalItems, page * pageSize);
  const visiblePages = totalPages <= 7
    ? Array.from({ length: totalPages }, (_, index) => index + 1)
    : Array.from(new Set([1, page - 1, page, page + 1, totalPages])).filter((item) => item >= 1 && item <= totalPages).sort((a, b) => a - b);

  return <nav className="trading-pagination" aria-label="交易记录分页">
    <span>显示 {start}–{end} / 共 {totalItems} 条</span>
    <div className="pagination-controls">
      <button type="button" disabled={page === 1} onClick={() => onPageChange(page - 1)}>上一页</button>
      {visiblePages.map((item, index) => <span className="pagination-page-group" key={item}>
        {index > 0 && item - visiblePages[index - 1] > 1 && <i>…</i>}
        <button type="button" className={item === page ? "active" : ""} aria-current={item === page ? "page" : undefined} onClick={() => onPageChange(item)}>{item}</button>
      </span>)}
      <button type="button" disabled={page === totalPages} onClick={() => onPageChange(page + 1)}>下一页</button>
      <label>每页
        <select value={pageSize} onChange={(event) => onPageSizeChange(Number(event.target.value))} aria-label="每页显示条数">
          <option value={20}>20</option>
          <option value={50}>50</option>
          <option value={100}>100</option>
        </select>
        条
      </label>
    </div>
  </nav>;
}

export function TradingTerminal({ snapshot, showPerformance = true }: { snapshot: TradingSnapshot; showPerformance?: boolean }) {
  const router = useRouter();
  const primaryPaper = snapshot.paperPerformance.find((item) => item.instance === "pmm_mister_paper" && item.paper)
    ?? snapshot.paperPerformance.find((item) => item.paper);
  const [tab, setTab] = useState<Tab>("positions");
  const [query, setQuery] = useState("");
  const [exchange, setExchange] = useState(primaryPaper?.exchange ?? "all");
  const [instance, setInstance] = useState(primaryPaper?.instance ?? "all");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  useEffect(() => {
    const interval = window.setInterval(() => router.refresh(), 15_000);
    return () => window.clearInterval(interval);
  }, [router]);

  const allExchanges = useMemo(() => Array.from(new Set([
    ...snapshot.balances.map((item) => item.exchange),
    ...snapshot.positions.map((item) => item.exchange),
    ...snapshot.orders.map((item) => item.exchange),
    ...snapshot.fills.map((item) => item.exchange),
  ].filter(Boolean))).sort(), [snapshot]);
  const allInstances = useMemo(() => Array.from(new Set([
    ...snapshot.openOrders.map((item) => item.instance),
    ...snapshot.orders.map((item) => item.instance),
    ...snapshot.fills.map((item) => item.instance),
  ].filter(Boolean))).sort(), [snapshot]);
  const includesQuery = (value: string) => value.toLowerCase().includes(query.trim().toLowerCase());
  const matches = (item: { exchange: string; instance?: string }, values: string[], includeInstance = true) =>
    (exchange === "all" || item.exchange === exchange)
    && (!includeInstance || instance === "all" || item.instance === instance)
    && (query.trim() === "" || values.some(includesQuery));
  const positions = snapshot.positions.filter((item) => matches(item, [item.symbol, item.controllerId, item.connector, item.instance]));
  const openOrders = snapshot.openOrders.filter((item) => matches(item, [item.symbol, item.id, item.instance, item.status]));
  const orders = snapshot.orders.filter((item) => matches(item, [item.symbol, item.id, item.instance, item.status]));
  const fills = snapshot.fills.filter((item) => matches(item, [item.symbol, item.id, item.orderId, item.instance]));
  const tabCount: Record<Tab, number> = { positions: positions.length, openOrders: openOrders.length, orders: orders.length, fills: fills.length };
  const totalPages = Math.max(1, Math.ceil(tabCount[tab] / pageSize));
  const currentPage = Math.min(page, totalPages);
  const pageItems = <T,>(items: T[]) => items.slice((currentPage - 1) * pageSize, currentPage * pageSize);
  useEffect(() => setPage(1), [tab, query, exchange, instance, pageSize]);

  return <div className="page-stack">
    {showPerformance && <PaperPerformancePanel performance={snapshot.paperPerformance.filter((item) => exchange === "all" || item.exchange === exchange)} />}
    <section className="trading-toolbar"><div className="trading-tabs" role="tablist">{tabs.map((item) => <button role="tab" aria-selected={tab === item.key} className={`tab-${item.key}${tab === item.key ? " active" : ""}`} onClick={() => setTab(item.key)} key={item.key}>{item.label}<span>{tabCount[item.key]}</span></button>)}</div><div className="trading-refresh"><span>{snapshot.snapshotAgeSeconds === null ? "等待快照" : snapshot.snapshotAgeSeconds <= 15 ? "实时" : `${snapshot.snapshotAgeSeconds} 秒前`}</span><button onClick={() => router.refresh()}>刷新</button></div></section>
    <Searchable value={query} exchange={exchange} instance={instance} onValueChange={setQuery} onExchangeChange={setExchange} onInstanceChange={setInstance} exchanges={allExchanges} instances={allInstances} />
    {tab === "positions" && <Positions positions={pageItems(positions)} />}
    {tab === "openOrders" && <OpenOrders orders={pageItems(openOrders)} />}
    {tab === "orders" && <Orders orders={pageItems(orders)} />}
    {tab === "fills" && <Fills fills={pageItems(fills)} />}
    <Pagination totalItems={tabCount[tab]} page={currentPage} pageSize={pageSize} onPageChange={setPage} onPageSizeChange={setPageSize} />
    <section className="panel balance-panel"><div className="panel-head"><div><span className="eyebrow">账户资产</span><h2>运行时余额</h2></div><small>只读快照，每 5 秒写入</small></div><Balances balances={snapshot.balances.filter((item) => (exchange === "all" || item.exchange === exchange) && (instance === "all" || item.instance === instance))} /></section>
  </div>;
}
