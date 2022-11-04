import { NetworkSelectionRequest } from '../../services/common-interfaces';
import { TokenBalance } from './ripple';

// export type RippleTransactionResponse = TransactionResponse;

export interface RippleBalanceRequest extends NetworkSelectionRequest {
  address: string;
  tokenSymbols: string[];
}

export interface RippleBalanceResponse {
  network: string;
  timestamp: number;
  latency: number;
  balances: Array<TokenBalance>;
}
