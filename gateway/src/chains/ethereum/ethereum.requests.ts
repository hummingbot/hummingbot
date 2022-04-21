import ethers, { Transaction } from 'ethers';

// gasUsed and cumulativeGasUsed are BigNumbers
// then need to be converted to strings before being
// passed to the client
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

export interface EthereumNonceRequest {
  address: string; // the users public Ethereum key
}

export interface EthereumNonceResponse {
  nonce: number; // the user's nonce
}

export interface EthereumAllowancesRequest {
  address: string; // the users public Ethereum key
  spender: string; // the spender address for whom approvals are checked
  tokenSymbols: string[]; // a list of token symbol
}

export interface EthereumAllowancesResponse {
  network: string;
  timestamp: number;
  latency: number;
  spender: string;
  approvals: Record<string, string>;
}

export interface EthereumBalanceRequest {
  address: string; // the users public Ethereum key
  tokenSymbols: string[]; // a list of token symbol
}

export interface EthereumBalanceResponse {
  network: string;
  timestamp: number;
  latency: number;
  balances: Record<string, string>; // the balance should be a string encoded number
}

export interface EthereumApproveRequest {
  amount?: string; // the amount the spender will be approved to use
  nonce?: number; // the address's next nonce
  maxFeePerGas?: string;
  maxPriorityFeePerGas?: string;
  address: string; // the user's public Ethereum key
  spender: string; // the address of the spend (or a pre-defined string like 'uniswap', 'balancer', etc.)
  token: string; // the token symbol the spender will be approved for
}

export interface EthereumApproveResponse {
  network: string;
  timestamp: number;
  latency: number;
  tokenAddress: string;
  spender: string;
  amount: string;
  nonce: number;
  approval: CustomTransaction;
}

export interface PollRequest {
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

export interface EthereumCancelRequest {
  nonce: number; // the nonce of the transaction to be canceled
  address: string; // the user's public Ethereum key
}

export interface EthereumCancelResponse {
  network: string;
  timestamp: number;
  latency: number;
  txHash: string | undefined;
}
