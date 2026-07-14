import "server-only";

import { execFileSync } from "node:child_process";
import { existsSync, readFileSync, readdirSync, statSync } from "node:fs";
import { resolve } from "node:path";
import type {
  IterationSnapshot,
  RuntimeSnapshot,
  StrategyCatalog,
  StrategyPromotionState,
  PaperPerformance,
  RoutingAdminSnapshot,
  TradingBalance,
  TradingFeeProfile,
  TradingFill,
  TradingOrder,
  TradingPosition,
  TradingSnapshot,
  UnifiedOperationsSnapshot,
  WalkForwardReport,
} from "./types";
import { zhExchange, zhInstance } from "./i18n";

function projectRoot(): string {
  const candidates = [
    process.env.HUMMINGBOT_ROOT,
    resolve(/* turbopackIgnore: true */ process.cwd(), ".."),
    process.cwd(),
  ].filter((value): value is string => Boolean(value));
  return candidates.find((candidate) => existsSync(resolve(candidate, "reports/strategy_catalog.json"))) ?? candidates[0];
}

function readJson<T>(path: string, fallback: T): T {
  try {
    return JSON.parse(readFileSync(path, "utf8")) as T;
  } catch {
    return fallback;
  }
}

function command(args: string[], cwd: string): string {
  try {
    return execFileSync(args[0], args.slice(1), {
      cwd,
      encoding: "utf8",
      timeout: 2500,
      stdio: ["ignore", "pipe", "ignore"],
    }).trim();
  } catch {
    return "";
  }
}

function paperContainerNames(): string[] {
  return Array.from(new Set([
    process.env.HUMMINGBOT_PAPER_CONTAINER,
    "hummingbot-pmm-mister-paper",
    "hummingbot-ai-router-paper",
  ].filter((value): value is string => Boolean(value?.trim())).map((value) => value.trim())));
}

function latestRuntimeSnapshotAgeSeconds(root: string): number | null {
  const files = runtimeSnapshotFiles(root);
  if (!files.length) return null;
  const newestMtime = Math.max(...files.map((path) => statSync(path).mtimeMs));
  return Math.max(0, Math.round((Date.now() - newestMtime) / 1_000));
}

export function getStrategyCatalog(): StrategyCatalog {
  const root = projectRoot();
  return readJson<StrategyCatalog>(resolve(root, "reports/strategy_catalog.json"), {
    version: "0",
    generated_at: "",
    policy: { profitability_claim: "策略目录不可用", promotion_path: [], default_live_state: "disabled" },
    sources: [],
    strategies: [],
  });
}

export function getIterationSnapshot(): IterationSnapshot {
  const root = projectRoot();
  return readJson<IterationSnapshot>(resolve(root, "reports/ai_strategy_router_iteration_latest.json"), {});
}

export function getRoutingAdminSnapshot(): RoutingAdminSnapshot {
  const root = projectRoot();
  const script = resolve(root, "scripts/strategy_router_admin_snapshot.py");
  try {
    const output = execFileSync(process.env.PYTHON_BIN || "python3", [script], {
      cwd: root,
      encoding: "utf8",
      timeout: 12_000,
      stdio: ["ignore", "pipe", "pipe"],
      env: { ...process.env, PYTHONUNBUFFERED: "1" },
    });
    return JSON.parse(output) as RoutingAdminSnapshot;
  } catch (error) {
    const message = "无法读取策略路由状态；请检查路由守护进程和运行日志。";
    return {
      version: 1,
      ok: false,
      error: message,
      generatedAt: new Date().toISOString(),
      configPath: "conf/runtime/strategy_router_accounts.yml",
      configValidated: false,
      environment: "paper",
      safety: {
        paperOnly: true,
        liveActions: false,
        automaticTransfers: false,
        manualTransferApproval: true,
        evolutionAutoStart: false,
        aiEnabled: false,
        aiMode: "shadow",
        aiProvider: "deepseek",
        aiPrimaryModel: "unknown",
      },
      router: {
        routeIntervalSeconds: 300,
        requireClosedCandle: true,
        reserveQuotePct: 0.25,
        minimumCandidateScore: 0.5,
        switchPolicy: {},
      },
      routerHeartbeat: {},
      globalRisk: {},
      accounts: [],
      strategies: [],
      compatibility: [],
      route: {
        mode: null,
        decisionAppended: null,
        releaseCount: 0,
        candidateCount: 0,
        plan: {
          decision_id: "",
          generated_at: 0,
          effective_at: 0,
          expires_at: 0,
          environment: "paper",
          allocations: [],
          reserve_quote: 0,
          blocked_candidates: [],
          risk_blockers: [],
          ai_applied: false,
          input_hash: "",
        },
        workerActions: [],
        runtimeMappingApplied: false,
        fresh: false,
      },
      workers: [],
      lifecycle: [],
      evolution: {
        generatedAt: null,
        summary: {},
        strategies: [],
        heartbeat: {},
        runtimeIdentity: null,
      },
      releases: [],
      decisions: [],
      transfers: { balances: {}, lastTransfer: {}, events: [] },
      conflicts: ["admin_snapshot_unavailable"],
    };
  }
}

