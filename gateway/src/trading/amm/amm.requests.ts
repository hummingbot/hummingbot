export interface NetworkSelectionRequest {
  connector: string; // the target connector (e.g. uniswap or pangolin)
  chain: string; // the target chain (e.g. ethereum or avalanche)
  network: string; // the target network of the chain (e.g. mainnet)
}

export type Side = 'BUY' | 'SELL';

export interface PriceRequest extends NetworkSelectionRequest {
  quote: string;
  base: string;
  amount: string;
  side: Side;
}

export interface PriceResponse {
  base: string;
  quote: string;
  amount: string;
  expectedAmount: string;
  price: string;
  network: string;
  timestamp: number;
  latency: number;
  gasPrice: number;
  gasLimit: number;
  gasCost: string;
}
