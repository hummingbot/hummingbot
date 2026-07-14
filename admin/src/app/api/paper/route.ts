import { execFileSync } from "node:child_process";
import { existsSync, mkdirSync, readFileSync, renameSync, writeFileSync } from "node:fs";
import { resolve } from "node:path";
import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";

const PAPER_CONTAINER = "hummingbot-pmm-mister-paper";
const ROUTING_ACCOUNT = "binance-mm";

type Action = "start" | "stop" | "fresh";
type ContainerState = "running" | "stopped" | "missing";

function rootPath(): string {
  return process.env.HUMMINGBOT_ROOT || resolve(process.cwd(), "..");
}

function docker(args: string[]): string {
  return execFileSync("docker", args, {
    cwd: rootPath(),
    encoding: "utf8",
    timeout: 35_000,
    stdio: ["ignore", "pipe", "pipe"],
  }).trim();
}

function paperContainerState(): ContainerState {
  try {
    const status = docker(["inspect", "--format", "{{.State.Status}}", PAPER_CONTAINER]);
    return status === "running" ? "running" : "stopped";
  } catch {
    return "missing";
  }
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

function readJson(path: string): Record<string, unknown> {
  try {
    const value = JSON.parse(readFileSync(path, "utf8")) as unknown;
    return typeof value === "object" && value !== null ? value as Record<string, unknown> : {};
  } catch {
    return {};
  }
}

function activePaperArtifacts(): { files: string[]; candidateId: string | null; releaseStatus: string | null } {
  const root = rootPath();
  const workerState = readJson(resolve(root, "data/strategy-routing/workers.json"));
  const workers = workerState.workers as Record<string, Record<string, unknown>> | undefined;
  const worker = workers?.[ROUTING_ACCOUNT] ?? {};
  const release = readJson(resolve(root, "data/strategy-evolution/strategies/pmm_mister/paper/release-manifest.json"));
  const files = new Set<string>();
  for (const value of [worker.runtime_path, release.runtime_file, release.database_file]) {
    if (typeof value === "string" && value.trim()) files.add(value.split("/").pop() || "");
  }
  return {
    files: Array.from(files).filter(Boolean),
    candidateId: typeof worker.candidate_id === "string" ? worker.candidate_id : null,
    releaseStatus: typeof release.status === "string" ? release.status : null,
  };
}

function updateRoutingWorker(status: "running" | "stopped", action: Action): void {
  const path = resolve(rootPath(), "data/strategy-routing/workers.json");
  const state = readJson(path);
  const workers = state.workers as Record<string, Record<string, unknown>> | undefined;
  if (!workers?.[ROUTING_ACCOUNT]) return;
  workers[ROUTING_ACCOUNT] = {
    ...workers[ROUTING_ACCOUNT],
    status,
    last_admin_action: action,
    last_admin_action_at: new Date().toISOString(),
  };
  const temporary = `${path}.tmp`;
  writeFileSync(temporary, `${JSON.stringify(state, null, 2)}\n`);
  renameSync(temporary, path);
}

function archiveCurrentPaperRun(): { archivePath: string; moved: string[] } {
  const dataPath = resolve(rootPath(), "data");
  const archiveName = new Date().toISOString().replace(/[:.]/g, "-");
  const archivePath = resolve(dataPath, "archive", "paper-runs", archiveName);
  mkdirSync(archivePath, { recursive: true });
  const artifacts = activePaperArtifacts();
  const moved: string[] = [];
  for (const filename of artifacts.files) {
    for (const candidate of [filename, `${filename}-wal`, `${filename}-shm`]) {
      const source = resolve(dataPath, candidate);
      if (!existsSync(source)) continue;
      renameSync(source, resolve(archivePath, candidate));
      moved.push(candidate);
    }
  }
  writeFileSync(resolve(archivePath, "session.json"), JSON.stringify({
    archivedAt: new Date().toISOString(),
    instance: ROUTING_ACCOUNT,
    candidateId: artifacts.candidateId,
    reason: "new_paper_observation_period",
    moved,
  }, null, 2));
  return { archivePath, moved };
}

function response(state: ContainerState, message: string, archivePath?: string) {
  return NextResponse.json({ state, message, archivePath });
}

export async function POST(request: Request) {
  if (!sameOrigin(request)) return NextResponse.json({ message: "请求来源不受信任" }, { status: 403 });
  let action: Action;
  try {
    const body = await request.json() as { action?: unknown };
    action = body.action as Action;
  } catch {
    return NextResponse.json({ message: "请求格式无效" }, { status: 400 });
  }
  if (!["start", "stop", "fresh"].includes(action)) {
    return NextResponse.json({ message: "不支持的纸盘操作" }, { status: 400 });
  }

  try {
    const currentState = paperContainerState();
    if (action === "start") {
      if (currentState === "missing") return response(currentState, "纸盘实例尚未初始化，请先在本机执行一次纸盘启动脚本。");
      if (currentState === "running") {
        updateRoutingWorker("running", action);
        return response(currentState, "纸盘策略已经在运行。");
      }
      const releaseStatus = activePaperArtifacts().releaseStatus;
      if (!releaseStatus || !["active_verified", "paper_champion"].includes(releaseStatus)) {
        return NextResponse.json({ message: "策略进化发布状态不可路由，策略路由拒绝重新启动。" }, { status: 409 });
      }
      docker(["start", PAPER_CONTAINER]);
      updateRoutingWorker("running", action);
      return response("running", "纸盘策略已启动，等待行情和运行快照恢复。");
    }

    if (action === "stop") {
      if (currentState === "missing") return response(currentState, "没有可停止的纸盘实例。");
      if (currentState === "stopped") {
        updateRoutingWorker("stopped", action);
        return response(currentState, "纸盘策略已经停止。");
      }
      docker(["stop", "--time", "20", PAPER_CONTAINER]);
      updateRoutingWorker("stopped", action);
      return response("stopped", "纸盘策略已停止；历史账本已保留。");
    }

    if (currentState === "missing") return response(currentState, "纸盘实例尚未初始化，不能创建新的观察期。");
    const releaseStatus = activePaperArtifacts().releaseStatus;
    if (!releaseStatus || !["active_verified", "paper_champion"].includes(releaseStatus)) {
      return NextResponse.json({ message: "策略进化发布状态不可路由，禁止绕过策略路由新建观察期。" }, { status: 409 });
    }
    if (currentState === "running") docker(["stop", "--time", "20", PAPER_CONTAINER]);
    const archive = archiveCurrentPaperRun();
    docker(["start", PAPER_CONTAINER]);
    updateRoutingWorker("running", action);
    return response("running", `已新建纸盘观察期，归档 ${archive.moved.length} 个运行文件并重新启动。`, archive.archivePath);
  } catch {
    return NextResponse.json({ message: "纸盘控制操作失败；请查看本机容器日志后重试。" }, { status: 500 });
  }
}
