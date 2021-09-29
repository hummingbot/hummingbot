export type Side = 'BUY' | 'SELL';

export interface UniswapPriceRequest {
  quote: string;
  base: string;
  amount: string;
  side: Side;
}

export interface UniswapTradeRequest {
  quote: string;
  base: string;
  amount: string;
  privateKey: string;
  side: Side;
  limitPrice?: string; // integer as string
  nonce?: number;
}
