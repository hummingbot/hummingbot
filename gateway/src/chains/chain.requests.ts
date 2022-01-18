export interface StatusRequest {
  chain: string; //the target chain (e.g. ethereum or avalanche)
  network: string; // the target network of the chain (e.g. mainnet)
}

export interface StatusResponse {
  chain: string;
  chainId: number;
  rpcUrl: string;
  currentBlockNumber: number;
}
