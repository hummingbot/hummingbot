import { ethers, Transaction } from 'ethers';

export interface NetworkSelectionRequest {
  connector?: string; //the target connector (e.g. uniswap or pangolin)
  chain: string; //the target chain (e.g. ethereum or avalanche)
  network: string; // the target network of the chain (e.g. mainnet)
}
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
export interface BalanceRequest extends NetworkSelectionRequest {
  address: string; // the users public Ethereum key
  tokenSymbols: string[]; // a list of token symbol
}
export interface BalanceResponse {
  network: string;
  timestamp: number;
  latency: number;
  balances: Record<string, string>; // the balance should be a string encoded number
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

export type Side = 'BUY' | 'SELL';

export interface PriceRequest extends NetworkSelectionRequest {
  quote: string;
  base: string;
  amount: string;
  side: Side;
}

export interface PriceResponse {
  network: string;
  timestamp: number;
  latency: number;
  base: string;
  quote: string;
  amount: string;
  expectedAmount: string;
  price: string;
  gasPrice: number;
  gasLimit: number;
  gasCost: string;
}

export interface PollRequest extends NetworkSelectionRequest {
  txHash: string;
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

export interface TradeRequest extends NetworkSelectionRequest {
  quote: string;
  base: string;
  amount: string;
  address: string;
  side: Side;
  limitPrice?: string; // integer as string
  nonce?: number;
  maxFeePerGas?: string;
  maxPriorityFeePerGas?: string;
}

export interface TradeResponse {
  network: string;
  timestamp: number;
  latency: number;
  base: string;
  quote: string;
  amount: string;
  expectedIn?: string;
  expectedOut?: string;
  price: string;
  gasPrice: number;
  gasLimit: number;
  gasCost: string;
  nonce: number;
  txHash: string | undefined;
}

export interface TradeErrorResponse {
  error: string;
  message: string;
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

export interface CustomTransactionReceipt
  extends Omit<
    ethers.providers.TransactionReceipt,
    'gasUsed' | 'cumulativeGasUsed' | 'effectiveGasPrice'
  > {
  gasUsed: string;
  cumulativeGasUsed: string;
  effectiveGasPrice: string | null;
}

export interface CustomTransaction
  extends Omit<
    Transaction,
    'maxPriorityFeePerGas' | 'maxFeePerGas' | 'gasLimit' | 'value'
  > {
  maxPriorityFeePerGas: string | null;
  maxFeePerGas: string | null;
  gasLimit: string | null;
  value: string;
}

export interface CustomTransactionResponse
  extends Omit<
    ethers.providers.TransactionResponse,
    'gasPrice' | 'gasLimit' | 'value'
  > {
  gasPrice: string | null;
  gasLimit: string;
  value: string;
}
