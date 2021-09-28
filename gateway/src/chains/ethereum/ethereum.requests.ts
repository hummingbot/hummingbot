export interface EthereumNonceRequest {
  privateKey: string; // the users private Ethereum key
}

export interface EthereumAllowancesRequest {
  privateKey: string; // the users private Ethereum key
  spender: string; // the spender address for whom approvals are checked
  tokenSymbols: string[]; // a list of token symbol
}

export interface EthereumBalanceRequest {
  privateKey: string; // the users private Ethereum key
  tokenSymbols: string[]; // a list of token symbol
}

export interface EthereumApproveRequest {
  amount?: string; // the amount the spender will be approved to use
  nonce?: number; // the privateKey's next nonce
  privateKey: string; // the user's private Ethereum key
  spender: string; // the address of the spend (or a pre-defined string like 'uniswap', 'balancer', etc.)
  token: string; // the token symbol the spender will be approved for
}

export interface EthereumPollRequest {
  txHash: string;
}
