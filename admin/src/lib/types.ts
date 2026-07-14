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
  containerEvidence: "docker" | "runtime_snapshot" | "unavailable";
  reportAgeHours: number | null;
  reportStale: boolean;
  gitHead: string;
  gitDirtyCount: number;
}

export interface TradingBalance {
  instance: string;
  connector: string;
  exchange: string;
  paper: boolean;
  asset: string;
  total: number;
  available: number;
}

export interface TradingPosition {
  id: string;
  instance: string;
  controllerId: string;
  connector: string;
  exchange: string;
  paper: boolean;
  symbol: string;
  side: string;
  amount: number;
  entryPrice: number;
  notional: number;
  unrealizedPnl: number;
  realizedPnl: number;
  fees: number;
  pnl: number;
}

export interface TradingOrder {
  id: string;
  instance: string;
  connector: string;
  exchange: string;
  paper: boolean;
  symbol: string;
  side: string;
  orderType: string;
  price: number;
  amount: number;
  filled: number;
  notional: number;
  status: string;
  createdAt: number;
  updatedAt: number;
  source: "runtime" | "recorder";
}

export interface TradingFill {
  id: string;
  instance: string;
  connector: string;
  exchange: string;
  paper: boolean;
  symbol: string;
  side: string;
  orderType: string;
  price: number;
  amount: number;
  notional: number;
  fee: number;
  timestamp: number;
  orderId: string;
}

export interface TradingFeeProfile {
  exchange: string;
  source: "binance_account" | "documented_standard_fallback" | "unknown";
  checkedAt: string | null;
  makerFeeBpsGross: number;
  takerFeeBpsGross: number;
  rebateRate: number;
  makerFeeBpsNet: number;
  takerFeeBpsNet: number;
}

export interface PaperPerformance {
  instance: string;
  connector: string;
  exchange: string;
  paper: boolean;
  quoteAsset: string;
  symbols: string[];
  markPrice: number | null;
  marketDataAgeSeconds: number | null;
  marketDataStale: boolean;
  activeOrderCount: number;
  pendingNotional: number;
  fillCount: number;
  realizedPnl: number;
  unrealizedPnl: number;
  netPnl: number;
  fees: number;
  feeProfile: TradingFeeProfile | null;
  markAvailable: boolean;
}

export interface TradingSnapshot {
  generatedAt: string | null;
  snapshotAgeSeconds: number | null;
  balances: TradingBalance[];
  positions: TradingPosition[];
  openOrders: TradingOrder[];
  orders: TradingOrder[];
  fills: TradingFill[];
  paperPerformance: PaperPerformance[];
  metrics: {
    historicalOrders: number;
    historicalFills: number;
    fillNotional: number;
    openOrders: number;
    positions: number;
  };
}

export type ExecutionState = "stopped" | "awaiting_snapshot" | "market_stale" | "awaiting_first_fill" | "valuing";

/**
 * The only site-wide view of the currently selected execution instance.
 * Historical records remain available in TradingSnapshot, but must not be
 * presented as the state of the active paper instance.
 */
export interface ExecutionOverview {
  state: ExecutionState;
  stateLabel: string;
  stateDetail: string;
  tone: "green" | "amber" | "red" | "blue" | "neutral";
  scopeLabel: string;
  instance: string | null;
  exchange: string | null;
  paper: boolean;
  quoteAsset: string | null;
  market: string | null;
  snapshotAgeSeconds: number | null;
  marketDataAgeSeconds: number | null;
  activeOrderCount: number;
  positionCount: number;
  orderHistoryCount: number;
  fillCount: number;
  fillNotional: number;
  netPnl: number | null;
  hasPnl: boolean;
}

export interface UnifiedOperationsSnapshot {
  runtime: RuntimeSnapshot;
  trading: TradingSnapshot;
  execution: ExecutionOverview;
}

export interface RoutingAccountSnapshot {
  id: string;
  kind: "master" | "subaccount" | "independent";
  parentId: string | null;
  exchange: string;
  connector: string;
  workerId: string | null;
  tradingEnabled: boolean;
  settlementAsset: string;
  allowedSleeves: string[];
  allowedPairs: string[];
  positionMode: string;
  marginMode: string;
  allocation: {
    minimumReserveQuote: number;
    maximumCapitalQuote: number;
  };
  risk: {
    maximumDrawdownQuote: number;
    maximumGrossExposureQuote: number;
    maximumOpenOrders: number;
    maximumLeverage: number | null;
    marketDataStaleAfterSeconds: number;
  };
  permissions: {
    trade: boolean;
    internalTransfer: boolean;
    withdraw: boolean;
  };
  transferPolicy: {
    enabled: boolean;
    requireManualApproval: boolean;
    allowedCounterparties: string[];
    minimumTransferQuote: number;
    maximumTransferQuote: number;
    maximumDailyTransferQuote: number;
    cooldownSeconds: number;
  };
  snapshot: {
    equity_quote?: number;
    available_quote?: number;
    gross_exposure_quote?: number;
    net_exposure_quote?: number;
    drawdown_quote?: number;
    open_orders?: number;
    data_fresh?: boolean;
    runtime_managed?: boolean;
  } | null;
  paperBalance: number | null;
  workerStatus: string | null;
  containerState: string;
  runtime: {
    path: string;
    generatedAt: string | null;
    settlementAsset: string;
    totalQuote: number;
    availableQuote: number;
    openOrders: number;
    positions: number;
    candidateId: string | null;
    configHash: string | null;
    paperOnly: boolean;
  } | null;
  runtimeAgeSeconds: number | null;
  runtimeFresh: boolean;
}

