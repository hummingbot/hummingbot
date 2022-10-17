import {
  TransactionEntryResponse,
  AccountLinesResponse,
} from 'xrpl';
import {
  CustomTransactionReceipt,
  CustomTransactionResponse,
  NetworkSelectionRequest,
} from '../../services/common-interfaces';

export type RippleTransactionResponse = TransactionEntryResponse;

export interface RippleBalanceRequest extends NetworkSelectionRequest {
  // the user's Ripple address as Base58
  address: string;
  // a list of trustlines to query
  linesSymbols: string[];
}

export interface RippleBalanceResponse {
  network: string;
  timestamp: number;
  latency: number;
  // should be a string encoded number
  balances: Record<string, string>;
}

export interface RippleTokenRequest extends NetworkSelectionRequest {
  // the user's Ripple address as Base58
  address: string;
  // the trustlines the spender will be approved for
  line: string;
}

export interface RippleTokenResponse {
  network: string;
  timestamp: number;
  token: string; // the token symbol the spender will be approved for
  mintAddress: string;
  accountAddress?: string;
  amount: string | null;
}

export interface SolanaPollRequest extends NetworkSelectionRequest {
  txHash: string;
}

export enum TransactionResponseStatusCode {
  FAILED = -1,
  CONFIRMED = 1,
}

export interface SolanaPollResponse {
  network: string;
  timestamp: number;
  currentBlock: number;
  txHash: string;
  txStatus: number;
  txBlock: number;
  txData: CustomTransactionResponse | null;
  txReceipt: CustomTransactionReceipt | null;
}
