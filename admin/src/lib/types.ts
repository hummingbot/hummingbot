export type StrategyStatus = "enabled" | "shadow" | "research" | "blocked";

export interface StrategyItem {
  id: string;
  name: string;
  family: string;
  status: StrategyStatus;
  evidence: string;
  source: string;
  license: string;
  regimes: string[];
  risk: string;
  adapter: string;
  summary: string;
}

export interface StrategySource {
  name: string;
  repo: string;
  url: string;
  license: string;
  role: string;
}

export interface StrategyCatalog {
  version: string;
  generated_at: string;
  policy: {
    profitability_claim: string;
    promotion_path: string[];
    default_live_state: string;
  };
  sources: StrategySource[];
  strategies: StrategyItem[];
}

export interface RouterDecision {
  regime?: string;
  action?: string;
  active?: string;
  recommended?: string;
  confidence?: string;
  scale?: string;
  reasons?: string;
  log_time?: string;
}

export interface IterationSnapshot {
  generated_at?: string;
  live?: {
    container?: string;
    container_status?: string;
    orders?: number;
    fills?: number;
    latest_decision?: RouterDecision | null;
    latest_protect?: RouterDecision | null;
    pnl?: Record<string, string>;
    status_counts?: Record<string, number>;
  };
  registry?: {
    total?: number;
    enabled_count?: number;
    disabled_count?: number;
    families?: Record<string, number>;
  };
  gaps?: Array<{ severity: string; area: string; title: string; action: string }>;
  tests?: Record<string, { ok?: boolean }>;
}

export interface RuntimeSnapshot {
  root: string;
  container: string;
  containerState: "running" | "stopped" | "missing" | "unknown";
  reportAgeHours: number | null;
  reportStale: boolean;
  gitHead: string;
  gitDirtyCount: number;
}
