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

export interface StrategyPromotionItem {
  strategy: string;
  strategy_label?: string;
  adapter: string;
  stage: string;
  stage_label?: string;
  live_enabled: boolean;
  completed_gates: string[];
  completed_gate_labels?: string[];
  blocking_gates: string[];
  blocking_gate_labels?: string[];
  target: string;
  execution_mode: string;
  execution_mode_label?: string;
  intended_regimes: string[];
  intended_regime_labels?: string[];
  minimum_paper_hours: number;
  required_features: string[];
  required_feature_labels?: string[];
  risk_controls: string[];
  risk_control_labels?: string[];
  evidence_refs?: string[];
}

export interface StrategyPromotionState {
  version: string;
  generated_at: string;
  default_live_state: string;
  strategies: StrategyPromotionItem[];
}

export interface WalkForwardReport {
  generated_at: string;
  strategy: string;
  strategy_label: string;
  status: string;
  validation_passed: boolean;
  summary: {
    completed_folds: number;
    profitable_folds: number;
    profitable_fold_ratio: number;
    total_adjusted_net_quote: number;
    maximum_drawdown_pct: number;
    total_positions: number;
  };
}

export interface RouterDecision {
  regime?: string;
  regime_label?: string;
  action?: string;
  action_label?: string;
  active?: string;
  recommended?: string;
  confidence?: string;
  scale?: string;
  reasons?: string;
  reason_labels?: string[];
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