export interface RoutingStrategySnapshot {
  strategyId: string;
  sleeve: string;
  accountIds: string[];
  allowedPairs: string[];
  compatibilityGroup: string;
  maximumInstancesPerAccount: number;
  evolutionStatus: string | null;
  evolutionStage: string | null;
  evolutionRunStatus: string | null;
  nextStep: string | null;
}

export interface RoutingAllocation {
  account_id: string;
  sleeve: string;
  strategy_id: string;
  candidate_id: string;
  config_hash: string;
  trading_pair: string;
  target_capital_quote: number;
  lifecycle_action: string;
  score: number;
  position_side: string;
}

export interface RoutingDecisionSnapshot {
  decision_id: string;
  generated_at: number;
  effective_at: number;
  expires_at: number;
  environment: string;
  allocations: RoutingAllocation[];
  reserve_quote: number;
  blocked_candidates: Array<Record<string, unknown>>;
  risk_blockers: string[];
  ai_applied: boolean;
  input_hash: string;
}

export interface RoutingTransferEvent {
  transfer_id: string;
  source_account_id: string;
  target_account_id: string;
  amount_quote: number;
  approved_by: string;
  requested_at: number;
  executed_at: number;
  status: string;
  balances_after?: Record<string, number>;
}

export interface RoutingAdminSnapshot {
  version: number;
  ok: boolean;
  error?: string;
  generatedAt: string;
  configPath: string;
  configValidated: boolean;
  environment: string;
  safety: {
    paperOnly: boolean;
    liveActions: boolean;
    automaticTransfers: boolean;
    manualTransferApproval: boolean;
    evolutionAutoStart: boolean;
    aiEnabled: boolean;
    aiMode: string;
    aiProvider: string;
    aiPrimaryModel: string;
  };
  router: {
    routeIntervalSeconds: number;
    requireClosedCandle: boolean;
    reserveQuotePct: number;
    minimumCandidateScore: number;
    switchPolicy: Record<string, number>;
  };
  routerHeartbeat: {
    status?: string;
    pid?: number;
    updated_at?: string;
    paper_only?: boolean;
    apply_workers?: boolean;
    iteration?: number;
    decision_id?: string;
    decision_expires_at?: number;
    market_symbol?: string;
    runtime_file?: string;
    config_path?: string;
    last_error?: string | null;
  };
  globalRisk: Record<string, number>;
  accounts: RoutingAccountSnapshot[];
  strategies: RoutingStrategySnapshot[];
  compatibility: Array<{
    left: string;
    right: string;
    relation: string;
    conditions: string[];
  }>;
  route: {
    mode: string | null;
    decisionAppended: boolean | null;
    releaseCount: number;
    candidateCount: number;
    plan: RoutingDecisionSnapshot;
    workerActions: Array<{
      account_id: string;
      worker_id: string;
      action: string;
      strategy_id?: string;
      candidate_id?: string;
      config_hash?: string;
      reason_codes: string[];
    }>;
    runtimeMappingApplied: boolean;
    fresh: boolean;
  };
  workers: Array<Record<string, unknown>>;
  lifecycle: Array<{
    record?: {
      account_id?: string;
      sleeve?: string;
      trading_pair?: string;
      state?: string;
      active_strategy_id?: string;
      desired_strategy_id?: string;
      confirmation_cycles?: number;
      last_error?: string | null;
    };
    last_decision_id?: string;
  }>;
  evolution: {
    generatedAt: string | null;
    summary: { total?: number; by_status?: Record<string, number> };
    strategies: Array<{
      strategy_id?: string;
      status?: string;
      stage_after?: string;
      run_status_after?: string;
      next_step?: string;
      paper_deployment?: {
        candidate_id?: string;
        config_hash?: string;
        status?: string;
        paper_only?: boolean;
        runtime_file?: string;
        rollback_reasons?: string[];
      } | null;
    }>;
    heartbeat: {
      status?: string;
      readiness_status?: string;
      safety_status?: string;
      safety_issues?: string[];
      last_activity?: string;
      last_success?: string;
      last_error?: string | null;
    };
    runtimeIdentity: {
      release_id?: string;
      source_sha256?: string;
      image_reference?: string;
    } | null;
  };
  releases: Array<{
    strategy_id?: string;
    candidate_id?: string;
    config_hash?: string;
    status?: string;
    paper_only?: boolean;
    runtime_file?: string;
    manifest_path?: string;
    rollback_reasons?: string[];
    rollback_recovered_at?: string;
    rollback_recovery?: {
      reasons?: string[];
      evidence_collected_at?: string;
      runtime_candidate_id?: string;
    };
  }>;
  decisions: RoutingDecisionSnapshot[];
  transfers: {
    balances: Record<string, number>;
    lastTransfer: Record<string, number>;
    events: RoutingTransferEvent[];
  };
  conflicts: string[];
}
