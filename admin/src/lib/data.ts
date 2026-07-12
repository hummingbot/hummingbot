import "server-only";

import { execFileSync } from "node:child_process";
import { existsSync, readFileSync, statSync } from "node:fs";
import { resolve } from "node:path";
import type { IterationSnapshot, RuntimeSnapshot, StrategyCatalog, StrategyPromotionState } from "./types";

function projectRoot(): string {
  const candidates = [
    process.env.HUMMINGBOT_ROOT,
    resolve(process.cwd(), ".."),
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

export function getStrategyPromotionState(): StrategyPromotionState {
  const root = projectRoot();
  return readJson<StrategyPromotionState>(resolve(root, "reports/strategy_promotion_state.json"), {
    version: "0",
    generated_at: "",
    default_live_state: "disabled",
    strategies: [],
  });
}

export function getRuntimeSnapshot(): RuntimeSnapshot {
  const root = projectRoot();
  const reportPath = resolve(root, "reports/ai_strategy_router_iteration_latest.json");
  let reportAgeHours: number | null = null;
  if (existsSync(reportPath)) {
    reportAgeHours = Math.max(0, (Date.now() - statSync(reportPath).mtimeMs) / 3_600_000);
  }

  const containerLine = command([
    "docker", "ps", "-a", "--filter", "name=hummingbot-ai-router-paper", "--format", "{{.Status}}",
  ], root);
  let containerState: RuntimeSnapshot["containerState"] = "unknown";
  if (!containerLine) containerState = "missing";
  else if (containerLine.startsWith("Up")) containerState = "running";
  else if (containerLine.startsWith("Exited") || containerLine.startsWith("Created")) containerState = "stopped";

  const dirty = command(["git", "status", "--porcelain"], root);
  const containerDisplay = !containerLine
    ? "未找到纸面实例"
    : containerLine.replace(/^Up/, "运行中").replace(/^Exited/, "已退出").replace(/^Created/, "已创建");
  return {
    root,
    container: containerDisplay,
    containerState,
    reportAgeHours,
    reportStale: reportAgeHours === null || reportAgeHours > 1,
    gitHead: command(["git", "rev-parse", "--short", "HEAD"], root) || "未知",
    gitDirtyCount: dirty ? dirty.split("\n").filter(Boolean).length : 0,
  };
}
