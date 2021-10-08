import ethers, { Transaction } from 'ethers';

// gasUsed and cumulativeGasUsed are BigNumbers
// then need to be converted to strings before being
// passed to the client
export interface EthereumTransactionReceipt
  extends Omit<
    ethers.providers.TransactionReceipt,
    'gasUsed' | 'cumulativeGasUsed'
  > {
  gasUsed: string;
  cumulativeGasUsed: string;
}

export interface EthereumNonceRequest {
  privateKey: string; // the users private Ethereum key
}

export interface EthereumNonceResponse {
  nonce: number; // the user's nonce
}

export interface EthereumAllowancesRequest {
  privateKey: string; // the users private Ethereum key
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
  privateKey: string; // the users private Ethereum key
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
  nonce?: number; // the privateKey's next nonce
  privateKey: string; // the user's private Ethereum key
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
  approval: Transaction;
}

export interface EthereumPollRequest {
  txHash: string;
}

export interface EthereumPollResponse {
  network: string;
  timestamp: number;
  currentBlock: number;
  txStatus: number;
  txBlock: number;
  txData: ethers.providers.TransactionResponse | null;
  txReceipt: EthereumTransactionReceipt | null;
}

export interface EthereumCancelRequest {
  nonce: number; // the nonce of the transaction to be canceled
  privateKey: string; // the user's private Ethereum key
}

export interface EthereumCancelResponse {
  network: string;
  timestamp: number;
  latency: number;
  txHash: string | undefined;
}
