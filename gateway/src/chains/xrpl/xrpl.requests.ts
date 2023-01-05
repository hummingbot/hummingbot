import { NetworkSelectionRequest } from '../../services/common-interfaces';
import { TxResponse } from 'xrpl';

export interface XRPLBalanceRequest extends NetworkSelectionRequest {
  address: string;
  tokenSymbols: string[];
}

export interface XRPLBalanceResponse {
  network: string;
  timestamp: number;
  latency: number;
  balances: Record<string, string>;
}

export interface XRPLTokenRequest extends NetworkSelectionRequest {
  address: string; // the user's Solana address as Base58
  token: string; // the token symbol the spender will be approved for
}

export interface XRPLTokenResponse {
  network: string;
  timestamp: number;
  token: string; // the token symbol the spender will be approved for
  mintAddress: string;
  accountAddress?: string;
  amount: string | null;
}

export interface XRPLPollRequest extends NetworkSelectionRequest {
  txHash: string;
}

export enum TransactionResponseStatusCode {
  FAILED = -1,
  CONFIRMED = 1,
}

export interface XRPLPollResponse {
  network: string;
  timestamp: number;
  currentLedgerIndex: number;
  txHash: string;
  txStatus: number;
  txLedgerIndex?: number;
  txData: TxResponse | null;
}
