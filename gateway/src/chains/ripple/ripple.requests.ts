import { NetworkSelectionRequest } from '../../services/common-interfaces';
import { TxResponse } from 'xrpl';

// export type RippleTransactionResponse = TransactionResponse;

export interface RippleBalanceRequest extends NetworkSelectionRequest {
  address: string;
  tokenSymbols: string[];
}

export interface RippleBalanceResponse {
  network: string;
  timestamp: number;
  latency: number;
  balances: Record<string, string>;
}

export interface RippleTokenRequest extends NetworkSelectionRequest {
  address: string; // the user's Solana address as Base58
  token: string; // the token symbol the spender will be approved for
}

export interface RippleTokenResponse {
  network: string;
  timestamp: number;
  token: string; // the token symbol the spender will be approved for
  mintAddress: string;
  accountAddress?: string;
  amount: string | null;
}

export interface RipplePollRequest extends NetworkSelectionRequest {
  txHash: string;
}

export interface RipplePollRequest extends NetworkSelectionRequest {
  txHash: string;
}

export enum TransactionResponseStatusCode {
  FAILED = -1,
  CONFIRMED = 1,
}

export interface RipplePollResponse {
  network: string;
  timestamp: number;
  currentLedgerIndex: number;
  txHash: string;
  txStatus: number;
  txLedgerIndex?: number;
  txData: TxResponse | null;
}
