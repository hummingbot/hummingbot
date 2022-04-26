import {
  CustomTransaction,
  NetworkSelectionRequest,
} from '../services/common-interfaces';

export interface NonceRequest extends NetworkSelectionRequest {
  address: string; // the users public Ethereum key
}
export interface NonceResponse {
  nonce: number; // the user's nonce
}

export interface AllowancesRequest extends NetworkSelectionRequest {
  address: string; // the users public Ethereum key
  spender: string; // the spender address for whom approvals are checked
  tokenSymbols: string[]; // a list of token symbol
}

export interface AllowancesResponse {
  network: string;
  timestamp: number;
  latency: number;
  spender: string;
  approvals: Record<string, string>;
}

export interface ApproveRequest extends NetworkSelectionRequest {
  amount?: string; // the amount the spender will be approved to use
  nonce?: number; // the address's next nonce
  maxFeePerGas?: string;
  maxPriorityFeePerGas?: string;
  address: string; // the user's public Ethereum key
  spender: string; // the address of the spend (or a pre-defined string like 'uniswap', 'balancer', etc.)
  token: string; // the token symbol the spender will be approved for
}

export interface ApproveResponse {
  network: string;
  timestamp: number;
  latency: number;
  tokenAddress: string;
  spender: string;
  amount: string;
  nonce: number;
  approval: CustomTransaction;
}

export interface CancelRequest extends NetworkSelectionRequest {
  nonce: number; // the nonce of the transaction to be canceled
  address: string; // the user's public Ethereum key
}

export interface CancelResponse {
  network: string;
  timestamp: number;
  latency: number;
  txHash: string | undefined;
}
