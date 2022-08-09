/* WIP */
import { Trade } from '@pangolindex/sdk';

export interface SifchainPriceResponse {
  network: string;
  timestamp: number;
  latency: number;
  base: string;
  quote: string;
  amount: string;
  expectedAmount: string;
  price: string;
  gasPrice: number;
  gasLimit: number;
  gasCost: string;
  trade: Trade;
}
