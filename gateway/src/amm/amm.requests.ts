import { NetworkSelectionRequest } from '../services/common-interfaces';
import { PerpPosition } from '../connectors/perp/perp';
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

export interface PerpPricesResponse {
  base: string;
  quote: string;
  network: string;
  timestamp: number;
  latency: number;
  gasPrice: number;
  gasPriceToken: string;
  gasLimit: number;
  gasCost: string;
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

export interface EstimateGasResponse {
  network: string;
  timestamp: number;
  gasPrice: number;
  gasPriceToken: string;
  gasLimit: number;
  gasCost: string;
}
