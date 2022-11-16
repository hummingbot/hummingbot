import { providers } from 'near-api-js';
import { NetworkSelectionRequest } from '../../services/common-interfaces';

export interface NonceRequest extends NetworkSelectionRequest {
  address: string; // the user's Near account Id
}

export interface NonceResponse {
  nonce: number; // the user's nonce
}

export interface NearBalanceRequest extends NetworkSelectionRequest {
  address: string; // the user's Near account Id
  tokenSymbols: string[]; // a list of token symbol
}

export interface BalanceRequest extends NetworkSelectionRequest {
  address: string; // the users Account Id
  tokenSymbols: string[]; // a list of token symbol
}

export interface BalanceResponse {
  network: string;
  timestamp: number;
  latency: number;
  balances: Record<string, string>; // the balance should be a string encoded number
}

export interface PollRequest {
  network: string; // the target network of the chain (e.g. mainnet)
  txHash: string;
  address: string;
}

export interface PollResponse {
  network: string;
  timestamp: number;
  currentBlock: number;
  txHash: string;
  txStatus: number;
  txReceipt: providers.FinalExecutionOutcome | null;
}

export interface CancelRequest extends NetworkSelectionRequest {
  nonce: number; // the nonce of the transaction to be canceled
  address: string; // the user's Near account Id
}

export interface CancelResponse {
  network: string;
  timestamp: number;
  latency: number;
  txHash: string | undefined;
}
