import { NetworkSelectionRequest } from '../services/common-interfaces';

export type Side = 'BUY' | 'SELL';
export interface PriceRequest extends NetworkSelectionRequest {
  quote: string;
  base: string;
  amount: string;
  side: Side;
}

export interface PriceResponse {
  network: string;
  timestamp: number;
  latency: number;
  base: string;
  quote: string;
  amount: string;
  expectedAmount: string;
  price: string;
  gasPrice: number;
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
}

export interface TradeResponse {
  network: string;
  timestamp: number;
  latency: number;
  base: string;
  quote: string;
  amount: string;
  expectedIn?: string;
  expectedOut?: string;
  price: string;
  gasPrice: number;
  gasLimit: number;
  gasCost: string;
  nonce: number;
  txHash: string | undefined;
}

export interface TradeErrorResponse {
  error: string;
  message: string;
}
