export interface NonceRequest {
  connector: string;
  chain: string;
  network: string;
  address: string; // the users public Ethereum key
}

export interface AllowancesRequest {
  connector: string;
  chain: string;
  network: string;
  address: string; // the users public Ethereum key
  spender: string; // the spender address for whom approvals are checked
  tokenSymbols: string[]; // a list of token symbol
}

export interface BalanceRequest {
  connector: string;
  chain: string;
  network: string;
  address: string; // the users public Ethereum key
  tokenSymbols: string[]; // a list of token symbol
}

export interface ApproveRequest {
  connector: string;
  chain: string;
  network: string;
  amount?: string; // the amount the spender will be approved to use
  nonce?: number; // the address's next nonce
  maxFeePerGas?: string;
  maxPriorityFeePerGas?: string;
  address: string; // the user's public Ethereum key
  spender: string; // the address of the spend (or a pre-defined string like 'uniswap', 'balancer', etc.)
  token: string; // the token symbol the spender will be approved for
}

export type Side = 'BUY' | 'SELL';

export interface PriceRequest {
  connector: string;
  chain: string;
  network: string;
  quote: string;
  base: string;
  amount: string;
  side: Side;
}
