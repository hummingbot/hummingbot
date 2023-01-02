import { DecodedTxRaw } from '@cosmjs/proto-signing';
export interface CosmosBalanceRequest {
  address: string; // the user's Cosmos address as Bech32
  tokenSymbols: string[]; // a list of token symbol
}

export interface CosmosBalanceResponse {
  network: string;
  timestamp: number;
  latency: number;
  balances: Record<string, string>;
}

export interface CosmosTokenRequest {
  address: string;
  token: string;
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
  currentBlock: number;
  txBlock: number;
  gasUsed: number;
  gasWanted: number;
  txData: DecodedTxRaw | null;
}