export function getStrategyPromotionState(): StrategyPromotionState {
  const root = projectRoot();
  return readJson<StrategyPromotionState>(resolve(root, "reports/strategy_promotion_state.json"), {
    version: "0",
    generated_at: "",
    default_live_state: "disabled",
    strategies: [],
  });
}

export function getCoreWalkForwardReports(): WalkForwardReport[] {
  const root = projectRoot();
  return [
    "supertrend_walk_forward_latest.json",
    "pmm_mister_walk_forward_latest.json",
    "funding_arb_walk_forward_latest.json",
  ].map((filename) => readJson<WalkForwardReport | null>(resolve(root, "reports", filename), null))
    .filter((report): report is WalkForwardReport => report !== null);
}

export function getRuntimeSnapshot(): RuntimeSnapshot {
  const root = projectRoot();
  const reportPath = resolve(root, "reports/ai_strategy_router_iteration_latest.json");
  let reportAgeHours: number | null = null;
  if (existsSync(reportPath)) {
    reportAgeHours = Math.max(0, (Date.now() - statSync(reportPath).mtimeMs) / 3_600_000);
  }

  const containerNames = paperContainerNames();
  const dockerAvailable = Boolean(command(["docker", "version", "--format", "{{.Server.Version}}"], root));
  const dockerStatus = dockerAvailable
    ? containerNames.map((name) => ({
      name,
      status: command(["docker", "ps", "-a", "--filter", `name=^/${name}$`, "--format", "{{.Status}}"], root),
    })).find(({ status }) => Boolean(status))
    : undefined;
  const snapshotAgeSeconds = latestRuntimeSnapshotAgeSeconds(root);
  const freshRuntimeSnapshot = snapshotAgeSeconds !== null && snapshotAgeSeconds <= 30;
  let containerState: RuntimeSnapshot["containerState"] = "unknown";
  if (dockerStatus?.status.startsWith("Up")) containerState = "running";
  else if (dockerStatus?.status.startsWith("Exited") || dockerStatus?.status.startsWith("Created")) containerState = "stopped";
  else if (dockerAvailable) containerState = "missing";
  else if (freshRuntimeSnapshot) containerState = "running";

  const dirty = command(["git", "status", "--porcelain"], root);
  const containerEvidence: RuntimeSnapshot["containerEvidence"] = dockerStatus
    ? "docker"
    : freshRuntimeSnapshot
      ? "runtime_snapshot"
      : "unavailable";
  const localizeDuration = (value: string) => value
    .replace(/Less than a second/gi, "少于 1 秒")
    .replace(/About an hour/gi, "约 1 小时")
    .replace(/(\d+) seconds?/gi, "$1 秒")
    .replace(/(\d+) minutes?/gi, "$1 分钟")
    .replace(/(\d+) hours?/gi, "$1 小时")
    .replace(/(\d+) days?/gi, "$1 天")
    .replace(/(\d+) weeks?/gi, "$1 周")
    .replace(/(\d+) months?/gi, "$1 个月")
    .replace(/\(healthy\)/gi, "（健康）")
    .replace(/\(unhealthy\)/gi, "（不健康）")
    .replace(/ ago/gi, "前");
  const localizeContainerStatus = (value: string) => localizeDuration(value)
    .replace(/^Up\s*/i, "运行中 · ")
    .replace(/^Exited\s*/i, "已退出 · ")
    .replace(/^Created\s*/i, "已创建 · ");
  const containerDisplay = dockerStatus
    ? `${dockerStatus.name} · ${localizeContainerStatus(dockerStatus.status)}`
    : freshRuntimeSnapshot
      ? `${containerNames[0]} · 运行快照 ${snapshotAgeSeconds} 秒前`
      : dockerAvailable
        ? `未找到纸面实例（${containerNames.join("、")}）`
        : "无法读取容器引擎；等待纸面运行快照";
  return {
    root,
    container: containerDisplay,
    containerState,
    containerEvidence,
    reportAgeHours,
    reportStale: reportAgeHours === null || reportAgeHours > 1,
    gitHead: command(["git", "rev-parse", "--short", "HEAD"], root) || "未知",
    gitDirtyCount: dirty ? dirty.split("\n").filter(Boolean).length : 0,
  };
}

