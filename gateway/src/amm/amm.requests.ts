import {
  NetworkSelectionRequest,
  PositionInfo,
} from '../services/common-interfaces';
export type Side = 'BUY' | 'SELL';

export interface PriceRequest extends NetworkSelectionRequest {
  quote: string;
  base: string;
  amount: string;
  side: Side;
  allowedSlippage?: string;
}

export interface PriceResponse {
  base: string;
  quote: string;
  amount: string;
  rawAmount: string;
  expectedAmount: string;
  price: string;
  network: string;
  timestamp: number;
  latency: number;
  gasPrice: number;
  gasPriceToken: string;
  gasLimit: number;
  gasCost: string;
}

export interface PoolPriceRequest extends NetworkSelectionRequest {
  token0: string;
  token1: string;
  fee: string;
  period: number;
  interval: number;
}

export interface PoolPriceResponse {
  token0: string;
  token1: string;
  fee: string;
  period: number;
  interval: number;
  prices: string[];
  network: string;
  timestamp: number;
  latency: number;
}

export interface TradeRequest extends NetworkSelectionRequest {
  quote: string;
  base: string;
  amount: string;
  address: string;
  side: Side;
  limitPrice?: string; // integer as string
  nonce?: number;
  maxFeePerGas?: string;
  maxPriorityFeePerGas?: string;
  allowedSlippage?: string;
}

export interface TradeResponse {
  network: string;
  timestamp: number;
  latency: number;
  base: string;
  quote: string;
  amount: string;
  rawAmount: string;
  expectedIn?: string;
  expectedOut?: string;
  price: string;
  gasPrice: number;
  gasPriceToken: string;
  gasLimit: number;
  gasCost: string;
  nonce: number;
  txHash: string | undefined;
}

export interface AddLiquidityRequest extends NetworkSelectionRequest {
  address: string;
  token0: string;
  token1: string;
  amount0: string;
  amount1: string;
  fee: string;
  lowerPrice: number;
  upperPrice: number;
  tokenId?: number;
  nonce?: number;
  maxFeePerGas?: string;
  maxPriorityFeePerGas?: string;
}

export interface AddLiquidityResponse {
  network: string;
  timestamp: number;
  latency: number;
  token0: string;
  token1: string;
  fee: string;
  tokenId: number;
  gasPrice: number;
  gasPriceToken: string;
  gasLimit: number;
  gasCost: string;
  nonce: number;
  txHash: string | undefined;
}

export interface CollectEarnedFeesRequest extends NetworkSelectionRequest {
  address: string;
  tokenId: number;
  nonce?: number;
  maxFeePerGas?: string;
  maxPriorityFeePerGas?: string;
}

export interface RemoveLiquidityRequest extends CollectEarnedFeesRequest {
  decreasePercent?: number;
}

export interface RemoveLiquidityResponse {
  network: string;
  timestamp: number;
  latency: number;
  tokenId: number;
  gasPrice: number;
  gasPriceToken: string;
  gasLimit: number;
  gasCost: string;
  nonce: number;
  txHash: string | undefined;
}

export interface PositionRequest extends NetworkSelectionRequest {
  tokenId: number;
}

export interface PositionResponse extends PositionInfo {
  network: string;
  timestamp: number;
  latency: number;
}

export interface EstimateGasResponse {
  network: string;
  timestamp: number;
  gasPrice: number;
  gasPriceToken: string;
  gasLimit: number;
  gasCost: string;
}
