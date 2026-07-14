import { randomUUID } from "node:crypto";
import { execFileSync } from "node:child_process";
import { existsSync, readFileSync } from "node:fs";
import { resolve } from "node:path";
import { NextResponse } from "next/server";
import type { RoutingAdminSnapshot } from "@/lib/types";

export const dynamic = "force-dynamic";

type Action = "refresh_route" | "simulate_transfer" | "update_account_limits";

function rootPath(): string {
  const candidates = [process.env.HUMMINGBOT_ROOT, resolve(/* turbopackIgnore: true */ process.cwd(), ".."), process.cwd()]
    .filter((value): value is string => Boolean(value));
  return candidates.find((candidate) => existsSync(resolve(candidate, "scripts/run_strategy_router.py"))) ?? candidates[0];
}

function sameOrigin(request: Request): boolean {
  const origin = request.headers.get("origin");
  const host = request.headers.get("host");
  if (!origin || !host) return true;
  try {
    return new URL(origin).host === host;
  } catch {
    return false;
  }
}

function runPython(args: string[], timeout = 30_000): string {
  const root = rootPath();
  return execFileSync(process.env.PYTHON_BIN || "python3", args, {
    cwd: root,
    encoding: "utf8",
    timeout,
    stdio: ["ignore", "pipe", "pipe"],
    env: { ...process.env, PYTHONUNBUFFERED: "1" },
  }).trim();
}

function routingSnapshot(): RoutingAdminSnapshot {
  const output = runPython([resolve(rootPath(), "scripts/strategy_router_admin_snapshot.py")], 12_000);
  return JSON.parse(output) as RoutingAdminSnapshot;
}

