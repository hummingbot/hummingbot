/* WIP */
import { DecodedTxRaw } from '@cosmjs/proto-signing';

export interface CosmosBalanceRequest {
  address: string; // the user's Cosmos address as Bech32
  tokenSymbols: string[]; // a list of token symbol
}

export interface CosmosBalanceResponse {
  network: string;
  timestamp: number;
  latency: number;
  balances: Record<string, string>; // the balance should be a string encoded number
}

export interface CosmosTokenRequest {
  address: string;
  token: string;
}

export interface SolanaTokenResponse {
  network: string;
  timestamp: number;
  token: string; // the token symbol the spender will be approved for
  mintAddress: string;
  accountAddress?: string;
  amount?: string;
}

export interface CosmosPollRequest {
  txHash: string;
}

export enum TransactionResponseStatusCode {
  FAILED = -1,
  CONFIRMED = 1,
}

export interface CosmosPollResponse {
  network: string;
  timestamp: number;
  txHash: string;
  txData: DecodedTxRaw | null;
}
