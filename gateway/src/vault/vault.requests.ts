import { NetworkSelectionRequest } from '../services/common-interfaces';

export interface PriceRequest extends NetworkSelectionRequest {
  tradeType: string;
  shares: number;
}

export interface PriceResponse {
  tradeType: string;
  shares: number;
  network: string;
  timestamp: number;
  latency: number;
  gasPrice: number;
  gasPriceToken: string;
  gasLimit: number;
  gasCost: string;
}

export type TradeRequest = NetworkSelectionRequest;

export interface TradeResponse {}

export interface EstimateGasResponse {
  network: string;
  timestamp: number;
  gasPrice: number;
  gasPriceToken: string;
  gasLimit: number;
  gasCost: string;
}
