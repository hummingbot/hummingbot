import {
  NetworkSelectionRequest,
} from '../services/common-interfaces';

export interface PriceRequest extends NetworkSelectionRequest {
}

export interface PriceResponse {
}

export interface TradeRequest extends NetworkSelectionRequest {
}

export interface TradeResponse {
}

export interface EstimateGasResponse {
  network: string;
  timestamp: number;
  gasPrice: number;
  gasPriceToken: string;
  gasLimit: number;
  gasCost: string;
}