type SqliteRow = Record<string, string | number | null>;
type RuntimeTradingSnapshot = {
  generated_at?: string;
  balances?: Array<Record<string, unknown>>;
  positions?: Array<Record<string, unknown>>;
  open_orders?: Array<Record<string, unknown>>;
  mark_prices?: Array<Record<string, unknown>>;
};

type FeeProfileFile = {
  exchange?: string;
  source?: string;
  checked_at?: string;
  maker_fee_bps_gross?: string | number;
  taker_fee_bps_gross?: string | number;
  rebate_rate?: string | number;
  maker_fee_bps_net?: string | number;
  taker_fee_bps_net?: string | number;
};

const DECIMAL_SCALE = 1_000_000;

function asNumber(value: unknown): number {
  const parsed = typeof value === "number" ? value : Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

function asText(value: unknown): string {
  return typeof value === "string" ? value : value === null || value === undefined ? "" : String(value);
}

function feeProfiles(root: string): Map<string, TradingFeeProfile> {
  const profile = readJson<FeeProfileFile | null>(resolve(root, "data/binance_fee_profile.json"), null);
  if (!profile?.exchange) return new Map();
  const source: TradingFeeProfile["source"] = profile.source === "binance_account"
    ? "binance_account"
    : profile.source === "documented_standard_fallback"
      ? "documented_standard_fallback"
      : "unknown";
  return new Map([[profile.exchange, {
    exchange: profile.exchange,
    source,
    checkedAt: profile.checked_at || null,
    makerFeeBpsGross: asNumber(profile.maker_fee_bps_gross),
    takerFeeBpsGross: asNumber(profile.taker_fee_bps_gross),
    rebateRate: asNumber(profile.rebate_rate),
    makerFeeBpsNet: asNumber(profile.maker_fee_bps_net),
    takerFeeBpsNet: asNumber(profile.taker_fee_bps_net),
  }]]);
}

function connectorFromMarket(market: string): string {
  return market.replace(/_PaperTrade$/i, "_paper_trade");
}

function exchangeFromConnector(connector: string): string {
  return connector.replace(/_paper_trade$/i, "");
}

function isPaperConnector(connector: string): boolean {
  return connector.toLowerCase().endsWith("_paper_trade");
}

function databaseFiles(root: string): string[] {
  const dataPath = resolve(root, "data");
  if (!existsSync(dataPath)) return [];
  try {
    return readdirSync(dataPath)
      .filter((filename) => filename.endsWith(".sqlite"))
      .map((filename) => resolve(dataPath, filename));
  } catch {
    return [];
  }
}

function runtimeSnapshotFiles(root: string): string[] {
  const dataPath = resolve(root, "data");
  if (!existsSync(dataPath)) return [];
  try {
    return readdirSync(dataPath)
      .filter((filename) => filename.endsWith("_runtime.json") || filename === "trading_runtime.json")
      .map((filename) => resolve(dataPath, filename));
  } catch {
    return [];
  }
}

function sqliteRows(databasePath: string, query: string): SqliteRow[] {
  const output = command(["sqlite3", "-readonly", "-json", databasePath, query], resolve(databasePath, ".."));
  try {
    const rows = JSON.parse(output) as unknown;
    return Array.isArray(rows) ? rows.filter((row): row is SqliteRow => typeof row === "object" && row !== null) : [];
  } catch {
    return [];
  }
}

function instanceFromPath(path: string): string {
  return path.split("/").pop()
    ?.replace(/^conf_/, "")
    .replace(/\.(sqlite|json)$/, "")
    .replace(/_runtime$/, "") || "未知实例";
}

function timestamp(value: unknown): number {
  const raw = asNumber(value);
  return raw > 0 && raw < 10_000_000_000 ? raw * 1000 : raw;
}

function dedupe<T extends { id: string }>(items: T[]): T[] {
  return Array.from(new Map(items.map((item) => [item.id, item])).values());
}

type PnlComponents = { realized: number; unrealized: number; fees: number; markAvailable: boolean };

function pnlForSymbol(fills: TradingFill[], markPrice: number | undefined): PnlComponents {
  let quantity = 0;
  let costBasis = 0;
  let realized = 0;
  let fees = 0;
  for (const fill of [...fills].sort((a, b) => a.timestamp - b.timestamp)) {
    const amount = fill.amount;
    const fee = fill.fee;
    const notional = fill.notional;
    fees += fee;
    if (fill.side === "BUY") {
      if (quantity >= 0) {
        quantity += amount;
        costBasis += notional + fee;
      } else {
        const shortQuantity = Math.abs(quantity);
        const closing = Math.min(amount, shortQuantity);
        const allocatedProceeds = costBasis * (closing / shortQuantity);
        const allocatedFee = fee * (closing / amount);
        realized += allocatedProceeds - (fill.price * closing + allocatedFee);
        quantity += closing;
        costBasis -= allocatedProceeds;
        const remainder = amount - closing;
        if (remainder > 0) {
          quantity = remainder;
          costBasis = fill.price * remainder + fee * (remainder / amount);
        }
      }
    } else if (quantity <= 0) {
      quantity -= amount;
      costBasis += notional - fee;
    } else {
      const closing = Math.min(amount, quantity);
      const allocatedCost = costBasis * (closing / quantity);
      const allocatedFee = fee * (closing / amount);
      realized += fill.price * closing - allocatedFee - allocatedCost;
      quantity -= closing;
      costBasis -= allocatedCost;
      const remainder = amount - closing;
      if (remainder > 0) {
        quantity = -remainder;
        costBasis = fill.price * remainder - fee * (remainder / amount);
      }
    }
  }
  if (Math.abs(quantity) < 1e-12) return { realized, unrealized: 0, fees, markAvailable: true };
  if (markPrice === undefined || markPrice <= 0) return { realized, unrealized: 0, fees, markAvailable: false };
  const unrealized = quantity > 0 ? quantity * markPrice - costBasis : costBasis - Math.abs(quantity) * markPrice;
  return { realized, unrealized, fees, markAvailable: true };
}

function buildPaperPerformance(
  snapshots: Array<{ path: string; snapshot: RuntimeTradingSnapshot }>,
  fills: TradingFill[],
  profiles: Map<string, TradingFeeProfile>,
): PaperPerformance[] {
  const performance: PaperPerformance[] = [];
  for (const { path, snapshot } of snapshots) {
    const instance = instanceFromPath(path);
    const connectors = new Set([
      ...(snapshot.balances ?? []).map((row) => asText(row.connector)),
      ...(snapshot.open_orders ?? []).map((row) => asText(row.connector)),
      ...(snapshot.mark_prices ?? []).map((row) => asText(row.connector)),
    ].filter(Boolean));
    for (const connector of Array.from(connectors)) {
      const instanceFills = fills.filter((fill) => fill.instance === instance && fill.connector === connector);
      const symbols = new Set([
        ...instanceFills.map((fill) => fill.symbol),
        ...(snapshot.mark_prices ?? []).filter((row) => asText(row.connector) === connector).map((row) => asText(row.symbol)),
      ].filter(Boolean));
      const byQuote = new Map<string, string[]>();
      for (const symbol of Array.from(symbols)) {
        const quote = symbol.split("-").pop() || "USDT";
        byQuote.set(quote, [...(byQuote.get(quote) ?? []), symbol]);
      }
      for (const [quoteAsset, quoteSymbols] of Array.from(byQuote.entries())) {
        let realizedPnl = 0;
        let unrealizedPnl = 0;
        let fees = 0;
        let markAvailable = true;
        for (const symbol of quoteSymbols) {
          const mark = (snapshot.mark_prices ?? []).find((row) => asText(row.connector) === connector && asText(row.symbol) === symbol);
          const result = pnlForSymbol(instanceFills.filter((fill) => fill.symbol === symbol), mark ? asNumber(mark.price) : undefined);
          realizedPnl += result.realized;
          unrealizedPnl += result.unrealized;
          fees += result.fees;
          markAvailable = markAvailable && result.markAvailable;
        }
        const activeOrders = (snapshot.open_orders ?? []).filter((row) =>
          asText(row.connector) === connector && quoteSymbols.includes(asText(row.symbol)));
        const markPrices = (snapshot.mark_prices ?? []).filter((row) =>
          asText(row.connector) === connector && quoteSymbols.includes(asText(row.symbol)));
        const marketDataAgeSeconds = markPrices.length === 1 && markPrices[0].age_seconds !== null && markPrices[0].age_seconds !== undefined
          ? asNumber(markPrices[0].age_seconds)
          : null;
        performance.push({
          instance,
          connector,
          exchange: exchangeFromConnector(connector),
          paper: isPaperConnector(connector),
          quoteAsset,
          symbols: quoteSymbols,
          markPrice: markPrices.length === 1 && markPrices[0].price !== null && markPrices[0].price !== undefined
            ? asNumber(markPrices[0].price)
            : null,
          marketDataAgeSeconds,
          marketDataStale: markPrices.length === 0 || markPrices.some((row) => row.stale === true),
          activeOrderCount: activeOrders.length,
          pendingNotional: activeOrders.reduce((total, order) =>
            total + Math.max(0, asNumber(order.amount) - asNumber(order.filled)) * asNumber(order.price), 0),
          fillCount: instanceFills.filter((fill) => quoteSymbols.includes(fill.symbol)).length,
          realizedPnl,
          unrealizedPnl,
          netPnl: realizedPnl + unrealizedPnl,
          fees,
          feeProfile: profiles.get(exchangeFromConnector(connector)) ?? null,
          markAvailable,
        });
      }
    }
  }
  return performance;
}

export function getTradingSnapshot(): TradingSnapshot {
  const root = projectRoot();
  const snapshots = runtimeSnapshotFiles(root).flatMap((path) => {
    const snapshot = readJson<RuntimeTradingSnapshot | null>(path, null);
    return snapshot ? [{ path, snapshot }] : [];
  });
  const generatedAt = snapshots
    .map(({ snapshot }) => snapshot.generated_at)
    .filter((value): value is string => Boolean(value))
    .sort()
    .at(-1) ?? null;
  const snapshotAgeSeconds = generatedAt === null
    ? null
    : Math.max(0, Math.round((Date.now() - new Date(generatedAt).getTime()) / 1000));
  // Never present a stopped instance's last persisted state as a live order or position.
  const currentSnapshots = snapshotAgeSeconds !== null && snapshotAgeSeconds <= 30 ? snapshots : [];

  type BalanceWithId = TradingBalance & { id: string };
  const balanceRows = currentSnapshots.flatMap(({ path, snapshot }) => (snapshot.balances ?? []).map((row): BalanceWithId => {
    const connector = asText(row.connector);
    const asset = asText(row.asset);
    return {
      instance: instanceFromPath(path),
      connector,
      exchange: asText(row.exchange) || exchangeFromConnector(connector),
      paper: row.paper === true || isPaperConnector(connector),
      asset,
      total: asNumber(row.total),
      available: asNumber(row.available),
      id: `${instanceFromPath(path)}:${connector}:${asset}`,
    };
  }));
  const balances = Array.from(new Map(balanceRows.map((balance) => [balance.id, balance])).values())
    .map(({ id: _id, ...balance }) => balance);

  const positions = dedupe(currentSnapshots.flatMap(({ path, snapshot }) => (snapshot.positions ?? []).map((row): TradingPosition => {
    const connector = asText(row.connector);
    return {
      id: `${instanceFromPath(path)}:${asText(row.id)}`,
      instance: instanceFromPath(path),
      controllerId: asText(row.controller_id),
      connector,
      exchange: asText(row.exchange) || exchangeFromConnector(connector),
      paper: row.paper === true || isPaperConnector(connector),
      symbol: asText(row.symbol),
      side: asText(row.side),
      amount: asNumber(row.amount),
      entryPrice: asNumber(row.entry_price),
      notional: asNumber(row.notional),
      unrealizedPnl: asNumber(row.unrealized_pnl),
      realizedPnl: asNumber(row.realized_pnl),
      fees: asNumber(row.fees),
      pnl: asNumber(row.pnl),
    };
  })));

  const openOrders = dedupe(currentSnapshots.flatMap(({ path, snapshot }) => (snapshot.open_orders ?? []).map((row): TradingOrder => {
    const connector = asText(row.connector);
    const amount = asNumber(row.amount);
    const price = asNumber(row.price);
    const id = asText(row.id);
    return {
      id: `${instanceFromPath(path)}:${id}`,
      instance: instanceFromPath(path),
      connector,
      exchange: asText(row.exchange) || exchangeFromConnector(connector),
      paper: row.paper === true || isPaperConnector(connector),
      symbol: asText(row.symbol),
      side: asText(row.side),
      orderType: asText(row.order_type),
      price,
      amount,
      filled: asNumber(row.filled),
      notional: amount * price,
      status: asText(row.status),
      createdAt: timestamp(row.created_at),
      updatedAt: timestamp(row.updated_at),
      source: "runtime",
    };
  })));

  const orders: TradingOrder[] = [];
  const fills: TradingFill[] = [];
  for (const databasePath of databaseFiles(root)) {
    const instance = instanceFromPath(databasePath);
    const orderRows = sqliteRows(databasePath, `
      SELECT id, market, symbol, order_type, amount / ${DECIMAL_SCALE}.0 AS amount,
             price / ${DECIMAL_SCALE}.0 AS price, last_status, creation_timestamp, last_update_timestamp
      FROM "Order" ORDER BY last_update_timestamp DESC
    `);
    for (const row of orderRows) {
      const connector = connectorFromMarket(asText(row.market));
      const amount = asNumber(row.amount);
      const price = asNumber(row.price);
      const orderId = asText(row.id);
      orders.push({
        id: `${instance}:${orderId}`,
        instance,
        connector,
        exchange: exchangeFromConnector(connector),
        paper: isPaperConnector(connector),
        symbol: asText(row.symbol),
        side: orderId.toLowerCase().startsWith("buy:") ? "BUY" : orderId.toLowerCase().startsWith("sell:") ? "SELL" : "—",
        orderType: asText(row.order_type),
        price,
        amount,
        filled: 0,
        notional: amount * price,
        status: asText(row.last_status),
        createdAt: timestamp(row.creation_timestamp),
        updatedAt: timestamp(row.last_update_timestamp),
        source: "recorder",
      });
    }

    const fillRows = sqliteRows(databasePath, `
      SELECT exchange_trade_id, order_id, market, symbol, trade_type, order_type,
             amount / ${DECIMAL_SCALE}.0 AS amount, price / ${DECIMAL_SCALE}.0 AS price,
             trade_fee_in_quote / ${DECIMAL_SCALE}.0 AS fee, timestamp
      FROM "TradeFill" ORDER BY timestamp DESC
    `);
    for (const row of fillRows) {
      const connector = connectorFromMarket(asText(row.market));
      const amount = asNumber(row.amount);
      const price = asNumber(row.price);
      fills.push({
        id: `${instance}:${asText(row.exchange_trade_id)}`,
        instance,
        connector,
        exchange: exchangeFromConnector(connector),
        paper: isPaperConnector(connector),
        symbol: asText(row.symbol),
        side: asText(row.trade_type),
        orderType: asText(row.order_type),
        price,
        amount,
        notional: amount * price,
        fee: asNumber(row.fee),
        timestamp: timestamp(row.timestamp),
        orderId: asText(row.order_id),
      });
    }
  }

  orders.sort((a, b) => b.updatedAt - a.updatedAt);
  fills.sort((a, b) => b.timestamp - a.timestamp);
  const uniqueOrders = dedupe(orders);
  const uniqueFills = dedupe(fills);
  const paperPerformance = buildPaperPerformance(currentSnapshots, uniqueFills, feeProfiles(root));
  return {
    generatedAt,
    snapshotAgeSeconds,
    balances,
    positions,
    openOrders,
    orders: uniqueOrders,
    fills: uniqueFills,
    paperPerformance,
    metrics: {
      historicalOrders: uniqueOrders.length,
      historicalFills: uniqueFills.length,
      fillNotional: uniqueFills.reduce((total, fill) => total + fill.notional, 0),
      openOrders: openOrders.length,
      positions: positions.length,
    },
  };
}

function primaryPaperPerformance(snapshot: TradingSnapshot): PaperPerformance | null {
  const configuredInstance = process.env.HUMMINGBOT_PRIMARY_PAPER_INSTANCE?.trim() || "pmm_mister_paper";
  return snapshot.paperPerformance.find((item) => item.instance === configuredInstance && item.paper)
    ?? snapshot.paperPerformance.find((item) => item.paper)
    ?? null;
}

function executionScopeLabel(performance: PaperPerformance | null): string {
  if (!performance) return "当前纸盘实例";
  const exchange = zhExchange(performance.exchange);
  const strategy = zhInstance(performance.instance);
  return `${exchange} · ${strategy}${performance.paper ? "（纸盘）" : ""}`;
}

/**
 * Canonical source for all current-state copy in the admin. It intentionally
 * scopes counters and PnL to one active paper instance; old recorder rows
 * remain searchable in the trading ledger but can never inflate current data.
 */
export function getUnifiedOperationsSnapshot(): UnifiedOperationsSnapshot {
  const runtime = getRuntimeSnapshot();
  const trading = getTradingSnapshot();
  const primary = primaryPaperPerformance(trading);
  const isPrimary = (item: { instance: string; connector: string }) =>
    primary !== null && item.instance === primary.instance && item.connector === primary.connector;
  const scopedOpenOrders = trading.openOrders.filter(isPrimary);
  const scopedPositions = trading.positions.filter(isPrimary);
  const scopedOrders = trading.orders.filter(isPrimary);
  const scopedFills = trading.fills.filter(isPrimary);
  const snapshotFresh = trading.snapshotAgeSeconds !== null && trading.snapshotAgeSeconds <= 30;
  const stopped = runtime.containerState === "stopped" || runtime.containerState === "missing";
  const waitingForSnapshot = !primary || !snapshotFresh;

  let state: UnifiedOperationsSnapshot["execution"]["state"] = "valuing";
  let stateLabel = "实时估值中";
  let stateDetail = `${scopedFills.length} 笔成交已写入当前账本。`;
  let tone: UnifiedOperationsSnapshot["execution"]["tone"] = "green";
  if (stopped) {
    state = "stopped";
    stateLabel = "纸盘实例未运行";
    stateDetail = "未检测到当前纸盘实例；历史记录不会当作实时状态展示。";
    tone = "red";
  } else if (waitingForSnapshot) {
    state = "awaiting_snapshot";
    stateLabel = "等待运行快照";
    stateDetail = "尚未收到当前实例的实时账本，暂不展示当前持仓、委托或盈亏。";
    tone = "amber";
  } else if (primary.marketDataStale) {
    state = "market_stale";
    stateLabel = "行情中断，纸盘已暂停";
    stateDetail = primary.marketDataAgeSeconds === null
      ? "未收到有效行情更新，当前盈亏不可评估。"
      : `行情已 ${Math.round(primary.marketDataAgeSeconds)} 秒未更新，当前盈亏不可评估。`;
    tone = "red";
  } else if (scopedFills.length === 0) {
    state = "awaiting_first_fill";
    stateLabel = "等待首笔成交";
    stateDetail = `${scopedOpenOrders.length} 笔活动委托正在等待成交；冻结资金不计作亏损。`;
    tone = "amber";
  }

  const hasPnl = primary !== null && scopedFills.length > 0 && !primary.marketDataStale && primary.markAvailable;
  return {
    runtime,
    trading,
    execution: {
      state,
      stateLabel,
      stateDetail,
      tone,
      scopeLabel: executionScopeLabel(primary),
      instance: primary?.instance ?? null,
      exchange: primary?.exchange ?? null,
      paper: primary?.paper ?? true,
      quoteAsset: primary?.quoteAsset ?? null,
      market: primary?.symbols.join(" / ") || null,
      snapshotAgeSeconds: trading.snapshotAgeSeconds,
      marketDataAgeSeconds: primary?.marketDataAgeSeconds ?? null,
      activeOrderCount: scopedOpenOrders.length,
      positionCount: scopedPositions.length,
      orderHistoryCount: scopedOrders.length,
      fillCount: scopedFills.length,
      fillNotional: scopedFills.reduce((total, fill) => total + fill.notional, 0),
      netPnl: hasPnl && primary ? primary.netPnl : null,
      hasPnl,
    },
  };
}
