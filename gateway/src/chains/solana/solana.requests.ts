import ethers, { Transaction } from 'ethers';

// gasUsed and cumulativeGasUsed are BigNumbers
// then need to be converted to strings before being
// passed to the client
export interface EthereumTransactionReceipt
  extends Omit<
    ethers.providers.TransactionReceipt,
    'gasUsed' | 'cumulativeGasUsed' | 'effectiveGasPrice'
  > {
  gasUsed: string;
  cumulativeGasUsed: string;
  effectiveGasPrice: string | null;
}

export interface EthereumTransaction
  extends Omit<
    Transaction,
    'maxPriorityFeePerGas' | 'maxFeePerGas' | 'gasLimit' | 'value'
  > {
  maxPriorityFeePerGas: string | null;
  maxFeePerGas: string | null;
  gasLimit: string | null;
  value: string;
}

export interface EthereumTransactionResponse
  extends Omit<
    ethers.providers.TransactionResponse,
    'gasPrice' | 'gasLimit' | 'value'
  > {
  gasPrice: string | null;
  gasLimit: string;
  value: string;
}

export interface EthereumAllowancesRequest {
  privateKey: string; // the users private Ethereum key
  tokenSymbols: string[]; // a list of token symbol
}

export interface SolanaBalanceRequest {
  privateKey: string; // the users private Solana key in Base58
  tokenSymbols: string[]; // a list of token symbol
}

export interface SolanaBalanceResponse {
  network: string;
  timestamp: number;
  latency: number;
  balances: Record<string, string>; // the balance should be a string encoded number
}

export interface SolanaTokenRequest {
  token: string; // the token symbol the spender will be approved for
  privateKey: string | null; // the user's private Solana key
}

export interface SolanaTokenResponse {
  token: string; // the token symbol the spender will be approved for
  mintAddress: string;
  accountAddress: string;
  amount: number;
}

export interface EthereumPollRequest {
  txHash: string;
}

export interface EthereumPollResponse {
  network: string;
  timestamp: number;
  currentBlock: number;
  txHash: string;
  txStatus: number;
  txBlock: number;
  txData: EthereumTransactionResponse | null;
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
