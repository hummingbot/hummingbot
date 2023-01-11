import { PerpPosition } from '../connectors/perp/perp';
import {
  NetworkSelectionRequest,
  PositionInfo as LPPositionInfo,
} from '../services/common-interfaces';
export type Side = 'BUY' | 'SELL';
export type PerpSide = 'LONG' | 'SHORT';

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
  nonce?: number;
  txHash: string | any | undefined;
}

export interface AddLiquidityRequest extends NetworkSelectionRequest {
  address: string;
  token0: string;
  token1: string;
  amount0: string;
  amount1: string;
  fee: string;
  lowerPrice: string; // integer as string
  upperPrice: string; // integer as string
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

export interface PositionResponse extends LPPositionInfo {
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

export interface PerpPricesResponse {
  base: string;
  quote: string;
  network: string;
  timestamp: number;
  latency: number;
  markPrice: string;
  indexPrice: string;
  indexTwapPrice: string;
}

export interface PerpMarketRequest extends NetworkSelectionRequest {
  quote: string;
  base: string;
}

export interface PerpMarketResponse {
  network: string;
  timestamp: number;
  latency: number;
  base: string;
  quote: string;
  isActive: boolean;
}

export interface PerpBalanceRequest extends NetworkSelectionRequest {
  address: string;
}

export interface PerpBalanceResponse {
  network: string;
  timestamp: number;
  latency: number;
  balance: string;
}

export interface PerpPositionRequest extends PerpMarketRequest {
  address: string;
}

export interface PerpPositionResponse extends PerpPosition {
  network: string;
  timestamp: number;
  latency: number;
  base: string;
  quote: string;
}

export interface PerpAvailablePairsResponse {
  network: string;
  timestamp: number;
  latency: number;
  pairs: string[];
}

export interface PerpCreateTakerRequest extends NetworkSelectionRequest {
  quote: string;
  base: string;
  address: string;
  amount?: string;
  side?: PerpSide;
  allowedSlippage?: string;
  nonce?: number;
}

export interface PerpCreateTakerResponse {
  network: string;
  timestamp: number;
  latency: number;
  base: string;
  quote: string;
  amount: string;
  gasPrice: number;
  gasPriceToken: string;
  gasLimit: number;
  gasCost: string;
  nonce: number;
  txHash: string | undefined;
}
