import {
  CustomTransactionReceipt,
  CustomTransactionResponse,
  NetworkSelectionRequest,
} from '../services/common-interfaces';

import { TokenInfo } from '../services/ethereum-base';

export interface BalanceRequest extends NetworkSelectionRequest {
  address: string; // the users public Ethereum key
  tokenSymbols: string[]; // a list of token symbol
}

export interface BalanceResponse {
  network: string;
  timestamp: number;
  latency: number;
  balances: Record<string, string | null>; // the balance should be a string encoded number
}

export interface PollRequest extends NetworkSelectionRequest {
  txHash: string;
}

export interface PollResponse {
  network: string;
  timestamp: number;
  currentBlock: number;
  txHash: string;
  txStatus: number;
  txBlock: number;
  txData: CustomTransactionResponse | null;
  txReceipt: CustomTransactionReceipt | null;
}

export interface StatusRequest {
  chain?: string; //the target chain (e.g. ethereum, avalanche, or harmony)
  network?: string; // the target network of the chain (e.g. mainnet)
}

export interface StatusResponse {
  chain: string;
  chainId: number;
  rpcUrl: string;
  nativeCurrency: string;
  currentBlockNumber?: number; // only reachable if connected
}

export interface TokensRequest {
  chain?: string; //the target chain (e.g. ethereum, avalanche, or harmony)
  network?: string; // the target network of the chain (e.g. mainnet)
  tokenSymbols?: string[];
}

export interface TokensResponse {
  tokens: TokenInfo[];
}
