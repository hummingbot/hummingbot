import ethers, { Transaction } from 'ethers';

// gasUsed and cumulativeGasUsed are BigNumbers
// then need to be converted to strings before being
// passed to the client
export interface HarmonyTransactionReceipt
  extends Omit<
    ethers.providers.TransactionReceipt,
    'gasUsed' | 'cumulativeGasUsed' | 'effectiveGasPrice'
  > {
  gasUsed: string;
  cumulativeGasUsed: string;
  effectiveGasPrice: string | null;
}

export interface HarmonyTransaction
  extends Omit<
    Transaction,
    'maxPriorityFeePerGas' | 'maxFeePerGas' | 'gasLimit' | 'value'
  > {
  maxPriorityFeePerGas: string | null;
  maxFeePerGas: string | null;
  gasLimit: string | null;
  value: string;
}

export interface HarmonyTransactionResponse
  extends Omit<
    ethers.providers.TransactionResponse,
    'gasPrice' | 'gasLimit' | 'value'
  > {
  gasPrice: string | null;
  gasLimit: string;
  value: string;
}

export interface HarmonyNonceRequest {
  address: string; // the users public Harmony key
}

export interface HarmonyNonceResponse {
  nonce: number; // the user's nonce
}

export interface HarmonyAllowancesRequest {
  address: string; // the users public Harmony key
  spender: string; // the spender address for whom approvals are checked
  tokenSymbols: string[]; // a list of token symbol
}

export interface HarmonyAllowancesResponse {
  network: string;
  timestamp: number;
  latency: number;
  spender: string;
  approvals: Record<string, string>;
}

export interface HarmonyBalanceRequest {
  address: string; // the users public Harmony key
  tokenSymbols: string[]; // a list of token symbol
}

export interface HarmonyBalanceResponse {
  network: string;
  timestamp: number;
  latency: number;
  balances: Record<string, string>; // the balance should be a string encoded number
}

export interface HarmonyApproveRequest {
  amount?: string; // the amount the spender will be approved to use
  nonce?: number; // the address's next nonce
  maxFeePerGas?: string;
  maxPriorityFeePerGas?: string;
  address: string; // the user's public Harmony key
  spender: string; // the address of the spend (or a pre-defined string like 'uniswap', 'balancer', etc.)
  token: string; // the token symbol the spender will be approved for
}

export interface HarmonyApproveResponse {
  network: string;
  timestamp: number;
  latency: number;
  tokenAddress: string;
  spender: string;
  amount: string;
  nonce: number;
  approval: HarmonyTransaction;
}

export interface HarmonyPollRequest {
  txHash: string;
}

export interface HarmonyPollResponse {
  network: string;
  timestamp: number;
  currentBlock: number;
  txHash: string;
  txStatus: number;
  txBlock: number;
  txData: HarmonyTransactionResponse | null;
  txReceipt: HarmonyTransactionReceipt | null;
}

export interface HarmonyCancelRequest {
  nonce: number; // the nonce of the transaction to be canceled
  address: string; // the user's public Harmony key
}

export interface HarmonyCancelResponse {
  network: string;
  timestamp: number;
  latency: number;
  txHash: string | undefined;
}