function commandError(error: unknown): string {
  if (typeof error === "object" && error !== null && "stdout" in error) {
    const output = String((error as { stdout?: unknown }).stdout ?? "").trim();
    try {
      const payload = JSON.parse(output) as { error?: unknown };
      if (typeof payload.error === "string") {
        const detail = payload.error;
        const release = detail.match(/Evolution release status is not routable:\s*([^\s\[]+)/)?.[1];
        if (release) return "策略进化发布状态不可路由，策略路由已按失败关闭原则拒绝重算。请先处理发布或回滚冲突。";
        if (detail.includes("paper transfer is in cooldown")) return "纸盘划转仍在冷却期，余额和审计账本均未改变。";
        if (detail.includes("exceeds daily limit")) return "纸盘划转超过当日限额，余额和审计账本均未改变。";
        if (detail.includes("violates single-transfer limits")) return "纸盘划转金额超出该账户单笔上下限。";
        if (detail.includes("violate source reserve")) return "纸盘划转会突破来源账户最低保留资金，已拒绝。";
        if (detail.includes("not allowlisted")) return "目标账户不在来源账户的划转白名单内。";
        if (detail.includes("policy is disabled")) return "该来源账户未启用纸盘划转策略。";
        if (detail.includes("unknown account")) return "纸盘划转引用了未配置账户。";
        if (detail.includes("another StrategyRouterService")) return "另一个策略路由周期正在运行，请稍后重试。";
        return "策略路由操作失败；底层错误已记录，请检查运行日志。";
      }
    } catch {
      // Fall through to the sanitized generic response.
    }
  }
  return "策略路由操作失败；状态未被伪装为成功。";
}

export async function GET() {
  try {
    return NextResponse.json(routingSnapshot(), {
      headers: { "cache-control": "no-store" },
    });
  } catch (error) {
    return NextResponse.json({ ok: false, error: commandError(error) }, { status: 500 });
  }
}

export async function POST(request: Request) {
  if (!sameOrigin(request)) {
    return NextResponse.json({ message: "请求来源不受信任" }, { status: 403 });
  }
  let body: Record<string, unknown>;
  try {
    body = await request.json() as Record<string, unknown>;
  } catch {
    return NextResponse.json({ message: "请求格式无效" }, { status: 400 });
  }
  const action = body.action as Action;
  if (!(["refresh_route", "simulate_transfer", "update_account_limits"] as Action[]).includes(action)) {
    return NextResponse.json({ message: "不支持的策略路由操作" }, { status: 400 });
  }

  const root = rootPath();
  try {
    if (action === "update_account_limits") {
      const account = typeof body.account === "string" ? body.account.trim() : "";
      const safeId = /^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$/;
      if (!safeId.test(account)) {
        return NextResponse.json({ message: "账户标识无效" }, { status: 400 });
      }
      const fields = [
        "minimum_reserve_quote",
        "maximum_capital_quote",
        "maximum_drawdown_quote",
        "maximum_gross_exposure_quote",
        "maximum_open_orders",
        "market_data_stale_after_seconds",
      ] as const;
      const fieldLabels: Record<(typeof fields)[number], string> = {
        minimum_reserve_quote: "最低保留资金",
        maximum_capital_quote: "最大可分配资金",
        maximum_drawdown_quote: "最大回撤",
        maximum_gross_exposure_quote: "最大总敞口",
        maximum_open_orders: "最大活动委托数",
        market_data_stale_after_seconds: "行情过期阈值",
      };
      const args = [resolve(root, "scripts/update_strategy_router_account.py"), "--account", account];
      for (const field of fields) {
        const value = body[field];
        const number = typeof value === "number" ? value : Number(value);
        const integerField = field === "maximum_open_orders" || field === "market_data_stale_after_seconds";
        const maximum = integerField ? (field === "maximum_open_orders" ? 10_000 : 86_400) : 1_000_000_000;
        const minimum = field === "market_data_stale_after_seconds" ? 1 : 0;
        if (!Number.isFinite(number) || number < minimum || number > maximum || (integerField && !Number.isInteger(number))) {
          return NextResponse.json({ message: `账户限制“${fieldLabels[field]}”无效` }, { status: 400 });
        }
        args.push(`--${field.replaceAll("_", "-")}`, String(number));
      }
      runPython(args);
      return NextResponse.json({
        message: "纸盘账户限制已校验并写入运行配置；下一次路由计算使用新值。",
        snapshot: routingSnapshot(),
      });
    }

    if (action === "refresh_route") {
      const runtimeMap = resolve(root, "reports/examples/strategy_router_runtime_map.example.json");
      const mapping = JSON.parse(readFileSync(runtimeMap, "utf8")) as {
        runtime_snapshots?: Record<string, { path?: string }>;
      };
      const runtimeRelative = mapping.runtime_snapshots?.["binance-mm"]?.path;
      if (!runtimeRelative || runtimeRelative.startsWith("/") || runtimeRelative.includes("..")) {
        return NextResponse.json({ message: "当前运行映射无效，拒绝刷新路由。" }, { status: 409 });
      }
      const runtimePath = resolve(root, runtimeRelative);
      if (!existsSync(runtimePath)) {
        return NextResponse.json({ message: "当前候选运行快照不存在，拒绝刷新路由。" }, { status: 409 });
      }
      const runtime = JSON.parse(readFileSync(runtimePath, "utf8")) as {
        mark_prices?: Array<{ symbol?: string }>;
      };
      const marketSymbol = runtime.mark_prices?.find((row) => typeof row.symbol === "string")?.symbol;
      if (!marketSymbol) {
        return NextResponse.json({ message: "当前运行快照没有可路由的行情标的。" }, { status: 409 });
      }
      runPython([
        resolve(root, "scripts/run_strategy_router.py"),
        "--market-runtime", runtimePath,
        "--market-symbol", marketSymbol,
        "--accounts", resolve(root, "reports/examples/strategy_router_accounts.smoke.json"),
        "--runtime-map", runtimeMap,
      ]);
      return NextResponse.json({
        message: "已按最新纸盘快照重新计算路由；没有启动、停止或切换执行实例。",
        snapshot: routingSnapshot(),
      });
    }

    const source = typeof body.source === "string" ? body.source.trim() : "";
    const target = typeof body.target === "string" ? body.target.trim() : "";
    const approvedBy = typeof body.approvedBy === "string" ? body.approvedBy.trim() : "";
    const amount = typeof body.amount === "number" ? body.amount : Number(body.amount);
    const safeId = /^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$/;
    if (!safeId.test(source) || !safeId.test(target) || source === target) {
      return NextResponse.json({ message: "划转账户无效" }, { status: 400 });
    }
    if (!approvedBy || approvedBy.length > 64) {
      return NextResponse.json({ message: "必须填写 1–64 字符的纸盘审批人" }, { status: 400 });
    }
    if (!Number.isFinite(amount) || amount <= 0 || amount > 1_000_000) {
      return NextResponse.json({ message: "划转金额无效" }, { status: 400 });
    }
    const output = runPython([
      resolve(root, "scripts/simulate_strategy_router_transfer.py"),
      "--transfer-id", `admin-${randomUUID()}`,
      "--source", source,
      "--target", target,
      "--amount", String(amount),
      "--approved-by", approvedBy,
    ]);
    const transfer = JSON.parse(output) as { transfer?: unknown };
    return NextResponse.json({
      message: "纸盘余额模拟划转已写入幂等审计账本；未调用交易所接口。",
      transfer: transfer.transfer,
      snapshot: routingSnapshot(),
    });
  } catch (error) {
    return NextResponse.json({ message: commandError(error) }, { status: 409 });
  }
}
