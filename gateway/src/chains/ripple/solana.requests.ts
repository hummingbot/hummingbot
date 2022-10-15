import { TransactionResponse } from '@solana/web3.js';
import {
  CustomTransactionReceipt,
  CustomTransactionResponse,
  NetworkSelectionRequest,
} from '../../services/common-interfaces';

export type SolanaTransactionResponse = TransactionResponse;

export interface SolanaBalanceRequest extends NetworkSelectionRequest {
  address: string; // the user's Solana address as Base58
  tokenSymbols: string[]; // a list of token symbol
}

export interface SolanaBalanceResponse {
  network: string;
  timestamp: number;
  latency: number;
  balances: Record<string, string>; // the balance should be a string encoded number
}

export interface SolanaTokenRequest extends NetworkSelectionRequest {
  address: string; // the user's Solana address as Base58
  token: string; // the token symbol the spender will be approved for
}

export interface SolanaTokenResponse {
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
