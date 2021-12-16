import ethers from 'ethers';

// gasUsed and cumulativeGasUsed are BigNumbers
// then need to be converted to strings before being
// passed to the client
export interface SolanaTransactionReceipt
  extends Omit<
    ethers.providers.TransactionReceipt,
    'gasUsed' | 'cumulativeGasUsed' | 'effectiveGasPrice'
  > {
  gasUsed: string;
  cumulativeGasUsed: string;
  effectiveGasPrice: string | null;
}
export interface SolanaTransactionResponse
  extends Omit<
    ethers.providers.TransactionResponse,
    'gasPrice' | 'gasLimit' | 'value'
  > {
  gasPrice: string | null;
  gasLimit: string;
  value: string;
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
  network: string;
  timestamp: number;
  token: string; // the token symbol the spender will be approved for
  mintAddress: string;
  accountAddress: string;
  amount: number;
}

export interface SolanaPollRequest {
  txHash: string;
}

export interface SolanaPollResponse {
  network: string;
  timestamp: number;
  currentBlock: number;
  txHash: string;
  txStatus: number;
  txBlock: number;
  txData: SolanaTransactionResponse | null;
  txReceipt: SolanaTransactionReceipt | null;
}
