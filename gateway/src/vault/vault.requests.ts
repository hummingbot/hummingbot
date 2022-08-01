import { NetworkSelectionRequest } from '../services/common-interfaces';

export interface PriceRequest extends NetworkSelectionRequest {
  tradeType: string;
  amount: number;
}

export interface PriceResponse {
  assetAmountWithFee: string;
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
